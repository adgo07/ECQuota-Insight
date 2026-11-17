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
