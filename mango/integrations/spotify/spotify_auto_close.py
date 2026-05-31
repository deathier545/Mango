"""Close Spotify after the track Mango started has finished (Windows desktop)."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_watch_lock = threading.Lock()
_active_watch_id = 0


def auto_close_when_done_enabled() -> bool:
    if sys.platform != "win32":
        return False
    raw = os.getenv("MANGO_SPOTIFY_CLOSE_WHEN_DONE", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def poll_interval_s() -> float:
    try:
        sec = float(os.getenv("MANGO_SPOTIFY_CLOSE_POLL_S", "2.5").strip())
    except ValueError:
        sec = 2.5
    return max(1.0, min(sec, 10.0))


def min_progress_ratio_to_close() -> float:
    """Only treat track change / idle as 'done' after this fraction of duration (0–1)."""
    try:
        v = float(os.getenv("MANGO_SPOTIFY_CLOSE_MIN_PROGRESS", "0.88").strip())
    except ValueError:
        v = 0.88
    return max(0.5, min(0.99, v))


def _end_threshold_ms(duration_ms: int) -> int:
    return max(15_000, int(duration_ms * min_progress_ratio_to_close()))


def should_close_after_track_change(
    *,
    saw_target_streak: int,
    last_progress_ms: int,
    duration_ms: int,
) -> bool:
    """Avoid closing Spotify on brief API glitches mid-song."""
    if saw_target_streak < 2:
        return False
    return last_progress_ms >= _end_threshold_ms(duration_ms)


def _clean_track_uri(uri: str | None) -> str:
    u = (uri or "").strip()
    if u.lower().endswith(":play"):
        u = u[: -5]
    return u


def _uris_match(a: str, b: str) -> bool:
    return _clean_track_uri(a).casefold() == _clean_track_uri(b).casefold()


def _duration_ms(track_obj: dict[str, Any] | None) -> int:
    if isinstance(track_obj, dict):
        try:
            ms = int(track_obj.get("duration_ms") or 0)
            if ms > 0:
                return ms
        except (TypeError, ValueError):
            pass
    return 240_000


def fetch_player_state(access_token: str) -> dict[str, Any] | None:
    """Return player JSON, or None when nothing is playing (HTTP 204)."""
    try:
        r = httpx.get(
            "https://api.spotify.com/v1/me/player",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        logger.debug("spotify player poll failed: %s", exc)
        return {}
    if r.status_code == 204:
        return None
    if r.status_code != 200:
        logger.debug("spotify player poll HTTP %s", r.status_code)
        return {}
    data = r.json()
    return data if isinstance(data, dict) else {}


def _watch_and_close(
    watch_id: int,
    target_uri: str,
    track_obj: dict[str, Any] | None,
    access_token: str | None,
) -> None:
    global _active_watch_id
    target = _clean_track_uri(target_uri)
    if not target:
        return
    duration_ms = _duration_ms(track_obj)
    end_threshold = _end_threshold_ms(duration_ms)
    deadline = time.time() + (duration_ms / 1000.0) + 120.0
    saw_target_streak = 0
    last_progress = 0
    poll = poll_interval_s()

    try:
        if not access_token:
            wait_s = (duration_ms / 1000.0) + 8.0
            logger.info(
                "spotify_auto_close: no user token; sleeping %.1fs then closing Spotify",
                wait_s,
            )
            time.sleep(min(wait_s, 900.0))
        else:
            while time.time() < deadline:
                with _watch_lock:
                    if watch_id != _active_watch_id:
                        logger.debug("spotify_auto_close: superseded watch %s", watch_id)
                        return
                state = fetch_player_state(access_token)
                if isinstance(state, dict) and state:
                    item = state.get("item")
                    if isinstance(item, dict):
                        cur_uri = str(item.get("uri") or "")
                        progress = int(state.get("progress_ms") or 0)
                        playing = bool(state.get("is_playing"))
                        if cur_uri and _uris_match(cur_uri, target):
                            saw_target_streak = min(saw_target_streak + 1, 20)
                            last_progress = max(last_progress, progress)
                            if progress >= end_threshold and not playing:
                                time.sleep(poll)
                                confirm = fetch_player_state(access_token)
                                if isinstance(confirm, dict) and confirm:
                                    c_item = confirm.get("item")
                                    c_prog = (
                                        int(confirm.get("progress_ms") or 0)
                                        if isinstance(c_item, dict)
                                        else 0
                                    )
                                    if c_prog >= end_threshold and not bool(
                                        confirm.get("is_playing")
                                    ):
                                        break
                            if progress >= max(0, duration_ms - 2500):
                                time.sleep(2.5)
                                last_progress = max(last_progress, progress)
                                break
                        elif should_close_after_track_change(
                            saw_target_streak=saw_target_streak,
                            last_progress_ms=last_progress,
                            duration_ms=duration_ms,
                        ):
                            logger.info(
                                "spotify_auto_close: track changed after %.0f%% — closing",
                                100.0 * last_progress / max(duration_ms, 1),
                            )
                            break
                elif (
                    state is None
                    and should_close_after_track_change(
                        saw_target_streak=saw_target_streak,
                        last_progress_ms=last_progress,
                        duration_ms=duration_ms,
                    )
                ):
                    break
                time.sleep(poll)

        with _watch_lock:
            if watch_id != _active_watch_id:
                return
        from mango.integrations.spotify.spotify_windows_ui import quit_spotify_processes

        if quit_spotify_processes():
            logger.info("spotify_auto_close: closed Spotify after track ended")
        else:
            logger.debug("spotify_auto_close: Spotify already not running")
    except Exception:
        logger.warning("spotify_auto_close watcher failed", exc_info=True)


def schedule_close_when_track_ends(
    *,
    track_uri: str | None,
    track_obj: dict[str, Any] | None,
    access_token: str | None = None,
) -> None:
    """Start a background watcher; a newer play cancels the previous watcher."""
    global _active_watch_id
    if not auto_close_when_done_enabled():
        return
    target = _clean_track_uri(track_uri)
    if not target or not target.lower().startswith("spotify:track:"):
        return
    with _watch_lock:
        _active_watch_id += 1
        watch_id = _active_watch_id
    threading.Thread(
        target=_watch_and_close,
        args=(watch_id, target, track_obj, access_token),
        daemon=True,
        name=f"spotify-auto-close-{watch_id}",
    ).start()
    logger.info("spotify_auto_close: scheduled for %s", target[:60])
