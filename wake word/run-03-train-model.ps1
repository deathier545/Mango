param([string]$Config = "config/mango.yml")
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$wslPath = (wsl wslpath -a $here).Trim()
wsl bash -lc "cd '$wslPath' && source .venv-train/bin/activate && bash scripts/03-train-model.sh '$Config'"

Write-Host ""
Write-Host "If training succeeded, copy the ONNX into Mango .env, e.g.:"
Write-Host "  MANGO_OWW_MODELS=$here\output\mango\mango.onnx"
Write-Host "  MANGO_WAKE_PHRASE=mango"
