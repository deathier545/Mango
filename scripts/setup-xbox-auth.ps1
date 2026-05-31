$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$EnvPath = Join-Path $Root ".env"

if (-not (Test-Path $Python)) {
    throw "Missing virtualenv Python at $Python. Run setup/install first."
}

if (Test-Path $EnvPath) {
    Get-Content $EnvPath | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or $line -notmatch "=") {
            return
        }
        $name, $value = $line.Split("=", 2)
        if ($name -and $null -ne $value) {
            [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), "Process")
        }
    }
}

$TokenPath = $env:XBOX_TOKENS_PATH
if (-not $TokenPath) {
    $TokenPath = Join-Path $env:USERPROFILE ".mango\xbox_tokens.json"
}

$TokenDir = Split-Path -Parent $TokenPath
New-Item -ItemType Directory -Force -Path $TokenDir | Out-Null

$argsList = @("-m", "xbox.webapi.scripts.authenticate", "--tokens", $TokenPath)

if ($env:XBOX_CLIENT_ID) {
    $argsList += @("--client-id", $env:XBOX_CLIENT_ID)
}
if ($env:XBOX_CLIENT_SECRET) {
    $argsList += @("--client-secret", $env:XBOX_CLIENT_SECRET)
}
if ($env:XBOX_REDIRECT_URI) {
    $argsList += @("--redirect-uri", $env:XBOX_REDIRECT_URI)
}

Write-Host "Starting Xbox sign-in. A browser window should open."
Write-Host "Token file: $TokenPath"
& $Python $argsList
