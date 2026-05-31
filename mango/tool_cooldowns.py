"""Per-tool cooldown limits to reduce accidental rapid re-triggers."""

from __future__ import annotations

import time

TOOL_COOLDOWN_SECONDS: dict[str, float] = {
    "desktop_notify": 3.0,
    "phone_call": 30.0,
    "discord_voice": 5.0,
    "volume_control": 1.0,
    "clipboard_write": 2.0,
    "run_routine": 10.0,
}


def check_tool_cooldown(last_run: dict[str, float], name: str) -> str | None:
    """Return an error string when the tool is still on cooldown, else None."""
    seconds = TOOL_COOLDOWN_SECONDS.get(name)
    if seconds is None:
        return None
    now = time.time()
    last = last_run.get(name, 0.0)
    remaining = seconds - (now - last)
    if remaining > 0:
        return (
            f"ERR_TOOL_COOLDOWN:{name} was used recently — wait {remaining:.1f}s before retrying."
        )
    return None


def record_tool_run(last_run: dict[str, float], name: str) -> None:
    if name in TOOL_COOLDOWN_SECONDS:
        last_run[name] = time.time()
