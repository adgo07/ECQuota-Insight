"""第一阶段共同样板行为；使用真实 Qt 控件和隔离数据库。"""
import os
from datetime import date
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QTabWidget
from uebench.bootstrap import create_context
from uebench.domain.models import StandardDefinition, LifecycleStatus
from uebench.ui.main_window import MainWindow

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def window(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    # 离屏平台默认只有 800×800；代表桌面宽度测试显式给定工作区，
    # 窗口约束本身另以大小屏、负坐标和掉屏用例验证。
    from PySide6.QtGui import QScreen
    from PySide6.QtCore import QRect
    monkeypatch.setattr(QScreen, "availableGeometry", lambda self: QRect(0, 0, 1920, 1080))
    for name in ("warning", "critical", "information"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: QMessageBox.Ok)
    context = create_context(tmp_path / "app")
    for name in ("gb-29446-2019", "gb-16780-2021", "gb-21343-2023"):
        standard = StandardDefinition.model_validate_json((ROOT / "data/definitions" / (name+".json")).read_text(encoding="utf-8"))
        context.standards.install(standard)
    win = MainWindow(context)
    win.show()
    app.processEvents()
    yield win
    win.close()
    context.database.dispose()

def row_for(window, sid):
    return next(r for r in range(window.standard_table.rowCount()) if window.standard_table.item(r, 0).data(Qt.UserRole) == sid)

def fill_and_calculate(window):
    window.start_formal_evaluation()
    window.gb29446_coal_type.setCurrentIndex(window.gb29446_coal_type.findText("炼焦煤"))
    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("重介、浮选联合"))
    window.gb29446_electricity.setText("8000000")
    window.gb29446_raw_coal.setText("1000000")
    window.calculate_button.click()
    assert window.last_result_id

def test_shell_disabled_entries_and_named_navigation(window):
    assert window.sidebar.isHidden()
    assert window.home_recent.isHidden()
    assert not window.home_empty_start.isHidden()
    assert list(window.home_task_buttons) == ["standards", "evaluation", "import", "records", "factors"]
    for key, row in (("import", 3), ("factors", 5)):
        assert not window.home_task_buttons[key].isEnabled()
        assert not (window.navigation.item(row).flags() & Qt.ItemIsEnabled)
        window.navigate(key)
        assert window.pages.currentWidget() is window.page_widgets["home"]
    window.navigate("settings")
    assert window.sidebar.isHidden()
    assert not window.settings_page.home_button.isHidden()
    window.navigate("records")
    assert window.navigation.currentItem().data(Qt.UserRole) == "records"
    window.navigate("home")
    assert window.sidebar.isHidden()

@pytest.mark.parametrize("column", [0, 1])
def test_standard_number_and_title_open_same_detail_and_preserve_context(window, column):
    window.navigate("standards")
    window.standard_search.setText("29446")
    item = window.standard_table.item(0, column)
    rect = window.standard_table.visualItemRect(item)
    QTest.mouseClick(window.standard_table.viewport(), Qt.LeftButton, pos=rect.center())
    assert window.pages.currentWidget() is window.page_widgets["standard_detail"]
    assert not window.sidebar.isHidden()
    assert window.navigation.currentItem().data(Qt.UserRole) == "standards"
    assert not window.page_widgets["standard_detail"].findChildren(QTabWidget)
    window.navigate("standards")
    assert window.standard_search.text() == "29446"
    assert window.standard_table.currentRow() == 0

def test_three_standard_states_and_status_filter(window):
    assert window.standard_table.columnCount() == 5
    for sid, supported, phrase in (("gb-29446-2019", True, "映射已确认"), ("gb-16780-2021", False, "V1.2 已批准版"), ("gb-21343-2023", False, "待整理确认")):
        window.standard_table.selectRow(row_for(window, sid))
        window.show_standard_detail()
        assert phrase in window.standard_confirmation_label.text()
        assert window.standard_evaluate_button.isEnabled() == supported
        assert bool(window.standard_indicator_table.rowCount()) == supported
        if supported:
            assert "第3.1条" in window.standard_requirements_basis.text()
            assert "表1" in window.standard_requirements_basis.text()
            assert "第3.2条" in window.standard_requirements_basis.text()
        else:
            assert window.standard_requirements_basis.text() == ""
    window.standard_status_filter.setCurrentText("尚未实施")
    assert window.standard_table.rowCount() == 0
    window.standard_status_filter.setCurrentIndex(0)
    window.standard_search.setText("煤炭洗选")
    assert window.standard_table.rowCount() == 1

def test_result_saved_once_navigation_preserves_input_and_edits_invalidate(window):
    fill_and_calculate(window)
    rid = window.last_result_id
    assert window.context.application.count_evaluations() == 1
    assert window.gb29446_result_grade.text() == "2级"
    assert window.gb29446_result_ed.text() == "6.64 kW·h/t"
    window.navigate("standards")
    window.start_formal_evaluation()
    assert window.gb29446_electricity.text() == "8000000"
    assert window.last_result_id == rid
    window.gb29446_electricity.setText("9000000")
    assert window.last_result_id is None
    assert "数据已修改" in window.gb29446_result_message.text()
    assert not window.gb29446_export_word.isEnabled()
    assert not window.gb29446_view_record.isEnabled()
    assert window.context.application.count_evaluations() == 1

def test_radio_linkage_and_responsive_fields(window):
    window.start_formal_evaluation()
    assert window.eval_standard.isHidden()
    assert "GB 29446-2019" in window.eval_standard_summary.text()
    assert "选煤电力消耗限额" in window.eval_standard_summary.text()
    radio = next(b for b in window.coal_button_group.buttons() if b.text() == "动力煤")
    radio.click()
    assert window.gb29446_coal_type.currentText() == "动力煤"
    assert window.gb29446_process.currentData() is None
    assert window.gb29446_factor.text() == ""
    assert window.gb29446_factor.isReadOnly()
    window.resize(1180,760)
    QApplication.processEvents()
    assert window.gb29446_business_fields.columns == 1
    window.resize(1440,900)
    QApplication.processEvents()
    assert window.gb29446_business_fields.columns == 2

def test_home_failure_is_retryable_and_recent_values_are_saved(window, monkeypatch):
    fill_and_calculate(window)
    assert not window.home_recent.isHidden()
    assert window.home_empty_start.isHidden()
    assert window.home_recent.item(0, 0).text() == "未填写企业名称"
    assert "6.64" in window.home_recent.item(0, 3).text()
    original = window.context.application.list_recent_evaluations
    monkeypatch.setattr(window.context.application, "list_recent_evaluations", lambda *a: (_ for _ in ()).throw(OSError("test")))
    window.refresh_home()
    assert "读取失败" in window.home_recent_notice.text()
    assert not window.home_retry.isHidden()
    assert window.home_recent.isHidden()
    assert window.home_empty_start.isHidden()
    monkeypatch.setattr(window.context.application, "list_recent_evaluations", original)
    window.home_retry.click()
    assert window.home_recent.rowCount() == 1
    assert window.home_retry.isHidden()

@pytest.mark.parametrize("render_failure", [False, True])
def test_saved_action_transition_never_recalculates_on_view(window, monkeypatch, render_failure):
    calls = []
    evaluate = window.context.application.evaluate
    def record_evaluation(request):
        calls.append(request)
        return evaluate(request)
    monkeypatch.setattr(window.context.application, "evaluate", record_evaluation)
    if render_failure:
        monkeypatch.setattr(window, "_show_gb29446_result", lambda *a: (_ for _ in ()).throw(RuntimeError("render")))
    fill_and_calculate(window)
    saved = window.last_result_id
    assert len(calls) == 1
    assert window.calculate_button.text() == "重新计算并生成新记录"
    assert window.gb29446_view_record.isEnabled()
    if render_failure:
        assert "记录已保存" in window.gb29446_result_message.text()
        assert not window.gb29446_export_word.isEnabled()
    window.gb29446_view_record.click()
    assert window.record_detail_page.record_id == saved
    assert len(calls) == 1
    assert window.context.application.count_evaluations() == 1
    window.gb29446_electricity.setText("9000000")
    assert window.calculate_button.text() == "计算并判级"
    assert window.last_result_id is None
    assert not window.gb29446_view_record.isEnabled()
    assert not window.gb29446_export_word.isEnabled()
    window.navigate("evaluation")
    window.calculate_button.click()
    assert len(calls) == 2
    assert window.last_result_id != saved
    assert window.context.application.count_evaluations() == 2

def test_saved_record_remains_accessible_if_result_rendering_fails(window, monkeypatch):
    monkeypatch.setattr(window, "_show_gb29446_result", lambda *a: (_ for _ in ()).throw(RuntimeError("render")))
    fill_and_calculate(window)
    assert window.context.application.count_evaluations() == 1
    assert "记录已保存" in window.gb29446_result_message.text()
    assert window.gb29446_view_record.isEnabled()
    assert not window.gb29446_export_word.isEnabled()

def test_standard_read_failure_has_retry(window, monkeypatch):
    original = window.context.application.list_library_standards
    monkeypatch.setattr(window.context.application, "list_library_standards", lambda: (_ for _ in ()).throw(OSError("catalogue")))
    window.refresh_standards()
    assert "读取失败" in window.standard_count_label.text()
    assert not window.standard_retry.isHidden()
    monkeypatch.setattr(window.context.application, "list_library_standards", original)
    window.standard_retry.click()
    assert window.standard_table.rowCount() == 3

def test_historical_catalogue_entry_is_reachable_by_status(window):
    standard = window.context.application.get_standard("gb-21343-2023").model_copy(deep=True, update={
        "id": "history-fixture", "number": "GB 99999-2023", "standard_family_id": "GB 99999",
        "lifecycle_status": LifecycleStatus.OBSOLETE, "obsolete_date": date(2026, 1, 1),
    })
    window.context.standards.install(standard)
    window.refresh_standards()
    window.standard_status_filter.setCurrentText("历史/已替代")
    assert window.standard_table.rowCount() == 1
    assert window.standard_table.item(0, 0).data(Qt.UserRole) == "history-fixture"


@pytest.mark.parametrize("size", [(1440, 900), (900, 600)])
def test_calculation_scrolls_to_heading_and_core_result_only_on_success(window, size):
    window.resize(*size)
    fill_and_calculate(window)
    for _ in range(4):
        QApplication.processEvents()
    viewport = window.evaluation_scroll.viewport()
    for widget in (window.gb29446_result_heading, window.gb29446_result_ed, window.gb29446_result_grade):
        position = widget.mapTo(viewport, QPoint(0, 0))
        assert position.y() >= 0
        assert position.y() + widget.height() <= viewport.height()
    assert window.context.application.count_evaluations() == 1
    window.gb29446_electricity.setText("0")
    assert window.last_result_id is None
    assert not window.gb29446_view_record.isEnabled()
    window.calculate_button.click()
    QApplication.processEvents()
    position = window.gb29446_electricity.mapTo(viewport, QPoint(0, 0))
    assert 0 <= position.y() < viewport.height()
    assert window.gb29446_electricity.hasFocus()
    assert window.context.application.count_evaluations() == 1
