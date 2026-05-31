"""Collect tool JSON schemas and dispatch execution."""

from __future__ import annotations

import logging
from typing import Any

from mango.config import Config
from mango.tool_cooldowns import check_tool_cooldown, record_tool_run
from mango.tool_dispatch.simple_tools import dispatch_simple_tool
from mango.integration_services import (
    DiscordVoiceToolService,
    HandoffRouterService,
    XboxConsoleToolService,
)
from mango.metrics import emit_metric
from mango.tool_narration import (
    narrate_tool_after,
    narrate_tool_before,
    routine_intro_line,
    speak_progress,
    suppress_tool_narration,
)
from mango.smart.smart_timeline import record_tool_done, record_tool_start
from mango.tool_definitions import build_tool_definitions
from mango.tool_policy import (
    _DISCORD_JOIN_OTHER_HINTS,
    _DISCORD_MUSIC_HINTS,
    _DISCORD_PING_HINTS,
    _ERR_TOOL_BAD_ARGS,
    _ERR_TOOL_EXCEPTION,
    _SENSITIVE_TOOL_OUTPUTS,
    _TOOL_HANDOFF_DOMAIN,
    _affirmative,
    _clipboard_intent,
    _contact_info_intent,
    _has_any_hint,
    _last_user_text,
)
from mango.tool_policy import (
    risk_level as policy_risk_level,
)
from mango.tools import (
    phone_call,
    read_clipboard,
    run_powershell,
    run_routine,
    saved_contact_phone,
    search_files,
    web_search,
)

logger = logging.getLogger(__name__)


def _truncate_tool_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 40)] + "\n…[truncated by Mango host]"


class ToolRegistry:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._discord_voice_service = DiscordVoiceToolService()
        self._xbox_console_service = XboxConsoleToolService()
        self._handoff_router = HandoffRouterService()
        run_routine.set_registry(self)
        self._shell_gate_pending = False
        self._shell_gate_key: str | None = None
        self._powershell_one_shot = False
        self._phone_gate_pending = False
        self._phone_gate_key: tuple[str, str] | None = None
        self._phone_one_shot = False
        self._xbox_turn_off_pending = False
        self._xbox_turn_off_key: str | None = None
        self._xbox_turn_off_one_shot = False
        self._last_tool_run: dict[str, float] = {}

    def requires_tool_confirmation(self, tool_name: str | None = None) -> bool:
        """Return whether spoken confirmation is required for a specific tool (or any tool)."""
        if tool_name == "run_powershell":
            return self._cfg.require_powershell_confirmation
        if tool_name == "phone_call":
            return self._cfg.require_phone_confirmation
        if tool_name == "xbox_console":
            return self._cfg.require_xbox_turn_off_confirmation
        return (
            self._cfg.require_powershell_confirmation
            or self._cfg.require_phone_confirmation
            or self._cfg.require_xbox_turn_off_confirmation
        )

    def has_pending_confirmation(self) -> bool:
        """Return True when any host-gated confirmation is currently pending."""
        return (
            self._shell_gate_pending
            or self._phone_gate_pending
            or self._xbox_turn_off_pending
        )

    def risk_level(self, tool_name: str) -> str:
        return policy_risk_level(tool_name)

    def _emit_tool_done(
        self,
        name: str,
        risk: str,
        *,
        ok: bool,
        out: str = "",
        error_code: str | None = None,
    ) -> None:
        preview = (out or "").replace("\n", " ")[:240]
        entry = record_tool_done(
            name,
            risk=risk,
            ok=ok,
            error_code=error_code,
            result_preview=preview,
        )
        fields: dict[str, Any] = {"tool": name, "risk": risk, "ok": ok}
        if error_code:
            fields["error_code"] = error_code
        if entry and entry.get("duration_ms") is not None:
            fields["duration_ms"] = entry["duration_ms"]
        emit_metric("tool_done", **fields)

    def try_arm_powershell_from_user(self, user_text: str) -> None:
        """After STT: if user affirms while a shell request is pending, arm one approved execution."""
        if _affirmative(user_text, tool_name="run_powershell") and self._shell_gate_pending and self._shell_gate_key:
            self._powershell_one_shot = True
            logger.info(
                "PowerShell approval armed for command_key=%r from user text.",
                self._shell_gate_key,
            )
        if _affirmative(user_text, tool_name="phone_call") and self._phone_gate_pending and self._phone_gate_key:
            self._phone_one_shot = True
            logger.warning("Phone call approval armed for contact=%r.", self._phone_gate_key[0])
        if _affirmative(user_text, tool_name="xbox_console") and self._xbox_turn_off_pending and self._xbox_turn_off_key:
            self._xbox_turn_off_one_shot = True
            logger.warning("Xbox turn-off approval armed for device=%r.", self._xbox_turn_off_key)

    def definitions(self) -> list[dict[str, Any]]:
        return build_tool_definitions(
            self._cfg,
            self._cfg.owner_display_name,
            self._cfg.phone_contact_slugs,
            disabled_tools=self._cfg.disabled_tools,
        )

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        conversation_messages: list[dict[str, Any]] | None = None,
    ) -> str:
        if name in self._cfg.disabled_tools:
            risk = self.risk_level(name)
            self._emit_tool_done(
                name,
                risk,
                ok=False,
                error_code="ERR_TOOL_DISABLED",
            )
            return (
                f"ERR_TOOL_DISABLED:{name} is turned off on this PC "
                "(remove it from MANGO_DISABLED_TOOLS to enable)."
            )
        cooldown_msg = check_tool_cooldown(self._last_tool_run, name)
        if cooldown_msg:
            risk = self.risk_level(name)
            self._emit_tool_done(name, risk, ok=False, error_code="ERR_TOOL_COOLDOWN")
            return cooldown_msg
        risk = self.risk_level(name)
        if name == "run_powershell":
            logger.info(
                "Executing tool %r risk=%s args=%s",
                name,
                risk,
                {"command_key": arguments.get("command_key")},
            )
        else:
            logger.info("Executing tool %r risk=%s args=%s", name, risk, arguments)
        record_tool_start(name, risk=risk)
        emit_metric("tool_start", tool=name, risk=risk)
        if narrate_tool_before(name, arguments):
            self._emit_tool_done(name, risk, ok=False, error_code="ERR_USER_INTERRUPT")
            return "Interrupted by user."
        last_user = _last_user_text(conversation_messages)
        domain = _TOOL_HANDOFF_DOMAIN.get(name)
        if domain:
            ok, reason = self._handoff_router.validate(domain, arguments)
            if not ok:
                self._emit_tool_done(
                    name,
                    risk,
                    ok=False,
                    error_code="ERR_TOOL_HANDOFF_CONTRACT",
                )
                return f"ERR_TOOL_HANDOFF_CONTRACT:{name}:{reason}"
        try:
            simple_out = dispatch_simple_tool(name, arguments, self._cfg)
            if simple_out is not None:
                out = simple_out
            elif name == "discord_voice":
                args = dict(arguments)
                if not self._cfg.discord_relax_intent_gates:
                    action = str(args.get("action") or "").strip().lower()
                    if action in ("music_start", "music_resume") and not _has_any_hint(
                        last_user,
                        _DISCORD_MUSIC_HINTS,
                    ):
                        out = (
                            "Host blocked Discord music stream: the user did not clearly ask to stream/play music "
                            "or audio into Discord."
                        )
                        return out
                    if args.get("ping_friend_user_ids") and not _has_any_hint(
                        last_user,
                        _DISCORD_PING_HINTS,
                    ):
                        args.pop("ping_friend_user_ids", None)
                    if args.get("allow_join_other_sessions") and not _has_any_hint(
                        last_user,
                        _DISCORD_JOIN_OTHER_HINTS,
                    ):
                        args["allow_join_other_sessions"] = False
                args["_host_control_timeout_s"] = self._cfg.discord_control_timeout_s
                args["_host_bridge_poll_interval_s"] = self._cfg.discord_bridge_poll_interval_s
                args["_host_bridge_wait_seconds"] = max(60.0, self._cfg.http_timeout_long_s)
                out = self._discord_voice_service.run(**args)
            elif name == "search_files":
                out = search_files.run(
                    self._cfg.search_roots,
                    self._cfg.search_max_results,
                    **arguments,
                )
            elif name == "web_search":
                q = (arguments.get("query") or "").strip()
                cap = max(1, min(int(self._cfg.search_max_results), 8))
                out = web_search.run(q, max_results=cap)
            elif name == "run_routine":
                act = str(arguments.get("action") or "").strip().lower()
                rid = str(arguments.get("routine_id") or "").strip()
                if act == "run" and rid:
                    intro = routine_intro_line(rid)
                    if intro:
                        speak_progress(intro, prefer_discord=False)
                with suppress_tool_narration():
                    out = run_routine.run(
                        **arguments,
                        conversation_messages=conversation_messages,
                    )
            elif name == "read_clipboard":
                if self._cfg.clipboard_require_intent and not _clipboard_intent(last_user):
                    out = (
                        "Host blocked clipboard read: the user did not clearly ask about the clipboard "
                        "or pasted content. Ask them to say e.g. what's on my clipboard."
                    )
                else:
                    out = read_clipboard.run()
            elif name == "run_powershell":
                key = (arguments.get("command_key") or "").strip()
                if self._cfg.require_powershell_confirmation:
                    approved = self._powershell_one_shot and self._shell_gate_pending
                    same_pending_command = bool(self._shell_gate_key) and key == self._shell_gate_key
                    if approved and not same_pending_command:
                        logger.warning(
                            "PowerShell approval blocked due to command_key mismatch "
                            "(pending=%r requested=%r).",
                            self._shell_gate_key,
                            key,
                        )
                        out = (
                            "HOST_PENDING_POWERSHELL: approval was for a different command. "
                            f"Re-run command_key={self._shell_gate_key} or ask for a new approval."
                        )
                        self._shell_gate_pending = True
                        self._powershell_one_shot = False
                        self._emit_tool_done(
                            name,
                            risk,
                            ok=False,
                            error_code="ERR_TOOL_CONFIRMATION_MISMATCH",
                        )
                        return out
                    if approved and same_pending_command:
                        self._powershell_one_shot = False
                        self._shell_gate_pending = False
                        self._shell_gate_key = None
                else:
                    approved = True
                out = run_powershell.run(key, _host_approved=approved)
                if (
                    self._cfg.require_powershell_confirmation
                    and not approved
                    and out.startswith("HOST_PENDING_POWERSHELL")
                ):
                    self._shell_gate_pending = True
                    self._shell_gate_key = key
                    self._powershell_one_shot = False
            elif name == "saved_contact_phone":
                contact = str(arguments.get("contact") or "").strip().casefold()
                if self._cfg.contact_info_require_intent and not _contact_info_intent(last_user):
                    out = (
                        "Host blocked contact info read: the user did not clearly ask for a phone number "
                        "or contact details. Ask them to say e.g. what is Ariana's phone number."
                    )
                else:
                    out = saved_contact_phone.run(
                        contact,
                        _allowed_contacts=self._cfg.phone_contact_slugs,
                    )
            elif name == "phone_call":
                contact = str(arguments.get("contact") or "").strip().casefold()
                message = str(arguments.get("message") or "").strip()
                key = (contact, message)
                pending_contact = self._phone_gate_key[0] if self._phone_gate_key else None
                pending_message = self._phone_gate_key[1] if self._phone_gate_key else None
                same_pending_message = (message == pending_message) or (
                    not message and not pending_message
                )
                same_pending_call = (
                    bool(self._phone_gate_key)
                    and contact == pending_contact
                    and same_pending_message
                )
                if self._cfg.require_phone_confirmation:
                    approved = self._phone_one_shot and same_pending_call
                    if approved:
                        self._phone_one_shot = False
                        self._phone_gate_pending = False
                        self._phone_gate_key = None
                else:
                    approved = True
                out = phone_call.run(
                    contact,
                    message,
                    _host_approved=approved,
                    _allowed_contacts=self._cfg.phone_contact_slugs,
                )
                if (
                    self._cfg.require_phone_confirmation
                    and not approved
                    and out.startswith("HOST_PENDING_PHONE_CALL")
                ):
                    self._phone_gate_pending = True
                    self._phone_gate_key = key
                    self._phone_one_shot = False
            elif name == "xbox_console":
                action = str(arguments.get("action") or "").strip().casefold()
                device_key = str(arguments.get("device_id") or "default").strip() or "default"
                if action == "turn_off" and not self._cfg.require_xbox_turn_off_confirmation:
                    out = self._xbox_console_service.run(**arguments, _host_approved=True)
                elif action == "turn_off":
                    same_pending_turn_off = (
                        bool(self._xbox_turn_off_key)
                        and (
                            self._xbox_turn_off_key == "default"
                            or self._xbox_turn_off_key == device_key
                        )
                    )
                    approved = self._xbox_turn_off_one_shot and same_pending_turn_off
                    if approved:
                        self._xbox_turn_off_one_shot = False
                        self._xbox_turn_off_pending = False
                        self._xbox_turn_off_key = None
                    out = self._xbox_console_service.run(**arguments, _host_approved=approved)
                    if not approved and out.startswith("HOST_PENDING_XBOX_TURN_OFF"):
                        self._xbox_turn_off_pending = True
                        self._xbox_turn_off_key = device_key
                        self._xbox_turn_off_one_shot = False
                else:
                    out = self._xbox_console_service.run(**arguments, _host_approved=False)
            else:
                out = f"Unknown tool {name!r}."
                logger.error("%s", out)
                return out

            out = _truncate_tool_text(out, self._cfg.max_tool_output_chars)
            if name in _SENSITIVE_TOOL_OUTPUTS:
                logger.info("Tool %r finished ok result_len=%d (preview suppressed)", name, len(out))
            else:
                preview = out[:500] + ("…" if len(out) > 500 else "")
                logger.info(
                    "Tool %r finished ok result_len=%d preview=%r",
                    name,
                    len(out),
                    preview,
                )
            self._emit_tool_done(name, risk, ok=True, out=out)
            record_tool_run(self._last_tool_run, name)
            narrate_tool_after(name, arguments, out)
            return out
        except TypeError as exc:
            logger.warning(
                "Tool %r argument mismatch: %s",
                name,
                exc,
                exc_info=True,
            )
            self._emit_tool_done(name, risk, ok=False, error_code=_ERR_TOOL_BAD_ARGS)
            return f"{_ERR_TOOL_BAD_ARGS}:{name}:{exc}"
        except Exception as exc:
            logger.exception("Tool %r raised unexpectedly", name)
            self._emit_tool_done(name, risk, ok=False, error_code=_ERR_TOOL_EXCEPTION)
            return f"{_ERR_TOOL_EXCEPTION}:{name}:{exc}"
