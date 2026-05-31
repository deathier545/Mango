"""Load bundled system-prompt voice/policy text from ``mango/prompts/``."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from mango.config import Config

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_VOICE_POLICIES_FILE = _PROMPTS_DIR / "voice_policies.txt"


def voice_policies_template() -> str:
    """Bundled voice + tool-guidance policies (placeholders: {owner}, {phone_contacts_line})."""
    try:
        text = _VOICE_POLICIES_FILE.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        logger.error("Missing bundled voice policies %s: %s", _VOICE_POLICIES_FILE, exc)
        return ""
    return text


def format_voice_policies(cfg: Config) -> str:
    """Substitute config-derived strings into the bundled template."""
    tmpl = voice_policies_template()
    if not tmpl:
        return ""
    labels = [_contact_label_for_slug(s) for s in cfg.phone_contact_slugs]
    phone_line = _english_join(labels)
    return tmpl.format(owner=cfg.owner_display_name, phone_contacts_line=phone_line)


def _contact_label_for_slug(slug: str) -> str:
    key = f"MANGO_CONTACT_{slug.upper()}_DISPLAY"
    raw = os.getenv(key, "").strip()
    if raw:
        return raw
    return slug.replace("_", " ").strip().title() or slug


def _english_join(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} or {parts[1]}"
    return ", ".join(parts[:-1]) + f", or {parts[-1]}"
