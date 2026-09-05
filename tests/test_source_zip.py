from __future__ import annotations

import zipfile

from tools.build_source_zip import build_source_zip


def test_source_zip_contains_development_standard_baseline(tmp_path):
    output = tmp_path / "source.zip"

    build_source_zip(output)

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())

    assert "standards/development/README.md" in names
    assert "standards/development/manifest.json" in names
    assert "standards/development/library-index.json" in names
    assert "standards/development/scope-63/scope-63.json" in names
    assert any(name.startswith("standards/development/scope-63/definitions/") for name in names)