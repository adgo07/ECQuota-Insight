"""仅在夹具内注入未发布采用标记；不改变生产规则或正式范围。"""
from dataclasses import replace
from datetime import date
from pathlib import Path
import json
import pytest

from uebench.application.coke_records import ADOPTION_MARKER, input_payload, calculate_record, require_complete
from uebench.domain.models import StandardDefinition, EvaluationRequest, InputMode, Grade
from uebench.domain.gb21342 import CokeAssessmentInput, CokeEnergyInput

ROOT = Path(__file__).resolve().parents[1]


def sample():
    assessment = CokeAssessmentInput(CokeEnergyInput("111","0","0","0","0","1","included_or_not_external"),
        oven_type="top_charging",heating_fuel="coke_oven_gas",dry_volatile_pct="23",total_moisture_pct="10",
        oven_age_years="20",quenching_method="mixed",conventional_oven=True)
    request = EvaluationRequest(evaluation_date=date(2026,11,17),standard_id="gb-21342-2025",
        product_id="top-charging-coke-oven",input_mode=InputMode.DETAIL,inputs={},
        coke_payload=input_payload(assessment),organization_name="合成焦炭验收对象",notes="2026年10月（合成数据）")
    snapshot = StandardDefinition.model_validate_json((ROOT / "data/definitions/gb-21342-2025.json").read_text(encoding="utf-8"))
    snapshot.rule_revision = 2
    snapshot.corrections.append(ADOPTION_MARKER)
    snapshot.supersedes = ["gb-21342-2013"]
    return request,snapshot


def test_high_grade_allows_unknown_lower_and_old_rule_rejected():
    request,snapshot = sample()
    result = calculate_record(request,snapshot)
    require_complete(request,result,snapshot)
    assert result.results[0].grade is Grade.LEVEL_1
    assert "LEVEL_3" not in result.results[0].corrected_thresholds
    snapshot.rule_revision=1
    with pytest.raises(ValueError,match="旧r1"):
        calculate_record(request,snapshot)


def test_stale_identity_and_incomplete_rejected():
    request,snapshot = sample()
    result = calculate_record(request,snapshot)
    request.coke_payload["assessment"]["energy"]["raw_coal_energy_kgce"] = "113"
    with pytest.raises(ValueError,match="不一致"):
        require_complete(request,result,snapshot)
    result = calculate_record(request,snapshot)
    with pytest.raises(ValueError,match="未完整判级"):
        require_complete(request,result,snapshot)
    request.coke_payload["assessment"]["energy"]["raw_coal_energy_kgce"] = True
    with pytest.raises(ValueError):
        calculate_record(request,snapshot)


@pytest.mark.parametrize("field,value",[("calculator_version","legacy-r1"),("numeric_behavior_version","unknown"),
                                      ("numeric_profile_id","other"),("standard_number","GB0000")])
def test_record_version_mismatch_rejected(field,value):
    request,snapshot = sample()
    result = calculate_record(request,snapshot)
    setattr(result,field,value)
    with pytest.raises(ValueError,match="不一致"):
        require_complete(request,result,snapshot)


@pytest.mark.parametrize("payload",[{}, {"version":"gb21342-record-v1"},
                                    {"version":"gb21342-record-v1","assessment":True}])
def test_malformed_payload_is_readable_error(payload):
    request,snapshot = sample()
    request.coke_payload=payload
    with pytest.raises(ValueError,match="载荷"):
        calculate_record(request,snapshot)


def test_sql_readback_report_no_recalculate_and_rollback(tmp_path, monkeypatch):
    from uebench.bootstrap import create_context
    from uebench.application import evaluation_support
    from uebench.application import coke_records
    from uebench.application.reporting import build_report_view
    from uebench.infrastructure.database import EvaluationRow
    request,snapshot = sample()
    context = create_context(tmp_path / "isolated")
    context.standards.install(snapshot)
    # 生产范围必须先拒绝，尚无保存。
    with pytest.raises(ValueError,match="正式评价记录"):
        context.application.evaluate(request)
    assert context.evaluations.count() == 0
    monkeypatch.setattr(evaluation_support,"SUPPORTED_EVALUATION_STANDARD_IDS",frozenset({"gb-29446-2019","gb-21342-2025"}))
    result = context.application.evaluate(request)
    assert context.evaluations.count() == 1
    with context.database.session() as session:
        row = session.get(EvaluationRow,result.evaluation_id)
        original = (row.request_json,row.result_json,row.rule_snapshot_json)
    def fail(*args,**kwargs):
        raise AssertionError("历史不得重算")
    monkeypatch.setattr(coke_records,"preview_coke",fail)
    loaded = context.application.get_evaluation(result.evaluation_id)
    view = build_report_view(*loaded)
    assert view.lines[0].metrics[0].grade == "1级"
    assert view.lines[0].metrics[0].thresholds[2].value == "待确定"
    assert "001" not in str(view) and "最高级别" not in str(view)
    with context.database.session() as session:
        row = session.get(EvaluationRow,result.evaluation_id)
        assert original == (row.request_json,row.result_json,row.rule_snapshot_json)
    context.database.dispose()


def test_audit_failure_rolls_back_record(tmp_path, monkeypatch):
    from uebench.bootstrap import create_context
    request,snapshot = sample()
    result = calculate_record(request,snapshot)
    context = create_context(tmp_path / "isolated")
    def fail(*args,**kwargs):
        raise RuntimeError("合成审计写失败")
    monkeypatch.setattr(context.audit,"append",fail)
    with pytest.raises(RuntimeError,match="审计"):
        context.evaluations.save(request,result,snapshot)
    assert context.evaluations.count() == 0
    context.database.dispose()


def flow_sample():
    from uebench.domain.coke_flows import CokeFlow, aggregate_flows, COMPONENTS
    from uebench.application.coke_records import decode_input
    request, snapshot = sample()
    flows = aggregate_flows([CokeFlow("raw-1", COMPONENTS[1], "electricity", "1000", "kWh")], zero_components=[k for k in COMPONENTS if k != COMPONENTS[1]])
    assessment = replace(decode_input(request.coke_payload), energy=flows.energy_input("2", "included_or_not_external"))
    request.coke_payload = input_payload(assessment, flow_result=flows)
    return request, snapshot


def test_flows_record_saved_readback_and_report(tmp_path, monkeypatch):
    from uebench.bootstrap import create_context
    from uebench.application import evaluation_support, coke_records
    request, snapshot = flow_sample()
    context = create_context(tmp_path / "flows", enforce_standard_library_readiness=False)
    context.standards.install(snapshot)
    monkeypatch.setattr(evaluation_support, "SUPPORTED_EVALUATION_STANDARD_IDS", frozenset({snapshot.id}))
    try:
        result = context.application.evaluate(request)
        monkeypatch.setattr(coke_records, "preview_coke", lambda *_: pytest.fail("历史不得重算"))
        loaded = context.application.get_evaluation(result.evaluation_id)
        assert loaded[0].coke_payload == request.coke_payload
        view = context.application.get_report_view(result.evaluation_id)
        assert "表A.2" in str(view) and "0.1229" in str(view)
        target = tmp_path / "flows.docx"
        context.application.export_word_report(result.evaluation_id, target)
        assert target.is_file()
        assert context.application.query_evaluations().items[0].period == request.notes
    finally:
        context.database.dispose()


@pytest.mark.parametrize("change", ["quantity", "coefficient", "source", "total", "assessment", "version"])
def test_flows_record_tamper_rejected(change):
    request, snapshot = flow_sample()
    flows = request.coke_payload["flows"]
    if change == "quantity":
        flows["rows"][0]["flow"]["quantity"] = "112"
    elif change == "coefficient":
        flows["rows"][0]["coefficient"] = "2"
    elif change == "source":
        flows["rows"][0]["coefficient_source"] = "伪造来源"
    elif change == "total":
        flows["totals"]["raw_coal_energy_kgce"] = "112"
    elif change == "version":
        flows["version"] = "unknown"
    else:
        request.coke_payload["assessment"]["energy"]["raw_coal_energy_kgce"] = "112"
    with pytest.raises(ValueError, match="不一致"):
        calculate_record(request, snapshot)


def test_saved_v1_survives_current_version_upgrade_and_write_stays_strict(tmp_path, monkeypatch):
    from uebench.bootstrap import create_context
    from uebench.application import coke_records
    request, snapshot = sample()
    result = calculate_record(request, snapshot)
    context = create_context(tmp_path / "historical", enforce_standard_library_readiness=False)
    context.evaluations.save(request, result, snapshot)
    context.database.dispose()
    monkeypatch.setattr(coke_records, "PAYLOAD_VERSION", "future-record-v2")
    monkeypatch.setattr(coke_records, "ASSESSMENT_CALCULATOR_VERSION", "future-v2")
    monkeypatch.setattr(coke_records, "ASSESSMENT_RULE_REVISION", "future-rule-v2")
    monkeypatch.setattr(coke_records, "ASSESSMENT_NUMERIC_BEHAVIOR_VERSION", "future-numeric-v2")
    monkeypatch.setattr(coke_records, "ADOPTION_MARKER", "gb21342-calculator-adoption:future-v2:future-rule-v2:"+snapshot.source_sha256)
    monkeypatch.setattr(coke_records, "preview_coke", lambda *_: pytest.fail("历史不得重算"))
    context = create_context(tmp_path / "historical", enforce_standard_library_readiness=False)
    try:
        view = context.application.get_report_view(result.evaluation_id)
        assert view.lines[0].metrics[0].grade == "1级"
        with pytest.raises(ValueError):
            coke_records.calculate_record(request, snapshot)
        with pytest.raises(ValueError):
            coke_records.require_complete(request, result, snapshot)
    finally:
        context.database.dispose()


@pytest.mark.parametrize("change", ["calculator", "rule", "numeric", "source", "payload", "marker"])
def test_historical_unknown_or_mismatched_identity_rejected(change):
    request, snapshot = sample()
    result = calculate_record(request, snapshot)
    if change == "calculator":
        result.calculator_version = "future-v9"
        result.coke_payload["assessment"]["calculator_version"] = "future-v9"
    elif change == "rule":
        result.coke_payload["assessment"]["rule_revision"] = "unknown-rule"
    elif change == "numeric":
        result.numeric_behavior_version = "unknown-numeric"
        result.coke_payload["assessment"]["numeric_behavior_version"] = "unknown-numeric"
    elif change == "source":
        snapshot.source_sha256 = "f"*64
    elif change == "payload":
        result.coke_payload["version"] = "unknown-payload"
    else:
        snapshot.corrections = ["gb21342-calculator-adoption:unknown:unknown:"+snapshot.source_sha256]
    with pytest.raises(ValueError):
        require_complete(request, result, snapshot, historical=True)


def test_desktop_coke_record_two_tabs_and_real_word_export(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
    from uebench.bootstrap import create_context
    from uebench.ui.main_window import MainWindow
    from uebench.application import coke_records
    from docx import Document
    app = QApplication.instance() or QApplication([])
    request, snapshot = flow_sample()
    result = calculate_record(request, snapshot)
    context = create_context(tmp_path / "desktop", enforce_standard_library_readiness=False)
    context.evaluations.save(request, result, snapshot)
    monkeypatch.setattr(coke_records, "preview_coke", lambda *_: pytest.fail("历史不得重算"))
    for name in ("warning", "critical", "information"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: QMessageBox.Ok)
    target = tmp_path / "焦炭.docx"
    filenames = []
    def dialog(*args, **kwargs):
        filenames.append(args[2])
        return str(target), "Word"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", dialog)
    win = MainWindow(context)
    try:
        win.view_record(result.evaluation_id)
        detail = win.record_detail_page
        assert detail.export_button.isEnabled()
        assert detail.tabs.count() == 2
        assert "1级" in detail.result_content.toPlainText()
        text = detail.input_content.toPlainText()
        assert "原料煤携带有效能量" in text and "统计期" in detail.result_content.toPlainText()
        assert "表A.2" in text
        detail.export_button.click()
        assert filenames == ["焦炭能耗对标报告.docx"]
        document = Document(target)
        content = "\n".join(p.text for p in document.paragraphs) + str([[c.text for c in row.cells] for t in document.tables for row in t.rows])
        assert "焦炭能耗对标报告" in content and "原料煤携带有效能量" in content
    finally:
        win.close()
        context.database.dispose()
