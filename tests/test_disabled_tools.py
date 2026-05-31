from __future__ import annotations

from mango.config import Config
from mango.tool_registry import ToolRegistry


def test_disabled_tools_omitted_from_definitions(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.setenv("MANGO_DISABLED_TOOLS", "discord_voice, xbox_console")
    cfg = Config.load()
    reg = ToolRegistry(cfg)
    names = {d["function"]["name"] for d in reg.definitions()}
    assert "discord_voice" not in names
    assert "xbox_console" not in names
    assert "open_app" in names


def test_disabled_tool_execute_returns_error(cfg_root, monkeypatch):
    monkeypatch.setenv("MANGO_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test012345678901234567890123456789")
    monkeypatch.setenv("MANGO_DISABLED_TOOLS", "globe_state")
    cfg = Config.load()
    reg = ToolRegistry(cfg)
    out = reg.execute("globe_state", {})
    assert out.startswith("ERR_TOOL_DISABLED:")
