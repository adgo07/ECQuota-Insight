from __future__ import annotations

import json
from pathlib import Path

from tools.build_development_manifest import validate_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_unified_development_library_index_is_complete() -> None:
    path = ROOT / "standards" / "development" / "library-index.json"
    report = validate_manifest(path)
    assert report["valid"] is True
    assert report["current_standard_count"] == 63
    assert report["retired_standard_count"] == 4
    assert report["standard_count"] == 67

    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload["standards"]
    keys = [(item["id"], item["version"], item["rule_revision"]) for item in entries]
    assert len(keys) == len(set(keys))
    assert sum(item["scope"] == "current" for item in entries) == 63
    assert sum(item["scope"] == "retired" for item in entries) == 4
    assert payload["canonical_scope"] == "scope-63"
    assert payload["comparison_snapshots"] == ["scope-65"]


def test_unified_development_library_does_not_make_scope_65_a_publish_input() -> None:
    payload = json.loads(
        (ROOT / "standards" / "development" / "library-index.json").read_text(encoding="utf-8")
    )
    assert all(
        item["definition_path"].startswith("scope-63/")
        for item in payload["standards"]
    )
    assert all(
        item["scope"] == "retired"
        for item in payload["standards"]
        if "/retired-definitions/" in item["definition_path"]
    )