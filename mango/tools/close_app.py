"""Close vetted Windows processes via ``taskkill /IM`` (allowlist only)."""

from __future__ import annotations

import logging
import subprocess
import sys

from mango.tools.open_app import normalized_app_key

logger = logging.getLogger(__name__)

# Image names for taskkill /IM (Windows). Multiple candidates try alternates (e.g. Calculator UWP vs classic).
_CLOSE_EXE_BY_KEY: dict[str, tuple[str, ...]] = {
    "spotify": ("Spotify.exe",),
    "notepad": ("notepad.exe",),
    "calculator": ("Calculator.exe", "calc.exe"),
    "calc": ("Calculator.exe", "calc.exe"),
    "paint": ("mspaint.exe",),
    "mspaint": ("mspaint.exe",),
    "chrome": ("chrome.exe",),
    "brave": ("brave.exe",),
    "edge": ("msedge.exe",),
    "firefox": ("firefox.exe",),
    "discord": ("Discord.exe",),
    "slack": ("slack.exe",),
    "teams": ("ms-teams.exe", "Teams.exe"),
    "zoom": ("Zoom.exe",),
    "steam": ("steam.exe",),
    "vlc": ("vlc.exe",),
    "code": ("Code.exe",),
    "vscode": ("Code.exe",),
    "whatsapp": ("WhatsApp.exe",),
    "signal": ("Signal.exe",),
    "telegram": ("Telegram.exe",),
    "obs": ("obs64.exe",),
    "obsstudio": ("obs64.exe",),
    "terminal": ("WindowsTerminal.exe",),
    "wt": ("WindowsTerminal.exe",),
    "powershell": ("powershell.exe",),
    "taskmanager": ("Taskmgr.exe",),
    "cmd": ("cmd.exe",),
}

_ALLOWLIST = {e.casefold() for tup in _CLOSE_EXE_BY_KEY.values() for e in tup}


def _taskkill(exe: str) -> tuple[int, str]:
    args = ["taskkill", "/IM", exe]
    kw: dict = {
        "args": args,
        "capture_output": True,
        "text": True,
        "timeout": 35,
    }
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    proc = subprocess.run(**kw)
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    detail = f"{out} {err}".strip()
    return proc.returncode, detail


def run(app_name: str) -> str:
    raw = (app_name or "").strip()
    if not raw:
        return "Error: app_name is empty."
    if sys.platform != "win32":
        return "close_app is only supported on Windows."
    key = normalized_app_key(raw)
    if not key:
        return "Error: app_name is empty."
    candidates = _CLOSE_EXE_BY_KEY.get(key)
    if not candidates:
        hits = ", ".join(sorted(_CLOSE_EXE_BY_KEY))
        return (
            f"Cannot close {raw!r} — only vetted apps are allowed. "
            f"Examples: {hits}."
        )

    last_detail = ""
    not_running = False
    for exe in candidates:
        if exe.casefold() not in _ALLOWLIST:
            logger.error("close_app allowlist mismatch for %r", exe)
            continue
        rc, detail = _taskkill(exe)
        last_detail = detail
        if rc == 0:
            logger.info("close_app: terminated %s (requested as %r)", exe, raw)
            return f"Closed {raw} ({exe})."
        low = detail.casefold()
        if any(
            s in low
            for s in (
                "not running",
                "could not find",
                "not found",
                "no tasks running",
                "there is no running instance",
            )
        ):
            not_running = True
            continue
        logger.warning("close_app: taskkill %r failed rc=%s detail=%r", exe, rc, detail[:500])

    if not_running:
        return f"No running process matched for {raw!r} (it may already be closed)."
    return f"Could not close {raw!r}. Last detail: {last_detail or '(empty)'}"


DESCRIPTION = (
    "Close a desktop application Mango is allowed to stop (Spotify, Notepad, Chrome, Edge, Brave, Firefox, "
    "Discord, Slack, Teams, Zoom, Steam, VLC, VS Code, WhatsApp, Signal, Telegram, OBS, Windows Terminal, "
    "PowerShell, Task Manager, CMD, Calculator, Paint). Uses Windows taskkill for a fixed allowlist only."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "app_name": {
            "type": "string",
            "description": (
                "Same naming style as open_app: e.g. spotify, notepad, chrome, discord, teams, zoom, "
                "vscode, terminal, taskmanager."
            ),
        },
    },
    "required": ["app_name"],
    "additionalProperties": False,
}
