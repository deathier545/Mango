# Copy completed 16GB .part file to acav_complete.npy (avoids locked partial .npy)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$data = Join-Path $Root "data"
$part = Join-Path $data "openwakeword_features_ACAV100M_2000_hrs_16bit.npy.part"
$dest = Join-Path $data "acav_complete.npy"
$minBytes = 15GB

if (Test-Path $dest) {
  $len = (Get-Item -LiteralPath $dest).Length
  if ($len -ge $minBytes) {
    Write-Host "acav_complete.npy OK: $([math]::Round($len/1GB,2)) GB"
    exit 0
  }
}

if (-not (Test-Path -LiteralPath $part)) {
  Write-Host "Missing: $part"
  Write-Host "Run: .\run-download-acav.ps1"
  exit 1
}

$partLen = (Get-Item -LiteralPath $part).Length
if ($partLen -lt $minBytes) {
  Write-Host "Part file incomplete: $([math]::Round($partLen/1GB,2)) GB - wait for download or run ensure-acav-download.ps1"
  exit 1
}

Write-Host "Copying $([math]::Round($partLen/1GB,2)) GB to acav_complete.npy (few minutes)..."
Copy-Item -LiteralPath $part -Destination $dest -Force
Write-Host "Done: $dest"
