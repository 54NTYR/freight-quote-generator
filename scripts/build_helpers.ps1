function Find-InnoSetupCompiler {
    $knownPaths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
    )

    foreach ($path in $knownPaths) {
        if (Test-Path $path) {
            return $path
        }
    }

    $registryRoots = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )

    foreach ($root in $registryRoots) {
        $entries = Get-ItemProperty $root -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -like "Inno Setup*" }

        foreach ($entry in $entries) {
            $candidates = @()
            if ($entry.InstallLocation) {
                $candidates += Join-Path $entry.InstallLocation "ISCC.exe"
            }
            if ($entry.UninstallString -match '^"([^"]+\\unins\d+\.exe)"') {
                $candidates += Join-Path (Split-Path $Matches[1] -Parent) "ISCC.exe"
            }

            foreach ($candidate in $candidates) {
                if (Test-Path $candidate) {
                    return (Resolve-Path $candidate).Path
                }
            }
        }
    }

    $searchRoots = @(
        "${env:ProgramFiles(x86)}",
        "${env:ProgramFiles}",
        "${env:LOCALAPPDATA}\Programs"
    )

    foreach ($root in $searchRoots) {
        if (-not (Test-Path $root)) { continue }
        $match = Get-ChildItem -Path $root -Recurse -Filter "ISCC.exe" -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($match) {
            return $match.FullName
        }
    }

    return $null
}

function Find-SignTool {
    $onPath = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($onPath) {
        return $onPath.Source
    }

    $kitRoot = "${env:ProgramFiles(x86)}\Windows Kits\10\bin"
    if (Test-Path $kitRoot) {
        $match = Get-ChildItem -Path $kitRoot -Recurse -Filter "signtool.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match "\\x64\\signtool\.exe$" } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($match) {
            return $match.FullName
        }
    }

    return $null
}

function Get-SigningConfig {
    param(
        [string]$ProjectRoot
    )

    $configPath = Join-Path $ProjectRoot "build\signing.local.json"
    if (-not (Test-Path $configPath)) {
        return $null
    }

    return Get-Content $configPath -Raw | ConvertFrom-Json
}

function Sign-WindowsBinary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string]$SignTool,

        [Parameter(Mandatory = $true)]
        [string]$PfxPath,

        [Parameter(Mandatory = $true)]
        [string]$Password
    )

    if (-not (Test-Path $FilePath)) {
        throw "Cannot sign missing file: $FilePath"
    }

    if (-not (Test-Path $PfxPath)) {
        throw "Cannot sign without certificate: $PfxPath"
    }

    $timestampUrl = "http://timestamp.digicert.com"
    & $SignTool sign /fd SHA256 /f $PfxPath /p $Password /tr $timestampUrl /td SHA256 /v $FilePath

    if ($LASTEXITCODE -ne 0) {
        throw "signtool failed for $FilePath (exit code $LASTEXITCODE)."
    }
}
