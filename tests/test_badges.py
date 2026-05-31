from __future__ import annotations

from pathlib import Path

import pytest

from mango import badges

_BADGE_TOTAL = 47


def _empty_home(tmp_path: Path) -> Path:
    home = tmp_path / "empty_home"
    home.mkdir()
    return home


def _patch_empty(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    monkeypatch.setattr(badges, "_mango_home", lambda: home)
    monkeypatch.setattr(badges, "load_cards", lambda: [])
    monkeypatch.setattr(badges, "load_inbox", lambda: [])
    monkeypatch.setattr(badges, "load_timeline_entries", lambda _limit=5000: [])
    monkeypatch.setattr(badges, "_skill_count", lambda: 0)
    monkeypatch.delenv("MANGO_PERSISTENT_MEMORY", raising=False)
    monkeypatch.delenv("MANGO_WAKEWORD", raising=False)
    monkeypatch.delenv("MANGO_SESSION_LOG", raising=False)


def test_compute_badge_snapshot_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_empty(monkeypatch, _empty_home(tmp_path))

    snap = badges.compute_badge_snapshot()

    assert snap["summary"]["total"] == _BADGE_TOTAL
    assert snap["summary"]["unlocked"] == 0
    assert snap["summary"]["percent"] == 0
    by_id = {b["id"]: b for b in snap["badges"]}
    assert by_id["memory_first"]["unlocked"] is False
    assert "progress" not in by_id["memory_first"]
    assert by_id["memory_collector"]["progress"] == {"current": 0, "target": 5}
    assert by_id["tool_globe"]["hint"]
    assert by_id["voice_wake"]["unlocked"] is False


def test_memory_badges_unlock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = _empty_home(tmp_path)
    monkeypatch.setattr(badges, "_mango_home", lambda: home)
    cards = [
        {"id": "1", "category": "fact", "title": "A", "content": "one"},
        {"id": "2", "category": "person", "title": "B", "content": "two"},
        {"id": "3", "category": "preference", "title": "C", "content": "three"},
        {"id": "4", "category": "device", "title": "D", "content": "four"},
        {"id": "5", "category": "task", "title": "E", "content": "five"},
    ]
    monkeypatch.setattr(badges, "load_cards", lambda: cards)
    monkeypatch.setattr(badges, "load_inbox", lambda: [])
    monkeypatch.setattr(badges, "load_timeline_entries", lambda _limit=5000: [])
    monkeypatch.setattr(badges, "_skill_count", lambda: 0)

    snap = badges.compute_badge_snapshot()
    by_id = {b["id"]: b for b in snap["badges"]}

    assert by_id["memory_first"]["unlocked"] is True
    assert by_id["memory_collector"]["unlocked"] is True
    assert by_id["memory_categories"]["unlocked"] is True
    assert by_id["memory_complete"]["unlocked"] is True


def test_tool_and_routine_badges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = _empty_home(tmp_path)
    monkeypatch.setattr(badges, "_mango_home", lambda: home)
    timeline = [
        {"tool": "open_app", "ok": True},
        {"tool": "spotify_play", "ok": True},
        {"tool": "volume_control", "ok": True},
        {"tool": "memory_card", "ok": True},
        {"tool": "run_powershell", "ok": True},
        {"tool": "web_search", "ok": True},
        {
            "tool": "run_routine",
            "ok": True,
            "result_preview": "Started night_mode routine",
        },
    ]
    monkeypatch.setattr(badges, "load_cards", lambda: [])
    monkeypatch.setattr(badges, "load_inbox", lambda: [])
    monkeypatch.setattr(badges, "load_timeline_entries", lambda _limit=5000: timeline)
    monkeypatch.setattr(badges, "_skill_count", lambda: 0)

    snap = badges.compute_badge_snapshot()
    by_id = {b["id"]: b for b in snap["badges"]}

    assert by_id["tool_first"]["unlocked"] is True
    assert by_id["tool_explorer"]["unlocked"] is True
    assert by_id["tool_spotify"]["unlocked"] is True
    assert by_id["tool_web"]["unlocked"] is True
    assert by_id["tool_veteran"]["progress"] == {"current": 7, "target": 50}
    assert by_id["routine_night"]["unlocked"] is True


def test_integrations_and_continuity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / ".mango"
    days = home / "memory" / "days"
    days.mkdir(parents=True)
    for i in range(7):
        (days / f"2025-01-0{i + 1}.json").write_text("{}", encoding="utf-8")
    (home / "spotify_user_token.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("MANGO_SMART_DIR", str(home / "smart"))
    monkeypatch.setenv("MANGO_PERSISTENT_MEMORY", "1")
    monkeypatch.setenv("MANGO_WAKEWORD", "1")
    monkeypatch.setattr(badges, "_mango_home", lambda: home)
    monkeypatch.setattr(badges, "load_cards", lambda: [])
    monkeypatch.setattr(badges, "load_inbox", lambda: [])
    monkeypatch.setattr(badges, "load_timeline_entries", lambda _limit=5000: [])
    monkeypatch.setattr(badges, "_skill_count", lambda: 2)

    snap = badges.compute_badge_snapshot()
    by_id = {b["id"]: b for b in snap["badges"]}

    assert by_id["integration_spotify"]["unlocked"] is True
    assert by_id["continuity_memory"]["unlocked"] is True
    assert by_id["continuity_days"]["unlocked"] is True
    assert by_id["voice_wake"]["unlocked"] is True
    assert by_id["skill_author"]["unlocked"] is True
    assert by_id["skill_library"]["progress"] == {"current": 2, "target": 3}


def test_badges_for_prompt_lists_locked_goals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_empty(monkeypatch, _empty_home(tmp_path))

    block = badges.badges_for_prompt(max_locked=5)

    assert "Progress badges (0/47 unlocked" in block or "My progress badges (0/47 unlocked" in block
    assert "Still locked for me" in block
    assert "First Memory" in block
    assert "Tell Mango one thing to remember" in block


def test_badge_titles_are_unique(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_empty(monkeypatch, _empty_home(tmp_path))
    snap = badges.compute_badge_snapshot()
    titles = [b["title"] for b in snap["badges"]]
    assert len(titles) == len(set(titles))
    assert len(snap["badges"]) == _BADGE_TOTAL
