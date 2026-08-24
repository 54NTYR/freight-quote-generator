# Quote modes

Mode picker: `templates/mode_select.html`. Routes live in `app.py`. Company fields come from `config.py` (`COMPANY_INFO`), not from this file.

| Mode | Status | Form | Output | Route |
|---|---|---|---|---|
| LTL — Tiered | live | `templates/ltl_quote_form.html` | `templates/ltl_quote_output.html` | `/ltl/tiered` |
| LTL — Single Shipment | live | `templates/ltl_single_quote_form.html` | `templates/ltl_single_quote_output.html` | `/ltl/single` |
| International | live | `templates/international_quote_form.html` | `templates/international_quote_output.html` | `/international` |
| FTL | live | `templates/ftl_quote_form.html` | `templates/ftl_quote_output.html` | `/ftl` |
| Dray | live | `templates/dray_quote_form.html` | `templates/dray_quote_output.html` | `/dray` |

`/ltl` redirects to `/ltl/tiered` for old bookmarks.

## Mode selection

LTL on `mode_select.html` opens a hover menu: **Single Shipment Quote** or **Tiered Quote**.

## How a live mode is shaped

1. Entry on `mode_select.html` (or LTL sub-menu)
2. GET form + POST handler in `app.py`
3. Form template + output template
4. Quote number from `QuoteGenerator` (`quote_counter.json` via `paths.data_path`)
5. PDF save: `/quote/prepare-pdf` in `app.py` + `desktop_api.py`

## LTL — Tiered

- Four pallet tiers (`tier1`–`tier4`) entered on the form
- Volume charts and supply-chain sections on output
- Driving miles via `/calculate_distance` (see `_shared/maps-api.md`)
- Transit estimate: `QuoteGenerator.estimate_transit_time` in `app.py`

## LTL — Single Shipment

- One lane (origin/destination) + fixed pallet count + one price per pallet
- Total = `pallet_count × price_per_pallet`
- Output is a single shipment summary (no tier charts)

## International-specific

- JSON payload of lanes → legs (`parse_international_payload` in `app.py`)
- Per-pallet cost = (sum of leg costs + `otherFees`) / example pallet count

All five modes are live. Spec a new mode in `01_spec` before adding a route.
