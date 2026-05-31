"""ElevenLabs REST: text-to-speech and speech-to-speech (voice changer)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from mango.retry_utils import retry_call
from mango.timeouts import ELEVENLABS_STS_S, ELEVENLABS_TTS_S

logger = logging.getLogger(__name__)

DEFAULT_MP3_FORMAT = "mp3_44100_128"


def text_to_speech_bytes(
    *,
    api_key: str,
    base_url: str,
    voice_id: str,
    text: str,
    model_id: str,
    output_format: str = DEFAULT_MP3_FORMAT,
    timeout_s: float = ELEVENLABS_TTS_S,
) -> bytes:
    url = f"{base_url.rstrip('/')}/v1/text-to-speech/{voice_id}"
    payload: dict[str, Any] = {"text": text, "model_id": model_id}
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    with httpx.Client(timeout=timeout_s) as client:
        r = retry_call(
            lambda: client.post(
                url,
                headers=headers,
                params={"output_format": output_format},
                json=payload,
            ),
            attempts=3,
            base_delay_s=0.5,
            retry_on=(httpx.TransportError,),
            retry_if_result=lambda resp: resp.status_code in (429, 500, 502, 503, 504),
            label="elevenlabs_tts_post",
        )
        if r.status_code >= 400:
            logger.warning(
                "ElevenLabs TTS HTTP %s body_snippet=%r",
                r.status_code,
                (r.text or "")[:400],
            )
        r.raise_for_status()
        return r.content


def speech_to_speech_bytes(
    *,
    api_key: str,
    base_url: str,
    voice_id: str,
    audio_bytes: bytes,
    audio_filename: str = "speech.mp3",
    sts_model_id: str,
    output_format: str = DEFAULT_MP3_FORMAT,
    file_format: str = "other",
    timeout_s: float = ELEVENLABS_STS_S,
) -> bytes:
    """Voice-changer: reshape `audio_bytes` into `voice_id` (content follows input audio)."""
    url = f"{base_url.rstrip('/')}/v1/speech-to-speech/{voice_id}"
    headers = {"xi-api-key": api_key}
    files = {
        "audio": (audio_filename, audio_bytes, "application/octet-stream"),
    }
    data = {"model_id": sts_model_id, "file_format": file_format}
    with httpx.Client(timeout=timeout_s) as client:
        r = retry_call(
            lambda: client.post(
                url,
                headers=headers,
                params={"output_format": output_format},
                files=files,
                data=data,
            ),
            attempts=3,
            base_delay_s=0.5,
            retry_on=(httpx.TransportError,),
            retry_if_result=lambda resp: resp.status_code in (429, 500, 502, 503, 504),
            label="elevenlabs_sts_post",
        )
        if r.status_code >= 400:
            logger.warning(
                "ElevenLabs STS HTTP %s body_snippet=%r",
                r.status_code,
                (r.text or "")[:400],
            )
        r.raise_for_status()
        return r.content
