param(
    [switch]$Restart,
    [switch]$NoDiscordBridge,
    [switch]$NoMango
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$FfmpegLinks = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"
$LogDir = Join-Path $Root "logs"

if (-not (Test-Path $Python)) {
    throw "Missing virtualenv Python at $Python. Run setup/install first."
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (Test-Path $FfmpegLinks) {
    $env:Path = "$FfmpegLinks;$env:Path"
}

function Stop-MangoProcesses {
    Get-CimInstance Win32_Process |
        Where-Object { $_.CommandLine -match '-m mango' } |
        ForEach-Object {
            Write-Host "Stopping Mango process $($_.ProcessId)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

function Start-MangoProcess {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [string]$LogName
    )

    $logPath = Join-Path $LogDir $LogName
    $errPath = Join-Path $LogDir ($LogName -replace '\.log$', '.err.log')
    $argList = @("-m", "mango") + $Arguments
    Write-Host "Starting $Name -> $logPath"
    Start-Process -FilePath $Python -ArgumentList $argList -WorkingDirectory $Root -RedirectStandardOutput $logPath -RedirectStandardError $errPath -WindowStyle Minimized
}

if ($Restart) {
    Stop-MangoProcesses
}

if (-not $NoDiscordBridge) {
    Start-MangoProcess -Name "Discord voice bridge" -Arguments @("--discord-voice") -LogName "discord-voice.log"
}

if (-not $NoMango) {
    Start-MangoProcess -Name "Mango assistant" -Arguments @() -LogName "mango.log"
}

Write-Host "Done. Use -Restart to stop existing Mango processes before launching."
