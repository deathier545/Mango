"""Optional queue to the desktop shell (``--desktop``) for UI actions from the voice process."""

from __future__ import annotations

import logging
import time
from typing import Any

from mango.desktop_events import emit_desktop_event

logger = logging.getLogger(__name__)

_parent_queue: Any = None  # multiprocessing.Queue | None
_last_audio_emit_ts = 0.0
_last_audio_emit_level = -1.0


def attach_parent_queue(q: Any) -> None:
    """Voice process: call once with the parent's ``multiprocessing.Queue``."""
    global _parent_queue
    _parent_queue = q


def try_send_globe_url(
    url: str,
    *,
    label: str,
    lat: float | None = None,
    lng: float | None = None,
    bbox: dict[str, float] | None = None,
    zoom: float | None = None,
) -> bool:
    """Notify desktop to show the map (optional Nominatim bbox frames regions correctly)."""
    msg: dict[str, Any] = {"type": "globe", "url": url, "label": label}
    if lat is not None and lng is not None:
        msg["lat"] = lat
        msg["lng"] = lng
    if zoom is not None:
        msg["zoom"] = zoom
    if bbox is not None:
        msg["bbox"] = bbox
    if _parent_queue is not None:
        try:
            _parent_queue.put(msg)
            return True
        except Exception:
            logger.warning("desktop_ipc: could not send globe message", exc_info=True)
            return False
    # Fallback for Electron shell mode: emit parseable log marker.
    try:
        import json

        logger.info("MANGO_GLOBE: %s", json.dumps(msg, ensure_ascii=True, separators=(",", ":")))
        emit_desktop_event({"type": "globe", **msg})
        return True
    except Exception:
        logger.warning("desktop_ipc: could not log globe fallback message", exc_info=True)
        return False


def try_set_globe_visible(visible: bool) -> bool:
    """Notify desktop UI to show/hide globe background and switch Mango mode."""
    value = bool(visible)
    if _parent_queue is not None:
        try:
            _parent_queue.put({"type": "globe_state", "visible": value})
            return True
        except Exception:
            logger.warning("desktop_ipc: could not send globe_state message", exc_info=True)
            return False
    logger.info("MANGO_GLOBE_VISIBLE: %s", "1" if value else "0")
    emit_desktop_event({"type": "globe_state", "visible": value})
    return True


def try_set_ai_state(state: str) -> bool:
    """Notify desktop UI about Mango runtime state: listening/thinking/speaking."""
    s = (state or "").strip().casefold()
    if s not in {"idle", "listening", "thinking", "speaking", "awaiting", "stopped", "error"}:
        return False
    if _parent_queue is None:
        emit_desktop_event({"type": "state", "state": s})
        logger.info("MANGO_STATE: %s", s)
        return True
    try:
        _parent_queue.put({"type": "ai_state", "state": s})
        return True
    except Exception:
        logger.warning("desktop_ipc: could not send ai_state message", exc_info=True)
        return False


def try_set_audio_level(level: float) -> bool:
    """Notify desktop UI about current TTS playback level (0..1)."""
    global _last_audio_emit_ts, _last_audio_emit_level
    try:
        v = float(level)
    except Exception:
        return False
    v = max(0.0, min(1.0, v))

    if _parent_queue is not None:
        try:
            _parent_queue.put({"type": "audio_level", "level": v})
            return True
        except Exception:
            logger.warning("desktop_ipc: could not send audio_level message", exc_info=True)
            return False

    # Fallback for Electron shell mode without a parent queue:
    # emit a parseable stdout log line at a bounded rate.
    now = time.monotonic()
    if now - _last_audio_emit_ts < 0.05 and abs(v - _last_audio_emit_level) < 0.02:
        return False
    _last_audio_emit_ts = now
    _last_audio_emit_level = v
    logger.info("MANGO_AUDIO_LEVEL: %.4f", v)
    emit_desktop_event({"type": "audio_level", "level": v})
    return True
