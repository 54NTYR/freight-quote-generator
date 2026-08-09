# Code signing and SmartScreen

Windows SmartScreen shows **"Unknown publisher"** when your installer is not signed with a **trusted** certificate, or when the signed file has not yet built reputation with Microsoft.

## What actually works (free)

### SignPath Foundation (recommended if you can open-source the project)

SignPath provides **free, trusted code signing** for qualifying open-source projects:

1. Publish the project on GitHub (public repository).
2. Apply at [signpath.io/open-source](https://signpath.io/open-source).
3. After approval, use the GitHub Actions workflow in `.github/workflows/release-signpath.yml`.
4. Signed installers show **SignPath Foundation** as publisher and avoid the unknown-publisher block over time.

This is the only practical **no-cost** way to get trusted signatures for software you share with other Windows users.

## What does NOT remove SmartScreen for other users

| Method | Cost | SmartScreen on other PCs |
|--------|------|--------------------------|
| Self-signed cert + SignTool | Free | Still blocked |
| Unsigned installer | Free | Blocked (what you see now) |
| Paid OV certificate (~$200+/yr) | Paid | Warning until reputation builds |
| EV certificate | Paid | Same as OV since 2024 |

Self-signing with Windows SDK SignTool is still included in this repo for **local testing** and to show a publisher name on **your** machine after you trust the cert. It will **not** fix the warning your friend saw.

## Local self-signing (testing only)

### 1. Install Windows SDK (includes SignTool)

```powershell
winget install Microsoft.WindowsSDK.10.0.22621
```

Or install **Windows SDK** from Visual Studio Installer and enable "Windows SDK Signing Tools".

### 2. Create a self-signed certificate

```powershell
.\scripts\create_codesign_cert.ps1
```

This creates `build/codesign.pfx` and `build/signing.local.json` (gitignored).

### 3. Build and sign

```powershell
.\build_installer.ps1
```

If `build/signing.local.json` exists, the script signs:

- `dist\FreightQuoteGenerator\FreightQuoteGenerator.exe`
- `installer_output\FreightQuoteGenerator-Setup.exe`

## Until you have trusted signing

Share these steps with recipients when SmartScreen appears:

1. Click **More info** on the blue SmartScreen screen.
2. Click **Run anyway**.
3. The app is safe if they received it directly from you.

SmartScreen is a reputation filter, not proof the file is malicious. New independent software almost always triggers it without trusted signing.

## Verify a signature

Right-click the `.exe` → **Properties** → **Digital Signatures**.

- Self-signed: signature present but **not trusted** on other PCs.
- SignPath / commercial CA: **Valid** and trusted once reputation is established.
