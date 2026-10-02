"""RS02 产品生命周期 Gate；业务数学矩阵仍由 RS01 / Numeric Gate 承担。"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton, QTextEdit

from uebench.bootstrap import create_context
from uebench.domain.engine import EvaluationEngine
from uebench.domain.models import EvaluationRequest, EvaluationResult, Grade, InputValue, StandardDefinition, StandardSelectionMode
from uebench.ui.main_window import MainWindow
from .test_gb29446 import _request
from .test_engine import make_standard

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/gb29446_record_r2.json"


def standard_r2():
    return StandardDefinition.model_validate_json((ROOT / "data/definitions/gb-29446-2019.json").read_text(encoding="utf-8"))


def request_r2(standard, electricity="560"):
    request = _request(standard, "炼焦煤", process="重介", electricity=electricity, raw_coal="100")
    request.organization_name = "宁夏测试企业"
    request.notes = MainWindow._encode_gb29446_notes("自定义", "2026年6月", "生命周期测试")
    return request


def normalized(loaded):
    return [json.loads(model.model_dump_json()) for model in loaded]


def raw_state(context, evaluation_id):
    with context.database.engine.connect() as connection:
        row = tuple(connection.execute(text("SELECT * FROM evaluations WHERE evaluation_id=:id"), {"id": evaluation_id}).one())
        audits = connection.execute(text("SELECT COUNT(*) FROM audit_log")).scalar_one()
    return row, audits


def forbidden(*args, **kwargs):
    raise AssertionError("历史只读操作不得运行 Engine / 当前标准查询")


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def lifecycle(tmp_path, qt_app, monkeypatch):
    context = create_context(tmp_path / "中文数据")
    standard = standard_r2()
    context.standards.install(standard)
    request = request_r2(standard)
    result = context.application.evaluate(request)
    window = MainWindow(context)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: pytest.fail(str(args)))
    try:
        yield context, window, request, result, standard
    finally:
        window.close()
        context.database.dispose()


def select_record(window, evaluation_id):
    window.refresh_records()
    for row in range(window.record_table.rowCount()):
        if window.record_table.item(row, 0).data(Qt.ItemDataRole.UserRole) == evaluation_id:
            window.record_table.selectRow(row)
            return
    raise AssertionError("记录未出现")


def detail_text(window):
    return window.record_detail_dialog.findChild(QTextEdit, "record_detail_content").toPlainText()


def technical_text(window):
    return window.record_detail_dialog.findChild(QTextEdit, "record_detail_technical").toPlainText()


def install_r3(context, standard):
    r3 = standard.model_copy(deep=True, update={"rule_revision": 3, "title": "测试新版标准标题"})
    r3.products[0].name = "测试新版煤种名称"
    r3.products[0].indicators[0].thresholds.level_1.value = "6.5"
    r3.source_file = "r3.pdf"
    source = context.paths.standards / r3.source_file
    source.write_bytes(b"test r3 PDF")
    r3.source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    for product in r3.products:
        for indicator in product.indicators:
            for reference in indicator.source_references:
                reference.source_file = r3.source_file
                reference.source_sha256 = r3.source_sha256
                reference.note = "仅供测试的新版依据"
    context.standards.install(r3)
    return r3


# A. 通用 Record Lifecycle

def test_frozen_r2_historical_json_remains_deserializable():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    models = [EvaluationRequest, EvaluationResult, StandardDefinition]
    keys = ["request_json", "result_json", "rule_snapshot_json"]
    parsed = [model.model_validate_json(fixture[key]) for model, key in zip(models, keys)]
    assert parsed[0].standard_id == parsed[1].standard_id == parsed[2].id
    assert parsed[1].rule_revision == parsed[2].rule_revision == 2


def test_save_get_roundtrip_and_frozen_fixture_storage(lifecycle):
    context, _window, request, result, standard = lifecycle
    assert normalized(context.application.get_evaluation(result.evaluation_id)) == normalized((request, result, standard))
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    old = tuple(model.model_validate_json(fixture[key]) for model, key in zip(
        [EvaluationRequest, EvaluationResult, StandardDefinition], ["request_json", "result_json", "rule_snapshot_json"]))
    context.evaluations.save(*old)
    assert normalized(context.application.get_evaluation(old[1].evaluation_id)) == normalized(old)


def test_view_is_readonly_no_engine_no_current_metadata(lifecycle, monkeypatch):
    context, window, request, result, standard = lifecycle
    select_record(window, result.evaluation_id)
    before = raw_state(context, result.evaluation_id)
    workspace = (window.last_result_id, window.gb29446_electricity.text())
    monkeypatch.setattr(EvaluationEngine, "evaluate", forbidden)
    monkeypatch.setattr(context.application, "get_standard", forbidden)
    monkeypatch.setattr(context.application, "get_standard_for_evaluation", forbidden)
    window.view_selected_record()
    assert raw_state(context, result.evaluation_id) == before
    assert workspace == (window.last_result_id, window.gb29446_electricity.text())
    ordinary = detail_text(window)
    for expected in ["宁夏测试企业", "2026年6月", "炼焦煤", "重介", "E_d：560", "m：100", "折算系数 k：1.12", "6.272", "2级", "e_d = 560 × 1.12 / 100", "第3.1条", "第5.2条", "附录A"]:
        assert expected in ordinary
    assert result.evaluation_id not in ordinary
    assert "numeric_profile_id" not in ordinary
    technical = window.record_detail_dialog.findChild(QTextEdit, "record_detail_technical")
    assert technical.isHidden()
    for expected in [result.evaluation_id, "rule_revision: 2", result.rule_snapshot_sha256, result.numeric_profile_id, request.model_dump_json(), result.model_dump_json(), standard.model_dump_json()]:
        assert expected in technical.toPlainText()
    next(button for button in window.record_detail_dialog.findChildren(QPushButton) if button.text() == "技术详情").click()
    assert not technical.isHidden()


def test_legacy_record_without_numeric_metadata_keeps_saved_conclusion(lifecycle, monkeypatch):
    context, window, request, result, standard = lifecycle
    legacy = result.model_copy(deep=True, update={
        "evaluation_id": "legacy-record", "numeric_profile_id": None,
        "numeric_contract_version": None, "calculator_version": None,
        "numeric_behavior_version": None,
    })
    legacy.results[0].actual_value = Decimal("5.0000004")
    legacy.results[0].grade = Grade.LEVEL_1
    context.evaluations.save(request, legacy, standard)
    select_record(window, legacy.evaluation_id)
    before = raw_state(context, legacy.evaluation_id)
    monkeypatch.setattr(EvaluationEngine, "evaluate", forbidden)
    window.view_selected_record()
    assert "当时保存的结果：1级" in detail_text(window)
    assert "5.0000004" in detail_text(window)
    assert "5.0000004 ≤ 5" not in detail_text(window)
    assert "判级采用原始计算值" not in detail_text(window)
    assert raw_state(context, legacy.evaluation_id) == before


def test_rule_drift_preserves_all_original_json_and_display(lifecycle, monkeypatch):
    context, window, request, result, standard = lifecycle
    original = normalized((request, result, standard))
    row_before = raw_state(context, result.evaluation_id)[0]
    install_r3(context, standard)
    select_record(window, result.evaluation_id)
    before = raw_state(context, result.evaluation_id)
    monkeypatch.setattr(EvaluationEngine, "evaluate", forbidden)
    window.view_selected_record()
    assert raw_state(context, result.evaluation_id) == before
    assert raw_state(context, result.evaluation_id)[0] == row_before
    assert normalized(context.application.get_evaluation(result.evaluation_id)) == original
    assert "测试新版" not in detail_text(window)
    assert "仅供测试的新版依据" not in detail_text(window)
    assert "1级 ≤ 5.00" in detail_text(window)
    assert "rule_revision: 2" in technical_text(window)
    summary = context.application.list_recent_evaluations()[0]
    assert summary.standard_title == standard.title
    assert summary.product_name == result.product_name


def test_history_source_uses_snapshot_hash_never_current(lifecycle, monkeypatch):
    context, window, request, result, standard = lifecycle
    # 小测试原文与真实测试 hash，不伪造正式 PDF。
    r2 = standard.model_copy(deep=True)
    old_pdf = context.paths.standards / "r2.pdf"
    old_pdf.write_bytes(b"test r2 PDF")
    r2.source_file = old_pdf.name
    r2.source_sha256 = hashlib.sha256(old_pdf.read_bytes()).hexdigest()
    for product in r2.products:
        for indicator in product.indicators:
            for reference in indicator.source_references:
                reference.source_file = r2.source_file
                reference.source_sha256 = r2.source_sha256
    context.standards.install(r2)
    record = context.application.evaluate(request)
    install_r3(context, r2)
    before = raw_state(context, record.evaluation_id)
    monkeypatch.setattr(context.application, "get_standard", forbidden)
    monkeypatch.setattr(context.application, "get_standard_for_evaluation", forbidden)
    monkeypatch.setattr(EvaluationEngine, "evaluate", forbidden)
    opened, warnings = [], []
    monkeypatch.setattr("uebench.ui.main_window.QDesktopServices.openUrl", lambda url: opened.append(Path(url.toLocalFile())) or True)
    monkeypatch.setattr(QMessageBox, "warning", lambda _p, _t, message: warnings.append(message))
    assert context.application.find_evaluation_standard_source(record.evaluation_id) == old_pdf.resolve()
    window.open_evaluation_standard_source(record.evaluation_id)
    assert opened == [old_pdf.resolve()]
    old_pdf.unlink()
    assert context.application.find_evaluation_standard_source(record.evaluation_id) is None
    window.open_evaluation_standard_source(record.evaluation_id)
    assert len(opened) == 1 and warnings == ["原评价标准原文当前不可用。"]
    assert context.application.find_evaluation_standard_source("missing") is None
    assert raw_state(context, record.evaluation_id) == before


def test_total_count_is_not_recent_ten_and_ids_are_hidden(lifecycle):
    context, window, request, result, standard = lifecycle
    for _ in range(11):
        context.application.evaluate(request)
    window.refresh_all()
    assert context.application.count_evaluations() == 12
    assert window.home_evaluation_count.text() == "12"
    assert window.home_recent.rowCount() == 10
    assert window.home_recent.columnCount() == 3
    assert window.record_table.columnCount() == 6
    for table in [window.home_recent, window.record_table]:
        for row in range(table.rowCount()):
            hidden_id = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            assert context.application.get_evaluation(hidden_id) is not None
            visible = " ".join(table.item(row, col).text() for col in range(table.columnCount()))
            assert hidden_id not in visible
            assert request.product_id not in visible
    select_record(window, result.evaluation_id)
    assert window._selected_record_id() == result.evaluation_id
    window.record_table.setCurrentCell(0, 4)
    assert window._selected_record_id() == window.record_table.item(0, 0).data(Qt.ItemDataRole.UserRole)


def test_selected_export_and_delete_keep_correct_hidden_id(lifecycle, monkeypatch, tmp_path):
    context, window, request, result, standard = lifecycle
    other = context.application.evaluate(request)
    select_record(window, result.evaluation_id)
    path = tmp_path / "原记录报告.xlsx"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(path), ""))
    window.export_selected_record()
    assert path.exists()
    event = next(event for event in context.audit.list_recent() if event.action == "WORKBOOK_EXPORT")
    assert event.entity_id == result.evaluation_id
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.delete_selected_record()
    assert context.application.get_evaluation(result.evaluation_id) is None
    assert context.application.get_evaluation(other.evaluation_id) is not None
    assert context.application.count_evaluations() == 1
    assert [s.evaluation_id for s in context.application.list_recent_evaluations()] == [other.evaluation_id]
    with context.database.engine.connect() as connection:
        assert connection.execute(text("SELECT deleted_at FROM evaluations WHERE evaluation_id=:id"), {"id": result.evaluation_id}).scalar_one() is not None
    assert any(e.action == "EVALUATION_DELETE" and e.entity_id == result.evaluation_id for e in context.audit.list_recent())


def test_future_preview_has_no_record_or_create_audit(lifecycle):
    context, window, request, result, standard = lifecycle
    future = standard.model_copy(deep=True, update={"id": "future-preview", "effective_date": date(2099, 1, 1)})
    context.standards.install(future)
    preview = request.model_copy(update={"standard_id": future.id, "selection_mode": StandardSelectionMode.FUTURE})
    before = context.application.count_evaluations()
    creates = [e for e in context.audit.list_recent() if e.action == "EVALUATION_CREATE"]
    window.calculate_evaluation(preview)
    assert window.last_result_id is None
    assert context.application.count_evaluations() == before
    assert [e for e in context.audit.list_recent() if e.action == "EVALUATION_CREATE"] == creates


# B. GB29446 Product Lifecycle

@pytest.mark.parametrize("field", ["electricity_consumption", "raw_coal_input"])
@pytest.mark.parametrize("value", [None, "0", "-1"])
def test_incomplete_characterization_is_saved_and_explicit(lifecycle, field, value):
    context, window, request, result, standard = lifecycle
    request = request.model_copy(deep=True)
    if value is None:
        request.inputs.pop(field)
    else:
        request.inputs[field] = InputValue(value=value, unit=request.inputs[field].unit)
    saved = context.application.evaluate(request)
    assert saved.results[0].grade is Grade.INCOMPLETE
    select_record(window, saved.evaluation_id)
    window.view_selected_record()
    assert "等级：不完整" in detail_text(window)
    assert "未形成正常等级或符合性结论" in detail_text(window)
    assert "等级：1级" not in detail_text(window)
    assert context.application.count_evaluations() == 2


@pytest.mark.parametrize("value", ["abc", "NaN", "Infinity"])
def test_ingress_valueerror_never_saves(lifecycle, value):
    context, window, request, result, standard = lifecycle
    request = request.model_copy(deep=True)
    request.inputs["electricity_consumption"] = InputValue(value=value, unit="kW·h")
    before = raw_state(context, result.evaluation_id)
    with pytest.raises(ValueError):
        context.application.evaluate(request)
    assert context.application.count_evaluations() == 1
    assert raw_state(context, result.evaluation_id) == before


@pytest.mark.parametrize("drift", [False, True])
def test_based_on_record_fills_only_then_creates_new_record(lifecycle, monkeypatch, drift):
    context, window, request, result, standard = lifecycle
    original = raw_state(context, result.evaluation_id)[0]
    if drift:
        install_r3(context, standard)
    select_record(window, result.evaluation_id)
    notices = []
    monkeypatch.setattr(QMessageBox, "information", lambda _p, title, message: notices.append((title, message)))
    before = context.application.count_evaluations()
    with monkeypatch.context() as guard:
        guard.setattr(EvaluationEngine, "evaluate", forbidden)
        window.recalculate_selected_record()
    assert context.application.count_evaluations() == before
    assert window.last_result_id is None
    assert window.navigation.currentRow() == 2
    assert window.gb29446_organization.text() == "宁夏测试企业"
    assert window.gb29446_custom_period.text() == "2026年6月"
    assert window.gb29446_notes.text() == "生命周期测试"
    assert window.gb29446_electricity.text() == "560"
    assert window.gb29446_raw_coal.text() == "100"
    assert window.gb29446_coal_type.currentData() == request.product_id
    assert window.gb29446_process.currentData() == "重介"
    assert window.gb29446_result_message.text() == "尚未计算"
    if drift:
        assert len(notices) == 1
        assert all(part in notices[0][1] for part in ["规则修订 2", "规则修订 3", "原记录不会被修改"])
    else:
        assert notices == []
    window.gb29446_electricity.setText("600")
    window.calculate_evaluation()
    assert window.last_result_id != result.evaluation_id
    saved_b = context.application.get_evaluation(window.last_result_id)
    assert saved_b[1].rule_revision == (3 if drift else 2)
    assert context.application.count_evaluations() == before + 1
    assert raw_state(context, result.evaluation_id)[0] == original
    assert any("已生成评价记录" in message for _title, message in notices)


def test_shared_based_on_record_entry_keeps_generic_standard(lifecycle, monkeypatch):
    context, window, _request_old, _result, _standard = lifecycle
    standard = make_standard()
    context.standards.install(standard)
    request = EvaluationRequest(evaluation_date=date.today(), standard_id=standard.id, product_id="product", input_mode="DIRECT", inputs={"actual": InputValue(value="15", unit="kgce/t")})
    result = context.application.evaluate(request)
    select_record(window, result.evaluation_id)
    before = raw_state(context, result.evaluation_id)
    monkeypatch.setattr(EvaluationEngine, "evaluate", forbidden)
    window.recalculate_selected_record()
    assert window.eval_product.currentData() == "product"
    assert window.eval_inputs.item(0, 2).text() == "15"
    assert raw_state(context, result.evaluation_id) == before
    assert window.last_result_id is None


def test_backup_restore_preserves_old_r2_after_r3(lifecycle, tmp_path):
    context, window, request, result, standard = lifecycle
    before = normalized(context.application.get_evaluation(result.evaluation_id))
    install_r3(context, standard)
    archive = context.application.create_backup(tmp_path / "snapshot.uebackup")
    context.application.delete_evaluation(result.evaluation_id)
    context.application.restore_backup(archive)
    assert normalized(context.application.get_evaluation(result.evaluation_id)) == before


def test_two_real_processes_restore_ui_then_create_b_without_drifting_a(tmp_path):
    env = os.environ.copy()
    env.update(UEBENCH_DATA_DIR=str(tmp_path / "跨进程中文数据"), PYTHONPATH=str(ROOT / "src") + os.pathsep + str(ROOT), QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8")
    common = "from tests.test_gb29446_record_lifecycle import *\ncontext=create_context()\n"
    process_a = common + '''
standard=standard_r2()
context.standards.install(standard)
request=request_r2(standard)
result=context.application.evaluate(request)
assert result.results[0].grade is Grade.LEVEL_2
payload={"id":result.evaluation_id,"models":normalized((request,result,standard)),"pid":os.getpid()}
context.database.dispose()
print("RS02:"+json.dumps(payload,ensure_ascii=False))
'''
    def launch(code):
        completed = subprocess.run([sys.executable, "-c", code], env=env, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert completed.returncode == 0, completed.stdout + completed.stderr
        return json.loads(next(line[5:] for line in completed.stdout.splitlines() if line.startswith("RS02:")))
    a = launch(process_a)
    env["RS02_RECORD_A"] = json.dumps(a, ensure_ascii=False)
    process_b = common + '''
a=json.loads(os.environ["RS02_RECORD_A"])
assert os.getpid()!=a["pid"]
assert any(s.evaluation_id==a["id"] for s in context.application.list_recent_evaluations())
loaded=context.application.get_evaluation(a["id"])
assert normalized(loaded)==a["models"]
app=QApplication.instance() or QApplication([])
window=MainWindow(context)
window.show()
window.navigation.setCurrentRow(3)
select_record(window,a["id"])
before=raw_state(context,a["id"])
original_engine=EvaluationEngine.evaluate
EvaluationEngine.evaluate=forbidden
window.view_selected_record()
app.processEvents()
assert all(s in detail_text(window) for s in ["宁夏测试企业","2026年6月","炼焦煤","重介","560","100","1.12","6.272","2级","第5.2条","第3.1条"])
assert raw_state(context,a["id"])==before
window.record_detail_dialog.close()
install_r3(context,loaded[2])
select_record(window,a["id"])
before=raw_state(context,a["id"])
window.view_selected_record()
assert "rule_revision: 2" in technical_text(window)
assert "测试新版" not in detail_text(window)
assert raw_state(context,a["id"])==before
window.record_detail_dialog.close()
notices=[]
QMessageBox.information=lambda _p,_t,m:notices.append(m)
window.recalculate_selected_record()
assert window.last_result_id is None
assert context.application.count_evaluations()==1
assert any("规则修订 2" in m and "规则修订 3" in m for m in notices)
assert normalized(context.application.get_evaluation(a["id"]))==a["models"]
EvaluationEngine.evaluate=original_engine
window.gb29446_electricity.setText("600")
window.calculate_evaluation()
assert window.last_result_id!=a["id"]
assert context.application.count_evaluations()==2
assert raw_state(context,a["id"])[0]==before[0]
assert normalized(context.application.get_evaluation(a["id"]))==a["models"]
assert context.application.get_evaluation(window.last_result_id)[1].rule_revision==3
window.close()
context.database.dispose()
print("RS02:"+json.dumps({"pid":os.getpid(),"restored":a["models"],"b":window.last_result_id}))
'''
    b = launch(process_b)
    assert b["pid"] != a["pid"]
    assert b["restored"] == a["models"]
    assert b["b"] != a["id"]
