"""Best-effort Spotify window foreground / minimize on Windows.

Used after desktop Connect plays, URI hand-offs, and media-key transport so the
app can briefly come forward for a reliable track change, then return to a
minimized state when ``MANGO_SPOTIFY_MINIMIZED`` prefers that end state.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import time
from ctypes import wintypes

logger = logging.getLogger(__name__)

GW_OWNER = 4
SW_RESTORE = 9
SW_SHOW = 5
SW_SHOWMINNOACTIVE = 7


def minimized_launch_preferred() -> bool:
    raw = os.getenv("MANGO_SPOTIFY_MINIMIZED", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def track_change_ui_delay_s() -> float:
    try:
        ms = float(os.getenv("MANGO_SPOTIFY_TRACK_CHANGE_UI_MS", "400").strip())
    except ValueError:
        ms = 400.0
    ms = max(50.0, min(ms, 3000.0))
    return ms / 1000.0


def track_change_window_cycle_enabled() -> bool:
    """Windows + user wants minimized end-state after track-change UI nudges."""
    return sys.platform == "win32" and minimized_launch_preferred()


def _spotify_pids() -> set[int]:
    try:
        import psutil
    except ImportError:
        return set()
    out: set[int] = set()
    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = (p.info.get("name") or "").lower()
            if name == "spotify.exe" and p.info.get("pid") is not None:
                out.add(int(p.info["pid"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError, ValueError):
            continue
    return out


def _enum_candidate_hwnds(pids: set[int]) -> list[tuple[int, int]]:
    """Return ``(hwnd, area)`` for visible top-level Spotify windows."""
    if not pids:
        return []
    user32 = ctypes.windll.user32
    found: list[tuple[int, int]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd: int, _lp: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.GetWindow(hwnd, GW_OWNER):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in pids:
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        w = int(rect.right) - int(rect.left)
        h = int(rect.bottom) - int(rect.top)
        if w < 120 or h < 120:
            return True
        found.append((hwnd, w * h))
        return True

    user32.EnumWindows(_cb, 0)
    found.sort(key=lambda t: t[1], reverse=True)
    return found


def _bring_hwnd_forward(hwnd: int) -> None:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.ShowWindow(hwnd, SW_RESTORE)
    fg = user32.GetForegroundWindow()
    cur_tid = kernel32.GetCurrentThreadId()
    fg_tid = int(user32.GetWindowThreadProcessId(fg, None) or 0)
    if fg_tid and fg_tid != cur_tid:
        user32.AttachThreadInput(cur_tid, fg_tid, True)
    try:
        user32.SetForegroundWindow(hwnd)
    finally:
        if fg_tid and fg_tid != cur_tid:
            user32.AttachThreadInput(cur_tid, fg_tid, False)


def foreground_spotify_windows() -> int:
    """Raise Spotify's largest visible top-level window, if any. Returns count nudged."""
    if sys.platform != "win32":
        return 0
    pids = _spotify_pids()
    cands = _enum_candidate_hwnds(pids)
    if not cands:
        logger.debug("spotify_windows_ui: no Spotify HWNDs to foreground")
        return 0
    hwnd = cands[0][0]
    try:
        _bring_hwnd_forward(hwnd)
        logger.info("spotify_windows_ui: foreground Spotify hwnd=%s", hwnd)
        return 1
    except Exception:
        logger.debug("spotify foreground failed", exc_info=True)
        return 0


def minimize_spotify_windows() -> int:
    """Minimize visible top-level Spotify windows (``SW_SHOWMINNOACTIVE``)."""
    if sys.platform != "win32":
        return 0
    pids = _spotify_pids()
    cands = _enum_candidate_hwnds(pids)
    user32 = ctypes.windll.user32
    n = 0
    for hwnd, _area in cands:
        try:
            user32.ShowWindow(hwnd, SW_SHOWMINNOACTIVE)
            n += 1
        except Exception:
            logger.debug("spotify minimize failed for hwnd=%s", hwnd, exc_info=True)
    if n:
        logger.info("spotify_windows_ui: minimized %d Spotify window(s)", n)
    return n


def pause_then_minimize_spotify() -> None:
    """Wait briefly for Spotify to apply a queue change, then minimize."""
    if not track_change_window_cycle_enabled():
        return
    time.sleep(track_change_ui_delay_s())
    minimize_spotify_windows()


def restart_wait_s() -> float:
    try:
        sec = float(os.getenv("MANGO_SPOTIFY_RESTART_WAIT_S", "0.9").strip())
    except ValueError:
        sec = 0.9
    return max(0.3, min(sec, 5.0))


def restart_on_new_track_enabled() -> bool:
    """Close Spotify before opening the next track (Windows desktop handoff)."""
    if sys.platform != "win32":
        return False
    raw = os.getenv("MANGO_SPOTIFY_RESTART_ON_PLAY", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def quit_spotify_processes() -> bool:
    """Terminate Spotify.exe if running. Returns True if a process was killed."""
    if sys.platform != "win32":
        return False
    if not _spotify_pids():
        return False
    try:
        from mango.tools import close_app

        msg = close_app.run("spotify")
        logger.info("spotify_windows_ui: quit before new track: %s", msg)
        return "closed" in msg.casefold() or "terminated" in msg.casefold()
    except Exception:
        logger.warning("spotify quit before play failed", exc_info=True)
        return False


def restart_spotify_for_new_track() -> None:
    """User-requested: fully close Spotify, brief wait, then next launch is a clean open."""
    if not restart_on_new_track_enabled():
        return
    if not quit_spotify_processes():
        return
    time.sleep(restart_wait_s())


def shell_open_spotify_uri_visible(uri: str) -> bool:
    """``ShellExecuteW`` with ``SW_SHOW`` (foreground-friendly)."""
    if sys.platform != "win32":
        return False
    try:
        ret = int(
            ctypes.windll.shell32.ShellExecuteW(  # type: ignore[attr-defined]
                None,
                "open",
                uri,
                None,
                None,
                SW_SHOW,
            )
        )
    except Exception:
        logger.debug("ShellExecuteW visible open failed", exc_info=True)
        return False
    if ret > 32:
        return True
    logger.warning("ShellExecuteW (SW_SHOW) returned %s for uri=%r", ret, uri[:80])
    return False
