from __future__ import annotations

import zipfile
from pathlib import Path
import runpy

import pytest

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
    assert "run_stage_d_cement.py" in names

    # 从实际源码包执行两种spec到Analysis边界，校验其真实输入均已交付。
    archive_root = tmp_path / "unpacked"
    with zipfile.ZipFile(output) as archive:
        archive.extractall(archive_root)
    class Captured(Exception):
        pass
    for spec, entry in (("uebench.spec", "run_uebench.py"), ("uebench-stage-d.spec", "run_stage_d_cement.py")):
        def analysis(scripts, **kwargs):
            assert [Path(script).name for script in scripts] == [entry]
            for source in [*scripts, *kwargs["runtime_hooks"], *(item[0] for item in kwargs["datas"])]:
                assert Path(source).exists(), f"源码包缺少spec输入：{source}"
            raise Captured
        with pytest.raises(Captured):
            runpy.run_path(str(archive_root / spec), init_globals={"SPECPATH": str(archive_root), "Analysis": analysis})


def test_missing_candidate_entry_fails_source_package(tmp_path, monkeypatch):
    from tools import build_source_zip as builder
    for name in builder.MANDATORY_ROOT_FILES - {"run_stage_d_cement.py"}:
        (tmp_path / name).write_text("test", encoding="utf-8")
    monkeypatch.setattr(builder, "project_root", lambda: tmp_path)
    with pytest.raises(SystemExit, match="run_stage_d_cement.py"):
        builder.build_source_zip(tmp_path / "source.zip")
