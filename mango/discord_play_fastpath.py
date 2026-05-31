"""Detect Discord+play intents and run one-shot routines without LLM tool thrashing."""

from __future__ import annotations

import re
from typing import Any

from mango.tool_narration import short_completion_reply
from mango.smart.routine_query import infer_song_query_from_messages, normalize_song_query

_DISCORD_PLAY_ROUTINES = frozenset({"join_discord_play", "discord_hi_and_play"})


def parse_discord_play_intent(user_text: str) -> tuple[str, str | None, int | None] | None:
    """Return (routine_id, song_query, volume) when the user clearly wants join+play."""
    text = (user_text or "").strip()
    if not text:
        return None
    low = text.casefold()

    if re.search(r"run\s+routine\s+(\w+)", text, re.I):
        m = re.search(r"run\s+routine\s+([\w_]+)", text, re.I)
        if m:
            rid = m.group(1).strip()
            if rid in _DISCORD_PLAY_ROUTINES:
                vol = _parse_volume(text)
                query = infer_song_query_from_messages([{"role": "user", "content": text}])
                return rid, query, vol

    needs_discord = any(
        k in low for k in ("discord", "voice call", "voice chat", "in call", "the call")
    )
    needs_play = any(k in low for k in ("play", "song", "music", "spotify", "track"))
    if not (needs_discord and needs_play):
        return None

    greet = any(
        k in low
        for k in (
            "greet",
            "hello everyone",
            "hi everyone",
            "say hi",
            "say hello",
            "discord_hi_and_play",
        )
    )
    rid = "discord_hi_and_play" if greet else "join_discord_play"
    if "discord_hi_and_play" in low or "hi_and_play" in low:
        rid = "discord_hi_and_play"
    query = infer_song_query_from_messages([{"role": "user", "content": text}])
    vol = _parse_volume(text)
    return rid, query, vol


def _parse_volume(text: str) -> int | None:
    m = re.search(r"(?:volume|at)\s+(\d{1,3})\s*%?", text, re.IGNORECASE)
    if not m:
        return None
    return max(0, min(100, int(m.group(1))))


def try_fast_discord_play_routine(
    user_text: str,
    messages: list[dict[str, Any]],
    registry: Any,
) -> str | None:
    """Run join/play routine directly when intent is clear (one tool chain, no LLM rounds)."""
    parsed = parse_discord_play_intent(user_text)
    if not parsed:
        return None
    rid, query, vol = parsed
    if rid in _DISCORD_PLAY_ROUTINES and not query:
        return None

    from mango.tools import run_routine

    run_routine.set_registry(registry)
    result = run_routine.run(
        action="run",
        routine_id=rid,
        query=query,
        volume=vol,
        conversation_messages=messages,
    )
    vars_map: dict[str, str] = {}
    if query:
        from mango.smart.routine_query import normalize_song_query

        vars_map["query"] = normalize_song_query(query)
    if vol is not None:
        vars_map["volume"] = str(max(0, min(100, int(vol))))
    elif rid == "discord_hi_and_play":
        vars_map["volume"] = "50"
    return summarize_routine_result(result, rid, variables=vars_map)


def summarize_routine_result(
    result: str,
    routine_id: str,
    *,
    variables: dict[str, str] | None = None,
) -> str:
    """Short spoken/chat summary from execute_routine output."""
    vars_map = dict(variables or {})
    lines = [ln.strip() for ln in (result or "").splitlines() if ln.strip()]
    if not lines:
        return short_completion_reply(routine_id, vars_map, result)
    failed = any("skipped" in ln.casefold() or "err " in ln.casefold() for ln in lines)
    if not failed:
        return short_completion_reply(routine_id, vars_map, result)
    spotify_line = next((ln for ln in lines if "spotify_play:" in ln), "")
    if "TRACK_PLAYED" in spotify_line or "Playing" in spotify_line:
        tail = spotify_line.split("spotify_play:", 1)[-1].strip()[:140]
        return f"Done — joined Discord and started music ({tail})."
    return short_completion_reply(routine_id, vars_map, result) + " " + lines[-1][:100]
