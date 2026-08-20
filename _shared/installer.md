# Windows installer

Ship command: `.\build_installer.ps1` (needs Python venv deps + Inno Setup 6). Output: `installer_output/FreightQuoteGenerator-Setup.exe`.

## What the installed app is

- PyInstaller bundle from `freight_quote_generator.spec` (entry: `launcher.py`)
- Desktop window via `webview` (`desktop_api.py` for Save PDF)
- User data: `%APPDATA%\FreightQuoteGenerator\` (`config.json`, `quote_counter.json`, `app.log`)
- Bundled templates/static are read-only under the exe's `_internal` — editing those does not change runtime config

## Version

Bump `MyAppVersion` in `installer.iss` when shipping a build users will notice. App id and publisher stay as in that file.

## Signing / SmartScreen

- Local signing notes: `build/signing.local.json.example` (never commit `build/signing.local.json` or `build/codesign.pfx`)
- Unsigned builds: users follow `INSTALL_FOR_USERS.md` (More info → Run anyway)

## Do not tell users to

- Install Python
- Edit `_internal/config.example.json` for the Maps key
