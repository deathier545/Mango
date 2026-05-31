"""Wake utterance capture helpers for streaming wake mode."""

from __future__ import annotations

import logging
import os
import threading
from collections import deque
from collections.abc import Callable
from typing import Any

import numpy as np
import sounddevice as sd

from mango.config import Config
from mango.interruption_policy import resolve_profile
from mango.wake.wake_audio_gates import rms

logger = logging.getLogger(__name__)


def capture_one_wake_utterance(
    *,
    cfg: Config,
    stop_event: threading.Event,
    suppress_event: threading.Event | None,
    hotkey_held: Callable[[], bool],
    mixer_busy: Callable[[], bool],
) -> np.ndarray | None:
    """Energy-gated one utterance (tuned for wake, not full command capture)."""
    from mango.audio import release_mixer_before_mic

    release_mixer_before_mic()

    rate = cfg.sample_rate
    profile = resolve_profile(cfg.interruption_profile)
    block = max(160, int(rate * 0.03))
    block_dur_ms = (block / float(rate)) * 1000.0
    silence_ms = cfg.wake_stream_silence_ms * profile.wake_silence_multiplier
    silence_blocks = max(3, int(silence_ms / max(1e-6, block_dur_ms)))
    min_speech_blocks = max(
        3,
        int(cfg.wake_stream_min_speech_ms / max(1e-6, block_dur_ms)),
    )
    max_blocks = int(cfg.wake_stream_max_seconds * rate / float(block)) + 24

    preroll: deque[np.ndarray] = deque(maxlen=18)
    calib_rms: list[float] = []

    stream_kw: dict[str, Any] = {
        "samplerate": rate,
        "channels": 1,
        "dtype": np.float32,
        "blocksize": block,
    }
    dev_raw = os.getenv("MANGO_SD_INPUT_DEVICE", "").strip()
    if dev_raw.isdigit():
        stream_kw["device"] = int(dev_raw)

    with sd.InputStream(**stream_kw) as stream:
        for _ in range(15):
            if hotkey_held():
                return None
            if stop_event.is_set() or (suppress_event is not None and suppress_event.is_set()):
                return None
            data, _ = stream.read(block)
            mono = np.copy(data)
            calib_rms.append(rms(mono))
            preroll.append(mono)

        calib_rms.sort()
        noise_floor = max(1e-5, float(calib_rms[len(calib_rms) // 2]))
        speech_hi = max(
            cfg.wake_stream_speech_hi_floor,
            noise_floor * cfg.wake_stream_speech_hi_mult,
        )
        speech_lo = max(
            cfg.wake_stream_speech_lo_floor,
            noise_floor * cfg.wake_stream_speech_lo_mult,
        )

        max_wait_blocks = max(
            30,
            int(profile.wake_wait_seconds / max(1e-6, block / float(rate))),
        )
        waited = 0

        while not stop_event.is_set():
            if hotkey_held():
                return None
            if suppress_event is not None and suppress_event.is_set():
                return None
            if mixer_busy():
                return None
            data, _ = stream.read(block)
            mono = np.copy(data)
            preroll.append(mono)
            waited += 1
            if waited >= max_wait_blocks:
                logger.debug(
                    "Wake VAD wait: no speech in ~%.2fs (noise_floor~%.5f gate~%.5f)",
                    waited * (block / float(rate)),
                    noise_floor,
                    speech_hi,
                )
                return None
            if rms(mono) >= speech_hi:
                break
        else:
            return None

        chunks: list[np.ndarray] = list(preroll)[-12:]
        silent_run = 0
        loud_blocks = sum(1 for c in chunks if rms(c) >= speech_lo)
        total_blocks = len(chunks)

        while total_blocks < max_blocks and not stop_event.is_set():
            if hotkey_held():
                return None
            if suppress_event is not None and suppress_event.is_set():
                return None
            if mixer_busy():
                return None
            data, _ = stream.read(block)
            mono = np.copy(data)
            chunks.append(mono)
            total_blocks += 1
            r = rms(mono)
            if r >= speech_lo:
                silent_run = 0
                loud_blocks += 1
            else:
                silent_run += 1
                if silent_run >= silence_blocks and loud_blocks >= min_speech_blocks:
                    break

    audio = np.concatenate(chunks, axis=0) if chunks else None
    if audio is None or audio.size == 0:
        return None
    peak = float(np.max(np.abs(audio)))
    if peak < cfg.wake_whisper_min_peak:
        logger.debug(
            "Wake VAD utterance dropped (peak_abs=%.5f below wake_whisper_min_peak %.5f)",
            peak,
            cfg.wake_whisper_min_peak,
        )
        return None
    dur = audio.shape[0] / float(rate)
    logger.debug(
        "Wake VAD clip: %.2fs samples=%d peak=%.4f noise_floor~%.5f",
        dur,
        audio.shape[0],
        peak,
        noise_floor,
    )
    return audio
