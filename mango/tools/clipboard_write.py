"""Place text on the Windows clipboard."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "Copy text to the system clipboard so the user can paste it elsewhere."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {
            "type": "string",
            "description": "Plain text to copy.",
        },
    },
    "required": ["text"],
    "additionalProperties": False,
}


def run(text: str) -> str:
    raw = text or ""
    if not raw.strip():
        return "Error: empty text."
    try:
        import pyperclip
    except ImportError as exc:
        return f"clipboard_write unavailable ({exc}). Install pyperclip."

    try:
        pyperclip.copy(raw)
    except Exception as exc:
        logger.warning("pyperclip.copy failed", exc_info=True)
        return f"Clipboard write failed: {exc}"
    return f"Copied {len(raw)} characters to clipboard."
