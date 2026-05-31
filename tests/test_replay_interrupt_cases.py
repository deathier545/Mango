from __future__ import annotations

from mango.interruption_policy import should_trigger_barge


def test_replay_interrupt_cases_across_profiles():
    # Synthetic replay-style interruption durations (ms).
    durations = [15, 40, 95, 230]
    strict = [should_trigger_barge("strict", d) for d in durations]
    normal = [should_trigger_barge("normal", d) for d in durations]
    fast = [should_trigger_barge("fast", d) for d in durations]

    assert strict == [False, False, False, True]
    assert normal == [False, False, True, True]
    assert fast == [False, True, True, True]
