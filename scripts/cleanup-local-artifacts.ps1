# Remove common local runtime artifacts generated during Mango development.
# Usage:
#   ./scripts/cleanup-local-artifacts.ps1              # dry run
#   ./scripts/cleanup-local-artifacts.ps1 -Apply       # actually delete

param(
    [switch]$Apply
)

Set-Location (Split-Path -Parent $PSScriptRoot)

$targets = @(
    ".pytest_cache",
    "logs\*.log",
    "logs\*.txt",
    "__pycache__"
)

Write-Host "Mango cleanup targets:" -ForegroundColor Cyan
$targets | ForEach-Object { Write-Host "  - $_" }

$allMatches = @()
foreach ($pattern in $targets) {
    $matches = Get-ChildItem -Path $pattern -Recurse -Force -ErrorAction SilentlyContinue
    if ($matches) {
        $allMatches += $matches
    }
}

if (-not $allMatches -or $allMatches.Count -eq 0) {
    Write-Host "Nothing to clean." -ForegroundColor Green
    exit 0
}

if (-not $Apply) {
    Write-Host "`nDry run (no deletions). Use -Apply to remove:" -ForegroundColor Yellow
    $allMatches | ForEach-Object { Write-Host "  $($_.FullName)" }
    exit 0
}

Write-Host "`nDeleting artifacts..." -ForegroundColor Yellow
foreach ($item in $allMatches | Sort-Object FullName -Unique) {
    try {
        if ($item.PSIsContainer) {
            Remove-Item -Path $item.FullName -Recurse -Force -ErrorAction Stop
        }
        else {
            Remove-Item -Path $item.FullName -Force -ErrorAction Stop
        }
        Write-Host "  removed $($item.FullName)"
    }
    catch {
        Write-Warning "Could not remove $($item.FullName): $($_.Exception.Message)"
    }
}

Write-Host "`nCleanup complete." -ForegroundColor Green
