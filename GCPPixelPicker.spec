# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

project = Path(SPECPATH)

rasterio_datas, rasterio_binaries, rasterio_hiddenimports = collect_all("rasterio")

# Windows Rasterio wheels may place GDAL/PROJ DLLs in a sibling
# rasterio.libs directory. collect_delvewheel_libs_directory handles that
# layout when available in the installed PyInstaller version.
try:
    from PyInstaller.utils.hooks import collect_delvewheel_libs_directory
    rasterio_datas, rasterio_binaries = collect_delvewheel_libs_directory(
        "rasterio", datas=rasterio_datas, binaries=rasterio_binaries
    )
except (ImportError, TypeError):
    pass

a = Analysis(
    [str(project / "main.py")],
    pathex=[str(project)],
    binaries=rasterio_binaries,
    datas=rasterio_datas + [
        (str(project / "app_icon.png"), "."),
        (str(project / "app_icon.ico"), "."),
    ],
    hiddenimports=rasterio_hiddenimports + [
        "numpy",
        "PIL._tkinter_finder",
        "rasterio._base",
        "rasterio._env",
        "rasterio._io",
        "rasterio._path",
        "rasterio._warp",
        "rasterio.crs",
        "rasterio.enums",
        "rasterio.errors",
        "rasterio.transform",
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
    a.binaries,
    a.datas,
    [],
    name="GCPPixelPicker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project / "app_icon.ico"),
)
