from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from uebench.bootstrap import create_context
from uebench.ui.main_window import MainWindow
from uebench.domain.models import (
    EvaluationRequest,
    InputMode,
    InputValue,
    PackageHistoryEntry,
    PublicationStatus,
    SelectionLevel,
    StandardSelectionMode,
    StandardDefinition,
)

from .test_engine import make_standard


GB29446_STANDARD_PATH = Path(__file__).parents[1] / "data" / "definitions" / "gb-29446-2019.json"


def _gb29446_standard() -> StandardDefinition:
    return StandardDefinition.model_validate_json(GB29446_STANDARD_PATH.read_text(encoding="utf-8"))


def test_main_window_starts_with_empty_database(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    window = MainWindow(context)
    assert window.navigation.count() == 6
    assert window.home_standard_count.text() == "0/0"
    window.close()
    context.database.dispose()


def test_main_window_lists_published_standard(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    context.standards.install(make_standard())
    window = MainWindow(context)
    window.refresh_all()
    assert window.home_standard_count.text() == "1/1"
    assert window.standard_table.rowCount() == 1
    assert window.eval_standard.count() == 1
    window.navigation.setCurrentRow(1)
    assert window.pages.currentIndex() == 1
    window.standard_table.selectRow(0)
    window.refresh_standard_detail()
    assert window.standard_indicator_table.rowCount() == 1
    assert window.standard_indicator_table.item(0, 1).text() == "单位产品能耗"
    window.close()
    context.database.dispose()


def test_record_request_can_be_loaded_for_copy_or_recalculation(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = make_standard()
    context.standards.install(standard)
    request = EvaluationRequest(
        evaluation_date=standard.effective_date,
        standard_id=standard.id,
        product_id="product",
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="15", unit="kgce/t")},
        notes="回归测试备注",
    )
    context.evaluation_service.evaluate(request)
    window = MainWindow(context)
    window.refresh_records()
    assert window._load_request_into_form(request)
    assert window.eval_standard.currentData() == standard.id
    assert window.eval_product.currentData() == "product"
    assert window.eval_inputs.item(0, 2).text() == "15"
    assert window.eval_notes.text() == "回归测试备注"
    window.close()
    context.database.dispose()


def test_result_view_shows_grade_count_without_overall_grade(tmp_path: Path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = make_standard()
    context.standards.install(standard)
    window = MainWindow(context)
    monkeypatch.setattr("uebench.ui.main_window.QMessageBox.information", lambda *args, **kwargs: None)
    request = EvaluationRequest(
        evaluation_date=standard.effective_date,
        standard_id=standard.id,
        product_id="product",
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="20", unit="kgce/t")},
    )
    window.calculate_evaluation(request)
    assert "2级 1 项" in window.eval_summary.text()
    assert "不生成总体等级" in window.eval_summary.text()
    window.close()
    context.database.dispose()

def test_duplicate_product_names_show_indicator_hint(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = make_standard()
    duplicate = standard.products[0].model_copy(deep=True)
    duplicate.id = "product-2"
    duplicate.name = standard.products[0].name
    duplicate.indicators[0].id = "energy-2"
    duplicate.indicators[0].name = "单位产品电耗"
    standard.products.append(duplicate)
    context.standards.install(standard)
    window = MainWindow(context)
    labels = [window.eval_product.itemText(index) for index in range(window.eval_product.count())]
    assert any("测试产品（指标：单位产品能耗）" == label for label in labels)
    assert any("测试产品（指标：单位产品电耗）" == label for label in labels)
    assert [window.eval_product.itemData(index) for index in range(window.eval_product.count())] == ["product", "product-2"]
    window.close()
    context.database.dispose()
def test_future_standard_calculation_is_preview_only(tmp_path: Path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    future = make_standard().model_copy(update={
        "id": "gb-future-ui",
        "number": "GB 00004-2027",
        "version": "2027",
        "effective_date": date(2027, 1, 1),
    })
    context.standards.install(future)
    window = MainWindow(context)
    monkeypatch.setattr("uebench.ui.main_window.QMessageBox.information", lambda *args, **kwargs: None)
    request = EvaluationRequest(
        evaluation_date=date(2026, 9, 1),
        standard_id=future.id,
        product_id="product",
        selection_mode=StandardSelectionMode.FUTURE,
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="20", unit="kgce/t")},
    )
    window.calculate_evaluation(request)
    assert window.last_result_id is None
    assert context.application.list_recent_evaluations() == []
    assert window.eval_results.rowCount() == 1
    window.close()
    context.database.dispose()

def test_maintenance_page_shows_package_history_from_application_layer(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    entry = PackageHistoryEntry(
        package_id="pkg-history",
        data_version="2026.09-published.1",
        package_mode="incremental",
        issued_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        installed_at=datetime(2026, 9, 2, 12, 34, 56, tzinfo=timezone.utc),
        parent_package_id="pkg-parent",
        standard_count=63,
        rule_count=900,
        package_sha256="a" * 64,
    )
    context.application.list_package_history = lambda limit=50: [entry]
    window = MainWindow(context)
    window.navigation.setCurrentRow(5)
    assert window.package_history_table.rowCount() == 1
    assert window.package_history_table.item(0, 1).text() == "2026.09-published.1"
    assert window.package_history_table.item(0, 2).text() == "增量包"
    assert window.package_history_table.item(0, 3).text() == "pkg-parent"
    assert window.package_history_table.item(0, 7).text() == "a" * 64
    window.close()
    context.database.dispose()


def test_standard_library_shows_pending_standard_in_chinese(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    pending = make_standard().model_copy(update={
        "id": "gb-pending-2027",
        "number": "GB 00005-2027",
        "version": "2027",
        "title": "待确认测试标准",
        "publication_status": PublicationStatus.DRAFT,
        "effective_date": date(2027, 1, 1),
    })
    pending.products[0].indicators[0].notes = ["requires_independent_review"]
    context.standards.install(pending)
    window = MainWindow(context)
    assert window.standard_table.rowCount() == 1
    assert window.standard_table.item(0, 2).text() == "待确认（不可正式评价）"
    window.standard_table.selectRow(0)
    assert "需独立复核后使用" in window.standard_indicator_table.item(0, 6).text()
    assert "requires_independent_review" not in window.standard_indicator_table.item(0, 6).text()
    window.close()
    context.database.dispose()


def test_evaluation_hides_date_and_project_and_uses_mode_buttons(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    context.standards.install(make_standard())
    window = MainWindow(context)
    assert not window.eval_date.isVisible()
    assert not window.eval_project.isVisible()
    assert window.eval_standard.isEditable()
    assert window.eval_standard_open.text() == "查看原文"
    assert window.eval_standard_status.text().startswith("GB 00000-2026")
    window.detail_mode_button.click()
    assert window.eval_mode.currentData() == InputMode.DETAIL.value
    window.direct_mode_button.click()
    assert window.eval_mode.currentData() == InputMode.DIRECT.value
    window.close()
    context.database.dispose()


def test_rule_declared_product_selection_cascades_and_keeps_product_id(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = make_standard()
    standard.selection_schema = [
        SelectionLevel(key="product_category", label="产品类别"),
        SelectionLevel(key="product_spec", label="产品规格/工序"),
    ]
    standard.products[0].selection_values = {
        "product_category": "类别A",
        "product_spec": "规格A",
    }
    second = standard.products[0].model_copy(deep=True)
    second.id = "product-2"
    second.name = "产品B"
    second.indicators[0].id = "energy-2"
    second.selection_values = {
        "product_category": "类别B",
        "product_spec": "规格B",
    }
    standard.products.append(second)
    context.standards.install(standard)
    window = MainWindow(context)

    assert [level.label for level, _combo in window.selection_widgets] == ["产品类别", "产品规格/工序"]
    category, specification = [combo for _level, combo in window.selection_widgets]
    assert [category.itemText(i) for i in range(category.count())] == ["类别A", "类别B"]
    assert [specification.itemText(i) for i in range(specification.count())] == ["规格A"]
    category.setCurrentIndex(category.findData("__value__:类别B"))
    assert [specification.itemText(i) for i in range(specification.count())] == ["规格B"]
    assert window.eval_product.currentData() == "product-2"
    window.close()
    context.database.dispose()


def test_standard_selector_restores_first_option_when_version_scope_changes(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    current = make_standard()
    future = make_standard().model_copy(update={
        "id": "gb-future-selector",
        "number": "GB 00006-2027",
        "version": "2027",
        "effective_date": date(2027, 1, 1),
    })
    context.standards.install(current)
    context.standards.install(future)
    window = MainWindow(context)
    assert window.eval_standard.currentData() == current.id
    window.eval_selection_mode.setCurrentIndex(2)
    assert window.eval_standard.currentData() == future.id
    assert "尚未实施" in window.eval_standard_status.text()
    window.close()
    context.database.dispose()


def test_gb29446_ordinary_evaluation_form_and_result_card(tmp_path: Path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = _gb29446_standard()
    context.standards.install(standard)
    window = MainWindow(context)
    window.show()
    window.navigation.setCurrentRow(2)
    application.processEvents()
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    assert window.eval_standard.currentData() == standard.id
    assert [window.gb29446_period.itemText(i) for i in range(window.gb29446_period.count())] == [
        "全年", *(f"{month}月" for month in range(1, 13)), "自定义"
    ]
    assert window.gb29446_period.currentData() == "全年"
    assert not window.gb29446_custom_period.isVisible()
    assert window.gb29446_factor.isReadOnly()
    assert window.gb29446_process.currentData() is None
    assert window.gb29446_factor.text() == ""
    assert not window.input_controls_container.isVisible()
    assert not window.generic_form_container.isVisible()
    assert not window.generic_result_section.isVisible()
    assert window.gb29446_result_section.isVisible()
    assert window.eval_inputs.rowCount() == 0

    visible_text = " ".join(
        widget.text()
        for widget in window.findChildren(QLabel)
        if widget.isVisible()
    )
    for internal_label in (
        "enterprise_status",
        "single_coal_single_process",
        "electricity_consumption",
        "raw_coal_input",
        "lookup",
        "constant",
        "运算轨迹",
        "是否符合",
        "执行要求",
    ):
        assert internal_label not in visible_text

    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("重介"))
    assert window.gb29446_factor.text() == "1.12"
    window.gb29446_electricity.setText("560")
    window.gb29446_raw_coal.setText("100")
    window.gb29446_notes.setText("页面回归备注")
    request = window._collect_request()
    assert set(request.inputs) == {
        "washing_process", "electricity_consumption", "raw_coal_input"
    }
    assert request.organization_name is None
    assert request.notes == "核算周期：全年\n备注：页面回归备注"

    window.calculate_evaluation()
    assert window.last_result_id is not None
    assert window.gb29446_result_ed.text() == "6.27 kW·h/t"
    assert window.gb29446_result_grade.text() == "2级"
    assert "未折算单位电耗 E_d/m：5.60 kW·h/t" in window.gb29446_explanation.text()
    assert "e_d = 560 × 1.12 / 100 = 6.272 kW·h/t" in window.gb29446_explanation.text()
    assert "1级 ≤ 5.00 kW·h/t" in window.gb29446_explanation.text()
    assert "原始计算值（未修约）：6.272 kW·h/t" in window.gb29446_explanation.text()
    assert "6.272000 <= 7.000000" in window.gb29446_explanation.text()
    assert "结果：2级" in window.gb29446_explanation.text()
    assert "显示位数不参与判级" in window.gb29446_explanation.text()
    assert "PDF第" not in window.gb29446_basis.text()
    assert "第3.1条" in window.gb29446_basis.text()
    assert "第5.2条" in window.gb29446_basis.text()
    assert "附录A表A.1" in window.gb29446_basis.text()
    assert window.gb29446_basis_open.text() == "查看标准原文"
    assert window.eval_results.rowCount() == 0
    assert window.eval_summary.text() == ""

    loaded = context.application.get_evaluation(window.last_result_id)
    assert loaded is not None
    saved_request, saved_result, _snapshot = loaded
    assert saved_request.organization_name is None
    assert "enterprise_status" not in saved_request.inputs
    assert "single_coal_single_process" not in saved_request.inputs
    assert saved_request.notes == "核算周期：全年\n备注：页面回归备注"
    assert saved_result.results[0].compliance_result is None

    window.gb29446_electricity.setText("1000")
    assert window.last_result_id is None
    assert window.gb29446_result_ed.text() == "— kW·h/t"
    assert window.gb29446_result_grade.text() == "—"
    assert window.gb29446_result_message.text() == "尚未计算"
    window.calculate_evaluation()
    assert window.gb29446_result_ed.text() == "11.20 kW·h/t"
    assert window.gb29446_result_grade.text() == "超出3级"
    assert "未达标" not in window.gb29446_result_grade.text()

    assert not window.gb29446_scope_details.isVisible()
    window.gb29446_scope_toggle.click()
    application.processEvents()
    assert window.gb29446_scope_details.isVisible()
    assert "原煤输送至选煤厂 → 选煤产品运输出选煤厂" in window.gb29446_scope_details.text()
    assert "化验室" in window.gb29446_scope_details.text()
    window.close()
    context.database.dispose()


def test_gb29446_coal_and_process_linkage_uses_appendix_a_factors(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    context.standards.install(_gb29446_standard())
    window = MainWindow(context)
    window.navigation.setCurrentRow(2)

    process_items = [window.gb29446_process.itemData(i) for i in range(1, window.gb29446_process.count())]
    assert process_items == [
        "跳汰", "跳汰、浮选联合", "重介", "重介、浮选联合", "重介、跳汰、浮选联合"
    ]
    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("重介"))
    assert window.gb29446_factor.text() == "1.12"

    power_index = window.gb29446_coal_type.findText("动力煤")
    window.gb29446_coal_type.setCurrentIndex(power_index)
    power_processes = [window.gb29446_process.itemData(i) for i in range(1, window.gb29446_process.count())]
    assert power_processes == [
        "干法选煤", "跳汰", "跳汰、浮选联合", "跳汰、重介联合", "重介", "重介、浮选联合", "重介、跳汰、浮选联合"
    ]
    assert window.gb29446_process.currentData() == "重介"
    assert window.gb29446_factor.text() == "0.89"

    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("干法选煤"))
    coking_index = window.gb29446_coal_type.findText("炼焦煤")
    window.gb29446_coal_type.setCurrentIndex(coking_index)
    assert window.gb29446_process.currentData() is None
    assert window.gb29446_factor.text() == ""
    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("跳汰"))
    assert window.gb29446_factor.text() == "1.26"
    window.close()
    context.database.dispose()


def test_gb29446_clears_result_when_coal_or_process_changes(tmp_path: Path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    context.standards.install(_gb29446_standard())
    window = MainWindow(context)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    window.navigation.setCurrentRow(2)
    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("重介"))
    window.gb29446_electricity.setText("560")
    window.gb29446_raw_coal.setText("100")
    window.calculate_evaluation()
    assert window.gb29446_result_grade.text() == "2级"

    window.gb29446_coal_type.setCurrentIndex(window.gb29446_coal_type.findText("动力煤"))
    assert window.gb29446_result_grade.text() == "—"
    assert window.gb29446_result_message.text() == "尚未计算"
    assert window.last_result_id is None

    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("干法选煤"))
    window.gb29446_electricity.setText("100")
    window.gb29446_raw_coal.setText("100")
    window.calculate_evaluation()
    assert window.gb29446_result_grade.text() == "1级"
    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("重介"))
    assert window.gb29446_result_grade.text() == "—"
    assert window.last_result_id is None

    window.close()
    context.database.dispose()


def test_gb29446_custom_period_must_be_filled_and_is_saved(tmp_path: Path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    context.standards.install(_gb29446_standard())
    window = MainWindow(context)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    window.navigation.setCurrentRow(2)
    window.gb29446_period.setCurrentIndex(window.gb29446_period.findData("自定义"))
    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("重介"))
    assert not window.gb29446_custom_period.isHidden()
    window.calculate_evaluation()
    assert warnings == ["请填写自定义核算周期。"]
    assert context.application.list_recent_evaluations() == []

    window.gb29446_custom_period.setText("2026年第一季度")
    window.gb29446_electricity.setText("560")
    window.gb29446_raw_coal.setText("100")
    window.calculate_evaluation()
    assert window.last_result_id is not None
    saved = context.application.get_evaluation(window.last_result_id)
    assert saved is not None
    assert saved[0].notes.startswith("核算周期：自定义\n自定义周期：2026年第一季度")
    window.close()
    context.database.dispose()


def test_gb29446_month_period_is_saved_and_restored(tmp_path: Path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = _gb29446_standard()
    context.standards.install(standard)
    window = MainWindow(context)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    window.navigation.setCurrentRow(2)
    window.gb29446_period.setCurrentIndex(window.gb29446_period.findData("6月"))
    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("重介"))
    window.gb29446_electricity.setText("560")
    window.gb29446_raw_coal.setText("100")
    window.calculate_evaluation()

    assert window.last_result_id is not None
    saved = context.application.get_evaluation(window.last_result_id)
    assert saved is not None
    assert saved[0].notes == "核算周期：6月"
    assert window._load_request_into_form(saved[0])
    assert window.gb29446_period.currentData() == "6月"
    assert window.gb29446_custom_period.isHidden()

    # Existing records that stored the former all-year label remain readable.
    assert MainWindow._decode_gb29446_notes("核算周期：1月～12月") == ("全年", "", "")
    window.close()
    context.database.dispose()


@pytest.mark.parametrize(
    ("electricity", "raw_coal", "expected_message", "internal_key"),
    [
        ("", "100", "统计期选煤电力消耗量 E_d", "electricity_consumption"),
        ("100", "", "统计期入选原煤量 m", "raw_coal_input"),
        ("0", "100", "必须大于 0", "electricity_consumption"),
    ],
)
def test_gb29446_error_card_uses_chinese_labels_and_no_grade(
    tmp_path: Path, monkeypatch, electricity, raw_coal, expected_message, internal_key
) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = _gb29446_standard()
    context.standards.install(standard)
    window = MainWindow(context)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    window.navigation.setCurrentRow(2)
    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("重介"))
    window.gb29446_electricity.setText(electricity)
    window.gb29446_raw_coal.setText(raw_coal)
    window.calculate_evaluation()

    assert window.gb29446_result_grade.text() == "—"
    assert expected_message in window.gb29446_result_message.text()
    assert internal_key not in window.gb29446_result_message.text()
    assert "electricity_consumption" not in window.gb29446_result_message.text()
    assert "raw_coal_input" not in window.gb29446_result_message.text()
    assert warnings == ["输入数据未通过校验，未生成电耗等级。请查看评价结果中的提示并修正。"]

    if window.last_result_id is not None:
        saved = context.application.get_evaluation(window.last_result_id)
        assert saved is not None
        assert saved[1].results[0].grade.value == "INCOMPLETE"
    window.close()
    context.database.dispose()


def test_gb29446_full_value_boundary_explanation_matches_formal_grade(tmp_path: Path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    context.standards.install(_gb29446_standard())
    window = MainWindow(context)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    window.navigation.setCurrentRow(2)
    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("跳汰、浮选联合"))
    window.gb29446_electricity.setText("5.0000004")
    window.gb29446_raw_coal.setText("1")
    window.calculate_evaluation()

    assert window.gb29446_result_grade.text() == "2级"
    explanation = window.gb29446_explanation.text()
    assert "原始计算值（未修约）：5.0000004 kW·h/t" in explanation
    assert "判级比较：5.0000004 <= 7；结果：2级" in explanation
    assert "正式判级使用未修约 Decimal 全值与阈值直接比较" in explanation
    assert "显示位数仅用于展示，不参与判级" in explanation
    assert "ROUND(" not in explanation
    assert "numeric_behavior=" not in explanation

    window.close()
    context.database.dispose()
