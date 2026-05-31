"""Fast-path casual social turns without LLM tool calls."""

from __future__ import annotations

import re
from typing import Any

_SOCIAL_RE = (
    re.compile(r"^how are you\b", re.I),
    re.compile(r"^how('s| is) it going\b", re.I),
    re.compile(r"^how you doing\b", re.I),
    re.compile(r"^how do you feel\b", re.I),
    re.compile(r"^what('s| is) up\b", re.I),
    re.compile(r"^you okay\b", re.I),
    re.compile(r"^you alright\b", re.I),
    re.compile(r"^how('s| is) mango\b", re.I),
)

_ACTION_MARKERS = (
    "play ",
    "open ",
    "call ",
    "spotify",
    "discord",
    "search ",
    "run ",
    "badge",
    "unlock",
    "volume",
    "screenshot",
    "remind",
)


def parse_social_intent(user_text: str) -> bool:
    """True for short greetings / how-are-you — not action or badge requests."""
    text = (user_text or "").strip()
    if not text or len(text) > 120:
        return False
    low = text.casefold()
    if any(m in low for m in _ACTION_MARKERS):
        return False
    if any(p.search(text) for p in _SOCIAL_RE):
        return True
    if low in {"hi", "hello", "hey", "yo", "sup", "hi mango", "hey mango", "hello mango"}:
        return True
    return False


def _pick(seed: str, *lines: str) -> str:
    if not lines:
        return "I'm here."
    return lines[sum(ord(c) for c in seed) % len(lines)]


def format_social_reply(user_text: str) -> str:
    seed = (user_text or "hi").casefold()
    low = seed
    if "how are you" in low or "how do you feel" in low:
        return _pick(
            seed,
            "I'm doing well — steady and ready to help.",
            "I'm good right now. What's on your mind?",
            "All good on my end. What do you need?",
        )
    if "how" in low and "going" in low:
        return _pick(seed, "Going well. What can I do for you?", "Pretty good — what do you need?")
    return _pick(
        seed,
        "Hey — I'm here.",
        "Hi. What can I help with?",
        "Hello. Ready when you are.",
    )


def try_fast_social_reply(user_text: str, messages: list[dict[str, Any]], registry: Any) -> str | None:
    _ = (messages, registry)
    if not parse_social_intent(user_text):
        return None
    return format_social_reply(user_text)
