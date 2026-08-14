# Freight Quote Generator

Desktop app for generating freight quotes (LTL, FTL, Dray, International). Runs in its own window — no separate browser tab required.

## Google Maps API key

Distance calculations need a Google Maps API key with the **Routes API** and **Geocoding API** enabled.

### Installed app (recommended)

1. Launch the app once.
2. Edit the config file:
   - Installed app: `%APPDATA%\FreightQuoteGenerator\config.json`
   - Development: `config.json` in the project folder (copy from `config.example.json`)
3. Set your key:
   ```json
   {
     "google_maps_api_key": "YOUR_KEY_HERE"
   }
   ```
4. Restart the app.

The key is read from `config.json` only — never commit that file. `config.example.json` is the safe template shipped with the project.

### Optional environment override

```powershell
$env:GOOGLE_MAPS_API_KEY = "your-key"
```

Environment variables take precedence over `config.json`.

## For end users

1. Run `FreightQuoteGenerator-Setup.exe`.
2. Launch **Freight Quote Generator** from the Start Menu (uses the yellow F app icon).
3. The app opens in its own desktop window.
4. Add your API key to `%APPDATA%\FreightQuoteGenerator\config.json` if you need distance calculations.

See `INSTALL_FOR_USERS.md` for SmartScreen installer notes.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-build.txt
copy config.example.json config.json
python launcher.py
```

Requires **WebView2** (pre-installed on most Windows 10/11 systems).

## Build Windows installer

```powershell
.\build_installer.ps1
```

Creates `build\app-icon.ico` from `static\img\app-icon.png`, bundles the app, and builds `installer_output\FreightQuoteGenerator-Setup.exe`.

## Repository

https://github.com/54NTYR/freight-quote-generator
