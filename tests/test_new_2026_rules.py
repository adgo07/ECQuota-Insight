from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from uebench.domain.engine import EvaluationEngine
from uebench.domain.models import EnergyLine, EvaluationRequest, InputMode, InputValue, ProductionLine, PublicationStatus, StandardDefinition


ROOT = Path(__file__).resolve().parents[1] / "data" / "definitions"


def load(number: str) -> StandardDefinition:
    for path in ROOT.glob("*.json"):
        definition = StandardDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        if definition.number == number:
            return definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
    raise AssertionError(number)


def direct_request(standard: StandardDefinition, product_id: str, values: dict[str, object]) -> EvaluationRequest:
    product = next(item for item in standard.products if item.id == product_id)
    definitions = {item.key: item for indicator in product.indicators for item in indicator.input_definitions}
    inputs = {key: InputValue(value=values.get(key, "0"), unit=item.unit) for key, item in definitions.items()}
    return EvaluationRequest(
        evaluation_date=max(standard.effective_date, date(2027, 1, 1)),
        standard_id=standard.id,
        product_id=product_id,
        input_mode=InputMode.DIRECT,
        inputs=inputs,
    )


def test_gb47834_efficiency_uses_gte_and_standard_rounding_places() -> None:
    standard = load("GB 47834-2026")
    product = standard.products[0]
    indicator = product.indicators[0]
    assert indicator.comparison.value == "gte"
    assert indicator.display_places == 1
    result = EvaluationEngine().evaluate(
        standard,
        direct_request(standard, product.id, {indicator.direct_input_key: "24.0"}),
    ).results[0]
    assert result.grade.value == "LEVEL_1"


def test_gb47834_limit_indicators_apply_same_limit_to_all_grades() -> None:
    standard = load("GB 47834-2026")
    indicator = standard.products[0].indicators[1]
    assert [str(getattr(indicator.thresholds, f"level_{n}").value) for n in (1, 2, 3)] == ["8.6", "8.6", "8.6"]


def test_gb47835_detail_mode_computes_per_unit_value() -> None:
    standard = load("GB 47835-2026")
    product = standard.products[0]
    indicator = product.indicators[0]
    request = direct_request(standard, product.id, {})
    request = request.model_copy(update={
        "input_mode": InputMode.DETAIL,
        "inputs": {},
        "energy_lines": [EnergyLine(
            line_id="e1", energy_name="电力", direction="input", amount="100", unit="kWh",
            standard_coal_coefficient="0.1229", coefficient_unit="kgce/kWh", allocation_ratio="1",
        )],
        "production_lines": [ProductionLine(
            line_id="p1", product_name="硅单晶", quantity="10", unit="kg", conversion_factor="1", qualified=True,
        )],
    })
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("1.229")
    assert result.grade.value == "LEVEL_1"
