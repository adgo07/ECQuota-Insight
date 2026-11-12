"""GB16780 V1.2 的分线、依赖计算。只用于明确采用映射的 r3。

式（2）～（9）来自2021正式版；源端四扣除采用Owner批准的2019技术参考。
ECQ-STD-GB16780-001/003是项目内部解释，不是官方勘误。
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, DecimalException, localcontext
from uuid import uuid4

from .engine import EvaluationContext, EvaluationValidationError
from .numeric import ECQUOTA_DECIMAL_FULL_VALUE_V1
from .models import (
    CalculationStep, EvaluationRequest, EvaluationResult, Grade, IndicatorResult,
    InputMode, InputValue, StandardDefinition, parse_decimal,
)

STANDARD_ID = "gb-16780-2021"
PRODUCT_ID = "cement-assessment"
RULE_REVISION = 3
MAPPING_SHA256 = "43d75b9724d8105ca27f0b3eeadd41de7dce1f92fa26965306c69cad5c17575c"
ADOPTION_MARKER = (
    "软件映射采用（非标准勘误）：GB16780-2021/标准映射表_V1.2_修订稿.md; "
    f"sha256={MAPPING_SHA256}"
)
CALCULATOR_VERSION = "gb16780-calculator-v1"
NUMERIC_BEHAVIOR_VERSION = "gb16780-v1.2-calculated-ratio-v2"

# 名称/单位/正数要求也作为原始输入校验契约；规则定义须与其一致。
INPUTS = {
    "site.altitude_m": ("厂区海拔", "m", False),
    "site.pressure_pa": ("环境大气压 P_H", "Pa", True),
    "clinker.production_t": ("熟料自产总产量 P_sh", "t", True),
    "cement.clinker_consumption_t": ("生产水泥消耗的熟料总量 P_shx", "t", False),
    "cement.production_t": ("水泥总产量 P_s", "t", True),
    "fuel.standard_coal_heat_kj_per_kgce": ("标准煤发热量 Q_BM", "kJ/kgce", True),
    "clinker.electricity_kwh": ("熟料综合用电量 w_sh", "kWh", False),
    "heat.generation_kwh": ("余热电站发电量 w_he", "kWh", False),
    "heat.own_use_kwh": ("余热电站自用电量 w_0", "kWh", False),
    "deduction.co_processing_fuel_tce": ("协同处置燃料折标煤量", "tce", False),
    "deduction.alternative_fuel_tce": ("替代燃料折标煤量", "tce", False),
    "deduction.co_processing_electricity_kwh": ("协同处置消耗电量", "kWh", False),
    "deduction.alternative_fuel_electricity_kwh": ("替代燃料消耗电量", "kWh", False),
    "cement.clinker_percent": ("水泥平均熟料配比 g", "%", False),
    "cement.grinding_packaging_kwh": ("水泥粉磨和包装电量 w_fm", "kWh", False),
    "cement.additives_preprocessing_kwh": ("混合材预处理电量 w_m", "kWh", False),
    "cement.gypsum_preprocessing_kwh": ("石膏预处理电量 w_g", "kWh", False),
    "cement.auxiliary_kwh": ("分摊辅助生产电量 w_fz", "kWh", False),
    "cement.preparation_fuel_kgce": ("水泥制备系统燃料折标煤量 e_h", "kgce", False),
    "cement.preparation_electricity_kwh": ("水泥制备工段电量 w_sg", "kWh", False),
}
DEDUCTIONS = tuple(key for key in INPUTS if key.startswith("deduction."))
SHARED_TARGETS = {
    "clinker_fuel": ("clinker.production_t", "fuel"),
    "clinker_electricity": ("clinker.production_t", "clinker.electricity_kwh"),
    "cement_auxiliary": ("cement.production_t", "cement.auxiliary_kwh"),
    "cement_preparation": ("cement.production_t", "cement.preparation_electricity_kwh"),
}
ACTUALS = {
    "cement.comprehensive_energy": "E_s", "clinker.comprehensive": "E_sh", "clinker.electricity": "W_sh",
    "clinker.coal": "e_sh", "cement-preparation.electricity": "W_sg",
}


def adopted(standard: StandardDefinition) -> bool:
    return (standard.id == STANDARD_ID and standard.rule_revision == RULE_REVISION
            and ADOPTION_MARKER in standard.corrections)


class NodeError(ValueError):
    pass


def number(value, label: str, *, positive=False, negative=False) -> Decimal:
    try:
        result = parse_decimal(value, field_name=label)
    except (TypeError, ValueError) as exc:
        raise NodeError(str(exc)) from exc
    if positive and result <= 0:
        raise NodeError(f"{label} 必须大于0")
    if not negative and result < 0:
        raise NodeError(f"{label} 不能为负数")
    return result


def input_number(supplied: InputValue | None, key: str) -> Decimal:
    label, unit, positive = INPUTS[key]
    if supplied is None or supplied.value in (None, ""):
        raise NodeError(f"缺少输入：{label}")
    if supplied.unit not in (None, unit):
        raise NodeError(f"{label} 单位应为 {unit}")
    result = number(supplied.value, label, positive=positive, negative=key == "site.altitude_m")
    if key == "cement.clinker_percent" and result > 100:
        raise NodeError(f"{label} 必须在0～100%之间")
    return result


RATIO_MODES = frozenset({"integrated", "partial_purchase"})


def clinker_ratio(inputs) -> Decimal:
    """Owner 2026-11-12 决定：新评价的 g 仅从原始数量计算。"""
    with localcontext(ECQUOTA_DECIMAL_FULL_VALUE_V1.decimal_context()):
        consumption = input_number(inputs.get("cement.clinker_consumption_t"), "cement.clinker_consumption_t")
        production = input_number(inputs.get("cement.production_t"), "cement.production_t")
        if consumption > production:
            raise NodeError("生产水泥消耗的熟料总量不能大于水泥总产量（计算配比超过100%）")
        try:
            return consumption / production * Decimal(100)
        except DecimalException as exc:
            raise NodeError("熟料配比无法计算，请核对熟料消耗量与水泥产量") from exc


def fuel_values(fuels):
    if not fuels:
        raise NodeError("缺少原始燃料明细；本期为零时请明确填写零用量")
    if len({f.line_id for f in fuels}) != len(fuels):
        raise NodeError("原始燃料明细标识重复")
    for fuel in fuels:
        yield (fuel, number(fuel.mass_kg, f"{fuel.energy_name} 实物量"),
               number(fuel.low_calorific_value_kj_per_kg, f"{fuel.energy_name} 低位发热量", positive=True))


class LineCalculation:
    def __init__(self, line, engine, k_formula):
        self.line = line
        self.engine = engine
        self.k_formula = k_formula
        self.cache: dict[str, Decimal | NodeError] = {}
        self.steps: dict[str, list[CalculationStep]] = {}
        self.shared: dict[str, list[tuple[Decimal | NodeError, list[CalculationStep]]]] = {}

    @staticmethod
    def step(label, expression, value, unit=None, operation="cement_formula"):
        return CalculationStep(sequence=0, label=label, operation=operation,
                               expression=expression, value=value, unit=unit)

    def extra(self, target):
        total = Decimal(0)
        for value, _ in self.shared.get(target, []):
            if isinstance(value, NodeError):
                raise value
            total += value
        return total

    def get(self, key):
        if key in self.cache:
            value = self.cache[key]
            if isinstance(value, NodeError):
                raise value
            return value
        trace = []
        self.steps[key] = trace

        def dep(name):
            try:
                return self.get(name)
            finally:
                trace.extend(self.steps.get(name, []))

        try:
            if key == "cement.clinker_percent":
                value = clinker_ratio(self.line.inputs)
                dep("cement.clinker_consumption_t")
                dep("cement.production_t")
                trace.append(self.step(INPUTS[key][0], "P_shx/P_s×100", value, "%"))
            elif key in INPUTS:
                supplied = self.line.inputs.get(key)
                label, unit, _ = INPUTS[key]
                if key in DEDUCTIONS and (supplied is None or supplied.value in (None, "")):
                    # 原始状态仍在request及trace中，空白不是活动不存在的证明。
                    trace.append(self.step(label, "未填（无需软件额外扣除）；额外扣量按0计算", None, unit, "input"))
                    value = Decimal(0)
                else:
                    value = input_number(supplied, key)
                    trace.append(self.step(label, key, value, unit, "input"))
                for target, (_, target_key) in SHARED_TARGETS.items():
                    if key == target_key:
                        value += self.extra(target)
                        for _, steps in self.shared.get(target, []):
                            trace.extend(steps)
            elif key == "H":
                value = Decimal(0)
                # Shared raw fuel is a valid explicit source even if the line has no local row.
                if self.line.fuels:
                    for fuel, mass, heat in fuel_values(self.line.fuels):
                        value += mass * heat
                        trace.append(self.step(f"燃料：{fuel.energy_name}", f"{mass} kg × {heat} kJ/kg", mass * heat, "kJ"))
                elif not self.shared.get("clinker_fuel"):
                    raise NodeError("缺少原始燃料明细；本期为零时请明确填写零用量")
                value += self.extra("clinker_fuel")
                for _, steps in self.shared.get("clinker_fuel", []):
                    trace.extend(steps)
            elif key == "F":
                value = dep("H") / dep("fuel.standard_coal_heat_kj_per_kgce")
            elif key == "E_he":
                net = dep("heat.generation_kwh") - dep("heat.own_use_kwh")
                if net < 0:
                    raise NodeError("余热电站自用电量不能大于发电量")
                value = Decimal("0.1229") * (net / dep("clinker.production_t"))
            elif key == "e_fc":
                value = Decimal(1000) * (dep(DEDUCTIONS[0]) + dep(DEDUCTIONS[1]))
            elif key == "w_fc":
                value = dep(DEDUCTIONS[2]) + dep(DEDUCTIONS[3])
            elif key == "e_sh_before":
                dep("F")  # 扣前总量审计；正式式（2）保持原分母运算顺序。
                value = dep("H") / (dep("fuel.standard_coal_heat_kj_per_kgce") * dep("clinker.production_t")) - dep("E_he")
            elif key == "e_sh":
                value = dep("e_sh_before") - dep("e_fc") / dep("clinker.production_t")
            elif key == "W_sh_before":
                value = dep("clinker.electricity_kwh") / dep("clinker.production_t")
            elif key == "W_sh":
                dep("W_sh_before")
                value = (dep("clinker.electricity_kwh") - dep("w_fc")) / dep("clinker.production_t")
            elif key == "E_sh":
                value = dep("e_sh") + Decimal("0.1229") * dep("W_sh")
            elif key == "w_s":
                own = Decimal(0) if self.line.production_mode == "purchased_clinker_grinding" else dep("W_sh")
                value = (dep("cement.grinding_packaging_kwh") + own * dep("cement.clinker_consumption_t")
                         + dep("cement.additives_preprocessing_kwh") + dep("cement.gypsum_preprocessing_kwh")
                         + dep("cement.auxiliary_kwh"))
            elif key == "W_s":
                value = dep("w_s") / dep("cement.production_t")
            elif key == "E_s":
                coal = Decimal(0) if self.line.production_mode == "purchased_clinker_grinding" else dep("e_sh")
                value = (coal * (dep("cement.clinker_percent") / Decimal(100))
                         + dep("cement.preparation_fuel_kgce") / dep("cement.production_t")
                         + Decimal("0.1229") * dep("W_s"))
            elif key == "W_sg":
                value = dep("cement.preparation_electricity_kwh") / dep("cement.production_t")
            elif key == "K":
                values = {"site.altitude_m": dep("site.altitude_m")}
                if values["site.altitude_m"] > Decimal(1500):
                    values["site.pressure_pa"] = dep("site.pressure_pa")
                value = self.engine.expressions.evaluate(
                    self.k_formula, EvaluationContext(values, {}), trace, label=NODE_LABELS["K"])
            else:
                raise NodeError(f"未定义的水泥计算节点：{key}")
            if not value.is_finite() or (key not in INPUTS and key != "K" and value < 0):
                raise NodeError("扣除量超过同统计边界原始用量，或计算结果无效")
            if key not in INPUTS and key != "K":
                trace.append(self.step(NODE_LABELS[key], NODE_EXPRESSIONS[key], value, NODE_UNITS.get(key)))
            self.cache[key] = value
            return value
        except (NodeError, DecimalException) as exc:
            error = NodeError(str(exc))
            self.cache[key] = error
            raise error from exc


NODE_LABELS = {
    "K": "海拔修正系数K",
    "H": "燃料热量合计", "F": "原始燃料折标煤量", "E_he": "余热发电折算标准煤量",
    "e_fc": "燃料扣除合计", "w_fc": "电量扣除合计", "e_sh_before": "熟料煤耗（四项扣除前，已扣余热）",
    "e_sh": "熟料净综合煤耗", "W_sh_before": "熟料电耗（扣除前）", "W_sh": "熟料净综合电耗",
    "E_sh": "熟料单位产品综合能耗", "w_s": "水泥综合用电总量", "W_s": "水泥单位产品综合电耗（中间量）",
    "E_s": "水泥单位产品综合能耗", "W_sg": "水泥制备工段电耗",
}
NODE_EXPRESSIONS = {
    "H": "Σ(m_i×Q_idw)，含按产量分摊的共用燃料", "F": "H/Q_BM",
    "E_he": "2021式（3）：0.1229×((w_he−w_0)/P_sh)",
    "e_fc": "V1.2软件解释（2019技术参考）：1000×(协同处置燃料tce+替代燃料tce)",
    "w_fc": "V1.2软件解释（2019技术参考）：协同处置电量+替代燃料电量",
    "e_sh_before": "2021式（2）：H/(Q_BM×P_sh)−E_he",
    "e_sh": "2021式（2）+批准的2019(C.1)技术参考：e_sh_before−e_fc/P_sh",
    "W_sh_before": "2021式（4）：w_sh/P_sh",
    "W_sh": "2021式（4）+批准的2019(C.3)技术参考：(w_sh−w_fc)/P_sh",
    "E_sh": "2021式（5）：e_sh+0.1229×W_sh（不再扣除）",
    "w_s": "2021式（7）：w_fm+W_sh×P_shx+w_m+w_g+w_fz（不再扣除）",
    "W_s": "2021式（6）：w_s/P_s",
    "E_s": "2021式（8）：e_sh×(g/100)+e_h/P_s+0.1229×W_s；Issue001内部解释",
    "W_sg": "2021式（9）：w_sg/P_s（不扣窑系统用量）",
}
NODE_UNITS = {"H": "kJ", "F": "kgce", "E_he": "kgce/t", "e_fc": "kgce", "w_fc": "kWh",
              "e_sh_before": "kgce/t", "e_sh": "kgce/t", "W_sh_before": "kWh/t", "W_sh": "kWh/t",
              "E_sh": "kgce/t", "w_s": "kWh", "W_s": "kWh/t", "E_s": "kgce/t", "W_sg": "kWh/t"}


def allocate_shared(request, calculations):
    seen = set()
    for shared in request.cement_shared_energy:
        if shared.shared_id in seen:
            raise EvaluationValidationError("共用系统用量标识重复，不能重复分摊")
        seen.add(shared.shared_id)
        if len(set(shared.line_ids)) != len(shared.line_ids) or any(x not in calculations for x in shared.line_ids):
            raise EvaluationValidationError("共用系统参与生产线重复或不存在")
        output_key, _ = SHARED_TARGETS[shared.target]
        participants = [calculations[x] for x in shared.line_ids]
        for calc in participants:
            forbidden = (calc.line.production_mode == "purchased_clinker_grinding"
                         if output_key == "clinker.production_t" else calc.line.production_mode == "clinker_only")
            if forbidden:
                raise EvaluationValidationError("共用系统目标与参与生产线模式不适用")
        if shared.target == "clinker_fuel" and shared.amount is not None:
            raise EvaluationValidationError("共用燃料须按实物量及发热量录入，不能用电量或折标总量代替")
        if shared.target != "clinker_fuel" and shared.fuels:
            raise EvaluationValidationError("共用电量不能混入燃料明细")
        try:
            outputs = [calc.get(output_key) for calc in participants]
            denominator = sum(outputs, Decimal(0))
            fuels = list(fuel_values(shared.fuels)) if shared.target == "clinker_fuel" else []
            amount = (None if fuels else number(
                None if shared.amount is None else shared.amount.value, "共用系统电量"))
            if not fuels and shared.amount is not None and shared.amount.unit not in (None, "kWh"):
                raise NodeError("共用系统电量单位应为 kWh")
            allocations = []
            for output in outputs:
                ratio = output / denominator
                steps = []
                if fuels:
                    value = Decimal(0)
                    for fuel, mass, heat in fuels:
                        allocated_mass = mass * ratio
                        contribution = allocated_mass * heat
                        value += contribution
                        steps.append(LineCalculation.step(
                            f"共用燃料分摊：{shared.shared_id} / {fuel.energy_name}",
                            f"{mass} kg × ({output}/{denominator}) × {heat} kJ/kg", contribution, "kJ", "allocation"))
                else:
                    value = amount * ratio
                    steps.append(LineCalculation.step(
                        f"共用电量分摊：{shared.shared_id}", f"{amount} kWh × ({output}/{denominator})",
                        value, "kWh", "allocation"))
                allocations.append((value, steps))
        except NodeError as exc:
            allocations = [(exc, []) for _ in participants]
        except DecimalException as exc:
            allocations = [(NodeError(f"共用系统分摊失败：{exc}"), []) for _ in participants]
        for calc, allocation in zip(participants, allocations, strict=True):
            calc.shared.setdefault(shared.target, []).append(allocation)


def _unique_trace(trace):
    result, seen = [], set()
    for step in trace:
        identity = (step.label, step.operation, step.expression, step.value, step.unit)
        if identity not in seen:
            seen.add(identity)
            result.append(step.model_copy(update={"sequence": len(result) + 1}))
    return result


def evaluate_cement(engine, standard: StandardDefinition, request: EvaluationRequest) -> EvaluationResult:
    """内部入口；必须由EvaluationEngine的Profile-owned authoritative scope调用。"""
    if not adopted(standard) or request.product_id != PRODUCT_ID:
        raise EvaluationValidationError("水泥V1.2只接受明确采用映射的r3及配套评价产品")
    if request.input_mode is not InputMode.DETAIL:
        raise EvaluationValidationError("水泥V1.2仅支持原始明细计算，不接受直接输入最终单位值")
    if request.inputs or request.energy_lines or request.production_lines:
        raise EvaluationValidationError("水泥V1.2须使用分线原始明细，不能混入通用最终值或折标总量")
    if not request.cement_lines:
        raise EvaluationValidationError("请至少填写一条水泥生产线")
    if len({line.line_id for line in request.cement_lines}) != len(request.cement_lines):
        raise EvaluationValidationError("生产线标识重复")
    product = next((item for item in standard.products if item.id == PRODUCT_ID), None)
    if product is None:
        raise EvaluationValidationError("水泥r3规则缺少配套评价产品，映射采用身份无效")
    if {item.id for item in product.indicators} != set(ACTUALS) or len(product.indicators) != 5:
        raise EvaluationValidationError("水泥r3规则缺少必要指标或包含重复指标")
    k_nodes = [display for indicator in product.indicators for display in indicator.display_calculations
               if display.key == "K" and InputMode.DETAIL in display.modes]
    if len(k_nodes) != 1:
        raise EvaluationValidationError("水泥r3规则须包含唯一的海拔修正系数K节点")
    calculations = {line.line_id: LineCalculation(line, engine, k_nodes[0].formula) for line in request.cement_lines}
    for line in request.cement_lines:
        if set(line.inputs) - INPUTS.keys():
            raise EvaluationValidationError("水泥生产线含未知输入，请使用配套明细字段")
        if line.production_mode == "purchased_clinker_grinding":
            for key in DEDUCTIONS:
                supplied = line.inputs.get(key)
                if supplied is not None and supplied.value not in (None, ""):
                    if input_number(supplied, key) != 0:
                        raise EvaluationValidationError("全部外购熟料粉磨站不适用窑系统扣除，请移除该用量")
    allocate_shared(request, calculations)
    results = []
    for line in request.cement_lines:
        calc = calculations[line.line_id]
        for indicator in product.indicators:
            context = EvaluationContext({"production_mode": line.production_mode}, {})
            item = IndicatorResult(
                line_id=line.line_id, line_name=line.line_name,
                indicator_id=indicator.id, indicator_name=indicator.name,
                actual_value=None, unit=indicator.unit, grade=Grade.NOT_APPLICABLE,
                source_references=indicator.source_references,
            )
            if engine.conditions.evaluate(indicator.applicability, context):
                node = ACTUALS[indicator.id]
                trace = []
                try:
                    try:
                        item.actual_value = calc.get(node)
                    finally:
                        trace.extend(calc.steps.get(node, []))
                    # 表3没有海拔/压力依赖；其余指标的实际值不因限额数据缺失而丢失。
                    if node != "W_sg":
                        try:
                            context.values["calculated.K"] = calc.get("K")
                        finally:
                            trace.extend(calc.steps.get("K", []))
                    if node == "E_s":
                        context.values["cement.clinker_percent"] = calc.get("cement.clinker_percent")
                    item.base_thresholds = engine._evaluate_threshold_set(
                        indicator.base_thresholds or indicator.thresholds, context, trace, "基准")
                    item.corrected_thresholds = engine._evaluate_threshold_set(indicator.thresholds, context, trace, "有效")
                    limits = list(item.corrected_thresholds.values())
                    if (len(limits) != 3 or any(not v.is_finite() for v in limits)
                            or not limits[0] <= limits[1] <= limits[2]):
                        raise NodeError("修正后的等级限额顺序无效，无法判级；请核对气压及配比")
                    item.grade = engine._grade(item.actual_value, item.corrected_thresholds, indicator.comparison,
                                               trace=trace, unit=item.unit,
                                               numeric_behavior_version=NUMERIC_BEHAVIOR_VERSION)
                except (ValueError, DecimalException) as exc:
                    item.grade = Grade.INCOMPLETE
                    item.warnings.append(str(exc))
                # 扣前/后及全链中间量来自本次计算缓存，无第二次公式计算。
                trace_labels = {step.label for step in trace}
                item.display_values = {key: value for key, value in calc.cache.items()
                                       if key in NODE_LABELS and NODE_LABELS[key] in trace_labels
                                       and isinstance(value, Decimal)}
                item.calculation_trace = _unique_trace(trace)
            results.append(item)
    return EvaluationResult(
        evaluation_id=str(uuid4()), evaluated_at=datetime.now(timezone.utc),
        standard_id=standard.id, standard_number=standard.number, standard_title=standard.title,
        standard_version=standard.version, standard_family_id=standard.family_id,
        rule_revision=standard.rule_revision,
        numeric_contract_version=engine.numeric_profile.numeric_contract_version,
        numeric_profile_id=engine.numeric_profile.numeric_profile_id,
        calculator_version=CALCULATOR_VERSION, numeric_behavior_version=NUMERIC_BEHAVIOR_VERSION,
        product_id=product.id, product_name=product.name, results=results,
        rule_snapshot_sha256=engine._snapshot_sha256(standard),
    )
