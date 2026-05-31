"""Unit tests for openWakeWord phrase mapping (no model download)."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

import mango.wake.oww_wake as oww_wake
from mango.wake.oww_wake import (
    float32_mono_to_int16_16k,
    max_scalar_prediction,
    phrase_to_builtin_oww_models,
    resolve_oww_model_names_for_wake,
)
from mango.wake.wake_listener import compile_wake_phrase_regex


def test_phrase_builtin_alexa() -> None:
    assert phrase_to_builtin_oww_models("alexa") == ["alexa"]


def test_phrase_builtin_jarvis_variants() -> None:
    assert phrase_to_builtin_oww_models("hey jarvis") == ["hey_jarvis"]
    assert phrase_to_builtin_oww_models("Hey_Jarvis") == ["hey_jarvis"]
    assert phrase_to_builtin_oww_models("jarvis") == ["hey_jarvis"]


def test_phrase_builtin_mango_empty() -> None:
    assert phrase_to_builtin_oww_models("mango") == []


def test_compile_wake_phrase_regex_single() -> None:
    r = compile_wake_phrase_regex("mango")
    assert r.search("Yo, mango — lights")
    assert not r.search("mangosteen")


def test_compile_wake_phrase_regex_csv_alternatives() -> None:
    r = compile_wake_phrase_regex("hey mango, hey mingo")
    assert r.search("Hey mingo, turn on the lamp")
    assert r.search("hey mango please")
    assert not r.search("hey ming")


def test_resolve_explicit_overrides_phrase() -> None:
    assert resolve_oww_model_names_for_wake(["alexa"], "mango") == ["alexa"]


def test_resolve_expands_existing_file_in_repo_root(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(oww_wake, "_REPO_ROOT", tmp_path)
    f = tmp_path / "hey_man_go.onnx"
    f.write_bytes(b"\x00\x00")
    out = resolve_oww_model_names_for_wake(["hey_man_go.onnx"], "mango")
    assert out == [str(f.resolve())]


def test_ensure_download_builtin_only() -> None:
    with patch("openwakeword.utils.download_models") as dm:
        oww_wake.ensure_oww_models_downloaded(["alexa"])
        dm.assert_called_once_with(model_names=["alexa"])


def test_ensure_download_placeholder_when_only_weight_paths() -> None:
    with patch("openwakeword.utils.download_models") as dm:
        oww_wake.ensure_oww_models_downloaded([r"C:\no\such\custom.onnx"])
        dm.assert_called_once_with(model_names=["__mango_oww_features_only__"])


def test_ensure_download_mixed_builtin_and_onnx_path() -> None:
    with patch("openwakeword.utils.download_models") as dm:
        oww_wake.ensure_oww_models_downloaded(["alexa", r"C:\fake\wake.onnx"])
        dm.assert_called_once_with(model_names=["alexa"])


def test_float32_to_int16_same_rate() -> None:
    x = np.array([0.0, -1.0, 1.0], dtype=np.float32)
    y = float32_mono_to_int16_16k(x, 16_000)
    assert y.dtype == np.int16
    assert y.shape == (3,)


def test_max_scalar_prediction_numpy_float32() -> None:
    assert max_scalar_prediction({"w": np.float32(0.73)}) == pytest.approx(0.73)


def test_max_scalar_prediction_mixed_keys() -> None:
    assert max_scalar_prediction(
        {"a": np.float32(0.1), "b": 0.9, "c": np.array([[0.2, 0.5]])}
    ) == pytest.approx(0.9)


def test_max_scalar_prediction_ignores_bool() -> None:
    assert max_scalar_prediction({"x": True, "y": np.float32(0.4)}) == pytest.approx(0.4)
