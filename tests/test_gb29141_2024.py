from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from uebench.domain.engine import EvaluationEngine
from uebench.domain.models import EnergyLine, EvaluationRequest, InputMode, InputValue, ProductionLine, StandardDefinition


def load() -> StandardDefinition:
    return StandardDefinition.model_validate_json(Path("data/definitions/gb-29141-2024.json").read_text(encoding="utf-8"))


def request(standard, product, indicator, *, actual: str, acid_type: str | None = None, heat_recovery: bool | None = None) -> EvaluationRequest:
    inputs = {indicator.direct_input_key: InputValue(value=actual, unit=indicator.unit)}
    if acid_type is not None:
        inputs["acid.product_type"] = InputValue(value=acid_type)
    if heat_recovery is not None:
        inputs["sulfur.has_low_temperature_heat_recovery"] = InputValue(value=heat_recovery)
    return EvaluationRequest(evaluation_date=date(2026, 8, 30), standard_id=standard.id, product_id=product.id, input_mode=InputMode.DIRECT, inputs=inputs)


def test_gb29141_replacement_metadata_and_rows() -> None:
    standard = load()
    assert standard.lifecycle_status.value == "active"
    assert standard.effective_date == date(2025, 6, 1)
    assert set(standard.supersedes) == {"GB 29141-2012", "GB 29437-2012", "GB 29441-2012"}
    assert len(standard.products) == 13
    assert sum(len(product.indicators) for product in standard.products) == 13
    assert standard.products[0].name == "硫黄制酸"
    assert standard.products[0].indicators[0].name == "单位产品综合能耗"


def test_gb29141_fuming_and_heat_recovery_corrections() -> None:
    standard = load()
    product = standard.products[0]
    indicator = product.indicators[0]
    concentrated = EvaluationEngine().evaluate(standard, request(standard, product, indicator, actual="-110", acid_type="浓硫酸", heat_recovery=False)).results[0]
    assert concentrated.corrected_thresholds == {"LEVEL_1": Decimal("-160"), "LEVEL_2": Decimal("-150"), "LEVEL_3": Decimal("-110")}
    fuming = EvaluationEngine().evaluate(standard, request(standard, product, indicator, actual="-85", acid_type="发烟硫酸（20%）", heat_recovery=True)).results[0]
    assert fuming.corrected_thresholds == {"LEVEL_1": Decimal("-125"), "LEVEL_2": Decimal("-115"), "LEVEL_3": Decimal("-85")}
    assert fuming.grade.value == "LEVEL_3"


def test_gb29141_detail_formula_and_special_missing_grades() -> None:
    standard = load()
    product = next(item for item in standard.products if item.id == "dilute-nitric-acid")
    indicator = product.indicators[0]
    detail = EvaluationRequest(
        evaluation_date=date(2026, 8, 30), standard_id=standard.id, product_id=product.id, input_mode=InputMode.DETAIL,
        inputs={}, energy_lines=[EnergyLine(line_id="e", energy_name="综合能源", amount="100", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce")],
        production_lines=[ProductionLine(line_id="p", product_name="稀硝酸", quantity="10", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, detail).results[0]
    assert result.actual_value == Decimal("10")
    assert result.grade.value == "LEVEL_3"
    special = next(item for item in standard.products if item.id == "lead-zinc-isp-so2-enrichment").indicators[0]
    assert special.thresholds.level_1 is None and special.thresholds.level_2 is None and special.thresholds.level_3.value == "960"


def test_scope_uses_new_standard_and_history_stays_out_of_current_rows() -> None:
    scope = json.loads(Path("data/scope-44.json").read_text(encoding="utf-8"))
    assert "GB 29141-2024" in scope["standards"]
    assert "GB 29141-2012" not in scope["standards"]

