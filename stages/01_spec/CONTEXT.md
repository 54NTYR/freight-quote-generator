# 01_spec — write the change spec

One job: turn the request into an editable spec before any code changes.

## Inputs

- Working (this run): the user's request in this chat
- Reference (every run): `../../_templates/change-spec.md`
- Reference (every run): `../../_shared/quote-modes.md`
- Reference (every run): `../../_shared/brand.md` (only if kind is brand)
- Reference (every run): `../../_shared/maps-api.md` (only if kind is maps)
- Reference (every run): `../../_shared/installer.md` (only if kind is installer)

Do NOT load: `stages/02_implement`, `stages/03_ship`, installer scripts, PDF JS bundles under `static/js/`.

## Process

1. Copy `_templates/change-spec.md` to `output/change-spec.md`.
2. Fill Kind, Mode, Intent, Files, Out of scope, and the implement-time human check.
3. Name exact repo paths. If adding FTL or Dray, say which live mode to copy and that `coming_soon.html` must stop being that route's body.
4. Stop. Do not edit Python, HTML, or CSS in this stage.

## Outputs

- `change-spec.md` → `output/`

## Human check

Read the spec. Confirm the mode and file list match the request. Edit in place; `02_implement` reads whatever is here.
