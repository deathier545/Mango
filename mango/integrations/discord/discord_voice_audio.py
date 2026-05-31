"""TTS synthesis and playback into a Discord voice client.

The selfbot bridge **never** records or transcribes other participants’ audio; desktop Mango
uses your **local microphone** for STT. This module only pushes synthesized speech **into** Discord.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import discord

logger = logging.getLogger(__name__)


def synthesize_mp3_sync(cfg: Any, text: str) -> bytes:
    """Synthesize speech to MP3 bytes (Edge or ElevenLabs from ``cfg``)."""
    text = (text or "").strip()
    if not text:
        return b""
    if cfg.tts_provider == "elevenlabs":
        from mango.elevenlabs_api import DEFAULT_MP3_FORMAT, text_to_speech_bytes

        if not cfg.elevenlabs_api_key or not cfg.elevenlabs_voice_id:
            raise RuntimeError("ElevenLabs TTS selected but key/voice missing in config.")
        return text_to_speech_bytes(
            api_key=cfg.elevenlabs_api_key,
            base_url=cfg.elevenlabs_api_base,
            voice_id=cfg.elevenlabs_voice_id,
            text=text,
            model_id=cfg.elevenlabs_tts_model,
            output_format=DEFAULT_MP3_FORMAT,
        )
    import edge_tts

    async def _run() -> bytes:
        communicate = edge_tts.Communicate(text, cfg.edge_voice)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    return asyncio.run(_run())


async def play_tts_in_voice(vc: discord.VoiceClient, cfg: Any, text: str) -> None:
    """Decode MP3 with FFmpeg and play into the given voice client (blocks until finished)."""
    if vc.is_playing():
        raise RuntimeError("Voice client is already playing.")
    mp3 = await asyncio.to_thread(synthesize_mp3_sync, cfg, text)
    if not mp3:
        raise RuntimeError("Empty TTS output.")
    fd, tmp_name = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    tmp = Path(tmp_name)
    src: discord.FFmpegPCMAudio | None = None
    try:
        tmp.write_bytes(mp3)
        src = discord.FFmpegPCMAudio(str(tmp))
        loop = asyncio.get_running_loop()
        play_done = asyncio.Event()

        def _after(err: BaseException | None) -> None:
            if err:
                logger.warning("Discord play finished with err=%s", err)
            loop.call_soon_threadsafe(play_done.set)

        vc.play(src, after=_after)
        await play_done.wait()
    finally:
        if src is not None:
            src.cleanup()
        for _ in range(5):
            try:
                tmp.unlink(missing_ok=True)
                break
            except PermissionError:
                await asyncio.sleep(0.1)
