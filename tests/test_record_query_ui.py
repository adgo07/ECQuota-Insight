"""全库只读查询及分页历史页：超过 200 条、损坏隔离及快照保护。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from datetime import datetime, timezone
from pathlib import Path
import json
import pytest
from sqlalchemy import text, event
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QFileDialog
from PySide6.QtCore import Qt, QRect
from PySide6.QtTest import QTest
from uebench.bootstrap import create_context
from uebench.domain.models import StandardDefinition, Grade
from uebench.domain.engine import EvaluationEngine
from uebench.ui.main_window import MainWindow
from .test_gb29446 import _request

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def records(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    # 离屏平台默认只有 800×800；代表桌面宽度测试显式给定工作区，
    # 窗口约束本身另以大小屏、负坐标和掉屏用例验证。
    from PySide6.QtGui import QScreen
    from PySide6.QtCore import QRect
    monkeypatch.setattr(QScreen, "availableGeometry", lambda self: QRect(0, 0, 1920, 1080))
    for name in ("warning", "critical", "information"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: QMessageBox.Ok)
    context = create_context(tmp_path / "records")
    standard = StandardDefinition.model_validate_json((ROOT / "data/definitions/gb-29446-2019.json").read_text(encoding="utf-8"))
    context.standards.install(standard)
    request = _request(standard, "炼焦煤", process="重介、浮选联合", electricity="8000000", raw_coal="1000000")
    result = context.application.preview_evaluation(request)
    stamp = datetime(2026, 10, 1, tzinfo=timezone.utc)
    for index in range(225):
        req = request.model_copy(deep=True, update={"organization_name": "最早企业_100%" if index == 0 else f"企业{index:03}", "notes": "核算周期：自定义\n自定义周期：历史第三季度"})
        saved = result.model_copy(deep=True, update={"evaluation_id": f"{index:036}", "evaluated_at": stamp})
        context.evaluations.save(req, saved, standard)
    with context.database.engine.begin() as connection:
        connection.execute(text("UPDATE evaluations SET result_json='{' WHERE evaluation_id=:id"), {"id": f"{12:036}"})
    win = MainWindow(context)
    win.show()
    yield context, win
    win.close()
    context.database.dispose()

def forbid(*a, **k):
    raise AssertionError("历史只读查询不得计算或读取当前规则")

def test_all_records_search_count_ties_and_corruption(records, monkeypatch):
    context, win = records
    monkeypatch.setattr(EvaluationEngine, "evaluate", forbid)
    statements = []
    event.listen(context.database.engine, "before_cursor_execute", lambda c, u, statement, *a: statements.append(statement))
    first = context.application.query_evaluations()
    assert first.total == 225 and len(first.items) == 20
    assert [item.evaluation_id for item in first.items] == [f"{i:036}" for i in range(224, 204, -1)]
    last = context.application.query_evaluations(page=12)
    assert last.total == 225 and len(last.items) == 5
    assert last.items[-1].organization == "最早企业_100%"
    assert context.application.query_evaluations(query="最早企业_100%", status="2级").total == 1
    assert context.application.query_evaluations(query="历史第三季度").total == 225
    broken = context.application.query_evaluations(status="记录损坏")
    assert broken.total == 1 and broken.items[0].evaluation_id == f"{12:036}"
    assert context.application.query_evaluations(status="2级").total == 224
    page_selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert page_selects and not any("rule_snapshot_json" in s for s in page_selects)
    assert all("uebench_saved_summary" in s or "count(" in s for s in page_selects)

def test_page_return_context_direct_id_and_two_tabs(records, monkeypatch):
    context, win = records
    monkeypatch.setattr(EvaluationEngine, "evaluate", forbid)
    win.navigate("records")
    for _ in range(11):
        win.record_next.click()
    assert win._record_page == 12
    win.record_table.selectRow(4)
    selected = win._selected_record_id()
    before = context.application.get_evaluation(selected)
    raw = tuple(obj.model_dump_json() for obj in before)
    monkeypatch.setattr(context.application, "get_standard", forbid)
    monkeypatch.setattr(context.application, "get_published_standard", forbid)
    win.view_selected_record()
    detail = win.record_detail_page
    assert win.pages.currentWidget() is detail
    assert [detail.tabs.tabText(i) for i in range(detail.tabs.count())] == ["基本信息与结果", "输入数据与计算依据"]
    assert detail.result_content.isReadOnly() and detail.input_content.isReadOnly()
    assert "2级" in detail.result_content.toPlainText()
    assert "8000000" in detail.input_content.toPlainText()
    detail.back_requested.emit()
    assert win._record_page == 12 and win._selected_record_id() == selected
    assert tuple(obj.model_dump_json() for obj in context.application.get_evaluation(selected)) == raw
    # 脱离当前页直接打开最早 ID，不依赖最近 200 条或行选中。
    win._record_page = 1
    win.refresh_records()
    win._open_home_record(f"{0:036}")
    assert detail.record_id == f"{0:036}" and "最早企业" in detail.title.text()
    visible_actions = [b.text() for b in win.page_widgets["records"].findChildren(QPushButton)]
    assert not any("重新评价" in t or "审计" in t for t in visible_actions)

def test_last_page_delete_filters_and_retry(records, monkeypatch):
    context, win = records
    win.navigate("records")
    win.record_search.setText("最早企业")
    win._record_filters_changed()
    assert win.record_table.rowCount() == 1 and "共 1 条" in win.record_count_label.text()
    win.record_search.clear()
    win._record_filters_changed()
    win._record_page = 12
    win.refresh_records()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    for _ in range(5):
        win.record_table.selectRow(0)
        win.delete_selected_record()
    assert win._record_page == 11 and "共 220 条" in win.record_count_label.text()
    win.record_status_filter.setCurrentText("记录损坏")
    assert win.record_table.rowCount() == 1 and "共 1 条" in win.record_count_label.text()
    win.record_table.selectRow(0)
    win.view_selected_record()
    assert "记录损坏" in win.record_detail_page.notice.text()
    assert not win.record_detail_page.export_button.isEnabled()
    win.navigate("records")
    original = context.application.query_evaluations
    monkeypatch.setattr(context.application, "query_evaluations", lambda **k: (_ for _ in ()).throw(OSError("read")))
    win.refresh_records()
    assert "读取失败" in win.record_count_label.text()
    monkeypatch.setattr(context.application, "query_evaluations", original)
    win.refresh_records()
    assert win.record_table.rowCount() == 1


def test_word_action_uses_direct_record_id_and_saved_snapshot(records, monkeypatch, tmp_path):
    context, win = records
    monkeypatch.setattr(EvaluationEngine, "evaluate", forbid)
    monkeypatch.setattr(context.application, "get_standard", forbid)
    win.view_record(f"{0:036}")
    target = tmp_path / "最早记录.docx"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), "Word"))
    exported = []
    export = context.application.export_word_report
    def spy(rid, path):
        exported.append(rid)
        return export(rid, path)
    monkeypatch.setattr(context.application, "export_word_report", spy)
    win.record_detail_page.export_button.click()
    assert exported == [f"{0:036}"]
    assert target.is_file()
    assert context.application.count_evaluations() == 225


def test_saved_incomplete_record_has_real_word_reason(records):
    context, win = records
    request, result, snapshot = context.application.get_evaluation(f"{0:036}")
    result = result.model_copy(deep=True, update={"evaluation_id": "incomplete-fixture"})
    result.results[0].grade = Grade.INCOMPLETE
    result.results[0].actual_value = None
    context.evaluations.save(request, result, snapshot)
    win.view_record(result.evaluation_id)
    assert not win.record_detail_page.export_button.isEnabled()
    assert "未形成有效电耗等级" in win.record_detail_page.notice.text()


@pytest.mark.parametrize("grade,label", [(Grade.INCOMPLETE, "不完整"), (Grade.NOT_APPLICABLE, "不适用")])
def test_saved_exceptional_status_stays_distinct_and_readonly(records, monkeypatch, grade, label):
    context, win = records
    request, result, snapshot = context.application.get_evaluation(f"{0:036}")
    request.organization_name = "A<b>x</b>B & 特殊企业"
    result.evaluation_id = "status-fixture"
    result.results[0].grade = grade
    result.results[0].actual_value = None
    context.evaluations.save(request, result, snapshot)
    raw = tuple(x.model_dump_json() for x in context.application.get_evaluation(result.evaluation_id))
    monkeypatch.setattr(EvaluationEngine, "evaluate", forbid)
    monkeypatch.setattr(context.application, "get_standard", forbid)
    monkeypatch.setattr(context.application, "get_published_standard", forbid)
    assert context.application.query_evaluations().total == 226
    page = context.application.query_evaluations(status=label)
    assert page.total == 1 and page.items[0].status == label
    other = "不适用" if label == "不完整" else "不完整"
    assert context.application.query_evaluations(status=other).total == 0
    win.navigate("records")
    win.record_status_filter.setCurrentText(label)
    assert win.record_table.rowCount() == 1
    assert win.record_table.item(0, 4).text() == label
    assert "共 1 条" in win.record_count_label.text()
    win.view_record(result.evaluation_id)
    assert label in win.record_detail_page.result_content.toPlainText()
    assert win.record_detail_page.title.textFormat() == Qt.TextFormat.PlainText
    assert win.record_detail_page.title.text() == request.organization_name
    assert tuple(x.model_dump_json() for x in context.application.get_evaluation(result.evaluation_id)) == raw
    assert context.application.count_evaluations() == 226


def click_navigation(win, key):
    item = next(win.navigation.item(i) for i in range(win.navigation.count()) if win.navigation.item(i).data(Qt.UserRole) == key)
    QApplication.processEvents()
    QTest.mouseClick(win.navigation.viewport(), Qt.LeftButton, pos=win.navigation.visualItemRect(item).center())
    QApplication.processEvents()


def test_parent_sidebar_mouse_return_context_and_single_navigation(records, monkeypatch):
    _, win = records
    win.navigate("records")
    win.record_search.setText("企业")
    win._record_filters_changed()
    win._record_page = 12
    win.refresh_records()
    win.record_table.selectRow(2)
    selected = win._selected_record_id()
    win.view_selected_record()
    click_navigation(win, "records")
    assert win.pages.currentWidget() is win.page_widgets["records"]
    assert win.record_search.text() == "企业" and win._record_page == 12
    assert win._selected_record_id() == selected
    win.navigate("standards")
    win.standard_table.selectRow(0)
    win.show_standard_detail()
    click_navigation(win, "standards")
    assert win.pages.currentWidget() is win.page_widgets["standards"]
    calls = []
    navigate = win.navigate
    def spy(key):
        calls.append(key)
        navigate(key)
    monkeypatch.setattr(win, "navigate", spy)
    click_navigation(win, "records")
    assert calls == ["records"]
    calls.clear()
    click_navigation(win, "import")
    assert calls == []
    win.navigation.setFocus()
    win.navigation.setCurrentRow(4)  # 键盘导航仍经过 currentRowChanged。
    QTest.keyClick(win.navigation, Qt.Key_Up)  # 跳过禁用的导入，进入新建。
    assert win.pages.currentWidget() is win.page_widgets["evaluation"]


def test_record_columns_fit_reference_window_and_wrap_long_names(records):
    _, win = records
    win.resize(1440, 900)
    win.navigate("records")
    QApplication.processEvents()
    table = win.record_table
    table.item(0, 0).setText("企业名称很长需要换行" * 6)
    table.item(0, 2).setText("GB 29446—2019 选煤电力消耗限额" * 4)
    table.fit_columns()
    QApplication.processEvents()
    assert sum(table.columnWidth(i) for i in range(7)) <= table.viewport().width()
    assert table.horizontalScrollBar().maximum() == 0
    assert table.columnWidth(6) >= 88
    assert table.rowHeight(0) > 60
    assert table.rowHeight(0) >= table.sizeHintForRow(0)
    for column in (0, 2):
        text_height = table.fontMetrics().boundingRect(QRect(0, 0, table.columnWidth(column) - 16, 100000), Qt.TextWordWrap, table.item(0, column).text()).height()
        assert table.rowHeight(0) >= text_height + 16
    button = table.cellWidget(0, 6)
    assert table.viewport().rect().contains(button.geometry())
    win.resize(900, 600)
    QApplication.processEvents()
    assert table.horizontalScrollBar().maximum() > 0
    assert table.columnWidth(6) >= 88
