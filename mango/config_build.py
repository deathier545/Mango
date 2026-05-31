"""Build a `Config` instance from `os.environ` (after dotenv load)."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from mango.config import Config
from mango.config_env import (
    _float_env,
    _int_env,
    _ollama_base_url_from_env,
    _sanitize_api_key,
)
from mango.config_sections import (
    AudioConfig,
    LlmConfig,
    ToolPolicyConfig,
    TtsConfig,
    WakeConfig,
)
from mango.interruption_policy import resolve_profile
from mango.logging_setup import mask_secret
from mango.presets import known_presets
from mango.quiet_hours import parse_quiet_hours
from mango.timeouts import HTTP_LONG_S, HTTP_MEDIUM_S, HTTP_SHORT_S

logger = logging.getLogger(__name__)

_EDGE_RATE_RE = re.compile(r"^[+-]?\d+%$")
_EDGE_PITCH_RE = re.compile(r"^[+-]?\d+Hz$", re.IGNORECASE)
_EDGE_VOLUME_RE = re.compile(r"^[+-]?\d+%$")


def _edge_param_env(name: str, default: str, pattern: re.Pattern[str]) -> str:
    raw = os.getenv(name, default).strip() or default
    if pattern.fullmatch(raw):
        return raw
    logger.warning("Invalid %s=%r — using %s", name, raw, default)
    return default


def build_config_from_env() -> Config:
    provider_raw = (
        os.getenv("MANGO_LLM_PROVIDER", "groq").strip().lower() or "groq"
    )
    if provider_raw not in ("groq", "ollama"):
        logger.warning(
            "Unknown MANGO_LLM_PROVIDER=%r — falling back to groq",
            provider_raw,
        )
        provider_raw = "groq"

    key = _sanitize_api_key(os.getenv("GROQ_API_KEY", ""))
    if provider_raw == "groq":
        if not key:
            logger.error("GROQ_API_KEY missing after load_dotenv()")
            raise RuntimeError(
                "Missing GROQ_API_KEY. Copy .env.example to .env and set your key, "
                "or set MANGO_LLM_PROVIDER=ollama for local Ollama."
            )
        if not key.startswith("gsk_"):
            logger.warning(
                "GROQ_API_KEY should normally start with gsk_; "
                "check for typos or extra characters.",
            )
        logger.debug(
            "GROQ_API_KEY loaded len=%s masked=%s",
            len(key),
            mask_secret(key),
        )
    elif key and not key.startswith("gsk_"):
        logger.warning(
            "GROQ_API_KEY is set but does not start with gsk_; "
            "ignored while using ollama provider.",
        )

    ollama_base = _ollama_base_url_from_env()
    ollama_model = os.getenv("MANGO_OLLAMA_MODEL", "llama3.2").strip() or "llama3.2"

    max_msgs = _int_env("MANGO_MAX_CONVERSATION_MESSAGES", 36)
    memory_tier_raw = os.getenv("MANGO_MEMORY_TIER", "").strip().lower()
    if memory_tier_raw not in ("", "session", "day", "profile"):
        logger.warning("Unknown MANGO_MEMORY_TIER=%r — using session/profile defaults", memory_tier_raw)
        memory_tier_raw = ""
    persist_raw = os.getenv("MANGO_PERSISTENT_MEMORY", "").strip().lower()
    persistent_memory = persist_raw in ("1", "true", "yes", "on")
    mem_dir_raw = os.getenv("MANGO_MEMORY_DIR", "").strip()
    memory_dir = (
        Path(mem_dir_raw).expanduser().resolve()
        if mem_dir_raw
        else (Path.home() / ".mango" / "memory").resolve()
    )
    memory_max = _int_env("MANGO_MEMORY_MAX_MESSAGES", 120)
    memory_max = max(24, min(memory_max, 512))
    memory_merge_days = _int_env("MANGO_MEMORY_MERGE_DAYS", 14)
    memory_merge_days = max(0, min(memory_merge_days, 90))
    snap_raw = os.getenv("MANGO_MEMORY_DAILY_SNAPSHOTS", "1").strip().lower()
    memory_daily_snapshots = snap_raw not in ("0", "false", "no", "off")

    memory_tier = "profile" if persistent_memory else "session"
    if memory_tier_raw:
        if memory_tier_raw == "session":
            memory_tier = "session"
            persistent_memory = False
            memory_merge_days = 0
            memory_daily_snapshots = False
        elif memory_tier_raw == "day":
            memory_tier = "day"
            persistent_memory = True
            memory_merge_days = 1
            memory_daily_snapshots = True
        elif memory_tier_raw == "profile":
            memory_tier = "profile"
            persistent_memory = True

    if persistent_memory:
        max_msgs = max(8, min(max(max_msgs, memory_max), 512))
    else:
        max_msgs = max(8, min(max_msgs, 128))

    preset = os.getenv("MANGO_PRESET", "default").strip().lower() or "default"
    if preset not in known_presets():
        logger.warning("Unknown MANGO_PRESET=%r — using default", preset)
        preset = "default"

    skills_dir_raw = os.getenv("MANGO_SKILLS_DIR", "").strip()
    if skills_dir_raw:
        skills_dir = Path(skills_dir_raw).expanduser().resolve()
    else:
        skills_dir = (Path.home() / ".mango" / "skills").resolve()

    skills_max = _int_env("MANGO_SKILLS_MAX_CHARS", 3500)
    skills_max = max(500, min(skills_max, 12_000))

    max_tool_out = _int_env("MANGO_MAX_TOOL_OUTPUT_CHARS", 10_000)
    max_tool_out = max(2000, min(max_tool_out, 100_000))
    max_spoken_chars = _int_env("MANGO_MAX_SPOKEN_REPLY_CHARS", 1200)
    max_spoken_chars = max(80, min(max_spoken_chars, 1200))

    # Wake listening: OFF by default. Set MANGO_WAKEWORD=1 (or true/yes/on) to enable hands-free phrase.
    _wake_raw = os.getenv("MANGO_WAKEWORD", "").strip().lower()
    wake_on = _wake_raw in ("1", "true", "yes", "on")
    wake_interval = _float_env("MANGO_WAKE_INTERVAL_SECONDS", 4.0)
    wake_interval = max(1.0, min(wake_interval, 30.0))
    wake_clip = _float_env("MANGO_WAKE_CLIP_SECONDS", 1.8)
    wake_clip = max(0.6, min(wake_clip, 3.0))
    # 0 = do not skip clips by RMS (optional extra gate). Example: 0.008
    wake_rms = _float_env("MANGO_WAKE_RMS_THRESHOLD", 0.0)
    wake_rms = max(0.0, min(wake_rms, 0.5))
    wake_wmin = _float_env("MANGO_WAKE_WHISPER_MIN_PEAK", 0.004)
    wake_wmin = max(0.0005, min(wake_wmin, 0.08))
    wake_wstd = _float_env("MANGO_WAKE_WHISPER_MIN_STD", 0.012)
    wake_wstd = max(0.002, min(wake_wstd, 0.08))
    wake_phrase = os.getenv("MANGO_WAKE_PHRASE", "mango").strip() or "mango"
    # Built-in OWW phrase map uses the first comma-separated entry only.
    wake_oww_phrase = wake_phrase.split(",")[0].strip() or "mango"
    wake_ack_text = os.getenv("MANGO_WAKE_ACK_TEXT", "").strip()
    wake_post_tts = _float_env("MANGO_WAKE_POST_TTS_SECONDS", 0.45)
    wake_post_tts = max(0.25, min(wake_post_tts, 20.0))
    suppress_after_skipped = _float_env("MANGO_SUPPRESS_AFTER_SKIPPED_TURN_SECONDS", 0.04)
    suppress_after_skipped = max(0.0, min(suppress_after_skipped, 2.0))
    wake_phrase_off = _int_env("MANGO_WAKE_PHRASE_MAX_OFFSET", 32)
    wake_phrase_off = max(8, min(wake_phrase_off, 120))
    _wake_stream_raw = os.getenv("MANGO_WAKE_STREAMING", "").strip().lower()
    if _wake_stream_raw in ("0", "false", "no", "off"):
        wake_streaming = False
    elif _wake_stream_raw in ("1", "true", "yes", "on"):
        wake_streaming = True
    else:
        wake_streaming = wake_on
    wake_whisper_model = os.getenv("MANGO_WAKE_WHISPER_MODEL", "").strip()
    wake_stream_silence_ms = _float_env("MANGO_WAKE_STREAM_SILENCE_MS", 720.0)
    wake_stream_silence_ms = max(300.0, min(wake_stream_silence_ms, 2000.0))
    wake_stream_max_seconds = _float_env("MANGO_WAKE_STREAM_MAX_SECONDS", 2.5)
    wake_stream_max_seconds = max(1.2, min(wake_stream_max_seconds, 5.0))
    wake_stream_min_speech_ms = _float_env("MANGO_WAKE_STREAM_MIN_SPEECH_MS", 150.0)
    wake_stream_min_speech_ms = max(80.0, min(wake_stream_min_speech_ms, 500.0))
    wake_hi_floor = _float_env("MANGO_WAKE_STREAM_SPEECH_HI_FLOOR", 0.009)
    wake_hi_floor = max(0.0025, min(wake_hi_floor, 0.025))
    wake_hi_mult = _float_env("MANGO_WAKE_STREAM_SPEECH_HI_MULT", 2.75)
    wake_hi_mult = max(1.35, min(wake_hi_mult, 5.0))
    wake_lo_floor = _float_env("MANGO_WAKE_STREAM_SPEECH_LO_FLOOR", 0.006)
    wake_lo_floor = max(0.002, min(wake_lo_floor, 0.02))
    wake_lo_mult = _float_env("MANGO_WAKE_STREAM_SPEECH_LO_MULT", 1.65)
    wake_lo_mult = max(1.1, min(wake_lo_mult, 3.0))

    from mango.wake.oww_wake import oww_import_ok, resolve_oww_model_names_for_wake

    oww_models_env = os.getenv("MANGO_OWW_MODELS", "").strip()
    oww_explicit = [x.strip() for x in oww_models_env.split(",") if x.strip()]
    resolved_oww = resolve_oww_model_names_for_wake(oww_explicit, wake_oww_phrase)
    wake_engine = os.getenv("MANGO_WAKE_ENGINE", "auto").strip().lower() or "auto"
    if wake_engine not in ("auto", "whisper", "openwakeword", "hybrid"):
        logger.warning("Unknown MANGO_WAKE_ENGINE=%r — using auto", wake_engine)
        wake_engine = "auto"
    oww_thr = _float_env("MANGO_OWW_THRESHOLD", 0.5)
    oww_thr = max(0.15, min(oww_thr, 0.95))
    oww_vad = _float_env("MANGO_OWW_VAD_THRESHOLD", 0.0)
    oww_vad = max(0.0, min(oww_vad, 0.99))
    oww_fw = os.getenv("MANGO_OWW_INFERENCE", "onnx").strip().lower() or "onnx"
    if oww_fw not in ("onnx", "tflite"):
        oww_fw = "onnx"

    oww_ok = oww_import_ok()
    wake_use_openwakeword = False
    wake_oww_whisper_confirm = True
    if wake_engine == "whisper":
        pass
    elif wake_on and resolved_oww and oww_ok:
        if wake_engine in ("auto", "hybrid"):
            wake_use_openwakeword = True
            wake_oww_whisper_confirm = wake_engine != "openwakeword"
        elif wake_engine == "openwakeword":
            wake_use_openwakeword = True
            wake_oww_whisper_confirm = False
    elif wake_on and wake_engine in ("openwakeword", "hybrid") and not resolved_oww:
        logger.warning(
            "MANGO_WAKE_ENGINE=%s needs OWW models; set MANGO_OWW_MODELS or a built-in "
            "wake phrase (e.g. hey mango, alexa). Falling back to Whisper wake.",
            wake_engine,
        )
    elif wake_on and wake_engine in ("openwakeword", "hybrid") and not oww_ok:
        logger.warning(
            "openWakeWord not installed (pip install openwakeword onnxruntime). "
            "Falling back to Whisper wake.",
        )

    listen_chime_wake = os.getenv("MANGO_LISTEN_CHIME_WAKE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    listen_chime_ptt = os.getenv("MANGO_LISTEN_CHIME_PTT", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    always_listen = os.getenv("MANGO_ALWAYS_LISTEN", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    always_listen_req_prefix = os.getenv(
        "MANGO_ALWAYS_LISTEN_REQUIRE_PREFIX", ""
    ).strip().lower() in ("1", "true", "yes", "on")
    always_listen_prefix_raw = os.getenv("MANGO_ALWAYS_LISTEN_PREFIX", "").strip()

    from mango.always_listen_gate import DEFAULT_PREFIX_ONLY_MISHEARS

    def _csv_prefixes(s: str) -> tuple[str, ...]:
        parts = [x.strip() for x in (s or "").split(",")]
        return tuple(dict.fromkeys(p for p in parts if p))

    # Common Whisper confusions + bare wake word when using PREFIX_ONLY (merged with any explicit CSV).
    _default_prefix_only_prefixes = DEFAULT_PREFIX_ONLY_MISHEARS

    always_listen_prefix_only = os.getenv(
        "MANGO_ALWAYS_LISTEN_PREFIX_ONLY", ""
    ).strip().lower() in ("1", "true", "yes", "on")
    if always_listen_prefix_only:
        always_listen = True
        always_listen_req_prefix = True
        wake_on = False
        wake_use_openwakeword = False
        wake_oww_whisper_confirm = True
        if _wake_stream_raw not in ("0", "false", "no", "off", "1", "true", "yes", "on"):
            wake_streaming = False
        logger.info(
            "MANGO_ALWAYS_LISTEN_PREFIX_ONLY: always-listen + transcript prefix gate on; "
            "openWakeWord/streaming wake disabled.",
        )

    if always_listen_prefix_raw and always_listen_prefix_only:
        explicit = _csv_prefixes(always_listen_prefix_raw)
        always_listen_transcript_prefixes = tuple(
            dict.fromkeys(explicit + _default_prefix_only_prefixes)
        )
    elif always_listen_prefix_raw:
        always_listen_transcript_prefixes = _csv_prefixes(always_listen_prefix_raw)
    elif always_listen_prefix_only:
        always_listen_transcript_prefixes = _default_prefix_only_prefixes
    elif always_listen_req_prefix:
        wp = (wake_phrase or "mango").strip()
        always_listen_transcript_prefixes = _csv_prefixes(wp) if wp else ("mango",)
    else:
        always_listen_transcript_prefixes = ()

    if always_listen_req_prefix and not always_listen_transcript_prefixes:
        wp = (wake_phrase or "mango").strip()
        always_listen_transcript_prefixes = _csv_prefixes(wp) if wp else ("mango",)

    vad_silence_ms = _float_env("MANGO_VAD_SILENCE_MS", 900.0)
    vad_silence_ms = max(300.0, min(vad_silence_ms, 3500.0))
    vad_min_speech_ms = _float_env("MANGO_VAD_MIN_SPEECH_MS", 400.0)
    vad_min_speech_ms = max(200.0, min(vad_min_speech_ms, 2500.0))
    vad_max_seconds = _float_env("MANGO_VAD_MAX_SECONDS", 22.0)
    vad_max_seconds = max(5.0, min(vad_max_seconds, 45.0))
    vad_min_peak = _float_env("MANGO_VAD_MIN_PEAK", 0.0025)
    vad_min_peak = max(0.0005, min(vad_min_peak, 0.08))
    vad_max_wait = _float_env("MANGO_VAD_MAX_WAIT_SECONDS", 3.5)
    vad_max_wait = max(1.0, min(vad_max_wait, 10.0))
    vad_idle_sleep = _float_env("MANGO_VAD_THREAD_IDLE_SLEEP_SECONDS", 0.022)
    vad_idle_sleep = max(0.0, min(vad_idle_sleep, 0.5))
    hands_free = _float_env("MANGO_HANDS_FREE_SECONDS", 10.0)
    hands_free = max(2.0, min(hands_free, 45.0))

    strict_tools = os.getenv("MANGO_STRICT_TOOLS", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    _confirm_raw = os.getenv("MANGO_REQUIRE_TOOL_CONFIRMATION", "").strip().lower()
    legacy_confirm_set = _confirm_raw != ""
    legacy_require_tool_confirmation = _confirm_raw in ("1", "true", "yes", "on")
    _confirm_ps_raw = os.getenv("MANGO_REQUIRE_POWERSHELL_CONFIRMATION", "").strip().lower()
    _confirm_phone_raw = os.getenv("MANGO_REQUIRE_PHONE_CONFIRMATION", "").strip().lower()
    _confirm_xbox_raw = os.getenv("MANGO_REQUIRE_XBOX_TURNOFF_CONFIRMATION", "").strip().lower()

    def _parse_bool(raw: str) -> bool:
        return raw in ("1", "true", "yes", "on")

    if _confirm_ps_raw:
        require_powershell_confirmation = _parse_bool(_confirm_ps_raw)
    elif legacy_confirm_set:
        require_powershell_confirmation = legacy_require_tool_confirmation
    else:
        require_powershell_confirmation = True

    if _confirm_phone_raw:
        require_phone_confirmation = _parse_bool(_confirm_phone_raw)
    elif legacy_confirm_set:
        require_phone_confirmation = legacy_require_tool_confirmation
    else:
        require_phone_confirmation = False

    if _confirm_xbox_raw:
        require_xbox_turn_off_confirmation = _parse_bool(_confirm_xbox_raw)
    elif legacy_confirm_set:
        require_xbox_turn_off_confirmation = legacy_require_tool_confirmation
    else:
        require_xbox_turn_off_confirmation = False

    require_tool_confirmation = (
        require_powershell_confirmation
        or require_phone_confirmation
        or require_xbox_turn_off_confirmation
    )
    _cb_raw = os.getenv("MANGO_CLIPBOARD_REQUIRE_INTENT", "").strip().lower()
    clipboard_require_intent = _cb_raw in ("1", "true", "yes", "on")
    _contact_raw = os.getenv("MANGO_CONTACT_INFO_REQUIRE_INTENT", "1").strip().lower()
    contact_info_require_intent = _contact_raw not in ("0", "false", "no", "off")
    _dd_raw = os.getenv("MANGO_DISCORD_STRICT_INTENTS", "").strip().lower()
    discord_relax_intent_gates = _dd_raw not in ("1", "true", "yes", "on")
    _disabled_tools_raw = os.getenv("MANGO_DISABLED_TOOLS", "").strip()
    disabled_tools = frozenset(
        part.strip().lower().replace(" ", "_")
        for part in _disabled_tools_raw.split(",")
        if part.strip()
    )
    quiet_raw = os.getenv("MANGO_QUIET_HOURS", "").strip()
    quiet_tuple = parse_quiet_hours(quiet_raw)
    quiet_tz = (
        os.getenv("MANGO_QUIET_TIMEZONE", "").strip()
        or os.getenv("MANGO_INTRO_TIMEZONE", "America/Chicago").strip()
        or "America/Chicago"
    )

    stream_tts = os.getenv("MANGO_STREAMING_TTS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    speak_err = os.getenv("MANGO_SPEAK_ON_ERROR", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    tts_pb = os.getenv("MANGO_TTS_PLAYBACK", "headset").strip().lower() or "headset"
    if tts_pb in ("discord", "vc", "voice"):
        tts_playback = "discord"
    else:
        if tts_pb not in ("headset", "local", "speakers", ""):
            logger.warning("Unknown MANGO_TTS_PLAYBACK=%r — using headset", tts_pb)
        tts_playback = "headset"
    slog_raw = os.getenv("MANGO_SESSION_LOG_DIR", "").strip()
    session_log_dir = (
        Path(slog_raw).expanduser().resolve()
        if slog_raw
        else (Path.home() / ".mango" / "logs").resolve()
    )
    slog_en = os.getenv("MANGO_SESSION_LOG", "").strip().lower()
    session_log_enabled = slog_en in ("1", "true", "yes", "on")

    max_tool_rounds = _int_env("MANGO_MAX_LLM_TOOL_ROUNDS", 6)
    max_tool_rounds = max(2, min(max_tool_rounds, 24))
    hf_sil_ms = _int_env("MANGO_HANDS_FREE_SILENCE_MS", 1000)
    hf_sil_ms = max(400, min(hf_sil_ms, 5000))
    hf_sil_rms = _float_env("MANGO_HANDS_FREE_SILENCE_RMS", 0.018)
    hf_sil_rms = max(0.003, min(hf_sil_rms, 0.2))

    profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
    candidates = (
        profile / "Documents",
        profile / "Desktop",
        profile / "Downloads",
    )
    roots = tuple(p.resolve() for p in candidates if p.is_dir())
    logger.info(
        "Search roots (%d): %s",
        len(roots),
        ", ".join(str(p) for p in roots) or "(none)",
    )

    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    whisper_sz = os.getenv("MANGO_WHISPER_MODEL", "base.en").strip() or "base.en"
    hotkey = os.getenv("HOTKEY", "alt+w").strip().lower() or "alt+w"
    hotkey = hotkey.replace(" ", "")

    sample_rate = _int_env("MANGO_SAMPLE_RATE", 16_000)
    sample_rate = max(8_000, min(sample_rate, 48_000))
    edge_voice = os.getenv("MANGO_EDGE_VOICE", "en-US-GuyNeural").strip() or "en-US-GuyNeural"
    edge_rate = _edge_param_env("MANGO_EDGE_RATE", "+0%", _EDGE_RATE_RE)
    edge_pitch = _edge_param_env("MANGO_EDGE_PITCH", "+0Hz", _EDGE_PITCH_RE)
    edge_volume = _edge_param_env("MANGO_EDGE_VOLUME", "+0%", _EDGE_VOLUME_RE)
    search_max = _int_env("MANGO_SEARCH_MAX_RESULTS", 25)
    search_max = max(1, min(search_max, 100))
    interruption_profile_raw = os.getenv("MANGO_INTERRUPT_PROFILE", "normal").strip().lower() or "normal"
    interruption_profile = resolve_profile(interruption_profile_raw).name
    timeout_short = _float_env("MANGO_HTTP_TIMEOUT_SHORT_S", HTTP_SHORT_S)
    timeout_short = max(1.0, min(timeout_short, 60.0))
    timeout_medium = _float_env("MANGO_HTTP_TIMEOUT_MEDIUM_S", HTTP_MEDIUM_S)
    timeout_medium = max(2.0, min(timeout_medium, 90.0))
    timeout_long = _float_env("MANGO_HTTP_TIMEOUT_LONG_S", HTTP_LONG_S)
    timeout_long = max(3.0, min(timeout_long, 180.0))
    groq_timeout = _float_env("MANGO_GROQ_TIMEOUT_S", 90.0)
    groq_timeout = max(20.0, min(groq_timeout, 180.0))
    ollama_timeout = _float_env("MANGO_OLLAMA_TIMEOUT_S", 120.0)
    ollama_timeout = max(20.0, min(ollama_timeout, 240.0))
    discord_bridge_poll_interval = _float_env("MANGO_DISCORD_BRIDGE_POLL_INTERVAL_S", 1.5)
    discord_bridge_poll_interval = max(0.25, min(discord_bridge_poll_interval, 5.0))
    discord_control_timeout = _float_env("MANGO_DISCORD_CONTROL_TIMEOUT_S", 60.0)
    discord_control_timeout = max(5.0, min(discord_control_timeout, 120.0))
    min_record = _float_env("MANGO_MIN_RECORD_SECONDS", 0.25)
    min_record = max(0.05, min(min_record, 3.0))
    vad_env = os.getenv("MANGO_WHISPER_VAD_FILTER", "").strip().lower()
    whisper_vad = vad_env in ("1", "true", "yes", "on")
    ns_thr = _float_env("MANGO_WHISPER_NO_SPEECH_THRESHOLD", 0.82)
    lp_thr = _float_env("MANGO_WHISPER_LOG_PROB_THRESHOLD", -1.5)
    norm_peak = _float_env("MANGO_AUDIO_NORMALIZE_TARGET_PEAK", 0.5)
    norm_max_gain = _float_env("MANGO_AUDIO_NORMALIZE_MAX_GAIN", 120.0)

    tts_provider = os.getenv("MANGO_TTS_PROVIDER", "edge").strip().lower() or "edge"
    if tts_provider == "elevenlabs" and os.getenv(
        "MANGO_ELEVENLABS_QUOTA_EXCEEDED", ""
    ).strip().lower() in ("1", "true", "yes", "on"):
        logger.warning(
            "MANGO_ELEVENLABS_QUOTA_EXCEEDED is set — using Edge TTS (free) instead of ElevenLabs."
        )
        tts_provider = "edge"
    if tts_provider not in ("edge", "elevenlabs"):
        raise RuntimeError(
            f"MANGO_TTS_PROVIDER must be 'edge' or 'elevenlabs' (got {tts_provider!r})."
        )
    el_base = os.getenv("ELEVENLABS_API_BASE", "https://api.elevenlabs.io").strip()
    if not el_base:
        el_base = "https://api.elevenlabs.io"
    el_key_raw = _sanitize_api_key(os.getenv("ELEVENLABS_API_KEY", ""))
    el_key = el_key_raw or None
    el_voice = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    el_tts_model = (
        os.getenv("ELEVENLABS_TTS_MODEL", "eleven_multilingual_v2").strip()
        or "eleven_multilingual_v2"
    )
    el_sts_model = (
        os.getenv("ELEVENLABS_STS_MODEL", "eleven_multilingual_sts_v2").strip()
        or "eleven_multilingual_sts_v2"
    )
    el_sts_after = os.getenv("MANGO_ELEVENLABS_STS_AFTER_TTS", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    hon_raw = os.getenv("MANGO_HONORIFIC", "").strip().casefold()
    if hon_raw in ("sir",):
        honorific = "sir"
    elif hon_raw in ("maam", "ma'am", "madam"):
        honorific = "maam"
    elif hon_raw in ("none", "neutral", "off", "0"):
        honorific = "none"
    else:
        honorific = ""

    from mango.persona import owner_display_name_from_env, parse_phone_contact_slugs

    owner_display_name = owner_display_name_from_env()
    phone_contact_slugs = parse_phone_contact_slugs(os.getenv("MANGO_PHONE_CONTACTS", "").strip())

    if tts_provider == "elevenlabs":
        if not el_key:
            raise RuntimeError(
                "MANGO_TTS_PROVIDER=elevenlabs requires ELEVENLABS_API_KEY in .env."
            )
        if not el_voice:
            raise RuntimeError(
                "MANGO_TTS_PROVIDER=elevenlabs requires ELEVENLABS_VOICE_ID "
                "(ElevenLabs dashboard → Voices)."
            )

    cfg = Config(
        llm_provider=provider_raw,
        groq_api_key=key if provider_raw == "groq" else (key or ""),
        groq_model=model or "llama-3.3-70b-versatile",
        groq_timeout_s=groq_timeout,
        ollama_base_url=ollama_base,
        ollama_model=ollama_model,
        ollama_timeout_s=ollama_timeout,
        max_conversation_messages=max_msgs,
        memory_tier=memory_tier,
        whisper_model=whisper_sz,
        search_roots=roots,
        hotkey=hotkey,
        sample_rate=sample_rate,
        edge_voice=edge_voice,
        edge_rate=edge_rate,
        edge_pitch=edge_pitch,
        edge_volume=edge_volume,
        search_max_results=search_max,
        interruption_profile=interruption_profile,
        http_timeout_short_s=timeout_short,
        http_timeout_medium_s=timeout_medium,
        http_timeout_long_s=timeout_long,
        min_record_seconds=min_record,
        max_llm_tool_rounds=max_tool_rounds,
        hands_free_silence_ms=hf_sil_ms,
        hands_free_silence_rms=hf_sil_rms,
        session_log_enabled=session_log_enabled,
        whisper_vad_filter=whisper_vad,
        whisper_no_speech_threshold=ns_thr,
        whisper_log_prob_threshold=lp_thr,
        audio_normalize_target_peak=norm_peak,
        audio_normalize_max_gain=norm_max_gain,
        tts_provider=tts_provider,
        elevenlabs_api_key=el_key,
        elevenlabs_api_base=el_base,
        elevenlabs_voice_id=el_voice,
        elevenlabs_tts_model=el_tts_model,
        elevenlabs_sts_model=el_sts_model,
        elevenlabs_sts_after_tts=el_sts_after,
        preset=preset,
        skills_dir=skills_dir,
        skills_max_chars=skills_max,
        max_tool_output_chars=max_tool_out,
        max_spoken_reply_chars=max_spoken_chars,
        wake_word_enabled=wake_on,
        wake_interval_seconds=wake_interval,
        wake_clip_seconds=wake_clip,
        wake_rms_threshold=wake_rms,
        wake_whisper_min_peak=wake_wmin,
        wake_whisper_min_std=wake_wstd,
        wake_phrase=wake_phrase,
        wake_ack_text=wake_ack_text,
        wake_post_tts_seconds=wake_post_tts,
        suppress_after_skipped_turn_seconds=suppress_after_skipped,
        wake_phrase_max_char_offset=wake_phrase_off,
        wake_streaming=wake_streaming,
        wake_whisper_model=wake_whisper_model,
        wake_stream_silence_ms=wake_stream_silence_ms,
        wake_stream_max_seconds=wake_stream_max_seconds,
        wake_stream_min_speech_ms=wake_stream_min_speech_ms,
        wake_stream_speech_hi_floor=wake_hi_floor,
        wake_stream_speech_hi_mult=wake_hi_mult,
        wake_stream_speech_lo_floor=wake_lo_floor,
        wake_stream_speech_lo_mult=wake_lo_mult,
        wake_engine=wake_engine,
        oww_model_names=tuple(resolved_oww),
        oww_threshold=oww_thr,
        oww_vad_threshold=oww_vad,
        oww_inference_framework=oww_fw,
        wake_use_openwakeword=wake_use_openwakeword,
        wake_oww_whisper_confirm=wake_oww_whisper_confirm,
        listen_chime_wake=listen_chime_wake,
        listen_chime_ptt=listen_chime_ptt,
        always_listen=always_listen,
        always_listen_require_transcript_prefix=always_listen_req_prefix,
        always_listen_transcript_prefixes=always_listen_transcript_prefixes,
        vad_silence_ms=vad_silence_ms,
        vad_min_speech_ms=vad_min_speech_ms,
        vad_max_seconds=vad_max_seconds,
        vad_min_peak=vad_min_peak,
        vad_max_wait_seconds=vad_max_wait,
        vad_thread_idle_sleep_seconds=vad_idle_sleep,
        hands_free_seconds=hands_free,
        strict_tools=strict_tools,
        require_powershell_confirmation=require_powershell_confirmation,
        require_phone_confirmation=require_phone_confirmation,
        require_xbox_turn_off_confirmation=require_xbox_turn_off_confirmation,
        require_tool_confirmation=require_tool_confirmation,
        clipboard_require_intent=clipboard_require_intent,
        contact_info_require_intent=contact_info_require_intent,
        discord_relax_intent_gates=discord_relax_intent_gates,
        quiet_hours=quiet_tuple,
        quiet_timezone=quiet_tz,
        streaming_tts=stream_tts,
        speak_on_error=speak_err,
        tts_playback=tts_playback,
        session_log_dir=session_log_dir,
        discord_bridge_poll_interval_s=discord_bridge_poll_interval,
        discord_control_timeout_s=discord_control_timeout,
        honorific=honorific,
        owner_display_name=owner_display_name,
        phone_contact_slugs=phone_contact_slugs,
        persistent_memory=persistent_memory,
        memory_dir=memory_dir,
        memory_max_messages=memory_max,
        memory_merge_days=memory_merge_days,
        memory_daily_snapshots=memory_daily_snapshots,
        disabled_tools=disabled_tools,
        llm=LlmConfig(
            provider=provider_raw,
            groq_model=model or "llama-3.3-70b-versatile",
            ollama_base_url=ollama_base,
            ollama_model=ollama_model,
        ),
        audio=AudioConfig(
            sample_rate=sample_rate,
            whisper_model=whisper_sz,
            min_record_seconds=min_record,
            whisper_vad_filter=whisper_vad,
            whisper_no_speech_threshold=ns_thr,
            whisper_log_prob_threshold=lp_thr,
            normalize_target_peak=norm_peak,
            normalize_max_gain=norm_max_gain,
        ),
        wake=WakeConfig(
            enabled=wake_on,
            engine=wake_engine,
            phrase=wake_phrase,
            streaming=wake_streaming,
            wake_whisper_model=wake_whisper_model,
            oww_model_names=tuple(resolved_oww),
            oww_threshold=oww_thr,
            oww_vad_threshold=oww_vad,
            oww_inference_framework=oww_fw,
        ),
        tool_policy=ToolPolicyConfig(
            strict_tools=strict_tools,
            max_tool_output_chars=max_tool_out,
            max_llm_tool_rounds=max_tool_rounds,
            require_powershell_confirmation=require_powershell_confirmation,
            require_phone_confirmation=require_phone_confirmation,
            require_xbox_turn_off_confirmation=require_xbox_turn_off_confirmation,
            clipboard_require_intent=clipboard_require_intent,
            contact_info_require_intent=contact_info_require_intent,
            discord_relax_intent_gates=discord_relax_intent_gates,
        ),
        tts=TtsConfig(
            provider=tts_provider,
            playback=tts_playback,
            edge_voice=edge_voice,
            edge_rate=edge_rate,
            edge_pitch=edge_pitch,
            edge_volume=edge_volume,
            streaming_tts=stream_tts,
            speak_on_error=speak_err,
            elevenlabs_voice_id=el_voice,
            elevenlabs_tts_model=el_tts_model,
            elevenlabs_sts_model=el_sts_model,
            elevenlabs_sts_after_tts=el_sts_after,
        ),
    )
    if cfg.always_listen_require_transcript_prefix and not cfg.always_listen:
        logger.warning(
            "MANGO_ALWAYS_LISTEN_REQUIRE_PREFIX is on but MANGO_ALWAYS_LISTEN is off — "
            "the VAD transcript gate has no effect.",
        )
    if not cfg.session_log_enabled:
        logger.info("Session file logging disabled (MANGO_SESSION_LOG off).")
    logger.info(
        "Owner display name for prompts/tools: %r (set MANGO_OWNER_NAME to override). "
        "Phone contacts: %s",
        cfg.owner_display_name,
        ", ".join(cfg.phone_contact_slugs) or "(none)",
    )
    if legacy_confirm_set:
        logger.warning(
            "MANGO_REQUIRE_TOOL_CONFIRMATION is legacy; prefer per-tool flags: "
            "MANGO_REQUIRE_POWERSHELL_CONFIRMATION / MANGO_REQUIRE_PHONE_CONFIRMATION / "
            "MANGO_REQUIRE_XBOX_TURNOFF_CONFIRMATION.",
        )
    if cfg.require_tool_confirmation:
        logger.warning(
            "Spoken confirmations enabled (powershell=%s phone=%s xbox_turn_off=%s).",
            cfg.require_powershell_confirmation,
            cfg.require_phone_confirmation,
            cfg.require_xbox_turn_off_confirmation,
        )
    if cfg.clipboard_require_intent:
        logger.info("Clipboard reads require explicit clipboard-related wording in the user utterance.")
    if cfg.contact_info_require_intent:
        logger.info("Contact info reads require explicit phone/contact wording in the user utterance.")
    if not cfg.discord_relax_intent_gates:
        logger.info("Discord strict intents on — music/ping/join-other hints apply.")
    if cfg.disabled_tools:
        logger.info(
            "Disabled tools (MANGO_DISABLED_TOOLS): %s",
            ", ".join(sorted(cfg.disabled_tools)),
        )
    if cfg.persistent_memory:
        logger.warning(
            "Persistent memory is ON — conversations are stored as plaintext JSON under %s "
            "(rolling.json and optional days/). Disable with MANGO_PERSISTENT_MEMORY=0.",
            cfg.memory_dir,
        )
        logger.info(
            "Persistent memory: tier=%s history_cap=%s memory_floor=%s merge_days=%s daily_snapshots=%s",
            cfg.memory_tier,
            cfg.max_conversation_messages,
            cfg.memory_max_messages,
            cfg.memory_merge_days,
            cfg.memory_daily_snapshots,
        )
    logger.info(
        "Config: llm=%s groq_model=%s ollama_base=%s ollama_model=%s history_cap=%s "
        "preset=%s honorific=%s skills_dir=%s skills_max_chars=%s tool_out_cap=%s spoken_cap=%s wake=%s always_listen=%s "
        "chime_wake=%s chime_ptt=%s hotkey=%s streaming_tts=%s speak_on_error=%s tts_playback=%s strict_tools=%s "
        "interrupt_profile=%s confirm_ps=%s confirm_phone=%s confirm_xbox_turn_off=%s clipboard_intent=%s contact_info_intent=%s discord_relaxed=%s quiet_hours=%s whisper=%s vad=%s "
        "no_speech_thr=%s logprob_thr=%s normalize_peak=%s rate=%s tts=%s",
        cfg.llm_provider,
        cfg.groq_model,
        cfg.ollama_base_url,
        cfg.ollama_model,
        cfg.max_conversation_messages,
        cfg.preset,
        cfg.honorific or "default",
        cfg.skills_dir,
        cfg.skills_max_chars,
        cfg.max_tool_output_chars,
        cfg.max_spoken_reply_chars,
        cfg.wake_word_enabled,
        cfg.always_listen,
        cfg.listen_chime_wake,
        cfg.listen_chime_ptt,
        repr(cfg.hotkey),
        cfg.streaming_tts,
        cfg.speak_on_error,
        cfg.tts_playback,
        cfg.strict_tools,
        cfg.interruption_profile,
        cfg.require_powershell_confirmation,
        cfg.require_phone_confirmation,
        cfg.require_xbox_turn_off_confirmation,
        cfg.clipboard_require_intent,
        cfg.contact_info_require_intent,
        cfg.discord_relax_intent_gates,
        cfg.quiet_hours,
        cfg.whisper_model,
        cfg.whisper_vad_filter,
        cfg.whisper_no_speech_threshold,
        cfg.whisper_log_prob_threshold,
        cfg.audio_normalize_target_peak,
        cfg.sample_rate,
        cfg.tts_provider,
    )
    if cfg.wake_word_enabled:
        logger.info(
            "Wake: engine=%s oww=%s oww_models=%s whisper_confirm=%s streaming=%s "
            "interval=%.1fs wake_whisper=%s phrase=%r stream_hi=max(%.4f,noise*x%.2f) "
            "stream_lo=max(%.4f,noise*x%.2f) whisper_min_peak=%.4f whisper_min_std=%.4f",
            cfg.wake_engine,
            cfg.wake_use_openwakeword,
            ",".join(cfg.oww_model_names) or "(none)",
            cfg.wake_oww_whisper_confirm,
            cfg.wake_streaming,
            cfg.wake_interval_seconds,
            cfg.wake_whisper_model or "(same as main)",
            cfg.wake_phrase,
            cfg.wake_stream_speech_hi_floor,
            cfg.wake_stream_speech_hi_mult,
            cfg.wake_stream_speech_lo_floor,
            cfg.wake_stream_speech_lo_mult,
            cfg.wake_whisper_min_peak,
            cfg.wake_whisper_min_std,
        )
    if cfg.tts_provider == "edge":
        logger.info(
            "Edge TTS voice=%s rate=%s pitch=%s volume=%s",
            cfg.edge_voice,
            cfg.edge_rate,
            cfg.edge_pitch,
            cfg.edge_volume,
        )
    else:
        logger.info(
            "ElevenLabs voice_id=%s… tts_model=%s sts_after_tts=%s sts_model=%s",
            cfg.elevenlabs_voice_id[:8] + "…" if len(cfg.elevenlabs_voice_id) > 8 else cfg.elevenlabs_voice_id,
            cfg.elevenlabs_tts_model,
            cfg.elevenlabs_sts_after_tts,
            cfg.elevenlabs_sts_model,
        )
    return cfg

