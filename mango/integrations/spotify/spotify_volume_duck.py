"""Lower playback while Mango listens, thinks, and speaks (Windows).

- Spotify.exe session volume (pycaw)
- Discord.exe session volume (what you hear in the Discord client)
- Discord **CABLE music stream** gain via the voice bridge (``PCMVolumeTransformer``)

Re-entrant: nested ``with duck_spotify_session():`` blocks restore only when the outermost exits.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

_duck_depth = 0
_duck_restore_stack: list[tuple[Any, float, int]] | None = None
_discord_stream_ducked = False


def ducking_enabled() -> bool:
    if sys.platform != "win32":
        return False
    raw = os.getenv("MANGO_SPOTIFY_DUCK", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _duck_volume_multiplier() -> float:
    """Fraction of the current per-session level to keep (e.g. ``0.12`` ≈ 12% of prior)."""
    try:
        v = float(os.getenv("MANGO_SPOTIFY_DUCK_VOLUME", "0.12").strip())
    except ValueError:
        v = 0.12
    return max(0.02, min(1.0, v))


def _duck_floor_scalar() -> float:
    """Never duck a session below this scalar (avoids effective silence)."""
    try:
        v = float(os.getenv("MANGO_SPOTIFY_DUCK_FLOOR", "0.02").strip())
    except ValueError:
        v = 0.02
    return max(0.01, min(0.5, v))


_PLAYBACK_PROCESS_NAMES = frozenset({"spotify.exe", "discord.exe"})


def _collect_playback_sessions() -> list[Any]:
    from pycaw.pycaw import AudioUtilities

    out: list[Any] = []
    for session in AudioUtilities.GetAllSessions():
        proc = session.Process
        if proc is None:
            continue
        try:
            if str(proc.name()).lower() not in _PLAYBACK_PROCESS_NAMES:
                continue
        except Exception:
            continue
        out.append(session)
    return out


def _duck_discord_cable_stream(level: float | None = None) -> bool:
    """POST to the Discord voice bridge to lower CABLE→call stream volume."""
    try:
        import httpx

        from mango.integrations.discord.discord_voice_client import (
            CONTROL_HEADER,
            control_port,
            control_secret,
        )

        mult = _duck_volume_multiplier() if level is None else max(0.0, min(1.0, float(level)))
        headers: dict[str, str] = {}
        secret = control_secret()
        if secret:
            headers[CONTROL_HEADER] = secret
        port = control_port()
        r = httpx.post(
            f"http://127.0.0.1:{port}/v1/voice/music/duck",
            json={"level": mult},
            headers=headers,
            timeout=4.0,
        )
        if r.status_code == 200:
            logger.info("Discord CABLE music stream ducked to %.0f%%", mult * 100)
            return True
        logger.debug("Discord music duck HTTP %s", r.status_code)
    except Exception:
        logger.debug("Discord CABLE stream duck skipped", exc_info=True)
    return False


def _restore_discord_cable_stream() -> None:
    try:
        import httpx

        from mango.integrations.discord.discord_voice_client import (
            CONTROL_HEADER,
            control_port,
            control_secret,
        )

        headers: dict[str, str] = {}
        secret = control_secret()
        if secret:
            headers[CONTROL_HEADER] = secret
        port = control_port()
        httpx.post(
            f"http://127.0.0.1:{port}/v1/voice/music/restore",
            json={},
            headers=headers,
            timeout=4.0,
        )
        logger.info("Discord CABLE music stream volume restored")
    except Exception:
        logger.debug("Discord CABLE stream restore skipped", exc_info=True)


def _snapshot_and_duck() -> list[tuple[Any, float, int]]:
    """Return list of ``(SimpleAudioVolume COM, prev_scalar, prev_mute_int)`` for restore."""
    mult = _duck_volume_multiplier()
    floor = _duck_floor_scalar()
    stacks: list[tuple[Any, float, int]] = []
    for session in _collect_playback_sessions():
        try:
            sav = session.SimpleAudioVolume
            prev = float(sav.GetMasterVolume())
            prev_mute = int(sav.GetMute())
            target = max(floor, min(1.0, prev * mult))
            sav.SetMasterVolume(target, None)
            stacks.append((sav, prev, prev_mute))
        except Exception:
            logger.debug("duck skip session", exc_info=True)
            continue
    if stacks:
        logger.info(
            "Playback volume duck: %d session(s) (Spotify/Discord), mult=%.3f floor=%.3f",
            len(stacks),
            mult,
            floor,
        )
    return stacks


def _restore(stacks: list[tuple[Any, float, int]]) -> None:
    for sav, prev, prev_mute in stacks:
        try:
            sav.SetMasterVolume(prev, None)
            sav.SetMute(prev_mute, None)
        except Exception:
            logger.debug("spotify duck restore failed", exc_info=True)


@contextmanager
def duck_spotify_session() -> Iterator[None]:
    """Context manager: duck Spotify, Discord app, and CABLE stream; restores in ``finally``."""
    global _duck_depth, _duck_restore_stack, _discord_stream_ducked
    if not ducking_enabled():
        yield
        return
    entered_outer = False
    if _duck_depth == 0:
        entered_outer = True
        _discord_stream_ducked = _duck_discord_cable_stream()
        try:
            _duck_restore_stack = _snapshot_and_duck()
        except ImportError:
            logger.warning(
                "Playback duck: pycaw/comtypes missing — install for Spotify/Discord app ducking."
            )
            _duck_restore_stack = None
        except Exception:
            logger.warning("Playback duck via pycaw failed", exc_info=True)
            _duck_restore_stack = None
        if not _duck_restore_stack and not _discord_stream_ducked:
            logger.warning(
                "Playback duck: no Spotify/Discord sessions and no active CABLE stream to duck."
            )
    _duck_depth += 1
    try:
        yield
    finally:
        _duck_depth -= 1
        if entered_outer and _duck_depth == 0:
            if _duck_restore_stack:
                _restore(_duck_restore_stack)
                _duck_restore_stack = None
            if _discord_stream_ducked:
                _restore_discord_cable_stream()
                _discord_stream_ducked = False
