from __future__ import annotations

from pathlib import Path

from tools.compare_development_snapshots import compare_snapshots


def test_development_snapshots_have_a_single_canonical_scope() -> None:
    root = Path(__file__).resolve().parents[1]
    report = compare_snapshots(
        root / "standards" / "development" / "scope-63",
        root / "standards" / "development" / "scope-65",
        root / "data" / "standard-replacements.json",
    )
    assert report["valid"] is True
    assert report["comparison"]["canonical_only"] == ["GB 29141-2024", "GB 29435-2025"]
    assert report["comparison"]["unresolved_legacy_only"] == []
    assert report["merge_decision"].startswith("scope-63是唯一开发基线")
