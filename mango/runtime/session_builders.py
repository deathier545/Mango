"""Build voice-session runtime pieces from config."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from mango.config import Config
from mango.conversation import trim_conversation
from mango.llm import GroqLLM, OllamaLLM
from mango.memory_store import load_persistent_messages
from mango.stt import WhisperSTT
from mango.tts import make_tts
from mango.voice_prompt import _build_system_prompt

logger = logging.getLogger(__name__)


def build_stt_runtime(cfg: Config) -> tuple[WhisperSTT, WhisperSTT | None]:
    audio = cfg.audio
    stt = WhisperSTT(
        model_size=audio.whisper_model,
        vad_filter=audio.whisper_vad_filter,
        no_speech_threshold=audio.whisper_no_speech_threshold,
        log_prob_threshold=audio.whisper_log_prob_threshold,
        normalize_target_peak=audio.normalize_target_peak,
        normalize_max_gain=audio.normalize_max_gain,
    )
    stt_wake: WhisperSTT | None = None
    wake_model = (cfg.wake.wake_whisper_model or "").strip()
    if cfg.wake.enabled and wake_model and wake_model != audio.whisper_model:
        stt_wake = WhisperSTT(
            model_size=wake_model,
            vad_filter=audio.whisper_vad_filter,
            no_speech_threshold=audio.whisper_no_speech_threshold,
            log_prob_threshold=audio.whisper_log_prob_threshold,
            normalize_target_peak=audio.normalize_target_peak,
            normalize_max_gain=audio.normalize_max_gain,
        )
        logger.info(
            "Dedicated Whisper model for wake only: %s (main STT: %s).",
            wake_model,
            audio.whisper_model,
        )
    preload_whisper = os.getenv("MANGO_PRELOAD_WHISPER", "1").strip().lower()
    if preload_whisper not in ("0", "false", "no", "off"):
        if stt_wake is not None:
            try:
                stt_wake.warm_model()
                logger.info("Wake Whisper preload finished before listener start.")
            except Exception:
                logger.exception("Wake Whisper preload failed")

        def _preload_whisper() -> None:
            try:
                stt.warm_model()
                logger.info("Background Whisper preload finished.")
            except Exception:
                logger.exception("Background Whisper preload failed")

        threading.Thread(target=_preload_whisper, daemon=True).start()
        logger.info("Whisper preload scheduled (MANGO_PRELOAD_WHISPER).")
    return stt, stt_wake


def build_llm_runtime(cfg: Config) -> GroqLLM | OllamaLLM:
    llm_cfg = cfg.llm
    if llm_cfg.provider == "ollama":
        llm: GroqLLM | OllamaLLM = OllamaLLM(
            base_url=llm_cfg.ollama_base_url,
            model=llm_cfg.ollama_model,
            timeout_seconds=cfg.ollama_timeout_s,
        )
        logger.info(
            "Using Ollama at %s model=%s",
            llm_cfg.ollama_base_url,
            llm_cfg.ollama_model,
        )
        return llm
    llm = GroqLLM(
        api_key=cfg.groq_api_key,
        model=cfg.groq_model,
        timeout_seconds=cfg.groq_timeout_s,
    )
    return llm


def build_memory_runtime(cfg: Config) -> tuple[list[dict[str, Any]], str]:
    system_prompt = _build_system_prompt(cfg)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    if cfg.persistent_memory:
        prior = load_persistent_messages(
            cfg.memory_dir,
            max_messages=cfg.max_conversation_messages,
            merge_days=cfg.memory_merge_days,
        )
        if prior:
            messages.extend(prior)
        trim_conversation(messages, cfg.max_conversation_messages)
    return messages, system_prompt


def build_tts_runtime(cfg: Config) -> Any:
    return make_tts(cfg)
