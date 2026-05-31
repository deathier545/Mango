# Start wake-word training in WSL (detached). Log: logs\pipeline.log
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$log = Join-Path $here "logs\pipeline.log"
New-Item -ItemType Directory -Force -Path (Join-Path $here "logs") | Out-Null
$wslPath = (wsl wslpath -a $here).Trim()

# Stop a stuck prior run (same folder only)
wsl -d Ubuntu bash -lc "cd '$wslPath' && pkill -f 'bash scripts/run-all.sh' 2>/dev/null || true"

Write-Host "System packages (root)..."
wsl -d Ubuntu -u root bash -lc "cd '$wslPath' && sed -i 's/\r$//' scripts/*.sh 2>/dev/null; chmod +x scripts/*.sh; bash scripts/install-system-packages.sh" | Out-File -FilePath $log -Encoding utf8

Write-Host "Starting pipeline in WSL background..."
$start = @"
cd '$wslPath'
sed -i 's/\r$//' scripts/*.sh 2>/dev/null
chmod +x scripts/*.sh
bash scripts/clean-junk.sh 2>/dev/null || true
: > logs/pipeline.log
nohup bash scripts/run-all.sh >> logs/pipeline.log 2>&1 &
echo pid=\$!
"@
wsl -d Ubuntu bash -lc $start
Write-Host "Log: $log"
Write-Host "Watch: Get-Content '$log' -Wait -Tail 25"
