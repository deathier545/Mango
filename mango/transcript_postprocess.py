"""Small, conservative transcript cleanup for recurring STT mishears."""

from __future__ import annotations

import re

_FOR_YOU_TODAY_ONLY = re.compile(r"^\s*for you today[\s?.!]*$", re.IGNORECASE)


def normalize_transcript_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    # Common Whisper mishear in casual greeting turns.
    if _FOR_YOU_TODAY_ONLY.fullmatch(raw):
        return "how are you today"
    return raw

