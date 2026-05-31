"""Windows desktop toast notification."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "Show a Windows toast notification with a title and short message. "
    "Use for alerts that should not interrupt speech output."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Toast title."},
        "message": {"type": "string", "description": "Toast body text."},
    },
    "required": ["title", "message"],
    "additionalProperties": False,
}


def run(title: str, message: str) -> str:
    t = (title or "").strip()[:120] or "Mango"
    m = (message or "").strip()[:500] or " "
    try:
        from plyer import notification

        notification.notify(title=t, message=m, app_name="Mango", timeout=10)
    except Exception as exc:
        logger.warning("desktop_notify failed", exc_info=True)
        return f"Notification failed: {exc}"
    return "Notification sent."
