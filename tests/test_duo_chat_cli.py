from __future__ import annotations

from types import SimpleNamespace

from mango.duo_chat_cli import _clean_line, _duo_context, _llm_reply


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeLLM:
    def chat(self, messages, tools):  # noqa: ANN001
        assert tools == []
        assert messages
        return _FakeCompletion("Hello from Mango.")


def test_llm_reply_uses_tools_and_extracts_content() -> None:
    text = _llm_reply(_FakeLLM(), [{"role": "user", "content": "Hi"}])
    assert text == "Hello from Mango."


def test_clean_line_truncates_long_text() -> None:
    long_text = "word " * 200
    cleaned = _clean_line(long_text, max_chars=40)
    assert len(cleaned) <= 40


def test_duo_context_formats_recent_lines() -> None:
    lines = [
        {"speaker": "mango", "text": "First"},
        {"speaker": "amber", "text": "Second"},
    ]
    ctx = _duo_context(lines)
    assert "Mango: First" in ctx
    assert "Amber: Second" in ctx
