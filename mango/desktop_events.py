"""Structured desktop events for Electron log parsing."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def emit_desktop_event(payload: dict[str, Any]) -> None:
    """Emit a single-line JSON event the Electron shell can parse."""
    try:
        line = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        logger.info("MANGO_EVENT: %s", line)
    except Exception:
        logger.warning("desktop_events: could not emit payload", exc_info=True)
