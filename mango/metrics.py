"""Lightweight structured metrics and correlation IDs."""

from __future__ import annotations

import contextvars
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CORRELATION_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "mango_correlation_id",
    default="",
)


def start_turn_correlation(source: str) -> str:
    cid = f"{source}-{uuid.uuid4().hex[:12]}"
    _CORRELATION_ID.set(cid)
    return cid


def current_correlation_id() -> str:
    return _CORRELATION_ID.get("")


def clear_correlation_id() -> None:
    _CORRELATION_ID.set("")


def metrics_jsonl_path() -> Path | None:
    raw = os.getenv("MANGO_METRICS_JSONL", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def emit_metric(event: str, **fields: Any) -> None:
    payload = {
        "ts_unix": time.time(),
        "event": event,
        "correlation_id": current_correlation_id() or None,
        **fields,
    }
    logger.info("metric %s", payload)
    path = metrics_jsonl_path()
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        logger.debug("metrics jsonl write failed path=%s", path, exc_info=True)
