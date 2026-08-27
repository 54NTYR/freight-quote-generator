# Quote Generator SOPs

These PDFs are the official how-to guides for the Freight Quote Generator.

They live in this folder so they can be committed to GitHub and bundled with the Windows app.

## Files

| File | Use |
|---|---|
| `SOP-LTL-Single-Shipment.pdf` | One LTL shipment quote |
| `SOP-LTL-Tiered.pdf` | Volume-tier LTL quote |
| `SOP-FTL.pdf` | Full truckload quote |
| `SOP-Drayage.pdf` | Port / rail dray quote |
| `SOP-International.pdf` | International quote |
| `SOP-Settings.pdf` | Settings cog, customers, terminals |

Open them in the app from the home-page settings cog: **SOP's**.

## Rebuild

From the project folder, with the venv active:

```
pip install reportlab
python scripts/build_sops.py
```

Do not gitignore this folder. The PDFs are product files, not local secrets.
