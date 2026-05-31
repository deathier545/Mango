"""Typed config sections used by `mango.config.Config`."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LlmConfig:
    provider: str = "groq"
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"


@dataclass
class AudioConfig:
    sample_rate: int = 16_000
    whisper_model: str = "base.en"
    min_record_seconds: float = 0.25
    whisper_vad_filter: bool = False
    whisper_no_speech_threshold: float = 0.82
    whisper_log_prob_threshold: float = -1.5
    normalize_target_peak: float = 0.5
    normalize_max_gain: float = 120.0


@dataclass
class WakeConfig:
    enabled: bool = False
    engine: str = "auto"
    phrase: str = "mango"
    streaming: bool = False
    wake_whisper_model: str = ""
    oww_model_names: tuple[str, ...] = ()
    oww_threshold: float = 0.5
    oww_vad_threshold: float = 0.0
    oww_inference_framework: str = "onnx"


@dataclass
class ToolPolicyConfig:
    strict_tools: bool = False
    max_tool_output_chars: int = 10_000
    max_spoken_reply_chars: int = 1200
    max_llm_tool_rounds: int = 6
    require_powershell_confirmation: bool = True
    require_phone_confirmation: bool = False
    require_xbox_turn_off_confirmation: bool = False
    clipboard_require_intent: bool = False
    contact_info_require_intent: bool = True
    discord_relax_intent_gates: bool = True


@dataclass
class TtsConfig:
    provider: str = "edge"
    playback: str = "headset"
    edge_voice: str = "en-US-GuyNeural"
    edge_rate: str = "+0%"
    edge_pitch: str = "+0Hz"
    edge_volume: str = "+0%"
    streaming_tts: bool = True
    speak_on_error: bool = True
    elevenlabs_voice_id: str = ""
    elevenlabs_tts_model: str = "eleven_multilingual_v2"
    elevenlabs_sts_model: str = "eleven_multilingual_sts_v2"
    elevenlabs_sts_after_tts: bool = False
