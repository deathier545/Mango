"""openWakeWord helpers: model resolution, downloads, and 16 kHz int16 PCM prep."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

OWW_SR = 16_000
OWW_CHUNK = 1280  # 80 ms @ 16 kHz (openWakeWord frame size)
# Hybrid Whisper confirm: keep enough pre-trigger audio for short phrases (~3.2 s).
OWW_HYBRID_RING_MAXLEN = 40  # 40 * 80 ms @ 16 kHz
OWW_HYBRID_WHISPER_TAIL_SEC = 3.2

_REPO_ROOT = Path(__file__).resolve().parent.parent


def oww_import_ok() -> bool:
    try:
        import openwakeword  # noqa: F401
    except ImportError:
        return False
    return True


def phrase_to_builtin_oww_models(phrase: str) -> list[str]:
    """Map MANGO_WAKE_PHRASE to bundled openWakeWord model keys (no *mango* builtin)."""
    p = (phrase or "").strip().lower()
    p2 = p.replace(" ", "_").replace("-", "_")
    if p == "alexa" or p2 == "alexa":
        return ["alexa"]
    if p2 in ("hey_mycroft", "heymycroft") or p.startswith("hey mycroft"):
        return ["hey_mycroft"]
    # openWakeWord built-in model id is hey_jarvis; phrase aliases still map for convenience.
    if p2 in ("hey_jarvis", "heyjarvis") or p.startswith("hey jarvis"):
        return ["hey_jarvis"]
    if p == "jarvis":
        return ["hey_jarvis"]
    if p2 in ("hey_rhasspy", "heyrhasspy") or p.startswith("hey rhasspy"):
        return ["hey_rhasspy"]
    if p2 == "timer" or ("timer" in p and p.startswith("set a ")):
        return ["timer"]
    if "weather" in p:
        return ["weather"]
    return []


def expand_oww_model_path(name: str) -> str:
    """Turn relative paths into absolute files when they exist (cwd, then repo root)."""
    s = (name or "").strip()
    if not s:
        return s
    p = Path(s)
    expanded = p.expanduser()
    if expanded.is_file():
        return str(expanded.resolve())
    rel = _REPO_ROOT / s
    if rel.is_file():
        return str(rel.resolve())
    return s


def resolve_oww_model_names_for_wake(explicit: list[str], phrase: str) -> list[str]:
    """Prefer MANGO_OWW_MODELS entries; otherwise infer from wake phrase."""
    if explicit:
        return list(dict.fromkeys(expand_oww_model_path(x) for x in explicit if x.strip()))
    return phrase_to_builtin_oww_models(phrase)


def _oww_entry_needs_hub_download(name: str) -> bool:
    """Built-in hub keys only; skip file paths so openWakeWord.utils.download_models is not misled."""
    n = (name or "").strip()
    if not n:
        return False
    if os.path.isfile(os.path.expanduser(n)):
        return False
    suf = Path(n).suffix.lower()
    if suf in (".onnx", ".tflite"):
        return False
    return True


def ensure_oww_models_downloaded(model_names: list[str]) -> None:
    """Download embedding/melspec/VAD and requested built-in wake models (idempotent).

    Custom ``*.onnx`` / ``*.tflite`` paths are skipped here (nothing to fetch from the
    openWakeWord release assets); feature + VAD weights are still ensured.
    """
    import openwakeword.utils as oww_utils

    keys = [n for n in model_names if _oww_entry_needs_hub_download(n)]
    # download_models([]) pulls *all* official wakewords; use a non-matching placeholder
    # so only shared feature/VAD models are refreshed when everything is custom paths.
    _PLACEHOLDER_NO_MATCH = "__mango_oww_features_only__"
    oww_utils.download_models(model_names=keys if keys else [_PLACEHOLDER_NO_MATCH])


def float32_mono_to_int16_16k(mono_f32: np.ndarray, sr_in: int) -> np.ndarray:
    """Resample float32 mono [-1, 1] to 16 kHz int16 PCM (openWakeWord input)."""
    x = np.asarray(mono_f32, dtype=np.float64).ravel()
    if x.size == 0:
        return np.array([], dtype=np.int16)
    x = np.clip(x, -1.0, 1.0)
    if sr_in == OWW_SR:
        return (x * 32767.0).astype(np.int16)
    n_out = max(1, int(round(x.size * OWW_SR / float(sr_in))))
    t_in = np.linspace(0.0, 1.0, num=x.size, endpoint=False)
    t_out = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    y = np.interp(t_out, t_in, x)
    y = np.clip(y, -1.0, 1.0)
    return (y * 32767.0).astype(np.int16)


def int16_16k_to_float32_for_whisper(i16: np.ndarray, sr_out: int) -> np.ndarray:
    """int16 mono @16 kHz → float32 mono @ sr_out for Whisper."""
    x = i16.astype(np.float64).ravel() / 32768.0
    if sr_out == OWW_SR:
        return x.astype(np.float32)
    n_out = max(1, int(round(x.size * float(sr_out) / OWW_SR)))
    t_in = np.linspace(0.0, 1.0, num=x.size, endpoint=False)
    t_out = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    y = np.interp(t_out, t_in, x)
    return y.astype(np.float32)


def build_oww_model(
    model_names: list[str],
    *,
    inference_framework: str = "onnx",
    vad_threshold: float = 0.0,
) -> Any:
    from openwakeword.model import Model

    return Model(
        wakeword_models=list(model_names),
        inference_framework=inference_framework,
        vad_threshold=vad_threshold,
    )


def max_scalar_prediction(preds: dict[Any, Any]) -> float:
    """Best scalar score from an openWakeWord ``predict`` dict.

    ONNX / numpy often returns ``np.float32`` scores, which are not instances of
    ``float`` — ignoring them made custom models look permanently silent.
    """
    best = 0.0
    for v in preds.values():
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            best = max(best, float(v))
            continue
        if isinstance(v, np.generic):
            best = max(best, float(np.asarray(v).item()))
            continue
        if isinstance(v, np.ndarray) and v.size:
            best = max(best, float(np.max(v.astype(np.float64, copy=False))))
    return best


class OwwPcm16Buffer:
    """Accumulate resampled int16 @16 kHz and slice into OWW_CHUNK frames."""

    def __init__(self, sr_in: int) -> None:
        self._sr_in = sr_in
        self._pcm16 = np.array([], dtype=np.int16)

    def feed_float_mono(self, mono_f32: np.ndarray) -> list[np.ndarray]:
        self._pcm16 = np.concatenate(
            [self._pcm16, float32_mono_to_int16_16k(mono_f32, self._sr_in)]
        )
        out: list[np.ndarray] = []
        while self._pcm16.size >= OWW_CHUNK:
            out.append(self._pcm16[:OWW_CHUNK].copy())
            self._pcm16 = self._pcm16[OWW_CHUNK:]
        return out

    def tail_int16(self, max_samples: int) -> np.ndarray:
        if self._pcm16.size == 0:
            return np.array([], dtype=np.int16)
        n = min(max_samples, self._pcm16.size)
        return self._pcm16[-n:].copy()

    def all_int16(self) -> np.ndarray:
        return self._pcm16.copy()

    def clear(self) -> None:
        self._pcm16 = np.array([], dtype=np.int16)
