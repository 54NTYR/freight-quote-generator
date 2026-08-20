# 03_ship — build the Windows installer

One job: produce `FreightQuoteGenerator-Setup.exe` from the current tree.

## Inputs

- Working (this run): `../02_implement/output/notes.md` (must exist unless this is a ship-only rebuild)
- Reference (every run): `../../_shared/installer.md`
- Reference (every run): `../../build_installer.ps1`, `../../installer.iss`, `../../freight_quote_generator.spec`

Do NOT load: quote templates, `app.py` pricing logic, Maps implementation.

## Process

1. Confirm the human already ran the `02_implement` click-path (or the user asked to ship as-is).
2. Bump `MyAppVersion` in `installer.iss` if this is a user-facing release.
3. Run `.\build_installer.ps1`.
4. Write `output/ship-log.md`: version, output path, whether signing ran, and the AppData config reminder.

## Outputs

- `installer_output/FreightQuoteGenerator-Setup.exe`
- `ship-log.md` → `output/`

## Human check

Install the new exe. Confirm the window opens, LTL and International still load, and distance still uses `%APPDATA%\FreightQuoteGenerator\config.json` — not `_internal/config.example.json`.
