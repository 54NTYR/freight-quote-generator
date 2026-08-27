# Google Maps — distance for LTL

Installed app reads **`%APPDATA%\FreightQuoteGenerator\config.json`**, not `config.example.json` in the install folder or `_internal`.

Development reads `config.json` in the project folder (copy from `config.example.json`). Never commit `config.json`.

## Required APIs

Enable **Routes API**, **Geocoding API**, and **Places API** on the key. Legacy Distance Matrix / Geocoding APIs fail on new Google Cloud projects.

Miles use **large vehicle routing** (`travelMode: TRUCK`, `TRAFFIC_AWARE_OPTIMAL`, plus a 5-axle tractor-trailer `vehicleInfo`) on `computeRouteMatrix`. That is the same path for LTL/FTL Calculate Miles and the dray prepull warning. LVR is available in the contiguous 48 US states and needs the Routes API project provisioned for large vehicles. If that call fails, the app falls back to car routing so miles still calculate.

Places is used only on the dray form: adding a terminal in the popup (Terminal Name search), and searching shipper/receiver addresses. Origin and return terminal fields search the local `terminals.json` catalog only. Autocomplete includes the United States, Puerto Rico, and Colombia (`includedRegionCodes`: `us`, `pr`, `co`). Puerto Rico is its own region code; a US-only filter will not return San Juan addresses.

Customer names live in local `customers.json` (`%APPDATA%\FreightQuoteGenerator\customers.json` when installed). That file is gitignored and is not part of the published repo.

If Places API (New) is not enabled **on the same Google Cloud project as the API key in `config.json`**, address search falls back to Geocoding. Type a fuller street + city or ZIP (for example `1010 Mead St Ohio`) rather than a house number alone. Enabling Places on a different project does not affect this key. If the key has API restrictions, add **Places API (New)** to that list.

## Code homes

- Load key: `config.py` → `load_google_maps_api_key` (env `GOOGLE_MAPS_API_KEY` wins)
- Miles: `app.py` → `compute_driving_distance_miles`; dray round-trip `POST /api/dray/route_miles`
- Address search: `GET /api/places/autocomplete` and `GET /api/places/details` (Places API New, then Geocoding fallback)
- Form AJAX: `POST /calculate_distance`; UI copy in `templates/ltl_quote_form.html`
- Terminals catalog: bundled `terminals.json` plus local `terminals.local.json` overlay (gitignored). Edit at `/locations`.
- Customers: local `customers.json` (gitignored) via `GET/POST /api/customers` and the `/customers` editor.
- Logs: `%APPDATA%\FreightQuoteGenerator\app.log` when frozen

## Typical failures

| Symptom | Cause |
|---|---|
| "Add your Google Maps API key to config.json" | Key missing, placeholder, or edited the wrong file |
| "Enable the Routes API…" | Routes API not enabled for that key |
| "Address search needs a more complete street, city, or ZIP." | Places API (New) off for this key, or the query is too vague for Geocoding |

Do not put the actual key in any markdown file.
