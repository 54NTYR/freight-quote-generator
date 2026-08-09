# Freight Quote Generator

Desktop app for generating freight quotes (LTL, FTL, Dray, International).

## For end users (installing the app)

1. Run `FreightQuoteGenerator-Setup.exe` (from whoever shared the app with you).
2. Follow the installer wizard.
3. Launch **Freight Quote Generator** from the Start Menu.
4. The app opens in your browser automatically.
5. To enable distance calculations, edit the config file:
   - `%APPDATA%\FreightQuoteGenerator\config.json`
   - Set your Google Maps API key:
     ```json
     {
       "google_maps_api_key": "YOUR_KEY_HERE"
     }
     ```
6. Restart the app after changing the config.

Your saved pricing templates and quote counter are stored in the same `%APPDATA%\FreightQuoteGenerator` folder.

## For developers (building the installer)

### Prerequisites

- Python 3.10+ on Windows
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) (optional, for a proper `.exe` installer)

### Build steps

```powershell
.\build_installer.ps1
```

This will:

1. Install Python dependencies
2. Bundle the app with PyInstaller into `dist\FreightQuoteGenerator\`
3. Create `installer_output\FreightQuoteGenerator-Setup.exe` (if Inno Setup is installed)
4. Or create `dist\FreightQuoteGenerator-portable.zip` as a fallback

### Share with others

Send them `FreightQuoteGenerator-Setup.exe`. They do **not** need Python installed.

### SmartScreen warning ("Unknown publisher")

Windows may block the installer until users click **More info → Run anyway**. This is normal for new unsigned software.

- **Free trusted signing:** open-source the project and apply to [SignPath Foundation](https://signpath.io/open-source) — see `SIGNPATH.md`
- **Local testing only:** run `.\scripts\create_codesign_cert.ps1` then rebuild (does not fix SmartScreen on other PCs)
- **Paid option:** standard code-signing certificate (~$200+/year); reputation still builds over time

### Build the installer

```powershell
.\build_installer.ps1
```

If Inno Setup is installed, the script auto-detects `ISCC.exe` from the registry and common install paths.

### Run locally during development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install waitress
python launcher.py
```

Or with Flask debug mode:

```powershell
$env:GOOGLE_MAPS_API_KEY = "your-key"
python app.py
```

## Static assets

Place the company logo at `static/img/jericho-freight-logo-blue.png` before building if you want it to appear on international quotes.
