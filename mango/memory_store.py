"""Opt-in persistent conversation memory (JSON on disk, survives restarts and calendar days)."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ROLLING = "rolling.json"
_DAY_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")


def _utc_date_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _read_payload(path: Path) -> list[dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read memory file %s: %s", path, exc)
        return []
    if not isinstance(data, dict):
        return []
    msgs = data.get("messages")
    if not isinstance(msgs, list):
        return []
    return [m for m in msgs if isinstance(m, dict)]


def _validate_messages(msgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed = frozenset({"user", "assistant", "tool", "system"})
    out: list[dict[str, Any]] = []
    for m in msgs:
        role = m.get("role")
        if role not in allowed or role == "system":
            continue
        out.append(m)
    return out


def load_persistent_messages(
    memory_dir: Path,
    *,
    max_messages: int,
    merge_days: int,
) -> list[dict[str, Any]]:
    """Load prior turns: prefer ``rolling.json``, else merge last ``merge_days`` daily snapshots."""
    memory_dir.mkdir(parents=True, exist_ok=True)
    rolling = memory_dir / _ROLLING
    combined: list[dict[str, Any]] = []

    if rolling.is_file():
        combined = _validate_messages(_read_payload(rolling))

    if not combined and merge_days > 0:
        day_dir = memory_dir / "days"
        if day_dir.is_dir():
            paths = sorted(
                p for p in day_dir.iterdir() if p.is_file() and _DAY_NAME.match(p.name)
            )
            if paths:
                candidates = paths[-merge_days:]
                for p in reversed(candidates):
                    chunk = _validate_messages(_read_payload(p))
                    if chunk:
                        combined = chunk
                        break

    if not combined:
        return []

    combined = combined[-max(1, min(max_messages, 4096)) :]
    logger.info(
        "Persistent memory: loaded %d prior message(s) from %s",
        len(combined),
        memory_dir,
    )
    return combined


def save_persistent_messages(
    memory_dir: Path,
    messages_non_system: list[dict[str, Any]],
    *,
    max_messages: int,
    write_daily_snapshot: bool,
) -> None:
    """Atomically write ``rolling.json``; optionally mirror the same payload to ``days/UTC-date.json``."""
    memory_dir.mkdir(parents=True, exist_ok=True)
    tail = messages_non_system[-max(1, min(max_messages, 4096)) :]
    payload = {
        "version": 1,
        "saved_at": datetime.now(UTC).isoformat(),
        "messages": tail,
    }
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    rolling = memory_dir / _ROLLING
    _atomic_write(rolling, text)

    if write_daily_snapshot:
        day_dir = memory_dir / "days"
        day_dir.mkdir(parents=True, exist_ok=True)
        day_path = day_dir / f"{_utc_date_str()}.json"
        _atomic_write(day_path, text)


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        logger.exception("Failed to write memory file %s", path)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
