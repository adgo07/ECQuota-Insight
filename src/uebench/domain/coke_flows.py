"""焦炭五类能流归集，仅采用已明确的有效系数，不猜测热值/焓换算常数。"""
from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext

from .gb21342 import CokeEnergyInput, CokeCalculationError, LABELS, _optional_number, _declared_context
from .coke_reference import SATURATED_STEAM, SUPERHEATED_STEAM

FLOW_VERSION = "gb21342-flows-unpublished-v1"
COMPONENTS = tuple(key for key in LABELS if key != "dry_coke_output_t")
# 附录A.1/A.2、B.1原表系数，不从平均热值反算。
# 气种005未决，不登记驰/弛放气自动别名。
REFERENCES = {
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


@dataclass(frozen=True)
class FlowValue:
    flow: CokeFlow
    coefficient: Decimal | None
    coefficient_unit: str | None
    coefficient_source: str
    energy_kgce: Decimal | None
    reason: str = ""


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


def _conversion(unit, base):
    if unit == base:
        return Decimal(1)
    conversions = {("t", "kg"): "1000", ("kg", "t"): "0.001",
                   ("tce", "kgce"): "1000", ("MWh", "kWh"): "1000",
                   ("GJ", "MJ"): "1000"}
    if (unit, base) not in conversions:
        raise CokeCalculationError(f"数量单位{unit}不能转换为系数分母单位{base}")
    return Decimal(conversions[unit, base])


def aggregate_flows(flows, *, zero_components=()):
    """未出现的分量为缺失；真实零须显式声明。重复物理流ID直接拒绝。"""
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
                if quantity is not None and quantity < 0 or measured is not None and measured < 0:
                    raise CokeCalculationError("原始数量及有效折标系数不能为负数，请核查能流方向")
                p = _optional_number(flow.pressure_mpa, "蒸汽绝对压力")
                t = _optional_number(flow.temperature_c, "蒸汽温度")
                reference = REFERENCES.get(flow.energy_id)
                coefficient, base, source = None, None, ""
                if reference and flow.energy_id in {"dry_clean_coal", "dry_coke"}:
                    _, base, value, location = reference
                    coefficient, source = Decimal(value), "GB 21342—2025 表" + location
                elif measured is not None:
                    if not flow.coefficient_unit or not flow.coefficient_unit.startswith("kgce/"):
                        raise CokeCalculationError("实测有效系数须明确kgce/数量单位")
                    coefficient, base, source = measured, flow.coefficient_unit[5:], flow.source or "实测有效系数（来源待补）"
                    if not flow.source.strip():
                        warnings.append("实测有效系数来源待补，请保留报告期计量依据。")
                elif reference:
                    _, base, value, location = reference
                    coefficient, source = Decimal(value), "GB 21342—2025 表" + location
                elif flow.energy_id in {"saturated_steam", "superheated_steam"}:
                    if flow.pressure_basis != "absolute":
                        raise CokeCalculationError("蒸汽参考查表必须使用绝对压力，不能将表压直接代入")
                    table = SATURATED_STEAM if flow.energy_id == "saturated_steam" else SUPERHEATED_STEAM
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
                    value = quantity * _conversion(flow.unit, base) * coefficient
                rows.append(FlowValue(flow, coefficient, "kgce/" + base if base else None, source, value, reason))
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
