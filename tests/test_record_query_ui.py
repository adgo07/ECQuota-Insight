"""全库只读查询及分页历史页：超过 200 条、损坏隔离及快照保护。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from datetime import datetime, timezone
from pathlib import Path
import json
import pytest
from sqlalchemy import text, event
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QFileDialog
from uebench.bootstrap import create_context
from uebench.domain.models import StandardDefinition, Grade
from uebench.domain.engine import EvaluationEngine
from uebench.ui.main_window import MainWindow
from .test_gb29446 import _request

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def records(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
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
