from __future__ import annotations

import numpy as np

from mango.wake.wake_audio_gates import rms, wake_audio_gates_pass


def test_rms_zero_for_empty():
    assert rms(np.array([], dtype=np.float32)) == 0.0


def test_wake_audio_gates_pass_for_strong_signal():
    mono = np.array([0.0, 0.2, -0.2, 0.15, -0.1], dtype=np.float32)
    assert wake_audio_gates_pass(
        mono,
        rms_threshold=0.01,
        whisper_min_peak=0.05,
        whisper_min_std=0.01,
    )


def test_wake_audio_gates_fail_for_too_quiet_signal():
    mono = np.array([0.001, -0.001, 0.0012, -0.0011], dtype=np.float32)
    assert not wake_audio_gates_pass(
        mono,
        rms_threshold=0.01,
        whisper_min_peak=0.002,
        whisper_min_std=0.0001,
    )


def test_wake_audio_gates_fail_for_flat_signal():
    mono = np.array([0.03, 0.03, 0.03, 0.03], dtype=np.float32)
    assert not wake_audio_gates_pass(
        mono,
        rms_threshold=0.0,
        whisper_min_peak=0.01,
        whisper_min_std=0.01,
    )
