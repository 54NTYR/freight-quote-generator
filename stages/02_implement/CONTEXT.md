# 02_implement — apply the spec to the app

One job: change only the files the spec names, then leave notes for the human test.

## Inputs

- Working (this run): `../01_spec/output/change-spec.md`
- Working (this run): the files that spec lists
- Reference (every run): `../../_shared/quote-modes.md`
- Reference (every run): `../../_shared/brand.md` (only if the spec's kind is brand)
- Reference (every run): `../../_shared/maps-api.md` (only if the spec's kind is maps)

Do NOT load: `stages/03_ship`, `build_installer.ps1`, `static/js/*.min.js`, other modes' templates unless the spec names them.

## Process

1. Read the spec. If `output/change-spec.md` is missing, stop and send the user back to `01_spec`.
2. Edit only listed files (and files those edits strictly require).
3. Keep quote numbers, AppData paths, and Maps key loading on their existing homes (`QuoteGenerator`, `paths.py`, `config.py`).
4. Write `output/notes.md`: what changed, how to run (`python launcher.py`), and the spec's human check copied verbatim.

## Outputs

- Code/templates as named in the spec
- `notes.md` → `output/`

## Human check

Run `python launcher.py`. Perform the spec's click-path. Edit code or the spec in place if the test fails; do not ship until this passes.
