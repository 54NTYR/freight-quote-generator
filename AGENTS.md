# Freight Quote Generator

Desktop app for Jericho Freight quotes (LTL, International live; FTL and Dray not built). What leaves the workspace is a working app change, or a Windows installer.

Built on ICM: folders carry sequencing, hierarchy carries context, files carry state. Source code stays in place — these files are the catalog, not a second copy of the app.

## Where things live

| Folder | What it holds |
|---|---|
| `stages/` | product-change pipeline, in order |
| `_shared/` | factory: brand, quote-mode map, Maps API, installer rules |
| `_templates/` | blank `change-spec.md` — copy, don't start from nothing |
| `app.py`, `templates/`, `static/` | the app |
| `launcher.py`, `desktop_api.py`, `paths.py` | desktop window + user data |
| `build_installer.ps1`, `installer.iss` | Windows packaging |

## Route by what just happened

| If | Go to | Then stop at |
|---|---|---|
| new quote mode, template, or pricing UI | `stages/01_spec/CONTEXT.md` | human reads `stages/01_spec/output/change-spec.md` |
| LTL single vs tiered | `_shared/quote-modes.md` | pick `/ltl/single` or `/ltl/tiered` on mode select |
| spec approved | `stages/02_implement/CONTEXT.md` | human runs the app and checks the spec's test |
| ready to share with other Windows users | `stages/03_ship/CONTEXT.md` | human runs the new installer once |
| distance / Google Maps | `_shared/maps-api.md` then `config.py` + `app.py` | do not start a pipeline run |
| company name, phone, logo | `_shared/brand.md` | edit the home it names, not this file |
| asked for status | scan `stages/*/output/` | report what exists |

## The one rule

Nothing moves to the next stage until a person has read the output of the last one.
