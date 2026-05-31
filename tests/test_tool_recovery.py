from __future__ import annotations

from typing import Any

from mango.tool_recovery import (
    recover_from_groq_tool_use_failed,
    strip_pseudo_tool_markup_for_speech,
    split_assistant_content_and_pseudo_tool,
)


class _FakeBadRequest(Exception):
    def __init__(self, failed_generation: str) -> None:
        self.body = {"error": {"failed_generation": failed_generation}}


class _FakeRegistry:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(  # noqa: D401
        self,
        name: str,
        args: dict[str, Any],
        *,
        conversation_messages: list[dict[str, Any]] | None = None,
    ) -> str:
        self.calls.append((name, args))
        if name == "run_powershell":
            return "HOST_PENDING_POWERSHELL: not executed."
        return "ok"


def test_recovery_salvages_pseudo_powershell_even_when_pending() -> None:
    exc = _FakeBadRequest('<function=run_powershell {"command_key":"list_processes"} </function>')
    messages: list[dict[str, Any]] = [{"role": "user", "content": "show me processes"}]
    registry = _FakeRegistry()

    ok = recover_from_groq_tool_use_failed(exc, messages, registry)

    assert ok is True
    assert registry.calls == [("run_powershell", {"command_key": "list_processes"})]
    assert messages[-1]["role"] == "tool"
    assert str(messages[-1]["content"]).startswith("HOST_PENDING_POWERSHELL")


def test_recovery_salvages_pseudo_run_routine() -> None:
    exc = _FakeBadRequest(
        '<function=run_routine{"action": "run", "routine_id": "join_discord_play"}</function>'
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": "run join_discord_play"}]
    registry = _FakeRegistry()

    ok = recover_from_groq_tool_use_failed(exc, messages, registry)

    assert ok is True
    assert registry.calls == [
        ("run_routine", {"action": "run", "routine_id": "join_discord_play"}),
    ]
    assert messages[-1]["role"] == "tool"
    assert messages[-1]["content"] == "ok"


def test_recovery_ignores_unknown_tool_name() -> None:
    exc = _FakeBadRequest('<function=not_a_real_tool {"x":1}></function>')
    messages: list[dict[str, Any]] = [{"role": "user", "content": "do thing"}]
    registry = _FakeRegistry()

    ok = recover_from_groq_tool_use_failed(exc, messages, registry)

    assert ok is False
    assert registry.calls == []


def test_split_assistant_content_parses_pseudo_tool_tail() -> None:
    spoken, pseudo = split_assistant_content_and_pseudo_tool(
        'Got it. <function=run_powershell {"command_key":"env_username"} </function>'
    )
    assert spoken == "Got it."
    assert pseudo == ("run_powershell", {"command_key": "env_username"})


def test_recovery_salvages_slash_pseudo_run_routine() -> None:
    exc = _FakeBadRequest(
        '<function/run_routine {"action": "run", "routine_id": "discord_hi_and_play", '
        '"query": "Bad Romance", "volume": 50}</function>'
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": "play bad romance"}]
    registry = _FakeRegistry()

    ok = recover_from_groq_tool_use_failed(exc, messages, registry)

    assert ok is True
    assert registry.calls == [
        (
            "run_routine",
            {
                "action": "run",
                "routine_id": "discord_hi_and_play",
                "query": "Bad Romance",
                "volume": 50,
            },
        ),
    ]


def test_split_assistant_parses_slash_function_syntax() -> None:
    raw = (
        '<function/run_routine {"action": "run", "routine_id": "discord_hi_and_play", '
        '"query": "Bad Romance", "volume": 50}</function>'
    )
    spoken, pseudo = split_assistant_content_and_pseudo_tool(raw)
    assert spoken == ""
    assert pseudo is not None
    assert pseudo[0] == "run_routine"
    assert pseudo[1]["routine_id"] == "discord_hi_and_play"


def test_split_assistant_parses_xml_style_tool_tag() -> None:
    spoken, pseudo = split_assistant_content_and_pseudo_tool(
        'Sure. <web_search query="interesting fact" />'
    )
    assert spoken == "Sure."
    assert pseudo == ("web_search", {"query": "interesting fact"})


def test_recovery_salvages_xml_style_tool_tag() -> None:
    exc = _FakeBadRequest('<web_search query="interesting fact" />')
    messages: list[dict[str, Any]] = [{"role": "user", "content": "tell me an interesting fact"}]
    registry = _FakeRegistry()

    ok = recover_from_groq_tool_use_failed(exc, messages, registry)

    assert ok is True
    assert registry.calls == [("web_search", {"query": "interesting fact"})]


def test_split_assistant_parses_function_wrapped_tool_with_json_tail() -> None:
    spoken, pseudo = split_assistant_content_and_pseudo_tool(
        'Sure thing. <function>web_search</function>{"query":"interesting fact"}'
    )
    assert spoken == "Sure thing."
    assert pseudo == ("web_search", {"query": "interesting fact"})


def test_recovery_salvages_function_wrapped_tool_with_json_tail() -> None:
    exc = _FakeBadRequest('<function>web_search</function>{"query":"interesting fact"}')
    messages: list[dict[str, Any]] = [{"role": "user", "content": "tell me an interesting fact"}]
    registry = _FakeRegistry()

    ok = recover_from_groq_tool_use_failed(exc, messages, registry)

    assert ok is True
    assert registry.calls == [("web_search", {"query": "interesting fact"})]


def test_split_assistant_parses_paired_tool_tag_with_json_body() -> None:
    spoken, pseudo = split_assistant_content_and_pseudo_tool(
        'Sure. <spotify_play>{"query":"popular rap song"}</spotify_play>'
    )
    assert spoken == "Sure."
    assert pseudo == ("spotify_play", {"query": "popular rap song"})


def test_recovery_salvages_function_name_with_arguments_json_attr() -> None:
    exc = _FakeBadRequest(
        """<function name="web_search" arguments='{"query":"interesting fact"}' />"""
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": "tell me an interesting fact"}]
    registry = _FakeRegistry()

    ok = recover_from_groq_tool_use_failed(exc, messages, registry)

    assert ok is True
    assert registry.calls == [("web_search", {"query": "interesting fact"})]


def test_strip_pseudo_tool_markup_for_speech_handles_partial_function_tag() -> None:
    cleaned = strip_pseudo_tool_markup_for_speech('Sure. <function=web_search {"query":"x"')
    assert cleaned == "Sure."


def test_strip_pseudo_tool_markup_for_speech_handles_generic_tag() -> None:
    cleaned = strip_pseudo_tool_markup_for_speech('Sure. <web_search query="x"')
    assert cleaned == "Sure."
