"""List or run saved multi-step routines."""

from __future__ import annotations

from typing import Any

from mango.smart.routine_query import (
    infer_song_query_from_messages,
    normalize_song_query,
    routines_needing_query,
)

DESCRIPTION = (
    "Run predefined multi-step routines in one tool call (counts as one step). "
    "Routines: join_discord_play, discord_hi_and_play (join + greet everyone + Spotify + Discord "
    "music + volume), night_mode, focus_mode. Use action list to see all. "
    "For discord_hi_and_play pass routine_id, query (song), and volume (0–100, default 50)."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["list", "run"]},
        "routine_id": {
            "type": "string",
            "description": "e.g. discord_hi_and_play, join_discord_play, night_mode, focus_mode",
        },
        "query": {
            "type": "string",
            "description": "Song/search for join_discord_play or discord_hi_and_play.",
        },
        "volume": {
            "type": "integer",
            "description": "For discord_hi_and_play — speaker volume percent 0–100 (default 50).",
        },
    },
    "required": ["action"],
    "additionalProperties": False,
}

# Registry injected at runtime from tool_registry.execute
_REGISTRY: Any = None


def set_registry(registry: Any) -> None:
    global _REGISTRY
    _REGISTRY = registry


def run(
    action: str,
    *,
    routine_id: str | None = None,
    query: str | None = None,
    volume: int | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> str:
    from mango.smart.smart_routines import execute_routine, list_routines_text

    act = (action or "").strip().lower()
    if act == "list":
        return list_routines_text()
    if act == "run":
        if not routine_id:
            return "run_routine needs routine_id."
        if _REGISTRY is None:
            return "Routine runner not available in this context."
        rid = routine_id.strip()
        vars_map: dict[str, str] = {}
        if query:
            vars_map["query"] = normalize_song_query(query)
        elif rid in routines_needing_query():
            inferred = infer_song_query_from_messages(conversation_messages)
            if inferred:
                vars_map["query"] = inferred
            else:
                return (
                    f"run_routine needs a song for {rid!r}. "
                    "Pass query= (e.g. Bad Romance) or say the song in your message."
                )
        if volume is not None:
            vars_map["volume"] = str(max(0, min(100, int(volume))))
        elif rid == "discord_hi_and_play":
            vars_map["volume"] = "50"
        return execute_routine(_REGISTRY, rid, variables=vars_map)
    return f"Unknown action {action!r}"
