"""Microphone capture (push-to-hold) and audio playback."""

from __future__ import annotations

import logging
import math
import os
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import keyboard
import numpy as np
import pygame
import sounddevice as sd

import mango.desktop.desktop_ipc as desktop_ipc
from mango.mic_lock import MIC_LOCK

logger = logging.getLogger(__name__)

# Serialize TTS synthesis + playback so nothing runs in parallel with pygame audio.
_PLAYBACK_LOCK = threading.Lock()

# Single pygame channel index reserved for voice (see init_voice_mixer num_channels=1).
_VOICE_CHANNEL_INDEX = 0

_MIC_RETRY_PAUSE_S = 0.35
_MIC_OPEN_ATTEMPTS = 3


def _pump_pygame_events() -> None:
    """Keep SDL audio responsive on Windows; safe if display module was never initialized."""
    try:
        pygame.event.pump()
    except Exception:
        pass


def init_voice_mixer() -> None:
    """Configure pygame/SDL for MP3 voice playback (call once at startup).

    Mono output + a single mixer channel avoids stacked playback (multiple pygame channels)
    and reduces Bluetooth \"double voice\" when stereo duplicates leak to HF vs A2DP paths.
    """
    if pygame.mixer.get_init():
        pygame.mixer.quit()
    # Mono device: stereo MP3s are mixed down by pygame.
    pygame.mixer.pre_init(44100, -16, 1, 4096)
    # Larger buffer reduces underruns/glitches on Bluetooth or busy CPUs during TTS decode.
    pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=4096)
    pygame.mixer.set_num_channels(1)
    drv = (os.environ.get("SDL_AUDIODRIVER") or "").strip().lower()
    logger.info(
        "Voice playback ready: 44100 Hz mono, 1 mixer channel; SDL_AUDIODRIVER=%r "
        "(try MANGO_SDL_AUDIODRIVER=wasapi if you hear nothing)",
        drv or "(unset)",
    )
    if drv == "wasapi":
        logger.info(
            "Screen/desktop recording: if capture misses Mango or errors with WASAPI exclusive, "
            "run this session with MANGO_SDL_AUDIODRIVER=directsound, or use your recorder's "
            "shared / desktop-audio (non-exclusive) source. In Windows: Sound → device → Advanced → "
            "uncheck 'Allow applications to take exclusive control' if needed.",
        )


def release_mixer_before_mic() -> None:
    """Free SDL/pygame audio so Bluetooth/USB headsets can switch back to capture profile."""
    try:
        pygame.mixer.stop()
    except Exception:
        logger.debug("release_mixer_before_mic: stop noop", exc_info=True)
    pause_s = 0.04
    try:
        raw = os.getenv("MANGO_MIXER_RELEASE_PAUSE_S", "").strip()
        if raw:
            pause_s = max(0.0, min(float(raw), 0.25))
    except Exception:
        logger.debug("Invalid MANGO_MIXER_RELEASE_PAUSE_S; using default", exc_info=True)
    if pause_s > 0.0:
        time.sleep(pause_s)


def _mono_block_rms(block: np.ndarray) -> float:
    if block.size == 0:
        return 0.0
    x = block.astype(np.float64).ravel()
    return float(np.sqrt(np.mean(x * x)))


def record_while_held(
    key: str,
    sample_rate: int,
    *,
    wait_for_key: bool = True,
) -> np.ndarray:
    """Record mono float32 audio while `key` stays pressed.

    Waits for the hotkey *before* opening the mic so the wake listener can use the
    microphone while Mango is idle (tradeoff: a very fast tap may open the stream
    after the key is already released).

    Set ``wait_for_key=False`` when the hotkey is **already** down (e.g. always-listen
    mode polling in the main loop) — returns empty audio if the key is not pressed.
    """
    block = int(sample_rate * 0.05)
    logger.debug(
        "record_while_held: sample_rate=%s block=%s key=%r wait_for_key=%s",
        sample_rate,
        block,
        key,
        wait_for_key,
    )
    if wait_for_key:
        logger.debug(
            "Waiting for key %r — if this hangs, keyboard hooks may be blocked (try Admin).",
            key,
        )
        keyboard.wait(key)
    else:
        if not keyboard.is_pressed(key):
            return np.zeros((0, 1), dtype=np.float32)
    logger.debug("Key down detected; opening mic until release…")

    last_exc: BaseException | None = None
    with MIC_LOCK:
        for attempt in range(1, _MIC_OPEN_ATTEMPTS + 1):
            chunks: list[np.ndarray] = []
            try:
                with sd.InputStream(
                    samplerate=sample_rate,
                    channels=1,
                    dtype=np.float32,
                    blocksize=block,
                ) as stream:
                    overflows = 0
                    while keyboard.is_pressed(key):
                        data, overflowed = stream.read(block)
                        if overflowed:
                            overflows += 1
                        chunks.append(np.copy(data))
                    if overflows:
                        logger.warning(
                            "sounddevice reported overflow %d time(s); audio may be clipped.",
                            overflows,
                        )
                break
            except sd.PortAudioError as exc:
                last_exc = exc
                logger.warning(
                    "Mic PortAudio error (%s/%s): %s — retrying after headset/driver glitch.",
                    attempt,
                    _MIC_OPEN_ATTEMPTS,
                    exc,
                )
                time.sleep(_MIC_RETRY_PAUSE_S)
            except OSError:
                logger.exception(
                    "Microphone open/read failed (wrong device, permissions, or PortAudio issue)."
                )
                raise
            except Exception:
                logger.exception("Unexpected failure during record_while_held.")
                raise
        else:
            logger.exception("Microphone failed after %s attempts", _MIC_OPEN_ATTEMPTS)
            assert last_exc is not None
            raise last_exc

    if not chunks:
        logger.debug("record_while_held: zero chunks (instant release?)")
        return np.zeros((0, 1), dtype=np.float32)
    audio = np.concatenate(chunks, axis=0)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    duration_s = audio.shape[0] / float(sample_rate)
    logger.info(
        "Recorded %.2fs of audio (~%d samples), peak_abs=%.4f",
        duration_s,
        audio.shape[0],
        peak,
    )
    if peak < 1e-4:
        logger.warning(
            "Recording is extremely quiet — check default mic in Windows / closer to mic."
        )
    elif peak < 0.02:
        logger.warning(
            "Recording is very quiet (peak_abs=%.4f). Boost mic input in Windows Sound settings "
            "or move closer — Whisper may mis-hear or return empty.",
            peak,
        )
    return audio


def record_fixed_seconds(sample_rate: int, duration_s: float) -> np.ndarray:
    """One-shot mono recording (hands-free turn after wake phrase)."""
    duration_s = max(0.3, min(duration_s, 30.0))
    frames = int(sample_rate * duration_s)
    with MIC_LOCK:
        audio = sd.rec(
            frames,
            samplerate=sample_rate,
            channels=1,
            dtype=np.float32,
        )
        sd.wait()
        mono = np.copy(audio)
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    logger.info(
        "record_fixed_seconds: %.2fs peak_abs=%.4f",
        duration_s,
        peak,
    )
    return mono


def record_hands_free(
    sample_rate: int,
    max_seconds: float,
    *,
    silence_ms: int = 1000,
    silence_rms: float = 0.018,
) -> np.ndarray:
    """Hands-free capture after wake: record up to ``max_seconds``, stop early after post-speech silence."""
    max_seconds = max(0.5, min(max_seconds, 45.0))
    block = max(1, int(sample_rate * 0.05))
    block_dur = block / float(sample_rate)
    silence_ms = max(400, min(int(silence_ms), 5000))
    silence_rms = max(0.003, min(float(silence_rms), 0.2))
    silence_blocks = max(1, int((silence_ms / 1000.0) / block_dur))
    max_blocks = max(1, int(max_seconds / block_dur))

    last_exc: BaseException | None = None
    with MIC_LOCK:
        for attempt in range(1, _MIC_OPEN_ATTEMPTS + 1):
            chunks: list[np.ndarray] = []
            stopped_on_silence = False
            try:
                with sd.InputStream(
                    samplerate=sample_rate,
                    channels=1,
                    dtype=np.float32,
                    blocksize=block,
                ) as stream:
                    seen_voice = False
                    silent_run = 0
                    for _ in range(max_blocks):
                        data, overflowed = stream.read(block)
                        if overflowed:
                            logger.debug("record_hands_free: overflow chunk")
                        chunks.append(np.copy(data))
                        rms = _mono_block_rms(data)
                        if rms >= silence_rms:
                            seen_voice = True
                            silent_run = 0
                        elif seen_voice:
                            silent_run += 1
                            if silent_run >= silence_blocks:
                                stopped_on_silence = True
                                break
                break
            except sd.PortAudioError as exc:
                last_exc = exc
                logger.warning(
                    "Mic PortAudio error (%s/%s): %s — retrying after headset/driver glitch.",
                    attempt,
                    _MIC_OPEN_ATTEMPTS,
                    exc,
                )
                time.sleep(_MIC_RETRY_PAUSE_S)
            except OSError:
                logger.exception(
                    "Microphone open/read failed (wrong device, permissions, or PortAudio issue)."
                )
                raise
            except Exception:
                logger.exception("Unexpected failure during record_hands_free.")
                raise
        else:
            logger.exception("Microphone failed after %s attempts", _MIC_OPEN_ATTEMPTS)
            assert last_exc is not None
            raise last_exc

    if not chunks:
        return np.zeros((0, 1), dtype=np.float32)
    mono = np.concatenate(chunks, axis=0)
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    duration_s = mono.shape[0] / float(sample_rate)
    logger.info(
        "record_hands_free: %.2fs (max %.2fs) peak_abs=%.4f stopped_on_silence=%s",
        duration_s,
        max_seconds,
        peak,
        stopped_on_silence,
    )
    return mono


def _sound_samples_numpy(sound: pygame.mixer.Sound) -> np.ndarray | None:
    """Copy ``Sound`` PCM into a 1-D float64 array (roughly -1..1), or None."""
    import pygame.sndarray as sndarray

    # pygame 2.x: sndarray.array(Sound). Older docs/examples used array_sound.
    arr: np.ndarray | None = None
    if hasattr(sndarray, "array"):
        arr = np.asarray(sndarray.array(sound))
    elif hasattr(sndarray, "array_sound"):
        arr = np.asarray(sndarray.array_sound(sound))
    if arr is not None and arr.size:
        if arr.ndim == 2:
            arr = np.mean(arr, axis=1)
        xf = arr.astype(np.float64)
        peak = float(np.max(np.abs(xf)))
        if peak > 1.5 or np.issubdtype(arr.dtype, np.integer):
            xf = xf / 32768.0
        return xf

    raw = getattr(sound, "get_raw", lambda: b"")()
    if not raw or len(raw) < 2:
        return None
    init = pygame.mixer.get_init()
    # size -16 → signed 16-bit sample frames
    fmt = init[1] if init else -16
    if fmt == -16:
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
        ch = init[2] if init else 1
        if ch > 1:
            x = x.reshape(-1, ch).mean(axis=1)
        return x
    return None


def _mono_samples_from_sound(sound: pygame.mixer.Sound) -> tuple[np.ndarray | None, int, float]:
    """Decode ``Sound`` buffer to mono float32 ~[-1,1]; returns (samples, sample_rate, duration_ms)."""
    try:
        arr = _sound_samples_numpy(sound)
        if arr is None or arr.size == 0:
            return None, 44100, 0.0
        init = pygame.mixer.get_init()
        sr = int(init[0]) if init else 44100
        dur_ms = (len(arr) / float(sr)) * 1000.0
        return arr.astype(np.float32), sr, dur_ms
    except Exception:
        logger.debug("sndarray sample extract for HUD failed", exc_info=True)
        return None, 44100, 0.0


def _tts_rms_envelope(
    samples: np.ndarray,
    sample_rate: int,
    *,
    hop_ms: float = 22.0,
) -> tuple[np.ndarray, np.ndarray]:
    """RMS per hop, peak-normalized to ~[0,1]; returns (time_ms_centers, levels)."""
    if samples.size == 0:
        return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.float64)
    hop = max(1, int(sample_rate * hop_ms / 1000.0))
    rms_list: list[float] = []
    for start in range(0, len(samples), hop):
        chunk = samples[start : start + hop]
        if chunk.size == 0:
            break
        xf = chunk.astype(np.float64)
        rms_list.append(float(np.sqrt(np.mean(xf * xf))))
    if not rms_list:
        return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.float64)
    levels = np.clip(np.array(rms_list, dtype=np.float64) / max(rms_list), 0.0, 1.0) ** 0.62
    centers = (np.arange(len(rms_list), dtype=np.float64) + 0.5) * (hop / sample_rate * 1000.0)
    return centers, levels


def _interp_envelope(times_ms: np.ndarray, levels: np.ndarray, pos_ms: float) -> float:
    if times_ms.size == 0 or levels.size == 0:
        return 0.0
    pos_ms = max(0.0, float(pos_ms))
    if pos_ms <= float(times_ms[0]):
        return float(levels[0])
    if pos_ms >= float(times_ms[-1]):
        return float(levels[-1])
    idx = int(np.searchsorted(times_ms, pos_ms, side="right"))
    idx = max(1, min(idx, len(times_ms) - 1))
    t0, t1 = float(times_ms[idx - 1]), float(times_ms[idx])
    a = (pos_ms - t0) / (t1 - t0 + 1e-9)
    return float(levels[idx - 1] * (1.0 - a) + levels[idx] * a)


def wait_playback_idle(*, timeout_s: float = 120.0) -> None:
    """Block until pygame voice playback has finished (used between talk→action steps)."""
    if not pygame.mixer.get_init():
        return
    deadline = time.monotonic() + max(1.0, timeout_s)
    voice_ch = pygame.mixer.Channel(_VOICE_CHANNEL_INDEX)
    while time.monotonic() < deadline:
        try:
            busy = voice_ch.get_busy() or pygame.mixer.get_busy()
        except Exception:
            break
        if not busy:
            break
        _pump_pygame_events()
        time.sleep(0.025)
    for _ in range(20):
        try:
            if not voice_ch.get_busy() and not pygame.mixer.get_busy():
                break
        except Exception:
            break
        _pump_pygame_events()
        time.sleep(0.02)


def play_mp3_bytes(
    data: bytes,
    interrupt_check: Callable[[], bool] | None = None,
    *,
    audio_reset: bool = True,
    hud_level_out: Any | None = None,
    on_playback_start: Callable[[], None] | None = None,
) -> bool:
    """Play MP3 bytes via pygame (writes a short-lived temp file).

    Set ``audio_reset=False`` when playing the next chunk of the same reply so we
    avoid a full ``mixer.stop()`` + long yield (reduces audible gaps between chunks).

    ``hud_level_out``: optional ``multiprocessing.Value`` (``'d'``) updated during
    playback from decoded PCM loudness (0..1) for the Mango HUD dot sphere.
    """
    if not data:
        logger.warning("play_mp3_bytes called with empty bytes")
        return False
    logger.debug("Playback: mp3 bytes=%d", len(data))
    if not pygame.mixer.get_init():
        init_voice_mixer()

    interrupted = False
    poll_ms = 20
    try:
        raw_poll = os.getenv("MANGO_TTS_INTERRUPT_POLL_MS", "").strip()
        if raw_poll:
            poll_ms = max(8, min(int(raw_poll), 80))
    except Exception:
        logger.debug("Invalid MANGO_TTS_INTERRUPT_POLL_MS; using default", exc_info=True)

    with _PLAYBACK_LOCK:
        if audio_reset:
            try:
                pygame.mixer.stop()
            except Exception:
                logger.debug("play_mp3_bytes: mixer.stop noop", exc_info=True)
            time.sleep(0.02)
        else:
            try:
                pygame.mixer.Channel(_VOICE_CHANNEL_INDEX).stop()
            except Exception:
                logger.debug("play_mp3_bytes: channel stop noop", exc_info=True)
            time.sleep(0.004)

        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(data)
                tmp_path = Path(tmp.name)

            sound = pygame.mixer.Sound(str(tmp_path))
            sound.set_volume(1.0)
            desktop_mode = (os.getenv("MANGO_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"})
            need_level_out = hud_level_out is not None or desktop_mode
            if need_level_out:
                samples, sr, dur_ms = _mono_samples_from_sound(sound)
                if samples is not None and samples.size and dur_ms > 0:
                    times_ms, levels = _tts_rms_envelope(samples, sr)
                else:
                    times_ms = np.zeros(0, dtype=np.float64)
                    levels = np.zeros(0, dtype=np.float64)
            else:
                dur_ms = 0.0
                times_ms = np.zeros(0, dtype=np.float64)
                levels = np.zeros(0, dtype=np.float64)

            voice_ch = pygame.mixer.Channel(_VOICE_CHANNEL_INDEX)
            voice_ch.stop()
            voice_ch.play(sound, loops=0)
            if on_playback_start is not None:
                try:
                    on_playback_start()
                except Exception:
                    logger.debug("on_playback_start callback failed", exc_info=True)
            logger.info(
                "Playing TTS (%.1f KiB, SDL driver=%r)",
                len(data) / 1024,
                os.environ.get("SDL_AUDIODRIVER"),
            )
            t_start = time.monotonic()
            hud_smooth = 0.0
            has_env = levels.size > 0
            dur_cap = dur_ms if dur_ms > 0 else 1e9
            # mixer.Channel has no get_pos() (unlike mixer.music); scrub envelope by wall clock.
            while voice_ch.get_busy():
                if interrupt_check is not None and interrupt_check():
                    voice_ch.stop()
                    try:
                        pygame.mixer.stop()
                    except Exception:
                        pass
                    logger.info("TTS playback interrupted (barge-in).")
                    interrupted = True
                    break
                if need_level_out:
                    pos_ms = min(dur_cap, (time.monotonic() - t_start) * 1000.0)
                    if has_env:
                        target = _interp_envelope(times_ms, levels, pos_ms)
                    else:
                        target = 0.42 + 0.28 * math.sin(
                            (time.monotonic() - t_start) * 6.5,
                        )
                    hud_smooth = hud_smooth * 0.38 + target * 0.62
                    smooth_level = float(max(0.0, min(1.0, hud_smooth)))
                    try:
                        if hud_level_out is not None:
                            hud_level_out.value = smooth_level
                    except Exception:
                        pass
                    desktop_ipc.try_set_audio_level(smooth_level)
                _pump_pygame_events()
                pygame.time.delay(poll_ms)
            sound.stop()
            for _ in range(500):
                if not pygame.mixer.get_busy():
                    break
                _pump_pygame_events()
                pygame.time.delay(10)
            logger.debug("Playback finished")
        except Exception:
            logger.exception("play_mp3_bytes failed")
            raise
        finally:
            if hud_level_out is not None:
                try:
                    hud_level_out.value = 0.0
                except Exception:
                    pass
            desktop_ipc.try_set_audio_level(0.0)
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
    return interrupted
