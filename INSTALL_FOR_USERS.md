# If SmartScreen blocks the installer

Windows may show a blue screen saying **"Windows protected your PC"** with **Unknown publisher**. This is normal for new software that is not yet signed with a trusted certificate.

## How to install anyway

1. On the blue SmartScreen screen, click **More info** (small link, not always obvious).
2. Click **Run anyway**.
3. Complete the installer normally.

The app runs locally in your browser at `http://127.0.0.1:17523`.

After install, edit `%APPDATA%\FreightQuoteGenerator\config.json` and add your Google Maps API key if you need distance calculations.
