# Creates a local self-signed Authenticode certificate for development/testing.
# IMPORTANT: This does NOT remove SmartScreen warnings on other people's PCs.
# For trusted signing that other Windows users accept, see SIGNPATH.md.

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BuildDir = Join-Path $ProjectRoot "build"
$PfxPath = Join-Path $BuildDir "codesign.pfx"
$ExampleConfig = Join-Path $BuildDir "signing.local.json.example"
$ConfigPath = Join-Path $BuildDir "signing.local.json"

New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

$Publisher = Read-Host "Publisher name shown in signature [Jericho Freight]"
if ([string]::IsNullOrWhiteSpace($Publisher)) {
    $Publisher = "Jericho Freight"
}

$PasswordPlain = Read-Host "PFX password (remember this for build signing)"
if ([string]::IsNullOrWhiteSpace($PasswordPlain)) {
    throw "A password is required."
}

$PasswordSecure = ConvertTo-SecureString $PasswordPlain -AsPlainText -Force

Write-Host "Creating self-signed code-signing certificate..." -ForegroundColor Cyan
$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject "CN=$Publisher" `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -KeyExportPolicy Exportable `
    -KeyUsage DigitalSignature `
    -NotAfter (Get-Date).AddYears(5)

Export-PfxCertificate -Cert $cert -FilePath $PfxPath -Password $PasswordSecure | Out-Null

@{
    pfx_path = "build/codesign.pfx"
    password = $PasswordPlain
    publisher = $Publisher
    note = "Self-signed certs do not bypass SmartScreen on other computers."
} | ConvertTo-Json | Set-Content -Path $ConfigPath -Encoding UTF8

Copy-Item $ConfigPath $ExampleConfig -Force

Write-Host ""
Write-Host "Certificate created:" -ForegroundColor Green
Write-Host "  $PfxPath"
Write-Host "  Config: $ConfigPath"
Write-Host ""
Write-Host "This certificate is useful for local testing only." -ForegroundColor Yellow
Write-Host "Other Windows users will still see SmartScreen unless you use a trusted signer." -ForegroundColor Yellow
Write-Host "See SIGNPATH.md for the free trusted option (open source required)." -ForegroundColor Yellow
