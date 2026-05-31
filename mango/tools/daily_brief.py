"""Daily briefing: memory, reminders, system, bridge status."""

from __future__ import annotations

from typing import Any

from mango.smart.smart_brief import build_daily_brief

DESCRIPTION = (
    "Produce a short daily briefing: memory card highlights, recent captures, "
    "pending reminders, system info, Discord bridge status."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


def run(**_: Any) -> str:
    return build_daily_brief()
