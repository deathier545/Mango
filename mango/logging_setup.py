"""Central logging for Mango (see MANGO_LOG_LEVEL in .env.example)."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging() -> None:
    """Configure handlers once. Default INFO; set MANGO_LOG_LEVEL=DEBUG when developing."""
    level_name = os.getenv("MANGO_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = "%(asctime)s %(levelname)-5s [%(name)s] %(message)s"
    datefmt = "%H:%M:%S"
    # Avoid UnicodeEncodeError on Windows consoles with legacy code pages.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(errors="replace")
        except Exception:
            pass
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    log_file = os.getenv("MANGO_LOG_FILE", "").strip()
    if log_file:
        try:
            max_bytes = int(os.getenv("MANGO_LOG_MAX_BYTES", "1048576").strip() or "1048576")
            backups = int(os.getenv("MANGO_LOG_BACKUPS", "5").strip() or "5")
        except ValueError:
            max_bytes = 1048576
            backups = 5
        path = Path(log_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=max(64 * 1024, max_bytes),
            backupCount=max(1, backups),
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
        root.addHandler(file_handler)
    root.setLevel(level)

    # asyncio is noisy when PYTHONDEVMODE=1 (e.g. run-dev.ps1).
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Third-party noise (enable with MANGO_VERBOSE_HTTP=1)
    verbose_http = os.getenv("MANGO_VERBOSE_HTTP", "").strip() in ("1", "true", "yes")
    if not verbose_http:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        # Groq SDK DEBUG logs full JSON bodies (tools + messages); keep quiet unless verbose.
        logging.getLogger("groq").setLevel(logging.WARNING)
        logging.getLogger("groq._base_client").setLevel(logging.WARNING)

    # faster_whisper logs "Processing audio with duration …" at INFO on every decode;
    # Whisper streaming wake triggers that often — keep quiet unless explicitly verbose.
    if os.getenv("MANGO_VERBOSE_FASTER_WHISPER", "").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        logging.getLogger("faster_whisper").setLevel(logging.WARNING)


def mask_secret(value: str, prefix_keep: int = 7, suffix_keep: int = 4) -> str:
    """Avoid leaking API keys in logs."""
    if not value:
        return "(empty)"
    if len(value) <= prefix_keep + suffix_keep:
        return "***"
    return f"{value[:prefix_keep]}…{value[-suffix_keep:]}"
