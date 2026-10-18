from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tools.check_delivery_scope import DEFINITIONS, PINNED_PACKAGE, ROOT, validate_scope
from tools.audit_release import audit_release
from tools.sync_catalogue_resource import SOURCE as CATALOGUE_SOURCE, TARGET as CATALOGUE_TARGET
from tools.promote_gb29435_2025 import main as retired_promoter_main


def test_current_signed_package_matches_explicit_bundled_scope() -> None:
    result = validate_scope(package_path=PINNED_PACKAGE)
    assert result["bundled_count"] == 48
    assert result["formal_evaluation_count"] == 1


def test_preview_catalogue_is_derived_from_definition() -> None:
    assert CATALOGUE_TARGET.read_bytes() == CATALOGUE_SOURCE.read_bytes()


def test_retired_scope_writer_refuses_to_run() -> None:
    with pytest.raises(SystemExit, match="writer已退役"):
        retired_promoter_main()


def test_sixteen_drafts_do_not_enter_bundled_or_formal_scope(tmp_path: Path) -> None:
    copied = tmp_path / "definitions"
    shutil.copytree(DEFINITIONS, copied)
    candidates = ROOT / "standards/development/scope-63/definitions"
    for path in candidates.glob("*.json"):
        target = copied / path.name
        if not target.exists():
            shutil.copyfile(path, target)
    result = validate_scope(definitions_dir=copied, package_path=PINNED_PACKAGE)
    assert result == {"definition_count": 64, "bundled_count": 48,
                      "formal_evaluation_count": 1, "draft_count": 16}


def test_draft_cannot_be_placed_on_bundled_list(tmp_path: Path) -> None:
    copied = tmp_path / "definitions"
    shutil.copytree(DEFINITIONS, copied)
    candidate = ROOT / "standards/development/scope-63/definitions/gb-21345-2024.json"
    shutil.copyfile(candidate, copied / candidate.name)
    scope = tmp_path / "scope.json"
    original = ROOT / "data/delivery-scope.json"
    import json
    payload = json.loads(original.read_text(encoding="utf-8"))
    payload["bundled_definition_ids"][0] = candidate.stem
    scope.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="(草稿不得进入随包清单|非随包定义须保持 draft)"):
        validate_scope(scope_path=scope, definitions_dir=copied)


def test_artifact_audit_rejects_delivery_workbook(tmp_path: Path) -> None:
    (tmp_path / "误入交付的模板.xlsx").write_bytes(b"legacy")
    report = audit_release(tmp_path)
    assert report["no_excel_workbook"] == {"valid": False, "files_present": ["误入交付的模板.xlsx"]}
    assert any("不得包含 Excel 工作簿" in error for error in report["errors"])
