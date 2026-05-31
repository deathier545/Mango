# Custom openWakeWord models in Mango

This note covers training a **custom** [openWakeWord](https://github.com/dscripka/openWakeWord) model (for example *“hey mango”*) and wiring it into Mango via **`MANGO_OWW_MODELS`** and **`MANGO_WAKE_ENGINE`**.

## How Mango uses openWakeWord (implemented)

Hands-free wake runs in `mango/wake_listener.py`:

- **`MANGO_WAKE_ENGINE=auto`** (default when wake is on): uses openWakeWord if `MANGO_OWW_MODELS` resolves (or the wake phrase maps to a built-in) **and** the `openwakeword` package imports; otherwise Whisper streaming/polled wake.
- **`openwakeword`**: OWW score only (no Whisper confirmation).
- **`hybrid`** (same as **auto** when models resolve): OWW score gate, then **Whisper** must match **`MANGO_WAKE_PHRASE`** (word-boundary regex in `WakeWordListener._phrase_accepted`).
- **`whisper`**: skips OWW; energy VAD or polled clips + Whisper only.

Helpers live in `mango/wake/oww_wake.py` (resampling to 16 kHz int16, model download, constants for hybrid buffer length). **`mango/config_build.py`** loads `MANGO_WAKE_ENGINE`, `MANGO_OWW_MODELS`, `MANGO_OWW_THRESHOLD`, `MANGO_OWW_VAD_THRESHOLD`, `MANGO_OWW_INFERENCE`, and resolves `wake_use_openwakeword` / `wake_oww_whisper_confirm`.

### Wake-related variables (quick reference)

| Variable | Role |
| -------- | ---- |
| `MANGO_WAKEWORD` | `1` / `true` / `yes` / `on` enables the wake thread. |
| `MANGO_WAKE_ENGINE` | `auto` \| `whisper` \| `openwakeword` \| `hybrid` |
| `MANGO_OWW_MODELS` | Comma-separated built-in keys (`hey_jarvis`, `alexa`, …) **or** paths to `.onnx` / `.tflite`. Relative paths resolve against **cwd**, then the **repo root**, if the file exists. |
| `MANGO_OWW_THRESHOLD` | Score threshold (clamped ~0.15–0.95 in config). |
| `MANGO_OWW_VAD_THRESHOLD` | Silero VAD inside openWakeWord; `0` = off. Try **0.45–0.55** to reduce false positives in noisy rooms. |
| `MANGO_OWW_INFERENCE` | `onnx` (default on Windows) \| `tflite` |
| `MANGO_WAKE_PHRASE` | Phrase for Whisper/hybrid confirmation (`\b…\b`, case-insensitive). Default `mango`. **Comma-separated** alternatives are allowed (e.g. `hey mango,hey mingo` → either match). |
| `MANGO_WAKE_PHRASE_MAX_OFFSET` | Reject phrase if match starts after this character index. |
| `MANGO_WAKE_STREAMING` | When wake is on and unset, defaults to match wake on/off. `0` = polled clips; `1` = stream+VAD (Whisper-only paths). |
| `MANGO_WAKE_WHISPER_MODEL` | Optional smaller Whisper for wake/hybrid confirm. |
| `MANGO_WAKE_RMS_THRESHOLD`, `MANGO_WAKE_WHISPER_MIN_PEAK`, `MANGO_WAKE_WHISPER_MIN_STD` | Gates before hybrid Whisper runs (same as streaming wake). |
| `MANGO_SD_INPUT_DEVICE` | Optional sounddevice input index. |
| `MANGO_SAMPLE_RATE` | Mic rate (default 16000; clamped 8000–48000). |

Hybrid mode keeps roughly **3.2 s** of recent 16 kHz audio for Whisper after an OWW hit (see `OWW_HYBRID_RING_MAXLEN` / `OWW_HYBRID_WHISPER_TAIL_SEC` in `oww_wake.py`). After a successful wake, the OWW loop sleeps **~1.25 s** to debounce echo/double triggers.

---

## Local training folder (this repo)

Scripts and config for the three notebook training steps live in **`wake word/`** at the repo root:

- `run-setup.ps1` → WSL environment
- `run-download-data.ps1` → shared datasets
- `run-01-generate-clips.ps1` / `run-02-augment-clips.ps1` / `run-03-train-model.ps1`
- `config/mango.yml` → target phrase **`mango`**

See `wake word/README.md`.

## Official training resources

- **Training overview:** [Training New Models](https://github.com/dscripka/openWakeWord#training-new-models)
- **Colab:** [openWakeWord training Colab](https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb?usp=sharing)
- **Notebook:** [automatic_model_training.ipynb](https://github.com/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb)
- **Example YAML:** [examples/custom_model.yml](https://github.com/dscripka/openWakeWord/blob/main/examples/custom_model.yml)

### Colab troubleshooting (common)

- **`onnx_tf` / TensorFlow optional:** Training stacks sometimes mention optional TF ONNX tooling; if a cell fails on TF-only steps, prefer the notebook’s **pure ONNX export** path or install only what that cell documents. Do not assume every optional extra is required for a minimal `.onnx` wake model.
- **AudioSet / external data 404:** Cached URLs for large negative corpora can move; retry later, mirror from the openWakeWord issue tracker, or point the notebook at local negatives if the upstream cell supports it.
- **`speex` / SpeexDSP optional:** openWakeWord can use Speex noise suppression **if** the optional library is installed; Mango leaves Speex off in the default `Model(...)` path. Missing `speexdsp` is normal unless you enable it in upstream code yourself.
- **pip dependency conflicts:** Colab preinstalls many packages. Prefer a **fresh venv** locally for reproducible exports, or use `pip install ... --no-deps` only when you understand the conflict. Pin `onnxruntime` / `openwakeword` to versions you actually run in Mango.

---

## Audio format for openWakeWord streaming

Inference expects **16-bit PCM, 16 kHz, mono** in **80 ms** chunks (1280 samples). Mango resamples the mic to int16 @ 16 kHz before `Model.predict` (see `OwwPcm16Buffer` and `float32_mono_to_int16_16k`).

---

## Tuning checklist

1. **`MANGO_OWW_THRESHOLD`** — Start near **0.5**; raise to reduce false accepts (more false rejects), lower for the opposite.
2. **`MANGO_OWW_VAD_THRESHOLD`** — Leave at **0** for quiet rooms; try **0.5** when TV/background speech fires OWW too often.
3. **Hybrid vs OWW-only** — `MANGO_WAKE_ENGINE=hybrid` (or `auto` with models + Whisper confirm) adds latency but cuts many false wakes; tune phrase gates (`MANGO_WAKE_WHISPER_MIN_*`) if Whisper rejects real wakes.
4. **Distant mic (Whisper streaming wake)** — Lower `MANGO_WAKE_STREAM_SPEECH_HI_FLOOR` / `MANGO_WAKE_STREAM_SPEECH_HI_MULT` so RMS can cross “speech started” without eating the mic; lower `MANGO_WAKE_WHISPER_MIN_PEAK` / `MIN_STD` cautiously (more false Whisper runs). Also raise Windows input volume and confirm `MANGO_SD_INPUT_DEVICE` if you have multiple mics.
5. **Custom ONNX name vs phrase** — A model file like `hey_man_go.onnx` loads by **path**; openWakeWord uses the **basename stem** (`hey_man_go`) internally for predictions. **`MANGO_WAKE_PHRASE` must still be what Whisper can hear** (e.g. `hey mango` or `mango`). Align training targets, your spoken habit, and the regex phrase; hybrid does **not** replace phrase text with the filename.
6. **`MANGO_WAKE_PHRASE_MAX_OFFSET`** — If Whisper often prefixes filler (“uh, mango”), increase slightly; if it accepts long ramble before the phrase, decrease.

---

## Example `.env` blocks

### openWakeWord + hybrid (custom ONNX)

```env
MANGO_WAKEWORD=1
MANGO_WAKE_ENGINE=hybrid
MANGO_OWW_MODELS=C:\Users\You\models\hey_man_go.onnx
MANGO_OWW_THRESHOLD=0.55
MANGO_OWW_VAD_THRESHOLD=0.5
MANGO_WAKE_PHRASE=hey mango
MANGO_WAKE_WHISPER_MODEL=tiny.en
MANGO_SAMPLE_RATE=16000
```

### Built-in model, OWW only (no Whisper confirm)

```env
MANGO_WAKEWORD=1
MANGO_WAKE_ENGINE=openwakeword
MANGO_OWW_MODELS=hey_jarvis
MANGO_OWW_THRESHOLD=0.5
```

### Whisper-only wake (no OWW)

```env
MANGO_WAKEWORD=1
MANGO_WAKE_ENGINE=whisper
MANGO_WAKE_PHRASE=mango
MANGO_WAKE_STREAMING=1
MANGO_WHISPER_MODEL=base.en
MANGO_WAKE_WHISPER_MODEL=tiny.en
```

---

## See also

- `mango/wake_listener.py` — capture, OWW loop, hybrid Whisper, phrase gate.
- `mango/oww_wake.py` — downloads, resampling, hybrid buffer constants.
- `mango/config.py` — env parsing for wake / OWW.
- `.env.example` — commented template.
