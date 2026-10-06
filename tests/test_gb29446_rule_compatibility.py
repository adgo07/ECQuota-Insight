"""ECQ-RS05 Part 1 — GB 29446 incompatible-rule FAIL-FAST.

The formal r2 rule needs its own 煤种 selection metadata and the 附录A
“选煤工艺 → 折算系数 k” lookup.  A pre-r2 definition that lacks them must never
be silently faked:

* the compatibility predicate must say so (single, importable helper);
* the GB 29446 page must show an explicit Chinese message and must not render a
  coal-type / process selector that looks usable while being empty;
* the evaluate action must be refused instead of producing a formal record;
* ``product.name`` must never be used as if it were a 煤种.

The normal r2 path is unchanged and is re-checked here against one Golden case.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from uebench.bootstrap import create_context
from uebench.domain.models import StandardDefinition
from uebench.ui.main_window import (
    GB29446_RULE_INCOMPATIBLE_MESSAGE,
    MainWindow,
    gb29446_rule_is_compatible,
)

ROOT = Path(__file__).resolve().parents[1]
DEFINITION_PATH = ROOT / "data" / "definitions" / "gb-29446-2019.json"
STANDARD_ID = "gb-29446-2019"
COKING_COAL_PRODUCT_ID = "gb_29446-2019-coking-coal"


# ---------------------------------------------------------------------------
# Fixtures: the current r2 definition and genuinely pre-r2-shaped copies
# ---------------------------------------------------------------------------


def definition_json() -> dict:
    return json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))


def r2_definition() -> StandardDefinition:
    return StandardDefinition.model_validate(definition_json())


def pre_r2_definition_json() -> dict:
    """Build a genuinely pre-r2-shaped definition from the current one.

    Stripped: the ``coal_type`` selection level, every product's
    ``selection_values``, and the ``process_factor`` (附录A) display calculation.
    This is what an old/incompatible GB 29446 payload looks like.
    """

    document = definition_json()
    document["selection_schema"] = []
    for product in document["products"]:
        product["selection_values"] = {}
        for indicator in product["indicators"]:
            indicator["display_calculations"] = [
                display
                for display in indicator.get("display_calculations", [])
                if display.get("key") != "process_factor"
            ]
    return document


def pre_r2_definition() -> StandardDefinition:
    return StandardDefinition.model_validate(pre_r2_definition_json())


def _variant(name: str) -> StandardDefinition:
    """One isolated structural gap, to pin each clause of the predicate."""

    document = definition_json()
    if name == "no_selection_schema":
        document["selection_schema"] = []
    elif name == "no_selection_values":
        for product in document["products"]:
            product["selection_values"] = {}
    elif name == "one_product_without_coal_type":
        document["products"][0]["selection_values"] = {}
    elif name == "no_process_factor_rows":
        for product in document["products"]:
            for indicator in product["indicators"]:
                indicator["display_calculations"] = [
                    display
                    for display in indicator.get("display_calculations", [])
                    if display.get("key") != "process_factor"
                ]
    elif name == "empty_process_factor_rows":
        for product in document["products"]:
            for indicator in product["indicators"]:
                for display in indicator.get("display_calculations", []):
                    if display.get("key") == "process_factor":
                        display["formula"]["rows"] = []
    else:  # pragma: no cover - defensive
        raise AssertionError(f"未知变体：{name}")
    return StandardDefinition.model_validate(document)


def _qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# 1. The predicate accepts the current repository definition
# ---------------------------------------------------------------------------


def test_predicate_accepts_current_repository_definition() -> None:
    definition = r2_definition()
    # The r2 definition is the one the formal Golden was frozen against.
    assert definition.rule_revision == 2
    assert gb29446_rule_is_compatible(definition) is True
    assert [level.key for level in definition.selection_schema] == ["coal_type"]


# ---------------------------------------------------------------------------
# 2. The predicate rejects genuinely pre-r2-shaped definitions
# ---------------------------------------------------------------------------


def test_predicate_rejects_fully_stripped_pre_r2_definition() -> None:
    assert gb29446_rule_is_compatible(pre_r2_definition()) is False


@pytest.mark.parametrize(
    "variant",
    [
        "no_selection_schema",
        "no_selection_values",
        "one_product_without_coal_type",
        "no_process_factor_rows",
        "empty_process_factor_rows",
    ],
)
def test_predicate_rejects_each_missing_structural_requirement(variant: str) -> None:
    assert gb29446_rule_is_compatible(_variant(variant)) is False


def test_predicate_rejects_missing_definition() -> None:
    assert gb29446_rule_is_compatible(None) is False


# ---------------------------------------------------------------------------
# 3. Installed incompatible definition:中文提示 + 拒绝正式计算
# ---------------------------------------------------------------------------


def test_incompatible_definition_shows_chinese_message_and_refuses_evaluation(
    tmp_path: Path, monkeypatch
) -> None:
    application = _qt_app()
    context = create_context(tmp_path / "appdata")
    incompatible = pre_r2_definition()
    context.standards.install(incompatible)

    window = MainWindow(context)
    window.show()
    window.navigation.setCurrentRow(2)
    application.processEvents()

    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: warnings.append(str(args[2]) if len(args) > 2 else "")
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    try:
        # 1) explicit Chinese message: 不完整/不兼容 + 更新标准数据
        message = window.gb29446_incompatibility_message
        assert message.isVisible(), "不兼容规则必须显示中文提示"
        text = message.text()
        assert "不完整" in text or "不兼容" in text
        assert "更新标准数据" in text
        assert text == GB29446_RULE_INCOMPATIBLE_MESSAGE

        # 2) no selector that looks usable while being empty/meaningless
        assert not window.gb29446_coal_type.isVisible()
        assert not window.gb29446_process.isVisible()
        assert window.gb29446_coal_type.count() == 0
        assert window.gb29446_process.count() <= 1  # 至多一个“请选择”占位项

        # 4) never use product.name as if it were a 煤种
        for product in incompatible.products:
            assert window.gb29446_coal_type.findText(product.name) < 0

        # 3) the evaluate action is refused and no formal record is produced
        assert window.calculate_button.isEnabled() is False
        window.gb29446_electricity.setText("350")
        window.gb29446_raw_coal.setText("63")
        window.calculate_evaluation()
        assert window.last_result_id is None
        assert context.application.list_recent_evaluations() == []
        assert GB29446_RULE_INCOMPATIBLE_MESSAGE in window.gb29446_result_message.text()
        assert any(GB29446_RULE_INCOMPATIBLE_MESSAGE in item for item in warnings), (
            "必须给出明确原因，而不是笼统错误"
        )
    finally:
        window.close()
        context.database.dispose()


def test_excel_evaluation_path_is_refused_for_incompatible_rule(
    tmp_path: Path, monkeypatch
) -> None:
    """The Excel import/evaluate path must not save a formal record either."""

    application = _qt_app()
    context = create_context(tmp_path / "appdata")
    context.standards.install(pre_r2_definition())

    window = MainWindow(context)
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: warnings.append(str(args[2]) if len(args) > 2 else "")
    )

    def _must_not_run(*_args, **_kwargs):  # pragma: no cover - asserted never called
        raise AssertionError("规则不兼容时不得进入正式 Excel 评价用例")

    monkeypatch.setattr(context.application, "evaluate_workbook", _must_not_run)
    try:
        # A workbook that validated before the incompatible rule was installed
        # (or was validated against it) must still be refused here.
        window.pending_import_id = "pending-import"
        window.pending_import_standard_id = STANDARD_ID
        window.import_commit_button.setEnabled(True)
        window.evaluate_import()
        assert window.pending_import_id is None
        assert window.import_commit_button.isEnabled() is False
        assert GB29446_RULE_INCOMPATIBLE_MESSAGE in window.import_status.text()
        assert any(GB29446_RULE_INCOMPATIBLE_MESSAGE in item for item in warnings)
        assert context.application.list_recent_evaluations() == []
    finally:
        window.close()
        context.database.dispose()


# ---------------------------------------------------------------------------
# 4. The normal r2 path still works (mirrors a Golden case)
# ---------------------------------------------------------------------------


def test_normal_r2_path_still_evaluates_coking_coal_by_jig(tmp_path: Path, monkeypatch) -> None:
    application = _qt_app()
    context = create_context(tmp_path / "appdata")
    definition = r2_definition()
    context.standards.install(definition)

    window = MainWindow(context)
    window.show()
    window.navigation.setCurrentRow(2)
    application.processEvents()

    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: warnings.append(str(args[2]) if len(args) > 2 else "")
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)
    try:
        assert window.calculate_button.isEnabled() is True
        assert not window.gb29446_incompatibility_message.isVisible()
        assert [window.gb29446_coal_type.itemText(i) for i in range(window.gb29446_coal_type.count())] == [
            "炼焦煤",
            "动力煤",
        ]

        # 炼焦煤 / 跳汰 → k = 1.26；E_d=350, m=63 → e_d = 350 × 1.26 / 63 = 7.0 → 2级
        window.gb29446_coal_type.setCurrentIndex(window.gb29446_coal_type.findText("炼焦煤"))
        assert window.gb29446_coal_type.currentData() == COKING_COAL_PRODUCT_ID
        window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("跳汰"))
        assert window.gb29446_factor.text() == "1.26"
        window.gb29446_electricity.setText("350")
        window.gb29446_raw_coal.setText("63")

        window.calculate_evaluation()

        assert window.last_result_id is not None
        assert window.gb29446_result_ed.text() == "7.00 kW·h/t"
        assert window.gb29446_result_grade.text() == "2级"
        assert not any(GB29446_RULE_INCOMPATIBLE_MESSAGE in item for item in warnings)
        records = context.application.list_recent_evaluations()
        assert len(records) == 1
    finally:
        window.close()
        context.database.dispose()
