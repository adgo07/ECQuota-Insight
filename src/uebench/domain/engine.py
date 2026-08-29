from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import uuid4

from .models import (
    CalculationStep,
    ComparisonDirection,
    Condition,
    DataType,
    EvaluationRequest,
    EvaluationResult,
    Expression,
    Grade,
    IndicatorDefinition,
    IndicatorResult,
    InputDefinition,
    InputMode,
    PublicationStatus,
    Scalar,
    StandardDefinition,
    parse_decimal,
)


class EvaluationValidationError(ValueError):
    """The request cannot be formally evaluated."""


class MissingInputError(EvaluationValidationError):
    pass


class RuleEvaluationError(EvaluationValidationError):
    pass


class EvaluationContext:
    def __init__(
        self,
        values: dict[str, Scalar],
        units: dict[str, str | None],
        pre_steps: list[CalculationStep] | None = None,
    ) -> None:
        self.values = values
        self.units = units
        self.pre_steps = pre_steps or []

    def require(self, key: str) -> Scalar:
        if key not in self.values or self.values[key] is None or self.values[key] == "":
            raise MissingInputError(f"缺少输入：{key}")
        return self.values[key]


class ConditionEvaluator:
    @staticmethod
    def _equal(left: Scalar, right: Scalar) -> bool:
        """Compare numeric conditions without relying on JSON string typing."""
        numeric_types = (Decimal, int)
        if (
            isinstance(left, numeric_types)
            and not isinstance(left, bool)
            and isinstance(right, (numeric_types, str))
            and not isinstance(right, bool)
        ):
            try:
                return parse_decimal(left, field_name="condition.left") == parse_decimal(
                    right, field_name="condition.right"
                )
            except (TypeError, ValueError):
                return False
        return left == right

    def evaluate(self, condition: Condition, context: EvaluationContext) -> bool:
        op = condition.op
        if op == "always":
            return True
        if op == "all":
            return all(self.evaluate(item, context) for item in condition.args)
        if op == "any":
            return any(self.evaluate(item, context) for item in condition.args)
        if op == "not":
            if len(condition.args) != 1:
                raise RuleEvaluationError("not 条件必须且只能有一个子条件")
            return not self.evaluate(condition.args[0], context)
        if not condition.field:
            raise RuleEvaluationError(f"条件 {op} 缺少 field")

        actual = context.require(condition.field)
        if op in {"eq", "ne", "in"}:
            if op == "eq":
                return self._equal(actual, condition.value)
            if op == "ne":
                return not self._equal(actual, condition.value)
            return any(self._equal(actual, candidate) for candidate in condition.values)

        actual_decimal = parse_decimal(actual, field_name=condition.field)
        if op in {"lt", "lte", "gt", "gte"}:
            expected = parse_decimal(condition.value, field_name=f"{condition.field}.condition")
            return {
                "lt": actual_decimal < expected,
                "lte": actual_decimal <= expected,
                "gt": actual_decimal > expected,
                "gte": actual_decimal >= expected,
            }[op]
        if op == "range":
            if condition.minimum is None or condition.maximum is None:
                raise RuleEvaluationError("range 条件必须包含 minimum 和 maximum")
            lower = actual_decimal >= condition.minimum if condition.include_minimum else actual_decimal > condition.minimum
            upper = actual_decimal <= condition.maximum if condition.include_maximum else actual_decimal < condition.maximum
            return lower and upper
        raise RuleEvaluationError(f"不支持的条件操作：{op}")


class ExpressionEvaluator:
    def __init__(self) -> None:
        self.conditions = ConditionEvaluator()

    def evaluate(
        self,
        expression: Expression,
        context: EvaluationContext,
        trace: list[CalculationStep],
        *,
        label: str | None = None,
    ) -> Decimal:
        op = expression.op
        step_label = label or expression.label or op

        if op == "constant":
            result = parse_decimal(expression.value, field_name=step_label)
            rendered = str(result)
        elif op == "input":
            if not expression.input_key:
                raise RuleEvaluationError("input 表达式缺少 input_key")
            result = parse_decimal(context.require(expression.input_key), field_name=expression.input_key)
            rendered = expression.input_key
        elif op in {"add", "subtract", "multiply", "divide", "sum", "min", "max"}:
            values = [self.evaluate(arg, context, trace) for arg in expression.args]
            if not values:
                raise RuleEvaluationError(f"{op} 表达式缺少参数")
            if op in {"add", "sum"}:
                result = sum(values, Decimal("0"))
                symbol = " + "
            elif op == "subtract":
                if len(values) != 2:
                    raise RuleEvaluationError("subtract 必须有两个参数")
                result = values[0] - values[1]
                symbol = " - "
            elif op == "multiply":
                result = Decimal("1")
                for value in values:
                    result *= value
                symbol = " × "
            elif op == "divide":
                if len(values) != 2:
                    raise RuleEvaluationError("divide 必须有两个参数")
                if values[1] == 0:
                    raise RuleEvaluationError("计算发生除零")
                result = values[0] / values[1]
                symbol = " ÷ "
            elif op == "min":
                result = min(values)
                symbol = ", "
            else:
                result = max(values)
                symbol = ", "
            rendered = symbol.join(str(value) for value in values)
        elif op == "negate":
            if len(expression.args) != 1:
                raise RuleEvaluationError("negate 必须有一个参数")
            value = self.evaluate(expression.args[0], context, trace)
            result = -value
            rendered = f"-({value})"
        elif op in {"piecewise", "lookup"}:
            candidates = expression.cases if op == "piecewise" else expression.rows
            selected = next((item for item in candidates if self.conditions.evaluate(item.condition, context)), None)
            if selected is None:
                if expression.default is None:
                    raise RuleEvaluationError(f"{op} 未找到匹配分支")
                result = self.evaluate(expression.default, context, trace)
                rendered = "default"
            else:
                result = self.evaluate(selected.expression, context, trace)
                rendered = selected.label or "matched"
        elif op == "energy_conversion":
            if len(expression.args) != 2:
                raise RuleEvaluationError("energy_conversion 必须是能源实物量 × 折标系数")
            amount = self.evaluate(expression.args[0], context, trace)
            coefficient = self.evaluate(expression.args[1], context, trace)
            result = amount * coefficient
            rendered = f"{amount} × {coefficient}"
        elif op == "per_unit":
            if len(expression.args) != 2:
                raise RuleEvaluationError("per_unit 必须是总能耗 ÷ 合格产品产量")
            energy = self.evaluate(expression.args[0], context, trace)
            production = self.evaluate(expression.args[1], context, trace)
            if production == 0:
                raise RuleEvaluationError("产品产量不能为零")
            result = energy / production
            rendered = f"{energy} ÷ {production}"
        elif op == "allocation":
            if len(expression.args) != 2:
                raise RuleEvaluationError("allocation 必须是共同能耗 × 分摊比例")
            common_energy = self.evaluate(expression.args[0], context, trace)
            ratio = self.evaluate(expression.args[1], context, trace)
            if ratio < 0 or ratio > 1:
                raise RuleEvaluationError("分摊比例必须在 0 到 1 之间")
            result = common_energy * ratio
            rendered = f"{common_energy} × {ratio}"
        else:
            raise RuleEvaluationError(f"不支持的表达式操作：{op}")

        if expression.round_places is not None:
            quantum = Decimal("1").scaleb(-expression.round_places)
            result = result.quantize(quantum, rounding=ROUND_HALF_UP)
            rendered = f"round({rendered}, {expression.round_places})"

        trace.append(
            CalculationStep(
                sequence=len(trace) + 1,
                label=step_label,
                operation=op,
                expression=rendered,
                value=result,
                unit=expression.unit,
            )
        )
        return result


class EvaluationEngine:
    def __init__(self) -> None:
        self.expressions = ExpressionEvaluator()
        self.conditions = ConditionEvaluator()

    def evaluate(self, standard: StandardDefinition, request: EvaluationRequest) -> EvaluationResult:
        if standard.publication_status is not PublicationStatus.PUBLISHED:
            raise EvaluationValidationError("只有 published 标准规则可以正式计算")
        if request.standard_id != standard.id:
            raise EvaluationValidationError("评价请求与标准 ID 不一致")
        if request.evaluation_date < standard.effective_date:
            raise EvaluationValidationError(
                f"评价日期 {request.evaluation_date} 早于标准实施日期 {standard.effective_date}"
            )
        product = next((item for item in standard.products if item.id == request.product_id), None)
        if product is None:
            raise EvaluationValidationError(f"标准中不存在产品/工序：{request.product_id}")

        definitions = {item.key: item for item in product.input_definitions}
        for indicator in product.indicators:
            definitions.update({item.key: item for item in indicator.input_definitions})
        try:
            values, units, pre_steps = self._validate_inputs(definitions, request)
        except EvaluationValidationError as exc:
            # Input-level failures (for example a wrong unit or an out-of-range
            # value) are part of the evaluated data quality result.  Preserve a
            # row for every indicator so the caller receives the fixed
            # INCOMPLETE enum instead of a partially computed or guessed grade.
            return self._incomplete_result(standard, request, product, str(exc))
        context = EvaluationContext(values, units, pre_steps)

        results = [
            self._evaluate_indicator(
                indicator,
                request.input_mode,
                context,
                product_input_definitions=product.input_definitions,
            )
            for indicator in product.indicators
        ]
        snapshot_sha256 = self._snapshot_sha256(standard)
        return EvaluationResult(
            evaluation_id=str(uuid4()),
            evaluated_at=datetime.now(timezone.utc),
            standard_id=standard.id,
            standard_number=standard.number,
            standard_title=standard.title,
            standard_version=standard.version,
            product_id=product.id,
            product_name=product.name,
            results=results,
            rule_snapshot_sha256=snapshot_sha256,
        )

    @staticmethod
    def _snapshot_sha256(standard: StandardDefinition) -> str:
        snapshot = standard.model_dump(mode="json")
        snapshot_bytes = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(snapshot_bytes).hexdigest()

    def _incomplete_result(
        self,
        standard: StandardDefinition,
        request: EvaluationRequest,
        product,
        warning: str,
    ) -> EvaluationResult:
        return EvaluationResult(
            evaluation_id=str(uuid4()),
            evaluated_at=datetime.now(timezone.utc),
            standard_id=standard.id,
            standard_number=standard.number,
            standard_title=standard.title,
            standard_version=standard.version,
            product_id=product.id,
            product_name=product.name,
            results=[
                IndicatorResult(
                    indicator_id=indicator.id,
                    indicator_name=indicator.name,
                    actual_value=None,
                    unit=indicator.unit,
                    grade=Grade.INCOMPLETE,
                    source_references=indicator.source_references,
                    warnings=[warning],
                )
                for indicator in product.indicators
            ],
            rule_snapshot_sha256=self._snapshot_sha256(standard),
            warnings=[warning],
        )

    def _validate_inputs(
        self, definitions: dict[str, InputDefinition], request: EvaluationRequest
    ) -> tuple[dict[str, Scalar], dict[str, str | None], list[CalculationStep]]:
        values: dict[str, Scalar] = {}
        units: dict[str, str | None] = {}
        pre_steps: list[CalculationStep] = []
        for key, supplied in request.inputs.items():
            definition = definitions.get(key)
            if definition is None:
                values[key] = supplied.value
                units[key] = supplied.unit
                continue
            if definition.unit and supplied.unit != definition.unit:
                raise EvaluationValidationError(
                    f"{definition.label} 单位应为 {definition.unit}，实际为 {supplied.unit or '空'}"
                )
            value: Scalar
            if definition.data_type is DataType.DECIMAL:
                value = parse_decimal(supplied.value, field_name=definition.label)
                if definition.minimum is not None and value < definition.minimum:
                    raise EvaluationValidationError(f"{definition.label} 小于允许最小值")
                if definition.maximum is not None and value > definition.maximum:
                    raise EvaluationValidationError(f"{definition.label} 大于允许最大值")
            elif definition.data_type is DataType.BOOLEAN:
                if not isinstance(supplied.value, bool):
                    raise EvaluationValidationError(f"{definition.label} 必须为布尔值")
                value = supplied.value
            else:
                value = str(supplied.value) if supplied.value is not None else None
                if definition.choices and value not in definition.choices:
                    raise EvaluationValidationError(f"{definition.label} 不在允许选项中")
            values[key] = value
            units[key] = supplied.unit
        if request.energy_lines:
            total_energy = Decimal("0")
            amount_totals: dict[str, Decimal] = {}
            category_amount_totals: dict[str, Decimal] = {}
            category_standard_coal_totals: dict[str, Decimal] = {}
            for line in request.energy_lines:
                coefficient_unit = line.coefficient_unit.strip()
                if "/" in coefficient_unit:
                    denominator = coefficient_unit.split("/", 1)[1].strip().strip("()")
                    if self._unit_key(denominator) != self._unit_key(line.unit):
                        raise EvaluationValidationError(
                            f"能源 {line.energy_name} 的实物量单位 {line.unit} 与折标系数分母 {denominator} 不一致"
                        )
                sign = Decimal("-1") if line.direction == "output" else Decimal("1")
                allocated_amount = line.amount * line.allocation_ratio * sign
                contribution = allocated_amount * line.standard_coal_coefficient
                total_energy += contribution
                unit_key = self._unit_key(line.unit)
                amount_totals[unit_key] = amount_totals.get(unit_key, Decimal("0")) + allocated_amount
                if line.category_key:
                    category_amount_totals[line.category_key] = (
                        category_amount_totals.get(line.category_key, Decimal("0")) + allocated_amount
                    )
                    category_standard_coal_totals[line.category_key] = (
                        category_standard_coal_totals.get(line.category_key, Decimal("0")) + contribution
                    )
                pre_steps.append(
                    CalculationStep(
                        sequence=len(pre_steps) + 1,
                        label=f"能源明细：{line.energy_name}",
                        operation="energy_line",
                        expression=(
                            f"{line.direction} {line.amount} {line.unit} × "
                            f"{line.standard_coal_coefficient} {line.coefficient_unit} × {line.allocation_ratio}"
                        ),
                        value=contribution,
                        unit="kgce",
                    )
                )
            values["energy.total_standard_coal"] = total_energy
            units["energy.total_standard_coal"] = "kgce"
            for unit_key, amount in amount_totals.items():
                key = f"energy.unit.{unit_key}.net_amount"
                values[key] = amount
                units[key] = unit_key
            for category_key, amount in category_amount_totals.items():
                key = f"energy.category.{category_key}.net_amount"
                values[key] = amount
                units[key] = None
            for category_key, amount in category_standard_coal_totals.items():
                key = f"energy.category.{category_key}.net_standard_coal"
                values[key] = amount
                units[key] = "kgce"
            pre_steps.append(
                CalculationStep(
                    sequence=len(pre_steps) + 1,
                    label="能源折标合计",
                    operation="sum",
                    expression="Σ能源输入折标量 - Σ能源输出折标量",
                    value=total_energy,
                    unit="kgce",
                )
            )
        if request.production_lines:
            total_production = Decimal("0")
            category_production_totals: dict[str, Decimal] = {}
            production_units = {self._unit_key(line.unit) for line in request.production_lines}
            if len(production_units) > 1:
                raise EvaluationValidationError("产量明细的单位不一致，不能直接合并折算产量")
            for line in request.production_lines:
                if not line.qualified:
                    continue
                contribution = line.quantity * line.conversion_factor
                total_production += contribution
                if line.category_key:
                    category_production_totals[line.category_key] = (
                        category_production_totals.get(line.category_key, Decimal("0")) + contribution
                    )
                pre_steps.append(
                    CalculationStep(
                        sequence=len(pre_steps) + 1,
                        label=f"产品产量：{line.product_name}",
                        operation="production_line",
                        expression=f"{line.quantity} {line.unit} × {line.conversion_factor}",
                        value=contribution,
                        unit=line.unit,
                    )
                )
            values["production.total_equivalent"] = total_production
            units["production.total_equivalent"] = request.production_lines[0].unit
            for category_key, quantity in category_production_totals.items():
                key = f"production.category.{category_key}.total_equivalent"
                values[key] = quantity
                units[key] = request.production_lines[0].unit
            pre_steps.append(
                CalculationStep(
                    sequence=len(pre_steps) + 1,
                    label="合格产品折算产量合计",
                    operation="sum",
                    expression="Σ合格产品产量 × 折算系数",
                    value=total_production,
                    unit=request.production_lines[0].unit,
                )
            )
        return values, units, pre_steps

    @staticmethod
    def _unit_key(unit: str) -> str:
        normalized = unit.strip().lower().replace("·", "").replace(" ", "")
        aliases = {
            "kw.h": "kWh",
            "kwh": "kWh",
            "千瓦时": "kWh",
            "m³": "m3",
            "立方米": "m3",
            "吨": "t",
            "千克": "kg",
        }
        return aliases.get(normalized, normalized.replace("/", "_per_"))

    def _evaluate_indicator(
        self,
        indicator: IndicatorDefinition,
        input_mode: InputMode,
        context: EvaluationContext,
        *,
        product_input_definitions: list[InputDefinition] | None = None,
    ) -> IndicatorResult:
        trace: list[CalculationStep] = [step.model_copy() for step in context.pre_steps]
        for sequence, step in enumerate(trace, start=1):
            step.sequence = sequence
        try:
            if not self.conditions.evaluate(indicator.applicability, context):
                return IndicatorResult(
                    indicator_id=indicator.id,
                    indicator_name=indicator.name,
                    actual_value=None,
                    unit=indicator.unit,
                    grade=Grade.NOT_APPLICABLE,
                    source_references=indicator.source_references,
                )

            # Product-level inputs apply to every indicator in that product.
            # Enforce them here (rather than only when a formula happens to
            # reference them) so a required condition cannot be silently
            # skipped in direct-entry mode.
            required_definitions: dict[str, InputDefinition] = {
                definition.key: definition for definition in (product_input_definitions or [])
            }
            required_definitions.update({definition.key: definition for definition in indicator.input_definitions})
            for definition in required_definitions.values():
                condition_met = (
                    definition.required_if is None
                    or self.conditions.evaluate(definition.required_if, context)
                )
                if definition.required and condition_met and input_mode in definition.modes:
                    context.require(definition.key)

            if input_mode is InputMode.DIRECT:
                actual = parse_decimal(context.require(indicator.direct_input_key), field_name=indicator.name)
                trace.append(
                    CalculationStep(
                        sequence=1,
                        label="直接录入实际值",
                        operation="input",
                        expression=indicator.direct_input_key,
                        value=actual,
                        unit=indicator.unit,
                    )
                )
            else:
                if indicator.detail_formula is None:
                    raise MissingInputError("该指标尚未配置明细计算公式")
                actual = self.expressions.evaluate(indicator.detail_formula, context, trace, label="计算实际值")

            base_thresholds = self._evaluate_threshold_set(
                indicator.base_thresholds or indicator.thresholds, context, trace, "修正前"
            )
            corrected_thresholds = self._evaluate_threshold_set(indicator.thresholds, context, trace, "修正后")
            grade = self._grade(actual, corrected_thresholds, indicator.comparison)
            return IndicatorResult(
                indicator_id=indicator.id,
                indicator_name=indicator.name,
                actual_value=actual,
                unit=indicator.unit,
                base_thresholds=base_thresholds,
                corrected_thresholds=corrected_thresholds,
                grade=grade,
                calculation_trace=trace,
                source_references=indicator.source_references,
            )
        except (MissingInputError, RuleEvaluationError, ValueError) as exc:
            return IndicatorResult(
                indicator_id=indicator.id,
                indicator_name=indicator.name,
                actual_value=None,
                unit=indicator.unit,
                grade=Grade.INCOMPLETE,
                calculation_trace=trace,
                source_references=indicator.source_references,
                warnings=[str(exc)],
            )

    @staticmethod
    def _grade(
        actual: Decimal, thresholds: dict[str, Decimal], comparison: ComparisonDirection
    ) -> Grade:
        predicate = (lambda left, right: left <= right) if comparison is ComparisonDirection.LTE else (
            lambda left, right: left >= right
        )
        for key, grade in (
            ("LEVEL_1", Grade.LEVEL_1),
            ("LEVEL_2", Grade.LEVEL_2),
            ("LEVEL_3", Grade.LEVEL_3),
        ):
            threshold = thresholds.get(key)
            if threshold is not None and predicate(actual, threshold):
                return grade
        return Grade.NOT_QUALIFIED

    def _evaluate_threshold_set(
        self,
        threshold_set,
        context: EvaluationContext,
        trace: list[CalculationStep],
        prefix: str,
    ) -> dict[str, Decimal]:
        thresholds: dict[str, Decimal] = {}
        for key, label, expression in (
            ("LEVEL_1", "1级限额", threshold_set.level_1),
            ("LEVEL_2", "2级限额", threshold_set.level_2),
            ("LEVEL_3", "3级限额", threshold_set.level_3),
        ):
            if expression is not None:
                thresholds[key] = self.expressions.evaluate(expression, context, trace, label=f"{prefix}{label}")
        return thresholds
