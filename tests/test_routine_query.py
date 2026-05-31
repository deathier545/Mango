from __future__ import annotations

from mango.smart.routine_query import infer_song_query_from_messages, normalize_song_query
from mango.tools import run_routine


def test_normalize_song_query_strips_volume_tail() -> None:
    assert normalize_song_query("Bad Romance and volume 50") == "Bad Romance"


def test_infer_song_from_user_message() -> None:
    msgs = [
        {
            "role": "user",
            "content": "Run routine discord_hi_and_play with the song Bad Romance and volume 50.",
        },
    ]
    assert infer_song_query_from_messages(msgs) == "Bad Romance"


def test_run_routine_infers_query_when_missing() -> None:
    class _Reg:
        def risk_level(self, _tool: str) -> str:
            return "low"

        def execute(self, tool: str, args: dict) -> str:
            if tool == "spotify_play":
                return f"TRACK_PLAYED: {args.get('query')!r}"
            return "ok"

    reg = _Reg()
    run_routine.set_registry(reg)
    out = run_routine.run(
        action="run",
        routine_id="discord_hi_and_play",
        volume=50,
        conversation_messages=[
            {"role": "user", "content": "play Bad Romance on discord"},
        ],
    )
    assert "Bad Romance" in out
    assert "{{query}}" not in out
