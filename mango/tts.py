"""Text-to-speech: Edge (free) or ElevenLabs (API)."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

import edge_tts

from mango.audio import play_mp3_bytes
from mango.elevenlabs_api import (
    DEFAULT_MP3_FORMAT,
    speech_to_speech_bytes,
    text_to_speech_bytes,
)

if TYPE_CHECKING:
    from mango.config import Config

logger = logging.getLogger(__name__)


def _wait_future(
    future: Future[bytes],
    interrupt_check: Callable[[], bool] | None,
    *,
    poll_s: float = 0.05,
) -> bytes | None:
    """Wait for synth future; return None if barge-in cancels it."""
    while not future.done():
        if interrupt_check is not None and interrupt_check():
            future.cancel()
            return None
        time.sleep(poll_s)
    try:
        return future.result(timeout=0.01)
    except Exception:
        return None


def _chunk_text(text: str, max_len: int = 520) -> list[str]:
    """Split for streaming playback; prefers sentence boundaries."""
    t = (text or "").strip()
    if not t:
        return []
    if len(t) <= max_len:
        return [t]
    parts = re.split(r"(?<=[.!?])\s+", t)
    merged: list[str] = []
    buf = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        candidate = f"{buf} {p}".strip() if buf else p
        if len(candidate) <= max_len:
            buf = candidate
        else:
            if buf:
                merged.append(buf)
            if len(p) > max_len:
                for i in range(0, len(p), max_len):
                    merged.append(p[i : i + max_len])
                buf = ""
            else:
                buf = p
    if buf:
        merged.append(buf)
    return merged if merged else [t[:max_len]]


class EdgeTTS:
    def __init__(
        self,
        voice: str = "en-US-GuyNeural",
        *,
        rate: str = "-8%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
    ) -> None:
        self._voice = voice
        self._rate = rate
        self._pitch = pitch
        self._volume = volume

    def speak(
        self,
        text: str,
        *,
        interrupt_check: Callable[[], bool] | None = None,
        streaming: bool = True,
        hud_level_out: Any | None = None,
        on_playback_start: Callable[[], None] | None = None,
    ) -> bool:
        """Speak text. Returns True if playback was interrupted (barge-in)."""
        text = (text or "").strip()
        if not text:
            logger.warning("speak() skipped — empty text")
            return False
        logger.info(
            "TTS: voice=%s rate=%s pitch=%s volume=%s chars=%d preview=%r",
            self._voice,
            self._rate,
            self._pitch,
            self._volume,
            len(text),
            text[:120],
        )
        eff = streaming and len(text) > 180
        chunks = _chunk_text(text) if eff else [text]
        playback_cb = on_playback_start
        playback_fired = False

        def _playback_start_once() -> None:
            nonlocal playback_fired
            if playback_fired or playback_cb is None:
                return
            playback_fired = True
            playback_cb()

        def _syn_edge(part: str) -> bytes:
            return asyncio.run(self._synthesize(part))

        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending: Future[bytes] | None = None
                for i, part in enumerate(chunks):
                    if interrupt_check is not None and interrupt_check():
                        logger.info("TTS stopped before chunk %d/%d (interrupt).", i + 1, len(chunks))
                        return True
                    t_syn = time.monotonic()
                    if pending is None:
                        pending = pool.submit(_syn_edge, part)
                    mp3 = _wait_future(pending, interrupt_check)
                    pending = None
                    if mp3 is None:
                        return True
                    logger.debug(
                        "TTS chunk %d/%d synthesized %d bytes in %.2fs",
                        i + 1,
                        len(chunks),
                        len(mp3),
                        time.monotonic() - t_syn,
                    )
                    if i + 1 < len(chunks):
                        pending = pool.submit(_syn_edge, chunks[i + 1])
                    interrupted = play_mp3_bytes(
                        mp3,
                        interrupt_check=interrupt_check,
                        audio_reset=(i == 0),
                        hud_level_out=hud_level_out,
                        on_playback_start=_playback_start_once if i == 0 else None,
                    )
                    if interrupted:
                        if pending is not None:
                            pending.cancel()
                        return True
        except Exception:
            logger.exception("edge-tts synthesis/playback failed")
            raise
        return False

    async def _synthesize(self, text: str) -> bytes:
        communicate = edge_tts.Communicate(
            text,
            self._voice,
            rate=self._rate,
            pitch=self._pitch,
            volume=self._volume,
        )
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)


class ElevenLabsTTS:
    """ElevenLabs text-to-speech; optional speech-to-speech pass on the synthesized clip."""

    def __init__(
        self,
        *,
        api_key: str,
        api_base: str,
        voice_id: str,
        tts_model_id: str,
        sts_model_id: str,
        sts_after_tts: bool,
        output_format: str = DEFAULT_MP3_FORMAT,
        edge_fallback_voice: str | None = None,
            edge_fallback_rate: str = "-8%",
            edge_fallback_pitch: str = "+0Hz",
            edge_fallback_volume: str = "+0%",
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base
        self._voice_id = voice_id
        self._tts_model_id = tts_model_id
        self._sts_model_id = sts_model_id
        self._sts_after_tts = sts_after_tts
        self._output_format = output_format
        self._edge_fallback = (
            EdgeTTS(
                voice=edge_fallback_voice,
                rate=edge_fallback_rate,
                pitch=edge_fallback_pitch,
                volume=edge_fallback_volume,
            )
            if edge_fallback_voice
            else None
        )

    def speak(
        self,
        text: str,
        *,
        interrupt_check: Callable[[], bool] | None = None,
        streaming: bool = True,
        hud_level_out: Any | None = None,
        on_playback_start: Callable[[], None] | None = None,
    ) -> bool:
        """Speak text. Returns True if playback was interrupted (barge-in)."""
        text = (text or "").strip()
        if not text:
            logger.warning("ElevenLabs speak() skipped — empty text")
            return False
        logger.info(
            "ElevenLabs TTS: voice_id=%s chars=%d preview=%r sts_after=%s",
            self._voice_id[:8] + "…" if len(self._voice_id) > 8 else self._voice_id,
            len(text),
            text[:120],
            self._sts_after_tts,
        )
        # Fewer, larger chunks + overlap synth with playback → fewer Bluetooth/SDL gaps.
        eff = streaming and len(text) > 250
        chunks = _chunk_text(text, max_len=2000) if eff else [text]
        playback_cb = on_playback_start
        playback_fired = False

        def _playback_start_once() -> None:
            nonlocal playback_fired
            if playback_fired or playback_cb is None:
                return
            playback_fired = True
            playback_cb()

        def _syn_el(part: str) -> bytes:
            mp3 = text_to_speech_bytes(
                api_key=self._api_key,
                base_url=self._api_base,
                voice_id=self._voice_id,
                text=part,
                model_id=self._tts_model_id,
                output_format=self._output_format,
            )
            if self._sts_after_tts:
                try:
                    mp3 = speech_to_speech_bytes(
                        api_key=self._api_key,
                        base_url=self._api_base,
                        voice_id=self._voice_id,
                        audio_bytes=mp3,
                        audio_filename="tts_reply.mp3",
                        sts_model_id=self._sts_model_id,
                        output_format=self._output_format,
                        file_format="other",
                    )
                except Exception:
                    logger.exception(
                        "ElevenLabs STS failed — playing raw TTS audio instead."
                    )
            return mp3

        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending: Future[bytes] | None = None
                for i, part in enumerate(chunks):
                    if interrupt_check is not None and interrupt_check():
                        logger.info(
                            "ElevenLabs TTS stopped before chunk %d/%d (interrupt).",
                            i + 1,
                            len(chunks),
                        )
                        return True
                    t_syn = time.monotonic()
                    if pending is None:
                        pending = pool.submit(_syn_el, part)
                    mp3 = _wait_future(pending, interrupt_check)
                    pending = None
                    if mp3 is None:
                        return True
                    logger.debug(
                        "ElevenLabs chunk %d/%d synthesized %d bytes in %.2fs",
                        i + 1,
                        len(chunks),
                        len(mp3),
                        time.monotonic() - t_syn,
                    )
                    if i + 1 < len(chunks):
                        pending = pool.submit(_syn_el, chunks[i + 1])
                    interrupted = play_mp3_bytes(
                        mp3,
                        interrupt_check=interrupt_check,
                        audio_reset=(i == 0),
                        hud_level_out=hud_level_out,
                        on_playback_start=_playback_start_once if i == 0 else None,
                    )
                    if interrupted:
                        if pending is not None:
                            pending.cancel()
                        return True
        except Exception as exc:
            if self._edge_fallback is None:
                logger.exception("ElevenLabs TTS pipeline failed")
                raise
            logger.warning(
                "ElevenLabs TTS failed (%s) — falling back to Edge TTS for this utterance.",
                exc,
            )
            return self._edge_fallback.speak(
                text,
                interrupt_check=interrupt_check,
                streaming=streaming,
                hud_level_out=hud_level_out,
                on_playback_start=on_playback_start,
            )
        return False


def make_tts(cfg: Config) -> EdgeTTS | ElevenLabsTTS:
    if cfg.tts_provider == "elevenlabs":
        if not cfg.elevenlabs_api_key:
            raise RuntimeError("ElevenLabs TTS selected but ELEVENLABS_API_KEY is missing.")
        return ElevenLabsTTS(
            api_key=cfg.elevenlabs_api_key,
            api_base=cfg.elevenlabs_api_base,
            voice_id=cfg.elevenlabs_voice_id,
            tts_model_id=cfg.elevenlabs_tts_model,
            sts_model_id=cfg.elevenlabs_sts_model,
            sts_after_tts=cfg.elevenlabs_sts_after_tts,
            edge_fallback_voice=cfg.edge_voice,
            edge_fallback_rate=cfg.edge_rate,
            edge_fallback_pitch=cfg.edge_pitch,
            edge_fallback_volume=cfg.edge_volume,
        )
    return EdgeTTS(
        voice=cfg.edge_voice,
        rate=cfg.edge_rate,
        pitch=cfg.edge_pitch,
        volume=cfg.edge_volume,
    )
