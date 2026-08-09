# Installs Freight Quote Generator from the portable folder.
# Right-click -> Run with PowerShell (or run from an elevated PowerShell for all users).

$ErrorActionPreference = "Stop"

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppName = "Freight Quote Generator"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\FreightQuoteGenerator"
$ExeName = "FreightQuoteGenerator.exe"
$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"

Write-Host "Installing $AppName..." -ForegroundColor Cyan
Write-Host "  From: $SourceDir"
Write-Host "  To:   $InstallDir"

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Path (Join-Path $SourceDir "*") -Destination $InstallDir -Recurse -Force

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut((Join-Path $StartMenuDir "$AppName.lnk"))
$Shortcut.TargetPath = Join-Path $InstallDir $ExeName
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Description = $AppName
$Shortcut.Save()

$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.lnk"
$CreateDesktop = Read-Host "Create desktop shortcut? (Y/n)"
if ($CreateDesktop -ne "n" -and $CreateDesktop -ne "N") {
    $DesktopLink = $WshShell.CreateShortcut($DesktopShortcut)
    $DesktopLink.TargetPath = Join-Path $InstallDir $ExeName
    $DesktopLink.WorkingDirectory = $InstallDir
    $DesktopLink.Save()
}

Write-Host ""
Write-Host "Installation complete." -ForegroundColor Green
Write-Host "Launch '$AppName' from the Start Menu."
Write-Host ""
Write-Host "Google Maps API key (optional, for distance calculations):"
Write-Host "  $env:APPDATA\FreightQuoteGenerator\config.json"

$Launch = Read-Host "Launch now? (Y/n)"
if ($Launch -ne "n" -and $Launch -ne "N") {
    Start-Process (Join-Path $InstallDir $ExeName)
}
