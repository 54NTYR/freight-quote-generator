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