"""水泥UI/Word同源视图；只读三件保存快照，绝不调用Engine。"""
from .gb16780 import MODE_LABELS, completeness_problems
from .gb29446 import decode_period_notes
from .reporting import (
    CementLineReport, CementMetricView, CementReportView, ReportField,
    _display_two_places, _local_datetime_text, _plain, _saved_snapshot_hash,
)
from uebench.domain.gb16780 import DEDUCTIONS, NODE_LABELS, adopted
from uebench.domain.models import GRADE_LABELS, Grade

SHARED_LABELS = {"clinker_fuel": "共用熟料燃料", "clinker_electricity": "共用熟料用电",
                 "cement_auxiliary": "共用水泥辅助用电", "cement_preparation": "共用水泥制备工段用电"}
SCOPE = (
    "熟料：原燃料进入厂区至熟料产出的主要及辅助生产过程；不含基建、技改项目建设用能。",
    "水泥：原燃料进入厂区至水泥出厂的主要及辅助生产过程；制备工段自调配库底至水泥成品入库。",
    "四项扣除按同一期、同一窑系统边界分别统计，仅在原始总量仍包含时填写；余热及四项仅在源端扣一次。",
)


def build_cement_report_view(request, result, snapshot):
    if not adopted(snapshot):
        raise ValueError("历史水泥规则未采用V1.2；保留原结果只读查看，不生成V1.2报告。")
    if result.rule_snapshot_sha256 != _saved_snapshot_hash(snapshot):
        raise ValueError("保存的水泥规则快照校验不一致，无法生成报告。")
    problems = completeness_problems(request, result, snapshot)
    if problems:
        raise ValueError("水泥保存快照不完整，无法导出：" + "；".join(problems))
    product = next((p for p in snapshot.products if p.id == request.product_id), None)
    if product is None:
        raise ValueError("保存的水泥规则快照缺少对应产品，无法生成报告。")
    definitions = {d.key: d for d in product.input_definitions}
    shared_names = {item.shared_id: f"共用系统{index}" for index, item in enumerate(request.cement_shared_energy, 1)}
    lines = []
    for line in request.cement_lines:
        fields = []
        # 使用保存规则的词与单位；空白扣除也明确显示，不能补造成活动不存在。
        for key, definition in definitions.items():
            supplied = line.inputs.get(key)
            if key in DEDUCTIONS and line.production_mode == "purchased_clinker_grinding":
                continue
            if supplied is None or supplied.value in (None, ""):
                if key in DEDUCTIONS:
                    fields.append(ReportField(key, definition.label, "未填（无需软件额外扣除）", definition.unit or ""))
                continue
            fields.append(ReportField(key, definition.label, _plain(supplied.value), supplied.unit or definition.unit or ""))
        for fuel in line.fuels:
            fields += [ReportField("fuel_mass", f"{fuel.energy_name}实物量", _plain(fuel.mass_kg), "kg"),
                       ReportField("fuel_heat", f"{fuel.energy_name}低位发热量", _plain(fuel.low_calorific_value_kj_per_kg), "kJ/kg")]
        metrics, calculations, basis = [], [], []
        for item in result.results:
            if item.line_id != line.line_id:
                continue
            limits = tuple(ReportField(key, f"{GRADE_LABELS[Grade(key)]}有效上限", _plain(value), item.unit)
                           for key, value in item.corrected_thresholds.items())
            base = tuple(ReportField(key, f"{GRADE_LABELS[Grade(key)]}基准上限", _plain(value), item.unit)
                         for key, value in item.base_thresholds.items())
            metrics.append(CementMetricView(item.indicator_name,
                "—" if item.actual_value is None else _display_two_places(item.actual_value),
                _plain(item.actual_value), item.unit, GRADE_LABELS[item.grade], limits, base))
            for step in item.calculation_trace:
                if step.operation in {"cement_formula", "allocation"} or step.label == NODE_LABELS["K"]:
                    label, expression = step.label, step.expression
                    if step.operation == "allocation":
                        for shared_id, name in shared_names.items():
                            label = label.replace("：" + shared_id, "：" + name)
                    if label == NODE_LABELS["e_sh_before"]:
                        label = "扣除前熟料煤耗（已扣余热）"
                    expression = expression.replace("e_sh_before", "扣除前熟料煤耗（已扣余热）")
                    expression = expression.replace("H/(Q_BM", "Σ(m_i×Q_idw)/(Q_BM").replace("H/Q_BM", "Σ(m_i×Q_idw)/Q_BM")
                    formula = "" if step.label == NODE_LABELS["K"] else f"（{expression}）"
                    calculations.append(f"{label}{formula}：{_plain(step.value)} {step.unit or ''}".strip())
            if item.actual_value is not None:
                calculations.append(f"{item.indicator_name}完整比较值：{_plain(item.actual_value)} {item.unit}；保存等级：{GRADE_LABELS[item.grade]}")
            for ref in item.source_references:
                basis.append(f"{ref.standard_number} 第{ref.page}页 {ref.clause or ''} {ref.table or ''}".strip())
            basis.extend(item.warnings)
        lines.append(CementLineReport(line.line_name, MODE_LABELS[line.production_mode], tuple(metrics), tuple(fields),
                                      tuple(dict.fromkeys(calculations)), tuple(dict.fromkeys(basis))))
    names = {line.line_id: line.line_name for line in request.cement_lines}
    shared = []
    for item in request.cement_shared_energy:
        participants = "、".join(names[x] for x in item.line_ids)
        if item.fuels:
            amount = "；".join(f"{f.energy_name} {_plain(f.mass_kg)} kg，低位发热量 {_plain(f.low_calorific_value_kj_per_kg)} kJ/kg" for f in item.fuels)
        else:
            amount = f"{_plain(item.amount.value)} {item.amount.unit or 'kWh'}"
        shared.append(f"{SHARED_LABELS[item.target]}：{amount}；参与生产线：{participants}；按适用产品产量比例分摊。")
    code, custom, _ = decode_period_notes(request.notes)
    explanations = [*SCOPE,
        "各指标分别判级，不合成熟料总等级，不判企业建设属性的限定值/准入值符合性。",
        "等级采用保存时的完整计算值与有效阈值比较；两位小数仅供展示，未重新运行计算器。",
        "Issue001：部分外购式（8）使用本企业熟料综合煤耗e_sh，非E_sh；项目内部解释，尚无官方勘误。",
        "Issue003：水泥3级先海拔后配比94K+1.20(g−75)；项目内部约定，非标准明文唯一组合公式。",
        "2019(C.1)/(C.3)只作用户采纳的源端扣除技术参考，不是2021正式附录；2019(C.7)不用于式（8）。"]
    if any(line.inputs.get("site.altitude_m") for line in request.cement_lines):
        explanations.append("海拔严格大于1500m时修正适用四项3级，软件扩展口径不限企业建设属性；表3不作海拔修正。")
    return CementReportView(result.evaluation_id, "GB 16780—2021 水泥分线能耗等级评价报告", (
        ReportField("standard", "标准", f"{result.standard_number} {result.standard_title}"),
        ReportField("organization", "企业名称", request.organization_name or "未填写"),
        ReportField("period", "统计期", custom if code == "自定义" else code),
        ReportField("evaluation_date", "评价日期", request.evaluation_date.isoformat()),
        ReportField("evaluated_at", "评价时间", _local_datetime_text(result.evaluated_at)),
    ), tuple(lines), tuple(shared), tuple(explanations), snapshot.rule_revision, result.rule_snapshot_sha256)
