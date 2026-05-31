"""Persist recent conversation to disk on exit."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def save_session_snapshot(
    messages: list[dict[str, Any]],
    log_dir: Path,
    *,
    enabled: bool = True,
) -> None:
    """Write last turns to ``log_dir/session-UTCstamp.md`` (best-effort)."""
    if not enabled:
        logger.debug("Session snapshot skipped (MANGO_SESSION_LOG disabled).")
        return
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        path = log_dir / f"session-{stamp}.md"
        lines: list[str] = [f"# Mango session {stamp}Z\n"]
        for m in messages:
            role = m.get("role", "")
            if role == "system":
                content = (m.get("content") or "")[:800]
                lines.append(f"## system (truncated)\n{content}\n")
                continue
            content = (m.get("content") or "").strip()
            if role == "assistant" and m.get("tool_calls"):
                lines.append(f"## assistant (tool_calls)\n{ m.get('tool_calls') }\n")
                continue
            if len(content) > 12_000:
                content = content[:12_000] + "\n…[truncated]"
            lines.append(f"## {role}\n{content}\n")
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Session log written: %s", path)
    except Exception:
        logger.warning("Session log failed", exc_info=True)
