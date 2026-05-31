"""Push-to-talk voice session loop: mic -> Whisper -> LLM + tools -> TTS."""

from __future__ import annotations

import ctypes
import logging
import os
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any

# Quieter Hugging Face cache on Windows (no symlink support unless Developer Mode).
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from dotenv import load_dotenv

# Minimal .env load before pygame/SDL audio initializes (so MANGO_SDL_AUDIODRIVER applies).
_ENV_BOOT = Path(__file__).resolve().parent.parent / ".env"
if _ENV_BOOT.is_file():
    load_dotenv(dotenv_path=_ENV_BOOT, override=False, encoding="utf-8-sig")

if sys.platform == "win32":
    _sdl = (os.getenv("MANGO_SDL_AUDIODRIVER") or "directsound").strip() or "directsound"
    os.environ.setdefault("SDL_AUDIODRIVER", _sdl)

import keyboard
import sounddevice as sd
from groq import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)

import mango.desktop.desktop_ipc as desktop_ipc
from mango.audio import (
    init_voice_mixer,
    record_hands_free,
    record_while_held,
    release_mixer_before_mic,
)
from mango.config import Config, apply_cli_wake_oww_test
from mango.continuous_listen import ContinuousVoiceListener
from mango.desktop.mango_hud import MangoHud
from mango.integrations.spotify.spotify_volume_duck import duck_spotify_session
from mango.interruption_policy import resolve_profile, should_trigger_barge_with_profile
from mango.listen_chime import play_listen_chime
from mango.llm_tool_loop import _needs_immediate_confirmation_followup, speaking_reply
from mango.logging_setup import setup_logging
from mango.memory_store import save_persistent_messages
from mango.metrics import emit_metric
from mango.quiet_hours import in_quiet_hours, local_now
from mango.reminder_watchdog import start_watchdog as start_reminder_watchdog
from mango.runtime.session_builders import (
    build_llm_runtime,
    build_memory_runtime,
    build_stt_runtime,
    build_tts_runtime,
)
from mango.session_log import save_session_snapshot
from mango.startup_intro import maybe_play_startup_intro
from mango.tool_registry import ToolRegistry
from mango.turn_engine import TurnOutcome, run_turn
from mango.wake.wake_listener import WakeWordListener

logger = logging.getLogger(__name__)


def _hotkey_label(hk: str) -> str:
    return "+".join(p.strip().upper() for p in hk.split("+") if p.strip())


def _speak_mango_reply(
    cfg: Config,
    tts: Any,
    reply: str,
    *,
    interrupt_check: Any,
    streaming: bool,
    hud_level_out: Any,
    on_playback_start: Any = None,
) -> bool:
    """Play assistant reply. Returns True if interrupted (barge-in)."""
    fired = False

    def _once() -> None:
        nonlocal fired
        if fired:
            return
        fired = True
        if on_playback_start is not None:
            on_playback_start()

    if cfg.tts_playback == "discord":
        from mango.integrations.discord.discord_tts_client import speak_via_discord

        ok, msg = speak_via_discord(
            reply,
            interrupt_check=interrupt_check,
            on_playback_start=_once,
        )
        if ok:
            if "(interrupt)" in (msg or "").casefold():
                logger.info("Discord TTS interrupted: %s", msg)
                return True
            logger.info("TTS via Discord bridge: %s", msg)
            return False
        logger.warning("Discord TTS failed (%s) — falling back to headset.", msg)
    return tts.speak(
        reply,
        interrupt_check=interrupt_check,
        streaming=streaming,
        hud_level_out=hud_level_out,
        on_playback_start=_once,
    )


def _drain_utterance_queue(q: queue.Queue) -> int:
    """Drop pending VAD clips (e.g. stale overlap with wake word or PTT)."""
    dropped = 0
    while True:
        try:
            q.get_nowait()
            dropped += 1
        except queue.Empty:
            break
    if dropped:
        logger.info("Dropped %d stale always-listen clip(s) from the queue.", dropped)
    return dropped


def _windows_is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        logger.debug("Could not detect Windows admin status", exc_info=True)
        return False


def run_voice_session(
    stop_event: Any = None,
    *,
    ptt_only: bool = False,
    wake_oww_cli: bool = False,
    wake_oww_cli_score_only: bool = False,
) -> None:
    """Full voice/STT/LLM/TTS pipeline. Pass a threading or multiprocessing Event for graceful shutdown."""
    try:
        cfg = Config.load()
    except RuntimeError as exc:
        logger.error("Startup aborted: %s", exc)
        print(exc, file=sys.stderr)
        sys.exit(1)

    if wake_oww_cli:
        apply_cli_wake_oww_test(cfg, score_only=wake_oww_cli_score_only)

    if cfg.safe_mode:
        ptt_only = True

    if ptt_only:
        cfg.always_listen = False
        hk = _hotkey_label(cfg.hotkey)
        logger.info(
            "Push-to-talk only (--ptt-only): always-listen disabled for this run; hold %s while speaking, then release.",
            hk,
        )
    try:
        init_voice_mixer()
    except Exception:
        logger.exception("Voice mixer init failed")
        raise

    stt, stt_wake = build_stt_runtime(cfg)
    tts = build_tts_runtime(cfg)
    llm = build_llm_runtime(cfg)
    registry = ToolRegistry(cfg)
    messages, system_prompt = build_memory_runtime(cfg)

    def _persist_memory() -> None:
        if not cfg.persistent_memory:
            return
        try:
            save_persistent_messages(
                cfg.memory_dir,
                messages[1:],
                max_messages=cfg.max_conversation_messages,
                write_daily_snapshot=cfg.memory_daily_snapshots,
            )
        except Exception:
            logger.debug("Persistent memory save failed", exc_info=True)

    logger.debug(
        "System prompt length=%d chars (preset=%s skills_dir=%s)",
        len(system_prompt),
        cfg.preset,
        cfg.skills_dir,
    )

    logger.info(
        "Mango ready. Press and HOLD %s before you talk, keep holding while speaking, then release.",
        _hotkey_label(cfg.hotkey),
    )
    logger.info("Ctrl+C to exit.")
    if sys.platform == "win32" and not _windows_is_admin():
        logger.warning(
            "Not running as Administrator — keyboard hooks often fail globally on Windows; "
            "run elevated if holding the push-to-talk key does nothing.",
        )

    idle_sleep_s = min(0.03, max(0.01, float(cfg.vad_thread_idle_sleep_seconds)))

    try:
        mic_info = sd.query_devices(kind="input")
        logger.info("Default input microphone: %s", mic_info["name"])
    except Exception as exc:
        logger.error("Could not query default microphone: %s", exc, exc_info=True)

    if not cfg.search_roots:
        logger.warning("No search roots (Documents/Desktop/Downloads missing).")
    logger.info(
        "Mic tuning: MANGO_MIN_RECORD_SECONDS=%.2f, normalize_peak=%.2f, whisper_vad=%s — "
        "if Whisper often skips or hallucinates, try MANGO_AUDIO_NORMALIZE_* or MANGO_WHISPER_NO_SPEECH_THRESHOLD.",
        cfg.min_record_seconds,
        cfg.audio_normalize_target_peak,
        cfg.whisper_vad_filter,
    )

    logger.debug(
        "Main loop parameters min_record_seconds=%s samples_cutoff=%d",
        cfg.min_record_seconds,
        int(cfg.sample_rate * cfg.min_record_seconds),
    )

    wake_event = threading.Event()
    stop_wake = threading.Event()
    wake_thread: threading.Thread | None = None
    stop_vad = threading.Event()
    stop_reminders = threading.Event()
    if cfg.safe_mode:
        logger.info("Safe mode: reminder watchdog disabled.")
    else:
        start_reminder_watchdog(stop_reminders)
    vad_thread: threading.Thread | None = None
    vad_queue: queue.Queue = queue.Queue(maxsize=2)
    # While set, WakeWordListener skips mic sampling (avoids Whisper on TTS bleed / parallel STT noise).
    wake_suppress = threading.Event()
    wake_turn_depth: list[int] = [0]
    wake_turn_lock = threading.Lock()

    disable_legacy_hud = os.getenv("MANGO_DISABLE_LEGACY_HUD", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    hud = None if disable_legacy_hud else MangoHud.try_start()
    hud_level = hud.level_sink() if hud else None
    from mango.tool_narration import set_narration_hud_level

    set_narration_hud_level(hud_level)
    _interrupt_profile = resolve_profile(cfg.interruption_profile)
    _barge_cooldown_raw = os.getenv("MANGO_BARGE_COOLDOWN_MS", "250").strip() or "250"
    try:
        _barge_cooldown_ms = int(_barge_cooldown_raw)
    except ValueError:
        logger.warning("Invalid MANGO_BARGE_COOLDOWN_MS=%r — using 250", _barge_cooldown_raw)
        _barge_cooldown_ms = 250
    _barge_cooldown_ms = max(0, min(2000, _barge_cooldown_ms))
    logger.info(
        "Interruption tuning: profile=%s min_hold_ms=%d barge_cooldown_ms=%d",
        _interrupt_profile.name,
        _interrupt_profile.min_barge_hold_ms,
        _barge_cooldown_ms,
    )
    _barge_press_started = [0.0]
    _barge_triggered = [False]
    _barge_block_until = [0.0]

    def _set_assistant_state(state: str) -> None:
        if hud:
            hud.set_state(state)
        desktop_ipc.try_set_ai_state(state)

    def _barge() -> bool:
        try:
            pressed = keyboard.is_pressed(cfg.hotkey)
        except Exception:
            return False
        now = time.monotonic()
        if now < _barge_block_until[0]:
            if not pressed:
                _barge_press_started[0] = 0.0
                _barge_triggered[0] = False
            return False
        if not pressed:
            if _barge_press_started[0] > 0.0 and not _barge_triggered[0]:
                held_ms = (now - _barge_press_started[0]) * 1000.0
                if should_trigger_barge_with_profile(_interrupt_profile, held_ms):
                    _barge_triggered[0] = True
                    emit_metric(
                        "barge_trigger",
                        profile=_interrupt_profile.name,
                        held_ms=round(held_ms, 1),
                        min_hold_ms=_interrupt_profile.min_barge_hold_ms,
                        interrupt_latency_ms=round(held_ms, 1),
                        edge="release",
                    )
                    _barge_block_until[0] = now + (_barge_cooldown_ms / 1000.0)
                    _barge_press_started[0] = 0.0
                    return True
                emit_metric(
                    "barge_missed_candidate",
                    profile=_interrupt_profile.name,
                    held_ms=round(held_ms, 1),
                    min_hold_ms=_interrupt_profile.min_barge_hold_ms,
                )
            _barge_press_started[0] = 0.0
            _barge_triggered[0] = False
            return False
        if _barge_press_started[0] <= 0.0:
            _barge_press_started[0] = now
            _barge_triggered[0] = False
            emit_metric(
                "barge_press_start",
                profile=_interrupt_profile.name,
                min_hold_ms=_interrupt_profile.min_barge_hold_ms,
            )
            triggered = should_trigger_barge_with_profile(_interrupt_profile, 0.0)
            if triggered:
                _barge_triggered[0] = True
                emit_metric(
                    "barge_trigger",
                    profile=_interrupt_profile.name,
                    held_ms=0.0,
                    min_hold_ms=_interrupt_profile.min_barge_hold_ms,
                    interrupt_latency_ms=0.0,
                )
                _barge_block_until[0] = now + (_barge_cooldown_ms / 1000.0)
            return triggered
        held_ms = (now - _barge_press_started[0]) * 1000.0
        triggered = should_trigger_barge_with_profile(_interrupt_profile, held_ms)
        if triggered and not _barge_triggered[0]:
            _barge_triggered[0] = True
            emit_metric(
                "barge_trigger",
                profile=_interrupt_profile.name,
                held_ms=round(held_ms, 1),
                min_hold_ms=_interrupt_profile.min_barge_hold_ms,
                interrupt_latency_ms=round(held_ms, 1),
            )
            _barge_block_until[0] = now + (_barge_cooldown_ms / 1000.0)
        return triggered

    def _run_turn(audio: Any, source: str) -> TurnOutcome:
        return run_turn(
            audio=audio,
            source=source,
            cfg=cfg,
            stt=stt,
            llm=llm,
            registry=registry,
            messages=messages,
            tts=tts,
            hud_level=hud_level,
            wake_suppress=wake_suppress,
            wake_turn_lock=wake_turn_lock,
            wake_turn_depth=wake_turn_depth,
            set_assistant_state=_set_assistant_state,
            barge_check=_barge,
            speak_reply=_speak_mango_reply,
            speaking_reply=speaking_reply,
            persist_memory=_persist_memory,
        )

    def _handoff_barge_capture(outcome: TurnOutcome, source: str) -> TurnOutcome:
        """If user barged in and PTT is still held, capture the interrupt utterance."""
        if not outcome.interrupted:
            return outcome
        try:
            if not keyboard.is_pressed(cfg.hotkey):
                return outcome
        except Exception:
            return outcome
        logger.info("Barge handoff — PTT still held, capturing interrupt utterance.")
        _set_assistant_state("listening")
        release_mixer_before_mic()
        if cfg.listen_chime_ptt:
            play_listen_chime()
        with duck_spotify_session():
            audio = record_while_held(cfg.hotkey, cfg.sample_rate, wait_for_key=False)
            samples = int(cfg.sample_rate * cfg.min_record_seconds)
            if audio.size < samples:
                return outcome
            emit_metric("turn_barge_in", source=source, capture_handoff=True)
            return _run_turn(audio, f"{source}_barge")

    try:
        skip_intro = in_quiet_hours(
            local_now(cfg.quiet_timezone),
            cfg.quiet_hours,
        )
        maybe_play_startup_intro(tts, hud, skip=skip_intro, cfg=cfg, set_state=_set_assistant_state)

        if cfg.always_listen:
            vad_thread = ContinuousVoiceListener(
                cfg=cfg,
                utterance_queue=vad_queue,
                stop_event=stop_vad,
                suppress_event=wake_suppress,
            )
            vad_thread.start()
            extra = ""
            if cfg.always_listen_require_transcript_prefix:
                extra = (
                    " VAD-only if transcript starts with one of "
                    f"{list(cfg.always_listen_transcript_prefixes)!r} (punctuation-insensitive)."
                )
            logger.info(
                "Always-listen (energy VAD) is on — speak anytime; Mango listens after you pause.%s "
                "Wake phrase + %s still work.",
                extra,
                _hotkey_label(cfg.hotkey),
            )
        if cfg.wake_word_enabled:
            wake_thread = WakeWordListener(
                stt=stt,
                cfg=cfg,
                wake_event=wake_event,
                stop_event=stop_wake,
                suppress_event=wake_suppress,
                mic_busy=None,
                stt_wake=stt_wake,
            )
            wake_thread.start()
            if cfg.wake_use_openwakeword:
                _wake_scan = (
                    f"openWakeWord ({','.join(cfg.oww_model_names)})"
                    + (" + Whisper phrase confirm" if cfg.wake_oww_whisper_confirm else "")
                )
            elif cfg.wake_streaming:
                _wake_scan = (
                    "speech-triggered mic + Whisper (Alexa-style gate)"
                )
            else:
                _wake_scan = (
                    f"short mic clips every ~{cfg.wake_interval_seconds:.0f}s"
                )
            logger.info(
                "Wake hands-free: say %r aloud (%s), then you get one hands-free "
                "capture; or hold %s for push-to-talk.",
                cfg.wake_phrase,
                _wake_scan,
                _hotkey_label(cfg.hotkey),
            )
            if not cfg.listen_chime_wake:
                logger.info(
                    "Tip: set MANGO_LISTEN_CHIME_WAKE=1 for a short listen earcon when wake "
                    "hands-free starts.",
                )
        else:
            logger.info(
                "Wake word listener off (set MANGO_WAKEWORD=1 to enable). Push-to-talk only with %s.",
                _hotkey_label(cfg.hotkey),
            )

        while True:
            try:
                if stop_event is not None and stop_event.is_set():
                    logger.info("Shutdown requested — exiting voice loop.")
                    break
                if cfg.always_listen:
                    if keyboard.is_pressed(cfg.hotkey):
                        wake_event.clear()
                        _drain_utterance_queue(vad_queue)
                        _set_assistant_state("listening")
                        release_mixer_before_mic()
                        if cfg.listen_chime_ptt:
                            play_listen_chime()
                        with duck_spotify_session():
                            audio = record_while_held(
                                cfg.hotkey,
                                cfg.sample_rate,
                                wait_for_key=False,
                            )
                            samples = int(cfg.sample_rate * cfg.min_record_seconds)
                            if audio.size >= samples:
                                _handoff_barge_capture(_run_turn(audio, "ptt"), "ptt")
                        continue
                    try:
                        vad_audio = vad_queue.get_nowait()
                    except queue.Empty:
                        vad_audio = None
                    if vad_audio is not None:
                        wake_event.clear()
                        _set_assistant_state("listening")
                        _handoff_barge_capture(_run_turn(vad_audio, "vad"), "vad")
                        continue

                if wake_event.is_set():
                    wake_suppress.set()
                    _drain_utterance_queue(vad_queue)
                    wake_event.clear()
                    _set_assistant_state("listening")
                    logger.info(
                        "Wake phrase heard — hands-free listen (up to %.0fs, silence-stop enabled).",
                        cfg.hands_free_seconds,
                    )
                    with duck_spotify_session():
                        if cfg.wake_ack_text:
                            _speak_mango_reply(
                                cfg,
                                tts,
                                cfg.wake_ack_text,
                                interrupt_check=None,
                                streaming=False,
                                hud_level_out=hud_level,
                                on_playback_start=lambda: _set_assistant_state("speaking"),
                            )
                            _set_assistant_state("listening")
                        release_mixer_before_mic()
                        if cfg.listen_chime_wake:
                            play_listen_chime()
                        audio_hf = record_hands_free(
                            cfg.sample_rate,
                            cfg.hands_free_seconds,
                            silence_ms=cfg.hands_free_silence_ms,
                            silence_rms=cfg.hands_free_silence_rms,
                        )
                        outcome = _handoff_barge_capture(_run_turn(audio_hf, "wake"), "wake")
                        reply = outcome.reply
                        should_follow = _needs_immediate_confirmation_followup(reply)
                        if not should_follow and hasattr(registry, "has_pending_confirmation"):
                            try:
                                should_follow = bool(registry.has_pending_confirmation())
                            except Exception:
                                logger.debug("Pending-confirmation probe failed", exc_info=True)
                        if should_follow:
                            logger.info(
                                "Confirmation requested — opening immediate follow-up capture "
                                "so user can approve without wake word."
                            )
                            _set_assistant_state("listening")
                            release_mixer_before_mic()
                            if cfg.listen_chime_wake:
                                play_listen_chime()
                            followup_audio = record_hands_free(
                                cfg.sample_rate,
                                min(6.0, max(2.0, cfg.hands_free_seconds)),
                                silence_ms=max(500, int(cfg.hands_free_silence_ms * 0.8)),
                                silence_rms=cfg.hands_free_silence_rms,
                            )
                            _handoff_barge_capture(_run_turn(followup_audio, "wake_confirm"), "wake_confirm")
                    continue

                if cfg.always_listen:
                    _set_assistant_state("listening")
                    time.sleep(idle_sleep_s)
                    continue

                if cfg.wake_word_enabled:
                    if keyboard.is_pressed(cfg.hotkey):
                        wake_event.clear()
                        _set_assistant_state("listening")
                        release_mixer_before_mic()
                        if cfg.listen_chime_ptt:
                            play_listen_chime()
                        with duck_spotify_session():
                            audio = record_while_held(
                                cfg.hotkey,
                                cfg.sample_rate,
                                wait_for_key=False,
                            )
                            samples = int(cfg.sample_rate * cfg.min_record_seconds)
                            if audio.size >= samples:
                                _handoff_barge_capture(_run_turn(audio, "ptt"), "ptt")
                    else:
                        _set_assistant_state("listening")
                        time.sleep(idle_sleep_s)
                    continue

                _set_assistant_state("listening")
                logger.info(
                    "Listening — hold %s while you speak, then release…",
                    _hotkey_label(cfg.hotkey),
                )
                release_mixer_before_mic()
                if cfg.listen_chime_ptt:
                    play_listen_chime()
                with duck_spotify_session():
                    audio = record_while_held(cfg.hotkey, cfg.sample_rate)
                    _handoff_barge_capture(_run_turn(audio, "ptt"), "ptt")
            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt — goodbye.")
                print("\nGoodbye.")
                break
            except AuthenticationError:
                if cfg.llm_provider != "groq":
                    logger.exception(
                        "Unexpected Groq AuthenticationError while llm_provider=%s",
                        cfg.llm_provider,
                    )
                    continue
                logger.error(
                    "Groq returned 401 Invalid API Key. Create or rotate a key at "
                    "https://console.groq.com/keys and set GROQ_API_KEY in your .env, "
                    "then restart Mango.",
                )
                print(
                    "\nGROQ_API_KEY is invalid or revoked. Update .env and run Mango again.\n",
                    file=sys.stderr,
                )
                sys.exit(1)
            except RateLimitError as exc:
                if cfg.llm_provider != "groq":
                    logger.exception(
                        "Unexpected Groq RateLimitError while llm_provider=%s",
                        cfg.llm_provider,
                    )
                    continue
                logger.warning("Groq rate limit (429): %s", exc)
                if cfg.speak_on_error:
                    try:
                        _speak_mango_reply(
                            cfg,
                            tts,
                            "Groq rate limit reached. Please wait a few seconds and try again.",
                            interrupt_check=None,
                            streaming=False,
                            hud_level_out=None,
                        )
                    except Exception:
                        logger.debug("Error TTS skipped", exc_info=True)
                continue
            except (APIConnectionError, APITimeoutError) as exc:
                if cfg.llm_provider != "groq":
                    logger.exception(
                        "Unexpected Groq connection or timeout while llm_provider=%s",
                        cfg.llm_provider,
                    )
                    continue
                logger.warning("Groq connection or timeout: %s", exc)
                if cfg.speak_on_error:
                    try:
                        _speak_mango_reply(
                            cfg,
                            tts,
                            "I cannot reach Groq right now. Check your network connection and try again.",
                            interrupt_check=None,
                            streaming=False,
                            hud_level_out=None,
                        )
                    except Exception:
                        logger.debug("Error TTS skipped", exc_info=True)
                continue
            except BadRequestError as exc:
                if cfg.llm_provider != "groq":
                    logger.exception(
                        "Unexpected Groq BadRequestError while llm_provider=%s",
                        cfg.llm_provider,
                    )
                    continue
                logger.error("Groq rejected the request (400): %s", exc)
                if cfg.speak_on_error:
                    err_text = str(exc).casefold()
                    if "tool_use_failed" in err_text or "failed to call a function" in err_text:
                        spoken = (
                            "I stumbled picking a tool — ask again in plain words and I'll handle it."
                        )
                    else:
                        spoken = (
                            "Groq rejected that request. Try a shorter message or ask again in a moment."
                        )
                    try:
                        _speak_mango_reply(
                            cfg,
                            tts,
                            spoken,
                            interrupt_check=None,
                            streaming=False,
                            hud_level_out=None,
                        )
                    except Exception:
                        logger.debug("Error TTS skipped", exc_info=True)
                continue
            except InternalServerError as exc:
                if cfg.llm_provider != "groq":
                    logger.exception(
                        "Unexpected Groq InternalServerError while llm_provider=%s",
                        cfg.llm_provider,
                    )
                    continue
                logger.error("Groq server error (5xx): %s", exc)
                if cfg.speak_on_error:
                    try:
                        _speak_mango_reply(
                            cfg,
                            tts,
                            "Groq returned a temporary server error. Try again in a moment.",
                            interrupt_check=None,
                            streaming=False,
                            hud_level_out=None,
                        )
                    except Exception:
                        logger.debug("Error TTS skipped", exc_info=True)
                continue
            except Exception:
                logger.exception("Unhandled error in main loop — continuing.")
                if cfg.speak_on_error:
                    try:
                        _speak_mango_reply(
                            cfg,
                            tts,
                            "Something went wrong. Please try again.",
                            interrupt_check=None,
                            streaming=False,
                            hud_level_out=None,
                        )
                    except Exception:
                        logger.debug("Error TTS skipped", exc_info=True)
    finally:
        stop_reminders.set()
        stop_wake.set()
        stop_vad.set()
        if vad_thread is not None:
            vad_thread.join(timeout=3.0)
        if wake_thread is not None:
            wake_thread.join(timeout=2.5)
        try:
            save_session_snapshot(
                messages,
                cfg.session_log_dir,
                enabled=cfg.session_log_enabled,
            )
        except Exception:
            logger.debug("Session snapshot skipped", exc_info=True)
        try:
            _persist_memory()
        except Exception:
            logger.debug("Persistent memory flush skipped", exc_info=True)
        if hud:
            hud.close()


def main() -> None:
    ptt_only = "--ptt-only" in sys.argv
    if os.getenv("MANGO_PTT_ONLY", "").strip().lower() in ("1", "true", "yes", "on"):
        ptt_only = True
    wake_oww_only = "--wake-oww-only" in sys.argv
    wake_oww_score_only = "--wake-oww-score-only" in sys.argv
    if ptt_only:
        sys.argv = [a for a in sys.argv if a != "--ptt-only"]
    if wake_oww_only or wake_oww_score_only:
        sys.argv = [
            a
            for a in sys.argv
            if a not in ("--wake-oww-only", "--wake-oww-score-only")
        ]
    setup_logging()
    root_log = logging.getLogger()
    logger.info(
        "Mango logging active effective_level=%s env MANGO_LOG_LEVEL=%r (set DEBUG for verbose traces)",
        logging.getLevelName(root_log.getEffectiveLevel()),
        os.getenv("MANGO_LOG_LEVEL", "INFO"),
    )
    if wake_oww_only or wake_oww_score_only:
        mode = "score-only (OWW)" if wake_oww_score_only else "hybrid (OWW + Whisper phrase)"
        logger.info(
            "Wake test CLI: %s — applied after Config.load(); set MANGO_OWW_MODELS or use "
            "scripts/run_mango_oww_test.ps1 with your .onnx path.",
            mode,
        )
    run_voice_session(
        stop_event=None,
        ptt_only=ptt_only,
        wake_oww_cli=wake_oww_only or wake_oww_score_only,
        wake_oww_cli_score_only=wake_oww_score_only,
    )
