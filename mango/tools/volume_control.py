"""Master playback volume and mute on Windows (default audio endpoint)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "Control default speaker output: mute, unmute, set volume percent, toggle mute, or read status. "
    "Windows only."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["mute", "unmute", "toggle_mute", "set", "status"],
            "description": "What to do.",
        },
        "percent": {
            "type": "integer",
            "description": "For set: volume 0–100.",
        },
    },
    "required": ["action"],
    "additionalProperties": False,
}


def run(action: str, percent: int | None = None) -> str:
    import sys

    if sys.platform != "win32":
        return "Volume tool is Windows-only."

    try:
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    except ImportError as exc:
        return f"Volume control unavailable ({exc}). Install pycaw and comtypes."

    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(interface, POINTER(IAudioEndpointVolume))
    except Exception as exc:
        logger.warning("pycaw init failed", exc_info=True)
        return f"Could not open audio endpoint: {exc}"

    act = (action or "").strip().casefold()
    try:
        if act == "mute":
            vol.SetMute(1, None)
            return "Muted."
        if act == "unmute":
            vol.SetMute(0, None)
            return "Unmuted."
        if act == "toggle_mute":
            muted = bool(vol.GetMute())
            vol.SetMute(0 if muted else 1, None)
            return "Unmuted." if muted else "Muted."
        if act == "set":
            if percent is None:
                return "Error: percent required for set (0–100)."
            level = max(0.0, min(100.0, float(percent))) / 100.0
            vol.SetMasterVolumeLevelScalar(level, None)
            return f"Volume set to {percent}%."
        if act == "status":
            muted = bool(vol.GetMute())
            pct = vol.GetMasterVolumeLevelScalar() * 100.0
            return f"Mute={muted}, volume={pct:.0f}%."
    except Exception as exc:
        logger.warning("volume action failed", exc_info=True)
        return f"Volume command failed: {exc}"
    return f"Unknown action {action!r}. Use mute, unmute, toggle_mute, set, or status."
