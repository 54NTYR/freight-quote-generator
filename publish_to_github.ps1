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
$Owner = gh api user -q .login
$RepoSlug = "$Owner/$RepoName"
$RemoteUrl = "https://github.com/$RepoSlug.git"

gh repo view $RepoSlug 2>$null
$RepoExists = ($LASTEXITCODE -eq 0)

if ($RepoExists) {
    Write-Host "Repository already exists: $RepoSlug" -ForegroundColor Cyan
} else {
    Write-Host "Creating public GitHub repository: $RepoName" -ForegroundColor Cyan
    gh repo create $RepoName `
        --public `
        --description $Description

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create GitHub repository."
    }
}

$ExistingRemote = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
    git remote add origin $RemoteUrl
} elseif ($ExistingRemote -ne $RemoteUrl) {
    git remote set-url origin $RemoteUrl
}

Write-Host "Pushing to origin..." -ForegroundColor Cyan
$Branch = git branch --show-current
if ([string]::IsNullOrWhiteSpace($Branch)) {
    $Branch = "main"
}

git push -u origin $Branch
if ($LASTEXITCODE -ne 0) {
    throw "Failed to push to GitHub repository."
}

$Url = gh repo view $RepoSlug --json url -q .url
Write-Host ""
Write-Host "Published successfully:" -ForegroundColor Green
Write-Host "  $Url"
