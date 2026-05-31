"""Wake phrase parsing and acceptance checks."""

from __future__ import annotations

import logging
import re

_logger = logging.getLogger(__name__)


def compile_wake_phrase_regex(phrase_csv: str) -> re.Pattern[str]:
    """Word-boundary match for one phrase, or alternation for CSV phrases."""
    raw = (phrase_csv or "").strip() or "mango"
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        parts = ["mango"]
    if len(parts) == 1:
        inner = re.escape(parts[0])
    else:
        inner = "|".join(re.escape(p) for p in parts)
    return re.compile(r"\b(?:" + inner + r")\b", re.IGNORECASE)


def phrase_accepted(
    text: str,
    *,
    phrase_re: re.Pattern[str],
    max_offset: int,
    suppress_active: bool,
    log_match: bool = True,
    logger: logging.Logger | None = None,
) -> bool:
    """Validate wake phrase text match and position against host policy."""
    log = logger or _logger
    if suppress_active:
        log.debug("Wake transcript discarded (turn in progress).")
        return False
    if not text:
        return False
    m = phrase_re.search(text)
    if not m:
        log.debug("Wake transcript (no phrase): %r", text[:160])
        return False
    phrase_idx = m.start()
    if phrase_idx < 0 or phrase_idx > max_offset:
        log.debug(
            "Wake phrase position rejected (idx=%s max=%s): %r",
            phrase_idx,
            max_offset,
            text[:160],
        )
        return False
    if log_match:
        log.info("Wake phrase detected from: %r", text[:120])
    return True
