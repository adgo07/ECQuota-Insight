import json
from pathlib import Path
import pytest
from uebench.stage_d_candidate import prepare_isolated_root, candidate_definition, main
from uebench.application.evaluation_support import SUPPORTED_EVALUATION_STANDARD_IDS, supports_formal_evaluation


def test_scope_is_unchanged_and_candidate_is_r3():
    assert SUPPORTED_EVALUATION_STANDARD_IDS == frozenset({"gb-29446-2019"})
    assert not supports_formal_evaluation("gb-16780-2021")
    assert candidate_definition().rule_revision == 3


def test_isolated_marker_and_nonempty_rejection(tmp_path, monkeypatch):
    import tempfile
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    root = prepare_isolated_root(tmp_path / "new")
    assert prepare_isolated_root(root) == root
    other = tmp_path / "occupied"
    other.mkdir()
    (other / "user.txt").write_text("untouched")
    with pytest.raises(ValueError, match="新空目录"):
        prepare_isolated_root(other)
    with pytest.raises(ValueError, match="TEMP"):
        prepare_isolated_root(tmp_path.parent / "outside")
    assert (other / "user.txt").read_text() == "untouched"


def test_formal_release_argument_rejected_before_data(tmp_path):
    with pytest.raises(SystemExit):
        main(["--data-dir", str(tmp_path / "data"), "--formal-release"])
    assert not (tmp_path / "data").exists()



def test_custom_data_root_and_ancestor_overlap_rejected(tmp_path, monkeypatch):
    import tempfile
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    protected = tmp_path / "protected" / "user-data"
    monkeypatch.setenv("UEBENCH_DATA_DIR", str(protected))
    for root in [protected, protected / "child", protected.parent]:
        with pytest.raises(ValueError, match="正式用户数据"):
            prepare_isolated_root(root)
        assert not root.exists()


def test_smoke_readback_is_exact_and_read_only(tmp_path, monkeypatch):
    import tempfile
    import sqlite3
    from uebench.stage_d_candidate import _readback
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    root = tmp_path / "isolated"
    assert main(["--data-dir", str(root), "--self-check"]) == 0
    files = {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}
    evidence = _readback(root)
    assert evidence["record_count"] == 1
    assert main(["--data-dir", str(root), "--readback"]) == 0
    assert {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()} == files
    with pytest.raises(SystemExit):
        main(["--data-dir", str(root), "--self-check", "--readback"])
