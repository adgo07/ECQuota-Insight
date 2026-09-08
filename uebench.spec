# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys


project_root = Path(SPECPATH)
site_packages = Path(sys.prefix) / "Lib" / "site-packages"
binaries = [
    # PySide6's extension modules live under PySide6/, while the shiboken
    # runtime DLL is collected under shiboken6/.  A flat copy makes the
    # dependency resolvable by the Windows loader before package init runs.
    (str(site_packages / "shiboken6" / "shiboken6.abi3.dll"), "."),
]
binaries.extend(
    (str(path), ".")
    for path in (site_packages / "PySide6").glob("*.dll")
    # The application opens PDF files with the Windows default viewer and
    # does not import QtWebEngine/QtWebView.  Do not ship these multi-hundred
    # megabyte browser runtimes in the offline desktop package.
    if path.name not in {"shiboken6.abi3.dll"}
    and not path.name.lower().startswith(("qt6webengine", "qt6webview"))
)
datas = [
    (str(project_root / "migrations"), "migrations"),
    (str(project_root / "src" / "uebench" / "resources"), "uebench/resources"),
    (
        str(project_root / "dist" / "standard-packages" / "initial-standard-package-published.uebench"),
        "uebench/resources",
    ),
]

a = Analysis(
    [str(project_root / "run_uebench.py")],
    pathex=[str(project_root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=["alembic.runtime.migration", "alembic.ddl.sqlite", "greenlet"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "packaging" / "pyi_rth_uebench.py")],
    excludes=["tkinter", "pytest", "hypothesis"],
    noarchive=False,
    optimize=1,
)
# The development host exposes Poppler's ICU 78 DLL on PATH.  PySide6's
# Qt6Core imports the Windows ICU API and must not be paired with that
# incompatible Poppler binary (it exports only version-suffixed symbols such
# as ``ucnv_open_78``).  Leave these two names to the Windows System32 ICU
# implementation instead of silently bundling the wrong copy.
a.binaries = [
    entry
    for entry in a.binaries
    if Path(entry[0]).name.lower() not in {"icuuc.dll", "icudt78.dll"}
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="UEBench",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(project_root / "packaging" / "uebench.ico"),
    target_arch="x86_64",
    codesign_identity=None,
    entitlements_file=None,
    version=str(project_root / "packaging" / "version_info.txt"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="UEBench",
)
