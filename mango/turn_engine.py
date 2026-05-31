"""Turn orchestration extracted from the main voice loop."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

import pygame

from mango.always_listen_gate import transcript_starts_with_any_prefix
from mango.config import Config
from mango.conversation import trim_conversation
from mango.integrations.spotify.spotify_volume_duck import duck_spotify_session
from mango.metrics import clear_correlation_id, emit_metric, start_turn_correlation
from mango.tool_narration import set_narration_interrupt_check
from mango.tool_recovery import strip_pseudo_tool_markup_for_speech
from mango.transcript_postprocess import normalize_transcript_text

logger = logging.getLogger(__name__)


@dataclass
class TurnOutcome:
    reply: str | None = None
    interrupted: bool = False


def _speech_safe_reply(reply: str, max_chars: int) -> str:
    compact = strip_pseudo_tool_markup_for_speech(reply or "")
    compact = " ".join(compact.split())
    if len(compact) <= max_chars:
        return compact
    keep = max(40, max_chars - len("... I can give more details if you want."))
    clipped = compact[:keep].rstrip(" ,;:")
    return clipped + "... I can give more details if you want."


def _barge_post_tts_pause(cfg: Config) -> float:
    raw = os.getenv("MANGO_BARGE_POST_TTS_SECONDS", "").strip()
    if raw:
        try:
            return max(0.0, min(float(raw), 2.0))
        except ValueError:
            logger.debug("Invalid MANGO_BARGE_POST_TTS_SECONDS=%r", raw)
    return min(cfg.wake_post_tts_seconds, 0.25)


def run_turn(
    *,
    audio: Any,
    source: str,
    cfg: Config,
    stt: Any,
    llm: Any,
    registry: Any,
    messages: list[dict[str, Any]],
    tts: Any,
    hud_level: Any,
    wake_suppress: threading.Event,
    wake_turn_lock: threading.Lock,
    wake_turn_depth: list[int],
    set_assistant_state: Any,
    barge_check: Any,
    speak_reply: Any,
    speaking_reply: Any,
    persist_memory: Any,
) -> TurnOutcome:
    """Run one end-to-end user turn from audio buffer to spoken assistant reply."""
    with wake_turn_lock:
        wake_turn_depth[0] += 1
    wake_suppress.set()
    cid = start_turn_correlation(source)
    emit_metric("turn_start", source=source, correlation_id=cid)

    suppress_pause_s = [cfg.suppress_after_skipped_turn_seconds]

    def _finish_wake_suppress() -> None:
        deadline = time.monotonic() + 120.0
        while time.monotonic() < deadline:
            try:
                if not (pygame.mixer.get_init() and pygame.mixer.get_busy()):
                    break
            except Exception:
                break
            time.sleep(0.03)
        if suppress_pause_s[0] > 0:
            time.sleep(suppress_pause_s[0])
        with wake_turn_lock:
            wake_turn_depth[0] -= 1
            if wake_turn_depth[0] <= 0:
                wake_turn_depth[0] = 0
                wake_suppress.clear()

    def _mark_interrupted(phase: str) -> None:
        suppress_pause_s[0] = _barge_post_tts_pause(cfg)
        emit_metric(
            "turn_barge_in",
            source=source,
            phase=phase,
            correlation_id=cid,
        )

    try:
        samples = int(cfg.sample_rate * cfg.min_record_seconds)
        if audio.size < samples:
            logger.warning(
                "Skipping turn (%s): recording too short (%d samples, need >= %d).",
                source,
                audio.size,
                samples,
            )
            return TurnOutcome()
        with duck_spotify_session():
            set_assistant_state("thinking")
            logger.info("Starting transcription (%s)…", source)
            t_stt = time.perf_counter()
            user_text = stt.transcribe(audio, cfg.sample_rate)
            user_text = normalize_transcript_text(user_text)
            logger.info("STT finished in %.2fs", time.perf_counter() - t_stt)
            emit_metric("turn_stt_done", source=source, stt_s=round(time.perf_counter() - t_stt, 3))
            if not user_text.strip():
                logger.warning(
                    "Whisper returned empty text — skipped (%s). "
                    "Speak louder or check the default mic; try MANGO_WHISPER_VAD_FILTER=0 for quiet headsets.",
                    source,
                )
                return TurnOutcome()
            logger.info("You said (%s): %s", source, user_text)
            if source == "vad" and cfg.always_listen and cfg.always_listen_require_transcript_prefix:
                prefs = cfg.always_listen_transcript_prefixes
                if not transcript_starts_with_any_prefix(user_text, prefs):
                    logger.info(
                        "Always-listen ignored (transcript start not in %s): %s",
                        list(prefs),
                        user_text[:200] + ("..." if len(user_text) > 200 else ""),
                    )
                    return TurnOutcome()
            messages.append({"role": "user", "content": user_text.strip()})
            registry.try_arm_powershell_from_user(user_text.strip())
            from mango.voice_prompt import refresh_system_message

            refresh_system_message(messages, cfg)
            t_llm = time.perf_counter()
            llm_stats: dict[str, int] = {}
            set_narration_interrupt_check(barge_check)
            try:
                reply = speaking_reply(
                    llm,
                    registry,
                    messages,
                    max_tool_rounds=cfg.max_llm_tool_rounds,
                    stats_out=llm_stats,
                    interrupt_check=barge_check,
                )
            finally:
                set_narration_interrupt_check(None)
            llm_interrupted = llm_stats.get("interrupted", 0) > 0
            logger.info(
                "LLM finished in %.2fs — Mango reply: %s",
                time.perf_counter() - t_llm,
                reply,
            )
            emit_metric(
                "turn_llm_done",
                source=source,
                llm_s=round(time.perf_counter() - t_llm, 3),
                llm_calls=llm_stats.get("llm_calls", 0),
                tool_steps=llm_stats.get("total_steps", 0),
                tool_calls_executed=llm_stats.get("tool_calls_executed", 0),
                rounds_with_tool_calls=llm_stats.get("rounds_with_tool_calls", 0),
                interrupted=int(llm_interrupted),
            )
            if llm_interrupted:
                _mark_interrupted("llm")
                trim_conversation(messages, cfg.max_conversation_messages)
                persist_memory()
                emit_metric("turn_done", source=source, interrupted=1)
                return TurnOutcome(reply=None, interrupted=True)

            suppress_pause_s[0] = cfg.wake_post_tts_seconds
            spoken_reply = _speech_safe_reply(reply, cfg.max_spoken_reply_chars)
            if spoken_reply != reply:
                logger.info(
                    "Spoken reply clipped for TTS (%d -> %d chars).",
                    len(reply),
                    len(spoken_reply),
                )

            def _on_reply_playback_start() -> None:
                set_assistant_state("speaking")

            t_tts = time.perf_counter()
            tts_interrupted = bool(
                speak_reply(
                    cfg,
                    tts,
                    spoken_reply,
                    interrupt_check=barge_check,
                    streaming=cfg.streaming_tts,
                    hud_level_out=hud_level,
                    on_playback_start=_on_reply_playback_start,
                )
            )
            logger.info("TTS finished in %.2fs", time.perf_counter() - t_tts)
            emit_metric(
                "turn_tts_done",
                source=source,
                tts_s=round(time.perf_counter() - t_tts, 3),
                interrupted=int(tts_interrupted),
            )
            if tts_interrupted:
                _mark_interrupted("tts")
            trim_conversation(messages, cfg.max_conversation_messages)
            persist_memory()
            emit_metric("turn_done", source=source, interrupted=int(tts_interrupted))
            return TurnOutcome(reply=reply, interrupted=tts_interrupted)
    finally:
        clear_correlation_id()
        threading.Thread(
            target=_finish_wake_suppress,
            daemon=True,
            name="MangoWakeUnsuppress",
        ).start()
