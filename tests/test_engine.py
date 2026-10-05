from datetime import date
from decimal import Decimal

import pytest

from uebench.domain.engine import EvaluationEngine, EvaluationValidationError, ExpressionEvaluator
from uebench.domain.models import (
    ComparisonDirection,
    Condition,
    DataType,
    EnergyLine,
    EvaluationRequest,
    Expression,
    Grade,
    IndicatorDefinition,
    InputDefinition,
    InputMode,
    InputValue,
    ProductDefinition,
    ProductionLine,
    PublicationStatus,
    SourceReference,
    StandardDefinition,
    ThresholdSet,
)


SOURCE = SourceReference(
    standard_number="GB 00000-2026",
    source_file="GB 00000-2026.pdf",
    source_sha256="a" * 64,
    page=5,
    table="表1",
)


def constant(value: str) -> Expression:
    return Expression(op="constant", value=value)


def make_standard(
    *,
    comparison: ComparisonDirection = ComparisonDirection.LTE,
    standard_id: str | None = None,
    standard_number: str | None = None,
) -> StandardDefinition:
    """一个最小可用标准定义。

    ``standard_id`` / ``standard_number`` 默认沿用测试占位标准（``gb-00000-2026``）。
    需要落在正式评价范围内的场景（例如 ``gb-29446-2019``）可以显式覆盖：此时
    id、number 与原文文件名三者保持一致，定义内部引用仍然自洽。
    """
    number = standard_number or SOURCE.standard_number
    identifier = standard_id or "gb-00000-2026"
    # 标准版本年份必须与标准编号末段一致（``StandardDefinition`` 自身会校验）。
    version = number.rsplit("-", 1)[-1]
    source = SOURCE.model_copy(update={"standard_number": number})
    indicator = IndicatorDefinition(
        id="energy",
        name="单位产品能耗",
        unit="kgce/t",
        comparison=comparison,
        direct_input_key="actual",
        input_definitions=[
            InputDefinition(key="actual", label="实际值", unit="kgce/t", modes=[InputMode.DIRECT])
        ],
        detail_formula=Expression(
            op="per_unit",
            args=[Expression(op="input", input_key="total"), Expression(op="input", input_key="production")],
        ),
        thresholds=ThresholdSet(level_1=constant("10"), level_2=constant("20"), level_3=constant("30")),
        source_references=[source],
    )
    product = ProductDefinition(
        id="product",
        name="测试产品",
        input_definitions=[
            InputDefinition(key="total", label="总能耗", unit="kgce", modes=[InputMode.DETAIL]),
            InputDefinition(
                key="production",
                label="产量",
                unit="t",
                minimum=Decimal("0"),
                modes=[InputMode.DETAIL],
            ),
        ],
        indicators=[indicator],
    )
    return StandardDefinition(
        id=identifier,
        number=number,
        title="测试标准",
        version=version,
        publication_status=PublicationStatus.PUBLISHED,
        publication_date=date(2026, 1, 1),
        effective_date=date(2026, 2, 1),
        source_file=source.source_file,
        source_sha256=SOURCE.source_sha256,
        products=[product],
    )


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        ("10", Grade.LEVEL_1),
        ("10.0001", Grade.LEVEL_2),
        ("20", Grade.LEVEL_2),
        ("20.0001", Grade.LEVEL_3),
        ("30", Grade.LEVEL_3),
        ("30.0001", Grade.NOT_QUALIFIED),
    ],
)
def test_lte_grade_boundaries(actual: str, expected: Grade) -> None:
    request = EvaluationRequest(
        evaluation_date=date(2026, 2, 1),
        standard_id="gb-00000-2026",
        product_id="product",
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value=actual, unit="kgce/t")},
    )
    result = EvaluationEngine().evaluate(make_standard(), request)
    assert result.results[0].grade is expected


def test_detail_formula_matches_direct_result() -> None:
    request = EvaluationRequest(
        evaluation_date=date(2026, 2, 2),
        standard_id="gb-00000-2026",
        product_id="product",
        input_mode=InputMode.DETAIL,
        inputs={
            "total": InputValue(value="150", unit="kgce"),
            "production": InputValue(value="10", unit="t"),
        },
    )
    result = EvaluationEngine().evaluate(make_standard(), request)
    assert result.results[0].actual_value == Decimal("15")
    assert result.results[0].grade is Grade.LEVEL_2
    assert result.results[0].calculation_trace


def test_detail_formula_can_use_energy_and_production_ledgers() -> None:
    standard = make_standard()
    indicator = standard.products[0].indicators[0]
    # The fixture's default product inputs are required for its original
    # formula; this variant intentionally uses the generated ledger keys
    # instead, so those alternative raw inputs are optional.
    for definition in standard.products[0].input_definitions:
        definition.required = False
    indicator.detail_formula = Expression(
        op="per_unit",
        args=[
            Expression(op="input", input_key="energy.total_standard_coal"),
            Expression(op="input", input_key="production.total_equivalent"),
        ],
    )
    request = EvaluationRequest(
        evaluation_date=date(2026, 2, 2),
        standard_id=standard.id,
        product_id="product",
        input_mode=InputMode.DETAIL,
        inputs={},
        energy_lines=[
            EnergyLine(
                line_id="e1",
                energy_name="电力",
                amount="100",
                unit="kWh",
                standard_coal_coefficient="0.1229",
                coefficient_unit="kgce/kWh",
            ),
            EnergyLine(
                line_id="e2",
                energy_name="外供蒸汽",
                direction="output",
                amount="2.29",
                unit="t",
                standard_coal_coefficient="1",
                coefficient_unit="kgce/t",
            ),
        ],
        production_lines=[
            ProductionLine(line_id="p1", product_name="合格品", quantity="1", unit="t")
        ],
    )
    result = EvaluationEngine().evaluate(standard, request)
    assert result.results[0].actual_value == Decimal("10.0000")
    assert result.results[0].grade is Grade.LEVEL_1
    assert any(step.operation == "energy_line" for step in result.results[0].calculation_trace)


def test_before_effective_date_is_blocked() -> None:
    request = EvaluationRequest(
        evaluation_date=date(2026, 1, 31),
        standard_id="gb-00000-2026",
        product_id="product",
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="10", unit="kgce/t")},
    )
    with pytest.raises(EvaluationValidationError, match="早于标准实施日期"):
        EvaluationEngine().evaluate(make_standard(), request)


def test_reviewed_rules_are_blocked_until_published() -> None:
    standard = make_standard().model_copy(update={"publication_status": PublicationStatus.REVIEWED})
    request = EvaluationRequest(
        evaluation_date=date(2026, 2, 2),
        standard_id=standard.id,
        product_id="product",
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="10", unit="kgce/t")},
    )
    with pytest.raises(EvaluationValidationError, match="只有 published"):
        EvaluationEngine().evaluate(standard, request)


def test_wrong_unit_returns_incomplete_results() -> None:
    request = EvaluationRequest(
        evaluation_date=date(2026, 2, 2),
        standard_id="gb-00000-2026",
        product_id="product",
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="10", unit="kWh/t")},
    )
    result = EvaluationEngine().evaluate(make_standard(), request)
    assert result.results[0].grade is Grade.INCOMPLETE
    assert "单位应为" in result.results[0].warnings[0]


def test_required_product_level_input_is_not_skipped_in_direct_mode() -> None:
    standard = make_standard()
    standard.products[0].input_definitions.append(
        InputDefinition(key="mandatory-condition", label="必填条件", unit="1", modes=[InputMode.DIRECT])
    )
    request = EvaluationRequest(
        evaluation_date=date(2026, 2, 2),
        standard_id=standard.id,
        product_id="product",
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="10", unit="kgce/t")},
    )
    result = EvaluationEngine().evaluate(standard, request)
    assert result.results[0].grade is Grade.INCOMPLETE
    assert "mandatory-condition" in result.results[0].warnings[0]


def test_zero_production_yields_incomplete() -> None:
    request = EvaluationRequest(
        evaluation_date=date(2026, 2, 2),
        standard_id="gb-00000-2026",
        product_id="product",
        input_mode=InputMode.DETAIL,
        inputs={
            "total": InputValue(value="150", unit="kgce"),
            "production": InputValue(value="0", unit="t"),
        },
    )
    result = EvaluationEngine().evaluate(make_standard(), request)
    assert result.results[0].grade is Grade.INCOMPLETE
    assert "产量不能为零" in result.results[0].warnings[0]


def test_energy_coefficient_denominator_mismatch_returns_incomplete() -> None:
    standard = make_standard()
    indicator = standard.products[0].indicators[0]
    indicator.detail_formula = Expression(
        op="per_unit",
        args=[
            Expression(op="input", input_key="energy.total_standard_coal"),
            Expression(op="input", input_key="production.total_equivalent"),
        ],
    )
    request = EvaluationRequest(
        evaluation_date=date(2026, 2, 2),
        standard_id=standard.id,
        product_id="product",
        input_mode=InputMode.DETAIL,
        inputs={},
        energy_lines=[
            EnergyLine(
                line_id="e1",
                energy_name="电力",
                amount="100",
                unit="kWh",
                standard_coal_coefficient="0.1229",
                coefficient_unit="kgce/t",
            )
        ],
        production_lines=[ProductionLine(line_id="p1", product_name="合格品", quantity="1", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert "分母" in result.warnings[0]


def test_mixed_production_units_return_incomplete() -> None:
    standard = make_standard()
    indicator = standard.products[0].indicators[0]
    indicator.detail_formula = Expression(
        op="per_unit",
        args=[
            Expression(op="input", input_key="energy.total_standard_coal"),
            Expression(op="input", input_key="production.total_equivalent"),
        ],
    )
    request = EvaluationRequest(
        evaluation_date=date(2026, 2, 2),
        standard_id=standard.id,
        product_id="product",
        input_mode=InputMode.DETAIL,
        inputs={},
        energy_lines=[EnergyLine(
            line_id="e1", energy_name="燃料", amount="100", unit="kgce",
            standard_coal_coefficient="1", coefficient_unit="kgce/kgce",
        )],
        production_lines=[
            ProductionLine(line_id="p1", product_name="产品A", quantity="1", unit="t"),
            ProductionLine(line_id="p2", product_name="产品B", quantity="1", unit="kg"),
        ],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert "单位不一致" in result.warnings[0]


def test_piecewise_and_decimal_rounding() -> None:
    expression = Expression(
        op="piecewise",
        cases=[
            {
                "condition": Condition(op="lte", field="temperature", value="0"),
                "expression": constant("1.000"),
                "label": "低温",
            },
            {
                "condition": Condition(op="gt", field="temperature", value="0"),
                "expression": Expression(
                    op="add",
                    args=[constant("1"), Expression(op="input", input_key="delta")],
                    round_places=3,
                    rounding={
                        "stage": "intermediate",
                        "mode": "ROUND_HALF_UP",
                        "purpose": "business-explicit",
                        "source": "synthetic test rule: explicit 3-place rounding",
                    },
                ),
                "label": "高温",
            },
        ],
    )
    context = type("Context", (), {"require": lambda self, key: {"temperature": "5", "delta": "0.0055"}[key]})()
    trace = []
    result = ExpressionEvaluator().evaluate(expression, context, trace)
    assert result == Decimal("1.006")


def test_numeric_string_condition_is_compared_as_decimal() -> None:
    expression = Expression(
        op="piecewise",
        cases=[
            {
                "condition": Condition(op="eq", field="grade", value="1"),
                "expression": constant("10"),
            }
        ],
        default=constant("20"),
    )
    context = type("Context", (), {"require": lambda self, key: {"grade": Decimal("1.0")}[key]})()
    assert ExpressionEvaluator().evaluate(expression, context, []) == Decimal("10")


def test_float_is_rejected() -> None:
    with pytest.raises((TypeError, ValueError)):
        InputValue(value=1.5, unit="kgce/t")
