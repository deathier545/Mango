"""Small retry helper for transient network operations."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


def retry_call(
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay_s: float = 0.2,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    retry_if_result: Callable[[T], bool] | None = None,
    label: str = "operation",
) -> T:
    """Run `operation` with bounded retries and linear backoff."""
    tries = max(1, int(attempts))
    delay = max(0.0, float(base_delay_s))
    last_err: BaseException | None = None
    for i in range(1, tries + 1):
        try:
            out = operation()
            if retry_if_result is not None and i < tries and retry_if_result(out):
                wait_s = delay * i
                logger.warning(
                    "%s retry %d/%d due to retryable result; sleeping %.2fs",
                    label,
                    i,
                    tries,
                    wait_s,
                )
                time.sleep(wait_s)
                continue
            return out
        except retry_on as exc:
            last_err = exc
            if i >= tries:
                raise
            wait_s = delay * i
            logger.warning(
                "%s retry %d/%d after %s; sleeping %.2fs",
                label,
                i,
                tries,
                type(exc).__name__,
                wait_s,
            )
            time.sleep(wait_s)
    if last_err is not None:
        raise last_err
    raise RuntimeError(f"{label} failed unexpectedly with no result or exception")
