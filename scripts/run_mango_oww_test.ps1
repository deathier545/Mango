# Start Mango with openWakeWord wake test defaults (prefers project .venv Python).
# Usage:
#   .\scripts\run_mango_oww_test.ps1 C:\path\to\model.onnx
#   .\scripts\run_mango_oww_test.ps1   # uses MANGO_OWW_MODELS from environment
# Extra args pass through to python -m mango.main (e.g. --wake-oww-score-only).

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

$pythonExe = $null
foreach ($candidate in @(
        (Join-Path $RepoRoot ".venv\Scripts\python.exe"),
        (Join-Path $RepoRoot "venv\Scripts\python.exe")
    )) {
    if (Test-Path -LiteralPath $candidate) {
        $pythonExe = $candidate
        break
    }
}
if (-not $pythonExe) {
    $pythonExe = "python"
}

$model = $env:MANGO_OWW_MODELS
$pass = @()
if ($args.Count -ge 1 -and ($args[0] -match '\.(onnx|tflite)$')) {
    $model = $args[0]
    if ($args.Count -gt 1) {
        $pass = $args[1..($args.Count - 1)]
    }
} else {
    $pass = @($args)
}

if (-not $model) {
    Write-Error "Set MANGO_OWW_MODELS or pass the path to your .onnx (or .tflite) as the first argument."
}

$env:MANGO_OWW_MODELS = $model
# Long intro TTS keeps pygame mixer busy; wake OWW skips the mic until playback ends.
if (-not $env:MANGO_STARTUP_INTRO) {
    $env:MANGO_STARTUP_INTRO = "0"
}

Write-Host "Using Python: $pythonExe"
Write-Host "MANGO_OWW_MODELS=$model"
if ($env:MANGO_STARTUP_INTRO -eq "0") {
    Write-Host "MANGO_STARTUP_INTRO=0 (wake mic not deferred for intro TTS; set MANGO_STARTUP_INTRO=1 to hear greeting)"
}
Write-Host "Launching: mango.main --wake-oww-only $($pass -join ' ')"

& $pythonExe -m mango.main @pass --wake-oww-only
