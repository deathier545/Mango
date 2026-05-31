# Connect this Mango folder to GitHub: https://github.com/deathier545/Mango
#
# Usage:
#   .\scripts\connect-github.ps1              # init + remote only
#   .\scripts\connect-github.ps1 -Push        # also commit (if needed) and push
#   .\scripts\connect-github.ps1 -Push -Message "Initial commit"

param(
    [switch]$Push,
    [string]$Message = "Initial Mango commit",
    [string]$RemoteUrl = "https://github.com/deathier545/Mango.git",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

function Step([string]$Text) { Write-Host $Text -ForegroundColor Cyan }
function Ok([string]$Text)   { Write-Host $Text -ForegroundColor Green }
function Warn([string]$Text) { Write-Host $Text -ForegroundColor Yellow }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not on PATH. Install from https://git-scm.com/download/win"
}

if (Test-Path .env) {
    Warn "Reminder: .env is gitignored - do not commit API keys."
}

if (-not (Test-Path .git)) {
    Step "Initializing git repository..."
    & git init -b $Branch
    if ($LASTEXITCODE -ne 0) { throw "git init failed" }
    Ok "Created .git on branch $Branch"
} else {
    Ok "Git repository already exists."
}

$originUrl = ""
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
$originLines = & git remote get-url origin 2>$null
$gotOrigin = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prevEap
if ($gotOrigin) {
    $originUrl = "$originLines".Trim()
}

if ($originUrl) {
    if ($originUrl -ne $RemoteUrl) {
        Warn "Updating origin: $originUrl -> $RemoteUrl"
        & git remote set-url origin $RemoteUrl
    } else {
        Ok "Remote origin already set: $RemoteUrl"
    }
} else {
    Step "Adding remote origin..."
    & git remote add origin $RemoteUrl
    if ($LASTEXITCODE -ne 0) { throw "git remote add failed" }
    Ok "origin -> $RemoteUrl"
}

Write-Host ""
Step "Remote:"
& git remote -v

$hasCommits = $false
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
& git rev-parse HEAD 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { $hasCommits = $true }
$ErrorActionPreference = $prevEap

if (-not $Push) {
    Write-Host ""
    Warn "Connected. To commit and push for the first time, run:"
    Write-Host "  .\scripts\connect-github.ps1 -Push"
    Write-Host ""
    Write-Host "Or manually:"
    Write-Host "  git add -A"
    Write-Host "  git commit -m `"$Message`""
    Write-Host "  git push -u origin $Branch"
    exit 0
}

Write-Host ""
Step "Staging files..."
& git add -A
$status = & git status --porcelain
if (-not $status) {
    if (-not $hasCommits) {
        Warn 'Nothing to commit - check .gitignore. Add files manually, then push.'
        exit 1
    }
    Ok "Working tree clean - pushing existing commits."
} else {
    if ($hasCommits) {
        Step "Committing changes..."
    } else {
        Step "Creating first commit..."
    }
    & git commit -m $Message
    if ($LASTEXITCODE -ne 0) { throw "git commit failed" }
    Ok "Commit created."
}

Step "Pushing to origin/$Branch ..."
& git push -u origin $Branch
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Warn "Push failed. Common fixes:"
    Write-Host "  - Log in: gh auth login   OR use GitHub Desktop / credential manager"
    Write-Host "  - Remote has README already:"
    Write-Host "      git pull origin $Branch --rebase --allow-unrelated-histories"
    Write-Host "    then run this script again with -Push"
    exit $LASTEXITCODE
}

Write-Host ""
Ok "Done. Repo: https://github.com/deathier545/Mango"
