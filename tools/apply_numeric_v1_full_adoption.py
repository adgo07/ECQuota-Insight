from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


# --- Engine: remove legacy global ROUND6, declare/consume project profile, isolate ambient context.
path = ROOT / "src/uebench/domain/engine.py"
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from decimal import Decimal, ROUND_HALF_UP\n",
    "from decimal import Decimal, ROUND_HALF_UP, localcontext\n",
    "engine decimal import",
)
legacy_block = '''# Legacy compatibility for standards that have not yet completed an
# independent standard-source numeric migration.  GB 29446 does NOT use this
# policy after QZC-N01-A.
_THRESHOLD_COMPARISON_QUANTUM = Decimal("0.000001")
LEGACY_ROUND6_NUMERIC_BEHAVIOR = "ecquota-legacy-round6-v1"
GB29446_NUMERIC_BEHAVIOR_VERSION = "ecquota-gb29446-full-value-v2"


def _round_threshold_value(value: Decimal) -> Decimal:
    """Legacy ECQuota comparison rule retained only for unmigrated standards."""
    return value.quantize(_THRESHOLD_COMPARISON_QUANTUM, rounding=ROUND_HALF_UP)


'''
profile_import = '''from .numeric import (
    ECQUOTA_CALCULATOR_VERSION,
    ECQUOTA_DECIMAL_FULL_VALUE_V1,
    ECQUOTA_FULL_VALUE_BEHAVIOR_VERSION,
    GB29446_NUMERIC_BEHAVIOR_VERSION,
    NumericProfile,
)


'''
text = replace_once(text, legacy_block, profile_import, "legacy ROUND6 block")
text = replace_once(
    text,
    '''class EvaluationEngine:
    def __init__(self) -> None:
        self.expressions = ExpressionEvaluator()
        self.conditions = ConditionEvaluator()

    def evaluate(
        self,
        standard: StandardDefinition,
        request: EvaluationRequest,
        *,
        allow_pre_effective: bool = False,
    ) -> EvaluationResult:
        if standard.publication_status is not PublicationStatus.PUBLISHED:
''',
    '''class EvaluationEngine:
    def __init__(self, numeric_profile: NumericProfile = ECQUOTA_DECIMAL_FULL_VALUE_V1) -> None:
        self.numeric_profile = numeric_profile
        self.expressions = ExpressionEvaluator()
        self.conditions = ConditionEvaluator()

    def evaluate(
        self,
        standard: StandardDefinition,
        request: EvaluationRequest,
        *,
        allow_pre_effective: bool = False,
    ) -> EvaluationResult:
        # The project Profile owns authoritative finite-precision arithmetic.
        # A caller's ambient Decimal context must not change a governed result.
        with localcontext(self.numeric_profile.decimal_context()):
            return self._evaluate_authoritative(
                standard,
                request,
                allow_pre_effective=allow_pre_effective,
            )

    def _evaluate_authoritative(
        self,
        standard: StandardDefinition,
        request: EvaluationRequest,
        *,
        allow_pre_effective: bool = False,
    ) -> EvaluationResult:
        if standard.publication_status is not PublicationStatus.PUBLISHED:
''',
    "engine profile wrapper",
)
# Both normal and incomplete results receive current Numeric traceability while legacy persisted JSON remains loadable.
trace_fields = '''            rule_revision=standard.rule_revision,
            numeric_contract_version=self.numeric_profile.numeric_contract_version,
            numeric_profile_id=self.numeric_profile.numeric_profile_id,
            calculator_version=ECQUOTA_CALCULATOR_VERSION,
            numeric_behavior_version=(
                GB29446_NUMERIC_BEHAVIOR_VERSION
                if standard.id == "gb-29446-2019"
                else ECQUOTA_FULL_VALUE_BEHAVIOR_VERSION
            ),
'''
count = text.count("            rule_revision=standard.rule_revision,\n")
if count != 2:
    raise RuntimeError(f"evaluation result traceability insertion: expected 2, got {count}")
text = text.replace("            rule_revision=standard.rule_revision,\n", trace_fields)
text = replace_once(
    text,
    '''        trace: list[CalculationStep] = [step.model_copy() for step in context.pre_steps]
        is_gb29446 = standard_id == "gb-29446-2019"
''',
    '''        trace: list[CalculationStep] = [step.model_copy() for step in context.pre_steps]
        is_gb29446 = standard_id == "gb-29446-2019"
        numeric_behavior_version = (
            GB29446_NUMERIC_BEHAVIOR_VERSION
            if is_gb29446
            else ECQUOTA_FULL_VALUE_BEHAVIOR_VERSION
        )
''',
    "indicator behavior marker",
)
text = replace_once(
    text,
    '''            grade = self._grade(
                actual,
                corrected_thresholds,
                indicator.comparison,
                trace=trace if is_gb29446 else None,
                unit=indicator.unit,
                full_value=is_gb29446,
            )
''',
    '''            grade = self._grade(
                actual,
                corrected_thresholds,
                indicator.comparison,
                trace=trace,
                unit=indicator.unit,
                numeric_behavior_version=numeric_behavior_version,
            )
''',
    "grade call",
)
text = replace_once(
    text,
    '''                    rounded_actual = _round_threshold_value(actual)
                    rounded_limit = _round_threshold_value(compliance_limit)
                    predicate = (
                        rounded_actual <= rounded_limit
                        if indicator.comparison is ComparisonDirection.LTE
                        else rounded_actual >= rounded_limit
                    )
                    compliance_requirement = compliance_case.requirement
                    compliance_result = "符合" if predicate else "不符合"
                    trace.append(
                        CalculationStep(
                            sequence=len(trace) + 1,
                            label="企业执行要求合规判定",
                            operation="compliance",
                            expression=(
                                f"ROUND({actual}, 6) {indicator.comparison.value} "
                                f"ROUND({compliance_limit}, 6)"
                            ),
                            value=compliance_result,
                            unit=indicator.unit,
                        )
                    )
''',
    '''                    predicate = (
                        actual <= compliance_limit
                        if indicator.comparison is ComparisonDirection.LTE
                        else actual >= compliance_limit
                    )
                    compliance_requirement = compliance_case.requirement
                    compliance_result = "符合" if predicate else "不符合"
                    relation = "<=" if indicator.comparison is ComparisonDirection.LTE else ">="
                    trace.append(
                        CalculationStep(
                            sequence=len(trace) + 1,
                            label="企业执行要求合规判定",
                            operation="compliance",
                            expression=(
                                f"numeric_behavior={numeric_behavior_version}; "
                                f"{_format_comparison_operand(actual)} {relation} "
                                f"{_format_comparison_operand(compliance_limit)}"
                            ),
                            value=compliance_result,
                            unit=indicator.unit,
                        )
                    )
''',
    "compliance full-value",
)
grade_pattern = re.compile(
    r'''    @staticmethod\n    def _grade\(.*?\n        return Grade\.NOT_QUALIFIED\n\n    def _evaluate_threshold_set''',
    re.S,
)
new_grade = '''    @staticmethod
    def _grade(
        actual: Decimal,
        thresholds: dict[str, Decimal],
        comparison: ComparisonDirection,
        *,
        trace: list[CalculationStep] | None = None,
        unit: str | None = None,
        numeric_behavior_version: str = ECQUOTA_FULL_VALUE_BEHAVIOR_VERSION,
    ) -> Grade:
        predicate = (lambda left, right: left <= right) if comparison is ComparisonDirection.LTE else (
            lambda left, right: left >= right
        )
        relation = "<=" if comparison is ComparisonDirection.LTE else ">="

        for key, grade in (
            ("LEVEL_1", Grade.LEVEL_1),
            ("LEVEL_2", Grade.LEVEL_2),
            ("LEVEL_3", Grade.LEVEL_3),
        ):
            threshold = thresholds.get(key)
            if threshold is None:
                continue
            matched = predicate(actual, threshold)
            if trace is not None:
                trace.append(
                    CalculationStep(
                        sequence=len(trace) + 1,
                        label=f"{grade.value}等级判定比较",
                        operation="grade_comparison",
                        expression=(
                            f"numeric_behavior={numeric_behavior_version}; "
                            f"{_format_comparison_operand(actual)} {relation} "
                            f"{_format_comparison_operand(threshold)}"
                        ),
                        value=matched,
                        unit=unit,
                    )
                )
            if matched:
                return grade
        return Grade.NOT_QUALIFIED

    def _evaluate_threshold_set'''
text, n = grade_pattern.subn(new_grade, text)
if n != 1:
    raise RuntimeError(f"grade function replacement: expected 1, got {n}")
# Explicit Rule rounding remains possible, but only with frozen-contract metadata.
text = replace_once(
    text,
    '''        if expression.round_places is not None:
            quantum = Decimal("1").scaleb(-expression.round_places)
            result = result.quantize(quantum, rounding=ROUND_HALF_UP)
            rendered = f"round({rendered}, {expression.round_places})"
''',
    '''        if expression.round_places is not None:
            if expression.rounding is None:
                raise RuleEvaluationError("显式修约缺少 rounding 元数据")
            if expression.rounding.mode != "ROUND_HALF_UP":
                raise RuleEvaluationError(f"暂不支持显式修约模式：{expression.rounding.mode}")
            quantum = Decimal("1").scaleb(-expression.round_places)
            result = result.quantize(quantum, rounding=ROUND_HALF_UP)
            rendered = (
                f"explicit_round({rendered}, {expression.round_places}, "
                f"{expression.rounding.mode}, source={expression.rounding.source})"
            )
''',
    "explicit rule rounding",
)
path.write_text(text, encoding="utf-8")


# --- Models: explicit rounding metadata + backward-compatible result traceability.
path = ROOT / "src/uebench/domain/models.py"
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''class LookupRow(StrictModel):
    condition: Condition
    expression: Expression
    label: str | None = None


class Expression(StrictModel):
''',
    '''class LookupRow(StrictModel):
    condition: Condition
    expression: Expression
    label: str | None = None


class ExplicitRounding(StrictModel):
    stage: Literal["intermediate", "comparison", "other"]
    mode: Literal["ROUND_HALF_UP"]
    purpose: Literal["business-explicit"]
    source: str = Field(min_length=1)


class Expression(StrictModel):
''',
    "ExplicitRounding model",
)
text = replace_once(
    text,
    '''    round_places: int | None = Field(default=None, ge=0, le=12)

    @field_validator("value", mode="before")
''',
    '''    round_places: int | None = Field(default=None, ge=0, le=12)
    rounding: ExplicitRounding | None = None

    @field_validator("value", mode="before")
''',
    "Expression rounding field",
)
text = replace_once(
    text,
    '''    def reject_float(cls, value: Any) -> Any:
        return _reject_float(value)


class CalculatedDisplayValue(StrictModel):
''',
    '''    def reject_float(cls, value: Any) -> Any:
        return _reject_float(value)

    @model_validator(mode="after")
    def validate_explicit_rounding(self) -> Expression:
        if self.round_places is None and self.rounding is not None:
            raise ValueError("rounding 元数据只能与 round_places 一起声明")
        if self.round_places is not None and self.rounding is None:
            raise ValueError("round_places 必须声明 stage/mode/purpose/source")
        return self


class CalculatedDisplayValue(StrictModel):
''',
    "Expression rounding validation",
)
text = replace_once(
    text,
    '''    rule_revision: int = Field(default=1, ge=1)
    product_name: str
''',
    '''    rule_revision: int = Field(default=1, ge=1)
    numeric_contract_version: str | None = None
    numeric_profile_id: str | None = None
    calculator_version: str | None = None
    numeric_behavior_version: str | None = None
    product_name: str
''',
    "EvaluationResult numeric traceability",
)
path.write_text(text, encoding="utf-8")


# --- Application service: production declaration is explicit at the authoritative scope boundary.
path = ROOT / "src/uebench/application/services.py"
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from uebench.domain.engine import EvaluationEngine\n",
    "from uebench.domain.engine import EvaluationEngine\nfrom uebench.domain.numeric import ECQUOTA_DECIMAL_FULL_VALUE_V1\n",
    "service profile import",
)
text = replace_once(
    text,
    "        self.engine = engine or EvaluationEngine()\n",
    "        self.engine = engine or EvaluationEngine(ECQUOTA_DECIMAL_FULL_VALUE_V1)\n",
    "service profile declaration",
)
path.write_text(text, encoding="utf-8")


# --- Existing unit test: the dormant explicit-rounding capability must now provide authority metadata.
path = ROOT / "tests/test_engine.py"
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''                    round_places=3,
''',
    '''                    round_places=3,
                    rounding={
                        "stage": "intermediate",
                        "mode": "ROUND_HALF_UP",
                        "purpose": "business-explicit",
                        "source": "synthetic test rule: explicit 3-place rounding",
                    },
''',
    "explicit rounding test metadata",
)
path.write_text(text, encoding="utf-8")


# --- Dev dependency: Frozen JSON Schema validation is part of the executable adoption suite.
path = ROOT / "pyproject.toml"
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''  "hypothesis>=6.122,<7",
]''',
    '''  "hypothesis>=6.122,<7",
  "jsonschema>=4.25,<5",
]''',
    "jsonschema dev dependency",
)
path.write_text(text, encoding="utf-8")

print("Numeric v1 full-adoption production patch applied successfully.")
