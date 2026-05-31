param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("generate_clips", "augment_clips", "train_model")]
  [string]$Step,
  [string]$Config = "config/mango.yml"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$py = Join-Path $Root ".venv-train\Scripts\python.exe"
$train = Join-Path $Root "vendor\openwakeword\openwakeword\train.py"
if (-not (Test-Path $py)) { throw "Run setup-environment.ps1 first" }
$flag = "--$Step"
Write-Host "=== $Step ===" 
& $py $train --training_config $Config $flag
