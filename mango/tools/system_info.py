"""Read-only system facts (time, power, CPU/RAM)."""

from __future__ import annotations

import datetime as dt
import logging

import psutil

logger = logging.getLogger(__name__)


DESCRIPTION = (
    "Read non-sensitive system information: local time, battery status, CPU and memory usage."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["time", "battery", "cpu_ram", "all"],
            "description": "Which information to fetch.",
        },
    },
    "required": ["kind"],
    "additionalProperties": False,
}


def run(kind: str) -> str:
    k = (kind or "all").strip().lower()
    parts: list[str] = []

    def append_time() -> None:
        now = dt.datetime.now().astimezone()
        parts.append(f"Local time is {now.strftime('%A, %B %d %Y %I:%M %p %Z')}.")

    def append_battery() -> None:
        try:
            bat = psutil.sensors_battery()
        except Exception as exc:  # pragma: no cover
            logger.warning("psutil.sensors_battery failed: %s", exc, exc_info=True)
            parts.append(f"Battery info unavailable ({exc}).")
            return
        if bat is None:
            parts.append("No battery sensor detected (likely desktop).")
            return
        pct = int(round(bat.percent))
        plugged = "plugged in" if bat.power_plugged else "on battery"
        parts.append(f"Battery {pct}% ({plugged}).")

    def append_cpu_ram() -> None:
        cpu = psutil.cpu_percent(interval=0.25)
        vm = psutil.virtual_memory()
        parts.append(
            f"CPU usage about {cpu:.0f}%. Memory {vm.percent:.0f}% used "
            f"({vm.used // (1024**3)} GiB of {vm.total // (1024**3)} GiB)."
        )

    if k in {"time", "all"}:
        append_time()
    if k in {"battery", "all"}:
        append_battery()
    if k in {"cpu_ram", "all"}:
        append_cpu_ram()

    if not parts:
        return "Unknown kind. Use time, battery, cpu_ram, or all."
    return " ".join(parts)
