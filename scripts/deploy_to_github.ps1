# Backward-compatible wrapper.
#
# Prefer scripts/publish_flucore_repo.ps1 for new releases. This wrapper keeps
# older documentation/shortcuts working while avoiding pushes to the wrong origin.
[CmdletBinding()]
param(
    [string]$Message = "Update Vigilante Digital",
    [string]$RemoteUrl = "https://github.com/Flucore/Vigilante-digital.git",
    [string]$Branch = "main",
    [switch]$RunTests,
    [switch]$DryRun,
    [switch]$Help
)

if ($Help) {
    Write-Host @"
Publishes Vigilante Digital to GitHub using an explicit remote URL.

Examples:
  .\scripts\deploy_to_github.ps1 -Message "Update docs" -DryRun
  .\scripts\deploy_to_github.ps1 -Message "Release v2.5.1" -RunTests

This script delegates to:
  .\scripts\publish_flucore_repo.ps1
"@
    exit 0
}

$argsList = @(
    "-ExecutionPolicy", "Bypass",
    "-File", ".\scripts\publish_flucore_repo.ps1",
    "-Message", $Message,
    "-RemoteUrl", $RemoteUrl,
    "-Branch", $Branch
)

if ($RunTests) { $argsList += "-RunTests" }
if ($DryRun) { $argsList += "-DryRun" }

& powershell @argsList
exit $LASTEXITCODE
