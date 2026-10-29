"""水泥页面与 Word 共用的保存快照投影；不调用计算器或当前标准库。"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from uebench.application.reporting import (ReportField, _local_datetime_text, _saved_snapshot_hash,
                                         _display_two_places, _display_implies_different_grade)
from uebench.application.gb29446 import decode_period_notes
from uebench.domain.models import EvaluationRequest, EvaluationResult, StandardDefinition, Grade, GRADE_LABELS, InputMode


SCOPE_NOTE = "本报告仅评价各单项能耗等级，不作限定值或准入值符合性判断。"
ALTITUDE_DISCLOSURE = "海拔修正采用软件扩展口径，不限企业建设属性；标准该条针对现有企业。"


@dataclass(frozen=True)
class CementIndicatorView:
    key: str
    label: str
    actual: str
    unit: str
    grade: str
    thresholds: tuple[ReportField, ...]
    complete: bool


@dataclass(frozen=True)
class CementReportView:
    record_id: str
    title: str
    information: tuple[ReportField, ...]
    indicators: tuple[CementIndicatorView, ...]
    inputs: tuple[ReportField, ...]
    calculations: tuple[ReportField, ...]
    disclosures: tuple[str, ...]
    basis: tuple[str, ...]
    scope_note: str
    complete: bool


def plain(value) -> str:
    if value is None or value == "":
        return "未填写"
    if isinstance(value, Decimal):
        text = format(value, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    return str(value)


def _disclosure_projection(request, warnings, display_notes):
    """仅投影保存事实；技术解释仍完整保留在既有计算依据中。"""
    def supplied_decimal(key):
        supplied = request.inputs.get(key)
        try:
            value = Decimal(str(supplied.value)) if supplied is not None else None
            return value if value is not None and value.is_finite() else None
        except (ArithmeticError, ValueError):
            return None

    altitude = supplied_decimal("altitude_m")
    ratio = supplied_decimal("clinker_ratio_percent")
    ordinary, technical = [], []
    for warning in warnings:
        if warning == ALTITUDE_DISCLOSURE:
            if altitude is not None and altitude > 1500:
                ordinary.append(ALTITUDE_DISCLOSURE)
        elif warning.startswith("ECQ-STD-GB16780-003"):
            technical.append(warning)
            if altitude is not None and altitude > 1500 and ratio is not None and ratio != 75:
                ordinary.append("3级限额先作海拔修正，再作熟料配比修正（软件解释）。")
        elif warning.startswith("ECQ-STD-GB16780-001"):
            technical.append(warning)
            ordinary.append("部分外购熟料按本企业熟料综合煤耗计算（软件解释）。")
        elif "2019" in warning and "扣除" in warning:
            technical.append(warning)
            from uebench.domain.gb16780 import DEDUCTION_KEYS
            if any((supplied_decimal(key) or Decimal(0)) > 0 for key in DEDUCTION_KEYS):
                ordinary.append("四项扣除按已批准的软件口径处理。")
        elif "ECQ-STD-" in warning:
            technical.append(warning)
        else:
            ordinary.append(warning)
    return (tuple(dict.fromkeys((*ordinary, *display_notes))), tuple(dict.fromkeys(technical)))


def build_cement_report_view(request: EvaluationRequest, result: EvaluationResult,
                             snapshot: StandardDefinition, *, formal: bool = True) -> CementReportView:
    from uebench.domain.gb16780 import STANDARD_ID, MODE_INDICATORS, PRODUCTION_MODES, DEDUCTION_KEYS

    if (request.standard_id, result.standard_id, snapshot.id) != (STANDARD_ID,) * 3:
        raise ValueError("水泥报告的标准身份不一致。")
    if request.product_id != result.product_id or request.input_mode is not InputMode.DETAIL:
        raise ValueError("水泥报告需要一致的明细计算记录。")
    if snapshot.rule_revision < 2 or not snapshot.cement_calculation_nodes:
        raise ValueError("该历史水泥快照尚未采用 V1.2 多指标报告，原结果未重新计算。")
    if (result.standard_number != snapshot.number or result.standard_version != snapshot.version
            or result.rule_revision != snapshot.rule_revision
            or result.rule_snapshot_sha256 != _saved_snapshot_hash(snapshot)):
        raise ValueError("评价结果与保存的规则快照身份不一致，无法生成报告。")
    mode_input = request.inputs.get("production_mode")
    mode = str(mode_input.value) if mode_input else ""
    if mode not in MODE_INDICATORS:
        raise ValueError("保存记录缺少有效生产模式。")
    product = next((item for item in snapshot.products if item.id == request.product_id), None)
    if product is None:
        raise ValueError("保存的规则快照缺少对应产品。")
    expected = set(MODE_INDICATORS[mode])
    ids = [item.indicator_id for item in result.results]
    if len(ids) != len(set(ids)) or not expected.issubset(ids):
        raise ValueError("保存的指标结果不完整或存在重复。")
    definitions = {item.id: item for item in product.indicators}
    rows = []
    display_notes = []
    complete = not result.warnings
    valid_grades = {Grade.LEVEL_1, Grade.LEVEL_2, Grade.LEVEL_3, Grade.NOT_QUALIFIED}
    for item in result.results:
        if item.indicator_id not in definitions or item.unit != definitions[item.indicator_id].unit:
            raise ValueError("保存指标或单位与规则快照不一致。")
        if item.indicator_id not in expected:
            if item.grade is not Grade.NOT_APPLICABLE:
                raise ValueError("保存结果包含生产模式不适用的有效指标。")
            continue
        if item.indicator_id not in definitions:
            raise ValueError("保存指标与规则快照不一致。")
        valid = (item.grade in valid_grades and item.actual_value is not None
                 and item.actual_value.is_finite()
                 and all(key in item.corrected_thresholds and item.corrected_thresholds[key].is_finite()
                         for key in ("LEVEL_1", "LEVEL_2", "LEVEL_3")))
        complete &= valid
        thresholds = tuple(ReportField(key, f"{GRADE_LABELS[Grade(key)]}上限", plain(value), item.unit)
                           for key, value in item.corrected_thresholds.items())
        display = _display_two_places(item.actual_value) if item.actual_value is not None and item.actual_value.is_finite() else "—"
        if valid and _display_implies_different_grade(display, item):
            display_notes.append(f"{definitions[item.indicator_id].name}按完整值 {plain(item.actual_value)} {item.unit} 判级；{display}仅用于显示。")
        rows.append(CementIndicatorView(item.indicator_id, definitions[item.indicator_id].name, display,
                                       item.unit, GRADE_LABELS[item.grade], thresholds, valid))
    if formal and not complete:
        raise ValueError("适用指标尚未完整判级，不能导出正式 Word 报告。")
    fields = {item.key: item for item in product.input_definitions}
    for indicator in product.indicators:
        fields.update({item.key: item for item in indicator.input_definitions})
    raw = []
    for key, definition in fields.items():
        if key in {"production_mode", "evaluation_period", "production_line_id"}:
            continue
        supplied = request.inputs.get(key)
        if supplied is not None or key in DEDUCTION_KEYS:
            raw.append(ReportField(key, definition.label, plain(supplied.value) if supplied else "未填写",
                                   supplied.unit or definition.unit or "" if supplied else definition.unit or ""))
    details = getattr(request, "cement_details", None)
    if details:
        for index, fuel in enumerate(details.fuel_lines, 1):
            label = fuel.name or f"燃料{index}"
            raw.extend((ReportField(f"fuel.{index}.amount", label + "消耗量", plain(fuel.amount_kg), "kg"),
                        ReportField(f"fuel.{index}.heat", label + "低位发热量", plain(fuel.low_heat_kj_per_kg), "kJ/kg")))
            if fuel.source_note:
                raw.append(ReportField(f"fuel.{index}.source", label + "来源", fuel.source_note))
        for index, allocation in enumerate(details.shared_allocations, 1):
            target = fields.get(allocation.target_input_key)
            raw.extend((ReportField(f"allocation.{index}.product", f"共用系统{index}产品", "熟料" if allocation.product == "clinker" else "水泥"),
                        ReportField(f"allocation.{index}.target", "分摊统计项", target.label if target else "保存的分摊统计项"),
                        ReportField(f"allocation.{index}.amount", "原始共用量", plain(allocation.original_amount), allocation.unit),
                        ReportField(f"allocation.{index}.line", "本线", allocation.target_line_id)))
            for line, production in allocation.line_production_t.items():
                raw.append(ReportField(f"allocation.{index}.production.{line}", f"参与线 {line} 同期产品产量", plain(production), "t"))
            if allocation.source_note:
                raw.append(ReportField(f"allocation.{index}.source", "分摊来源", allocation.source_note))
    calculations = []
    seen = set()
    nodes = {node.key: node for node in snapshot.cement_calculation_nodes}
    for item in result.results:
        if item.indicator_id not in expected:
            continue
        for key, value in item.display_values.items():
            if key in nodes and key not in seen:
                node = nodes[key]
                calculations.append(ReportField(key, node.label, plain(value), node.unit or ""))
                seen.add(key)
        for step in item.calculation_trace:
            if "共用系统" not in step.label and step.operation != "allocation_audit":
                continue
            token = (step.label, plain(step.value), step.unit)
            if token not in seen:
                calculations.append(ReportField(str(step.sequence), step.label, plain(step.value), step.unit or ""))
                seen.add(token)
    warnings = tuple(dict.fromkeys((*result.warnings, *(w for item in result.results for w in item.warnings))))
    disclosures, technical_warnings = _disclosure_projection(request, warnings, display_notes)
    source_basis = tuple(dict.fromkeys(
        f"{ref.standard_number} {ref.clause or ''} {ref.table or ''}".strip()
        for item in result.results if item.indicator_id in expected for ref in item.source_references))
    basis = (*source_basis, *technical_warnings)
    period = plain(request.inputs["evaluation_period"].value) if "evaluation_period" in request.inputs else "未记录"
    if (request.notes or "").startswith("核算周期："):
        code, custom, _ = decode_period_notes(request.notes)
        period = custom if code == "自定义" else code
    information = (
        ReportField("standard", "标准", f"{result.standard_number} {result.standard_title}"),
        ReportField("organization", "企业名称", request.organization_name or "未填写"),
        ReportField("line", "生产线", plain(request.inputs["production_line_id"].value) if "production_line_id" in request.inputs else request.project_name or "未填写"),
        ReportField("period", "统计期", period),
        ReportField("mode", "生产模式", PRODUCTION_MODES[mode]),
        ReportField("time", "评价时间", _local_datetime_text(result.evaluated_at)),
    )
    return CementReportView(result.evaluation_id, "GB 16780—2021 水泥单位产品能耗等级评价报告",
                            information, tuple(rows), tuple(raw), tuple(calculations), disclosures,
                            basis, SCOPE_NOTE, bool(complete))
