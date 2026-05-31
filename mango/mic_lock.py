"""Exclusive access to the default microphone between PTT, wake, VAD always-listen, and hands-free."""

from __future__ import annotations

import threading

MIC_LOCK = threading.RLock()


def mic_is_busy() -> bool:
    """True if another thread is holding ``MIC_LOCK`` (PTT or hands-free recording)."""
    if MIC_LOCK.acquire(blocking=False):
        MIC_LOCK.release()
        return False
    return True
