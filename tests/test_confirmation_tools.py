from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
import pytest

from tools.publish_confirmed_rules import validate_confirmation


def _workbook(path: Path, indicator_id: str, conclusion: str = "同意发布") -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "规则确认"
    sheet.append([])
    sheet.append([])
    sheet.append(["序号", "标准编号", "指标ID", "确认结论", "确认人", "确认日期"])
    sheet.append([1, "GB 00000-2026", indicator_id, conclusion, "测试人", "2026-08-28"])
    workbook.save(path)


def test_published_rows_are_immutable_and_can_be_revalidated(tmp_path: Path) -> None:
    path = tmp_path / "confirmation.xlsx"
    _workbook(path, "published.indicator")
    assert validate_confirmation(
        path,
        reviewed_ids=set(),
        published_ids={"published.indicator"},
        all_ids={"published.indicator"},
        scope_count=1,
    ) == set()


def test_draft_rows_cannot_be_published_without_review(tmp_path: Path) -> None:
    path = tmp_path / "confirmation.xlsx"
    _workbook(path, "draft.indicator")
    with pytest.raises(ValueError, match="当前仍为draft"):
        validate_confirmation(
            path,
            reviewed_ids=set(),
            published_ids=set(),
            all_ids={"draft.indicator"},
            scope_count=1,
        )
