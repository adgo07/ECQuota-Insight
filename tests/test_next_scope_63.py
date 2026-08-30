from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from uebench.domain.engine import EvaluationEngine
from uebench.domain.models import EnergyLine, EvaluationRequest, Grade, InputMode, InputValue, ProductionLine, PublicationStatus, StandardDefinition

ROOT = Path("work/next-scope-63/data")


def _definition() -> StandardDefinition:
    return StandardDefinition.model_validate_json((ROOT / "definitions/gb-29145-2023.json").read_text(encoding="utf-8"))


def _published() -> StandardDefinition:
    return _definition().model_copy(update={"publication_status": PublicationStatus.PUBLISHED})


def _gb29435_definition() -> StandardDefinition:
    return StandardDefinition.model_validate_json((ROOT / "definitions/gb-29435-2012.json").read_text(encoding="utf-8"))


def _gb29435_published() -> StandardDefinition:
    return _gb29435_definition().model_copy(update={"publication_status": PublicationStatus.PUBLISHED})


def _energy_lines(*, total: str = "300") -> list[EnergyLine]:
    return [
        EnergyLine(line_id="production", energy_name="选矿/焙烧生产系统", category_key="production_system", amount=total, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="auxiliary", energy_name="辅助系统", category_key="auxiliary_system", amount="0", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="affiliated", energy_name="附属系统", category_key="affiliated_system", amount="0", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="output", energy_name="外供二次能源", category_key="external_output", direction="output", amount="0", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
    ]


def test_gb29145_names_thresholds_and_citations_follow_standard() -> None:
    standard = _definition()
    assert [p.name for p in standard.products] == [
        "钨精矿—黑钨", "钨精矿—白钨", "钼精矿—三段一闭路", "钼精矿—SABC",
        "焙烧钼精矿—多膛炉", "焙烧钼精矿—内热式回转窑",
    ]
    assert [p.indicators[0].name for p in standard.products] == [
        "单位产品可比能耗", "单位产品可比能耗", "单位产品可比能耗", "单位产品可比能耗",
        "单位产品能耗", "单位产品能耗",
    ]
    assert [
        [i.thresholds.level_1.value, i.thresholds.level_2.value, i.thresholds.level_3.value]
        for p in standard.products for i in p.indicators
    ] == [
        ["550", "1150", "1450"], ["1640", "1750", "2050"], ["1250", "1390", "1475"],
        ["1900", "2060", "2150"], ["210", "230", "260"], ["170", "180", "200"],
    ]
    assert {reference.page for p in standard.products for reference in p.indicators[0].source_references} >= {4, 6, 7, 10}


def test_gb29145_direct_values_grade_at_level_one_boundary() -> None:
    standard = _published()
    engine = EvaluationEngine()
    for product in standard.products:
        indicator = product.indicators[0]
        request = EvaluationRequest(
            evaluation_date=date(2025, 1, 1),
            standard_id=standard.id,
            product_id=product.id,
            input_mode=InputMode.DIRECT,
            inputs={indicator.direct_input_key: InputValue(value=indicator.thresholds.level_1.value, unit="kgce/t")},
        )
        result = engine.evaluate(standard, request).results[0]
        assert result.grade is Grade.LEVEL_1


def test_gb29145_tungsten_detail_uses_appendix_c_lookup_and_formula_two() -> None:
    standard = _published()
    product = standard.products[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 1, 1),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={"gb29145.tungsten.ore_ratio": InputValue(value="280", unit="ratio")},
        energy_lines=[
            EnergyLine(line_id="production", energy_name="生产系统", category_key="production_system", amount="280", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
            EnergyLine(line_id="auxiliary", energy_name="辅助系统", category_key="auxiliary_system", amount="20", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
            EnergyLine(line_id="affiliated", energy_name="附属系统", category_key="affiliated_system", amount="10", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
            EnergyLine(line_id="output", energy_name="外供二次能源", category_key="external_output", direction="output", amount="10", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        ],
        production_lines=[ProductionLine(line_id="p", product_name="黑钨精矿", category_key="qualified", quantity="1", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("300")
    assert result.grade is Grade.LEVEL_1
    assert any("单位产品能耗 e（公式1）" in step.label and step.operation == "divide" for step in result.calculation_trace)
    assert any(step.operation == "lookup" and step.value == Decimal("1.00") for step in result.calculation_trace)


def test_gb29145_unknown_ore_ratio_is_incomplete_without_interpolation() -> None:
    standard = _published()
    product = standard.products[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 1, 1),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={"gb29145.tungsten.ore_ratio": InputValue(value="285", unit="ratio")},
        energy_lines=_energy_lines(),
        production_lines=[ProductionLine(line_id="p", product_name="黑钨精矿", category_key="qualified", quantity="1", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert any("lookup" in warning or "匹配" in warning for warning in result.warnings)


def test_gb29145_roasted_detail_does_not_apply_comparable_factor() -> None:
    standard = _published()
    product = standard.products[4]
    request = EvaluationRequest(
        evaluation_date=date(2025, 1, 1),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={},
        energy_lines=_energy_lines(total="210"),
        production_lines=[ProductionLine(line_id="p", product_name="焙烧钼精矿", category_key="qualified", quantity="1", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("210")
    assert result.grade is Grade.LEVEL_1
    assert not any("e_KB" in step.label for step in result.calculation_trace)



def test_gb29435_names_levels_and_citations_follow_standard() -> None:
    standard = _gb29435_definition()
    assert len(standard.products) == 31
    assert all(product.indicators[0].name == "单位产品综合能耗" for product in standard.products)
    assert [
        [product.indicators[0].thresholds.level_1.value, product.indicators[0].thresholds.level_2.value, product.indicators[0].thresholds.level_3.value]
        for product in standard.products[:3]
    ] == [["2.19", "2.31", "2.54"], ["2.47", "2.60", "2.86"], ["2.49", "2.62", "2.88"]]
    assert {reference.page for product in standard.products for reference in product.indicators[0].source_references} >= {4, 5, 6, 7, 8, 10, 11}


def test_gb29435_detail_formula_combines_direct_and_indirect_energy() -> None:
    standard = _gb29435_published()
    product = standard.products[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 1, 1),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={},
        energy_lines=[
            EnergyLine(line_id="direct", energy_name="工序直接能耗", category_key="direct_process", amount="2.0", unit="tce", standard_coal_coefficient="1", coefficient_unit="tce/tce"),
            EnergyLine(line_id="indirect", energy_name="间接辅助及损耗", category_key="indirect_aux_loss", amount="0.5", unit="tce", standard_coal_coefficient="1", coefficient_unit="tce/tce"),
        ],
        production_lines=[ProductionLine(line_id="p", product_name="氧化镧", category_key="qualified", quantity="1", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("2.5")
    assert result.grade is Grade.LEVEL_3
    assert any(step.operation == "add" and step.value == Decimal("2.5") for step in result.calculation_trace)


def test_gb29435_missing_indirect_energy_is_incomplete() -> None:
    standard = _gb29435_published()
    product = standard.products[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 1, 1),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={},
        energy_lines=[EnergyLine(line_id="direct", energy_name="工序直接能耗", category_key="direct_process", amount="2.0", unit="tce", standard_coal_coefficient="1", coefficient_unit="tce/tce")],
        production_lines=[ProductionLine(line_id="p", product_name="氧化镧", category_key="qualified", quantity="1", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert any("indirect_aux_loss" in warning for warning in result.warnings)

