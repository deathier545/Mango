from __future__ import annotations

from mango.discord_play_fastpath import parse_discord_play_intent


def test_parse_discord_hi_and_play_intent() -> None:
    parsed = parse_discord_play_intent(
        "Run routine discord_hi_and_play with the song Bad Romance and volume 50."
    )
    assert parsed is not None
    rid, query, vol = parsed
    assert rid == "discord_hi_and_play"
    assert query == "Bad Romance"
    assert vol == 50


def test_parse_join_discord_play_intent() -> None:
    parsed = parse_discord_play_intent("Join Discord and play Never Gonna Give You Up")
    assert parsed is not None
    rid, query, vol = parsed
    assert rid == "join_discord_play"
    assert query == "Never Gonna Give You Up"
    assert vol is None
