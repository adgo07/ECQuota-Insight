from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from uebench.bootstrap import create_context
from uebench.domain.engine import EvaluationEngine
from uebench.domain.models import Grade, InputMode, InputValue, StandardDefinition, parse_decimal
from uebench.ui.main_window import MainWindow

from .test_gb29446 import PROCESSES, _request


ROOT = Path(__file__).parents[1]
GB29446_STANDARD_PATH = ROOT / "data" / "definitions" / "gb-29446-2019.json"


def _gb29446_standard() -> StandardDefinition:
    return StandardDefinition.model_validate_json(GB29446_STANDARD_PATH.read_text(encoding="utf-8"))


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
    assert "判级比较：6.272 ≤ 7；结果：2级" in window.gb29446_explanation.text()
    assert "结果：2级" in window.gb29446_explanation.text()
    assert "页面显示的小数位仅用于展示，不影响判级" in window.gb29446_explanation.text()
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
    assert "判级比较：5.0000004 ≤ 7；结果：2级" in explanation
    assert "判级采用原始计算值与等级限值直接比较" in explanation
    assert "页面显示的小数位仅用于展示，不影响判级" in explanation
    assert "ROUND(" not in explanation
    assert "numeric_behavior=" not in explanation

    window.close()
    context.database.dispose()


@pytest.fixture
def reference_window(tmp_path: Path, monkeypatch):
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = _gb29446_standard()
    context.standards.install(standard)
    window = MainWindow(context)
    window.navigation.setCurrentRow(2)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    def unexpected_dialog(_parent, _title, message):
        pytest.fail(f"意外业务提示：{message}")
    monkeypatch.setattr(QMessageBox, "warning", unexpected_dialog)
    monkeypatch.setattr(QMessageBox, "critical", unexpected_dialog)
    try:
        yield window, context, standard
    finally:
        window.close()
        context.database.dispose()


def _fill_reference_form(window, *, coal="炼焦煤", process="重介", electricity="560", raw_coal="100"):
    window.gb29446_coal_type.setCurrentIndex(window.gb29446_coal_type.findText(coal))
    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData(process))
    window.gb29446_electricity.setText(electricity)
    window.gb29446_raw_coal.setText(raw_coal)


def test_gb29446_data_and_scope63_definitions_are_semantically_equal():
    runtime = json.loads(GB29446_STANDARD_PATH.read_text(encoding="utf-8"))
    current = json.loads((ROOT / "standards/development/scope-63/definitions/gb-29446-2019.json").read_text(encoding="utf-8"))
    assert runtime == current


def test_gb29446_catalog_revision_matches_current_definition():
    catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
    row = next(item for item in catalog["standards"] if item["id"] == "gb-29446-2019")
    assert row["rule_revision"] == _gb29446_standard().rule_revision == 2


def test_gb29446_discovery_to_new_evaluation(reference_window):
    window, context, standard = reference_window
    window.navigation.setCurrentRow(1)
    window.standard_search.setText("29446")
    assert window.standard_table.rowCount() == 1
    assert [window.standard_table.item(0, column).text() for column in range(5)] == [
        standard.number, "选煤电力消耗限额", "当前有效", "2019", "2020-07-01"
    ]
    window.standard_table.selectRow(0)
    assert "已发布" in window.standard_detail_label.text()
    assert window.standard_indicator_table.rowCount() == 2
    assert window.standard_indicator_table.item(0, 2).text() == "kW·h/t"
    window.navigation.setCurrentRow(2)
    window.eval_standard.setCurrentIndex(window.eval_standard.findData(standard.id))
    assert window.current_standard.rule_revision == 2
    _fill_reference_form(window)
    window.calculate_evaluation()
    assert window.gb29446_result_grade.text() == "2级"


@pytest.mark.parametrize("entry", ["library", "evaluation"])
def test_gb29446_source_open_verifies_test_file_hash(tmp_path: Path, monkeypatch, entry):
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "source-appdata")
    original = _gb29446_standard()
    standard = original.model_copy(deep=True)
    source = context.paths.standards / "test-source.pdf"
    source.write_bytes(b"isolated source-open mechanism test")
    standard.source_file = source.name
    standard.source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    for product in standard.products:
        for indicator in product.indicators:
            for reference in indicator.source_references:
                reference.source_file = source.name
                reference.source_sha256 = standard.source_sha256
    context.standards.install(standard)
    window = MainWindow(context)
    opened, warnings, calls = [], [], []
    monkeypatch.setattr("uebench.ui.main_window.QDesktopServices.openUrl", lambda url: opened.append(url.toLocalFile()) or True)
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, message: warnings.append(message))
    find_source = context.application.find_standard_source
    def observed_source(standard_id, **kwargs):
        calls.append((standard_id, kwargs))
        return find_source(standard_id, **kwargs)
    monkeypatch.setattr(context.application, "find_standard_source", observed_source)
    try:
        window.standard_table.selectRow(0)
        open_source = window.open_selected_standard if entry == "library" else window.open_selected_standard_for_evaluation
        assert find_source(standard.id) == source.resolve()
        open_source()
        assert [Path(path) for path in opened] == [source.resolve()]
        assert calls[0][0] == standard.id
        if entry == "evaluation":
            assert calls[0][1]["evaluation_date"] == date.today()
        source.write_bytes(b"wrong hash for the selected standard")
        assert find_source(standard.id) is None
        open_source()
        assert len(opened) == 1
        assert warnings and "未找到" in warnings[-1]
        assert original.source_file == "28.GB 29446-2019选煤电力消耗限额.pdf"
        assert original.source_sha256 == "72011768d81cc35db8e53f6470fadc3b14140b61bd4f9ee3546a3e225e9cb15d"
    finally:
        window.close()
        context.database.dispose()


@pytest.mark.parametrize("coal,process,factor", [(coal, process, factor) for coal, processes in PROCESSES.items() for process, factor in processes.items()])
def test_gb29446_reference_form_all_twelve_factors_enter_same_engine(reference_window, coal, process, factor):
    window, context, standard = reference_window
    _fill_reference_form(window, coal=coal, process=process, electricity="100", raw_coal="100")
    assert window.gb29446_factor.isReadOnly()
    assert window.gb29446_factor.text() == factor
    request = window._collect_request()
    assert "process_factor" not in request.inputs
    assert request.inputs["electricity_consumption"].unit == "kW·h"
    assert request.inputs["raw_coal_input"].unit == "t"
    expected = EvaluationEngine().evaluate(standard, request).results[0]
    window.calculate_evaluation()
    saved = context.application.get_evaluation(window.last_result_id)[1].results[0]
    assert saved.actual_value == expected.actual_value == Decimal(factor)
    assert saved.display_values["process_factor"] == Decimal(factor)
    assert window.gb29446_result_grade.text() == MainWindow._gb29446_grade_label(expected.grade)
    assert process in window.gb29446_explanation.text()


@pytest.mark.parametrize("field", ["electricity_consumption", "raw_coal_input"])
@pytest.mark.parametrize("lexical", ["abc", "NaN", "sNaN", "Infinity", "-Infinity", "inf", "-inf"])
def test_gb29446_domain_rejects_bad_decimal_with_business_label(field, lexical):
    standard = _gb29446_standard()
    request = _request(standard, "炼焦煤")
    request.inputs[field] = InputValue(value=lexical, unit="kW·h" if field == "electricity_consumption" else "t")
    expected_label = "统计期选煤电力消耗量 E_d" if field == "electricity_consumption" else "统计期入选原煤量 m"
    with pytest.raises(ValueError) as error:
        EvaluationEngine().evaluate(standard, request)
    assert expected_label in str(error.value)
    assert ("不是有效十进制数" if lexical == "abc" else "必须是有限十进制数") in str(error.value)


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_gb29446_decimal_objects_cannot_bypass_finite_ingress(value):
    with pytest.raises(ValueError, match="电力消耗量 必须是有限十进制数"):
        parse_decimal(value, field_name="电力消耗量")


@pytest.mark.parametrize("field", ["electricity", "raw_coal"])
@pytest.mark.parametrize("lexical", ["", "0", "-1", "abc", "NaN", "sNaN", "Infinity", "-Infinity", "inf", "-inf"])
def test_gb29446_bad_input_clears_previous_grade_without_internal_error(reference_window, monkeypatch, field, lexical):
    window, context, standard = reference_window
    warnings, critical = [], []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, message: warnings.append(message))
    monkeypatch.setattr(QMessageBox, "critical", lambda _parent, _title, message: critical.append(message))
    _fill_reference_form(window)
    window.calculate_evaluation()
    assert window.gb29446_result_grade.text() == "2级"
    _fill_reference_form(window, **{field: lexical})
    window.calculate_evaluation()
    assert window.gb29446_result_grade.text() == "—"
    assert window.gb29446_result_ed.text() == "— kW·h/t"
    assert warnings and not critical
    message = window.gb29446_result_message.text() + " ".join(warnings)
    for internal in ["decimal.InvalidOperation", "ValidationError", "CalculationStep", "value.decimal", "numeric_behavior", "electricity_consumption", "raw_coal_input"]:
        assert internal not in message
    if window.last_result_id:
        assert context.application.get_evaluation(window.last_result_id)[1].results[0].grade is Grade.INCOMPLETE


@pytest.mark.parametrize("failure", ["request", "domain", "unexpected"])
def test_gb29446_attempt_failure_clears_stale_result_before_work(reference_window, monkeypatch, failure):
    window, context, standard = reference_window
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, message: messages.append(message))
    monkeypatch.setattr(QMessageBox, "critical", lambda _parent, _title, message: messages.append(message))
    _fill_reference_form(window)
    window.calculate_evaluation()
    saved_id = window.last_result_id
    request = window._collect_request()
    def fail(*args, **kwargs):
        if failure == "request":
            raise ValueError("请选择选煤工艺。")
        if failure == "domain":
            raise ValueError("统计期入选原煤量 m 必须是有限十进制数")
        raise RuntimeError("内部 CalculationStep schema/field_id 发生错误")
    if failure == "request":
        monkeypatch.setattr(window, "_collect_request", fail)
        window.calculate_evaluation()
    else:
        monkeypatch.setattr(context.application, "evaluate", fail)
        window.calculate_evaluation(request)
    assert messages
    assert window.gb29446_result_grade.text() == "—"
    assert window.gb29446_result_ed.text() == "— kW·h/t"
    assert window.last_result_id is None
    assert "CalculationStep" not in " ".join(messages)
    assert [item.evaluation_id for item in context.application.list_recent_evaluations()] == [saved_id]


def test_gb29446_unselected_or_illegal_process_cannot_produce_grade(reference_window, monkeypatch):
    window, context, standard = reference_window
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, message: warnings.append(message))
    window.calculate_evaluation()
    assert warnings == ["请选择选煤工艺。"]
    assert window.last_result_id is None
    assert window.gb29446_result_grade.text() == "—"
    request = _request(standard, "炼焦煤", process="干法选煤")
    window.calculate_evaluation(request)
    assert window.gb29446_result_grade.text() == "—"
    assert "选煤工艺" in window.gb29446_result_message.text()


@pytest.mark.parametrize("widget", ["gb29446_organization", "gb29446_period", "gb29446_custom_period", "gb29446_notes"])
def test_gb29446_metadata_change_invalidates_visible_result(reference_window, widget):
    window, context, standard = reference_window
    _fill_reference_form(window)
    window.calculate_evaluation()
    control = getattr(window, widget)
    if widget == "gb29446_period":
        control.setCurrentIndex(control.findData("6月"))
    else:
        control.setText("元数据变更")
    assert window.last_result_id is None
    assert window.gb29446_result_grade.text() == "—"
    assert window.gb29446_result_message.text() == "尚未计算"


@pytest.mark.parametrize("coal,process,electricity,expected_grade", [
    ("炼焦煤", "跳汰、浮选联合", "50", Grade.LEVEL_1),
    ("炼焦煤", "跳汰、浮选联合", "60", Grade.LEVEL_2),
    ("炼焦煤", "跳汰、浮选联合", "80", Grade.LEVEL_3),
    ("炼焦煤", "跳汰、浮选联合", "90", Grade.NOT_QUALIFIED),
    ("动力煤", "干法选煤", "10", Grade.LEVEL_1),
    ("动力煤", "干法选煤", "20", Grade.LEVEL_2),
    ("动力煤", "干法选煤", "30", Grade.LEVEL_3),
    ("动力煤", "干法选煤", "50", Grade.NOT_QUALIFIED),
])
def test_gb29446_typed_result_grade_and_coal_basis_ignore_internal_trace(reference_window, coal, process, electricity, expected_grade):
    window, context, standard = reference_window
    _fill_reference_form(window, coal=coal, process=process, electricity=electricity, raw_coal="10")
    request = window._collect_request()
    result = EvaluationEngine().evaluate(standard, request)
    item = result.results[0]
    assert item.grade is expected_grade
    clauses = {ref.clause.split(" ", 1)[0] for ref in item.source_references}
    retained_clauses = {"4.1.1", "4.1.2"} if coal == "炼焦煤" else {"4.2.1", "4.2.2"}
    assert retained_clauses <= clauses
    for step in item.calculation_trace:
        if step.operation == "grade_comparison":
            step.expression = "numeric_behavior=not-a-display-protocol; malformed internal text"
    window._show_gb29446_result(request, result)
    basis = window.gb29446_basis.text()
    assert ("等级依据：第3.1条，表1" if coal == "炼焦煤" else "等级依据：第3.2条，表2") in basis
    assert ("第3.2条" if coal == "炼焦煤" else "第3.1条") not in basis
    assert "计算依据：第5.2条，式（1）" in basis
    assert "折算系数依据：附录A表A.1" in basis
    assert "第4." not in basis
    assert window.gb29446_result_grade.text() == MainWindow._gb29446_grade_label(expected_grade)
    text = window.gb29446_explanation.text()
    assert (" > " if expected_grade is Grade.NOT_QUALIFIED else " ≤ ") in text
    for internal in ["Decimal", "numeric_behavior=", "malformed", "calculator", "rule_id", item.indicator_id]:
        assert internal not in text


def test_gb29446_finite_scientific_input_has_no_invented_business_maximum(reference_window):
    window, context, standard = reference_window
    assert parse_decimal("1e999", field_name="电力消耗量") == Decimal("1e999")
    _fill_reference_form(window, process="跳汰、浮选联合", electricity="1e999", raw_coal="1")
    window.calculate_evaluation()
    assert window.gb29446_result_grade.text() == "超出3级"
    item = context.application.get_evaluation(window.last_result_id)[1].results[0]
    assert item.actual_value == Decimal("1e999")
    assert item.actual_value.is_finite()


def test_gb29446_explanation_preserves_exact_small_boundary_difference(reference_window):
    window, context, standard = reference_window
    _fill_reference_form(window, process="跳汰、浮选联合", electricity="5.0000000000000001", raw_coal="1")
    window.calculate_evaluation()
    assert window.gb29446_result_ed.text() == "5.00 kW·h/t"
    assert window.gb29446_result_grade.text() == "2级"
    assert "判级比较：5.0000000000000001 ≤ 7；结果：2级" in window.gb29446_explanation.text()
