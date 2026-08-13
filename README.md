# Freight Quote Generator

Desktop app for generating freight quotes (LTL, FTL, Dray, International).

## Google Maps API key

Distance calculations need a Google Maps API key with the **Distance Matrix API** enabled.

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

For temporary testing you can also set:

```powershell
$env:GOOGLE_MAPS_API_KEY = "your-key"
```

Environment variables take precedence over `config.json`.

## For end users

1. Run `FreightQuoteGenerator-Setup.exe`.
2. Launch **Freight Quote Generator** from the Start Menu.
3. Add your API key to `%APPDATA%\FreightQuoteGenerator\config.json` if you need distance calculations.

See `INSTALL_FOR_USERS.md` for SmartScreen installer notes.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install waitress
copy config.example.json config.json
python launcher.py
```

## Build Windows installer

```powershell
.\build_installer.ps1
```

Requires Python 3.10+ and optionally [Inno Setup 6](https://jrsoftware.org/isinfo.php).

Output: `installer_output\FreightQuoteGenerator-Setup.exe`

## Publish changes to GitHub

```powershell
.\publish_to_github.ps1
```

Optional custom commit message:

```powershell
.\publish_to_github.ps1 -Message "Add shared page headers"
```

This stages all changes, commits, and pushes to `origin/main`.

## Repository

https://github.com/AiSanty/freight-quote-generator
