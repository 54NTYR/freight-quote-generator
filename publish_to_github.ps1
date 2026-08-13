param(
    [string]$Message = "Update freight quote generator"
)

$ErrorActionPreference = "Stop"

$env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'User')
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Get-GitAuthorFromGitHub {
    $user = gh api user | ConvertFrom-Json
    $name = if ($user.name) { $user.name } else { $user.login }
    $email = "$($user.id)+$($user.login)@users.noreply.github.com"
    return @{ Name = $name; Email = $email }
}

Write-Host "Checking GitHub authentication..." -ForegroundColor Cyan
gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Log in to GitHub first:" -ForegroundColor Yellow
    Write-Host "  gh auth login --hostname github.com --git-protocol https --web"
    exit 1
}

$Author = Get-GitAuthorFromGitHub
$RepoName = "freight-quote-generator"
$Description = "Desktop freight quote generator for LTL, FTL, Dray, and international quotes."
$Owner = gh api user -q .login
$RepoSlug = "$Owner/$RepoName"
$RemoteUrl = "https://github.com/$RepoSlug.git"

gh repo view $RepoSlug --json name -q .name 2>$null | Out-Null
$RepoExists = ($LASTEXITCODE -eq 0)

if ($RepoExists) {
    Write-Host "Repository: $RepoSlug" -ForegroundColor Cyan
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

Write-Host "Staging changes..." -ForegroundColor Cyan
git add -A
$Status = git status --short

if ($Status) {
    Write-Host $Status
    Write-Host "Committing as $($Author.Name) <$($Author.Email)>..." -ForegroundColor Cyan
    git -c "user.name=$($Author.Name)" -c "user.email=$($Author.Email)" commit -m $Message
    if ($LASTEXITCODE -ne 0) {
        throw "Commit failed."
    }
} else {
    Write-Host "No changes to commit." -ForegroundColor Yellow
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
