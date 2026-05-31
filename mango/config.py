"""Configuration loaded from environment and sensible defaults."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from mango.config_sections import (
    AudioConfig,
    LlmConfig,
    ToolPolicyConfig,
    TtsConfig,
    WakeConfig,
)
from mango.timeouts import HTTP_LONG_S, HTTP_MEDIUM_S, HTTP_SHORT_S

logger = logging.getLogger(__name__)

# Repo root: .../mango/config.py -> parent of the `mango` package
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_timeout_s: float = 90.0
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_s: float = 120.0
    max_conversation_messages: int = 36
    memory_tier: str = "session"
    # Opt-in: JSON memory survives restarts (plaintext on disk — see MANGO_PERSISTENT_MEMORY).
    persistent_memory: bool = False
    memory_dir: Path = field(default_factory=lambda: Path.home() / ".mango" / "memory")
    # When persistent_memory: floor for max_conversation_messages and rolling save depth (clamped in load()).
    memory_max_messages: int = 120
    # If rolling.json is missing, merge last N dated snapshots from memory_dir/days/*.json
    memory_merge_days: int = 14
    # Also write memory_dir/days/YYYY-MM-DD.json on each save (recovery + multi-day merge).
    memory_daily_snapshots: bool = True
    whisper_model: str = "base.en"
    hotkey: str = "alt+w"
    sample_rate: int = 16_000
    edge_voice: str = "en-US-GuyNeural"
    edge_rate: str = "+0%"
    edge_pitch: str = "+0Hz"
    edge_volume: str = "+0%"
    search_max_results: int = 25
    interruption_profile: str = "normal"
    http_timeout_short_s: float = HTTP_SHORT_S
    http_timeout_medium_s: float = HTTP_MEDIUM_S
    http_timeout_long_s: float = HTTP_LONG_S
    min_record_seconds: float = 0.25
    # Cap LLM ↔ tool turns per user utterance (prevents infinite tool loops).
    max_llm_tool_rounds: int = 6
    # Hands-free (wake): end capture after this many ms of low-RMS audio once speech was detected.
    hands_free_silence_ms: int = 1000
    hands_free_silence_rms: float = 0.018
    # Persist session transcripts on exit (plaintext — opt in via MANGO_SESSION_LOG=1).
    session_log_enabled: bool = False
    # Silero VAD often drops quiet headset audio entirely; leave off unless you enable via env.
    whisper_vad_filter: bool = False
    # Whisper "silent segment" gate: higher no_speech_threshold = harder to discard as non-speech.
    whisper_no_speech_threshold: float = 0.82
    whisper_log_prob_threshold: float = -1.5
    # Software gain before Whisper (0 disables). Helps quiet headsets.
    audio_normalize_target_peak: float = 0.5
    audio_normalize_max_gain: float = 120.0
    search_roots: tuple[Path, ...] = field(default_factory=tuple)
    # TTS: edge (Edge TTS, free) | elevenlabs (API key)
    tts_provider: str = "edge"
    elevenlabs_api_key: str | None = None
    elevenlabs_api_base: str = "https://api.elevenlabs.io"
    elevenlabs_voice_id: str = ""
    elevenlabs_tts_model: str = "eleven_multilingual_v2"
    elevenlabs_sts_model: str = "eleven_multilingual_sts_v2"
    # Run speech-to-speech on top of TTS output (same ElevenLabs voice; extra latency + cost).
    elevenlabs_sts_after_tts: bool = False
    # Short preset suffix on the system prompt (see mango/presets.py).
    preset: str = "default"
    # Markdown snippets: ~/.mango/skills/*.md unless MANGO_SKILLS_DIR is set.
    skills_dir: Path = field(default_factory=lambda: Path.home() / ".mango" / "skills")
    skills_max_chars: int = 3500
    max_tool_output_chars: int = 10_000
    # Keep spoken replies reasonably bounded while allowing detailed answers.
    max_spoken_reply_chars: int = 1200
    wake_word_enabled: bool = False
    wake_interval_seconds: float = 4.0
    wake_clip_seconds: float = 1.8
    wake_rms_threshold: float = 0.0
    # Skip Whisper on wake clips quieter than this (float32 peak abs); stops silence hallucinations.
    wake_whisper_min_peak: float = 0.004
    # Skip Whisper when sample std is below this (flat / steady noise); reduces junk transcriptions.
    wake_whisper_min_std: float = 0.012
    wake_phrase: str = "mango"
    wake_ack_text: str = ""
    # Pause wake sampling during a turn and this many seconds after TTS (stops mic picking up playback).
    wake_post_tts_seconds: float = 0.45
    # After a turn that never plays TTS (rejected prefix, empty STT, too-short clip): unsuppress delay (seconds).
    suppress_after_skipped_turn_seconds: float = 0.04
    # Phrase must appear within this many characters (wake is usually "Mango, …" not a long ramble).
    wake_phrase_max_char_offset: int = 32
    # When wake is on and MANGO_WAKE_STREAMING is unset: stream+VAD (Alexa-like). Set MANGO_WAKE_STREAMING=0 for old polled clips.
    wake_streaming: bool = False
    # Optional smaller Whisper for wake only (e.g. tiny.en). Empty = same model as MANGO_WHISPER_MODEL.
    wake_whisper_model: str = ""
    # Streaming wake: end utterance after this much silence (ms).
    wake_stream_silence_ms: float = 720.0
    # Streaming wake: hard cap on captured speech (seconds).
    wake_stream_max_seconds: float = 2.5
    # Streaming wake: minimum voiced duration before end-of-utterance can fire (ms).
    wake_stream_min_speech_ms: float = 150.0
    # RMS gates inside streaming-wake capture (quiet room / distant mic): start-of-speech vs sustain.
    wake_stream_speech_hi_floor: float = 0.009
    wake_stream_speech_hi_mult: float = 2.75
    wake_stream_speech_lo_floor: float = 0.006
    wake_stream_speech_lo_mult: float = 1.65
    # Wake backend: auto (prefer openWakeWord when models resolve) | whisper | openwakeword | hybrid
    wake_engine: str = "auto"
    # Resolved OWW model names or .onnx/.tflite paths (from MANGO_OWW_MODELS or built-in phrase map).
    oww_model_names: tuple[str, ...] = ()
    oww_threshold: float = 0.5
    # Silero VAD inside openWakeWord (0 = off). Try 0.45–0.55 to suppress TV/room false triggers.
    oww_vad_threshold: float = 0.0
    oww_inference_framework: str = "onnx"
    # True when openWakeWord handles wake (streaming Whisper wake paths are skipped).
    wake_use_openwakeword: bool = False
    # When True, OWW score must pass then Whisper must match MANGO_WAKE_PHRASE (auto/hybrid).
    wake_oww_whisper_confirm: bool = True
    # Earcon before mic open when MANGO_LISTEN_CHIME_* is enabled.
    listen_chime_wake: bool = False
    listen_chime_ptt: bool = False
    # Background thread captures speech after silence (energy VAD).
    always_listen: bool = False
    # When always_listen + True: VAD path ignores transcripts that do not start with the prefix (no LLM/TTS).
    always_listen_require_transcript_prefix: bool = False
    # Required opening phrases for VAD when ``always_listen_require_transcript_prefix`` (comma-separated in env).
    always_listen_transcript_prefixes: tuple[str, ...] = ()
    vad_silence_ms: float = 900.0
    vad_min_speech_ms: float = 400.0
    vad_max_seconds: float = 22.0
    vad_min_peak: float = 0.0025
    # Energy VAD: max seconds to wait for speech onset before yielding the mic (lower = re-arm sooner).
    vad_max_wait_seconds: float = 3.5
    # Sleep in the VAD thread when idle (no clip / between clips); lower = poll the mic sooner.
    vad_thread_idle_sleep_seconds: float = 0.022
    hands_free_seconds: float = 10.0
    strict_tools: bool = False
    # Per-tool spoken confirmations. Defaults: PowerShell ON, phone OFF, Xbox turn_off OFF.
    require_powershell_confirmation: bool = True
    require_phone_confirmation: bool = False
    require_xbox_turn_off_confirmation: bool = False
    # Legacy aggregate flag retained for compatibility/logging (true when any per-tool confirmation is on).
    require_tool_confirmation: bool = True
    # When True, read_clipboard only runs if user text matches clipboard-intent hints.
    clipboard_require_intent: bool = False
    # When True, saved_contact_phone only runs for explicit contact/number phrasing.
    contact_info_require_intent: bool = True
    # When False, Discord music/ping/join host hints are enforced (stricter).
    discord_relax_intent_gates: bool = True
    quiet_hours: tuple[int, int] | None = None
    quiet_timezone: str = "America/Chicago"
    streaming_tts: bool = True
    speak_on_error: bool = True
    # headset = pygame/local audio | discord = POST to voice bridge only (requires bridge running + in call).
    tts_playback: str = "headset"
    # sir | maam | none | "" (empty = prefer sir, never ma'am unless MANGO_HONORIFIC overrides).
    honorific: str = ""
    # Human-facing name in prompts and tools (MANGO_OWNER_NAME, else OS username).
    owner_display_name: str = "you"
    # phone_call contact keys + MANGO_CONTACT_{SLUG}_PHONE / _DISPLAY env vars.
    phone_contact_slugs: tuple[str, ...] = ("ariana", "brooke", "dylan")
    session_log_dir: Path = field(default_factory=lambda: Path.home() / ".mango" / "logs")
    discord_bridge_poll_interval_s: float = 1.5
    discord_control_timeout_s: float = 60.0
    # Typed sections for incremental architecture split (flat fields retained for compatibility).
    llm: LlmConfig = field(default_factory=LlmConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    wake: WakeConfig = field(default_factory=WakeConfig)
    tool_policy: ToolPolicyConfig = field(default_factory=ToolPolicyConfig)
    tts: TtsConfig = field(default_factory=TtsConfig)

    # Comma-separated tool names omitted from the LLM schema (see MANGO_DISABLED_TOOLS).
    disabled_tools: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def load(cls) -> Config:
        from mango.config_build import build_config_from_env
        from mango.config_dotenv import load_project_dotenv

        load_project_dotenv(_PROJECT_ROOT)
        return build_config_from_env()


def apply_cli_wake_oww_test(cfg: Config, *, score_only: bool = False) -> None:
    """After ``Config.load()``: force openWakeWord wake test so CLI flags beat ``.env`` (dotenv override=True).

    Enables wake, turns off always-listen, sets ``hybrid`` (default) or ``openwakeword`` (score_only),
    and recomputes ``wake_use_openwakeword`` / ``wake_oww_whisper_confirm`` like normal parsing.
    """
    from mango.wake.oww_wake import oww_import_ok

    cfg.wake_word_enabled = True
    cfg.always_listen = False
    cfg.wake_engine = "openwakeword" if score_only else "hybrid"

    oww_ok = oww_import_ok()
    resolved_oww = list(cfg.oww_model_names)
    wake_engine = cfg.wake_engine

    cfg.wake_use_openwakeword = False
    cfg.wake_oww_whisper_confirm = True
    if wake_engine == "whisper":
        pass
    elif resolved_oww and oww_ok:
        if wake_engine in ("auto", "hybrid"):
            cfg.wake_use_openwakeword = True
            cfg.wake_oww_whisper_confirm = wake_engine != "openwakeword"
        elif wake_engine == "openwakeword":
            cfg.wake_use_openwakeword = True
            cfg.wake_oww_whisper_confirm = False
    else:
        if not resolved_oww:
            logger.warning(
                "CLI wake test: no OWW models resolved — set MANGO_OWW_MODELS or pass .onnx path to "
                "scripts/run_mango_oww_test.ps1.",
            )
        if not oww_ok:
            logger.warning(
                "CLI wake test: openWakeWord not importable — pip install openwakeword onnxruntime",
            )

    logger.info(
        "CLI wake test override: wake_engine=%s wake_use_openwakeword=%s whisper_confirm=%s "
        "always_listen=%s oww_models=%s",
        cfg.wake_engine,
        cfg.wake_use_openwakeword,
        cfg.wake_oww_whisper_confirm,
        cfg.always_listen,
        ",".join(cfg.oww_model_names) or "(none)",
    )
