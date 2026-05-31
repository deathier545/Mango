"""Interruption profile settings for wake and turn behavior."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InterruptionProfile:
    name: str
    min_barge_hold_ms: int
    wake_wait_seconds: float
    wake_silence_multiplier: float


def _override_barge_hold_ms(profile: str, default: int) -> int:
    """Return profile-specific hold threshold with optional env override.

    Supported env vars:
    - MANGO_BARGE_MIN_HOLD_MS (global override)
    - MANGO_BARGE_MIN_HOLD_MS_STRICT / _NORMAL / _FAST (per-profile)
    """
    global_raw = os.getenv("MANGO_BARGE_MIN_HOLD_MS", "").strip()
    profile_raw = os.getenv(f"MANGO_BARGE_MIN_HOLD_MS_{profile.upper()}", "").strip()
    raw = profile_raw or global_raw
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid %s value=%r — using default %d", f"MANGO_BARGE_MIN_HOLD_MS_{profile.upper()}" if profile_raw else "MANGO_BARGE_MIN_HOLD_MS", raw, default)
        return default
    clamped = max(0, min(value, 1200))
    if clamped != value:
        logger.warning(
            "Clamped %s from %d to %d (allowed 0..1200).",
            f"MANGO_BARGE_MIN_HOLD_MS_{profile.upper()}" if profile_raw else "MANGO_BARGE_MIN_HOLD_MS",
            value,
            clamped,
        )
    return clamped


_PROFILES: dict[str, InterruptionProfile] = {
    "strict": InterruptionProfile(
        name="strict",
        min_barge_hold_ms=_override_barge_hold_ms("strict", 220),
        wake_wait_seconds=3.2,
        wake_silence_multiplier=1.2,
    ),
    "normal": InterruptionProfile(
        name="normal",
        min_barge_hold_ms=_override_barge_hold_ms("normal", 90),
        wake_wait_seconds=2.5,
        wake_silence_multiplier=1.0,
    ),
    "fast": InterruptionProfile(
        name="fast",
        min_barge_hold_ms=_override_barge_hold_ms("fast", 20),
        wake_wait_seconds=1.8,
        wake_silence_multiplier=0.85,
    ),
}


def resolve_profile(name: str) -> InterruptionProfile:
    key = (name or "normal").strip().lower()
    return _PROFILES.get(key, _PROFILES["normal"])


def should_trigger_barge(profile_name: str, held_ms: float) -> bool:
    profile = resolve_profile(profile_name)
    return float(held_ms) >= float(profile.min_barge_hold_ms)


def should_trigger_barge_with_profile(profile: InterruptionProfile, held_ms: float) -> bool:
    return float(held_ms) >= float(profile.min_barge_hold_ms)
