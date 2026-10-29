"""V1.2 cement orchestration. Fixed formulae live in the complete r2 rule snapshot."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, localcontext
from uuid import uuid4

from .engine import EvaluationContext, EvaluationEngine, EvaluationValidationError, RuleEvaluationError
from .models import (CalculationStep, DataType, EvaluationRequest, EvaluationResult,
                     Expression, Grade, IndicatorResult, InputMode, PublicationStatus, StandardDefinition, parse_decimal)

STANDARD_ID = "gb-16780-2021"
PRODUCT_ID = "cement"
PRODUCTION_MODES = {
    "integrated": "自产熟料并生产水泥", "partial_purchased": "部分外购熟料生产水泥",
    "clinker_only": "仅生产熟料", "grinding_station": "全部外购熟料粉磨站",
}
CLINKER_IDS = ("clinker.comprehensive", "clinker.coal", "clinker.electricity")
MODE_INDICATORS = {
    "integrated": ("cement.comprehensive_energy", *CLINKER_IDS, "cement-preparation.electricity"),
    "partial_purchased": ("cement.comprehensive_energy", *CLINKER_IDS, "cement-preparation.electricity"),
    "clinker_only": CLINKER_IDS, "grinding_station": ("cement-preparation.electricity",),
}
DEDUCTION_KEYS = tuple("deduction." + key for key in (
    "co_processing_fuel_tce", "alternative_fuel_tce", "co_processing_electricity_kwh", "alternative_fuel_electricity_kwh"))
COMMON_KEYS = ("evaluation_period", "production_line_id")
KILN_KEYS = ("altitude_m", "pressure_pa", "clinker_production_t", "clinker_electricity_kwh",
             "waste_heat_generation_kwh", "waste_heat_self_use_kwh", *DEDUCTION_KEYS)
CEMENT_KEYS = ("clinker_consumption_t", "cement_production_t", "clinker_ratio_percent",
               "cement_grinding_packaging_kwh", "admixture_preparation_kwh", "gypsum_preparation_kwh",
               "auxiliary_electricity_kwh", "cement_fuel_kgce", "grinding_electricity_kwh")
MODE_INPUT_KEYS = {
    "integrated": (*COMMON_KEYS, *KILN_KEYS, *CEMENT_KEYS),
    "partial_purchased": (*COMMON_KEYS, *KILN_KEYS, *CEMENT_KEYS),
    "clinker_only": (*COMMON_KEYS, *KILN_KEYS),
    "grinding_station": (*COMMON_KEYS, "cement_production_t", "grinding_electricity_kwh"),
}
COMPLETE_GRADES = frozenset((Grade.LEVEL_1, Grade.LEVEL_2, Grade.LEVEL_3, Grade.NOT_QUALIFIED))
ALLOCATION_TARGETS = {
    "clinker": {"clinker_electricity_kwh"},
    "cement": {"cement_grinding_packaging_kwh", "admixture_preparation_kwh", "gypsum_preparation_kwh",
               "auxiliary_electricity_kwh", "grinding_electricity_kwh", "cement_fuel_kgce"},
}


def is_complete(result: EvaluationResult) -> bool:
    return not result.warnings and bool(result.results) and any(x.grade in COMPLETE_GRADES for x in result.results) and all(
        x.grade in COMPLETE_GRADES or x.grade is Grade.NOT_APPLICABLE for x in result.results)


def _references(expression: Expression) -> set[str]:
    refs = {expression.input_key} if expression.op == "input" and expression.input_key else set()
    def conditions(condition):
        if condition.field: refs.add(condition.field)
        for child in condition.args: conditions(child)
    for arg in expression.args: refs.update(_references(arg))
    for case in [*expression.cases, *expression.rows]:
        conditions(case.condition)
        refs.update(_references(case.expression))
    if expression.default: refs.update(_references(expression.default))
    return refs


def validate_graph(standard: StandardDefinition) -> list:
    nodes = {node.key: node for node in standard.cement_calculation_nodes}
    if len(nodes) != len(standard.cement_calculation_nodes):
        raise RuleEvaluationError("水泥计算节点重复")
    if not nodes: raise RuleEvaluationError("水泥r2缺少计算节点")
    raw = {d.key for p in standard.products for d in p.input_definitions} | {"internal.fuel_heat_kj"}
    visited, visiting, ordered = set(), set(), []
    def visit(key):
        if key in visited: return
        if key in visiting: raise RuleEvaluationError("水泥计算节点存在循环依赖")
        if key not in nodes: raise RuleEvaluationError(f"未知水泥计算节点：{key}")
        visiting.add(key)
        for ref in _references(nodes[key].formula):
            if ref.startswith("computed."): visit(ref.removeprefix("computed."))
            elif ref not in raw: raise RuleEvaluationError(f"水泥计算节点引用未知输入：{ref}")
        visiting.remove(key); visited.add(key); ordered.append(nodes[key])
    for key in nodes: visit(key)
    for product in standard.products:
        for indicator in product.indicators:
            for expression in (indicator.detail_formula, indicator.thresholds.level_1, indicator.thresholds.level_2, indicator.thresholds.level_3):
                if expression:
                    for ref in _references(expression):
                        if ref.startswith("computed.") and ref.removeprefix("computed.") not in nodes:
                            raise RuleEvaluationError(f"指标引用未知水泥节点：{ref}")
                        if not ref.startswith("computed.") and ref not in raw:
                            raise RuleEvaluationError(f"指标引用未知输入：{ref}")
    # Adapter constants are a compatibility projection, never a second rule.
    # Fail visibly if a UI matrix drifts from the authoritative rule conditions.
    for mode, expected in MODE_INDICATORS.items():
        actual = indicator_ids_for_mode(standard, mode)
        if set(actual) != set(expected):
            raise RuleEvaluationError("水泥适用性描述与规则条件不一致，不能继续计算。")
    return ordered


def indicator_ids_for_mode(standard: StandardDefinition, mode: str) -> tuple[str, ...]:
    from .engine import ConditionEvaluator
    context = EvaluationContext({"production_mode": mode}, {})
    return tuple(indicator.id for product in standard.products for indicator in product.indicators
                 if ConditionEvaluator().evaluate(indicator.applicability, context))


class Gb16780Calculator:
    def __init__(self, engine: EvaluationEngine | None = None):
        self.engine = engine or EvaluationEngine()

    def evaluate(self, standard: StandardDefinition, request: EvaluationRequest, *, allow_pre_effective=False) -> EvaluationResult:
        if request.input_mode is not InputMode.DETAIL:
            raise EvaluationValidationError("水泥评价仅接受原始明细数据，不接受单位能耗直接录入。")
        if standard.id != STANDARD_ID or standard.rule_revision < 2 or request.standard_id != STANDARD_ID:
            raise EvaluationValidationError("水泥V1.2协调器仅适用于本标准r2及后续规则。")
        if standard.publication_status is not PublicationStatus.PUBLISHED:
            raise EvaluationValidationError("只有 published 标准规则可以正式计算")
        if request.product_id != PRODUCT_ID:
            raise EvaluationValidationError("水泥r2按同一生产线选择生产模式，请重新选择评价对象。")
        if not allow_pre_effective and request.evaluation_date < standard.effective_date:
            raise EvaluationValidationError("评价日期早于标准实施日期。")
        with localcontext(self.engine.numeric_profile.decimal_context()):
            return self._evaluate(standard, request)

    def _evaluate(self, standard, request):
        nodes = validate_graph(standard)
        product = next(p for p in standard.products if p.id == PRODUCT_ID)
        definitions = {d.key: d for d in product.input_definitions}
        if any(k not in definitions for k in request.inputs):
            raise EvaluationValidationError("水泥请求含未知输入或保留的派生字段；请仅提交原始数据。")
        mode = request.inputs.get("production_mode")
        mode = mode.value if mode else None
        if mode not in PRODUCTION_MODES:
            raise EvaluationValidationError("请选择有效的水泥生产模式。")
        if request.energy_lines or request.production_lines:
            raise EvaluationValidationError("水泥r2使用专属原始燃料及分线明细，不接受通用折标明细混入。")
        if mode == "grinding_station" and request.cement_details and request.cement_details.fuel_lines:
            raise EvaluationValidationError("全部外购熟料粉磨站不接收窑系统燃料明细，请核对当前生产模式。")
        # Hidden inputs from an old mode must never flow into the active request.
        if any(k not in {*MODE_INPUT_KEYS[mode], "production_mode"} and v.value not in (None, "") for k, v in request.inputs.items()):
            raise EvaluationValidationError("请求含当前生产模式不适用的输入，请切换模式后重新核对。")
        values, errors, trace = {}, {}, []
        for key, definition in definitions.items():
            supplied = request.inputs.get(key)
            if supplied is None or supplied.value is None or supplied.value == "":
                if key in DEDUCTION_KEYS: values[key] = Decimal(0)
                continue
            try:
                if supplied.unit != definition.unit: raise ValueError(f"单位应为{definition.unit or '无单位'}")
                if definition.data_type is DataType.TEXT:
                    if not isinstance(supplied.value, str): raise ValueError("应填写文本")
                    values[key] = supplied.value
                else:
                    value = parse_decimal(supplied.value, field_name=definition.label)
                    if definition.minimum is not None and value < definition.minimum: raise ValueError("低于允许下限")
                    if definition.maximum is not None and value > definition.maximum: raise ValueError("超过允许上限")
                    if key in ("pressure_pa", "clinker_production_t", "cement_production_t") and value <= 0:
                        raise ValueError("必须大于0")
                    values[key] = value
            except (ValueError, TypeError) as exc: errors[key] = f"{definition.label}：{exc}"
        # Required record metadata is a completeness concern, not a formula input.
        for key in COMMON_KEYS:
            if not values.get(key): errors[key] = f"请填写{definitions[key].label}"
        if mode != "grinding_station":
            self._fuel(request, values, errors, trace)
        self._allocations(request, definitions, values, errors, trace)
        context = EvaluationContext(values, {}, trace, {k:d.label for k,d in definitions.items()})
        node_errors, node_values = {}, {}
        for node in nodes:
            refs = _references(node.formula)
            failures = [errors[r] for r in refs if r in errors]
            failures += [node_errors[r[9:]] for r in refs if r.startswith("computed.") and r[9:] in node_errors]
            try:
                if failures: raise ValueError("；".join(dict.fromkeys(failures)))
                value = self.engine.expressions.evaluate(node.formula, context, trace, label=node.label)
                if node.source:
                    trace.append(CalculationStep(sequence=len(trace)+1, label=node.label+"参数来源", operation="source", expression=node.source, value=value, unit=node.unit))
                if node.key in ("waste_heat_net", "clinker_coal", "clinker_electricity") and value < 0:
                    message = "余热净发电量为负，当前受限处理不允许相关指标正式判级" if node.key == "waste_heat_net" else "扣除后能耗为负，请核对同统计边界及重复扣除"
                    raise ValueError(message)
                if node.key == "fuel_deduction" and "computed.fuel_standard_coal" in values and value > values["computed.fuel_standard_coal"]:
                    raise ValueError("燃料扣除超过原始燃料折标煤总量")
                values["computed." + node.key] = value; node_values[node.key] = value
            except (ValueError, ArithmeticError) as exc: node_errors[node.key] = f"{node.label}：{exc}"
        results = []
        for indicator in product.indicators:
            if not self.engine.conditions.evaluate(indicator.applicability, context):
                results.append(IndicatorResult(indicator_id=indicator.id, indicator_name=indicator.name, actual_value=None,
                    unit=indicator.unit, grade=Grade.NOT_APPLICABLE, source_references=indicator.source_references))
                continue
            item_trace = [s.model_copy() for s in trace]
            refs = set().union(*(_references(x) for x in (indicator.detail_formula, indicator.thresholds.level_1, indicator.thresholds.level_2, indicator.thresholds.level_3) if x))
            failures = [errors[r] for r in refs if r in errors]
            failures += [node_errors[r[9:]] for r in refs if r.startswith("computed.") and r[9:] in node_errors]
            warnings = []
            try:
                if failures: raise ValueError("；".join(dict.fromkeys(failures)))
                actual = self.engine.expressions.evaluate(indicator.detail_formula, context, item_trace, label=indicator.name)
                base = self.engine._evaluate_threshold_set(indicator.base_thresholds, context, item_trace, "基准")
                thresholds = self.engine._evaluate_threshold_set(indicator.thresholds, context, item_trace, "有效")
                if not thresholds["LEVEL_1"] <= thresholds["LEVEL_2"] <= thresholds["LEVEL_3"]:
                    raise ValueError("有效阈值顺序异常，无法判级；请核对气压与配比及适用边界。")
                grade = self.engine._grade(actual, thresholds, indicator.comparison, trace=item_trace, unit=indicator.unit)
                if indicator.id != "cement-preparation.electricity":
                    if values.get("altitude_m", Decimal(0)) > 1500:
                        warnings.append("海拔修正采用软件扩展口径，不限企业建设属性；标准该条针对现有企业。")
                    if indicator.id == "cement.comprehensive_energy":
                        warnings.append("ECQ-STD-GB16780-003：3级先海拔后配比修正，属于软件解释。")
                        if mode == "partial_purchased": warnings.append("ECQ-STD-GB16780-001：部分外购熟料式（8）采用本企业熟料综合煤耗，属于软件解释。")
                    if any(request.inputs.get(k) and request.inputs[k].value not in (None, "") for k in DEDUCTION_KEYS):
                        warnings.append("四项源端扣除采用2019征求意见稿(C.1)/(C.3)技术参考及用户软件决定，不冒充2021正式公式；不采用2019(C.7)。")
                results.append(IndicatorResult(indicator_id=indicator.id, indicator_name=indicator.name, actual_value=actual,
                    unit=indicator.unit, grade=grade, base_thresholds=base, corrected_thresholds=thresholds,
                    display_values=node_values, calculation_trace=item_trace, source_references=indicator.source_references, warnings=warnings))
            except (ValueError, ArithmeticError) as exc:
                results.append(IndicatorResult(indicator_id=indicator.id, indicator_name=indicator.name, actual_value=None,
                    unit=indicator.unit, grade=Grade.INCOMPLETE, display_values=node_values, calculation_trace=item_trace,
                    source_references=indicator.source_references, warnings=[str(exc)]))
        profile = self.engine.numeric_profile
        return EvaluationResult(evaluation_id=str(uuid4()), evaluated_at=datetime.now(timezone.utc), standard_id=standard.id,
            standard_number=standard.number, standard_title=standard.title, standard_version=standard.version,
            standard_family_id=standard.family_id, rule_revision=standard.rule_revision, product_id=product.id, product_name=product.name,
            results=results, rule_snapshot_sha256=self.engine._snapshot_sha256(standard), numeric_contract_version=profile.numeric_contract_version,
            numeric_profile_id=profile.numeric_profile_id, calculator_version="ecquota-gb16780-r2-dsl-v1",
            numeric_behavior_version="ecquota-gb16780-v1.2-full-value-v1", warnings=list(dict.fromkeys(errors[k] for k in COMMON_KEYS if k in errors)))

    def _fuel(self, request, values, errors, trace):
        lines = request.cement_details.fuel_lines if request.cement_details else []
        try:
            if not lines: raise ValueError("请填写原始燃料消耗量与低位发热量")
            if len({x.line_id for x in lines}) != len(lines): raise ValueError("燃料明细行标识重复")
            terms = []
            for line in lines:
                amount = parse_decimal(line.amount_kg, field_name=f"{line.name}燃料量")
                heat = parse_decimal(line.low_heat_kj_per_kg, field_name=f"{line.name}低位发热量")
                if amount < 0 or heat <= 0: raise ValueError("燃料量须非负且低位发热量须大于0")
                terms.append(Expression(op="multiply", args=[Expression(op="constant", value=amount), Expression(op="constant", value=heat)], label=line.name))
            values["internal.fuel_heat_kj"] = self.engine.expressions.evaluate(Expression(op="sum", args=terms), EvaluationContext({}, {}), trace, label="逐燃料原始热量合计 Σ(m_i×Q_idw)")
        except (ValueError, ArithmeticError) as exc: errors["internal.fuel_heat_kj"] = str(exc)

    def _allocations(self, request, definitions, values, errors, trace):
        allocations = request.cement_details.shared_allocations if request.cement_details else []
        seen = set()
        for allocation in allocations:
            key = allocation.target_input_key
            try:
                if allocation.allocation_id in seen: raise ValueError("同一共用量重复分摊")
                seen.add(allocation.allocation_id)
                if key not in ALLOCATION_TARGETS[allocation.product]: raise ValueError("共用系统产品或统计边界不明确，不能自动分摊")
                if key not in MODE_INPUT_KEYS[values.get("production_mode")]: raise ValueError("分摊目标不适用当前生产模式")
                if allocation.unit != definitions[key].unit: raise ValueError("共用量单位与目标统计项不一致")
                if values.get("production_line_id") != allocation.target_line_id: raise ValueError("分摊目标生产线与评价不一致")
                amount = parse_decimal(allocation.original_amount, field_name="原始共用量")
                productions = {k:parse_decimal(v, field_name="参与线产品产量") for k,v in allocation.line_production_t.items()}
                if amount < 0 or not productions or any(x <= 0 for x in productions.values()): raise ValueError("共用量须非负，参与线产量须大于0")
                if allocation.target_line_id not in productions: raise ValueError("参与线缺少本线")
                production_key = "clinker_production_t" if allocation.product == "clinker" else "cement_production_t"
                if productions[allocation.target_line_id] != values.get(production_key):
                    raise ValueError("分摊本线产品产量与本次评价对应产品产量不一致")
                denominator = sum(productions.values(), Decimal(0))
                allocated = {}
                for line_id, production in productions.items():
                    formula = Expression(op="divide", args=[Expression(op="multiply", args=[Expression(op="constant", value=amount),Expression(op="constant", value=production)]),Expression(op="constant", value=denominator)])
                    allocated[line_id] = self.engine.expressions.evaluate(formula, EvaluationContext({}, {}), trace, label=f"共用系统{allocation.allocation_id}→{line_id}按产品产量分摊")
                residual = amount - sum(allocated.values(), Decimal(0))
                trace.append(CalculationStep(sequence=len(trace)+1, label="分摊审计：原量、分母、残差（精度28；不调整末线）", operation="allocation_audit", expression=f"original={amount}; denominator={denominator}; productions={productions}; allocated={allocated}; residual={residual}; source={allocation.source_note or '未填'}", value=residual, unit=allocation.unit))
                values[key] = values.get(key, Decimal(0)) + allocated[allocation.target_line_id]
            except (ValueError, ArithmeticError) as exc:
                errors[key] = f"共用系统分摊：{exc}"
                # Allocation structure belongs to the whole submitted record.
                # Preserve independent previews while forbidding a formal save.
                errors["production_line_id"] = f"共用系统分摊：{exc}"
