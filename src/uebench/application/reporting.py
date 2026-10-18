"""从保存的三件快照生成 UI 与 Word 共用的选煤业务视图。

这里不运行计算器，也不读取当前标准。术语来源为 2026-10-18 批准映射；
老规则快照只作兼容展示，不能据此声称历史评价采用了新映射。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
import json
import re

from uebench.application.gb29446 import decode_period_notes
from uebench.domain.models import (
    GRADE_LABELS, EvaluationRequest, EvaluationResult, Grade, IndicatorResult,
    InputMode, StandardDefinition,
)

MAPPING_ID = "GB29446-2019/标准映射表_2026-10-18_已批准.md"
MAPPING_SHA256 = "d8019b19358caf52956a6b2ebde2211f5474cbd76e44bf71cfe9732c9c76a6ba"
PRESENTATION_VERSION = "gb29446-presentation-2026-10-18"
ADOPTION_MARKER = f"软件映射采用（非标准勘误）：{MAPPING_ID}; sha256={MAPPING_SHA256}"
PERIOD_LABEL = "统计期"  # 批准映射 §3.2、§8.2；旧 notes 编码仍称“核算周期”

# 映射 §7.1–7.3；“机修”和“等”均为原文范围，不将列举误作封闭清单。
STATISTICS_SCOPE = (
    "统计起点：原煤输送至选煤厂；统计终点：选煤产品运输出选煤厂。"
    "统计范围包括选煤、机修、照明、化验室等所消耗的电能，"
    "以及与上述有关的线路和变压器的电损失。"
)


@dataclass(frozen=True)
class ReportField:
    key: str
    label: str
    value: str
    unit: str = ""
    mapping_section: str = ""


@dataclass(frozen=True)
class ReportView:
    record_id: str
    title: str
    headings: tuple[str, str, str, str]
    standard: ReportField
    evaluation_date: ReportField
    evaluated_at: ReportField
    organization: ReportField | None
    period: ReportField | None
    enterprise_type: ReportField
    process_type: ReportField
    electricity: ReportField | None
    raw_coal: ReportField | None
    factor: ReportField | None
    actual: ReportField
    actual_full_value: str
    grade: ReportField
    thresholds: tuple[ReportField, ...]
    explanation: tuple[str, ...]
    scope: ReportField
    basis: tuple[str, ...]
    warnings: tuple[str, ...]
    mapping_id: str
    mapping_sha256: str
    mapping_adoption: str
    presentation_version: str
    input_mode: InputMode
    saved_rule_revision: int
    saved_rule_snapshot_sha256: str


def _plain(value: Decimal | str | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, Decimal):
        lexical = format(value, "f")
        return lexical.rstrip("0").rstrip(".") if "." in lexical else lexical
    return str(value)


def _finite(value: Decimal | None) -> bool:
    return value is not None and value.is_finite()


def _saved_snapshot_hash(snapshot: StandardDefinition) -> str:
    payload = json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _local_datetime_text(value) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _field_definition(product, key: str):
    for definition in product.input_definitions:
        if definition.key == key:
            return definition
    for indicator in product.indicators:
        for definition in indicator.input_definitions:
            if definition.key == key:
                return definition
    return None


def _business_label(snapshot: StandardDefinition, product, key: str, fallback: str, adopted: bool) -> str:
    """新规则从机器定义读词；旧快照使用批准词作兼容展示。"""
    if adopted:
        if key == "coal_type":
            source = next((s for s in snapshot.selection_schema if s.key == key), None)
            return source.label if source else fallback
        if key == "process_factor":
            source = next(
                (d for i in product.indicators for d in i.display_calculations if d.key == key), None
            )
            return source.label if source else fallback
        if key == "actual":
            return product.indicators[0].name + " e_d"
        source = _field_definition(product, key)
        return source.label if source else fallback
    return fallback


def gb29446_business_labels(snapshot: StandardDefinition, product) -> dict[str, str]:
    adopted = ADOPTION_MARKER in snapshot.corrections
    return {
        "coal_type": _business_label(snapshot, product, "coal_type", "选煤企业类型", adopted),
        "washing_process": _business_label(snapshot, product, "washing_process", "选煤工艺类型", adopted),
        "electricity_consumption": _business_label(snapshot, product, "electricity_consumption", "统计期内选煤电力消耗量 E_d", adopted),
        "raw_coal_input": _business_label(snapshot, product, "raw_coal_input", "统计期内入选原煤量 m", adopted),
        "process_factor": _business_label(snapshot, product, "process_factor", "选煤工艺类型折算系数 k", adopted),
        "actual": _business_label(snapshot, product, "actual", "选煤电力单耗 e_d", adopted),
    }


def render_gb29446_warning(warning: str, snapshot: StandardDefinition, product) -> str:
    """仅替换独立的机器输入键；原警告、标准引用和保存快照均不变。"""
    labels = gb29446_business_labels(snapshot, product)
    replacements = {key: label for key, label in labels.items() if key != "actual"}
    for indicator in product.indicators:
        replacements[indicator.direct_input_key] = labels["actual"]
    for key, label in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        warning = re.sub(rf"(?<![A-Za-z0-9_.-]){re.escape(key)}(?![A-Za-z0-9_.-])", label, warning)
    return warning


def _saved_input(request: EvaluationRequest, product, key: str, *, label: str, section: str) -> ReportField | None:
    supplied = request.inputs.get(key)
    if supplied is None:
        return None
    definition = _field_definition(product, key)
    if definition is None:
        raise ValueError(f"规则快照缺少输入项 {key}，无法导出报告。")
    try:
        numeric = Decimal(str(supplied.value))
    except Exception as exc:
        raise ValueError(f"保存的输入项 {label} 不是有效数值，无法导出报告。") from exc
    if not numeric.is_finite() or numeric <= 0:
        raise ValueError(f"保存的输入项 {label} 不是有效正数，无法导出报告。")
    if supplied.unit not in {None, definition.unit}:
        raise ValueError(f"保存的输入项 {label} 单位与规则快照不一致，无法导出报告。")
    return ReportField(key, label, _plain(supplied.value), supplied.unit or definition.unit or "", section)


def _display_two_places(value: Decimal) -> str:
    """显式展示修约；只用于文字，绝不回流到等级比较。"""
    with localcontext() as context:
        context.prec = max(28, len(value.as_tuple().digits) + 2, value.adjusted() + 3)
        context.rounding = ROUND_HALF_EVEN
        return format(value.quantize(Decimal("0.01")), ".2f")


def _display_implies_different_grade(display: str, item: IndicatorResult) -> bool:
    shown = Decimal(display)
    for key, grade in (("LEVEL_1", Grade.LEVEL_1), ("LEVEL_2", Grade.LEVEL_2), ("LEVEL_3", Grade.LEVEL_3)):
        if shown <= item.corrected_thresholds[key]:
            return grade is not item.grade
    return item.grade is not Grade.NOT_QUALIFIED


def _basis(item: IndicatorResult) -> tuple[str, ...]:
    lines: list[str] = []
    for ref in item.source_references:
        clause = (ref.clause or "").split(" ", 1)[0]
        if clause in {"3.1", "3.2"} and ref.table:
            lines.append(f"等级依据：第{clause}条，{ref.table}")
        elif clause == "5.2" and ref.table:
            lines.append(f"计算依据：第{clause}条，{ref.table}")
        elif clause == "附录A" and ref.table:
            lines.append(f"折算系数依据：{clause}{ref.table}")
    return tuple(dict.fromkeys(lines))


def build_report_view(
    request: EvaluationRequest, result: EvaluationResult, snapshot: StandardDefinition,
) -> ReportView:
    """仅投影已保存事实；未形成有效等级的记录拒绝正式报告。"""
    if (request.standard_id, result.standard_id, snapshot.id) != ("gb-29446-2019",) * 3:
        raise ValueError("此报告仅支持 GB 29446—2019 选煤评价记录。")
    if request.product_id != result.product_id:
        raise ValueError("评价记录的产品身份不一致，无法导出报告。")
    if (
        result.standard_number != snapshot.number
        or result.standard_version != snapshot.version
        or result.rule_revision != snapshot.rule_revision
        or result.rule_snapshot_sha256 != _saved_snapshot_hash(snapshot)
    ):
        raise ValueError("评价结果与保存的规则快照身份不一致，无法导出报告。")
    product = next((p for p in snapshot.products if p.id == request.product_id), None)
    if product is None or len(result.results) != 1:
        raise ValueError("评价记录的规则快照或指标结果不完整，无法导出报告。")
    item = result.results[0]
    if item.indicator_id not in {indicator.id for indicator in product.indicators}:
        raise ValueError("评价指标与产品规则快照不一致，无法导出报告。")
    if not _finite(item.actual_value) or item.grade not in {
        Grade.LEVEL_1, Grade.LEVEL_2, Grade.LEVEL_3, Grade.NOT_QUALIFIED,
    }:
        raise ValueError("该记录未形成有效电耗等级，无法导出正式报告。")
    if not all(_finite(item.corrected_thresholds.get(key)) for key in ("LEVEL_1", "LEVEL_2", "LEVEL_3")):
        raise ValueError("评价记录缺少有效的等级限值，无法导出正式报告。")
    enterprise_value = product.selection_values.get("coal_type")
    if not enterprise_value:
        raise ValueError("规则快照缺少选煤企业类型，无法导出报告。")
    process = request.inputs.get("washing_process")
    if process is None:
        raise ValueError("评价记录缺少选煤工艺类型，无法导出报告。")

    # r2 的标签及映射采用状态可能不同；兼容投影使用批准词，但不修改历史快照。
    # 这是本仓兼容采用记录，不是中央 Contract 或国家标准勘误。
    adopted = ADOPTION_MARKER in snapshot.corrections
    mapping_adoption = (
        "本次评价规则已记录采用 2026-10-18 批准映射。"
        if adopted else "原评价规则的映射采用状态未记录；本报告使用 2026-10-18 批准映射兼容展示词，原结果未重新计算。"
    )
    labels = gb29446_business_labels(snapshot, product)
    electricity = _saved_input(
        request, product, "electricity_consumption",
        label=labels["electricity_consumption"], section="§3.2、§8.1",
    )
    raw_coal = _saved_input(
        request, product, "raw_coal_input",
        label=labels["raw_coal_input"], section="§3.2、§8.1",
    )
    factor_value = item.display_values.get("process_factor")
    if factor_value is not None and not _finite(factor_value):
        raise ValueError("评价记录的折算系数无效，无法导出报告。")
    factor = ReportField(
        "process_factor", labels["process_factor"], _plain(factor_value) if factor_value is not None else "未保存", "", "§3.2、§9"
    )
    actual_full = _plain(item.actual_value)
    actual_display = _display_two_places(item.actual_value)
    grade_label = GRADE_LABELS[item.grade]
    thresholds = tuple(
        ReportField(key, f"{GRADE_LABELS[grade]}上限", _plain(item.corrected_thresholds[key]), item.unit, "§5、§10")
        for key, grade in (("LEVEL_1", Grade.LEVEL_1), ("LEVEL_2", Grade.LEVEL_2), ("LEVEL_3", Grade.LEVEL_3))
        if key in item.corrected_thresholds
    )
    explanation: list[str] = [
        f"{labels['washing_process']}：{_plain(process.value)}，{factor.label} = {factor.value}"
    ]
    if request.input_mode is InputMode.DETAIL:
        if electricity is None or raw_coal is None or factor_value is None:
            raise ValueError("明细计算记录缺少 E_d、m 或 k，无法导出报告。")
        explanation.append(
            f"计算：e_d = E_d × k ÷ m = {electricity.value} × {factor.value} ÷ {raw_coal.value} = {actual_full} {item.unit}"
        )
    elif request.input_mode is InputMode.DIRECT:
        explanation.append(f"直接录入选煤电力单耗 {actual_full} {item.unit}；本报告不补造 E_d、m 公式代入。")
    else:
        raise ValueError("评价记录输入方式无效，无法导出报告。")
    basis = _basis(item)
    explanation.append(f"判定：{grade_label}" + (f"（{'；'.join(basis)}）" if basis else "。"))
    if result.numeric_profile_id == "ECQUOTA_DECIMAL_FULL_VALUE_V1":
        if _display_implies_different_grade(actual_display, item):
            explanation.append(f"判级使用完整计算值 {actual_full} {item.unit}；{actual_display} {item.unit} 仅用于显示。")
    else:
        explanation.append("历史记录的数值规则以原保存结果为准；本报告不重新判级。")

    period_code, custom_period, _note = decode_period_notes(request.notes)
    period_value = (custom_period if period_code == "自定义" else period_code) if (request.notes or "").startswith("核算周期：") else "未记录"
    period = ReportField("period", PERIOD_LABEL, period_value or "未记录", "", "§3.2、§8.2")
    return ReportView(
        record_id=result.evaluation_id,
        title="GB 29446—2019 选煤电力单耗等级评价报告",
        headings=("评价信息", "评价结果", "计算与判定说明", "统计范围与依据"),
        standard=ReportField("standard", "标准", f"{result.standard_number} {result.standard_title}", "", "§1"),
        evaluation_date=ReportField("evaluation_date", "评价日期", request.evaluation_date.isoformat()),
        evaluated_at=ReportField("evaluated_at", "评价时间", _local_datetime_text(result.evaluated_at)),
        organization=ReportField("organization", "企业名称", request.organization_name or "未填写", "", "§12"),
        period=period,
        enterprise_type=ReportField("coal_type", labels["coal_type"], enterprise_value, "", "§3.2、§4"),
        process_type=ReportField("washing_process", labels["washing_process"], _plain(process.value), "", "§3.2、§9"),
        electricity=electricity,
        raw_coal=raw_coal,
        factor=factor,
        actual=ReportField("actual", labels["actual"], actual_display, item.unit, "§3.1、§8"),
        actual_full_value=actual_full,
        grade=ReportField("grade", "等级或评价结果", grade_label, "", "§5.3、§12"),
        thresholds=thresholds,
        explanation=tuple(explanation),
        scope=ReportField("scope", "统计范围", STATISTICS_SCOPE, "", "§7.1–7.3"),
        basis=basis,
        warnings=tuple(dict.fromkeys(
            render_gb29446_warning(warning, snapshot, product)
            for warning in (*result.warnings, *item.warnings)
        )),
        mapping_id=MAPPING_ID,
        mapping_sha256=MAPPING_SHA256,
        mapping_adoption=mapping_adoption,
        presentation_version=PRESENTATION_VERSION,
        input_mode=request.input_mode,
        saved_rule_revision=snapshot.rule_revision,
        saved_rule_snapshot_sha256=result.rule_snapshot_sha256,
    )
