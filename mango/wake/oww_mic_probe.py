"""Record from the default mic and print openWakeWord scores (no pygame / no LLM).

Use this to see whether a custom ONNX model reacts to your voice before debugging
hybrid Whisper or Mango's main loop:

    python -m mango --oww-mic-probe path/to/model.onnx
    python -m mango --oww-mic-probe   # uses MANGO_OWW_MODELS from the environment

Optional: ``MANGO_SD_INPUT_DEVICE`` (integer index) matches ``WakeWordListener``.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

import numpy as np

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    argv = [a for a in argv if a != "--oww-mic-probe"]

    p = argparse.ArgumentParser(
        description="Record mono 16 kHz audio and print per-frame OWW scores.",
    )
    p.add_argument(
        "model",
        nargs="?",
        default=os.getenv("MANGO_OWW_MODELS", "").strip() or None,
        help="Path to .onnx / .tflite or built-in key (default: MANGO_OWW_MODELS)",
    )
    p.add_argument(
        "--seconds",
        type=float,
        default=6.0,
        help="Recording length in seconds (default: 6)",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Report how many frames exceed this score (default: 0.5)",
    )
    p.add_argument(
        "--also",
        type=float,
        default=0.35,
        help="Second threshold line in the summary (default: 0.35)",
    )
    args = p.parse_args(argv)

    if not args.model:
        print(
            "Error: pass a model path or set MANGO_OWW_MODELS.\n"
            "  Example: python -m mango --oww-mic-probe C:\\path\\hey_man_go.onnx",
            file=sys.stderr,
        )
        return 2

    import mango.wake.oww_wake as oww_wake

    if not oww_wake.oww_import_ok():
        print("Error: openwakeword not installed (pip install openwakeword onnxruntime).", file=sys.stderr)
        return 1

    names = oww_wake.resolve_oww_model_names_for_wake([args.model], "mango")
    if not names:
        print("Error: no model resolved.", file=sys.stderr)
        return 2

    try:
        import sounddevice as sd
    except ImportError:
        print("Error: sounddevice not installed.", file=sys.stderr)
        return 1

    dev_raw = os.getenv("MANGO_SD_INPUT_DEVICE", "").strip()
    dev: int | None = int(dev_raw) if dev_raw.isdigit() else None
    try:
        default = sd.query_devices(kind="input")
        print(f"Default input device: {default.get('name', '?')!r}  index={default.get('index')}")
    except Exception as exc:
        print(f"(Could not query default input device: {exc})")

    n_frames = max(1, int(float(args.seconds) * oww_wake.OWW_SR))
    print(
        f"\nRecording {args.seconds:.1f}s @ {oww_wake.OWW_SR} Hz mono - speak your wake phrase clearly.\n"
        "Starting in 2 seconds...\n"
    )
    time.sleep(2.0)

    try:
        rec = sd.rec(
            n_frames,
            samplerate=oww_wake.OWW_SR,
            channels=1,
            dtype=np.float32,
            device=dev,
        )
        sd.wait()
    except Exception as exc:
        print(f"Error: microphone recording failed: {exc}", file=sys.stderr)
        return 1

    mono = np.asarray(rec, dtype=np.float32).reshape(-1)
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    rms = float(np.sqrt(np.mean(mono * mono))) if mono.size else 0.0
    print(f"Captured {mono.size} samples  peak_abs={peak:.4f}  rms={rms:.5f}")

    try:
        oww_wake.ensure_oww_models_downloaded(names)
        model = oww_wake.build_oww_model(
            names,
            inference_framework=os.getenv("MANGO_OWW_INFERENCE", "onnx").strip().lower() or "onnx",
            vad_threshold=float(os.getenv("MANGO_OWW_VAD_THRESHOLD", "0") or 0),
        )
    except Exception:
        logger.exception("openWakeWord model setup failed")
        return 1

    pad = (oww_wake.OWW_CHUNK - (mono.size % oww_wake.OWW_CHUNK)) % oww_wake.OWW_CHUNK
    if pad:
        mono = np.concatenate([mono, np.zeros(pad, dtype=np.float32)])

    buf = oww_wake.OwwPcm16Buffer(oww_wake.OWW_SR)
    scores: list[float] = []
    sample_pred_keys: set[str] | None = None
    for i in range(0, mono.size, oww_wake.OWW_CHUNK):
        chunk = mono[i : i + oww_wake.OWW_CHUNK]
        if chunk.size != oww_wake.OWW_CHUNK:
            break
        for pcm in buf.feed_float_mono(chunk):
            preds = model.predict(pcm)
            if sample_pred_keys is None and isinstance(preds, dict):
                sample_pred_keys = set(str(k) for k in preds.keys())
            scores.append(oww_wake.max_scalar_prediction(preds))

    if scores:
        arr = np.array(scores, dtype=np.float64)
        t_main = float(args.threshold)
        t_alt = float(args.also)
        above_main = int(np.sum(arr >= t_main))
        above_alt = int(np.sum(arr >= t_alt))
        print(f"\nModel: {names[0]!r}")
        if sample_pred_keys:
            print(f"Prediction keys (first frame): {sorted(sample_pred_keys)}")
        print(f"OWW frames: {len(scores)}  (~{len(scores) * 0.08:.2f}s of 80ms windows)")
        print(f"Score max={arr.max():.4f}  mean={arr.mean():.4f}  p95={np.percentile(arr, 95):.4f}")
        print(
            f"Frames >= {t_main:.2f}: {above_main}   "
            f"Frames >= {t_alt:.2f}: {above_alt}"
        )
        if arr.max() < t_alt:
            print(
                "\nInterpretation: scores stayed below the lower threshold - try speaking louder, "
                "closer to the trained phrase, MANGO_SD_INPUT_DEVICE if the wrong mic, "
                "or retrain with more real microphone clips."
            )
        elif arr.max() < t_main:
            print(
                f"\nInterpretation: model reacts (max {arr.max():.3f}) but default "
                f"MANGO_OWW_THRESHOLD ({t_main:.2f}) may be too high - try 0.35-0.45 in .env."
            )
        else:
            print(
                "\nInterpretation: OWW exceeded the main threshold on at least one frame - "
                "if Mango still ignores you, check hybrid Whisper (phrase / gates) or mixer-busy wake skips."
            )
    else:
        print("Error: no complete OWW frames produced (unexpected).", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
