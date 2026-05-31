param([string]$Distro = "Ubuntu")
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$wslPath = (wsl -d $Distro wslpath -a $here).Trim()
wsl -d $Distro bash -lc "cd '$wslPath' && sed -i 's/\r$//' scripts/*.sh 2>/dev/null; chmod +x scripts/*.sh && bash scripts/setup-environment.sh"
