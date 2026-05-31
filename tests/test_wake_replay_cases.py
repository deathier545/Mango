from __future__ import annotations

import numpy as np

from mango.wake.wake_audio_gates import wake_audio_gates_pass
from mango.wake.wake_phrase import compile_wake_phrase_regex, phrase_accepted


def test_wake_replay_style_cases():
    phrase_re = compile_wake_phrase_regex("hey mango,hey mingo")
    # Synthetic "replay-like" clips to guard tuning regressions without real mic IO.
    cases = [
        {
            "name": "clean_phrase",
            "audio": np.sin(np.linspace(0, 8.0, 2400, dtype=np.float32)) * 0.07,
            "text": "hey mango play music",
            "expect_gate": True,
            "expect_phrase": True,
        },
        {
            "name": "too_quiet",
            "audio": np.sin(np.linspace(0, 8.0, 2400, dtype=np.float32)) * 0.0007,
            "text": "hey mango",
            "expect_gate": False,
            "expect_phrase": True,
        },
        {
            "name": "late_phrase",
            "audio": np.sin(np.linspace(0, 8.0, 2400, dtype=np.float32)) * 0.06,
            "text": "uh give me one second hey mango",
            "expect_gate": True,
            "expect_phrase": False,
        },
    ]

    for case in cases:
        gate = wake_audio_gates_pass(
            case["audio"],
            rms_threshold=0.001,
            whisper_min_peak=0.002,
            whisper_min_std=0.002,
        )
        phrase_ok = phrase_accepted(
            case["text"],
            phrase_re=phrase_re,
            max_offset=12,
            suppress_active=False,
        )
        assert gate is case["expect_gate"], case["name"]
        assert phrase_ok is case["expect_phrase"], case["name"]
