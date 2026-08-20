# Freight Quote Generator — the pipeline

The flow in one line: spec the change, implement it in the app, ship a Windows installer when someone else needs the build.

| Stage | Job | Input | Output | Human check |
|---|---|---|---|---|
| `01_spec` | write the change spec | `_templates/change-spec.md` + `_shared/` | `stages/01_spec/output/change-spec.md` | the spec names the right mode, files, and test |
| `02_implement` | apply the spec to code | `01_spec` output | the files the spec names + `stages/02_implement/output/notes.md` | run `python launcher.py` and perform the spec's test |
| `03_ship` | build the installer | approved code | `installer_output/FreightQuoteGenerator-Setup.exe` + `stages/03_ship/output/ship-log.md` | install on a clean-enough Windows box; distance still needs AppData `config.json` |

Factory (stable, every run): `_shared/brand.md`, `_shared/quote-modes.md`, `_shared/maps-api.md`, `_shared/installer.md`

Product (new each run): each stage's `output/`

Status is whatever exists: a stage is COMPLETE when its `output/` holds files other than `.gitkeep`. Skip `03_ship` unless the change must leave this machine.
