"""Optional quiet-hours window (e.g. skip startup intro, nudge shorter replies)."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def parse_quiet_hours(raw: str) -> tuple[int, int] | None:
    """Parse ``22-7`` as 22:00–07:00 local; ``9-17`` as 09:00–17:00."""
    s = (raw or "").strip()
    if not s or "-" not in s:
        return None
    left, _, right = s.partition("-")
    try:
        a = int(left.strip())
        b = int(right.strip())
    except ValueError:
        logger.warning("Invalid MANGO_QUIET_HOURS=%r — ignoring.", raw)
        return None
    a %= 24
    b %= 24
    return (a, b)


def in_quiet_hours(now: datetime, window: tuple[int, int] | None) -> bool:
    if window is None:
        return False
    start, end = window
    h = now.hour
    if start == end:
        return False
    if start > end:
        return h >= start or h < end
    return start <= h < end


def local_now(tz_name: str | None) -> datetime:
    if tz_name:
        try:
            return datetime.now(ZoneInfo(tz_name))
        except Exception:
            logger.debug("quiet_hours: bad tz %r", tz_name, exc_info=True)
    return datetime.now().astimezone()
