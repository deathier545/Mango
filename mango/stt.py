"""Local speech-to-text using faster-whisper."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


def _normalize_peak(
    audio: np.ndarray,
    target_peak: float,
    max_gain: float,
    *,
    log_details: bool = True,
) -> tuple[np.ndarray, dict[str, float]]:
    """Boost quiet mic audio toward `target_peak` (cap absolute samples at 1.0)."""
    peak = float(np.max(np.abs(audio)))
    meta: dict[str, float] = {
        "peak_before": peak,
        "gain": 1.0,
        "peak_after": peak,
    }
    if target_peak <= 0 or peak <= 1e-8:
        logger.debug("Audio normalize skipped (target_peak=%s peak=%s)", target_peak, peak)
        return audio.astype(np.float32, copy=False), meta

    gain = min(target_peak / peak, max_gain)
    boosted = np.clip(audio.astype(np.float32) * gain, -1.0, 1.0)
    meta["gain"] = gain
    meta["peak_after"] = float(np.max(np.abs(boosted)))
    log_fn = logger.info if log_details else logger.debug
    log_fn(
        "Audio normalize peak_before=%.5f gain=%.1fx peak_after=%.4f (target=%.2f max_gain=%.0f)",
        peak,
        gain,
        meta["peak_after"],
        target_peak,
        max_gain,
    )
    return boosted, meta


class WhisperSTT:
    """Lazy-loaded Whisper model (CPU, int8)."""

    def __init__(
        self,
        model_size: str = "base.en",
        *,
        vad_filter: bool = False,
        no_speech_threshold: float = 0.82,
        log_prob_threshold: float = -1.5,
        normalize_target_peak: float = 0.5,
        normalize_max_gain: float = 120.0,
    ) -> None:
        self._model_size = model_size
        self._vad_filter = vad_filter
        self._no_speech_threshold = no_speech_threshold
        self._log_prob_threshold = log_prob_threshold
        self._normalize_target_peak = normalize_target_peak
        self._normalize_max_gain = normalize_max_gain
        self._model: WhisperModel | None = None
        self._lock = threading.Lock()
        logger.info(
            "Whisper STT vad_filter=%s no_speech_threshold=%s log_prob_threshold=%s "
            "normalize_target_peak=%s (disable normalize: set MANGO_AUDIO_NORMALIZE_TARGET_PEAK=0)",
            vad_filter,
            no_speech_threshold,
            log_prob_threshold,
            normalize_target_peak,
        )

    def _ensure_model(self) -> WhisperModel:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    logger.info(
                        "Loading Whisper model %r (first run may download weights)…",
                        self._model_size,
                    )
                    t0 = time.monotonic()
                    self._model = WhisperModel(
                        self._model_size,
                        device="cpu",
                        compute_type="int8",
                    )
                    logger.info(
                        "Whisper model ready in %.1fs", time.monotonic() - t0
                    )
        return self._model

    def warm_model(self) -> None:
        """Load Whisper weights before first utterance (optional background preload)."""
        self._ensure_model()

    def transcribe(
        self,
        audio_mono_float32: np.ndarray,
        sample_rate: int,
        *,
        wake_mode: bool = False,
    ) -> str:
        if audio_mono_float32.size == 0:
            logger.debug("transcribe: empty buffer")
            return ""
        model = self._ensure_model()
        audio = audio_mono_float32.reshape(-1).astype(np.float32)
        audio, _norm_meta = _normalize_peak(
            audio,
            self._normalize_target_peak,
            self._normalize_max_gain,
            log_details=not wake_mode,
        )

        t0 = time.monotonic()
        try:
            ns_thr = float(self._no_speech_threshold)
            lp_thr = float(self._log_prob_threshold)
            if wake_mode:
                # Stricter than PTT: reject ambiguous clips that often hallucinate short phrases.
                ns_thr = min(0.98, max(ns_thr, 0.92))
                # Higher (less negative) log-prob bar → fewer low-confidence garbage segments.
                lp_thr = max(-0.35, lp_thr + 0.85)
            transcribe_kw: dict[str, Any] = {
                "language": "en",
                "vad_filter": self._vad_filter,
                "no_speech_threshold": ns_thr,
                "log_prob_threshold": lp_thr,
            }
            if self._vad_filter:
                transcribe_kw["vad_parameters"] = dict(min_silence_duration_ms=400)
            segments, info = model.transcribe(audio, **transcribe_kw)
            parts = [s.text for s in segments]
            text = " ".join(parts).strip()
        except Exception:
            logger.exception("Whisper transcribe crashed")
            raise

        elapsed = time.monotonic() - t0
        lang = getattr(info, "language", "?")
        prob = getattr(info, "language_probability", None)
        preview = text[:200] + ("…" if len(text) > 200 else "")
        log_fn = logger.debug if wake_mode else logger.info
        log_fn(
            "Transcribe done in %.2fs lang=%s prob=%s chars=%d text=%r",
            elapsed,
            lang,
            f"{prob:.2f}" if isinstance(prob, float) else prob,
            len(text),
            preview,
        )
        return text
