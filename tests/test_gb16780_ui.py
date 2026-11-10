"""水泥未开放路径的离屏交互，不能替代原生窗口验收。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
import pytest

from uebench.ui.main_window import MainWindow
from uebench.domain.gb16780 import DEDUCTIONS
from .test_gb16780_application import cement_context, request, state


@pytest.fixture
def window(cement_context, monkeypatch):
    app = QApplication.instance() or QApplication([])
    for name in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, name, lambda *args: None)
    widget = MainWindow(cement_context)
    widget.cement_form.load(request())
    yield widget
    widget.close()
    app.processEvents()


def test_cement_detail_page_reuses_shell_and_hides_direct_ui(window):
    assert window.current_standard.id == "gb-16780-2021"
    assert window.input_controls_container.isHidden()
    assert not window.cement_form.isHidden()
    assert window.gb29446_form_container.isHidden()
    assert window._collect_request().input_mode.value == "DETAIL"
    assert window.eval_standard_open.isEnabled()
    assert window.eval_official_status.text() == "国家标准全文公开系统"


def test_four_deductions_blank_placeholder_and_decimal_text_are_preserved(window):
    line = window.cement_form.lines[0]
    for key in DEDUCTIONS:
        line.fields[key].clear()
        assert line.fields[key].placeholderText() == "若已扣除，则不填"
    exact = "2000.0000000000000000000000000001"
    line.fields["cement.production_t"].setText(exact)
    collected = window._collect_request().cement_lines[0]
    assert collected.inputs["cement.production_t"].value == exact
    assert all(key not in collected.inputs for key in DEDUCTIONS)


def test_saved_once_double_signal_no_second_save_and_edit_invalidates(window):
    window.calculate_evaluation()
    rid = window.last_result_id
    assert rid and state(window.context) == (1, 1)
    assert window.cement_view_record.isEnabled() and window.cement_export_word.isEnabled()
    assert not window.calculate_button.isEnabled()
    window.calculate_evaluation()
    assert window.last_result_id == rid and state(window.context) == (1, 1)
    window.cement_form.lines[0].fields["cement.production_t"].setText("2001")
    assert window.last_result_id is None
    assert window.calculate_button.isEnabled()
    assert not window.cement_export_word.isEnabled()
    assert "数据已修改" in window.cement_notice.text()


def test_partial_preview_keeps_complete_indicators_and_no_record(window):
    window.cement_form.lines[0].fuels.table.item(0, 1).setText("")
    window.calculate_evaluation()
    assert state(window.context) == (0, 0) and window.last_result_id is None
    assert "部分预览" in window.cement_notice.text()
    text = window.cement_results.toPlainText()
    assert "57.00" in text and "34.00" in text
    assert not window.cement_view_record.isEnabled() and not window.cement_export_word.isEnabled()


def test_mode_switch_does_not_submit_hidden_kiln_data(window):
    line = window.cement_form.lines[0]
    line.mode.setCurrentIndex(line.mode.findData("purchased_clinker_grinding"))
    collected = window._collect_request().cement_lines[0]
    assert set(collected.inputs) == {"cement.production_t", "cement.preparation_electricity_kwh"}
    assert not collected.fuels
    window.calculate_evaluation()
    assert state(window.context) == (1, 1)
    assert window.cement_results.toPlainText().count("不适用") == 4


def test_readonly_saved_record_two_tabs_and_no_engine(window, monkeypatch):
    window.calculate_evaluation()
    rid = window.last_result_id

    def forbidden(*args, **kwargs):
        raise AssertionError("历史展示不能重算")

    monkeypatch.setattr(window.context.evaluation_service.engine, "evaluate", forbidden)
    window.view_record(rid)
    detail = window.record_detail_page
    assert detail.tabs.count() == 2
    assert detail.tabs.tabText(0) == "基本信息与结果"
    assert detail.tabs.tabText(1) == "输入数据与计算依据"
    assert "生产线" in detail.result_content.toPlainText()
    assert "93.33" in detail.result_content.toPlainText()
    assert "93.32515" in detail.input_content.toPlainText()
    assert "海拔修正系数K" in detail.input_content.toPlainText()
    assert detail.export_button.isEnabled()
    assert state(window.context) == (1, 1)


def test_shared_form_collects_selected_participants_and_raw_fuel(window):
    form = window.cement_form
    second = form.lines[0].collect().model_copy(deep=True, update={"line_id": "second", "line_name": "第二线"})
    form.add_line(second)
    form.add_shared()
    shared = form.shared[0]
    for index in range(shared.participants.count()):
        shared.participants.item(index).setCheckState(Qt.CheckState.Checked)
    shared.amount.setText("8000.00000000000000001")
    collected = window._collect_request()
    assert collected.cement_shared_energy[0].line_ids == [form.lines[0].line_id, "second"]
    assert collected.cement_shared_energy[0].amount.value == "8000.00000000000000001"
    shared.target.setCurrentIndex(shared.target.findData("clinker_fuel"))
    shared.fuels.add()
    for col, value in enumerate(("共用燃料", "1000", "29307")):
        shared.fuels.table.item(0, col).setText(value)
    value = window._collect_request().cement_shared_energy[0]
    assert value.amount is None and value.fuels[0].mass_kg == "1000"


def test_add_remove_lines_and_rename_invalidate_result_and_shared_labels(window):
    window.calculate_evaluation()
    form = window.cement_form
    second = form.add_line()
    assert window.last_result_id is None and not window.cement_export_word.isEnabled()
    form.add_shared()
    second.name.setText("很长的第二生产线中文名称")
    labels = [form.shared[0].participants.item(i).text() for i in range(form.shared[0].participants.count())]
    assert "很长的第二生产线中文名称" in labels
    form.remove_line(second)
    assert len(form.lines) == 1 and form.shared[0].participants.count() == 1
