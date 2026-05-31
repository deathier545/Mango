# Patch Mango repo .env for custom mango.onnx wake word when the model exists.
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$RepoRoot = Split-Path -Parent $Root
$OnnxCandidates = @(
  (Join-Path $Root "output\mango\mango.onnx"),
  (Join-Path $Root "output\mango\mango\mango.onnx"),
  (Join-Path $Root "my_custom_model\mango\mango.onnx")
)

$onnx = $null
foreach ($c in $OnnxCandidates) {
  if (Test-Path $c) { $onnx = (Resolve-Path $c).Path; break }
}
if (-not $onnx) {
  Get-ChildItem -Path (Join-Path $Root "output") -Filter "mango.onnx" -Recurse -ErrorAction SilentlyContinue |
    Select-Object -First 1 |
    ForEach-Object { $onnx = $_.FullName }
}

if (-not $onnx) {
  Write-Host "No mango.onnx found yet. Train first or copy Colab export to:" -ForegroundColor Yellow
  Write-Host "  $Root\output\mango\mango.onnx"
  exit 1
}

$envFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $envFile)) {
  Write-Host "Creating $envFile"
  New-Item -ItemType File -Path $envFile -Force | Out-Null
}

$lines = @(Get-Content $envFile -ErrorAction SilentlyContinue)
$wanted = @{
  "MANGO_WAKEWORD"           = "1"
  "MANGO_WAKE_ENGINE"        = "openwakeword"
  "MANGO_OWW_MODELS"         = $onnx
  "MANGO_WAKE_PHRASE"        = "mango"
  "MANGO_OWW_THRESHOLD"      = "0.5"
}
$keys = $wanted.Keys
$newLines = [System.Collections.Generic.List[string]]::new()
$seen = @{}

foreach ($line in $lines) {
  if ($line -match '^\s*#' -or $line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=') {
    $newLines.Add($line)
    continue
  }
  $key = $Matches[1]
  if ($keys -contains $key) {
    $newLines.Add("$key=$($wanted[$key])")
    $seen[$key] = $true
  } else {
    $newLines.Add($line)
  }
}

foreach ($key in $keys) {
  if (-not $seen[$key]) {
    $newLines.Add("$key=$($wanted[$key])")
  }
}

# Remove old hey mango phrase comment block duplication — keep file valid
$out = ($newLines -join "`n").TrimEnd() + "`n"
Set-Content -Path $envFile -Value $out -Encoding utf8

Write-Host "Updated $envFile" -ForegroundColor Green
Write-Host "  MANGO_OWW_MODELS=$onnx"
Write-Host "  MANGO_WAKE_PHRASE=mango"
Write-Host ""
Write-Host "Restart Mango (Stop -> Start in Mango Console)."
