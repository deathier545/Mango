# Train "mango" wake word — start here

## Fastest path (you need Admin once)

1. **Right-click PowerShell → Run as administrator**
2. ```powershell
   cd "C:\Users\Dylan\jarvis\wake word"
   .\install-wsl.ps1
   ```
3. **Reboot** when prompted
4. Normal PowerShell:
   ```powershell
   cd "C:\Users\Dylan\jarvis\wake word"
   .\run-after-reboot.ps1
   ```
   (Step 1 alone may run **many hours** for 30,000 clips.)

5. When finished:
   ```powershell
   .\apply-mango-wake-env.ps1
   ```
   Restart Mango in Mango Console.

## Data already on disk

- `validation_set_features.npy` — ready
- `openwakeword_features_...npy.part` — **16 GB complete** → run `.\scripts\finalize-acav.ps1` to copy to `acav_complete.npy`

## Colab instead of WSL

[Training Colab](https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb?usp=sharing)  
Settings: **30000** examples, **20000** steps, **1500** penalty, phrase **`mango`**.  
Download `mango.onnx` → `wake word\output\mango\mango.onnx` → `.\apply-mango-wake-env.ps1`
