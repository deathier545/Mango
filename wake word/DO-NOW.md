# Wake word — do it now

Phrase: **mango** · Config: 30k examples, 20k steps, penalty 1500

## Path A — Ubuntu (local, best if WSL works)

1. Open **Ubuntu** from the Start menu (finish username/password if asked).
2. Paste this **one command**:

```bash
cd "/mnt/c/Users/Dylan/jarvis/wake word" && bash scripts/run-all.sh
```

That runs setup → data → 3 training steps. Step 1 can take **many hours**.

When done (look for `output/mango/mango.onnx`), in **Windows PowerShell**:

```powershell
cd "C:\Users\Dylan\jarvis\wake word"
.\apply-mango-wake-env.ps1
```

Restart Mango (Stop → Start).

---

## Path B — Colab (if WSL hangs)

1. Open: https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb?usp=sharing
2. Set phrase **mango**, examples **30000**, steps **20000**, penalty **1500**
3. Run all cells; download `mango.onnx`
4. Save to: `C:\Users\Dylan\jarvis\wake word\output\mango\mango.onnx`
5. Run `.\apply-mango-wake-env.ps1`

---

## If WSL commands hang from PowerShell

Automated `wsl` checks may exit with code **4294967295** (WSL not responding). Fix:

1. **Reboot** the PC.
2. Open **Ubuntu** from Start menu; finish username/password if prompted.
3. In Ubuntu, run Path A’s `bash scripts/run-all.sh` command (do not rely on hung PowerShell `wsl` calls until this works: `wsl -d Ubuntu -e echo OK`).

If it still fails: **Settings → Apps → Installed apps → Ubuntu → Repair**, or `wsl --unregister Ubuntu` then `wsl --install -d Ubuntu` (Admin).

Data already on disk: `data/acav_complete.npy` (~16 GB), `data/validation_set_features.npy`
