# Start wake-word training (WSL background)
$here = $PSScriptRoot
$wslPath = (wsl wslpath -a $here).Trim()
$log = Join-Path $here "logs\pipeline.log"
New-Item -ItemType Directory -Force -Path (Join-Path $here "logs") | Out-Null

Write-Host "Installing system packages (root)..."
wsl -d Ubuntu -u root bash -lc "cd '$wslPath' && bash scripts/install-system-packages.sh" 2>&1 | Out-File -Append $log -Encoding utf8

Write-Host "Starting training pipeline in WSL..."
wsl -d Ubuntu bash -lc "cd '$wslPath' && sed -i 's/\r$//' scripts/*.sh go-start.sh 2>/dev/null; chmod +x go-start.sh scripts/*.sh; nohup bash go-start.sh >> logs/pipeline.log 2>&1 & echo started"

Write-Host "Log: $log"
Write-Host "Watch: Get-Content '$log' -Wait -Tail 25"
