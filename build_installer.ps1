$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

. (Join-Path $ProjectRoot "scripts\build_helpers.ps1")

Write-Host "==> Setting up build environment..." -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& ".venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-build.txt

Write-Host "==> Building application with PyInstaller..." -ForegroundColor Cyan
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build\pyinstaller") { Remove-Item -Recurse -Force "build\pyinstaller" }

pyinstaller --noconfirm freight_quote_generator.spec

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$AppExe = Join-Path $ProjectRoot "dist\FreightQuoteGenerator\FreightQuoteGenerator.exe"
$SigningConfig = Get-SigningConfig -ProjectRoot $ProjectRoot
$SignTool = Find-SignTool

if ($SigningConfig -and $SignTool) {
    $PfxPath = Join-Path $ProjectRoot ($SigningConfig.pfx_path -replace "/", "\")
    Write-Host "==> Signing application executable..." -ForegroundColor Cyan
    Sign-WindowsBinary -FilePath $AppExe -SignTool $SignTool -PfxPath $PfxPath -Password $SigningConfig.password
} elseif ($SigningConfig -and -not $SignTool) {
    Write-Host "Signing config found but signtool.exe was not found." -ForegroundColor Yellow
    Write-Host "Install Windows SDK signing tools: winget install Microsoft.WindowsSDK.10.0.22621" -ForegroundColor Yellow
}

$InnoCompiler = Find-InnoSetupCompiler

if ($InnoCompiler) {
    Write-Host "==> Building Windows installer with Inno Setup..." -ForegroundColor Cyan
    Write-Host "    Using: $InnoCompiler" -ForegroundColor DarkGray
    New-Item -ItemType Directory -Force -Path "installer_output" | Out-Null
    & $InnoCompiler "installer.iss"

    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup build failed."
    }

    $SetupExe = Join-Path $ProjectRoot "installer_output\FreightQuoteGenerator-Setup.exe"
    if ($SigningConfig -and $SignTool -and (Test-Path $SetupExe)) {
        Write-Host "==> Signing installer executable..." -ForegroundColor Cyan
        Sign-WindowsBinary -FilePath $SetupExe -SignTool $SignTool -PfxPath (Join-Path $ProjectRoot ($SigningConfig.pfx_path -replace "/", "\")) -Password $SigningConfig.password
    }

    Write-Host ""
    Write-Host "Installer created:" -ForegroundColor Green
    Get-ChildItem "installer_output\*.exe" | ForEach-Object { Write-Host "  $($_.FullName)" -ForegroundColor Green }
} else {
    Write-Host ""
    Write-Host "Inno Setup compiler (ISCC.exe) not found." -ForegroundColor Yellow
    Write-Host "Install Inno Setup 6, then rerun this script." -ForegroundColor Yellow
    Write-Host "Download: https://jrsoftware.org/isinfo.php" -ForegroundColor Yellow

    $ZipPath = Join-Path $ProjectRoot "dist\FreightQuoteGenerator-portable.zip"
    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
    Compress-Archive -Path "dist\FreightQuoteGenerator\*" -DestinationPath $ZipPath

    Write-Host ""
    Write-Host "Portable package created:" -ForegroundColor Green
    Write-Host "  $ZipPath" -ForegroundColor Green
}

Copy-Item "setup.ps1" "dist\FreightQuoteGenerator\setup.ps1" -Force

Write-Host ""
if ($SigningConfig) {
    Write-Host "Build used a self-signed certificate (local testing only)." -ForegroundColor Yellow
} else {
    Write-Host "Installer is unsigned. Recipients may see a SmartScreen warning." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Share installer_output\FreightQuoteGenerator-Setup.exe (or the portable ZIP)." -ForegroundColor Cyan
