"""Wake audio gating helpers shared by wake pipelines."""

from __future__ import annotations

import logging

import numpy as np

_logger = logging.getLogger(__name__)


def rms(mono: np.ndarray) -> float:
    """Root-mean-square energy for mono float audio."""
    if mono.size == 0:
        return 0.0
    x = mono.astype(np.float64).ravel()
    return float(np.sqrt(np.mean(x * x)))


def wake_audio_gates_pass(
    mono: np.ndarray,
    *,
    rms_threshold: float,
    whisper_min_peak: float,
    whisper_min_std: float,
    logger: logging.Logger | None = None,
    label: str = "Wake sample",
) -> bool:
    """Return True when audio passes RMS, peak, and std-dev wake gates."""
    log = logger or _logger

    if rms_threshold > 0:
        clip_rms = rms(mono)
        if clip_rms < rms_threshold:
            log.debug(
                "%s skipped (rms=%.5f below gate %.5f)",
                label,
                clip_rms,
                rms_threshold,
            )
            return False

    clip_peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    if clip_peak < whisper_min_peak:
        log.debug(
            "%s skipped (peak_abs=%.5f below whisper_min_peak %.5f)",
            label,
            clip_peak,
            whisper_min_peak,
        )
        return False

    clip_std = float(np.std(mono.astype(np.float64))) if mono.size > 1 else 0.0
    if clip_std < whisper_min_std:
        log.debug(
            "%s skipped (std=%.5f below whisper_min_std %.5f)",
            label,
            clip_std,
            whisper_min_std,
        )
        return False

    return True
