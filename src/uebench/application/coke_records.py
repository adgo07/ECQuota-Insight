"""焦炭版本化记录适配。生产采用门禁独立于开发预览，历史读取不重算。"""
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from uuid import uuid4

from uebench.domain.gb21342 import (
    CokeAssessmentInput, CokeEnergyInput, ASSESSMENT_CALCULATOR_VERSION,
    ASSESSMENT_RULE_REVISION, ASSESSMENT_NUMERIC_BEHAVIOR_VERSION, SOURCE_SHA256,
)
from uebench.domain.models import EvaluationResult, IndicatorResult, CalculationStep, Grade, InputMode
from .gb21342 import preview_coke

PAYLOAD_VERSION = "gb21342-record-v1"
ADOPTION_MARKER = f"gb21342-calculator-adoption:{ASSESSMENT_CALCULATOR_VERSION}:{ASSESSMENT_RULE_REVISION}:{SOURCE_SHA256}"
STANDARD_ID = "gb-21342-2025"
PRODUCTS = {"top_charging": "top-charging-coke-oven", "stamp_charging": "stamp-charging-coke-oven"}
COMPLETE_GRADES = {Grade.LEVEL_1, Grade.LEVEL_2, Grade.LEVEL_3, Grade.NOT_QUALIFIED}


def json_data(value):
    def default(item):
        if isinstance(item, Decimal):
            return str(item)
        raise TypeError(type(item).__name__)
    return json.loads(json.dumps(value, default=default, ensure_ascii=False))


def snapshot_hash(snapshot):
    return hashlib.sha256(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False,
                                    sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def input_payload(assessment, *, flow_result=None):
    return {"version": PAYLOAD_VERSION, "assessment": json_data(asdict(assessment)),
            "flows": json_data(asdict(flow_result)) if flow_result else None}


def _reject_floats(value):
    if isinstance(value, float):
        raise ValueError("焦炭载荷不允许浮点数")
    if isinstance(value, dict):
        for item in value.values():
            _reject_floats(item)
    if isinstance(value, (list, tuple)):
        for item in value:
            _reject_floats(item)


def decode_input(payload):
    if not isinstance(payload, dict) or payload.get("version") != PAYLOAD_VERSION:
        raise ValueError("焦炭输入载荷版本不匹配")
    _reject_floats(payload)
    try:
        data = dict(payload["assessment"])
        data["energy"] = CokeEnergyInput(**data["energy"])
        return CokeAssessmentInput(**data)
    except (KeyError, TypeError) as exc:
        raise ValueError("焦炭输入载荷缺项或结构无效") from exc


def require_binding(request, snapshot, *, verify_flows=True):
    if (request.standard_id != STANDARD_ID or snapshot.id != STANDARD_ID
            or snapshot.rule_revision < 2 or ADOPTION_MARKER not in snapshot.corrections
            or snapshot.source_sha256 != SOURCE_SHA256
            or "gb-21342-2013" not in snapshot.supersedes
            or request.input_mode is not InputMode.DETAIL):
        raise ValueError("配套焦炭规则尚未采用新计算链，旧r1不能形成新记录")
    assessment = decode_input(request.coke_payload)
    if (request.product_id != PRODUCTS.get(assessment.oven_type)
            or not any(p.id == request.product_id for p in snapshot.products)):
        raise ValueError("焦炭输入炉型、产品与规则快照不一致")
    if request.inputs or request.energy_lines or request.production_lines or request.cement_lines or request.cement_shared_energy:
        raise ValueError("焦炭专属输入不能与其他输入通道同时生效")
    flows = request.coke_payload.get("flows")
    if flows is not None and (not isinstance(flows, dict) or not isinstance(flows.get("rows"), list)
            or any(not isinstance(row, dict) or not isinstance(row.get("flow"), dict) for row in flows["rows"])):
        raise ValueError("焦炭原始能流载荷结构无效")
    if flows is not None and verify_flows:
        from uebench.domain.coke_flows import aggregate_flows, CokeFlow, COMPONENTS
        rows = flows.get("rows", [])
        # 显式零分量保留在总量中；有明细的分量不允许以零声明覆盖。
        present = {r["flow"]["component"] for r in rows}
        zeros = [k for k in COMPONENTS if k not in present and flows.get("totals", {}).get(k) == "0"]
        normalized = aggregate_flows([CokeFlow(**r["flow"]) for r in rows], zero_components=zeros)
        if json_data(asdict(normalized)) != flows:
            raise ValueError("原始能流与折标快照不一致")
        if normalized.energy_input(assessment.energy.dry_coke_output_t, assessment.energy.external_services_status) != assessment.energy:
            raise ValueError("原始能流与五分量总量不一致")
    return assessment


def calculate_record(request, snapshot):
    assessment = require_binding(request, snapshot)
    result = preview_coke(assessment)
    product = next(p for p in snapshot.products if p.id == request.product_id)
    payload = {"version": PAYLOAD_VERSION, "assessment": json_data(asdict(result)),
               "input_sha256": hashlib.sha256(json.dumps(request.coke_payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
    indicator = IndicatorResult(indicator_id=request.product_id+".energy", indicator_name="焦炭单位产品能耗",
        actual_value=result.energy.evaluation_energy_kgce_per_t, unit="kgce/t", grade=result.grade,
        base_thresholds={v.grade.value:v.base_threshold for v in result.levels if v.base_threshold is not None},
        corrected_thresholds={v.grade.value:v.threshold for v in result.levels if v.threshold is not None},
        display_values={"actual_energy":result.energy.actual_energy_kgce_per_t,
                        **({"external_adjustment":result.energy.adjustment_kgce_per_t} if result.energy.adjustment_kgce_per_t is not None else {})},
        calculation_trace=[CalculationStep(sequence=s.sequence,label=s.label,operation="coke",expression=s.expression,value=s.value,unit=s.unit) for s in result.calculation_trace],
        warnings=list(result.warnings))
    return EvaluationResult(evaluation_id=str(uuid4()),evaluated_at=datetime.now(timezone.utc),
        standard_id=snapshot.id,standard_number=snapshot.number,standard_title=snapshot.title,
        standard_version=snapshot.version,standard_family_id=snapshot.standard_family_id,
        rule_revision=snapshot.rule_revision, product_id=product.id,product_name=product.name,
        numeric_contract_version=result.numeric_contract_version,numeric_profile_id=result.numeric_profile_id,
        calculator_version=result.calculator_version,numeric_behavior_version=result.numeric_behavior_version,
        rule_snapshot_sha256=snapshot_hash(snapshot),results=[indicator],coke_payload=payload,warnings=list(result.warnings))


def require_complete(request, result, snapshot):
    """只校验保存快照，不重算；最高级别已确定时不强求低级未知。"""
    require_binding(request, snapshot, verify_flows=False)
    payload = result.coke_payload or {}
    digest = hashlib.sha256(json.dumps(request.coke_payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if (payload.get("version") != PAYLOAD_VERSION or payload.get("input_sha256") != digest
            or result.rule_snapshot_sha256 != snapshot_hash(snapshot)
            or result.standard_id != request.standard_id or result.product_id != request.product_id
            or result.rule_revision != snapshot.rule_revision or result.standard_version != snapshot.version
            or result.standard_number != snapshot.number or result.standard_title != snapshot.title
            or result.calculator_version != ASSESSMENT_CALCULATOR_VERSION
            or result.numeric_behavior_version != ASSESSMENT_NUMERIC_BEHAVIOR_VERSION
            or result.numeric_contract_version != "v1" or result.numeric_profile_id != "ECQUOTA_DECIMAL_FULL_VALUE_V1"
            or len(result.results) != 1):
        raise ValueError("焦炭请求、结果、版本与规则快照不一致")
    r = payload.get("assessment", {})
    if not isinstance(r, dict) or not isinstance(r.get("energy"), dict):
        raise ValueError("焦炭结果载荷缺项或结构无效")
    item = result.results[0]
    if (item.indicator_id != request.product_id+".energy" or item.unit != "kgce/t"
            or item.compliance_result is not None or item.compliance_limit is not None
            or r.get("inputs") != request.coke_payload["assessment"]
            or r.get("energy",{}).get("inputs") != request.coke_payload["assessment"]["energy"]
            or r.get("energy",{}).get("numeric_contract_version") != result.numeric_contract_version
            or r.get("energy",{}).get("numeric_profile_id") != result.numeric_profile_id
            or r.get("calculator_version") != result.calculator_version
            or r.get("rule_revision") != ASSESSMENT_RULE_REVISION
            or r.get("source_sha256") != snapshot.source_sha256
            or r.get("numeric_behavior_version") != result.numeric_behavior_version
            or r.get("grade") != item.grade.value):
        raise ValueError("焦炭专属结果与保存结果不一致")
    if (item.grade not in COMPLETE_GRADES or item.actual_value is None
            or not item.actual_value.is_finite() or r.get("energy",{}).get("evaluation_energy_kgce_per_t") != str(item.actual_value)):
        raise ValueError("焦炭结果未完整判级，尚未生成记录")
    # 高等级先行，只要求到首个满足等级之前的比较均确定。
    selected = Grade.NOT_QUALIFIED
    levels = r.get("levels", [])
    if (not isinstance(levels, list) or any(not isinstance(v, dict) or not
            {"grade","threshold","base_threshold","matched","undetermined_reasons"} <= v.keys() for v in levels)
            or [v.get("grade") for v in levels] != ["LEVEL_1", "LEVEL_2", "LEVEL_3"]):
        raise ValueError("焦炭逐级快照缺项或顺序不一致")
    if ({v["grade"]:v["threshold"] for v in levels if v["threshold"] is not None}
            != {k:str(v) for k,v in item.corrected_thresholds.items()}
            or {v["grade"]:v["base_threshold"] for v in levels if v["base_threshold"] is not None}
            != {k:str(v) for k,v in item.base_thresholds.items()}):
        raise ValueError("焦炭限额与保存快照不一致")
    for level in levels:
        if level.get("matched") is None:
            raise ValueError("更高等级待确定，不能保存")
        if level["matched"] is True:
            selected = Grade(level["grade"])
            break
    if selected is not item.grade:
        raise ValueError("逐级比较与最终等级不一致")
    if not request.notes or not request.notes.strip():
        raise ValueError("请填写统计期")
