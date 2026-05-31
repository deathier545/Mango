from __future__ import annotations

from mango.wake.wake_phrase import compile_wake_phrase_regex, phrase_accepted


def test_phrase_accepted_true_when_phrase_near_start():
    re_phrase = compile_wake_phrase_regex("hey mango,hey mingo")
    assert phrase_accepted(
        "hey mango what's the weather",
        phrase_re=re_phrase,
        max_offset=16,
        suppress_active=False,
    )


def test_phrase_accepted_false_when_offset_too_far():
    re_phrase = compile_wake_phrase_regex("mango")
    assert not phrase_accepted(
        "uh hold on please mango",
        phrase_re=re_phrase,
        max_offset=5,
        suppress_active=False,
    )


def test_phrase_accepted_false_when_suppressed():
    re_phrase = compile_wake_phrase_regex("mango")
    assert not phrase_accepted(
        "mango",
        phrase_re=re_phrase,
        max_offset=32,
        suppress_active=True,
    )
