"""LLM chat with native tool calls and spoken reply synthesis."""

from __future__ import annotations

from contextlib import nullcontext
import json
import logging
import os
import re
import uuid
from urllib.parse import urlparse
from collections.abc import Callable
from typing import Any

from groq import BadRequestError

from mango.llm import (
    GroqLLM,
    OllamaLLM,
    assistant_message_as_dict,
    parse_tool_arguments,
)
from mango.planner_executor import PlannerExecutorState, StepState
from mango.tool_recovery import (
    KNOWN_TOOL_NAMES,
    recover_from_groq_tool_use_failed,
    strip_pseudo_tool_markup_for_speech,
    split_assistant_content_and_pseudo_tool,
)
from mango.badge_fastpath import try_fast_badge_status
from mango.discord_play_fastpath import (
    summarize_routine_result,
    try_fast_discord_play_routine,
)
from mango.social_fastpath import try_fast_social_reply
from mango.tool_narration import suppress_tool_narration
from mango.tool_registry import ToolRegistry
from mango.voice_prompt import (
    _memory_card_spoken_result,
    _phone_call_spoken_result,
    _powershell_output_brief_for_llm,
    _powershell_spoken_result,
    _xbox_spoken_result,
    SPOKEN_APPROVAL_PROMPTS,
)

logger = logging.getLogger(__name__)

_THANKS_TOKENS = ("thanks", "thank you", "thx", "ty")
_BYE_TOKENS = ("bye", "goodbye", "see you", "later")
_OK_TOKENS = ("ok", "okay", "cool", "got it")
_APPROVAL_FOLLOWUP_MARKERS = tuple(
    p.casefold().replace(".", "") for p in SPOKEN_APPROVAL_PROMPTS
) + ("say: i approve call ",)
_NO_MEMORY_DISCLAIMER_RE = re.compile(
    r"(don't have the ability to recall|cannot recall|can't recall|new conversation|each time you interact)",
    re.IGNORECASE,
)
_NO_OPINION_DISCLAIMER_RE = re.compile(
    r"(don't have personal thoughts|don't have personal opinions|cannot have opinions|as an ai[^.]*opinions?|don't think about my own code|i don't think about)",
    re.IGNORECASE,
)
_ROBOTIC_TELLS_RE = re.compile(
    r"^(certainly|absolutely|as an ai|i'm here to help|i am here to help)\b",
    re.IGNORECASE,
)

_TOOL_SPOKEN_LABELS: dict[str, str] = {
    "daily_brief": "a daily briefing",
    "badge_status": "my badge progress",
    "run_powershell": "that command",
    "phone_call": "that phone call",
    "saved_contact_phone": "that contact lookup",
    "open_app": "that app action",
    "discord_voice": "that Discord action",
    "spotify_play": "that music request",
    "xbox_console": "that Xbox request",
    "globe_view": "that map request",
    "globe_state": "that map action",
}


def _source_cues_enabled() -> bool:
    raw = os.getenv("MANGO_SOURCE_CUES", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _route_hint_for_round(user_text: str, round_idx: int, step_count: int) -> str:
    """Small heuristic for model routing: fast for simple first-turn chat, complex for loops."""
    text = (user_text or "").strip()
    if round_idx > 1 or step_count >= 1:
        return "complex"
    if not text:
        return "default"
    if len(text) <= 80 and "?" not in text and "," not in text:
        return "fast"
    return "default"


def _extract_source_cues(tool_name: str, result: str) -> list[str]:
    if tool_name != "web_search":
        return []
    cues: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"^\s*\d+\.\s+.*\n\s+(https?://\S+)", result or "", re.MULTILINE):
        url = m.group(1).rstrip(".,)")
        try:
            host = urlparse(url).netloc.lower()
            if host.startswith("www."):
                host = host[4:]
        except Exception:
            host = ""
        key = host.casefold()
        if not host or key in seen:
            continue
        seen.add(key)
        cues.append(host)
        if len(cues) >= 3:
            break
    return cues


def _with_source_cues(spoken: str, source_cues: list[str]) -> str:
    if not spoken or not source_cues or not _source_cues_enabled():
        return spoken
    if re.search(r"\b(sources?|according to|from)\b", spoken, re.IGNORECASE):
        return spoken
    if len(spoken) > 220:
        return spoken
    host = source_cues[0]
    site = (host.split(".")[0] if host else "").strip()
    if not site:
        return spoken
    label = site[0].upper() + site[1:]
    return f"{spoken} That's from {label}."


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _memory_reply_fallback(user_text: str) -> str:
    if "yesterday" in (user_text or "").casefold():
        return "Happy to talk about yesterday. Tell me what happened and I'll pick it up from there."
    return "What part should I pick back up?"


def _opinion_reply_fallback(user_text: str) -> str:
    del user_text
    return "My take: I'm getting better at voice replies, and I still have room to polish."


def _strip_opinion_disclaimer(text: str) -> tuple[str, bool]:
    if not _NO_OPINION_DISCLAIMER_RE.search(text):
        return text, False
    m = re.search(r",\s*but\s+(.+)$", text.strip(), re.IGNORECASE)
    if m:
        tail = m.group(1).strip()
        if tail and not _NO_OPINION_DISCLAIMER_RE.search(tail):
            if tail[0].islower():
                tail = tail[0].upper() + tail[1:]
            return tail, True
    cleaned, _, saw = _strip_disclaimer_sentences(text, memory=False, opinion=True)
    return cleaned, saw or bool(_NO_OPINION_DISCLAIMER_RE.search(text))


def _strip_memory_disclaimer(text: str) -> tuple[str, bool]:
    if not _NO_MEMORY_DISCLAIMER_RE.search(text):
        return text, False
    cleaned, saw, _ = _strip_disclaimer_sentences(text, memory=True, opinion=False)
    return cleaned, saw or bool(_NO_MEMORY_DISCLAIMER_RE.search(text))


def _strip_disclaimer_sentences(text: str, *, memory: bool, opinion: bool) -> tuple[str, bool, bool]:
    kept: list[str] = []
    saw_memory = False
    saw_opinion = False
    for sentence in _split_sentences(text):
        if memory and _NO_MEMORY_DISCLAIMER_RE.search(sentence):
            saw_memory = True
            continue
        if opinion and _NO_OPINION_DISCLAIMER_RE.search(sentence):
            saw_opinion = True
            continue
        kept.append(sentence)
    return " ".join(kept).strip(), saw_memory, saw_opinion


def _track_hint_from_result(result: str) -> str:
    m = re.search(r"track_played:\s*(.+)", result or "", re.IGNORECASE)
    if m:
        return m.group(1).strip()[:90]
    return ""


def _deterministic_tool_spoken_result(
    name: str,
    args: dict[str, Any],
    result: str,
    *,
    user_text: str = "",
) -> str | None:
    t = (result or "").strip()
    low = t.casefold()
    if not t or low.startswith("err") or "failed" in low[:60]:
        return None
    if name == "phone_call":
        return _phone_call_spoken_result(result)
    if name == "memory_card":
        return _memory_card_spoken_result(result)
    if name == "xbox_console":
        return _xbox_spoken_result(result)
    if name == "run_powershell":
        return _powershell_spoken_result(result)
    if name == "spotify_play":
        hint = _track_hint_from_result(result)
        if hint:
            return f"All set. Playing {hint}."
        if "playing" in low or "spotify" in low:
            return "All set. Spotify is playing."
    if name == "open_app":
        app = str(args.get("app_name") or args.get("app") or args.get("name") or "that app").strip()
        return f"All set. {app} is open."
    if name == "close_app":
        app = str(args.get("app") or args.get("name") or "that app").strip()
        return f"All set. {app} is closed."
    if name == "volume_control":
        act = str(args.get("action") or "").strip().lower()
        if act == "set":
            val = args.get("percent")
            try:
                pct = int(val)
                return f"All set. Volume is {pct} percent."
            except (TypeError, ValueError):
                return "All set. Volume adjusted."
        if act in ("mute", "toggle_mute"):
            return "All set. Audio is muted."
        if act == "unmute":
            return "All set. Audio is on."
    if name == "badge_status":
        from mango.badges import format_badge_reply

        return format_badge_reply(user_text)
    return None


def _tool_spoken_label(name: str) -> str:
    key = (name or "").strip()
    if not key:
        return "that request"
    return _TOOL_SPOKEN_LABELS.get(key, "that request")


def _empty_reply_fallback(user_text: str) -> str:
    from mango.badge_fastpath import parse_badge_intent
    from mango.social_fastpath import format_social_reply, parse_social_intent

    if parse_social_intent(user_text):
        return format_social_reply(user_text)
    if parse_badge_intent(user_text):
        from mango.badges import format_badge_reply

        return format_badge_reply(user_text)
    t = (user_text or "").strip().casefold()
    seed = t or "empty"
    if any(tok in t for tok in _THANKS_TOKENS):
        return _pick_fallback(seed, "You're welcome.", "Anytime.", "Happy to help.")
    if any(tok in t for tok in _BYE_TOKENS):
        return _pick_fallback(seed, "See you soon.", "Talk later.", "Bye for now.")
    if any(tok == t for tok in _OK_TOKENS):
        return _pick_fallback(seed, "Got it.", "Okay.", "Sure.")
    return _pick_fallback(seed, "Could you rephrase that?", "Say that another way?", "What did you mean?")


def _pick_fallback(seed: str, *lines: str) -> str:
    if not lines:
        return "Could you rephrase that?"
    return lines[sum(ord(c) for c in seed) % len(lines)]


def _sanitize_model_reply(text: str, user_text: str) -> str:
    out = (text or "").strip()
    if not out:
        return out
    had_memory = bool(_NO_MEMORY_DISCLAIMER_RE.search(out))
    had_opinion = bool(_NO_OPINION_DISCLAIMER_RE.search(out))
    if had_memory:
        out, had_memory = _strip_memory_disclaimer(out)
    if had_opinion:
        out, had_opinion = _strip_opinion_disclaimer(out)
    if _ROBOTIC_TELLS_RE.search(out):
        out = _ROBOTIC_TELLS_RE.sub("", out, count=1).lstrip(" ,.-")
    out = " ".join(out.split()).strip()
    if out:
        return out
    if had_memory:
        return _memory_reply_fallback(user_text)
    if had_opinion:
        return _opinion_reply_fallback(user_text)
    return out


def _last_assistant_reply(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "assistant":
            return str(m.get("content") or "")
    return ""


def _finalize_spoken_reply(text: str, user_text: str, previous_assistant: str = "") -> str:
    spoken = _sanitize_model_reply(text or "", user_text)
    spoken = strip_pseudo_tool_markup_for_speech(spoken)
    spoken = " ".join((spoken or "").split()).strip()
    if not spoken:
        return ""
    if previous_assistant:
        prev = " ".join((previous_assistant or "").split()).strip().casefold()
        cur = spoken.casefold()
        if cur == prev:
            from mango.badge_fastpath import parse_badge_intent
            from mango.social_fastpath import format_social_reply, parse_social_intent

            if parse_social_intent(user_text):
                return format_social_reply(user_text)
            if parse_badge_intent(user_text):
                from mango.badges import format_badge_reply

                return format_badge_reply(user_text)
            spoken = _pick_fallback(user_text or spoken, "Right.", "Got it.", "Same as before.")
    return spoken


def _args_signature(args: dict[str, Any]) -> str:
    try:
        return json.dumps(args or {}, sort_keys=True, separators=(",", ":"))
    except Exception:
        return str(args)


def _generic_tool_retry_without_progress(planner_state: PlannerExecutorState) -> bool:
    if len(planner_state.steps) < 2:
        return False
    prev = planner_state.steps[-2]
    curr = planner_state.steps[-1]
    if prev.tool_name != curr.tool_name:
        return False
    if _args_signature(prev.arguments) != _args_signature(curr.arguments):
        return False
    if curr.status not in {"failed", "needs_confirmation"}:
        return False
    return prev.status == curr.status


def _looks_like_action_request(user_text: str) -> bool:
    low = (user_text or "").strip().casefold()
    if not low:
        return False
    action_words = (
        "play ",
        "open ",
        "call ",
        "run ",
        "search ",
        "remind",
        "volume",
        "spotify",
        "discord",
        "screenshot",
        "badge",
        "unlock",
        "launch",
        "powershell",
        "globe",
        "clipboard",
        "xbox",
        "routine",
        "brief",
    )
    return any(w in low for w in action_words)


def _clarification_for_tool_result(name: str, result: str, *, user_text: str = "") -> str | None:
    from mango.social_fastpath import parse_social_intent

    if parse_social_intent(user_text):
        return None
    r = (result or "").strip()
    if not r:
        return None
    if r.startswith("ERR_TOOL_HANDOFF_CONTRACT:"):
        reason = r.split(":", 2)[-1].strip() if ":" in r else "missing required details."
        low = reason.casefold()
        if name == "spotify_play" or "query" in low or "song" in low:
            return "Which song?"
        if name == "phone_call" or "contact" in low:
            return "Who should I call?"
        if name == "open_app" or "app" in low:
            return "Which app?"
        return f"I need one detail: {reason}."
    if r.startswith("ERR_TOOL_BAD_ARGS:"):
        if name == "spotify_play":
            return "Which song?"
        if name == "phone_call":
            return "Who should I call?"
        if not _looks_like_action_request(user_text):
            return None
        return "What exactly should I do?"
    if "invalid JSON arguments" in r:
        if not _looks_like_action_request(user_text):
            return None
        return "What exactly should I do?"
    return None


def _log_completion_usage(completion: Any) -> None:
    usage = getattr(completion, "usage", None)
    if usage is None:
        return
    try:
        logger.info("LLM usage: %s", vars(usage))
    except TypeError:
        logger.info("LLM usage: %s", usage)


def _discord_bridge_unreachable(result: str) -> bool:
    r = (result or "").casefold()
    return (
        "bridge is not reachable" in r
        or "no voice control http server" in r
        or "nothing listening on localhost" in r
    )


def _discord_voice_action(step: StepState) -> str:
    args = step.arguments if isinstance(step.arguments, dict) else {}
    return str(args.get("action") or "").strip().lower()


_DISCORD_PLAY_ROUTINES = frozenset({"join_discord_play", "discord_hi_and_play"})
_POST_ROUTINE_BLOCK_TOOLS = frozenset(
    {"discord_voice", "spotify_play", "volume_control", "run_routine"}
)


def _last_user_message(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return str(m.get("content") or "")
    return ""


def _completed_discord_play_routine(planner_state: PlannerExecutorState) -> bool:
    for step in planner_state.steps:
        if step.tool_name != "run_routine" or step.status != "completed":
            continue
        rid = str((step.arguments or {}).get("routine_id") or "").strip()
        if rid in _DISCORD_PLAY_ROUTINES:
            return True
    return False


def _is_redundant_post_routine_tool(
    planner_state: PlannerExecutorState,
    name: str,
    args: dict[str, Any],
) -> bool:
    if not _completed_discord_play_routine(planner_state):
        return False
    if name in _POST_ROUTINE_BLOCK_TOOLS:
        return True
    if name == "discord_voice":
        act = str(args.get("action") or "").strip().lower()
        if act in ("sync", "ensure_bridge", "status", "music_start", "music_resume"):
            return True
    return False


def _maybe_finish_after_discord_routine(
    name: str,
    args: dict[str, Any],
    result: str,
    step: StepState,
) -> str | None:
    if name != "run_routine" or step.status != "completed":
        return None
    rid = str(args.get("routine_id") or "").strip()
    if rid not in _DISCORD_PLAY_ROUTINES:
        return None
    if (result or "").startswith("ERR") or "needs routine_id" in (result or ""):
        return None
    vars_map: dict[str, str] = {}
    q = args.get("query")
    if q:
        vars_map["query"] = str(q).strip()
    v = args.get("volume")
    if v is not None:
        vars_map["volume"] = str(v)
    return summarize_routine_result(result, rid, variables=vars_map)


def _discord_voice_stuck_loop(planner_state: PlannerExecutorState) -> bool:
    """True when discord_voice is looping unproductively — not sync → greet → music flows."""
    if _completed_discord_play_routine(planner_state):
        discord_after = [
            s
            for s in planner_state.steps
            if s.tool_name == "discord_voice"
        ]
        if len(discord_after) >= 1:
            return True

    discord_steps = [s for s in planner_state.steps if s.tool_name == "discord_voice"]
    if len(discord_steps) < 2:
        return False
    last = discord_steps[-2:]
    a1, a2 = _discord_voice_action(last[0]), _discord_voice_action(last[1])
    if a1 and a1 == a2:
        return True
    tail_actions = [_discord_voice_action(s) for s in discord_steps[-4:]]
    if tail_actions.count("status") >= 2:
        return True
    if tail_actions.count("sync") >= 2:
        return True
    return False


def _early_tool_loop_spoken_reply(
    planner_state: PlannerExecutorState,
    last_result: str,
) -> str | None:
    """Stop burning LLM tool rounds on bridge-down or repeated discord_voice retries."""
    if _discord_bridge_unreachable(last_result):
        return (
            "Discord voice bridge is not running. "
            "Start it in another terminal with: python -m mango --discord-voice, then ask again."
        )
    if _discord_voice_stuck_loop(planner_state):
        for step in reversed(planner_state.steps[-6:]):
            if step.tool_name == "discord_voice" and _discord_bridge_unreachable(step.note):
                return (
                    "Discord voice bridge is not running. "
                    "Start it in another terminal with: python -m mango --discord-voice, then ask again."
                )
        if _completed_discord_play_routine(planner_state):
            return (
                "Discord join-and-play routine already ran. "
                "Check Discord and Spotify, then tell me what still failed."
            )
        return (
            "Discord voice is retrying the same step. "
            "Try one sync request, or start the bridge with python -m mango --discord-voice."
        )
    if _generic_tool_retry_without_progress(planner_state):
        step = planner_state.steps[-1]
        label = _tool_spoken_label(step.tool_name)
        return (
            f"I'm repeating {label} without progress. "
            "What exact action do you want now?"
        )
    return None


def _needs_immediate_confirmation_followup(reply: str | None) -> bool:
    t = (reply or "").strip().casefold()
    if not t:
        return False
    normalized = t.replace(".", "")
    return any(marker in normalized for marker in _APPROVAL_FOLLOWUP_MARKERS)


def speaking_reply(
    llm: GroqLLM | OllamaLLM,
    registry: ToolRegistry,
    messages: list[dict],
    *,
    max_tool_rounds: int = 6,
    stats_out: dict[str, int] | None = None,
    interrupt_check: Callable[[], bool] | None = None,
) -> str:
    if interrupt_check is not None and interrupt_check():
        if stats_out is not None:
            stats_out["interrupted"] = 1
        return ""
    tools = registry.definitions()
    max_tool_rounds = max(2, min(int(max_tool_rounds), 24))
    last_tool_label = ""
    planner_state = PlannerExecutorState()
    user_text = _last_user_message(messages)
    llm_calls = 0
    tool_calls_executed = 0
    rounds_with_tool_calls = 0
    source_cues: list[str] = []

    def _store_stats() -> None:
        if stats_out is None:
            return
        stats_out["llm_calls"] = llm_calls
        stats_out["tool_calls_executed"] = tool_calls_executed
        stats_out["rounds_with_tool_calls"] = rounds_with_tool_calls
        stats_out["total_steps"] = len(planner_state.steps)

    def _abort_interrupted() -> str:
        if stats_out is not None:
            stats_out["interrupted"] = 1
        _store_stats()
        return ""

    def _emit_reply(text: str) -> str:
        spoken = _finalize_spoken_reply(text, user_text, _last_assistant_reply(messages))
        spoken = _with_source_cues(spoken, source_cues)
        messages.append({"role": "assistant", "content": spoken})
        _store_stats()
        return spoken or _empty_reply_fallback(user_text)
    fast = try_fast_discord_play_routine(user_text, messages, registry)
    if fast is not None:
        logger.info("Discord play fast-path (single routine, no LLM tool rounds)")
        return _emit_reply(fast)

    social_fast = try_fast_social_reply(user_text, messages, registry)
    if social_fast is not None:
        logger.info("Social fast-path (no LLM tool rounds)")
        return _emit_reply(social_fast)

    badge_fast = try_fast_badge_status(user_text, messages, registry)
    if badge_fast is not None:
        logger.info("Badge status fast-path (no LLM tool rounds)")
        return _emit_reply(badge_fast)

    for round_idx in range(1, max_tool_rounds + 1):
        if interrupt_check is not None and interrupt_check():
            logger.info("LLM tool loop interrupted before round %d.", round_idx)
            return _abort_interrupted()
        logger.debug("LLM conversation round %d", round_idx)
        completion = None
        for attempt in range(3):
            try:
                llm_calls += 1
                route_hint = _route_hint_for_round(user_text, round_idx, len(planner_state.steps))
                completion = llm.chat(messages, tools, route_hint=route_hint)
                _log_completion_usage(completion)
                break
            except BadRequestError as exc:
                if attempt < 2 and recover_from_groq_tool_use_failed(
                    exc, messages, registry
                ):
                    logger.warning(
                        "Retrying Groq after salvaged pseudo-tool-call (attempt %s/2)",
                        attempt + 1,
                    )
                    continue
                raise
        if completion is None:
            raise RuntimeError("LLM chat failed after retries")

        message = completion.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            text = (message.content or "").strip()
            spoken_prefix, pseudo = split_assistant_content_and_pseudo_tool(text)
            if pseudo is not None:
                name, args = pseudo
                last_tool_label = name or last_tool_label
                if name not in KNOWN_TOOL_NAMES:
                    logger.warning(
                        "Pseudo tool name %r not recognized — reply cleaned for speech only",
                        name,
                    )
                    return _emit_reply(spoken_prefix)
                logger.warning(
                    "Model put pseudo tool syntax in content; running %r as native tool flow",
                    name,
                )
                call_id = f"ptool_{uuid.uuid4().hex[:18]}"
                entry: dict[str, Any] = {
                    "role": "assistant",
                    "content": spoken_prefix or "",
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(args),
                            },
                        }
                    ],
                }
                messages.append(entry)
                step = planner_state.add_step(round_idx=round_idx, tool_name=name, arguments=args)
                if _is_redundant_post_routine_tool(planner_state, name, args):
                    result = (
                        "Skipped: run_routine already handled Discord join, music, and volume "
                        "for this turn."
                    )
                else:
                    tool_calls_executed += 1
                    if interrupt_check is not None and interrupt_check():
                        return _abort_interrupted()
                    result = registry.execute(
                        name,
                        args,
                        conversation_messages=messages,
                    )
                    if result == "Interrupted by user.":
                        return _abort_interrupted()
                if name == "run_powershell":
                    result = _powershell_output_brief_for_llm(result)
                planner_state.mark_done(step, result)
                for cue in _extract_source_cues(name, result):
                    if cue not in source_cues:
                        source_cues.append(cue)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": result,
                    }
                )
                done = _maybe_finish_after_discord_routine(name, args, result, step)
                if done:
                    return _emit_reply(done)
                clarify = _clarification_for_tool_result(name, result, user_text=user_text)
                if clarify:
                    return _emit_reply(clarify)
                spoken = _deterministic_tool_spoken_result(name, args, result, user_text=user_text)
                if spoken:
                    return _emit_reply(spoken)
                early = _early_tool_loop_spoken_reply(planner_state, result)
                if early:
                    return _emit_reply(early)
                continue

            spoken = _finalize_spoken_reply(spoken_prefix, user_text, _last_assistant_reply(messages))
            logger.debug(
                "Model returned spoken reply (no tools), len=%d",
                len(spoken),
            )
            return _emit_reply(spoken)

        n_tools = len(tool_calls)
        rounds_with_tool_calls += 1
        logger.info("Model issued %d tool call(s) — executing in order.", n_tools)
        assistant_entry = assistant_message_as_dict(message)
        messages.append(assistant_entry)
        pending_spoken: str | None = None
        for idx, tc in enumerate(tool_calls):
            if interrupt_check is not None and interrupt_check():
                return _abort_interrupted()
            fn = getattr(tc, "function", None)
            name = getattr(fn, "name", "") if fn is not None else ""
            if name:
                last_tool_label = name
            raw_args = getattr(fn, "arguments", None) if fn is not None else None
            if raw_args is None:
                raw_args = "{}"
            elif not isinstance(raw_args, str):
                raw_args = str(raw_args)
            args = parse_tool_arguments(raw_args)
            call_id = getattr(tc, "id", "")
            logger.debug(
                "Tool call id=%s name=%s raw_args=%r",
                call_id,
                name,
                raw_args[:300],
            )
            ra = raw_args.strip()
            if ra and ra not in ("{}", "") and not args:
                logger.warning(
                    "Tool %s had invalid JSON arguments — not executing.", name
                )
                result = f"Tool call for {name} had invalid JSON arguments."
                step = planner_state.add_step(round_idx=round_idx, tool_name=name, arguments=args)
                planner_state.mark_done(step, result)
            else:
                step = planner_state.add_step(round_idx=round_idx, tool_name=name, arguments=args)
                if _is_redundant_post_routine_tool(planner_state, name, args):
                    result = (
                        "Skipped: run_routine already handled Discord join, music, and volume "
                        "for this turn."
                    )
                else:
                    tool_calls_executed += 1
                    if interrupt_check is not None and interrupt_check():
                        return _abort_interrupted()
                    narr_ctx = suppress_tool_narration() if n_tools > 1 and idx > 0 else nullcontext()
                    with narr_ctx:
                        result = registry.execute(
                            name,
                            args,
                            conversation_messages=messages,
                        )
                    if result == "Interrupted by user.":
                        return _abort_interrupted()
                if name == "run_powershell":
                    result = _powershell_output_brief_for_llm(result)
                planner_state.mark_done(step, result)
            for cue in _extract_source_cues(name, result):
                if cue not in source_cues:
                    source_cues.append(cue)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result,
                }
            )
            done = _maybe_finish_after_discord_routine(name, args, result, step)
            if done:
                return _emit_reply(done)
            clarify = _clarification_for_tool_result(name, result, user_text=user_text)
            if clarify:
                pending_spoken = clarify
                break
            spoken = _deterministic_tool_spoken_result(name, args, result, user_text=user_text)
            if spoken:
                pending_spoken = spoken
                break
        if pending_spoken:
            return _emit_reply(pending_spoken)

        last_result = ""
        for step in reversed(planner_state.steps):
            if step.round_idx == round_idx:
                last_result = step.note
                break
        early = _early_tool_loop_spoken_reply(planner_state, last_result)
        if early:
            return _emit_reply(early)

    logger.warning(
        "LLM tool loop exceeded max_rounds=%d (last_tool=%r) steps=%s",
        max_tool_rounds,
        last_tool_label,
        planner_state.compact_summary(),
    )
    label = _tool_spoken_label(last_tool_label)
    hint = f"The last action was {label}. " if last_tool_label else ""
    trace = planner_state.compact_summary()
    if _completed_discord_play_routine(planner_state):
        for step in reversed(planner_state.steps):
            if step.tool_name == "run_routine" and step.status == "completed":
                rid = str((step.arguments or {}).get("routine_id") or "discord_hi_and_play")
                stuck = summarize_routine_result(step.note, rid)
                return _emit_reply(stuck)
    stuck = (
        "That request needed too many tool steps in one turn. "
        + hint
        + "I should simplify this to one action next turn. "
        + "For Discord plus music, ask in one sentence with the song name so I can run the single routine."
    )
    logger.debug("Tool loop trace: %s", trace)
    return _emit_reply(stuck)
