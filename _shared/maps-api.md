# Google Maps — distance for LTL

Installed app reads **`%APPDATA%\FreightQuoteGenerator\config.json`**, not `config.example.json` in the install folder or `_internal`.

Development reads `config.json` in the project folder (copy from `config.example.json`). Never commit `config.json`.

## Required APIs

Enable **Routes API**, **Geocoding API**, and **Places API** on the key. Legacy Distance Matrix / Geocoding APIs fail on new Google Cloud projects.

Places is used only on the dray form: adding a terminal in the popup, and searching shipper/receiver addresses. Origin and return terminal fields search the local `terminals.json` catalog only.

If Places API (New) is not enabled **on the same Google Cloud project as the API key in `config.json`**, address search falls back to Geocoding. Type a fuller street + city or ZIP (for example `1010 Mead St Ohio`) rather than a house number alone. Enabling Places on a different project does not affect this key. If the key has API restrictions, add **Places API (New)** to that list.

## Code homes

- Load key: `config.py` → `load_google_maps_api_key` (env `GOOGLE_MAPS_API_KEY` wins)
- Miles: `app.py` → `compute_driving_distance_miles`; dray round-trip `POST /api/dray/route_miles`
- Address search: `GET /api/places/autocomplete` and `GET /api/places/details` (Places API New, then Geocoding fallback)
- Form AJAX: `POST /calculate_distance`; UI copy in `templates/ltl_quote_form.html`
- Terminals catalog: `terminals.json` (git-tracked) via `GET/POST /api/terminals`
- Logs: `%APPDATA%\FreightQuoteGenerator\app.log` when frozen

## Typical failures

| Symptom | Cause |
|---|---|
| "Add your Google Maps API key to config.json" | Key missing, placeholder, or edited the wrong file |
| "Enable the Routes API…" | Routes API not enabled for that key |
| "Address search needs a more complete street, city, or ZIP." | Places API (New) off for this key, or the query is too vague for Geocoding |

Do not put the actual key in any markdown file.
