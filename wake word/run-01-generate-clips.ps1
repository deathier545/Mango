param([string]$Config = "config/mango.yml")
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$wslPath = (wsl wslpath -a $here).Trim()
wsl bash -lc "cd '$wslPath' && source .venv-train/bin/activate && bash scripts/01-generate-clips.sh '$Config'"
