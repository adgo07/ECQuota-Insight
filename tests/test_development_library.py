from __future__ import annotations

import json
from pathlib import Path

from tools.build_development_manifest import validate_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_unified_development_library_index_is_complete() -> None:
    path = ROOT / "standards" / "development" / "library-index.json"
    report = validate_manifest(path)
    assert report["valid"] is True
    assert report["current_standard_count"] == 64
    assert report["draft_standard_count"] == 16
    assert report["standard_count"] == 64

    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload["standards"]
    keys = [(item["id"], item["version"], item["rule_revision"]) for item in entries]
    assert len(keys) == len(set(keys))
    assert sum(item["scope"] == "bundled" for item in entries) == 48
    assert sum(item["scope"] == "draft" for item in entries) == 16
    assert payload["canonical_source"] == "data/definitions"
    assert payload["formal_evaluation_standard_ids"] == ["gb-29446-2019"]
    assert payload["comparison_snapshots"] == ["standards/development/scope-63", "standards/development/scope-65"]


def test_unified_development_library_does_not_make_snapshots_publish_inputs() -> None:
    payload = json.loads(
        (ROOT / "standards" / "development" / "library-index.json").read_text(encoding="utf-8")
    )
    assert all(
        item["definition_path"].startswith("data/definitions/")
        for item in payload["standards"]
    )
