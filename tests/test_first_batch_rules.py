from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from uebench.domain.engine import EvaluationEngine, EvaluationValidationError
from uebench.domain.models import (
    DataType,
    EnergyLine,
    EvaluationRequest,
    Grade,
    InputMode,
    InputValue,
    ProductionLine,
    PublicationStatus,
    StandardDefinition,
)


DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "definitions"
FIRST_BATCH_NUMBERS = {
    "GB 16780-2021",
    "GB 29436-2023",
    "GB 21342-2025",
    "GB 21341-2022",
    "GB 21346-2022",
    "GB 21256-2025",
}


DEFAULTS = {
    "site.altitude_m": "0",
    "site.pressure_pa": "101325",
    "cement.clinker_ratio_pct": "75",
    "coke.heating_fuel": "焦炉煤气",
    "coke.mixed_gas_ratio": "0",
    "coke.dry_volatile_pct": "25",
    "coke.total_moisture_pct": "10.5",
    "coke.quenching_method": "干熄焦",
    "coke.oven_age_years": "10",
    "blast-furnace.feed_grade_pct": "62",
    "converter.type": "普通转炉",
    "converter.scrap_ratio_pct": "0",
    "converter.steel_category": "普碳钢",
    "eaf.hot_metal_ratio_pct": "0",
    "eaf.steel_category": "普碳钢",
}


def load_first_batch() -> list[StandardDefinition]:
    definitions = [
        StandardDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        for path in DATA_ROOT.glob("*.json")
    ]
    return [
        definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
        for definition in definitions
        if definition.number in FIRST_BATCH_NUMBERS
    ]


def default_value(definition) -> object:
    if definition.key in DEFAULTS:
        return DEFAULTS[definition.key]
    if definition.data_type is DataType.TEXT:
        return definition.choices[0] if definition.choices else "测试"
    if definition.data_type is DataType.BOOLEAN:
        return False
    if ".grade_pct" in definition.key:
        return definition.minimum or "40"
    return definition.minimum if definition.minimum is not None else "0"


def direct_request(standard: StandardDefinition, product_id: str) -> EvaluationRequest:
    product = next(product for product in standard.products if product.id == product_id)
    definitions = {
        definition.key: definition
        for indicator in product.indicators
        for definition in indicator.input_definitions
    }
    inputs = {
        key: InputValue(value=default_value(definition), unit=definition.unit)
        for key, definition in definitions.items()
    }
    return EvaluationRequest(
        evaluation_date=max(standard.effective_date, date(2026, 8, 23)),
        standard_id=standard.id,
        product_id=product_id,
        input_mode=InputMode.DIRECT,
        inputs=inputs,
    )


def expected_grade(actual: Decimal, thresholds: dict[str, Decimal]) -> Grade:
    for key, grade in (("LEVEL_1", Grade.LEVEL_1), ("LEVEL_2", Grade.LEVEL_2), ("LEVEL_3", Grade.LEVEL_3)):
        if key in thresholds and actual <= thresholds[key]:
            return grade
    return Grade.NOT_QUALIFIED


@pytest.mark.parametrize("standard", load_first_batch(), ids=lambda item: item.number)
def test_every_first_batch_indicator_has_sources_and_boundary_grading(standard: StandardDefinition) -> None:
    engine = EvaluationEngine()
    for product in standard.products:
        seed_request = direct_request(standard, product.id)
        seed_result = engine.evaluate(standard, seed_request)
        by_id = {result.indicator_id: result for result in seed_result.results}
        for indicator in product.indicators:
            seed = by_id[indicator.id]
            assert seed.grade is not Grade.INCOMPLETE, (standard.number, product.id, indicator.id, seed.warnings)
            assert indicator.source_references
            assert all(reference.page >= 1 and reference.clause for reference in indicator.source_references)
            limits = seed.corrected_thresholds
            probes = [limits["LEVEL_1"], limits["LEVEL_3"], limits["LEVEL_3"] + Decimal("0.01")]
            if "LEVEL_2" in limits:
                probes.extend(
                    [
                        (limits["LEVEL_1"] + limits["LEVEL_2"]) / Decimal("2"),
                        limits["LEVEL_2"],
                        (limits["LEVEL_2"] + limits["LEVEL_3"]) / Decimal("2"),
                    ]
                )
            else:
                probes.append((limits["LEVEL_1"] + limits["LEVEL_3"]) / Decimal("2"))
            for actual in probes:
                request = seed_request.model_copy(deep=True)
                request.inputs[indicator.direct_input_key] = InputValue(value=actual, unit=indicator.unit)
                result = engine.evaluate(standard, request)
                item = next(value for value in result.results if value.indicator_id == indicator.id)
                assert item.grade is expected_grade(actual, limits), (
                    standard.number,
                    product.id,
                    indicator.id,
                    actual,
                    limits,
                    item.grade,
                )


def test_direct_and_detail_modes_match_for_standard_coal_and_electricity() -> None:
    standards = {item.number: item for item in load_first_batch()}
    engine = EvaluationEngine()

    methanol = standards["GB 29436-2023"]
    direct = direct_request(methanol, "methanol-bituminous")
    direct.inputs["actual.methanol-bituminous.comprehensive_energy"] = InputValue(value="1400", unit="kgce/t")
    direct_result = engine.evaluate(methanol, direct).results[0]
    detail = direct.model_copy(
        update={
            "input_mode": InputMode.DETAIL,
            "inputs": {},
            "energy_lines": [
                EnergyLine(
                    line_id="e1",
                    energy_name="折标能源",
                    amount="1400",
                    unit="kgce",
                    standard_coal_coefficient="1",
                    coefficient_unit="kgce/kgce",
                )
            ],
            "production_lines": [
                ProductionLine(line_id="p1", product_name="合格甲醇", quantity="1", unit="t")
            ],
        }
    )
    detail_result = engine.evaluate(methanol, detail).results[0]
    assert detail_result.actual_value == direct_result.actual_value == Decimal("1400")
    assert detail_result.grade is direct_result.grade

    aluminum = standards["GB 21346-2022"]
    direct = direct_request(aluminum, "electrolytic-aluminum")
    for key in list(direct.inputs):
        if key.startswith("actual.electrolytic-aluminum"):
            direct.inputs[key] = InputValue(value="13000", unit=direct.inputs[key].unit)
    direct_result = engine.evaluate(aluminum, direct)
    detail = direct.model_copy(
        update={
            "input_mode": InputMode.DETAIL,
            "inputs": {},
            "energy_lines": [
                EnergyLine(
                    line_id="e1",
                    energy_name="交流电",
                    category_key="electricity",
                    amount="13000",
                    unit="kWh",
                    standard_coal_coefficient="0.1229",
                    coefficient_unit="kgce/kWh",
                )
            ],
            "production_lines": [
                ProductionLine(line_id="p1", product_name="铝液", quantity="1", unit="t")
            ],
        }
    )
    detail_result = engine.evaluate(aluminum, detail)
    assert detail_result.results[0].actual_value == Decimal("13000")
    assert detail_result.results[0].grade is direct_result.results[0].grade


def test_representative_corrections_and_missing_level_are_exact() -> None:
    standards = {item.number: item for item in load_first_batch()}
    engine = EvaluationEngine()

    cement = standards["GB 16780-2021"]
    request = direct_request(cement, "cement")
    request.inputs["site.altitude_m"] = InputValue(value="2000", unit="m")
    request.inputs["site.pressure_pa"] = InputValue(value="80000", unit="Pa")
    request.inputs["cement.clinker_ratio_pct"] = InputValue(value="76", unit="%")
    result = engine.evaluate(cement, request).results[0]
    assert result.base_thresholds == {"LEVEL_1": Decimal("80"), "LEVEL_2": Decimal("87"), "LEVEL_3": Decimal("94")}
    assert result.corrected_thresholds["LEVEL_1"] == Decimal("81.10")
    assert result.corrected_thresholds["LEVEL_2"] == Decimal("88.15")
    expected_level_3 = Decimal("95.20") * (Decimal("1.179") - Decimal("0.211") * Decimal("80000") / Decimal("101325"))
    assert result.corrected_thresholds["LEVEL_3"] == expected_level_3

    coke = standards["GB 21342-2025"]
    request = direct_request(coke, "top-charging-coke-oven")
    request.inputs["coke.heating_fuel"] = InputValue(value="混合煤气")
    request.inputs["coke.mixed_gas_ratio"] = InputValue(value="0.5", unit="ratio")
    request.inputs["coke.dry_volatile_pct"] = InputValue(value="24.5", unit="%")
    request.inputs["coke.total_moisture_pct"] = InputValue(value="11", unit="%")
    request.inputs["coke.quenching_method"] = InputValue(value="湿熄焦")
    request.inputs["coke.oven_age_years"] = InputValue(value="20", unit="年")
    result = engine.evaluate(coke, request).results[0]
    raw = Decimal("6.40") + Decimal("3.67")
    assert result.corrected_thresholds["LEVEL_1"] == Decimal("110") + Decimal("4") + raw + Decimal("2.50")
    assert result.corrected_thresholds["LEVEL_2"] == Decimal("110") + Decimal("4") + raw
    assert result.corrected_thresholds["LEVEL_3"] == Decimal("135") + Decimal("4") + raw + Decimal("46.46") + Decimal("2.50")

    steel = standards["GB 21256-2025"]
    request = direct_request(steel, "electric-arc-furnace-lt50")
    result = engine.evaluate(steel, request).results[0]
    assert result.corrected_thresholds == {"LEVEL_1": Decimal("61"), "LEVEL_3": Decimal("86")}
    request.inputs["actual.electric-arc-furnace-lt50.energy"] = InputValue(value="70", unit="kgce/t")
    assert engine.evaluate(steel, request).results[0].grade is Grade.LEVEL_3


def test_pre_effective_date_is_blocked() -> None:
    standard = next(item for item in load_first_batch() if item.number == "GB 21256-2025")
    request = direct_request(standard, "sintering")
    request.evaluation_date = date(2026, 6, 30)
    with pytest.raises(EvaluationValidationError, match="早于标准实施日期"):
        EvaluationEngine().evaluate(standard, request)
