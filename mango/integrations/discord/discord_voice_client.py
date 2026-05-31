"""Discord voice bridge settings (no ``discord`` import — safe for desktop tool load)."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

CONTROL_HEADER = "X-Mango-Discord-Control"
DEFAULT_CONTROL_PORT = 37564


def control_port() -> int:
    raw = os.getenv("MANGO_DISCORD_VOICE_CONTROL_PORT", "").strip()
    if not raw:
        return DEFAULT_CONTROL_PORT
    try:
        return int(raw)
    except ValueError:
        logger.warning(
            "Invalid MANGO_DISCORD_VOICE_CONTROL_PORT=%r — using %s",
            raw,
            DEFAULT_CONTROL_PORT,
        )
        return DEFAULT_CONTROL_PORT


def control_secret() -> str:
    return os.getenv("MANGO_DISCORD_CONTROL_SECRET", "").strip()


def owner_user_id() -> int | None:
    raw = os.getenv("MANGO_DISCORD_OWNER_USER_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid MANGO_DISCORD_OWNER_USER_ID=%r", raw)
        return None


def notify_channel_id() -> int | None:
    raw = os.getenv("MANGO_DISCORD_NOTIFY_CHANNEL_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid MANGO_DISCORD_NOTIFY_CHANNEL_ID=%r", raw)
        return None


def preferred_guild_id() -> int | None:
    raw = os.getenv("MANGO_DISCORD_PREFERRED_GUILD_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid MANGO_DISCORD_PREFERRED_GUILD_ID=%r", raw)
        return None
