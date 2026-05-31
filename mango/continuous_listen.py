"""Energy-gated continuous mic listen (stream until silence, then emit one clip).

Runs in a daemon thread. Uses ``MIC_LOCK`` like PTT/wake so only one capture path uses the mic at a time.
Not a neural VAD — RMS vs an adaptive noise floor — but works on Windows without extra native deps.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from queue import Full, Queue
from typing import TYPE_CHECKING, Any

import keyboard
import numpy as np
import sounddevice as sd

from mango.metrics import emit_metric

if TYPE_CHECKING:
    from mango.config import Config

logger = logging.getLogger(__name__)


def _rms(block: np.ndarray) -> float:
    if block.size == 0:
        return 0.0
    x = block.astype(np.float64).ravel()
    return float(np.sqrt(np.mean(x * x)))


class ContinuousVoiceListener(threading.Thread):
    """Captures one utterance at a time when speech is detected; pushes float32 mono to ``utterance_queue``."""

    def __init__(
        self,
        *,
        cfg: Config,
        utterance_queue: Queue,
        stop_event: threading.Event,
        suppress_event: threading.Event | None = None,
    ) -> None:
        super().__init__(daemon=True, name="MangoVAD")
        self._cfg = cfg
        self._queue = utterance_queue
        # Not named ``_stop`` — that shadows ``threading.Thread._stop`` and breaks ``join()``.
        self._stop_evt = stop_event
        self._suppress = suppress_event
        self._last_noise_hint_s = 0.0

    def _mixer_busy(self) -> bool:
        try:
            import pygame

            return bool(pygame.mixer.get_init() and pygame.mixer.get_busy())
        except Exception:
            return False

    def _hotkey_held(self) -> bool:
        """Yield mic to push-to-talk when the user is holding the PTT combo."""
        try:
            return bool(keyboard.is_pressed(self._cfg.hotkey))
        except Exception:
            return False

    def _capture_one_utterance(self) -> np.ndarray | None:
        from mango.audio import release_mixer_before_mic

        # Let Bluetooth/USB headsets leave A2DP-only playback so the default capture device works.
        release_mixer_before_mic()

        rate = self._cfg.sample_rate
        block = max(160, int(rate * 0.03))
        block_dur_ms = (block / float(rate)) * 1000.0
        silence_ms = self._cfg.vad_silence_ms
        silence_blocks = max(3, int(silence_ms / max(1e-6, block_dur_ms)))
        min_speech_blocks = max(4, int(self._cfg.vad_min_speech_ms / max(1e-6, block_dur_ms)))
        max_blocks = int(self._cfg.vad_max_seconds * rate / float(block)) + 24

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
            # Ambient calibration (~0.45s)
            for _ in range(15):
                if self._hotkey_held():
                    return None
                if self._stop_evt.is_set() or (
                    self._suppress is not None and self._suppress.is_set()
                ):
                    return None
                data, _ = stream.read(block)
                mono = np.copy(data)
                calib_rms.append(_rms(mono))
                preroll.append(mono)

            calib_rms.sort()
            noise_floor = max(1e-5, float(calib_rms[len(calib_rms) // 2]))
            # Quiet headsets / BT mics sit close to the noise floor; keep gates reachable.
            speech_hi = max(0.009, noise_floor * 2.75)
            speech_lo = max(0.006, noise_floor * 1.65)
            now = time.monotonic()
            if noise_floor >= 0.02 and (now - self._last_noise_hint_s) > 90.0:
                self._last_noise_hint_s = now
                logger.info(
                    "High ambient mic noise detected (noise_floor=%.5f). "
                    "For better reliability, use push-to-talk or set interrupt profile to strict.",
                    noise_floor,
                )
                emit_metric(
                    "noise_guidance",
                    source="vad",
                    noise_floor=round(noise_floor, 5),
                    recommendation="ptt_or_strict_interrupt",
                )

            # Do not hold the mic forever while waiting for speech — PTT / wake need MIC_LOCK too.
            max_wait_blocks = max(
                40,
                int(self._cfg.vad_max_wait_seconds / max(1e-6, block / float(rate))),
            )
            waited = 0

            # Wait for speech onset
            while not self._stop_evt.is_set():
                if self._hotkey_held():
                    logger.debug("VAD wait: hotkey held - releasing mic for PTT.")
                    return None
                if self._suppress is not None and self._suppress.is_set():
                    return None
                if self._mixer_busy():
                    return None
                data, _ = stream.read(block)
                mono = np.copy(data)
                preroll.append(mono)
                waited += 1
                if waited >= max_wait_blocks:
                    logger.debug(
                        "VAD wait: no speech in ~%.2fs (noise_floor~%.5f gate~%.5f) - yielding mic.",
                        waited * (block / float(rate)),
                        noise_floor,
                        speech_hi,
                    )
                    return None
                if _rms(mono) >= speech_hi:
                    break
            else:
                return None

            # Trigger block is already the last item in preroll
            chunks: list[np.ndarray] = list(preroll)[-12:]
            silent_run = 0
            loud_blocks = sum(1 for c in chunks if _rms(c) >= speech_lo)
            total_blocks = len(chunks)

            while total_blocks < max_blocks and not self._stop_evt.is_set():
                if self._hotkey_held():
                    logger.debug("VAD record: hotkey held - discarding partial clip for PTT.")
                    return None
                if self._suppress is not None and self._suppress.is_set():
                    return None
                if self._mixer_busy():
                    return None
                data, _ = stream.read(block)
                mono = np.copy(data)
                chunks.append(mono)
                total_blocks += 1
                r = _rms(mono)
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
        if peak < self._cfg.vad_min_peak:
            logger.debug(
                "VAD utterance dropped (peak_abs=%.5f below vad_min_peak %.5f)",
                peak,
                self._cfg.vad_min_peak,
            )
            return None
        dur = audio.shape[0] / float(rate)
        logger.info(
            "VAD captured utterance: %.2fs samples=%d peak=%.4f noise_floor~%.5f",
            dur,
            audio.shape[0],
            peak,
            noise_floor,
        )
        return audio

    def run(self) -> None:
        from mango.mic_lock import MIC_LOCK

        logger.info(
            "Always-listen (energy VAD) on - silence~%.0fms min_speech~%.0fms max~%.0fs max_wait~%.1fs idle_sleep~%.3fs; "
            "hold %s for manual capture too.",
            self._cfg.vad_silence_ms,
            self._cfg.vad_min_speech_ms,
            self._cfg.vad_max_seconds,
            self._cfg.vad_max_wait_seconds,
            self._cfg.vad_thread_idle_sleep_seconds,
            self._cfg.hotkey,
        )
        while not self._stop_evt.is_set():
            if self._suppress is not None and self._suppress.is_set():
                time.sleep(0.1)
                continue
            if self._mixer_busy():
                time.sleep(0.08)
                continue
            if not MIC_LOCK.acquire(timeout=0.4):
                continue
            audio: np.ndarray | None = None
            try:
                if self._stop_evt.is_set():
                    break
                if self._suppress is not None and self._suppress.is_set():
                    continue
                if self._mixer_busy():
                    continue
                audio = self._capture_one_utterance()
            except sd.PortAudioError as exc:
                logger.warning("VAD mic PortAudio error: %s - retrying.", exc)
                time.sleep(0.35)
            except Exception:
                logger.debug("VAD capture failed", exc_info=True)
            finally:
                MIC_LOCK.release()

            if audio is None or audio.size == 0:
                idle = float(self._cfg.vad_thread_idle_sleep_seconds)
                if idle > 0:
                    time.sleep(idle)
                continue
            try:
                self._queue.put_nowait(audio)
            except Full:
                logger.warning("VAD utterance queue full; dropping clip.")
            idle = float(self._cfg.vad_thread_idle_sleep_seconds)
            if idle > 0:
                time.sleep(min(idle, 0.5))
