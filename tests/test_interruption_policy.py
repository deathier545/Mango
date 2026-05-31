from __future__ import annotations

import importlib

import mango.interruption_policy as interruption_policy
from mango.interruption_policy import resolve_profile, should_trigger_barge_with_profile


def test_resolve_profile_defaults_to_normal():
    p = resolve_profile("unknown-profile")
    assert p.name == "normal"


def test_resolve_profile_fast_and_strict_thresholds():
    fast = resolve_profile("fast")
    strict = resolve_profile("strict")
    assert fast.min_barge_hold_ms < strict.min_barge_hold_ms
    assert fast.wake_wait_seconds < strict.wake_wait_seconds


def test_should_trigger_barge_with_profile_uses_profile_threshold():
    normal = resolve_profile("normal")
    assert should_trigger_barge_with_profile(normal, 89) is False
    assert should_trigger_barge_with_profile(normal, 90) is True


def test_profile_threshold_override_from_env(monkeypatch):
    with monkeypatch.context() as m:
        m.setenv("MANGO_BARGE_MIN_HOLD_MS_FAST", "55")
        importlib.reload(interruption_policy)
        fast = interruption_policy.resolve_profile("fast")
        assert fast.min_barge_hold_ms == 55
        assert interruption_policy.should_trigger_barge_with_profile(fast, 54) is False
        assert interruption_policy.should_trigger_barge_with_profile(fast, 55) is True
    importlib.reload(interruption_policy)
