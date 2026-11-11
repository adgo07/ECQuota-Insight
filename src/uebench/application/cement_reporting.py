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
    from uebench.domain.cement_history import HistoricalCementStandard
    if isinstance(snapshot, HistoricalCementStandard):
        return _historical_report(request, result, snapshot)
    if snapshot.rule_revision == 2 and request.product_id == "cement-assessment":
        # PR38未发布r2多线只读；不改变规则身份，不调用Engine。
        pass
    elif not adopted(snapshot):
        raise ValueError("历史水泥规则未采用V1.2；保留原结果只读查看，不生成V1.2报告。")
    if result.rule_snapshot_sha256 != _saved_snapshot_hash(snapshot):
        raise ValueError("保存的水泥规则快照校验不一致，无法生成报告。")
    problems = completeness_problems(request, result, snapshot, historical_read=True)
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
        supplied_g = line.inputs.get("cement.clinker_percent")
        if supplied_g is not None and supplied_g.value not in (None, ""):
            from decimal import Decimal, localcontext, ROUND_HALF_EVEN
            with localcontext() as context:
                context.prec = 28
                context.rounding = ROUND_HALF_EVEN
                difference = Decimal(str(supplied_g.value)) - Decimal(75)
            fields.append(ReportField("clinker_percent_difference", "熟料配比与75%的百分点差（g−75）",
                                      _plain(difference), "百分点"))
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


def _historical_report(request, result, snapshot):
    from uebench.domain.cement_history import HistoricalCementRequest, original_hash
    if (not isinstance(request, HistoricalCementRequest)
            or result.rule_revision != 2 or result.product_id != request.product_id
            or result.standard_id != snapshot.id or request.standard_id != snapshot.id
            or result.standard_number != snapshot.number or result.standard_version != snapshot.version
            or request.product_id not in {p.id for p in snapshot.products}
            or result.rule_snapshot_sha256 != original_hash(snapshot)):
        raise ValueError("历史水泥保存快照身份或原始哈希不一致")
    expected = {"cement.comprehensive_energy", "clinker.comprehensive", "clinker.coal",
                "clinker.electricity", "cement-preparation.electricity"}
    mode = request.inputs.get("production_mode")
    mode = mode.value if mode else None
    applicable = {"integrated": expected, "partial_purchased": expected,
                  "clinker_only": {"clinker.comprehensive", "clinker.coal", "clinker.electricity"},
                  "grinding_station": {"cement-preparation.electricity"}}.get(mode)
    if (applicable is None or len(result.results) != 5
            or {item.indicator_id for item in result.results} != expected):
        raise ValueError("历史水泥模式或保存指标不完整，不能生成报告")
    for item in result.results:
        if item.indicator_id not in applicable:
            if item.grade is not Grade.NOT_APPLICABLE or item.actual_value is not None:
                raise ValueError("历史水泥不适用指标状态不一致")
        elif (item.grade in {Grade.INCOMPLETE, Grade.NOT_APPLICABLE}
                or item.actual_value is None or not item.actual_value.is_finite()
                or set(item.corrected_thresholds) != {"LEVEL_1", "LEVEL_2", "LEVEL_3"}
                or any(not value.is_finite() for value in item.corrected_thresholds.values())):
            raise ValueError("历史水泥保存结果不完整，不能生成报告")
    definitions = {field.key: field for product in snapshot.products for field in product.input_definitions}
    definitions.update({field.key: field for product in snapshot.products for indicator in product.indicators for field in indicator.input_definitions})
    fields = list(ReportField(key, definitions[key].label if key in definitions else "保存时输入", _plain(value.value), value.unit or "")
                   for key, value in request.inputs.items())
    if request.cement_details:
        for fuel in request.cement_details.fuel_lines:
            fields.extend((ReportField("fuel", fuel.name + "实物量", _plain(fuel.amount_kg), "kg"),
                           ReportField("heat", fuel.name + "低位发热量", _plain(fuel.low_heat_kj_per_kg), "kJ/kg")))
            if fuel.source_note:
                fields.append(ReportField("fuel_source", fuel.name + "来源说明", fuel.source_note))
    shared = tuple(f"{'熟料' if item.product == 'clinker' else '水泥'} / {definitions[item.target_input_key].label if item.target_input_key in definitions else '共用能耗'}：原总量{_plain(item.original_amount)} {item.unit}；目标生产线{item.target_line_id}；产量依据" + "、".join(f"{key}: {_plain(value)} t" for key, value in item.line_production_t.items()) + (f"；来源说明：{item.source_note}" if item.source_note else "")
                   for item in (request.cement_details.shared_allocations if request.cement_details else []))
    metrics = tuple(CementMetricView(item.indicator_name,
                    "—" if item.actual_value is None else _display_two_places(item.actual_value),
                    _plain(item.actual_value), item.unit, GRADE_LABELS[item.grade],
                    tuple(ReportField(key, GRADE_LABELS[Grade(key)], _plain(value), item.unit)
                          for key, value in item.corrected_thresholds.items()),
                    tuple(ReportField(key, GRADE_LABELS[Grade(key)] + "基准上限", _plain(value), item.unit)
                          for key, value in item.base_thresholds.items()))
                    for item in result.results)
    calculations = tuple(f"{step.label}：{_plain(step.value)} {step.unit or ''}"
                         for item in result.results for step in item.calculation_trace)
    return CementReportView(result.evaluation_id, "历史水泥评价报告（保存时结果）",
               (ReportField("standard", "标准", snapshot.number + " " + snapshot.title),
                ReportField("organization", "企业名称", request.organization_name or "未填写"),
                ReportField("date", "评价日期", request.evaluation_date.isoformat()),
                ReportField("evaluated", "评价时间", _local_datetime_text(result.evaluated_at)),
                ReportField("period", "统计期", _plain(request.inputs.get("evaluation_period").value) if request.inputs.get("evaluation_period") else "未记录")),
               (CementLineReport("保存时评价", {"integrated": "一体化生产", "partial_purchased": "部分外购熟料", "clinker_only": "仅熟料生产", "grinding_station": "水泥粉磨站"}.get(mode, "历史生产模式"), metrics, tuple(fields), calculations,
                   tuple(dict.fromkeys(f"{ref.standard_number} 第{ref.page}页 {ref.clause or ''} {ref.table or ''} {ref.note or ''}" for item in result.results for ref in item.source_references))),), shared,
               tuple(dict.fromkeys(["历史r2只读投影；保留保存值、等级及原始规则哈希，不重新计算或转换为r3。", *snapshot.corrections, *(warning for item in result.results for warning in item.warnings)])),
               snapshot.rule_revision, result.rule_snapshot_sha256)
