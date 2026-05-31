"""One-shot relative timer with Windows toast when done (in-process; clears on Mango exit)."""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "Start a simple countdown timer that shows a Windows notification when it finishes. "
    "Does not survive Mango restarting — use reminders for persistent alerts."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "seconds": {
            "type": "integer",
            "description": "Duration in seconds (1–86400).",
        },
        "label": {
            "type": "string",
            "description": "Short label shown in the toast.",
        },
    },
    "required": ["seconds"],
    "additionalProperties": False,
}


def run(seconds: int, label: str = "") -> str:
    sec = max(1, min(int(seconds), 86_400))
    lbl = (label or "").strip() or "Timer finished"

    def fire() -> None:
        try:
            from plyer import notification

            notification.notify(
                title="Mango timer",
                message=lbl[:256],
                app_name="Mango",
                timeout=12,
            )
        except Exception:
            logger.warning("Timer toast failed", exc_info=True)

    t = threading.Timer(float(sec), fire)
    t.daemon = True
    t.start()
    return f"Timer started for {sec} seconds."
