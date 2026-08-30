from __future__ import annotations

import json
import pytest
from datetime import date
from decimal import Decimal
from pathlib import Path

from uebench.domain.engine import EvaluationEngine, EvaluationValidationError
from uebench.domain.models import EnergyLine, EvaluationRequest, Grade, InputMode, InputValue, ProductionLine, PublicationStatus, StandardDefinition

ROOT = Path("work/next-scope-63/data")


def _definition() -> StandardDefinition:
    return StandardDefinition.model_validate_json((ROOT / "definitions/gb-29145-2023.json").read_text(encoding="utf-8"))


def _published() -> StandardDefinition:
    return _definition().model_copy(update={"publication_status": PublicationStatus.PUBLISHED})


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




def _gb29435_definition() -> StandardDefinition:
    return StandardDefinition.model_validate_json((ROOT / "definitions/gb-29435-2025.json").read_text(encoding="utf-8"))


def _gb29435_published() -> StandardDefinition:
    return _gb29435_definition().model_copy(update={"publication_status": PublicationStatus.PUBLISHED})


def _gb29435_energy_lines(*, production: str = "1000", auxiliary: str = "200", affiliated: str = "100", exported: str = "100") -> list[EnergyLine]:
    return [
        EnergyLine(line_id="production", energy_name="主要生产系统", category_key="production_system", amount=production, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="auxiliary", energy_name="辅助生产系统", category_key="auxiliary_system", amount=auxiliary, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="affiliated", energy_name="附属生产系统", category_key="affiliated_system", amount=affiliated, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="output", energy_name="二次能源回收并外供", category_key="external_output", direction="output", amount=exported, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
    ]


def test_gb29435_2025_names_levels_and_citations_follow_standard() -> None:
    standard = _gb29435_definition()
    assert standard.number == "GB 29435-2025"
    assert standard.effective_date == date(2027, 1, 1)
    assert standard.lifecycle_status.value == "future"
    assert len(standard.products) == 51
    assert all(product.indicators[0].name == "单位产品综合能耗" for product in standard.products)
    assert standard.products[0].name == "离子型稀土矿生产—氧化镧"
    assert [standard.products[i].indicators[0].thresholds.level_1.op for i in (0, 16, 27, 28, 33, 47)] == ["constant", "constant", "piecewise", "constant", "constant", "constant"]
    assert [standard.products[0].indicators[0].thresholds.level_1.value, standard.products[0].indicators[0].thresholds.level_2.value, standard.products[0].indicators[0].thresholds.level_3.value] == ["1.41", "1.46", "1.62"]
    assert {reference.page for product in standard.products for reference in product.indicators[0].source_references} >= {5, 6, 7, 8, 9, 10, 11}


def test_gb29435_2025_blocks_formal_evaluation_before_effective_date() -> None:
    standard = _gb29435_published()
    product = standard.products[0]
    indicator = product.indicators[0]
    request = EvaluationRequest(
        evaluation_date=date(2026, 12, 31), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DIRECT,
        inputs={indicator.direct_input_key: InputValue(value="1.41", unit="tce/t")},
    )
    with pytest.raises(EvaluationValidationError, match="早于标准实施日期"):
        EvaluationEngine().evaluate(standard, request)


def test_gb29435_2025_detail_formula_converts_kgce_and_subtracts_external_output() -> None:
    standard = _gb29435_published()
    product = standard.products[0]
    request = EvaluationRequest(
        evaluation_date=date(2027, 1, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL, inputs={}, energy_lines=_gb29435_energy_lines(),
        production_lines=[ProductionLine(line_id="p", product_name="氧化镧", quantity="1", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("1.2")
    assert result.grade is Grade.LEVEL_1
    assert any("kgce换算为tce" in step.label for step in result.calculation_trace)
    assert any(step.operation == "add" and step.value == Decimal("1200") for step in result.calculation_trace)


def test_gb29435_2025_missing_required_energy_category_is_incomplete() -> None:
    standard = _gb29435_published()
    product = standard.products[0]
    lines = _gb29435_energy_lines()
    request = EvaluationRequest(
        evaluation_date=date(2027, 1, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL, inputs={}, energy_lines=lines[:3],
        production_lines=[ProductionLine(line_id="p", product_name="氧化镧", quantity="1", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert any("external_output" in warning for warning in result.warnings)


def test_gb29435_2025_fluorocarbon_footnote_selects_table_three_or_table_two() -> None:
    standard = _gb29435_published()
    product = standard.products[27]
    indicator = product.indicators[0]
    process_key = product.input_definitions[0].key
    direct = lambda process, value: EvaluationRequest(
        evaluation_date=date(2027, 1, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DIRECT,
        inputs={process_key: InputValue(value=process), indicator.direct_input_key: InputValue(value=value, unit="tce/t")},
    )
    table3 = EvaluationEngine().evaluate(standard, direct("氧化焙烧-盐酸浸出", "0.66")).results[0]
    table2 = EvaluationEngine().evaluate(standard, direct("浓硫酸强化焙烧", "1.38")).results[0]
    assert table3.grade is Grade.LEVEL_1
    assert table2.grade is Grade.LEVEL_1
    missing = EvaluationEngine().evaluate(standard, EvaluationRequest(
        evaluation_date=date(2027, 1, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DIRECT, inputs={indicator.direct_input_key: InputValue(value="0.66", unit="tce/t")},
    )).results[0]
    assert missing.grade is Grade.INCOMPLETE

def _gb30185_definition() -> StandardDefinition:
    return StandardDefinition.model_validate_json((ROOT / "definitions/gb-30185-2025.json").read_text(encoding="utf-8"))


def _gb30185_published() -> StandardDefinition:
    return _gb30185_definition().model_copy(update={"publication_status": PublicationStatus.PUBLISHED})


def _gb30185_energy_lines(*, production: str = "2000", auxiliary: str = "1000", affiliated: str = "0") -> list[EnergyLine]:
    return [
        EnergyLine(line_id="production", energy_name="生产系统", category_key="production_system", amount=production, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="auxiliary", energy_name="辅助生产系统", category_key="auxiliary_system", amount=auxiliary, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="affiliated", energy_name="附属生产系统", category_key="affiliated_system", amount=affiliated, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
    ]


def test_gb30185_names_levels_and_citations_follow_standard() -> None:
    standard = _gb30185_definition()
    assert standard.number == "GB 30185-2025"
    assert standard.title == "铝(塑)复合板单位产品能源消耗限额"
    assert standard.effective_date == date(2026, 3, 1)
    assert standard.lifecycle_status.value == "active"
    assert len(standard.products) == 7
    assert [product.name for product in standard.products] == [
        "铝塑复合板—热压复合装饰板",
        "铝塑复合板—化成涂装和热压复合",
        "铝塑复合板—幕墙板热压复合",
        "铝塑复合板—幕墙板化成涂装和热压复合",
        "不燃铝复合板",
        "装饰用铝单板—粉末喷涂",
        "装饰用铝单板—液体喷涂",
    ]
    assert all(product.indicators[0].name == "单位产品综合能耗" for product in standard.products)
    assert all(product.indicators[0].unit == "kgce/10^4m2" for product in standard.products)
    assert [
        [indicator.thresholds.level_1.value, indicator.thresholds.level_2.value, indicator.thresholds.level_3.value]
        for product in standard.products for indicator in product.indicators
    ] == [
        ["2400", "3000", "4400"], ["3500", "5000", "6500"], ["2700", "3200", "4800"],
        ["4400", "5600", "7600"], ["3200", "3900", "5400"], ["7000", "8500", "10200"],
        ["12000", "14000", "17200"],
    ]
    assert {reference.page for product in standard.products for reference in product.indicators[0].source_references} >= {5, 6, 7, 8}


def test_gb30185_direct_values_grade_at_level_one_boundary() -> None:
    standard = _gb30185_published()
    product = standard.products[0]
    indicator = product.indicators[0]
    request = EvaluationRequest(
        evaluation_date=date(2026, 3, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DIRECT,
        inputs={indicator.direct_input_key: InputValue(value="2400", unit="kgce/10^4m2")},
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("2400")
    assert result.grade is Grade.LEVEL_1


def test_gb30185_detail_formula_uses_three_energy_systems_and_formula_two() -> None:
    standard = _gb30185_published()
    product = standard.products[0]
    request = EvaluationRequest(
        evaluation_date=date(2026, 3, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL, inputs={}, energy_lines=_gb30185_energy_lines(),
        production_lines=[ProductionLine(line_id="p", product_name=product.name, category_key="qualified", quantity="1", unit="10^4m2")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("3000")
    assert result.grade is Grade.LEVEL_2
    assert any(step.operation == "per_unit" and step.value == Decimal("3000") for step in result.calculation_trace)


def test_gb30185_detail_missing_energy_system_is_incomplete() -> None:
    standard = _gb30185_published()
    product = standard.products[0]
    request = EvaluationRequest(
        evaluation_date=date(2026, 3, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL, inputs={}, energy_lines=_gb30185_energy_lines()[:2],
        production_lines=[ProductionLine(line_id="p", product_name=product.name, category_key="qualified", quantity="1", unit="10^4m2")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert any("energy.category.affiliated_system.net_standard_coal" in warning for warning in result.warnings)

def _gb30530_definition() -> StandardDefinition:
    return StandardDefinition.model_validate_json((ROOT / "definitions/gb-30530-2024.json").read_text(encoding="utf-8"))


def _gb30530_published() -> StandardDefinition:
    return _gb30530_definition().model_copy(update={"publication_status": PublicationStatus.PUBLISHED})


def _gb30530_energy_lines(*, production: str = "600", auxiliary: str = "40", affiliated: str = "0", exported: str = "100") -> list[EnergyLine]:
    return [
        EnergyLine(line_id="production", energy_name="生产系统", category_key="production_system", amount=production, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="auxiliary", energy_name="辅助生产系统", category_key="auxiliary_system", amount=auxiliary, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="affiliated", energy_name="附属生产系统", category_key="affiliated_system", amount=affiliated, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="external-output", energy_name="向外输出能源", category_key="external_output", direction="output", amount=exported, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
    ]


def _gb30530_raw_inputs(*, silicon_quantity: str = "100", chloromethane_quantity: str = "100") -> dict[str, InputValue]:
    return {
        "raw_material.silicon_powder.quantity": InputValue(value=silicon_quantity, unit="t"),
        "raw_material.silicon_powder.unit_energy": InputValue(value="0.0275", unit="kgce/t"),
        "raw_material.chloromethane.quantity": InputValue(value=chloromethane_quantity, unit="t"),
        "raw_material.chloromethane.unit_energy": InputValue(value="0.0797", unit="kgce/t"),
    }


def _gb30530_production_lines(*, external_dmdcs: str = "0") -> list[ProductionLine]:
    return [
        ProductionLine(line_id="hydrolysate", product_name="合格水解物", quantity="1", unit="t"),
        ProductionLine(line_id="cyclic", product_name="合格环体", quantity="0", unit="t"),
        ProductionLine(line_id="linear", product_name="合格线性体", quantity="0", unit="t"),
        ProductionLine(line_id="external-dmdcs", product_name="外售二甲基二氯硅烷", quantity=external_dmdcs, unit="t", conversion_factor="0.56"),
    ]


def test_gb30530_names_levels_and_citations_follow_standard() -> None:
    standard = _gb30530_definition()
    assert standard.number == "GB 30530-2024"
    assert standard.title == "二甲基硅氧烷单位产品能源消耗限额"
    assert standard.effective_date == date(2025, 5, 1)
    assert standard.lifecycle_status.value == "active"
    assert len(standard.products) == 1
    product = standard.products[0]
    indicator = product.indicators[0]
    assert product.name == "二甲基硅氧烷"
    assert indicator.name == "单位产品能耗"
    assert indicator.unit == "kgce/t"
    assert [indicator.thresholds.level_1.value, indicator.thresholds.level_2.value, indicator.thresholds.level_3.value] == ["650", "750", "1000"]
    assert {reference.page for reference in indicator.source_references} >= {5, 6, 7, 8, 9, 10}


def test_gb30530_direct_value_grade_at_level_one_boundary() -> None:
    standard = _gb30530_published()
    product = standard.products[0]
    indicator = product.indicators[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 5, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DIRECT,
        inputs={indicator.direct_input_key: InputValue(value="650", unit="kgce/t")},
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("650")
    assert result.grade is Grade.LEVEL_1


def test_gb30530_detail_formula_includes_raw_material_energy_and_excludes_external_output() -> None:
    standard = _gb30530_published()
    product = standard.products[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 5, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL, inputs=_gb30530_raw_inputs(),
        energy_lines=_gb30530_energy_lines(), production_lines=_gb30530_production_lines(),
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("650.72")
    assert result.grade is Grade.LEVEL_2
    assert any(step.label == "外购硅粉能耗 g₁×q₁" and step.value == Decimal("2.7500") for step in result.calculation_trace)
    assert any(step.label == "外购氯甲烷能耗 g₂×q₂" and step.value == Decimal("7.9700") for step in result.calculation_trace)


def test_gb30530_detail_formula_uses_external_dmdcs_conversion_factor() -> None:
    standard = _gb30530_published()
    product = standard.products[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 5, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL, inputs=_gb30530_raw_inputs(silicon_quantity="0", chloromethane_quantity="0"),
        energy_lines=_gb30530_energy_lines(production="650", auxiliary="0", exported="0"),
        production_lines=_gb30530_production_lines(external_dmdcs="1"),
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("650") / Decimal("1.56")
    assert result.grade is Grade.LEVEL_1
    assert any(step.operation == "production_line" and step.value == Decimal("0.56") for step in result.calculation_trace)


def test_gb30530_missing_raw_material_input_is_incomplete() -> None:
    standard = _gb30530_published()
    product = standard.products[0]
    inputs = _gb30530_raw_inputs()
    inputs.pop("raw_material.chloromethane.unit_energy")
    request = EvaluationRequest(
        evaluation_date=date(2025, 5, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL, inputs=inputs,
        energy_lines=_gb30530_energy_lines(), production_lines=_gb30530_production_lines(),
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert any("raw_material.chloromethane.unit_energy" in warning for warning in result.warnings)

def _gb30182_definition() -> StandardDefinition:
    return StandardDefinition.model_validate_json((ROOT / "definitions/gb-30182-2013.json").read_text(encoding="utf-8"))


def _gb30182_published() -> StandardDefinition:
    return _gb30182_definition().model_copy(update={"publication_status": PublicationStatus.PUBLISHED})


def test_gb30182_names_and_indicator_names_follow_standard() -> None:
    standard = _gb30182_definition()
    product = standard.products[0]
    assert product.name == "不带钢背（或蹄铁）的模压型摩擦材料"
    assert [indicator.name for indicator in product.indicators] == ["单位产品综合能耗", "电耗"]
    assert [indicator.unit for indicator in product.indicators] == ["kgce/t", "kWh/t"]
    assert [
        [indicator.thresholds.level_1.value, indicator.thresholds.level_2.value, indicator.thresholds.level_3.value]
        for indicator in product.indicators
    ] == [["115", "135", "175"], ["800", "1000", "1300"]]
    assert {reference.page for indicator in product.indicators for reference in indicator.source_references} >= {3, 4, 5, 7}


def test_gb30182_direct_boundaries_and_detail_energy_match_standard_formula() -> None:
    standard = _gb30182_published()
    product = standard.products[0]
    direct_inputs = {
        indicator.direct_input_key: InputValue(value=value, unit=indicator.unit)
        for indicator, value in zip(product.indicators, ("115", "800"), strict=True)
    }
    direct = EvaluationRequest(
        evaluation_date=date(2014, 12, 1),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DIRECT,
        inputs=direct_inputs,
    )
    direct_results = EvaluationEngine().evaluate(standard, direct).results
    assert [result.grade for result in direct_results] == [Grade.LEVEL_1, Grade.LEVEL_1]
    detail = direct.model_copy(update={
        "input_mode": InputMode.DETAIL,
        "inputs": {},
        "energy_lines": [
            EnergyLine(line_id="fuel", energy_name="燃料折标量", amount="100", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
            EnergyLine(line_id="electricity", energy_name="直接电力", category_key="direct_electricity", amount="800", unit="kWh", standard_coal_coefficient="0.1229", coefficient_unit="kgce/kWh"),
        ],
        "production_lines": [ProductionLine(line_id="p", product_name="合格摩擦材料", quantity="1", unit="t")],
    })
    detail_results = EvaluationEngine().evaluate(standard, detail).results
    assert detail_results[0].actual_value == Decimal("198.32")
    assert detail_results[1].actual_value == Decimal("800")
    assert detail_results[1].grade is Grade.LEVEL_1


def test_gb30182_missing_direct_electricity_is_incomplete_only_for_electricity_indicator() -> None:
    standard = _gb30182_published()
    product = standard.products[0]
    request = EvaluationRequest(
        evaluation_date=date(2014, 12, 1),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={},
        energy_lines=[EnergyLine(line_id="fuel", energy_name="燃料折标量", amount="100", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce")],
        production_lines=[ProductionLine(line_id="p", product_name="合格摩擦材料", quantity="1", unit="t")],
    )
    results = EvaluationEngine().evaluate(standard, request).results
    assert results[0].grade is Grade.LEVEL_1
    assert results[1].grade is Grade.INCOMPLETE
    assert any("direct_electricity" in warning for warning in results[1].warnings)




def test_gb29435_replacement_is_reflected_in_active_scope() -> None:
    scope = json.loads((ROOT / "scope-63.json").read_text(encoding="utf-8"))
    assert "GB 29435-2025" in scope["standards"]
    assert "GB 29435-2012" not in scope["standards"]
    retired = ROOT / "retired-definitions/gb-29435-2012.json"
    retired_definition = StandardDefinition.model_validate_json(retired.read_text(encoding="utf-8"))
    assert retired_definition.lifecycle_status.value == "obsolete"
    assert retired_definition.obsolete_date == date(2027, 1, 1)
    assert retired_definition.replaced_by == ["GB 29435-2025"]
