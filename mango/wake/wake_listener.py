"""Background wake phrase detection: energy VAD + Whisper (optional tiny model), or polled short clips."""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import keyboard
import numpy as np
import sounddevice as sd

from mango.metrics import emit_metric
from mango.wake.wake_audio_gates import wake_audio_gates_pass
from mango.wake.wake_capture import capture_one_wake_utterance
from mango.wake.wake_phrase import phrase_accepted as _phrase_text_accepted

if TYPE_CHECKING:
    from mango.config import Config
    from mango.stt import WhisperSTT

logger = logging.getLogger(__name__)


def compile_wake_phrase_regex(phrase_csv: str) -> re.Pattern[str]:
    """Compatibility shim; implementation lives in ``mango.wake.wake_phrase``."""
    from mango.wake.wake_phrase import compile_wake_phrase_regex as _compile

    return _compile(phrase_csv)


class WakeWordListener(threading.Thread):
    """Hands-free wake: openWakeWord (optional Whisper confirm), streaming VAD + Whisper, or polled clips."""

    def __init__(
        self,
        *,
        stt: WhisperSTT,
        cfg: Config,
        wake_event: threading.Event,
        stop_event: threading.Event,
        suppress_event: threading.Event | None = None,
        mic_busy: Callable[[], bool] | None = None,
        stt_wake: WhisperSTT | None = None,
    ) -> None:
        super().__init__(daemon=True, name="MangoWake")
        self._stt = stt
        self._stt_wake = stt_wake
        self._cfg = cfg
        self._wake_event = wake_event
        # Not ``_stop`` — shadows ``threading.Thread._stop`` and breaks ``join()``.
        self._stop_evt = stop_event
        self._suppress = suppress_event
        from mango.mic_lock import mic_is_busy

        self._mic_busy = mic_busy or mic_is_busy
        self._phrase_re = compile_wake_phrase_regex(cfg.wake_phrase or "mango")

    def _mixer_busy(self) -> bool:
        try:
            import pygame

            return bool(pygame.mixer.get_init() and pygame.mixer.get_busy())
        except Exception:
            return False

    def _hotkey_held(self) -> bool:
        try:
            return bool(keyboard.is_pressed(self._cfg.hotkey))
        except Exception:
            return False

    def _transcribe_wake(self, mono: np.ndarray, rate: int) -> str:
        engine = self._stt_wake or self._stt
        return engine.transcribe(mono, rate, wake_mode=True)

    def _gates_pass(self, mono: np.ndarray) -> bool:
        return wake_audio_gates_pass(
            mono,
            rms_threshold=self._cfg.wake_rms_threshold,
            whisper_min_peak=self._cfg.wake_whisper_min_peak,
            whisper_min_std=self._cfg.wake_whisper_min_std,
            logger=logger,
            label="Wake sample",
        )

    def _phrase_accepted(self, text: str, *, log_match: bool = True) -> bool:
        return _phrase_text_accepted(
            text,
            phrase_re=self._phrase_re,
            max_offset=self._cfg.wake_phrase_max_char_offset,
            suppress_active=self._suppress is not None and self._suppress.is_set(),
            log_match=log_match,
            logger=logger,
        )

    def _run_openwakeword(self) -> None:
        import mango.wake.oww_wake as oww_wake
        from mango.audio import release_mixer_before_mic
        from mango.mic_lock import MIC_LOCK

        if not oww_wake.oww_import_ok():
            logger.error("openWakeWord not available; falling back to Whisper wake.")
            if self._cfg.wake_streaming:
                self._run_streaming()
            else:
                self._run_polled()
            return

        names = list(self._cfg.oww_model_names)
        try:
            oww_wake.ensure_oww_models_downloaded(names)
            model = oww_wake.build_oww_model(
                names,
                inference_framework=self._cfg.oww_inference_framework,
                vad_threshold=self._cfg.oww_vad_threshold,
            )
        except Exception:
            logger.exception("openWakeWord setup failed; falling back to Whisper wake.")
            if self._cfg.wake_streaming:
                self._run_streaming()
            else:
                self._run_polled()
            return

        thr = self._cfg.oww_threshold
        hybrid = self._cfg.wake_oww_whisper_confirm
        whisper_sr = self._cfg.sample_rate
        logger.info(
            "Wake listener on — openWakeWord models=%r threshold=%.2f vad=%.2f fw=%s%s",
            names,
            thr,
            self._cfg.oww_vad_threshold,
            self._cfg.oww_inference_framework,
            " + Whisper phrase confirm" if hybrid else "",
        )

        burst_max = 380
        dev_raw = os.getenv("MANGO_SD_INPUT_DEVICE", "").strip()
        dev_kw: dict[str, Any] = {}
        if dev_raw.isdigit():
            dev_kw["device"] = int(dev_raw)

        while not self._stop_evt.is_set():
            if self._suppress is not None and self._suppress.is_set():
                time.sleep(0.1)
                continue
            if self._mixer_busy():
                time.sleep(0.08)
                continue
            if self._mic_busy():
                time.sleep(0.1)
                continue
            if not MIC_LOCK.acquire(timeout=0.4):
                continue
            ring: deque[np.ndarray] = deque(maxlen=oww_wake.OWW_HYBRID_RING_MAXLEN)
            stream = None
            stream_sr = 16000
            block = oww_wake.OWW_CHUNK
            for sr_try, blk in (
                (16000, oww_wake.OWW_CHUNK),
                (self._cfg.sample_rate, max(160, int(self._cfg.sample_rate * 0.08))),
            ):
                skw: dict[str, Any] = {
                    "samplerate": sr_try,
                    "channels": 1,
                    "dtype": np.float32,
                    "blocksize": blk,
                    **dev_kw,
                }
                try:
                    stream = sd.InputStream(**skw)
                    stream_sr = sr_try
                    block = blk
                    break
                except sd.PortAudioError:
                    stream = None
                    continue
            if stream is None:
                logger.warning("Wake mic could not open for openWakeWord; retrying.")
                MIC_LOCK.release()
                time.sleep(0.35)
                continue

            chunk_buf = oww_wake.OwwPcm16Buffer(stream_sr)
            try:
                if self._stop_evt.is_set():
                    break
                if self._suppress is not None and self._suppress.is_set():
                    continue
                release_mixer_before_mic()
                with stream:
                    fired = False
                    for _ in range(burst_max):
                        if self._stop_evt.is_set():
                            break
                        if self._suppress is not None and self._suppress.is_set():
                            break
                        if self._hotkey_held():
                            break
                        if self._mixer_busy():
                            break
                        data, _ = stream.read(block)
                        mono = np.copy(
                            data[:, 0] if getattr(data, "ndim", 1) > 1 else data
                        )
                        for pcm in chunk_buf.feed_float_mono(mono):
                            ring.append(pcm)
                            preds = model.predict(pcm)
                            score = oww_wake.max_scalar_prediction(preds)
                            if score < thr:
                                continue
                            if hybrid:
                                logger.info(
                                    "Wake OWW fired (hybrid) score=%.3f — Whisper phrase check",
                                    score,
                                )
                                parts = list(ring)
                                tail_i16 = (
                                    np.concatenate(parts) if parts else pcm
                                )
                                cap = int(
                                    oww_wake.OWW_HYBRID_WHISPER_TAIL_SEC * oww_wake.OWW_SR
                                )
                                if tail_i16.size > cap:
                                    tail_i16 = tail_i16[-cap:]
                                wf = oww_wake.int16_16k_to_float32_for_whisper(
                                    tail_i16, whisper_sr
                                )
                                if not self._gates_pass(wf):
                                    logger.info(
                                        "Wake OWW hybrid rejected: audio too quiet/flat "
                                        "for Whisper (score=%.3f)",
                                        score,
                                    )
                                    emit_metric(
                                        "wake_reject",
                                        engine="openwakeword_hybrid",
                                        reason="audio_gate",
                                        score=round(float(score), 4),
                                    )
                                    model.reset()
                                    chunk_buf.clear()
                                    ring.clear()
                                    continue
                                try:
                                    text = self._transcribe_wake(wf, whisper_sr)
                                except Exception:
                                    logger.debug(
                                        "Wake OWW hybrid transcribe failed",
                                        exc_info=True,
                                    )
                                    model.reset()
                                    chunk_buf.clear()
                                    ring.clear()
                                    continue
                                if not self._phrase_accepted(text, log_match=False):
                                    logger.info(
                                        "Wake OWW hybrid rejected: phrase mismatch "
                                        "(score=%.3f transcript=%r)",
                                        score,
                                        text[:200],
                                    )
                                    emit_metric(
                                        "wake_reject",
                                        engine="openwakeword_hybrid",
                                        reason="phrase_mismatch",
                                        score=round(float(score), 4),
                                    )
                                    model.reset()
                                    chunk_buf.clear()
                                    ring.clear()
                                    continue
                                logger.info(
                                    "Wake OWW hybrid confirmed (Whisper matched phrase; "
                                    "OWW score=%.3f) from: %r",
                                    score,
                                    text[:120],
                                )
                            else:
                                logger.info(
                                    "Wake openWakeWord hit score=%.3f (models=%s)",
                                    score,
                                    names,
                                )
                            self._wake_event.set()
                            emit_metric(
                                "wake_trigger",
                                engine="openwakeword_hybrid" if hybrid else "openwakeword",
                                score=round(float(score), 4),
                            )
                            model.reset()
                            chunk_buf.clear()
                            ring.clear()
                            # Debounce: real mics can echo/refire; 1.0s was tight on some setups.
                            time.sleep(1.25)
                            fired = True
                            break
                        if fired:
                            break
                    model.reset()
                    chunk_buf.clear()
                    ring.clear()
            except sd.PortAudioError as exc:
                logger.warning("Wake openWakeWord mic error: %s", exc)
                time.sleep(0.35)
            except Exception:
                logger.debug("Wake openWakeWord loop error", exc_info=True)
            finally:
                MIC_LOCK.release()
            time.sleep(0.02)

    def _capture_one_wake_utterance(self) -> np.ndarray | None:
        return capture_one_wake_utterance(
            cfg=self._cfg,
            stop_event=self._stop_evt,
            suppress_event=self._suppress,
            hotkey_held=self._hotkey_held,
            mixer_busy=self._mixer_busy,
        )

    def _run_streaming(self) -> None:
        from mango.mic_lock import MIC_LOCK

        rate = self._cfg.sample_rate
        wmodel = (
            (self._cfg.wake_whisper_model or "").strip()
            or "(same as main STT)"
        )
        logger.info(
            "Wake listener on — streaming+VAD (phrase=%r silence_ms=%.0f max_s=%.2f min_speech_ms=%.0f "
            "rms_gate=%s whisper_min_peak=%.4f whisper_min_std=%.4f wake_whisper=%s)",
            self._cfg.wake_phrase or "mango",
            self._cfg.wake_stream_silence_ms,
            self._cfg.wake_stream_max_seconds,
            self._cfg.wake_stream_min_speech_ms,
            f"{self._cfg.wake_rms_threshold:.4f}"
            if self._cfg.wake_rms_threshold > 0
            else "off",
            self._cfg.wake_whisper_min_peak,
            self._cfg.wake_whisper_min_std,
            wmodel,
        )
        while not self._stop_evt.is_set():
            if self._suppress is not None and self._suppress.is_set():
                time.sleep(0.1)
                continue
            if self._mixer_busy():
                time.sleep(0.08)
                continue
            if self._mic_busy():
                time.sleep(0.1)
                continue
            if not MIC_LOCK.acquire(timeout=0.4):
                continue
            mono: np.ndarray | None = None
            try:
                if self._stop_evt.is_set():
                    break
                if self._suppress is not None and self._suppress.is_set():
                    continue
                if self._mixer_busy():
                    continue
                mono = self._capture_one_wake_utterance()
            except sd.PortAudioError as exc:
                logger.warning("Wake mic PortAudio error: %s - retrying.", exc)
                time.sleep(0.35)
            except Exception:
                logger.debug("Wake streaming capture failed", exc_info=True)
            finally:
                MIC_LOCK.release()

            if mono is None or mono.size == 0:
                time.sleep(0.02)
                continue
            if not self._gates_pass(mono):
                time.sleep(0.08)
                continue
            try:
                text = self._transcribe_wake(mono, rate)
            except Exception:
                logger.debug("Wake transcribe failed", exc_info=True)
                time.sleep(0.05)
                continue
            if not self._phrase_accepted(text):
                emit_metric("wake_reject", engine="whisper_streaming", reason="phrase_mismatch")
                time.sleep(0.28)
                continue
            self._wake_event.set()
            emit_metric("wake_trigger", engine="whisper_streaming")
            time.sleep(1.0)

    def _run_polled(self) -> None:
        from mango.mic_lock import MIC_LOCK

        rate = self._cfg.sample_rate
        clip_s = max(0.6, min(self._cfg.wake_clip_seconds, 3.0))
        interval = max(1.0, self._cfg.wake_interval_seconds)
        thr = self._cfg.wake_rms_threshold
        logger.info(
            "Wake listener on (polled clips — phrase=%r interval=%.1fs clip=%.2fs rms_gate=%s "
            "whisper_min_peak=%.4f whisper_min_std=%.4f)",
            self._cfg.wake_phrase or "mango",
            interval,
            clip_s,
            f"{thr:.4f}" if thr > 0 else "off",
            self._cfg.wake_whisper_min_peak,
            self._cfg.wake_whisper_min_std,
        )
        first = True
        while not self._stop_evt.is_set():
            if not first and self._stop_evt.wait(interval):
                break
            first = False
            if self._suppress is not None and self._suppress.is_set():
                continue
            try:
                if self._mixer_busy():
                    continue
            except Exception:
                pass
            if self._mic_busy():
                continue
            if not MIC_LOCK.acquire(blocking=False):
                continue
            try:
                if self._suppress is not None and self._suppress.is_set():
                    continue
                try:
                    if self._mixer_busy():
                        continue
                except Exception:
                    pass
                frames = int(clip_s * rate)
                audio = sd.rec(
                    frames,
                    samplerate=rate,
                    channels=1,
                    dtype=np.float32,
                )
                sd.wait()
                mono = np.copy(audio)
            except Exception:
                logger.debug("Wake sample failed", exc_info=True)
                continue
            finally:
                MIC_LOCK.release()

            if not self._gates_pass(mono):
                continue
            try:
                text = self._transcribe_wake(mono, rate)
            except Exception:
                logger.debug("Wake transcribe failed", exc_info=True)
                continue
            if not self._phrase_accepted(text):
                emit_metric("wake_reject", engine="whisper_polled", reason="phrase_mismatch")
                continue
            self._wake_event.set()
            emit_metric("wake_trigger", engine="whisper_polled")

    def run(self) -> None:
        if self._cfg.wake_use_openwakeword:
            self._run_openwakeword()
        elif self._cfg.wake_streaming:
            self._run_streaming()
        else:
            self._run_polled()
