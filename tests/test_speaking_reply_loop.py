from __future__ import annotations

from mango.llm_tool_loop import (
    _deterministic_tool_spoken_result,
    _extract_source_cues,
    _route_hint_for_round,
    _clarification_for_tool_result,
    _discord_bridge_unreachable,
    _discord_voice_stuck_loop,
    _early_tool_loop_spoken_reply,
    _generic_tool_retry_without_progress,
    _needs_immediate_confirmation_followup,
    _sanitize_model_reply,
    _with_source_cues,
)
from mango.planner_executor import PlannerExecutorState


def test_discord_bridge_unreachable_detects_connect_error() -> None:
    msg = (
        "Discord voice bridge is not reachable on this PC (nothing listening on localhost). "
        "Start it in a **separate** terminal"
    )
    assert _discord_bridge_unreachable(msg)


def test_discord_bridge_unreachable_detects_404_hint() -> None:
    assert _discord_bridge_unreachable(
        "No voice control HTTP server on port 37564. Is `python -m mango --discord-voice` running?"
    )


def test_early_exit_on_bridge_down() -> None:
    st = PlannerExecutorState()
    s = st.add_step(round_idx=1, tool_name="discord_voice", arguments={"action": "sync"})
    st.mark_done(s, "Discord voice bridge is not reachable on this PC")
    spoken = _early_tool_loop_spoken_reply(st, s.note)
    assert spoken is not None
    assert "python -m mango --discord-voice" in spoken


def test_stuck_loop_on_same_discord_action_twice() -> None:
    st = PlannerExecutorState()
    s1 = st.add_step(round_idx=1, tool_name="discord_voice", arguments={"action": "status"})
    st.mark_done(s1, "Connected to voice channel")
    s2 = st.add_step(round_idx=2, tool_name="discord_voice", arguments={"action": "status"})
    st.mark_done(s2, "Connected to voice channel")
    assert _discord_voice_stuck_loop(st)
    spoken = _early_tool_loop_spoken_reply(st, s2.note)
    assert spoken is not None
    assert "Discord voice" in spoken


def test_no_stuck_loop_for_sync_then_greet() -> None:
    st = PlannerExecutorState()
    s1 = st.add_step(round_idx=1, tool_name="discord_voice", arguments={"action": "sync"})
    st.mark_done(s1, "Joined voice channel")
    s2 = st.add_step(round_idx=2, tool_name="discord_voice", arguments={"action": "greet_everyone"})
    st.mark_done(s2, "Greeted Ariana")
    assert not _discord_voice_stuck_loop(st)
    assert _early_tool_loop_spoken_reply(st, s2.note) is None


def test_no_early_exit_for_single_discord_voice() -> None:
    st = PlannerExecutorState()
    s = st.add_step(round_idx=1, tool_name="discord_voice", arguments={"action": "sync"})
    st.mark_done(s, "Joined voice channel")
    assert not _discord_voice_stuck_loop(st)
    assert _early_tool_loop_spoken_reply(st, s.note) is None


def test_generic_tool_retry_without_progress_detects_duplicate_failed_step() -> None:
    st = PlannerExecutorState()
    s1 = st.add_step(round_idx=1, tool_name="web_search", arguments={"query": "weather"})
    st.mark_done(s1, "ERR_TOOL_BAD_ARGS:web_search:missing query")
    s2 = st.add_step(round_idx=2, tool_name="web_search", arguments={"query": "weather"})
    st.mark_done(s2, "ERR_TOOL_BAD_ARGS:web_search:missing query")
    assert _generic_tool_retry_without_progress(st)
    spoken = _early_tool_loop_spoken_reply(st, s2.note)
    assert spoken is not None
    assert "without progress" in spoken


def test_generic_tool_retry_without_progress_ignores_different_args() -> None:
    st = PlannerExecutorState()
    s1 = st.add_step(round_idx=1, tool_name="web_search", arguments={"query": "weather"})
    st.mark_done(s1, "ERR_TOOL_BAD_ARGS:web_search:missing query")
    s2 = st.add_step(round_idx=2, tool_name="web_search", arguments={"query": "news"})
    st.mark_done(s2, "ERR_TOOL_BAD_ARGS:web_search:missing query")
    assert not _generic_tool_retry_without_progress(st)


def test_confirmation_followup_detects_spoken_approval_prompt() -> None:
    assert _needs_immediate_confirmation_followup(
        "PowerShell needs approval. Say: I approve shell."
    )
    assert _needs_immediate_confirmation_followup(
        "I need approval before calling Ariana. Say: I approve call Ariana."
    )


def test_clarification_for_tool_result_handles_handoff_contract_errors() -> None:
    msg = _clarification_for_tool_result(
        "spotify_play",
        "ERR_TOOL_HANDOFF_CONTRACT:spotify_play:missing field query",
    )
    assert msg == "Which song?"


def test_sanitize_model_reply_rewrites_no_memory_disclaimer() -> None:
    raw = (
        "I'm happy to chat, but I don't have the ability to recall previous conversations. "
        "Each time you interact with me, it's a new conversation."
    )
    cleaned = _sanitize_model_reply(raw, "let me talk about yesterday")
    assert "don't have the ability to recall" not in cleaned.lower()
    assert "new conversation" not in cleaned.lower()
    assert "yesterday" in cleaned.lower()


def test_sanitize_model_reply_rewrites_no_opinion_disclaimer() -> None:
    raw = (
        "I don't have personal thoughts or opinions, but I can tell you my code is designed "
        "to provide helpful and accurate responses."
    )
    cleaned = _sanitize_model_reply(raw, "what do you think about your own code")
    assert "don't have personal thoughts" not in cleaned.lower()
    assert "helpful and accurate responses" in cleaned.lower()


def test_sanitize_model_reply_rewrites_i_dont_think_about_my_code_variant() -> None:
    raw = "I don't think about my own code."
    cleaned = _sanitize_model_reply(raw, "what do you think about your own code")
    assert "don't think about my own code" not in cleaned.lower()
    assert "my take" in cleaned.lower()


def test_extract_source_cues_parses_domains_from_web_search_results() -> None:
    result = (
        "1. Example\n"
        "   https://www.wikipedia.org/topic\n"
        "   body\n"
        "2. Another\n"
        "   https://news.ycombinator.com/item?id=1\n"
        "   body\n"
    )
    cues = _extract_source_cues("web_search", result)
    assert cues == ["wikipedia.org", "news.ycombinator.com"]


def test_with_source_cues_folds_primary_host_into_reply() -> None:
    out = _with_source_cues("Here is the update.", ["wikipedia.org", "example.com"])
    assert out.endswith("That's from Wikipedia.")


def test_route_hint_for_round_prefers_fast_on_short_simple_prompt() -> None:
    assert _route_hint_for_round("play music", round_idx=1, step_count=0) == "fast"
    assert _route_hint_for_round("please explain this deeply?", round_idx=1, step_count=0) == "default"
    assert _route_hint_for_round("ok", round_idx=1, step_count=1) == "complex"


def test_speaking_reply_aborts_when_interrupt_check_fires() -> None:
    from mango.llm_tool_loop import speaking_reply

    class _FakeLlm:
        def chat(self, *_args, **_kwargs):
            raise AssertionError("LLM should not be called when interrupt fires first")

    class _FakeRegistry:
        def definitions(self):
            return []

    stats: dict[str, int] = {}
    out = speaking_reply(
        _FakeLlm(),
        _FakeRegistry(),
        [{"role": "user", "content": "hello"}],
        stats_out=stats,
        interrupt_check=lambda: True,
    )
    assert out == ""
    assert stats.get("interrupted") == 1
    assert _route_hint_for_round("ok", round_idx=2, step_count=0) == "complex"


def test_deterministic_tool_spoken_result_for_spotify_and_apps() -> None:
    spotify = _deterministic_tool_spoken_result(
        "spotify_play",
        {"query": "Bad Romance"},
        "spotify_play: TRACK_PLAYED: Bad Romance",
    )
    assert spotify is not None
    assert "bad romance" in spotify.casefold()

    opened = _deterministic_tool_spoken_result(
        "open_app",
        {"app_name": "Discord"},
        "Opened app Discord.",
    )
    assert opened == "All set. Discord is open."

    saved = _deterministic_tool_spoken_result(
        "memory_card",
        {"action": "add"},
        "Saved memory card abc123: Coffee preference",
    )
    assert saved is not None
    assert "coffee preference" in saved.casefold()
    assert "abc123" not in saved.casefold()
