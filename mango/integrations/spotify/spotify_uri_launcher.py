"""Spotify URI launch and desktop handoff helpers."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Any

logger = logging.getLogger(__name__)


def minimized_launch_preferred() -> bool:
    raw = os.getenv("MANGO_SPOTIFY_MINIMIZED", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def spotify_exe_windows() -> str | None:
    """Return path to Spotify.exe if installed in the usual Windows locations."""
    if sys.platform != "win32":
        return None
    override = os.getenv("MANGO_SPOTIFY_EXE", "").strip().strip('"')
    if override and os.path.isfile(override):
        return override
    local = os.environ.get("LOCALAPPDATA", "").strip()
    roaming = os.environ.get("APPDATA", "").strip()
    candidates = []
    if local:
        candidates.append(os.path.join(local, "Spotify", "Spotify.exe"))
    if roaming:
        candidates.append(os.path.join(roaming, "Spotify", "Spotify.exe"))
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None


def spotify_exe_uri_param(uri: str) -> str:
    """Spotify.exe --uri works better without trailing `:play` on many Windows builds."""
    u = uri.strip()
    low = u.lower()
    if low.endswith(":play"):
        return u[: len(u) - 5]
    return u


def launch_uri_via_spotify_exe(uri: str, *, prefer_minimized: bool | None = None) -> bool:
    exe = spotify_exe_windows()
    if not exe:
        return False
    if prefer_minimized is None:
        prefer_minimized = minimized_launch_preferred()
    param = spotify_exe_uri_param(uri)
    args = [exe, f"--uri={param}"]
    if prefer_minimized:
        args.append("--minimized")
    try:
        cf = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        cwd = os.path.dirname(exe) or None
        popen_kw: dict[str, Any] = {"cwd": cwd, "creationflags": cf}
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7 if prefer_minimized else 1
        popen_kw["startupinfo"] = si
        subprocess.Popen(args, **popen_kw)
        logger.info("Spotify.exe --uri launch ok exe=%s minimized=%s", exe, prefer_minimized)
        return True
    except Exception:
        logger.warning("Spotify.exe --uri launch failed", exc_info=True)
        return False


def shell_open_spotify_uri_minimized(uri: str) -> bool:
    """Hand URI to registered spotify handler without activating window (best effort)."""
    import ctypes

    SW_SHOWMINNOACTIVE = 7
    try:
        ret = int(
            ctypes.windll.shell32.ShellExecuteW(  # type: ignore[attr-defined]
                None,
                "open",
                uri,
                None,
                None,
                SW_SHOWMINNOACTIVE,
            )
        )
    except Exception:
        logger.debug("ShellExecuteW minimized open failed", exc_info=True)
        return False
    if ret > 32:
        logger.info("Spotify URI ShellExecuteW minimized ok ret=%s", ret)
        return True
    logger.warning("ShellExecuteW returned %s for uri=%r", ret, uri[:80])
    return False


def uri_for_desktop_playback(uri: str) -> str:
    """Desktop often only selects spotify:track:ID while playing; `:play` forces playback."""
    import re

    u = uri.strip()
    if u.lower().endswith(":play"):
        return u
    if re.fullmatch(r"spotify:track:[A-Za-z0-9]+", u, re.IGNORECASE):
        return f"{u}:play"
    return u


def launch_uri(uri: str) -> None:
    """Open spotify URI with Windows handoff/minimize behavior, or xdg/open on non-Windows."""
    if sys.platform != "win32":
        import shutil

        opener = shutil.which("xdg-open") or shutil.which("open")
        if not opener:
            raise OSError("No xdg-open or open binary for Spotify URI")
        subprocess.run([opener, uri], check=False, timeout=30)
        return

    import mango.integrations.spotify.spotify_windows_ui as swu

    if swu.track_change_window_cycle_enabled():
        swu.foreground_spotify_windows()
        if swu.shell_open_spotify_uri_visible(uri):
            swu.pause_then_minimize_spotify()
            return
        if launch_uri_via_spotify_exe(uri, prefer_minimized=False):
            swu.pause_then_minimize_spotify()
            return
        try:
            cf = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.run(
                ["cmd", "/c", "start", "", uri],
                timeout=30,
                capture_output=True,
                text=True,
                creationflags=cf,
            )
            if proc.returncode == 0:
                logger.debug("Spotify URI start (visible) ok")
                swu.pause_then_minimize_spotify()
                return
            logger.warning("start visible failed rc=%s err=%r", proc.returncode, (proc.stderr or "")[:200])
        except Exception:
            logger.debug("start visible fallback failed", exc_info=True)
        try:
            os.startfile(uri)  # type: ignore[attr-defined]
        except Exception:
            logger.warning("os.startfile Spotify URI failed", exc_info=True)
            raise
        swu.pause_then_minimize_spotify()
        return

    if minimized_launch_preferred():
        if shell_open_spotify_uri_minimized(uri):
            return
        if launch_uri_via_spotify_exe(uri):
            return
    else:
        if launch_uri_via_spotify_exe(uri):
            return
        if shell_open_spotify_uri_minimized(uri):
            return

    if minimized_launch_preferred():
        try:
            cf = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.run(
                ["cmd", "/c", "start", "/min", "", uri],
                timeout=30,
                capture_output=True,
                text=True,
                creationflags=cf,
            )
            if proc.returncode == 0:
                logger.debug("Spotify URI start /min ok")
                return
            logger.warning("start /min failed rc=%s err=%r", proc.returncode, (proc.stderr or "")[:200])
        except Exception:
            logger.debug("start /min fallback failed", exc_info=True)

    os.startfile(uri)  # type: ignore[attr-defined]
