# Wake word training status

**Phrase:** `mango` (not hey mango)  
**Config:** `config/mango.yml` — 30,000 examples, 20,000 steps, false_activation_penalty 1500

## Data files

| File | Target size | Status |
|------|-------------|--------|
| `data/validation_set_features.npy` | ~176 MB | **Ready** |
| `data/acav_complete.npy` | ~16 GB | **Ready** |
| `data/mit_rirs` | small | WSL download step |
| `data/fma` | ~1 hr clips | WSL download step |

## Training (requires WSL)

Windows cannot run Step 1 (needs `piper-phonemize` + `webrtcvad` on Linux).

### One-time (Administrator)

```powershell
cd "C:\Users\Dylan\jarvis\wake word"
.\install-wsl.ps1
# Reboot when prompted
```

### After reboot

```powershell
cd "C:\Users\Dylan\jarvis\wake word"
.\run-after-reboot.ps1
```

That runs setup → data → generate_clips → augment → train (~many hours for 30k clips).

### Or step-by-step in WSL

```powershell
.\run-setup.ps1
.\run-download-data.ps1
.\run-01-generate-clips.ps1
.\run-02-augment-clips.ps1
.\run-03-train-model.ps1
.\apply-mango-wake-env.ps1
```

## Colab shortcut

[openWakeWord Colab](https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb?usp=sharing) — 30k / 20k / 1500, phrase `mango`.  
Save `mango.onnx` to `output\mango\mango.onnx`, then:

```powershell
.\apply-mango-wake-env.ps1
```

## Output

`wake word\output\mango\mango.onnx` → wired via `apply-mango-wake-env.ps1` to jarvis `.env`
