"""Desktop Mango → Discord bridge: send reply text for in-call TTS (no local headset playback)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import httpx

from mango.integrations.discord.discord_voice_client import (
    CONTROL_HEADER,
    control_port,
    control_secret,
)

logger = logging.getLogger(__name__)

# Bridge caps body text; keep under that with margin.
_CHUNK = 3800


def _chunks(text: str) -> list[str]:
    t = (text or "").strip()
    if not t:
        return []
    if len(t) <= _CHUNK:
        return [t]
    parts: list[str] = []
    start = 0
    while start < len(t):
        end = min(start + _CHUNK, len(t))
        if end < len(t):
            cut = t.rfind("\n\n", start, end)
            if cut == -1 or cut < start + 200:
                cut = t.rfind(". ", start, end)
            if cut == -1 or cut < start + 200:
                cut = end
            else:
                cut += 1
            end = cut
        parts.append(t[start:end].strip())
        start = end
    return [p for p in parts if p]


def speak_via_discord(
    text: str,
    *,
    interrupt_check: Callable[[], bool] | None = None,
    timeout_per_request: float = 180.0,
    on_playback_start: Callable[[], None] | None = None,
) -> tuple[bool, str]:
    """POST ``/v1/voice/speak`` for each chunk. Returns (ok, message for logs / UI)."""
    parts = _chunks(text)
    if not parts:
        return False, "Nothing to speak."

    port = control_port()
    url = f"http://127.0.0.1:{port}/v1/voice/speak"
    headers: dict[str, str] = {}
    sec = control_secret()
    if sec:
        headers[CONTROL_HEADER] = sec

    playback_fired = False

    def _playback_start_once() -> None:
        nonlocal playback_fired
        if playback_fired or on_playback_start is None:
            return
        playback_fired = True
        on_playback_start()

    try:
        with httpx.Client(timeout=timeout_per_request) as client:
            for i, part in enumerate(parts):
                if interrupt_check is not None and interrupt_check():
                    return True, f"Stopped after chunk {i}/{len(parts)} (interrupt)."
                r = client.post(url, headers=headers, json={"text": part})
                if r.status_code == 401:
                    return False, "Discord bridge rejected control secret."
                if r.status_code in (404, 502, 503) or (
                    r.status_code >= 500 and r.status_code < 600
                ):
                    return (
                        False,
                        f"No bridge on port {port} (HTTP {r.status_code}). "
                        "Run `python -m mango --discord-voice` and join a call.",
                    )
                if r.is_error:
                    return False, f"HTTP {r.status_code}: {(r.text or '')[:200]}"
                try:
                    data = r.json()
                except Exception:
                    data = {}
                if isinstance(data, dict) and data.get("ok") is False:
                    lines = data.get("lines") or []
                    detail = " ".join(str(x) for x in lines[:3]) or str(data)
                    return False, detail
                if i == 0:
                    _playback_start_once()
                if i + 1 < len(parts):
                    time.sleep(0.15)
    except httpx.ConnectError:
        return (
            False,
            f"Could not connect to Discord voice bridge on 127.0.0.1:{port}. "
            "Start `python -m mango --discord-voice` and ensure you are in a voice call.",
        )
    except Exception as exc:
        logger.exception("speak_via_discord")
        return False, str(exc)

    return True, f"Spoke {len(parts)} chunk(s) in Discord voice."
