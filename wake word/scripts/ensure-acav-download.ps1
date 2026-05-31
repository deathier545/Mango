# Ensure ~16GB ACAV features file is complete (resume-friendly)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$data = Join-Path $Root "data"
New-Item -ItemType Directory -Force -Path $data | Out-Null

$final = Join-Path $data "openwakeword_features_ACAV100M_2000_hrs_16bit.npy"
$part = "$final.part"
$url = "https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/openwakeword_features_ACAV100M_2000_hrs_16bit.npy"
$minBytes = 15GB

if (Test-Path $final) {
  $len = (Get-Item $final).Length
  if ($len -ge $minBytes) {
    Write-Host "ACAV features OK: $([math]::Round($len/1GB,2)) GB"
    exit 0
  }
  Write-Host "ACAV file too small ($len bytes), re-downloading..."
  Remove-Item -Force $final -ErrorAction SilentlyContinue
}

Write-Host "Downloading ACAV features (~16 GB). This can take 30-90+ minutes..."
Write-Host "  $final"
curl.exe -L -C - -o $part $url
if ($LASTEXITCODE -ne 0) { throw "curl failed with exit $LASTEXITCODE" }

Move-Item -Force $part $final
$len = (Get-Item $final).Length
Write-Host "Download complete: $([math]::Round($len/1GB,2)) GB"
