from __future__ import annotations

from mango.transcript_postprocess import normalize_transcript_text


def test_normalize_for_you_today_mishear() -> None:
    assert normalize_transcript_text("for you today") == "how are you today"
    assert normalize_transcript_text("For you today?") == "how are you today"


def test_normalize_does_not_change_unrelated_text() -> None:
    assert normalize_transcript_text("for your todo list") == "for your todo list"
    assert normalize_transcript_text("how are you today") == "how are you today"
