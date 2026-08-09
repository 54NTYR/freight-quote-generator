# -*- mode: python ; coding: utf-8 -*-
import os

project_dir = os.path.abspath(".")

datas = [
    ("templates", "templates"),
    ("config.example.json", "."),
    ("pricing_templates.json", "."),
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
        "geopy",
        "geopy.distance",
        "flask",
        "jinja2",
        "werkzeug",
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
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FreightQuoteGenerator",
)
