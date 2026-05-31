"""Persist tool timeline entries with durations for Smart UI."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from mango.metrics import current_correlation_id
from mango.smart.smart_store import smart_dir

logger = logging.getLogger(__name__)

_pending: dict[str, float] = {}


def _key(tool: str, correlation_id: str | None) -> str:
    return f"{correlation_id or 'none'}::{tool}"


def record_tool_start(tool: str, *, risk: str) -> None:
    _pending[_key(tool, current_correlation_id() or None)] = time.monotonic()


def record_tool_done(
    tool: str,
    *,
    risk: str,
    ok: bool,
    error_code: str | None = None,
    result_preview: str = "",
) -> dict[str, Any] | None:
    cid = current_correlation_id() or None
    k = _key(tool, cid)
    started = _pending.pop(k, None)
    duration_ms = int((time.monotonic() - started) * 1000) if started is not None else None
    entry: dict[str, Any] = {
        "ts": time.time(),
        "correlation_id": cid,
        "tool": tool,
        "risk": risk,
        "ok": ok,
        "duration_ms": duration_ms,
        "error_code": error_code,
        "result_preview": (result_preview or "")[:240],
    }
    try:
        path = smart_dir()
        path.mkdir(parents=True, exist_ok=True)
        log_path = path / "timeline.jsonl"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        logger.debug("timeline write failed", exc_info=True)
    return entry
