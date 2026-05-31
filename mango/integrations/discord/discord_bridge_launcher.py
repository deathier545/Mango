"""Start and wait for the Discord voice bridge (``python -m mango --discord-voice``)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

from mango.integrations.discord.discord_voice_client import (
    CONTROL_HEADER,
    control_port,
    control_secret,
)

logger = logging.getLogger(__name__)

_start_lock = threading.Lock()
_last_spawn_monotonic = 0.0

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def workspace_root() -> Path:
    return Path(__file__).resolve().parent.parent


def auto_start_enabled() -> bool:
    raw = os.getenv("MANGO_DISCORD_AUTO_START_BRIDGE", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return os.getenv("MANGO_DESKTOP", "").strip().lower() in ("1", "true", "yes", "on")


def bridge_poll_interval_seconds(default: float = 1.5) -> float:
    raw = os.getenv("MANGO_DISCORD_BRIDGE_POLL_INTERVAL_S", "").strip()
    if not raw:
        return max(0.25, min(float(default), 5.0))
    try:
        return max(0.25, min(float(raw), 5.0))
    except ValueError:
        logger.warning("Invalid MANGO_DISCORD_BRIDGE_POLL_INTERVAL_S=%r — using %.2fs", raw, default)
        return max(0.25, min(float(default), 5.0))


def _poll_interval_for_elapsed(base_poll_interval: float, elapsed_s: float) -> float:
    # Faster early checks reduce perceived startup latency without changing long-tail reliability.
    if elapsed_s < 10.0:
        return min(base_poll_interval, 0.5)
    return base_poll_interval


def bridge_control_reachable(*, timeout: float = 2.0) -> bool:
    port = control_port()
    headers: dict[str, str] = {}
    secret = control_secret()
    if secret:
        headers[CONTROL_HEADER] = secret
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"http://127.0.0.1:{port}/v1/voice/status", headers=headers)
            return r.status_code in (200, 401)
    except (httpx.ConnectError, httpx.TimeoutException):
        return False
    except httpx.HTTPError:
        return True


def _python_executable() -> str:
    root = workspace_root()
    if sys.platform == "win32":
        venv_py = root / ".venv" / "Scripts" / "python.exe"
        if venv_py.is_file():
            return str(venv_py)
    else:
        venv_py = root / ".venv" / "bin" / "python"
        if venv_py.is_file():
            return str(venv_py)
    return sys.executable


def _log_paths() -> tuple[Path, Path]:
    log_dir = workspace_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "discord-voice.log", log_dir / "discord-voice.err.log"


def _spawn_bridge_process() -> tuple[bool, str]:
    global _last_spawn_monotonic
    token = os.getenv("MANGO_DISCORD_BOT_TOKEN", "").strip()
    if not token:
        return (
            False,
            "Cannot start Discord bridge: MANGO_DISCORD_BOT_TOKEN is not set in .env.",
        )

    root = workspace_root()
    py = _python_executable()
    out_path, err_path = _log_paths()
    try:
        out_f = open(out_path, "a", encoding="utf-8")
        err_f = open(err_path, "a", encoding="utf-8")
    except OSError as exc:
        return False, f"Cannot open bridge log files: {exc}"

    creationflags = CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        proc = subprocess.Popen(
            [py, "-m", "mango", "--discord-voice"],
            cwd=str(root),
            stdout=out_f,
            stderr=err_f,
            creationflags=creationflags,
            start_new_session=True,
        )
    except OSError as exc:
        out_f.close()
        err_f.close()
        return False, f"Failed to launch Discord bridge: {exc}"

    _last_spawn_monotonic = time.monotonic()
    logger.info("Spawned Discord voice bridge pid=%s logs=%s", proc.pid, out_path)
    return (
        True,
        f"Started Discord voice bridge (pid {proc.pid}). Logs: {out_path}",
    )


def ensure_discord_bridge_running(
    *,
    wait_seconds: float = 90.0,
    poll_interval: float | None = None,
) -> tuple[bool, str]:
    """Return (ready, message). Spawns the bridge when auto-start is enabled."""
    if bridge_control_reachable():
        return True, "Discord voice bridge is already running."

    if not auto_start_enabled():
        return (
            False,
            "Discord voice bridge is not running. Start it with "
            "`python -m mango --discord-voice` or set MANGO_DISCORD_AUTO_START_BRIDGE=1.",
        )

    base_poll_interval = bridge_poll_interval_seconds(
        1.5 if poll_interval is None else poll_interval
    )

    with _start_lock:
        if bridge_control_reachable():
            return True, "Discord voice bridge is already running."

        recently_spawned = (time.monotonic() - _last_spawn_monotonic) < wait_seconds
        if not recently_spawned:
            ok, msg = _spawn_bridge_process()
            if not ok:
                return False, msg
            spawn_note = msg
        else:
            spawn_note = "Discord bridge is still starting from a recent launch."

        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            elapsed = max(0.0, wait_seconds - max(0.0, deadline - time.monotonic()))
            interval = _poll_interval_for_elapsed(base_poll_interval, elapsed)
            if bridge_control_reachable(timeout=min(interval, 3.0)):
                return True, f"{spawn_note} Bridge HTTP API is ready."
            time.sleep(interval)

    return (
        False,
        f"{spawn_note} Bridge did not become ready within {int(wait_seconds)}s. "
        f"Check logs under logs/discord-voice.err.log for login or token errors.",
    )
