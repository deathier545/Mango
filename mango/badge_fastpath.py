"""Fast-path badge progress queries without LLM tool thrashing."""

from __future__ import annotations

import re
from typing import Any

from mango.badges import format_badge_reply

_ACTION_VETO = (
    "spotify",
    "discord",
    "open ",
    "play ",
    "call ",
    "volume",
    "chrome",
    "youtube",
    "remind",
    "screenshot",
    "powershell",
    "xbox",
    "globe",
    "search ",
)

_STRONG_BADGE_PHRASES = (
    "badge status",
    "badge progress",
    "my badges",
    "your badges",
    "mango badges",
    "how many badges",
    "badges unlocked",
    "badges do you have",
    "badges do i still",
    "unlock more badge",
    "want to unlock",
    "want more badge",
    "help you unlock",
    "help you earn",
    "should we unlock",
    "should you unlock",
    "what badge",
    "which badge",
    "smart tab",
    "smart → badges",
)


def parse_badge_intent(user_text: str) -> bool:
    """True when the user clearly asks about Mango's Smart-tab badges."""
    text = (user_text or "").strip()
    if not text:
        return False
    low = text.casefold()
    if any(v in low for v in _ACTION_VETO):
        return False
    if re.search(r"\bbadges?\b", low):
        return True
    if any(p in low for p in _STRONG_BADGE_PHRASES):
        return True
    if "mango" in low and re.search(r"\b(progress|unlock|milestone|achievement)\b", low):
        return True
    if re.search(r"\bunlock\b", low) and re.search(r"\b(badge|mango|milestone)\b", low):
        return True
    return False


def try_fast_badge_status(user_text: str, messages: list[dict[str, Any]], registry: Any) -> str | None:
    """Answer badge questions directly — no LLM round-trip."""
    _ = (messages, registry)
    if not parse_badge_intent(user_text):
        return None
    return format_badge_reply(user_text)
