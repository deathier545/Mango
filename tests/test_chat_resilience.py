from __future__ import annotations

from mango.llm_tool_loop import _clarification_for_tool_result, _empty_reply_fallback, _looks_like_action_request


def test_clarification_skips_social_turns() -> None:
    assert _clarification_for_tool_result(
        "open_app",
        "ERR_TOOL_BAD_ARGS:open_app:missing app_name",
        user_text="How are you right now?",
    ) is None


def test_clarification_skips_non_action_turns() -> None:
    assert _clarification_for_tool_result(
        "memory_card",
        "Tool call for memory_card had invalid JSON arguments.",
        user_text="Tell me a joke.",
    ) is None


def test_clarification_keeps_action_turns() -> None:
    assert _clarification_for_tool_result(
        "open_app",
        "ERR_TOOL_BAD_ARGS:open_app:missing",
        user_text="open something for me",
    ) == "What exactly should I do?"


def test_empty_fallback_social() -> None:
    out = _empty_reply_fallback("How are you right now?")
    assert "what exactly should i do" not in out.casefold()
    assert len(out) > 8


def test_looks_like_action_request() -> None:
    assert _looks_like_action_request("play Drake on Spotify")
    assert not _looks_like_action_request("How are you right now?")
