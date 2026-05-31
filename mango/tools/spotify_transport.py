"""Playback control: Spotify Web API when web playback mode is on; else Windows media keys."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "Control **playback**. **Default (MANGO_SPOTIFY_WEB_PLAYBACK off, Windows):** sends **system media keys** "
    "(play/pause, next, previous, stop) to whatever app owns the **active media session** — normally **Spotify** after "
    "**spotify_play** started or switched a track. With **MANGO_SPOTIFY_MINIMIZED** (default), Mango **foregrounds Spotify**, "
    "sends the key, waits briefly, then **minimizes** Spotify again. If skip/pause does nothing, play a song with **spotify_play** first so "
    "Spotify is the current media target. "
    "When **MANGO_SPOTIFY_WEB_PLAYBACK=1** and logged in (**spotify_session**), uses the **Spotify Web API** instead. "
    "Use **spotify_play** to pick a **different** track by name."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["play_pause", "next", "previous", "stop"],
            "description": "play_pause toggles play/pause; next/previous skip tracks; stop stops playback.",
        },
    },
    "required": ["action"],
    "additionalProperties": False,
}

# https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
_VK_MEDIA_NEXT_TRACK = 0xB0
_VK_MEDIA_PREV_TRACK = 0xB1
_VK_MEDIA_STOP = 0xB2
_VK_MEDIA_PLAY_PAUSE = 0xB3
_KEYEVENTF_KEYUP = 0x0002


def _web_playback_enabled() -> bool:
    return os.getenv("MANGO_SPOTIFY_WEB_PLAYBACK", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _tap_vk(vk: int) -> None:
    import ctypes

    u = ctypes.windll.user32
    u.keybd_event(vk, 0, 0, 0)
    u.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


def run(action: str) -> str:
    act = (action or "").strip().lower()
    if act not in ("play_pause", "next", "previous", "stop"):
        return f"Unknown action {action!r}. Use play_pause, next, previous, or stop."

    if _web_playback_enabled():
        import mango.integrations.spotify.spotify_player_server as sps
        import mango.integrations.spotify.spotify_user_auth as sua

        tok = sua.get_valid_access_token()
        if tok:
            if act == "play_pause":
                ok, msg = sps.toggle_play_pause(tok)
            elif act == "next":
                ok, msg = sps.web_api_transport(tok, "next")
            elif act == "previous":
                ok, msg = sps.web_api_transport(tok, "previous")
            else:
                ok, msg = sps.web_api_transport(tok, "pause")
            if ok:
                labels = {
                    "play_pause": "Play/Pause toggled",
                    "next": "Next track",
                    "previous": "Previous track",
                    "stop": "Paused (Web API)",
                }
                return f"{labels.get(act, act)} via Spotify Web API."
            return (
                f"Spotify Web API transport failed: {msg} "
                "Open the Mango player tab, keep it active, or run spotify_session login."
            )

    if sys.platform != "win32":
        return (
            "spotify_transport needs Windows media keys when web playback is off or not logged in. "
            "Set MANGO_SPOTIFY_WEB_PLAYBACK=1 and run spotify_session login for Web API control on this OS."
        )

    vk: int
    if act == "play_pause":
        vk = _VK_MEDIA_PLAY_PAUSE
    elif act == "next":
        vk = _VK_MEDIA_NEXT_TRACK
    elif act == "previous":
        vk = _VK_MEDIA_PREV_TRACK
    else:
        vk = _VK_MEDIA_STOP

    if sys.platform == "win32":
        import mango.integrations.spotify.spotify_windows_ui as swu

        if swu.track_change_window_cycle_enabled():
            swu.foreground_spotify_windows()
    try:
        _tap_vk(vk)
    except Exception as exc:
        logger.warning("media key tap failed", exc_info=True)
        return f"Media key failed: {exc}"
    if sys.platform == "win32":
        import mango.integrations.spotify.spotify_windows_ui as swu

        if swu.track_change_window_cycle_enabled():
            swu.pause_then_minimize_spotify()

    labels = {
        "play_pause": "Play/Pause (toggle)",
        "next": "Next track",
        "previous": "Previous track",
        "stop": "Stop",
    }
    return f"{labels.get(act, act)} key sent to the active Windows media session."
