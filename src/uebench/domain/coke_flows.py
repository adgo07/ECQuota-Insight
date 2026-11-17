"""焦炭五类能流归集，采用经原文核实的有效系数及实测热值/热焓折标。"""
from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext

from .gb21342 import CokeEnergyInput, CokeCalculationError, LABELS, _optional_number, _declared_context
from .coke_reference import SATURATED_STEAM, SUPERHEATED_STEAM

FLOW_VERSION = "gb21342-flows-v2"
COMPONENTS = tuple(key for key in LABELS if key != "dry_coke_output_t")
# 附录A.1/A.2、B.1原表系数，不从平均热值反算。
# 气种005未决，不登记驰/弛放气自动别名。
_REFERENCE_ROWS = {
    "dry_clean_coal": ("干洗精煤", "kg", "1.0143", "A.1"),
    "dry_coke": ("干全焦", "kg", "0.9714", "A.1"),
    "coal_tar": ("高温煤焦油（干基）", "kg", "1.2857", "A.1"),
    "crude_benzene": ("粗苯", "kg", "1.4286", "A.1"),
    "coke_oven_gas": ("焦炉煤气", "m³", "0.5714", "A.1"),
    "blast_furnace_gas": ("高炉煤气", "m³", "0.1286", "A.1"),
    "converter_gas": ("转炉煤气", "m³", "0.2500", "A.1"),
    "natural_gas": ("天然气", "m³", "1.3300", "A.1"),
    "diesel": ("柴油", "kg", "1.4571", "A.1"),
    "gasoline": ("汽油", "kg", "1.4714", "A.1"),
    "electricity": ("电力（当量值）", "kWh", "0.1229", "A.2"),
    "heat": ("热力（当量值）", "MJ", "0.03412", "A.2"),
    "fresh_water": ("新水", "t", "0.2571", "B.1"),
    "soft_water": ("软化水", "t", "0.4857", "B.1"),
    "compressed_air": ("压缩空气", "m³", "0.0400", "B.1"),
    "oxygen": ("氧气", "m³", "0.4000", "B.1"),
    "nitrogen_byproduct": ("氮气（做副产品）", "m³", "0.4000", "B.1"),
    "nitrogen_main": ("氮气（做主产品）", "m³", "0.6714", "B.1"),
}


# 当前界面展示字典可独立演进；严格参数校验使用固定版本的声明。
REFERENCES = dict(_REFERENCE_ROWS)


@dataclass(frozen=True)
class CokeFlow:
    flow_id: str
    component: str
    energy_id: str
    quantity: Decimal | str | int | None
    unit: str
    measured_coefficient: Decimal | str | int | None = None
    coefficient_unit: str | None = None
    source: str = ""
    pressure_mpa: Decimal | str | int | None = None
    temperature_c: Decimal | str | int | None = None
    pressure_basis: str = "absolute"
    measured_calorific_value: Decimal | str | int | None = None
    calorific_value_unit: str | None = None
    measured_enthalpy_kj_per_kg: Decimal | str | int | None = None


@dataclass(frozen=True)
class FlowValue:
    flow: CokeFlow
    coefficient: Decimal | None
    coefficient_unit: str | None
    coefficient_source: str
    energy_kgce: Decimal | None
    reason: str = ""
    conversion_trace: dict | None = None


@dataclass(frozen=True)
class CokeFlowResult:
    rows: tuple[FlowValue, ...]
    totals: dict[str, Decimal | None]
    warnings: tuple[str, ...]
    version: str = FLOW_VERSION

    def energy_input(self, dry_coke_output_t, external_services_status):
        missing = [LABELS[k] for k, v in self.totals.items() if v is None]
        if missing:
            raise CokeCalculationError("能流分量待确定：" + "、".join(missing))
        return CokeEnergyInput(**self.totals, dry_coke_output_t=dry_coke_output_t,
                               external_services_status=external_services_status)


FUEL_IDS = frozenset({"coal_tar", "crude_benzene", "coke_oven_gas", "blast_furnace_gas", "converter_gas", "natural_gas", "diesel", "gasoline", "other_fuel"})
STEAM_IDS = frozenset({"saturated_steam", "superheated_steam"})


def verified_flow_reference_payload():
    """已核实、严格版本绑定的参数；不把实时Markdown作为规则源。"""
    return {
        "version": "gb21342-flow-reference-v1",
        "standard_coal_heat_kj_per_kgce": "29307.6",
        "heat_basis": "GB/T 2589—2020 §8.2，国际蒸汽表卡；收到基低位发热量",
        "steam_basis": "GB 21342—2025 §6.1.2.1，蒸汽热焓；不自动扣给水焓",
        "source_sha256": {
            "GB21342-2025": "00fcc51c02c6d73d39bcab3103227fca2ee93841abce45d1576edaeba25595a0",
            "GBT2589-2020": "984549542768ee2566997a28642af56c3ea76a67e3dab0a62821048ed6bb3f05",
            "GBT12723-2024": "ee3123197ed101c9c1fe83f01595feb43be7532656e979c3c0597b0232aa48c7",
        },
        "priority": "fixed-dry-coal-coke;exclusive-effective-coefficient-or-measured-q-or-h;reference-fallback",
        "references": {key: list(value) for key, value in _REFERENCE_ROWS.items()},
        "saturated_steam": [list(row) for row in SATURATED_STEAM],
        "superheated_steam": [list(row) for row in SUPERHEATED_STEAM],
        "unit_conversions": [["t", "kg", "1000"], ["kg", "t", "0.001"], ["tce", "kgce", "1000"], ["MWh", "kWh", "1000"], ["GJ", "MJ", "1000"]],
        "fuel_ids": sorted(FUEL_IDS), "steam_ids": sorted(STEAM_IDS),
    }


def _conversion(unit, base, parameters):
    if unit == base:
        return Decimal(1)
    conversions = {(a, b): c for a, b, c in parameters["unit_conversions"]}
    if (unit, base) not in conversions:
        raise CokeCalculationError(f"数量单位{unit}不能转换为系数分母单位{base}")
    return Decimal(conversions[unit, base])


def aggregate_flows(flows, *, zero_components=(), flow_parameters=None):
    """未出现的分量为缺失；真实零须显式声明。重复物理流ID直接拒绝。"""
    expected = verified_flow_reference_payload()
    parameters = expected if flow_parameters is None else flow_parameters
    if parameters != expected:
        raise CokeCalculationError("焦炭能流参数与已核实版本不一致")
    flows = tuple(flows)
    zero_components = frozenset(zero_components)
    if not zero_components <= set(COMPONENTS):
        raise CokeCalculationError("零发生量分量无效")
    totals = {key: Decimal(0) if key in zero_components else None for key in COMPONENTS}
    seen, grouped, rows, warnings = set(), {}, [], []
    try:
        with localcontext(_declared_context()):
            for flow in flows:
                if not isinstance(flow, CokeFlow) or not isinstance(flow.flow_id, str) or not flow.flow_id.strip():
                    raise CokeCalculationError("每股能流必须具有非空的唯一标识")
                if flow.flow_id in seen:
                    raise CokeCalculationError("同一股能流重复计入，请核查回收与抵扣")
                seen.add(flow.flow_id)
                if flow.component not in COMPONENTS or flow.component in zero_components:
                    raise CokeCalculationError("能流分量无效，或明细与零发生量声明冲突")
                quantity = _optional_number(flow.quantity, "能流数量")
                measured = _optional_number(flow.measured_coefficient, "实测有效折标系数")
                q = _optional_number(flow.measured_calorific_value, "实测收到基低位热值")
                h = _optional_number(flow.measured_enthalpy_kj_per_kg, "实测蒸汽热焓")
                methods = sum(v is not None for v in (measured, q, h))
                if methods > 1:
                    raise CokeCalculationError("实测有效系数、燃料低位热值和蒸汽热焓不能同时生效")
                if any(v is not None and v < 0 for v in (quantity, measured, q, h)):
                    raise CokeCalculationError("原始数量及有效折标系数不能为负数，请核查能流方向")
                p = _optional_number(flow.pressure_mpa, "蒸汽绝对压力")
                t = _optional_number(flow.temperature_c, "蒸汽温度")
                reference = parameters["references"].get(flow.energy_id)
                conversion_trace = None
                coefficient, base, source = None, None, ""
                if reference and flow.energy_id in {"dry_clean_coal", "dry_coke"}:
                    if methods:
                        raise CokeCalculationError("干洗精煤、干全焦采用附录A固定系数，请移除实测系数或热值冲突输入")
                    _, base, value, location = reference
                    coefficient, source = Decimal(value), "GB 21342—2025 表" + location
                elif measured is not None:
                    if not flow.coefficient_unit or not flow.coefficient_unit.startswith("kgce/"):
                        raise CokeCalculationError("实测有效系数须明确kgce/数量单位")
                    coefficient, base, source = measured, flow.coefficient_unit[5:], flow.source or "实测有效系数（来源待补）"
                    if not flow.source.strip():
                        warnings.append("实测有效系数来源待补，请保留报告期计量依据。")
                elif q is not None or h is not None:
                    if q is not None:
                        if flow.energy_id not in parameters["fuel_ids"]:
                            raise CokeCalculationError("实测低位热值只适用于燃料能源，不能用于电力、热力或耗能工质")
                        if flow.calorific_value_unit not in {"kJ/kg", "kJ/m³"}:
                            raise CokeCalculationError("实测低位热值单位须为kJ/kg或kJ/m³，并与数量维度匹配")
                        raw, base, method = q, flow.calorific_value_unit[3:], "实测收到基低位热值"
                    else:
                        if flow.energy_id not in parameters["steam_ids"]:
                            raise CokeCalculationError("实测热焓只适用于蒸汽")
                        raw, base, method = h, "kg", "实测蒸汽热焓"
                    denominator = Decimal(parameters["standard_coal_heat_kj_per_kgce"])
                    coefficient = raw / denominator
                    source = flow.source or method + "（来源待补）"
                    if not flow.source.strip():
                        warnings.append(method + "来源待补，请保留报告期计量依据。")
                    conversion_trace = {"method": method, "input_value": str(raw),
                        "input_unit": flow.calorific_value_unit if q is not None else "kJ/kg",
                        "expression": f"{raw} / {denominator}", "denominator_kj_per_kgce": str(denominator),
                        "coefficient": str(coefficient), "source": source,
                        "reference_version": parameters["version"], "basis": parameters["heat_basis"] if q is not None else parameters["steam_basis"]}
                elif reference:
                    _, base, value, location = reference
                    coefficient, source = Decimal(value), "GB 21342—2025 表" + location
                elif flow.energy_id in {"saturated_steam", "superheated_steam"}:
                    if flow.pressure_basis != "absolute":
                        raise CokeCalculationError("蒸汽参考查表必须使用绝对压力，不能将表压直接代入")
                    table = parameters["saturated_steam"] if flow.energy_id == "saturated_steam" else parameters["superheated_steam"]
                    node = next((row for row in table if p == Decimal(row[0]) and t == Decimal(row[1])), None)
                    if node:
                        coefficient, base = Decimal(node[3]), "kg"
                        source = "GB 21342—2025 表" + ("A.3" if flow.energy_id == "saturated_steam" else "A.4") + f" 绝对压力{p}MPa，{t}℃"
                elif flow.energy_id == "standard_coal":
                    coefficient, base, source = Decimal(1), "kgce", "已折标能流，单位换算"
                value = None
                reason = ""
                if quantity is None:
                    reason = "缺少能流数量"
                elif coefficient is None:
                    reason = "缺少有效系数，或蒸汽不在精确表列节点；未自动外推"
                else:
                    value = quantity * _conversion(flow.unit, base, parameters) * coefficient
                rows.append(FlowValue(flow, coefficient, "kgce/" + base if base else None, source, value, reason, conversion_trace))
                grouped.setdefault(flow.component, []).append(value)
            for key, values in grouped.items():
                totals[key] = None if any(v is None for v in values) else sum(values, Decimal(0))
    except DecimalException as exc:
        raise CokeCalculationError("能流折标超出项目数值配置范围") from exc
    if flows:
        warnings.append("请核查内部煤气、化产品及回收热量的统计边界；每股能流只计一次。")
    return CokeFlowResult(tuple(rows), totals, tuple(warnings))


def normalize_energy(*, mode, totals=None, flows=None, zero_components=(), dry_coke_output_t, external_services_status):
    if mode == "totals":
        if flows is not None or zero_components:
            raise CokeCalculationError("五分量总量与原始能流明细不能同时生效")
        return CokeEnergyInput(**(totals or {}), dry_coke_output_t=dry_coke_output_t,
                               external_services_status=external_services_status), None
    if mode == "flows":
        if totals is not None:
            raise CokeCalculationError("五分量总量与原始能流明细不能同时生效")
        result = aggregate_flows(flows or (), zero_components=zero_components)
        return result.energy_input(dry_coke_output_t, external_services_status), result
    raise CokeCalculationError("请选择已折标总量或原始能流明细")
