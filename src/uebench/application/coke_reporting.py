"""焦炭保存快照投影；复用现有多指标报告载体和两页签，不运行计算器。"""
from dataclasses import dataclass
from .coke_records import require_complete, PRODUCTS
from .reporting import ReportField, CementReportView, CementLineReport, CementMetricView, _local_datetime_text
from uebench.domain.models import GRADE_LABELS, Grade
from uebench.domain.gb21342 import LABELS


@dataclass(frozen=True)
class CokeReportView(CementReportView):
    """焦炭保存快照的报告视图。"""


def build_coke_report_view(request, result, snapshot):
    require_complete(request, result, snapshot, historical=True)
    saved = result.coke_payload["assessment"]
    values = request.coke_payload["assessment"]
    energy = saved["energy"]
    def field(label, value, unit=""):
        return ReportField("", label, "待确定" if value is None else str(value), unit)
    information = (
        field("标准", f"{snapshot.number} {snapshot.title}"),
        field("对象名称", request.organization_name or "未填写"),
        field("统计期", request.notes or "未填写"),
        field("评价时间", _local_datetime_text(result.evaluated_at)),
    )
    inputs = [field(label, values["energy"][key], "t" if key == "dry_coke_output_t" else "kgce") for key,label in LABELS.items()]
    choices = {"heating_fuel": ("加热燃料", {"coke_oven_gas":"焦炉煤气","mixed_gas":"混合煤气","other":"其他","unknown":"待确定"}),
               "quenching_method": ("熄焦方式", {"dry":"干熄焦","wet":"湿熄焦","mixed":"干湿并存","unknown":"待确定"})}
    for key,(label, options) in choices.items():
        inputs.append(field(label, options.get(values.get(key), "待确定")))
    for key,label,unit in (("dry_volatile_pct","干基挥发分","%"),("total_moisture_pct","全水分","%"),
                           ("oven_age_years","炉龄","年")):
        inputs.append(field(label, values.get(key), unit))
    fuel = values.get("heating_fuel")
    ratio = values.get("mixed_gas_ratio") if fuel == "mixed_gas" else None
    if fuel in {"coke_oven_gas", "other"}:
        ratio = "不适用"
    inputs.append(field("混合煤气使用时间比例", ratio))
    external = {"included_or_not_external":"不外属，或能耗已计入", "both_external_excluded":"两项全部外属且能耗均未计入", "partial_or_unknown":"部分或未知"}
    inputs.append(field("煤气净化及废水处理", external[values["energy"]["external_services_status"]]))
    actual = energy["actual_energy_kgce_per_t"]
    evaluation = energy["evaluation_energy_kgce_per_t"]
    limits = tuple(field(GRADE_LABELS[Grade(v["grade"])]+"修正限额",v["threshold"],"kgce/t") for v in saved["levels"])
    bases = tuple(field(GRADE_LABELS[Grade(v["grade"])]+"基准限额",v["base_threshold"],"kgce/t") for v in saved["levels"])
    metric = CementMetricView("评价能耗",evaluation,evaluation,"kgce/t",GRADE_LABELS[result.results[0].grade],limits,bases)
    calculations = [f"实际能耗：{actual} kgce/t",f"外属调整：{energy['adjustment_kgce_per_t']} kgce/t",
                    f"评价能耗：{evaluation} kgce/t"]
    for level in saved["levels"]:
        match = level["matched"]
        calculations.append(GRADE_LABELS[Grade(level["grade"])]+"："+("待确定" if match is None else "满足" if match else "不满足")
                            + ("；"+"；".join(level["undetermined_reasons"]) if level["undetermined_reasons"] else ""))
    flows = request.coke_payload.get("flows")
    if flows:
        # v2名称取保存参数；旧v1采用固定展示字典，不随当前系数表改名。
        legacy_names = {"dry_clean_coal":"干洗精煤", "dry_coke":"干全焦", "coal_tar":"高温煤焦油（干基）",
                        "crude_benzene":"粗苯", "coke_oven_gas":"焦炉煤气", "blast_furnace_gas":"高炉煤气",
                        "converter_gas":"转炉煤气", "natural_gas":"天然气", "diesel":"柴油", "gasoline":"汽油",
                        "electricity":"电力（当量值）", "heat":"热力（当量值）", "fresh_water":"新水", "soft_water":"软化水",
                        "compressed_air":"压缩空气", "oxygen":"氧气", "nitrogen_byproduct":"氮气（做副产品）", "nitrogen_main":"氮气（做主产品）"}
        saved_references = (snapshot.coke_rule_parameters or {}).get("flow_reference", {}).get("references", {})
        for row in flows["rows"]:
            flow = row["flow"]
            name = saved_references.get(flow["energy_id"], (legacy_names.get(flow["energy_id"], "蒸汽或其他能流"),))[0]
            inputs.append(field(LABELS[flow["component"]]+" · "+name,
                f"{flow['quantity']} {flow['unit']} × {row['coefficient']} {row['coefficient_unit']} = {row['energy_kgce']} kgce"))
            inputs.append(field("系数来源",row["coefficient_source"]))
            trace = row.get("conversion_trace")
            if trace:
                inputs.append(field(trace["method"], trace["input_value"], trace["input_unit"]))
                inputs.append(field("实测折标换算", f"{trace['expression']} = {trace['coefficient']} {row['coefficient_unit']}"))
                inputs.append(field("换算依据", trace["basis"]))
    oven = "顶装焦炉" if values["oven_type"] == "top_charging" else "捣固焦炉"
    basis = ("GB 21342—2025 §4表1、§5.3表2、§6.1.1及§6.2式（3）",)
    return CokeReportView(result.evaluation_id,"焦炭能耗对标报告",information,
        (CementLineReport(request.organization_name or "评价对象",oven,(metric,),tuple(inputs),tuple(calculations),basis),),(),
        ("同一统计期、同一常规焦炉类型；采用保存时输入、能流及计算结果。", *saved["warnings"]),result.rule_revision,result.rule_snapshot_sha256)
