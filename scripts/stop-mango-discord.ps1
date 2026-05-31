$ErrorActionPreference = "Stop"

$found = $false
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match '-m mango' } |
    ForEach-Object {
        $found = $true
        Write-Host "Stopping Mango process $($_.ProcessId): $($_.CommandLine)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

if (-not $found) {
    Write-Host "No Mango or Discord bridge processes were running."
} else {
    Write-Host "Stopped Mango and Discord bridge processes."
}
