# Create a Desktop shortcut to run-desktop.ps1 (Windows).
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$target = Join-Path $repo "run-desktop.ps1"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Mango.lnk"

$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut($shortcutPath)
$sc.TargetPath = "powershell.exe"
$sc.Arguments = "-NoExit -ExecutionPolicy Bypass -File `"$target`""
$sc.WorkingDirectory = $repo
$sc.WindowStyle = 1
$sc.Description = "Mango voice assistant (desktop)"
$sc.Save()

Write-Host "Created: $shortcutPath" -ForegroundColor Green
