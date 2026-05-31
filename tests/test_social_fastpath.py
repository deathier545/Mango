from __future__ import annotations

from mango.badge_fastpath import parse_badge_intent
from mango.social_fastpath import parse_social_intent, try_fast_social_reply


def test_social_intent_how_are_you() -> None:
    assert parse_social_intent("How are you right now?")
    assert parse_social_intent("hey")
    assert not parse_social_intent("play Drake on Spotify")
    assert not parse_social_intent("Do you want to open Chrome?")


def test_social_does_not_overlap_badge() -> None:
    assert parse_social_intent("How are you right now?")
    assert not parse_badge_intent("How are you right now?")


def test_social_fast_reply() -> None:
    out = try_fast_social_reply("How are you right now?", [], object())
    assert out is not None
    assert "what exactly should i do" not in out.casefold()
    assert len(out) > 10
