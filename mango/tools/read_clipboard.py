"""Read Windows clipboard text (no write — avoids silent overwrites)."""

from __future__ import annotations

import logging
import subprocess
import sys
from typing import Any

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "Read plain text from the Windows clipboard. Use when the user refers to pasted content "
    "or asks what's copied."
)

SCHEMA = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


def run(**_: Any) -> str:
    if sys.platform != "win32":
        return "Clipboard read is only implemented on Windows."
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-Clipboard -Raw",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=12,
            creationflags=creationflags,
        )
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError) as exc:
        logger.warning("Clipboard read failed: %s", exc)
        return f"Could not read clipboard: {exc}"
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return f"Clipboard command failed ({proc.returncode}): {err[:400]}"
    text = (proc.stdout or "").strip()
    if not text:
        return "Clipboard is empty or non-text."
    if len(text) > 16_000:
        return text[:16_000] + "\n…[truncated for LLM]"
    return text
