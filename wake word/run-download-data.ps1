$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$wslPath = (wsl wslpath -a $here).Trim()
wsl bash -lc "cd '$wslPath' && sed -i 's/\r$//' scripts/*.sh && chmod +x scripts/*.sh && bash scripts/00-download-data.sh"
