$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

. (Join-Path $ProjectRoot "scripts\build_helpers.ps1")

Write-Host "==> Setting up build environment..." -ForegroundColor Cyan

$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvCfg = Join-Path $VenvDir "pyvenv.cfg"
$venvStale = $false
if (Test-Path $VenvCfg) {
    $cfg = Get-Content $VenvCfg -Raw
    $rootNeedle = $ProjectRoot.TrimEnd("\")
    if ($cfg -match "(?im)^command\s*=\s*(.+)$") {
        $createdFrom = $Matches[1].Trim()
        if ($createdFrom -notlike "*$rootNeedle*") {
            $venvStale = $true
            Write-Host "    Recreating .venv (it was created at another path; pip/pyinstaller launchers are stale)." -ForegroundColor Yellow
        }
    }
}
if ($venvStale -or -not (Test-Path $VenvPython)) {
    if (Test-Path $VenvDir) {
        try {
            Remove-Item -Recurse -Force $VenvDir -ErrorAction Stop
        } catch {
            Write-Host "    Could not replace .venv (a process still has it open). Continuing with python -m pip / PyInstaller." -ForegroundColor Yellow
        }
    }
    if (-not (Test-Path $VenvPython)) {
        python -m venv $VenvDir
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) {
            throw "Failed to create virtualenv at $VenvDir"
        }
    }
}

& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $VenvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install requirements.txt failed." }
& $VenvPython -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "pip install requirements-build.txt failed." }

Write-Host "==> Creating Windows app icon..." -ForegroundColor Cyan
& $VenvPython scripts/create_app_icon.py
if ($LASTEXITCODE -ne 0) {
    throw "App icon generation failed."
}

Write-Host "==> Building application with PyInstaller..." -ForegroundColor Cyan
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build\freight_quote_generator") { Remove-Item -Recurse -Force "build\freight_quote_generator" }

$iconPath = Join-Path $ProjectRoot "build\app-icon.ico"
if (-not (Test-Path $iconPath)) {
    throw "Missing build\app-icon.ico"
}

& $VenvPython -m PyInstaller --noconfirm freight_quote_generator.spec

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

Copy-Item $iconPath (Join-Path $ProjectRoot "dist\FreightQuoteGenerator\app-icon.ico") -Force

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
