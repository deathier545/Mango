#Requires -RunAsAdministrator
<#
  Installs WSL2 + Ubuntu for openWakeWord training (Piper needs Linux).
  Right-click PowerShell -> Run as administrator, then:
    Set-Location "C:\Users\Dylan\jarvis\wake word"
    .\install-wsl.ps1
  Reboot when prompted, then run:
    .\run-after-reboot.ps1
#>
$ErrorActionPreference = "Stop"

function Test-IsAdmin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
  Write-Host "ERROR: Run this script as Administrator." -ForegroundColor Red
  Write-Host "  Right-click PowerShell -> Run as administrator"
  exit 1
}

Write-Host "Enabling WSL optional features (may take a few minutes)..."
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Out-Null
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Out-Null

Write-Host "Installing WSL (default: Ubuntu)..."
wsl --install

Write-Host ""
Write-Host "=== REBOOT REQUIRED ===" -ForegroundColor Yellow
Write-Host "After reboot, open PowerShell in:"
Write-Host '  cd "C:\Users\Dylan\jarvis\wake word"'
Write-Host "  .\run-after-reboot.ps1"
Write-Host ""
$reboot = Read-Host "Reboot now? (y/N)"
if ($reboot -eq 'y' -or $reboot -eq 'Y') {
  Restart-Computer -Force
}
