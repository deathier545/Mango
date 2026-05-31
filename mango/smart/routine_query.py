"""Infer song search text for play routines from user messages."""

from __future__ import annotations

import re

_ROUTINES_NEED_QUERY = frozenset({"join_discord_play", "discord_hi_and_play"})

_ROUTINE_IDS = frozenset(
    {
        "join_discord_play",
        "discord_hi_and_play",
        "night_mode",
        "focus_mode",
    }
)

_SONG_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:with\s+)?(?:the\s+)?song\s+(.+?)(?:\s+and\s+volume|\s+volume\s+\d+|\s+at\s+\d+\s*%|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bfor\s+(.+?)(?:\s+and\s+volume|\s+volume\s+\d+|\s+at\s+\d+\s*%|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:play|queue|put on)\s+(.+?)(?:\s+on\s+spotify|\s+in\s+discord|\s+and\s+volume|$)",
        re.IGNORECASE,
    ),
)


def routines_needing_query() -> frozenset[str]:
    return _ROUTINES_NEED_QUERY


def normalize_song_query(raw: str) -> str:
    q = (raw or "").strip().strip("'\"")
    q = re.sub(r"^(?:the\s+)?song\s+", "", q, flags=re.IGNORECASE)
    q = re.sub(r"\s+and\s+volume\s+.*$", "", q, flags=re.IGNORECASE)
    q = re.sub(r"\s+volume\s+\d+.*$", "", q, flags=re.IGNORECASE)
    q = re.sub(r"\s+at\s+\d+\s*%?\s*$", "", q, flags=re.IGNORECASE)
    return q.strip()


def _is_routine_token(text: str) -> bool:
    low = text.casefold().strip()
    return low in _ROUTINE_IDS or low.startswith("run routine")


def infer_song_query_from_messages(messages: list[dict] | None) -> str | None:
    """Best-effort song title from recent user text (when the model omits ``query``)."""
    for msg in reversed(messages or []):
        if msg.get("role") != "user":
            continue
        text = str(msg.get("content") or "").strip()
        if not text:
            continue
        for quoted in re.findall(r'"([^"]+)"|\'([^\']+)\'', text):
            part = (quoted[0] or quoted[1]).strip()
            if part and not _is_routine_token(part):
                return normalize_song_query(part)
        for pat in _SONG_PATTERNS:
            m = pat.search(text)
            if not m:
                continue
            candidate = normalize_song_query(m.group(1))
            if candidate and not _is_routine_token(candidate):
                return candidate
    return None
