"""Unit tests for Config.load() parsing (no mic, no pygame)."""

from __future__ import annotations

from mango.config import Config


def test_config_invalid_int_env_falls_back_to_default(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.setenv("MANGO_MAX_CONVERSATION_MESSAGES", "not_a_number")
    cfg = Config.load()
    assert cfg.max_conversation_messages == 36


def test_config_invalid_float_env_falls_back(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.setenv("MANGO_MIN_RECORD_SECONDS", "bogus")
    cfg = Config.load()
    assert cfg.min_record_seconds == 0.25


def test_config_hotkey_from_env(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.setenv("HOTKEY", "V")
    cfg = Config.load()
    assert cfg.hotkey == "v"


def test_config_legacy_require_tool_confirmation_off(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.setenv("MANGO_REQUIRE_TOOL_CONFIRMATION", "0")
    cfg = Config.load()
    assert cfg.require_tool_confirmation is False
    assert cfg.require_powershell_confirmation is False
    assert cfg.require_phone_confirmation is False
    assert cfg.require_xbox_turn_off_confirmation is False


def test_config_require_tool_confirmation_defaults(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.delenv("MANGO_REQUIRE_TOOL_CONFIRMATION", raising=False)
    monkeypatch.delenv("MANGO_REQUIRE_POWERSHELL_CONFIRMATION", raising=False)
    monkeypatch.delenv("MANGO_REQUIRE_PHONE_CONFIRMATION", raising=False)
    monkeypatch.delenv("MANGO_REQUIRE_XBOX_TURNOFF_CONFIRMATION", raising=False)
    cfg = Config.load()
    assert cfg.require_powershell_confirmation is True
    assert cfg.require_phone_confirmation is False
    assert cfg.require_xbox_turn_off_confirmation is False
    assert cfg.require_tool_confirmation is True


def test_config_legacy_require_tool_confirmation_enable_with_one(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.setenv("MANGO_REQUIRE_TOOL_CONFIRMATION", "1")
    cfg = Config.load()
    assert cfg.require_tool_confirmation is True
    assert cfg.require_powershell_confirmation is True
    assert cfg.require_phone_confirmation is True
    assert cfg.require_xbox_turn_off_confirmation is True


def test_config_per_tool_confirmation_overrides_legacy(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.setenv("MANGO_REQUIRE_TOOL_CONFIRMATION", "0")
    monkeypatch.setenv("MANGO_REQUIRE_POWERSHELL_CONFIRMATION", "1")
    monkeypatch.setenv("MANGO_REQUIRE_PHONE_CONFIRMATION", "0")
    monkeypatch.setenv("MANGO_REQUIRE_XBOX_TURNOFF_CONFIRMATION", "0")
    cfg = Config.load()
    assert cfg.require_powershell_confirmation is True
    assert cfg.require_phone_confirmation is False
    assert cfg.require_xbox_turn_off_confirmation is False
    assert cfg.require_tool_confirmation is True


def test_config_ollama_without_groq_key(cfg_root, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "ollama")
    cfg = Config.load()
    assert cfg.llm_provider == "ollama"


def test_config_typed_sections_defaults(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    cfg = Config.load()
    assert cfg.llm.provider == cfg.llm_provider
    assert cfg.audio.sample_rate == cfg.sample_rate
    assert cfg.wake.enabled == cfg.wake_word_enabled
    assert cfg.tool_policy.require_powershell_confirmation is True
    assert cfg.tts.provider == cfg.tts_provider


def test_config_typed_sections_follow_env(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("MANGO_OLLAMA_MODEL", "llama3.2")
    monkeypatch.setenv("MANGO_REQUIRE_POWERSHELL_CONFIRMATION", "0")
    monkeypatch.setenv("MANGO_WAKEWORD", "1")
    monkeypatch.setenv("MANGO_WAKE_ENGINE", "whisper")
    cfg = Config.load()
    assert cfg.llm.provider == "ollama"
    assert cfg.wake.enabled is True
    assert cfg.wake.engine == "whisper"
    assert cfg.tool_policy.require_powershell_confirmation is False


def test_config_memory_tier_day_overrides(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.setenv("MANGO_MEMORY_TIER", "day")
    cfg = Config.load()
    assert cfg.memory_tier == "day"
    assert cfg.persistent_memory is True
    assert cfg.memory_merge_days == 1


def test_config_memory_tier_session_overrides(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.setenv("MANGO_MEMORY_TIER", "session")
    monkeypatch.setenv("MANGO_PERSISTENT_MEMORY", "1")
    cfg = Config.load()
    assert cfg.memory_tier == "session"
    assert cfg.persistent_memory is False


def test_config_spoken_reply_cap_from_env(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.setenv("MANGO_MAX_SPOKEN_REPLY_CHARS", "180")
    cfg = Config.load()
    assert cfg.max_spoken_reply_chars == 180


def test_config_contact_info_intent_default_on(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.delenv("MANGO_CONTACT_INFO_REQUIRE_INTENT", raising=False)
    cfg = Config.load()
    assert cfg.contact_info_require_intent is True


def test_config_contact_info_intent_can_disable(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.setenv("MANGO_CONTACT_INFO_REQUIRE_INTENT", "0")
    cfg = Config.load()
    assert cfg.contact_info_require_intent is False


def test_config_preset_mango_mlx_and_legacy_alias(cfg_root, monkeypatch):
    from mango.presets import suffix_for

    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.setenv("MANGO_PRESET", "mango_mlx")
    cfg = Config.load()
    assert cfg.preset == "mango_mlx"
    assert "Concise preset" in suffix_for(cfg.preset)
    monkeypatch.setenv("MANGO_PRESET", "jarvis_mlx")
    cfg_legacy = Config.load()
    assert cfg_legacy.preset == "jarvis_mlx"
    assert suffix_for("jarvis_mlx") == suffix_for("mango_mlx")
