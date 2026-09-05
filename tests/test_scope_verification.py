from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from tools.verify_scope import _source_confirms_gap, _source_confirms_non_monotonic


ROOT = Path(__file__).resolve().parents[1]


def test_source_gap_marker_is_distinguished_from_unresolved_gap() -> None:
    assert _source_confirms_gap(SimpleNamespace(notes=["缺级：原文为—，保留空值"]))
    assert _source_confirms_gap(SimpleNamespace(notes=["missing_grade_preserved"]))
    assert not _source_confirms_gap(SimpleNamespace(notes=["缺级：原文未录入"]))


def test_non_monotonic_source_marker_is_explicit() -> None:
    assert _source_confirms_non_monotonic(SimpleNamespace(notes=["non_monotonic_source_values_preserved"]))
    assert not _source_confirms_non_monotonic(SimpleNamespace(notes=[]))


def test_scope_report_records_confirmed_gaps_separately() -> None:
    report_path = ROOT / "standards" / "development" / "scope-63" / "verification" / "scope-63-verify-20260905.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["valid"] is True
    assert report["source_confirmed_gap_count"] == 11
    assert report["draft_quality_warning_count"] == 0