from __future__ import annotations

import os
from unittest.mock import patch

from mango.tool_narration import (
    narrate_routine_step_after,
    narrate_tool_before,
    short_completion_reply,
    tool_done_line,
    tool_start_line,
)


def test_tool_lines() -> None:
    sync = tool_start_line("discord_voice", {"action": "sync"}) or ""
    assert "discord" in sync.casefold() or "voice" in sync.casefold() or "call" in sync.casefold()
    assert "join" in sync.casefold() or "connect" in sync.casefold()
    greet = tool_start_line("discord_voice", {"action": "greet_everyone"}) or ""
    assert "hello" in greet.casefold() or "greet" in greet.casefold()
    open_line = tool_start_line("open_app", {"app_name": "Discord"}) or ""
    assert open_line == ""
    assert tool_start_line("product_research", {"product": "headphones"}) or ""
    assert tool_start_line("spotify_play", {"query": "Bad Romance"}) is None
    assert tool_start_line("web_search", {"query": "weather"}) is None


def test_skip_before_tools() -> None:
    assert tool_start_line("run_powershell", {"command": "Get-Date"}) is None
    assert tool_start_line("phone_call", {"contact": "Alex"}) is None


def test_tool_done_line() -> None:
    done = tool_done_line(
        "discord_voice",
        {"action": "sync"},
        "Joined voice channel ok",
    )
    assert done and "sir" in done.casefold()


def test_narrate_before_blocks() -> None:
    with patch("mango.tool_narration.speak_progress") as speak:
        narrate_tool_before("discord_voice", {"action": "sync"})
        speak.assert_called_once()


def test_routine_step_after() -> None:
    with patch.dict(os.environ, {"MANGO_TOOL_NARRATION_AFTER": "1"}):
        with patch("mango.tool_narration.speak_progress") as speak:
            narrate_routine_step_after(
                "volume_control",
                {"action": "set", "percent": 50},
                "Volume set to 50%.",
            )
            speak.assert_called_once()


def test_short_completion_reply_is_concise() -> None:
    out = short_completion_reply("discord_hi_and_play", {"query": "Bad Romance"}, "ok")
    assert "sir" not in out.casefold()
    assert "all set" in out.casefold()
