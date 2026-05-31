# Wake word training ("mango")

Local copy of the **openWakeWord** training flow (same three steps as the Colab / `automatic_model_training.ipynb`).

## What’s in this folder

| Item | Purpose |
|------|--------|
| `notebooks/automatic_model_training.ipynb` | Full notebook (reference) |
| `notebooks/training_models.ipynb` | Manual / advanced training |
| `custom_model.yml` | Upstream template |
| `config/mango.yml` | **Phrase `mango`** — 30k examples, 20k steps, penalty 1500 |
| `config/mango-colab-settings.txt` | Your Colab numbers ↔ YAML field names |
| `scripts/01-generate-clips.sh` | Step 1 — synthetic TTS clips |
| `scripts/02-augment-clips.sh` | Step 2 — augment clips |
| `scripts/03-train-model.sh` | Step 3 — train + export ONNX |
| `scripts/00-download-data.sh` | Shared datasets (run once) |
| `scripts/setup-environment.sh` | Clone repos + Python venv |
| `run-*.ps1` | Run the above from **Windows via WSL2** |

## Important (Windows)

Piper TTS (clip generation) is **Linux-only** in upstream openWakeWord. On your PC:

- Use **WSL2** and the `run-*.ps1` scripts, **or**
- Keep using **Google Colab** and only copy the finished `.onnx` here.

Native Windows Python will **not** complete step 1 reliably.

## Training parameters (your settings)

| Colab UI | YAML (`config/mango.yml`) | Your value |
|----------|---------------------------|------------|
| `number_of_examples` | `n_samples` | **30000** |
| `number_of_training_steps` | `steps` | **20000** |
| `false_activation_penalty` | `max_negative_weight` | **1500** |

Validation clips (`n_samples_val`) are set to **6000** (~20% of 30k). Step 1 can take several hours on CPU; GPU/WSL helps.

## Quick start (WSL2)

From PowerShell in this folder:

```powershell
.\run-setup.ps1
.\run-download-data.ps1    # large downloads; can take a while
.\run-01-generate-clips.ps1
.\run-02-augment-clips.ps1
.\run-03-train-model.ps1
```

Or inside WSL:

```bash
cd "/mnt/c/Users/Dylan/jarvis/wake word"
bash scripts/setup-environment.sh
bash scripts/00-download-data.sh
bash scripts/01-generate-clips.sh
bash scripts/02-augment-clips.sh
bash scripts/03-train-model.sh
```

Trained model (expected):

`output/mango/mango.onnx`

## Wire into Mango

In jarvis `.env`:

```env
MANGO_WAKEWORD=1
MANGO_WAKE_ENGINE=hybrid
MANGO_OWW_MODELS=C:\Users\Dylan\jarvis\wake word\output\mango\mango.onnx
MANGO_WAKE_PHRASE=mango
MANGO_OWW_THRESHOLD=0.5
```

Restart Mango (Stop → Start).

## Colab (no WSL)

If you prefer the browser UI: [openWakeWord training Colab](https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb?usp=sharing)

Set `target_phrase` to `["mango"]` and save the `.onnx` into `output/mango/` here.

## More detail

See `mango/WAKE_OWW.md` in the main repo.
