# Google Maps — distance for LTL

Installed app reads **`%APPDATA%\FreightQuoteGenerator\config.json`**, not `config.example.json` in the install folder or `_internal`.

Development reads `config.json` in the project folder (copy from `config.example.json`). Never commit `config.json`.

## Required APIs

Enable **Routes API** and **Geocoding API** on the key. Legacy Distance Matrix / Geocoding APIs fail on new Google Cloud projects.

## Code homes

- Load key: `config.py` → `load_google_maps_api_key` (env `GOOGLE_MAPS_API_KEY` wins)
- Miles: `app.py` → `compute_driving_distance_miles`
- Form AJAX: `POST /calculate_distance`; UI copy in `templates/ltl_quote_form.html`
- Logs: `%APPDATA%\FreightQuoteGenerator\app.log` when frozen

## Typical failures

| Symptom | Cause |
|---|---|
| "Add your Google Maps API key to config.json" | Key missing, placeholder, or edited the wrong file |
| "Enable the Routes API…" | Routes API not enabled for that key |
| "ZIP codes not found" | Geocoding miss; check `app.log` |

Do not put the actual key in any markdown file.
