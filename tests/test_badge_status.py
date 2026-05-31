from __future__ import annotations

from pathlib import Path

import pytest

from mango import badges
from mango.tools import badge_status
from mango.voice_prompt import _build_system_prompt, refresh_system_message


def test_badge_status_tool_returns_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "empty_home"
    home.mkdir()
    monkeypatch.setattr(badges, "_mango_home", lambda: home)
    monkeypatch.setattr(badges, "load_cards", lambda: [])
    monkeypatch.setattr(badges, "load_inbox", lambda: [])
    monkeypatch.setattr(badges, "load_timeline_entries", lambda _limit=5000: [])
    monkeypatch.setattr(badges, "_skill_count", lambda: 0)

    out = badge_status.run()

    assert "0 of 47" in out or "47" in out
    assert "My progress badges" not in out or "I'm at" in out


def test_system_prompt_mentions_badges_and_never_deny(cfg_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from mango.config import Config

    monkeypatch.setenv("MANGO_LLM_PROVIDER", "ollama")
    cfg = Config.load()
    prompt = _build_system_prompt(cfg)

    assert "My progress badges" in prompt
    assert "progress badges" in prompt.casefold()
    assert prompt.find("My progress badges") < prompt.find("Runtime policy:")


def test_refresh_system_message_updates_first_message(cfg_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from mango.config import Config

    monkeypatch.setenv("MANGO_LLM_PROVIDER", "ollama")
    cfg = Config.load()
    messages = [{"role": "system", "content": "stale"}, {"role": "user", "content": "hi"}]
    refresh_system_message(messages, cfg)

    assert "My progress badges" in messages[0]["content"]
    assert messages[1]["content"] == "hi"
