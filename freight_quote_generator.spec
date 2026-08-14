# -*- mode: python ; coding: utf-8 -*-
import os

project_dir = os.path.abspath(".")
icon_file = os.path.join(project_dir, "build", "app-icon.ico")

if not os.path.exists(icon_file):
    raise SystemExit(f"Missing app icon: {icon_file}. Run scripts/create_app_icon.py first.")

datas = [
    ("templates", "templates"),
    ("config.example.json", "."),
]

if os.path.isdir("static"):
    datas.append(("static", "static"))

a = Analysis(
    ["launcher.py"],
    pathex=[project_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "waitress",
        "googlemaps",
        "flask",
        "jinja2",
        "werkzeug",
        "webview",
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
        "clr_loader",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FreightQuoteGenerator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FreightQuoteGenerator",
)
