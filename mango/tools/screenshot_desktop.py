"""Capture primary or chosen monitor to PNG under Pictures/MangoScreenshots."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "Capture the desktop to a PNG file. Saves under the user's Pictures/MangoScreenshots folder. "
    "Returns the file path for reference."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "monitor_index": {
            "type": "integer",
            "description": "mss monitor index: 0=all monitors combined, 1=primary, etc. Default 1.",
        },
    },
    "additionalProperties": False,
}


def run(monitor_index: int = 1) -> str:
    try:
        import mss
    except ImportError as exc:
        return f"Screenshot unavailable ({exc}). Install mss."

    root = Path.home() / "Pictures" / "MangoScreenshots"
    root.mkdir(parents=True, exist_ok=True)
    fp = root / f"mango_{int(time.time())}.png"
    idx = int(monitor_index)
    try:
        with mss.mss() as sct:
            n = len(sct.monitors)
            if idx <= 0:
                mon = -1 if n > 1 else 1
            else:
                mon = min(idx, n - 1)
            path = sct.shot(mon=mon, output=str(fp))
    except Exception as exc:
        logger.warning("screenshot failed", exc_info=True)
        return f"Screenshot failed: {exc}"
    return f"Saved screenshot to {path}"
