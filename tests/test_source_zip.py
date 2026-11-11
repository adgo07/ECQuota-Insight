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
    assert "standards/mappings/INDEX.md" in names
    assert any(name.startswith("data/definitions/") for name in names)


import pytest

@pytest.mark.parametrize("spec_name", ["uebench.spec", "uebench-stage-d.spec"])
def test_extracted_source_has_real_spec_inputs(tmp_path, monkeypatch, spec_name):
    from pathlib import Path
    archive_path = build_source_zip(tmp_path / "source.zip")
    root = tmp_path / "extracted"
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(root)
    captured = {}
    class Stub:
        binaries = []
        pure = scripts = zipfiles = datas = []
    def analysis(entries, **kwargs):
        captured.update(entries=entries, **kwargs)
        return Stub()
    namespace = {"SPECPATH": str(root), "Analysis": analysis,
                 "PYZ": lambda *a, **k: Stub(), "EXE": lambda *a, **k: Stub(),
                 "COLLECT": lambda *a, **k: Stub()}
    identity = tmp_path / "build-identity.json"
    identity.write_text("{}")
    monkeypatch.setenv("ECQ_CEMENT_DEVELOPMENT_BUILD_INFO", str(identity))
    exec(compile((root / spec_name).read_text(encoding="utf-8"), spec_name, "exec"), namespace)
    for path in captured["entries"] + captured["runtime_hooks"]:
        assert Path(path).is_file(), path
    for path, _ in captured["datas"]:
        assert Path(path).exists(), path
    assert (root / "release/standard-packages/PIN.json").is_file()
    assert (root / ".gitattributes").is_file()


def test_source_zip_rejects_missing_real_entry(tmp_path, monkeypatch):
    import pytest
    import tools.build_source_zip as tool
    monkeypatch.setattr(tool, "project_root", lambda: tmp_path)
    with pytest.raises(SystemExit, match="run_uebench.py"):
        tool.build_source_zip(tmp_path / "must-not-exist.zip")
    assert not (tmp_path / "must-not-exist.zip").exists()
