from __future__ import annotations

from mango.planner_executor import PlannerExecutorState


def test_planner_executor_marks_statuses():
    st = PlannerExecutorState()
    s1 = st.add_step(round_idx=1, tool_name="run_powershell", arguments={"command_key": "env_username"})
    st.mark_done(s1, "HOST_PENDING_POWERSHELL: not executed")
    s2 = st.add_step(round_idx=1, tool_name="phone_call", arguments={"contact": "ariana"})
    st.mark_done(s2, "PHONE_CALL_FAILED: missing number")
    s3 = st.add_step(round_idx=2, tool_name="spotify_play", arguments={"query": "x"})
    st.mark_done(s3, "Opened Spotify")

    assert s1.status == "needs_confirmation"
    assert s2.status == "failed"
    assert s3.status == "completed"
    assert "run_powershell:needs_confirmation" in st.compact_summary()
