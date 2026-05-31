"""Start Discord voice music capture after local Spotify playback when the bridge is in-call."""

from __future__ import annotations

import logging

import httpx

from mango.integrations.discord.discord_voice_client import (
    CONTROL_HEADER,
    control_port,
    control_secret,
)

logger = logging.getLogger(__name__)


def try_start_discord_music_stream() -> str | None:
    """POST /v1/voice/music/start when the bridge is connected. Returns a user-facing suffix or None."""
    port = control_port()
    url = f"http://127.0.0.1:{port}/v1/voice/music/start"
    headers: dict[str, str] = {}
    secret = control_secret()
    if secret:
        headers[CONTROL_HEADER] = secret
    try:
        r = httpx.post(url, json={}, headers=headers, timeout=8.0)
    except httpx.HTTPError as exc:
        logger.debug("discord music sync skipped (bridge unreachable): %s", exc)
        return None
    if r.status_code != 200:
        logger.debug("discord music sync HTTP %s", r.status_code)
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    lines = data.get("lines")
    if isinstance(lines, list) and lines:
        return " ".join(str(x) for x in lines if str(x).strip())
    if data.get("ok"):
        return "Discord music stream started."
    return None
