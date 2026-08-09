$ErrorActionPreference = "Stop"

$env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'User')
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "Checking GitHub authentication..." -ForegroundColor Cyan
gh auth status
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Log in to GitHub first:" -ForegroundColor Yellow
    Write-Host "  gh auth login --hostname github.com --git-protocol https --web"
    exit 1
}

$RepoName = "freight-quote-generator"
$Description = "Desktop freight quote generator for LTL, FTL, Dray, and international quotes."

Write-Host "Creating public GitHub repository: $RepoName" -ForegroundColor Cyan
gh repo create $RepoName `
    --public `
    --source . `
    --remote origin `
    --description $Description `
    --push

if ($LASTEXITCODE -ne 0) {
    throw "Failed to create or push GitHub repository."
}

$Url = gh repo view --json url -q .url
Write-Host ""
Write-Host "Published successfully:" -ForegroundColor Green
Write-Host "  $Url"
