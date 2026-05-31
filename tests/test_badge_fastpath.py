from __future__ import annotations

from pathlib import Path

import pytest

from mango import badges
from mango.badge_fastpath import parse_badge_intent, try_fast_badge_status


def test_parse_badge_intent_matches_motivation() -> None:
    assert parse_badge_intent("Do you want to unlock more badges?")
    assert parse_badge_intent("Tell me about your badge status.")
    assert not parse_badge_intent("Do you want to play Spotify?")
    assert not parse_badge_intent("How are you right now?")
    assert not parse_badge_intent("I want to learn guitar")


def test_motivation_reply_is_enthusiastic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "empty_home"
    home.mkdir()
    monkeypatch.setattr(badges, "_mango_home", lambda: home)
    monkeypatch.setattr(badges, "load_cards", lambda: [])
    monkeypatch.setattr(badges, "load_inbox", lambda: [])
    monkeypatch.setattr(badges, "load_timeline_entries", lambda _limit=5000: [])
    monkeypatch.setattr(badges, "_skill_count", lambda: 0)

    out = try_fast_badge_status("Do you want to unlock more badges?", [], object())

    assert out is not None
    low = out.casefold()
    assert "want" in low or "do" in low
    assert "right." not in low
    assert len(out) > 40


def test_status_reply_includes_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "empty_home"
    home.mkdir()
    monkeypatch.setattr(badges, "_mango_home", lambda: home)
    monkeypatch.setattr(badges, "load_cards", lambda: [])
    monkeypatch.setattr(badges, "load_inbox", lambda: [])
    monkeypatch.setattr(badges, "load_timeline_entries", lambda _limit=5000: [])
    monkeypatch.setattr(badges, "_skill_count", lambda: 0)

    out = badges.format_badge_reply("Tell me about your badge status.")

    assert "0 of 47" in out or "47" in out
