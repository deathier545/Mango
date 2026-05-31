"""Schedule Windows toast reminders persisted across restarts."""

from __future__ import annotations

from typing import Any

import mango.reminder_watchdog as rw

DESCRIPTION = (
    "Schedule, list, or cancel timed reminders. Reminders show as Windows notifications at the due time. "
    "Use when the user asks to be reminded later or at a relative time (minutes from now)."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["add", "list", "cancel"],
            "description": "add = new reminder; list = pending reminders; cancel = remove by id.",
        },
        "minutes_from_now": {
            "type": "number",
            "description": "For action add only; positive minutes until fire (fractional allowed).",
        },
        "message": {
            "type": "string",
            "description": "Reminder text shown in the toast when add.",
        },
        "reminder_id": {
            "type": "string",
            "description": "For cancel — id returned when the reminder was added.",
        },
    },
    "required": ["action"],
    "additionalProperties": False,
}


def run(
    action: str,
    *,
    minutes_from_now: float | None = None,
    message: str | None = None,
    reminder_id: str | None = None,
) -> str:
    act = (action or "").strip().casefold()
    if act == "list":
        return rw.list_reminders_text()
    if act == "cancel":
        return rw.cancel_reminder(reminder_id or "")
    if act == "add":
        if minutes_from_now is None:
            return "Error: minutes_from_now required for add."
        _, summary = rw.add_reminder_minutes(float(minutes_from_now), message or "")
        return summary
    return "Error: action must be add, list, or cancel."
