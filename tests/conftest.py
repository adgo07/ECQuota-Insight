from __future__ import annotations

import pytest


# N01-A intentionally changes only the GB 29446 cases whose old expected grade
# existed solely because ROUND(actual, 6) was applied before comparison.  Keep
# those historical tests in the suite as executable legacy evidence instead of
# deleting them; the corrected expectations are exercised by the N01-A vectors.
_LEGACY_BREAKING_VALUES = ("5.0000004", "8.5000004")
_LEGACY_TRACE_TEST = "test_detail_formula_grade_trace_shows_six_place_comparison"
_LEGACY_GRADE_TEST = "test_gb29446_grade_threshold_comparisons_round_both_values_to_six_places"


def pytest_collection_modifyitems(items):
    for item in items:
        nodeid = item.nodeid
        is_changed_legacy_grade = (
            _LEGACY_GRADE_TEST in nodeid
            and any(value in nodeid for value in _LEGACY_BREAKING_VALUES)
        )
        is_legacy_round6_trace = _LEGACY_TRACE_TEST in nodeid
        if is_changed_legacy_grade or is_legacy_round6_trace:
            item.add_marker(
                pytest.mark.xfail(
                    strict=True,
                    reason=(
                        "QZC-N01-A intentional numeric behavior change: this test records "
                        "the legacy GB 29446 ROUND6 contract; corrected full-value behavior "
                        "is asserted by tests/pilots/numeric/test_qzc_n01_a.py"
                    ),
                )
            )
