# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


project_root = Path(SPECPATH)
# Qt 与 shiboken 正本由 PyInstaller hook 按包目录收集；现有运行时
# hook 提供 DLL 搜索路径。不再手工生成根目录下的四个重复 DLL 副本。
# 保留自动 hook 收集的全部插件、翻译与其他运行库。
binaries = []
# ECQ-RS05: the standard package is bundled from a PINNED, tracked release
# input rather than from dist/.  A clean checkout has no dist/ directory, so
# reading it from there made a reproducible build impossible.  The pinned copy
# is byte-identical to the published asset and its hash is locked by
# release/standard-packages/PIN.json.  Keep the relative path as one canonical
# string so the Source Gate can audit it.
STANDARD_PACKAGE_RELATIVE_PATH = (
    "release/standard-packages/initial-standard-package-published.uebench"
)

datas = [
    (str(project_root / "migrations"), "migrations"),
    (str(project_root / "src" / "uebench" / "resources"), "uebench/resources"),
    (str(project_root / STANDARD_PACKAGE_RELATIVE_PATH), "uebench/resources"),
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
    and not Path(entry[0]).name.lower().startswith(("qt6webengine", "qt6webview"))
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
