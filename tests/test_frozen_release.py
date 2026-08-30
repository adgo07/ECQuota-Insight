from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]


def test_portable_release_does_not_bundle_incompatible_poppler_icu() -> None:
    archive = ROOT / "dist" / "release" / "UEBench-0.1.0-win-x64.zip"
    assert archive.exists(), f"发布便携包不存在：{archive}"
    with ZipFile(archive) as package:
        names = package.namelist()
    lower_names = {name.lower() for name in names}
    assert not any(name.endswith("icuuc.dll") for name in lower_names)
    assert not any(name.endswith("icudt78.dll") for name in lower_names)
    assert any(name.endswith("pyside6/qtgui.pyd") for name in lower_names)
