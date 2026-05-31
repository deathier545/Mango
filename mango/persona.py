"""Owner display name and related defaults (env + OS username fallback)."""

from __future__ import annotations

import getpass
import logging
import os
import re

logger = logging.getLogger(__name__)


def owner_display_name_from_env() -> str:
    """Human-facing owner name for prompts, TTS scripts, and tool copy."""
    raw = os.getenv("MANGO_OWNER_NAME", "").strip()
    if raw:
        return raw
    try:
        u = (getpass.getuser() or "").strip()
    except Exception:
        u = ""
    if u:
        return u.replace("_", " ").strip().title() or u
    return "you"


def parse_phone_contact_slugs(raw: str | None) -> tuple[str, ...]:
    """Comma-separated slug list, lowercased; default built-in trio if unset."""
    s = (raw or "").strip()
    if not s:
        return ("ariana", "brooke", "dylan")
    parts: list[str] = []
    for piece in s.split(","):
        slug = piece.strip().casefold()
        if not slug:
            continue
        if not re.fullmatch(r"[a-z0-9_]{1,32}", slug):
            logger.warning("Ignoring invalid MANGO_PHONE_CONTACTS entry %r", piece)
            continue
        parts.append(slug)
    return tuple(parts) if parts else ("ariana", "brooke", "dylan")
