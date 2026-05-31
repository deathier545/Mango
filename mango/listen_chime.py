"""Short earcon before opening the mic (listen cue, Windows-safe).

Uses ``sounddevice`` output only — no MLX, no pygame mixer (call after ``release_mixer_before_mic``).
"""

from __future__ import annotations

import logging
import math

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


def _output_sample_rate() -> int:
    try:
        d = sd.query_devices(kind="output")
        raw = d.get("default_samplerate")
        if raw:
            return max(8000, min(int(float(raw)), 192_000))
    except Exception:
        logger.debug("listen_chime: could not query output sample rate", exc_info=True)
    return 44_100


def play_listen_chime(
    *,
    frequency_hz: float = 880.0,
    duration_s: float = 0.11,
    volume: float = 0.16,
    second_tone_hz: float | None = 660.0,
    second_duration_s: float = 0.08,
) -> None:
    """Two short tones before capture. Safe no-op on failure."""
    try:
        sr = _output_sample_rate()
        frequency_hz = max(200.0, min(float(frequency_hz), 4000.0))
        duration_s = max(0.04, min(float(duration_s), 0.35))
        volume = max(0.02, min(float(volume), 0.45))

        def _tone(hz: float, dur: float) -> np.ndarray:
            n = max(1, int(sr * dur))
            t = np.arange(n, dtype=np.float64) / sr
            x = np.sin(2.0 * math.pi * hz * t)
            # Hann fade in/out
            w = np.hanning(n).astype(np.float64)
            return (x * w * volume).astype(np.float32)

        parts: list[np.ndarray] = [_tone(frequency_hz, duration_s)]
        if second_tone_hz and second_tone_hz > 0:
            parts.append(
                _tone(
                    max(200.0, min(float(second_tone_hz), 4000.0)),
                    max(0.03, min(float(second_duration_s), 0.25)),
                ),
            )
        y = np.concatenate(parts)
        sd.play(y, sr, blocking=True)
    except Exception:
        logger.debug("listen_chime skipped", exc_info=True)
