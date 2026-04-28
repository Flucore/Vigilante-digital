# Audit repository contents before publishing to GitHub.
#
# The script focuses on common public-repo risks:
# - generated reports and runtime state,
# - local credentials and env files,
# - biometric media/datasets,
# - large model weights or binaries.
[CmdletBinding()]
param(
    [int]$MaxFileMb = 50
)

$ErrorActionPreference = "Stop"
$failed = $false

function Add-Failure {
    param([string]$Message)
    $script:failed = $true
    Write-Host "FAIL: $Message" -ForegroundColor Red
}

function Add-Ok {
    param([string]$Message)
    Write-Host "OK: $Message" -ForegroundColor Green
}

if (-not (Test-Path ".git")) {
    Add-Failure "This directory is not a Git repository."
    exit 1
}

$tracked = @(git ls-files)
$blockedPatterns = @(
    '(^|/)test_outputs/',
    '(^|/)reports/',
    '(^|/)secrets/',
    '(^|/)\.secrets/',
    '(^|/)config/secrets/',
    '(^|/)datasets/',
    '(^|/)data/',
    '(^|/)\.env(\.|$)',
    '\.(pem|key|p12|pfx)$',
    '\.(mp4|avi|mov|mkv)$',
    '\.(jpg|jpeg|png|webp|pdf)$',
    '\.(pt|pth|onnx|engine|tflite)$',
    'firebase-adminsdk.*\.json$',
    'service[-_]?account.*\.json$'
)

$blockedTracked = @()
foreach ($file in $tracked) {
    $normalized = $file -replace '\\', '/'
    foreach ($pattern in $blockedPatterns) {
        if ($normalized -match $pattern) {
            $blockedTracked += $file
            break
        }
    }
}

if ($blockedTracked.Count -gt 0) {
    Add-Failure "Blocked files are tracked:"
    $blockedTracked | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
} else {
    Add-Ok "No blocked generated, secret, media, dataset, or model files are tracked."
}

$oversized = @()
foreach ($file in $tracked) {
    if (Test-Path $file) {
        $sizeMb = (Get-Item $file).Length / 1MB
        if ($sizeMb -gt $MaxFileMb) {
            $oversized += "{0} ({1:N1} MB)" -f $file, $sizeMb
        }
    }
}

if ($oversized.Count -gt 0) {
    Add-Failure "Tracked files exceed ${MaxFileMb}MB:"
    $oversized | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
} else {
    Add-Ok "No tracked file exceeds ${MaxFileMb}MB."
}

$secretPattern = 'AIza[0-9A-Za-z_-]{35}|ghp_[A-Za-z0-9_]{36,}|github_pat_[A-Za-z0-9_]+|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----'
$secretMatches = @(git grep -n -I -E $secretPattern -- . 2>$null)
if ($secretMatches.Count -gt 0) {
    Add-Failure "Potential secrets found in tracked text files:"
    $secretMatches | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
} else {
    Add-Ok "No high-confidence secret tokens found in tracked text files."
}

$ignoredRequired = @("demo_config.json")
foreach ($required in $ignoredRequired) {
    if ((Test-Path $required) -and (git check-ignore -q $required)) {
        Add-Failure "$required is ignored but should be publishable as a safe sample config."
    }
}

if ($failed) {
    Write-Host "Repository audit failed. Fix the items above before publishing." -ForegroundColor Red
    exit 1
}

Write-Host "Repository audit passed." -ForegroundColor Green
