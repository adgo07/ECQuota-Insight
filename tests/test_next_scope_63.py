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

def _gb29145_scope_input(product_id: str, *, mining_method: str | None = None) -> dict[str, InputValue]:
    if product_id.startswith("tungsten"):
        return {"condition.GB29145.tungsten.mining_method": InputValue(value=mining_method or "地下开采")}
    if product_id.startswith("molybdenum"):
        return {"condition.GB29145.molybdenum.mining_method": InputValue(value=mining_method or "露天开采")}
    return {}


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
    assert standard.supersedes == ["GB 29145-2012", "GB 29146-2012", "GB 31340-2014"]


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
            inputs={indicator.direct_input_key: InputValue(value=indicator.thresholds.level_1.value, unit="kgce/t"), **_gb29145_scope_input(product.id)},
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
        inputs={"gb29145.tungsten.ore_ratio": InputValue(value="280", unit="ratio"), **_gb29145_scope_input(product.id)},
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
        inputs={"gb29145.tungsten.ore_ratio": InputValue(value="285", unit="ratio"), **_gb29145_scope_input(product.id)},
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


def _gb31823_definition() -> StandardDefinition:
    return StandardDefinition.model_validate_json(
        (ROOT / "definitions/gb-31823-2021.json").read_text(encoding="utf-8")
    )


def _gb31823_published() -> StandardDefinition:
    return _gb31823_definition().model_copy(update={"publication_status": PublicationStatus.PUBLISHED})


def _gb31823_energy_lines(*, production: str = "0", auxiliary: str = "0", affiliated: str = "0", pipeline_heat: str = "0") -> list[EnergyLine]:
    return [
        EnergyLine(line_id="production", energy_name="生产系统", category_key="production_system", amount=production, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="auxiliary", energy_name="辅助生产系统", category_key="auxiliary_system", amount=auxiliary, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="affiliated", energy_name="附属生产系统", category_key="affiliated_system", amount=affiliated, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="pipeline-heat", energy_name="管道伴热", category_key="pipeline_heat", amount=pipeline_heat, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
    ]


def test_gb31823_names_levels_and_citations_follow_standard() -> None:
    standard = _gb31823_definition()
    assert standard.number == "GB 31823-2021"
    assert standard.title == "码头作业单位产品能源消耗限额"
    assert standard.effective_date == date(2022, 11, 1)
    assert standard.lifecycle_status.value == "active"
    assert standard.supersedes == ["GB 31823-2015", "GB 31827-2015"]
    assert [product.name for product in standard.products] == ["集装箱码头", "干散货码头", "原油码头"]
    assert all(product.indicators[0].name == "单位产品可比综合能耗" for product in standard.products)
    assert [product.indicators[0].unit for product in standard.products] == ["tce/10^4TEU", "tce/10^4t", "tce/10^4t"]
    assert [
        [indicator.thresholds.level_1.value, indicator.thresholds.level_2.value, indicator.thresholds.level_3.value]
        for product in standard.products for indicator in product.indicators
    ] == [["24", "28", "45"], ["1.8", "2.0", "2.7"], ["0.36", "0.51", "0.88"]]
    assert {reference.page for product in standard.products for reference in product.indicators[0].source_references} >= {4, 5, 6, 7, 8, 9, 10}


def test_gb31823_direct_level_one_boundaries() -> None:
    standard = _gb31823_published()
    engine = EvaluationEngine()
    for product in standard.products:
        indicator = product.indicators[0]
        request = EvaluationRequest(
            evaluation_date=date(2022, 11, 1),
            standard_id=standard.id,
            product_id=product.id,
            input_mode=InputMode.DIRECT,
            inputs={indicator.direct_input_key: InputValue(value=indicator.thresholds.level_1.value, unit=indicator.unit)},
        )
        result = engine.evaluate(standard, request).results[0]
        assert result.actual_value == Decimal(indicator.thresholds.level_1.value)
        assert result.grade is Grade.LEVEL_1


def test_gb31823_container_detail_uses_adaptation_factor_and_teu_throughput() -> None:
    standard = _gb31823_published()
    product = standard.products[0]
    base_inputs = {"condition.GB31823.container.adaptation_degree": InputValue(value="2", unit="ratio")}
    request = EvaluationRequest(
        evaluation_date=date(2022, 11, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL, inputs=base_inputs,
        energy_lines=_gb31823_energy_lines(production="24000"),
        production_lines=[ProductionLine(line_id="throughput", product_name="集装箱吞吐量", quantity="1", unit="10^4TEU")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("24")
    assert result.grade is Grade.LEVEL_1
    adjusted = request.model_copy(update={"inputs": {"condition.GB31823.container.adaptation_degree": InputValue(value="2.5", unit="ratio")}})
    adjusted_result = EvaluationEngine().evaluate(standard, adjusted).results[0]
    assert adjusted_result.actual_value == Decimal("22.8")
    assert any("a=0.95" in step.label for step in adjusted_result.calculation_trace)


def test_gb31823_dry_bulk_detail_uses_g_k_and_c_corrections() -> None:
    standard = _gb31823_published()
    product = standard.products[1]
    inputs = {
        "condition.GB31823.dry_bulk.portal_crane": InputValue(value=False),
        "condition.GB31823.dry_bulk.direct_to_factory": InputValue(value=False),
        "condition.GB31823.dry_bulk.unloading_share": InputValue(value="0.5", unit="fraction"),
        "condition.GB31823.dry_bulk.work_line_length": InputValue(value="500", unit="m"),
        "condition.GB31823.dry_bulk.heating_region": InputValue(value="采暖地区"),
    }
    request = EvaluationRequest(
        evaluation_date=date(2022, 11, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL, inputs=inputs,
        energy_lines=_gb31823_energy_lines(production="1000", auxiliary="500"),
        production_lines=[ProductionLine(line_id="throughput", product_name="干散货吞吐量", quantity="1", unit="10^4t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    expected = (Decimal("1") / (Decimal("1.4") * Decimal("0.5") + Decimal("0.04")) * Decimal("1.1") + Decimal("0.5")) * Decimal("0.95")
    assert result.actual_value == expected
    assert result.grade is Grade.LEVEL_2
    assert any("g=1/(1.4w+0.04)" in step.label for step in result.calculation_trace)


def test_gb31823_dry_bulk_portal_crane_branch_does_not_require_unloading_share() -> None:
    standard = _gb31823_published()
    product = standard.products[1]
    request = EvaluationRequest(
        evaluation_date=date(2022, 11, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={
            "condition.GB31823.dry_bulk.portal_crane": InputValue(value=True),
            "condition.GB31823.dry_bulk.work_line_length": InputValue(value="500", unit="m"),
            "condition.GB31823.dry_bulk.heating_region": InputValue(value="非采暖地区"),
        },
        energy_lines=_gb31823_energy_lines(production="1000"),
        production_lines=[ProductionLine(line_id="throughput", product_name="干散货吞吐量", quantity="1", unit="10^4t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("1.1")
    assert result.grade is Grade.LEVEL_1


def test_gb31823_dry_bulk_missing_conditional_inputs_is_incomplete() -> None:
    standard = _gb31823_published()
    request = EvaluationRequest(
        evaluation_date=date(2022, 11, 1), standard_id=standard.id, product_id=standard.products[1].id,
        input_mode=InputMode.DETAIL,
        inputs={"condition.GB31823.dry_bulk.portal_crane": InputValue(value=False)},
        energy_lines=_gb31823_energy_lines(production="1000"),
        production_lines=[ProductionLine(line_id="throughput", product_name="干散货吞吐量", quantity="1", unit="10^4t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert any("direct_to_factory" in warning for warning in result.warnings)


def test_gb31823_crude_oil_detail_uses_pipeline_heat_beta() -> None:
    standard = _gb31823_published()
    product = standard.products[2]
    request = EvaluationRequest(
        evaluation_date=date(2022, 11, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={"condition.GB31823.crude_oil.pipeline_heat_temperature": InputValue(value="0", unit="℃")},
        energy_lines=_gb31823_energy_lines(production="3000", auxiliary="500", pipeline_heat="1000"),
        production_lines=[ProductionLine(line_id="throughput", product_name="原油吞吐量", quantity="10", unit="10^4t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("0.445")
    assert result.grade is Grade.LEVEL_2
    assert any("βt×Ebp" in step.label for step in result.calculation_trace)


def test_gb31823_crude_oil_missing_pipeline_heat_is_incomplete() -> None:
    standard = _gb31823_published()
    product = standard.products[2]
    request = EvaluationRequest(
        evaluation_date=date(2022, 11, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={"condition.GB31823.crude_oil.pipeline_heat_temperature": InputValue(value="5", unit="℃")},
        energy_lines=_gb31823_energy_lines(production="3000", auxiliary="500", pipeline_heat="0")[:3],
        production_lines=[ProductionLine(line_id="throughput", product_name="原油吞吐量", quantity="10", unit="10^4t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert any("pipeline_heat" in warning for warning in result.warnings)


def test_gb31823_crude_oil_missing_temperature_is_incomplete() -> None:
    standard = _gb31823_published()
    product = standard.products[2]
    request = EvaluationRequest(
        evaluation_date=date(2022, 11, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL, inputs={},
        energy_lines=_gb31823_energy_lines(production="3000", auxiliary="500", pipeline_heat="1000"),
        production_lines=[ProductionLine(line_id="throughput", product_name="原油吞吐量", quantity="10", unit="10^4t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert any("pipeline_heat_temperature" in warning for warning in result.warnings)


def test_gb31823_dry_bulk_direct_to_factory_branch_uses_fixed_g() -> None:
    standard = _gb31823_published()
    product = standard.products[1]
    request = EvaluationRequest(
        evaluation_date=date(2022, 11, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={
            "condition.GB31823.dry_bulk.portal_crane": InputValue(value=False),
            "condition.GB31823.dry_bulk.direct_to_factory": InputValue(value=True),
            "condition.GB31823.dry_bulk.work_line_length": InputValue(value="500", unit="m"),
            "condition.GB31823.dry_bulk.heating_region": InputValue(value="非采暖地区"),
        },
        energy_lines=_gb31823_energy_lines(production="1000"),
        production_lines=[ProductionLine(line_id="throughput", product_name="干散货吞吐量", quantity="1", unit="10^4t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("1.43")
    assert result.grade is Grade.LEVEL_1
    assert any("g=1.3" in step.label for step in result.calculation_trace)


def _gb21345_definition() -> StandardDefinition:
    return StandardDefinition.model_validate_json(
        (ROOT / "definitions/gb-21345-2024.json").read_text(encoding="utf-8")
    )


def _gb21345_published() -> StandardDefinition:
    return _gb21345_definition().model_copy(update={"publication_status": PublicationStatus.PUBLISHED})


def _gb21345_energy_lines(*, carbon: str = "100", furnace: str = "200000", other: str = "50", auxiliary: str = "20", exported: str = "10") -> list[EnergyLine]:
    return [
        EnergyLine(line_id="carbon", energy_name="炭质还原剂", category_key="carbon_reducing", amount=carbon, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="furnace", energy_name="电炉加热电量", category_key="furnace_electricity", amount=furnace, unit="kWh", standard_coal_coefficient="1", coefficient_unit="kWh/kWh"),
        EnergyLine(line_id="other", energy_name="生产系统其他能源", category_key="production_other", amount=other, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="auxiliary", energy_name="辅助及附属系统", category_key="auxiliary_affiliated", amount=auxiliary, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        EnergyLine(line_id="output", energy_name="界区外输出能源", category_key="external_output", direction="output", amount=exported, unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
    ]


def _gb21345_inputs(*, ns: str = "0", ps: str = "0", ppw_ps: str = "0", nh: str = "0", ph: str = "0", ppw_ph: str = "0", ppwn: str = "0", n1: str = "10") -> dict[str, InputValue]:
    return {
        "yellow_phosphorus.feedstock.p2o5_pct": InputValue(value=n1, unit="%"),
        "yellow_phosphorus.feedstock.fe2o3_pct": InputValue(value="1", unit="%"),
        "yellow_phosphorus.feedstock.co2_pct": InputValue(value="2", unit="%"),
        "yellow_phosphorus.product.qualified_t": InputValue(value="10", unit="t"),
        "yellow_phosphorus.product.phosphoric_acid_mass_fraction": InputValue(value=ns, unit="fraction"),
        "yellow_phosphorus.product.phosphoric_acid_production_t": InputValue(value=ps, unit="t"),
        "yellow_phosphorus.product.phosphoric_acid_external_yellow_phosphorus_t": InputValue(value=ppw_ps, unit="t"),
        "yellow_phosphorus.product.other_chemical_phosphorus_fraction": InputValue(value=nh, unit="fraction"),
        "yellow_phosphorus.product.other_chemical_production_t": InputValue(value=ph, unit="t"),
        "yellow_phosphorus.product.other_chemical_external_yellow_phosphorus_t": InputValue(value=ppw_ph, unit="t"),
        "yellow_phosphorus.product.external_mud_recovered_t": InputValue(value=ppwn, unit="t"),
    }


def _gb21345_request(*, input_mode: InputMode = InputMode.DETAIL, inputs: dict[str, InputValue] | None = None, energy_lines: list[EnergyLine] | None = None, evaluation_date: date = date(2025, 5, 1)) -> EvaluationRequest:
    standard = _gb21345_published()
    return EvaluationRequest(
        evaluation_date=evaluation_date,
        standard_id=standard.id,
        product_id=standard.products[0].id,
        input_mode=input_mode,
        inputs=inputs or {},
        energy_lines=energy_lines or [],
        production_lines=[ProductionLine(line_id="ppz", product_name="符合GB/T 7816的黄磷", category_key="qualified", quantity="10", unit="t")],
    )


def test_gb21345_names_effective_date_levels_and_citations_follow_standard() -> None:
    standard = _gb21345_definition()
    assert standard.number == "GB 21345-2024"
    assert standard.title == "黄磷单位产品能源消耗限额"
    assert standard.publication_date == date(2024, 4, 29)
    assert standard.effective_date == date(2025, 5, 1)
    assert standard.lifecycle_status.value == "active"
    assert standard.supersedes == ["GB 21345-2015"]
    assert [product.name for product in standard.products] == ["电炉法黄磷"]
    assert [indicator.name for product in standard.products for indicator in product.indicators] == ["单位产品综合能耗"]
    indicator = standard.products[0].indicators[0]
    assert indicator.unit == "kgce/t"
    assert [indicator.thresholds.level_1.value, indicator.thresholds.level_2.value, indicator.thresholds.level_3.value] == ["2300", "2450", "2800"]
    assert {reference.page for reference in indicator.source_references} >= {6, 8, 9}


@pytest.mark.parametrize(
    ("actual", "expected"),
    [("2300", Grade.LEVEL_1), ("2300.01", Grade.LEVEL_2), ("2450", Grade.LEVEL_2),
     ("2450.01", Grade.LEVEL_3), ("2800", Grade.LEVEL_3), ("2800.01", Grade.NOT_QUALIFIED)],
)
def test_gb21345_direct_boundaries_are_inclusive_and_ordered(actual: str, expected: Grade) -> None:
    standard = _gb21345_published()
    indicator = standard.products[0].indicators[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 5, 1),
        standard_id=standard.id,
        product_id=standard.products[0].id,
        input_mode=InputMode.DIRECT,
        inputs={indicator.direct_input_key: InputValue(value=actual, unit="kgce/t")},
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal(actual)
    assert result.grade is expected


def test_gb21345_detail_formula_calculates_epl_and_deducts_external_output() -> None:
    standard = _gb21345_published()
    request = _gb21345_request(inputs=_gb21345_inputs(), energy_lines=_gb21345_energy_lines())
    result = EvaluationEngine().evaluate(standard, request).results[0]
    n1 = Decimal("10")
    correction = (
        Decimal("170000") / (n1 - Decimal("0.5"))
        + (Decimal("7750") / (n1 - Decimal("8")) - Decimal("76")) * Decimal("1")
        + (Decimal("3200") / (n1 - Decimal("3.5")) + Decimal("8")) * Decimal("2")
        - Decimal("7234")
    )
    epl = (Decimal("200000") - correction * Decimal("10")) * Decimal("0.1229")
    expected = (Decimal("100") + epl + Decimal("50") + Decimal("20") - Decimal("10")) / Decimal("10")
    assert result.actual_value == expected
    assert result.grade is Grade.LEVEL_1
    assert any(step.label == "黄磷产品电炉电耗 EPL" and step.operation == "multiply" for step in result.calculation_trace)
    assert any(step.label == "界区外输出能源 EPW" and step.value == Decimal("10") for step in result.calculation_trace)
    no_output = EvaluationEngine().evaluate(
        standard,
        request.model_copy(update={"energy_lines": _gb21345_energy_lines(exported="0")}),
    ).results[0]
    assert no_output.actual_value - result.actual_value == Decimal("1")


def test_gb21345_formula9_and_formula10_derive_pp_from_byproducts() -> None:
    standard = _gb21345_published()
    inputs = _gb21345_inputs(ns="0.8", ps="1", ppw_ps="0.1", nh="0.5", ph="1", ppw_ph="0.05", ppwn="0.2")
    request = _gb21345_request(inputs=inputs, energy_lines=_gb21345_energy_lines(exported="0"))
    result = EvaluationEngine().evaluate(standard, request).results[0]
    expected_pp = Decimal("10") + Decimal("0.3163") * Decimal("0.8") * Decimal("1") - Decimal("0.1") + Decimal("0.5") * Decimal("1") - Decimal("0.05") - Decimal("0.2")
    assert result.grade is Grade.LEVEL_1
    assert any(step.operation == "subtract" and step.label == "黄磷产品产量 PP（公式8）" and step.value == expected_pp for step in result.calculation_trace)
    assert any(step.label == "泥磷制磷酸折合黄磷量 PPS（公式9）" and step.value == Decimal("0.15304") for step in result.calculation_trace)
    assert any(step.label == "泥磷制其他化学品折合黄磷量 PPH（公式10）" and step.value == Decimal("0.45") for step in result.calculation_trace)


def test_gb21345_missing_detail_input_is_incomplete_without_guessing() -> None:
    standard = _gb21345_published()
    request = _gb21345_request(inputs={}, energy_lines=_gb21345_energy_lines())
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert result.actual_value is None
    assert any("yellow_phosphorus.feedstock.p2o5_pct" in warning for warning in result.warnings)


def test_gb21345_zero_formula_denominator_is_incomplete() -> None:
    standard = _gb21345_published()
    request = _gb21345_request(inputs=_gb21345_inputs(n1="8"), energy_lines=_gb21345_energy_lines())
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert any("除零" in warning for warning in result.warnings)


def test_gb29145_scope_condition_blocks_inapplicable_tungsten_mining_method() -> None:
    standard = _published()
    product = standard.products[0]
    indicator = product.indicators[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 1, 1),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DIRECT,
        inputs={
            indicator.direct_input_key: InputValue(value="550", unit="kgce/t"),
            "condition.GB29145.tungsten.mining_method": InputValue(value="露天开采"),
        },
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.NOT_APPLICABLE


def test_gb29145_scope_condition_requires_mining_method_when_applicability_is_unknown() -> None:
    standard = _published()
    product = standard.products[2]
    indicator = product.indicators[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 1, 1),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DIRECT,
        inputs={indicator.direct_input_key: InputValue(value="1250", unit="kgce/t")},
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert any("condition.GB29145.molybdenum.mining_method" in warning for warning in result.warnings)

def _gb29450_definition() -> StandardDefinition:
    return StandardDefinition.model_validate_json((ROOT / "definitions/gb-29450-2012.json").read_text(encoding="utf-8"))


def _gb29450_published() -> StandardDefinition:
    return _gb29450_definition().model_copy(update={"publication_status": PublicationStatus.PUBLISHED})


def _gb29450_energy_lines(total: str) -> list[EnergyLine]:
    return [
        EnergyLine(
            line_id="glass-fiber-energy",
            energy_name="玻璃纤维生产能源",
            category_key="production_system",
            amount=total,
            unit="kgce",
            standard_coal_coefficient="1",
            coefficient_unit="kgce/kgce",
        ),
    ]


def test_gb29450_names_levels_and_indicator_split_follow_source_tables() -> None:
    standard = _gb29450_definition()
    assert standard.number == "GB 29450-2012"
    assert standard.title == "玻璃纤维单位产品能源消耗限额"
    assert standard.effective_date == date(2013, 10, 1)
    assert [product.name for product in standard.products] == [
        "池窑法—E玻璃纤维纱（纤维直径≤9μm）",
        "池窑法—E(ECR)玻璃纤维纱（纤维直径＞9μm）",
        "池窑法—中碱玻璃纤维纱",
        "坩埚法—制球—无碱玻璃球",
        "坩埚法—制球—中碱玻璃球",
        "坩埚法—拉丝—玻璃纤维纱",
    ]
    assert all(product.indicators[0].name == "单位产品综合能耗" for product in standard.products)
    assert [
        [None if getattr(product.indicators[0].thresholds, f"level_{level}") is None else getattr(product.indicators[0].thresholds, f"level_{level}").value for level in (1, 2, 3)]
        for product in standard.products
    ] == [
        ["750", "750", "900"], ["550", "550", "700"], ["550", None, "650"],
        ["400", None, "580"], ["300", None, "400"], ["300", None, "430"],
    ]
    assert all(
        any("缺级" in note for note in product.indicators[0].notes) == (product is not standard.products[0] and product is not standard.products[1])
        for product in standard.products
    )
    assert {reference.page for product in standard.products for reference in product.indicators[0].source_references} >= {3, 4, 5, 6, 7}


def test_gb29450_direct_values_grade_at_level_one_boundary() -> None:
    standard = _gb29450_published()
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


def test_gb29450_fine_yarn_detail_formula_three() -> None:
    standard = _gb29450_published()
    product = standard.products[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 1, 1),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={
            "glass_fiber.pool.yarn_mode": InputValue(value="单纯细纱"),
            "glass_fiber.pool.fine_yarn_gt5um_t": InputValue(value="8", unit="t"),
            "glass_fiber.pool.fine_yarn_le5um_t": InputValue(value="2", unit="t"),
        },
        energy_lines=_gb29450_energy_lines("9000"),
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("9000") / Decimal("11")
    assert result.grade is Grade.LEVEL_3
    assert any("Gyz9" in step.expression for step in result.calculation_trace)


def test_gb29450_mixed_pool_yarn_formulas_four_and_five() -> None:
    standard = _gb29450_published()
    coarse = standard.products[1]
    coarse_request = EvaluationRequest(
        evaluation_date=date(2025, 1, 1), standard_id=standard.id, product_id=coarse.id,
        input_mode=InputMode.DETAIL,
        inputs={
            "glass_fiber.pool.yarn_mode": InputValue(value="混合型窑（粗纱为主体）"),
            "glass_fiber.pool.coarse_yarn_t": InputValue(value="10", unit="t"),
            "glass_fiber.pool.fine_yarn_total_t": InputValue(value="5", unit="t"),
        },
        energy_lines=_gb29450_energy_lines("1700"),
    )
    coarse_result = EvaluationEngine().evaluate(standard, coarse_request).results[0]
    assert coarse_result.actual_value == Decimal("100")
    assert coarse_result.grade is Grade.LEVEL_1
    assert any("公式4" in step.expression for step in coarse_result.calculation_trace)

    fine = standard.products[0]
    fine_request = EvaluationRequest(
        evaluation_date=date(2025, 1, 1), standard_id=standard.id, product_id=fine.id,
        input_mode=InputMode.DETAIL,
        inputs={
            "glass_fiber.pool.yarn_mode": InputValue(value="混合型窑（细纱为主体）"),
            "glass_fiber.pool.fine_yarn_gt5um_t": InputValue(value="8", unit="t"),
            "glass_fiber.pool.fine_yarn_le5um_t": InputValue(value="2", unit="t"),
            "glass_fiber.pool.coarse_yarn_t": InputValue(value="7", unit="t"),
        },
        energy_lines=_gb29450_energy_lines("1500"),
    )
    fine_result = EvaluationEngine().evaluate(standard, fine_request).results[0]
    assert fine_result.actual_value == Decimal("100")
    assert fine_result.grade is Grade.LEVEL_1
    assert any("公式5" in step.expression for step in fine_result.calculation_trace)


def test_gb29450_crucible_yarn_uses_table_four_conversion_factor() -> None:
    standard = _gb29450_published()
    product = standard.products[-1]
    request = EvaluationRequest(
        evaluation_date=date(2025, 1, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL, inputs={}, energy_lines=_gb29450_energy_lines("300"),
        production_lines=[
            ProductionLine(line_id="fine", product_name="细纱", quantity="10", unit="t", conversion_factor="0.5"),
            ProductionLine(line_id="coarse", product_name="粗纱", quantity="2", unit="t", conversion_factor="1"),
        ],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("300") / Decimal("7")
    assert result.grade is Grade.LEVEL_1
    assert any(step.operation == "production_line" and "0.5" in step.expression for step in result.calculation_trace)


def test_gb29450_missing_pool_yarn_mode_is_incomplete() -> None:
    standard = _gb29450_published()
    product = standard.products[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 1, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={
            "glass_fiber.pool.fine_yarn_gt5um_t": InputValue(value="8", unit="t"),
            "glass_fiber.pool.fine_yarn_le5um_t": InputValue(value="2", unit="t"),
        },
        energy_lines=_gb29450_energy_lines("9000"),
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert any("glass_fiber.pool.yarn_mode" in warning for warning in result.warnings)


def test_gb29450_missing_level_two_is_preserved_in_grading() -> None:
    standard = _gb29450_published()
    product = standard.products[2]
    indicator = product.indicators[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 1, 1), standard_id=standard.id, product_id=product.id,
        input_mode=InputMode.DIRECT,
        inputs={indicator.direct_input_key: InputValue(value="600", unit="kgce/t")},
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.LEVEL_3
    assert result.base_thresholds == {"LEVEL_1": Decimal("550"), "LEVEL_3": Decimal("650")}
