# Publish the current repository to Flucore/Vigilante-digital without changing origin.
#
# This script intentionally pushes to the explicit RemoteUrl instead of relying
# on the local origin, because this workspace may be cloned from another repo.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Message,

    [string]$RemoteUrl = "https://github.com/Flucore/Vigilante-digital.git",
    [string]$Branch = "main",
    [switch]$RunTests,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Exec {
    param([string]$Command)
    Write-Host "> $Command" -ForegroundColor Cyan
    if (-not $DryRun) {
        Invoke-Expression $Command
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code ${LASTEXITCODE}: $Command"
        }
    }
}

if (-not (Test-Path ".git")) {
    throw "No .git directory found. Run this script from the repository root."
}

Exec "powershell -ExecutionPolicy Bypass -File .\scripts\audit_github_ready.ps1"

if ($RunTests) {
    Exec "python -m pytest tests"
}

$changes = git status --porcelain
if ($changes) {
    Exec "git add -A"
    Exec "git commit -m `"$Message`""
} else {
    Write-Host "No local changes to commit." -ForegroundColor Yellow
}

Exec "git fetch $RemoteUrl $Branch"

if (-not $DryRun) {
    git merge-base --is-ancestor FETCH_HEAD HEAD 2>$null
    if ($LASTEXITCODE -ne 0) {
        git merge-base FETCH_HEAD HEAD 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Exec "git merge --allow-unrelated-histories --no-edit -X ours FETCH_HEAD"
        } else {
            Exec "git merge --no-edit FETCH_HEAD"
        }
    } else {
        Write-Host "Remote $Branch is already contained in local history." -ForegroundColor Green
    }
}

Exec "git push $RemoteUrl HEAD:$Branch"

Write-Host "Published to $RemoteUrl ($Branch)." -ForegroundColor Green
