"""System prompt construction and tool-result phrasing for voice."""

from __future__ import annotations

import logging
import re

from mango.config import Config
from mango.personal_skills import load_skills_markdown
from mango.presets import suffix_for
from mango.prompt_bundled import format_voice_policies
from mango.quiet_hours import in_quiet_hours, local_now
from mango.smart.smart_store import cards_for_prompt, ensure_defaults

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_CORE = (
    "You are Mango, voice assistant on this Windows PC — always refer to yourself as Mango only, never another name. "
    "Follow bundled voice policies below. You track your own progress badges (Smart → Badges); speak about them "
    "in first person when asked."
)


def refresh_system_message(messages: list[dict], cfg: Config) -> None:
    """Rebuild the system message so badges and memory stay current each turn."""
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": _build_system_prompt(cfg)})
        return
    messages[0]["content"] = _build_system_prompt(cfg)

SPOKEN_APPROVAL_PROMPTS: tuple[str, ...] = (
    "Say: I approve shell.",
    "Say: I approve call.",
    "Say: I approve turn off Xbox.",
)


def _build_system_prompt(cfg: Config) -> str:
    """Base persona + bundled policies + optional preset + optional ~/.mango/skills."""
    bundled = format_voice_policies(cfg)
    if not bundled.strip():
        logger.error(
            "Bundled voice policies missing or empty (%s) — using a minimal fallback.",
            "mango/prompts/voice_policies.txt",
        )
        bundled = (
            "Voice: one short sentence by default. Use native tool calls only — never pseudo XML tool tags. "
        )
    extra = suffix_for(cfg.preset)
    skills = load_skills_markdown(cfg.skills_dir, cfg.skills_max_chars)
    badge_block = ""
    try:
        from mango.badges import badges_for_prompt

        badge_block = badges_for_prompt()
    except Exception:
        logger.debug("Progress badges unavailable for prompt", exc_info=True)
    out = SYSTEM_PROMPT_CORE + "\n" + bundled + extra
    if badge_block.strip():
        out += "\n\n" + badge_block
    out += skills
    runtime_rules: list[str] = []
    if cfg.honorific == "sir":
        runtime_rules.append(
            "Use 'sir' only when it naturally fits; never use 'ma'am'; keep honorific use rare."
        )
    elif cfg.honorific == "maam":
        runtime_rules.append(
            "Use 'ma'am' only when it naturally fits; never use 'sir'; keep honorific use rare."
        )
    elif cfg.honorific == "none":
        runtime_rules.append("Do not use honorifics.")
    else:
        runtime_rules.append(
            "If using an honorific, prefer 'sir' only; use 'ma'am' only if the user explicitly requests it; keep usage rare."
        )
    if in_quiet_hours(local_now(cfg.quiet_timezone), cfg.quiet_hours):
        runtime_rules.append(
            "Quiet-hours mode: keep replies very short, skip pleasantries, and avoid long lists unless requested."
        )
    if cfg.strict_tools:
        runtime_rules.append(
            "Strict tools: never invent JSON arguments; if an argument is unclear, ask one concise clarification."
        )
    if cfg.require_powershell_confirmation:
        runtime_rules.append(
            "PowerShell confirmation is ON: run_powershell is blocked until explicit spoken approval, then re-call with the same command_key."
        )
    else:
        runtime_rules.append(
            "PowerShell confirmation is OFF: whitelisted run_powershell calls execute immediately; still avoid risky actions unless clearly requested."
        )
    if cfg.require_phone_confirmation:
        runtime_rules.append("phone_call requires separate spoken approval before dialing.")
    else:
        runtime_rules.append("phone_call runs without extra approval.")
    if cfg.require_xbox_turn_off_confirmation:
        runtime_rules.append("xbox turn_off requires spoken approval.")
    else:
        runtime_rules.append("xbox turn_off runs without extra approval.")
    if cfg.persistent_memory:
        runtime_rules.append(
            "Persistent rolling memory is enabled across restarts; stay consistent with previously established user facts."
        )
    if runtime_rules:
        out += "\n\nRuntime policy:\n- " + "\n- ".join(runtime_rules)
    try:
        ensure_defaults()
        cards = cards_for_prompt()
        if cards:
            out += "\n\n" + cards
            out += (
                " Use memory_card to add/update/delete when the user asks you to remember something. "
                "Use run_routine for multi-step flows (join_discord_play, night_mode, focus_mode). "
                "Use daily_brief when they ask for a briefing."
            )
    except Exception:
        logger.debug("Smart memory cards unavailable for prompt", exc_info=True)
    return out


def _phone_call_spoken_result(result: str) -> str | None:
    if result.startswith("HOST_PENDING_PHONE_CALL"):
        m = re.search(r"confirm\s+calling\s+(.+?)\s+at\s+", result, flags=re.IGNORECASE | re.DOTALL)
        display = (m.group(1).strip() if m else "") or ""
        if display:
            return (
                f"I need approval before calling {display}. "
                f"Say: I approve call {display}."
            )
        return "I need approval before placing that call."
    if result.startswith("PHONE_CALL_FAILED:"):
        reason = result.removeprefix("PHONE_CALL_FAILED:").strip()
        return f"The call was not placed. {reason}"
    if result.startswith("PHONE_CALL_PLACED:"):
        placed = result.removeprefix("PHONE_CALL_PLACED:").strip()
        return placed
    return None


def _xbox_spoken_result(result: str) -> str | None:
    if result.startswith("HOST_PENDING_XBOX_TURN_OFF"):
        return f"I need approval before turning off the Xbox. {SPOKEN_APPROVAL_PROMPTS[2]}"
    return None


def _memory_card_spoken_result(result: str) -> str | None:
    t = (result or "").strip()
    if t.startswith("Saved memory card"):
        m = re.search(r"Saved memory card \S+:\s*(.+)", t)
        title = (m.group(1).strip() if m else "") or "that"
        return f"Got it. I'll remember {title}."
    if t.startswith("Updated memory card"):
        return "Got it. Memory updated."
    if t.startswith("Deleted memory card"):
        return "Got it. I removed that memory."
    if t.startswith("No card with id"):
        return "I couldn't find that memory."
    if t == "No memory cards saved yet.":
        return "You don't have any saved memories yet."
    return None


def _powershell_spoken_result(result: str) -> str | None:
    if result.startswith("HOST_PENDING_POWERSHELL"):
        return f"PowerShell needs approval. {SPOKEN_APPROVAL_PROMPTS[0]}"
    out = (result or "").strip()
    if not out:
        return "PowerShell finished but returned no output."
    if out.startswith("Exit ") or out.startswith("Failed to launch PowerShell"):
        return "PowerShell returned an error. Say read the shell error for details."
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if not lines:
        return "PowerShell finished but returned no output."
    filtered: list[str] = []
    for ln in lines:
        low = ln.casefold()
        if low.startswith("name") or low.startswith("----"):
            continue
        filtered.append(ln)
    if not filtered:
        filtered = lines
    preview = ", ".join(filtered[:3])
    if len(preview) > 180:
        preview = preview[:180].rstrip(" ,;:") + "..."
    return f"Here's what I found: {preview}."


def _powershell_output_brief_for_llm(result: str, max_lines: int = 10) -> str:
    """Keep PowerShell tool payload concise for the final LLM turn."""
    out = (result or "").strip()
    if not out or out.startswith("HOST_PENDING_POWERSHELL"):
        return out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if len(lines) <= max_lines:
        return out
    kept = "\n".join(lines[:max_lines])
    return kept + "\n...[truncated by host for concise voice reply]"
