from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from uebench.domain.engine import EvaluationEngine
from uebench.domain.models import EnergyLine, EvaluationRequest, InputMode, InputValue, ProductionLine, PublicationStatus, StandardDefinition


ROOT = Path("work/next-scope-65/data")


def _definitions() -> list[StandardDefinition]:
    return [
        StandardDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "definitions").glob("*.json"))
    ]


def test_next_scope_has_65_unique_standards_and_expected_replacement() -> None:
    scope = json.loads((ROOT / "scope-65.json").read_text(encoding="utf-8"))
    definitions = _definitions()
    numbers = {definition.number for definition in definitions}
    assert len(scope["standards"]) == 65
    assert numbers == set(scope["standards"])
    assert "GB 29447-2022" not in numbers
    assert {"GB 29447-2026", "GB 47834-2026", "GB 47835-2026"} <= numbers


def test_next_scope_published_and_draft_counts_are_explicit() -> None:
    definitions = _definitions()
    statuses = {definition.publication_status for definition in definitions}
    assert statuses == {PublicationStatus.PUBLISHED, PublicationStatus.DRAFT}
    assert sum(definition.publication_status is PublicationStatus.PUBLISHED for definition in definitions) == 46
    assert sum(definition.publication_status is PublicationStatus.DRAFT for definition in definitions) == 19
    assert all(definition.products for definition in definitions)
    assert all(product.indicators for definition in definitions for product in definition.products)


def test_next_scope_draft_rules_keep_source_citations() -> None:
    for definition in _definitions():
        for product in definition.products:
            for indicator in product.indicators:
                assert indicator.source_references
                assert all(reference.standard_number == definition.number for reference in indicator.source_references)
                assert all(reference.page >= 1 for reference in indicator.source_references)


def test_gb21345_product_and_indicator_names_follow_confirmation_convention() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 21345-2024")
    product = definition.products[0]
    indicator = product.indicators[0]
    assert product.name == "电炉法黄磷"
    assert indicator.name == "单位产品综合能耗"
    assert {reference.page for reference in indicator.source_references} >= {6, 8, 9}


def test_gb21345_refined_detail_formula_uses_standard_categories_and_formula() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 21345-2024")
    standard = definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
    product = standard.products[0]
    indicator = product.indicators[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 5, 1),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={
            "yellow_phosphorus.feedstock.p2o5_pct": InputValue(value="10", unit="%"),
            "yellow_phosphorus.feedstock.fe2o3_pct": InputValue(value="1", unit="%"),
            "yellow_phosphorus.feedstock.co2_pct": InputValue(value="2", unit="%"),
            "yellow_phosphorus.product.qualified_t": InputValue(value="10", unit="t"),
            "yellow_phosphorus.product.phosphoric_acid_mass_fraction": InputValue(value="0", unit="fraction"),
            "yellow_phosphorus.product.phosphoric_acid_production_t": InputValue(value="0", unit="t"),
            "yellow_phosphorus.product.phosphoric_acid_external_yellow_phosphorus_t": InputValue(value="0", unit="t"),
            "yellow_phosphorus.product.other_chemical_phosphorus_fraction": InputValue(value="0", unit="fraction"),
            "yellow_phosphorus.product.other_chemical_production_t": InputValue(value="0", unit="t"),
            "yellow_phosphorus.product.other_chemical_external_yellow_phosphorus_t": InputValue(value="0", unit="t"),
            "yellow_phosphorus.product.external_mud_recovered_t": InputValue(value="0", unit="t"),
        },
        energy_lines=[
            EnergyLine(line_id="carbon", energy_name="炭质还原剂", category_key="carbon_reducing", amount="100", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
            EnergyLine(line_id="furnace", energy_name="电炉加热电量", category_key="furnace_electricity", amount="200000", unit="kWh", standard_coal_coefficient="1", coefficient_unit="kWh/kWh"),
            EnergyLine(line_id="other", energy_name="生产系统其他能源", category_key="production_other", amount="50", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
            EnergyLine(line_id="aux", energy_name="辅助附属系统", category_key="auxiliary_affiliated", amount="20", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
            EnergyLine(line_id="output", energy_name="界区外输出能源", category_key="external_output", direction="output", amount="0", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        ],
        production_lines=[ProductionLine(line_id="pp", product_name="黄磷", category_key="qualified", quantity="10", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.indicator_id == indicator.id
    assert result.grade is not None
    assert result.actual_value is not None
    assert result.actual_value > Decimal("0")
    assert result.grade.value == "LEVEL_1"
    assert any(step.operation == "divide" and step.unit == "kgce/t" for step in result.calculation_trace)


def test_gb21345_formula9_and_formula10_derive_product_output() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 21345-2024")
    standard = definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
    product = standard.products[0]
    indicator = product.indicators[0]
    request = EvaluationRequest(
        evaluation_date=date(2025, 5, 1),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={
            "yellow_phosphorus.feedstock.p2o5_pct": InputValue(value="10", unit="%"),
            "yellow_phosphorus.feedstock.fe2o3_pct": InputValue(value="1", unit="%"),
            "yellow_phosphorus.feedstock.co2_pct": InputValue(value="2", unit="%"),
            "yellow_phosphorus.product.qualified_t": InputValue(value="10", unit="t"),
            "yellow_phosphorus.product.phosphoric_acid_mass_fraction": InputValue(value="0.8", unit="fraction"),
            "yellow_phosphorus.product.phosphoric_acid_production_t": InputValue(value="1", unit="t"),
            "yellow_phosphorus.product.phosphoric_acid_external_yellow_phosphorus_t": InputValue(value="0.1", unit="t"),
            "yellow_phosphorus.product.other_chemical_phosphorus_fraction": InputValue(value="0.5", unit="fraction"),
            "yellow_phosphorus.product.other_chemical_production_t": InputValue(value="1", unit="t"),
            "yellow_phosphorus.product.other_chemical_external_yellow_phosphorus_t": InputValue(value="0.05", unit="t"),
            "yellow_phosphorus.product.external_mud_recovered_t": InputValue(value="0.2", unit="t"),
        },
        energy_lines=[
            EnergyLine(line_id="carbon", energy_name="炭质还原剂", category_key="carbon_reducing", amount="100", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
            EnergyLine(line_id="furnace", energy_name="电炉加热电量", category_key="furnace_electricity", amount="200000", unit="kWh", standard_coal_coefficient="1", coefficient_unit="kWh/kWh"),
            EnergyLine(line_id="other", energy_name="生产系统其他能源", category_key="production_other", amount="50", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
            EnergyLine(line_id="aux", energy_name="辅助附属系统", category_key="auxiliary_affiliated", amount="20", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
            EnergyLine(line_id="output", energy_name="界区外输出能源", category_key="external_output", direction="output", amount="0", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
        ],
        production_lines=[ProductionLine(line_id="pp", product_name="黄磷", category_key="qualified", quantity="10", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    expected_pp = Decimal("10") + Decimal("0.3163") * Decimal("0.8") * Decimal("1") - Decimal("0.1") + Decimal("0.5") * Decimal("1") - Decimal("0.05") - Decimal("0.2")
    assert result.grade.value == "LEVEL_1"
    assert any(step.operation == "subtract" and step.label == "黄磷产品产量 PP（公式8）" and step.value == expected_pp for step in result.calculation_trace)
    assert any(step.label == "泥磷制磷酸折合黄磷量 PPS（公式9）" for step in result.calculation_trace)
    assert any(step.label == "泥磷制其他化学品折合黄磷量 PPH（公式10）" for step in result.calculation_trace)


def test_gb29441_refined_levels_and_detail_formula() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 29441-2012")
    standard = definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
    product = standard.products[0]
    indicator = product.indicators[0]
    direct = EvaluationRequest(
        evaluation_date=date(2013, 10, 1),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DIRECT,
        inputs={indicator.direct_input_key: InputValue(value="160", unit="kgce/t")},
    )
    assert EvaluationEngine().evaluate(standard, direct).results[0].grade.value == "LEVEL_3"
    detail = direct.model_copy(update={
        "input_mode": InputMode.DETAIL,
        "inputs": {},
        "energy_lines": [EnergyLine(
            line_id="e1", energy_name="综合能源", amount="2000", unit="kgce",
            standard_coal_coefficient="1", coefficient_unit="kgce/kgce",
        )],
        "production_lines": [ProductionLine(
            line_id="p1", product_name="稀硝酸", quantity="10", unit="t",
        )],
    })
    result = EvaluationEngine().evaluate(standard, detail).results[0]
    assert result.actual_value == Decimal("200")
    assert result.grade.value == "NOT_QUALIFIED"


def test_gb29437_refined_process_rows_keep_distinct_thresholds() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 29437-2012")
    standard = definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
    assert [product.name for product in standard.products] == [
        "羰基法（年产20万t及以上醋酸）",
        "酒精法—空气氧化乙醛",
        "酒精法—氧气氧化乙醛",
        "乙烯法",
    ]
    thresholds = [
        [indicator.thresholds.level_1.value, indicator.thresholds.level_2.value, indicator.thresholds.level_3.value]
        for product in standard.products
        for indicator in product.indicators
    ]
    assert thresholds == [["106", "124", "176"], ["418", "418", "500"], ["429", "429", "505"], ["300", "300", "429"]]


def test_gb30182_refined_comprehensive_and_electricity_indicators() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 30182-2013")
    standard = definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
    product = standard.products[0]
    assert len(product.indicators) == 2
    direct_inputs = {
        indicator.direct_input_key: InputValue(value=value, unit=indicator.unit)
        for indicator, value in zip(product.indicators, ("115", "800"), strict=True)
    }
    request = EvaluationRequest(
        evaluation_date=date(2014, 12, 1),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DIRECT,
        inputs=direct_inputs,
    )
    results = EvaluationEngine().evaluate(standard, request).results
    assert [result.grade.value for result in results] == ["LEVEL_1", "LEVEL_1"]
    detail = request.model_copy(update={
        "input_mode": InputMode.DETAIL,
        "inputs": {},
        "energy_lines": [
            EnergyLine(line_id="fuel", energy_name="燃料", amount="100", unit="kgce", standard_coal_coefficient="1", coefficient_unit="kgce/kgce"),
            EnergyLine(line_id="electricity", energy_name="直接电力", category_key="direct_electricity", amount="800", unit="kWh", standard_coal_coefficient="1", coefficient_unit="kWh/kWh"),
        ],
        "production_lines": [ProductionLine(line_id="p1", product_name="摩擦材料", quantity="1", unit="t")],
    })
    detail_results = EvaluationEngine().evaluate(standard, detail).results
    assert detail_results[0].actual_value == Decimal("900")
    assert detail_results[1].actual_value == Decimal("800")


def test_gb29450_refined_fine_yarn_uses_formula_3_output_equivalent() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 29450-2012")
    standard = definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
    fine_product = standard.products[0]
    assert fine_product.name.startswith("池窑法E玻璃纤维纱")
    indicator = fine_product.indicators[0]
    request = EvaluationRequest(
        evaluation_date=date(2013, 10, 1),
        standard_id=standard.id,
        product_id=fine_product.id,
        input_mode=InputMode.DETAIL,
        inputs={
            "glass_fiber.fine_yarn.gt5um_t": InputValue(value="8", unit="t"),
            "glass_fiber.fine_yarn.le5um_t": InputValue(value="2", unit="t"),
        },
        energy_lines=[EnergyLine(
            line_id="e1", energy_name="玻璃纤维纱能源", amount="9000", unit="kgce",
            standard_coal_coefficient="1", coefficient_unit="kgce/kgce",
        )],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("9000") / Decimal("11")
    assert result.grade.value == "LEVEL_3"
    assert any("Gyz9" in step.label for step in result.calculation_trace)


def test_gb36890_refined_temperature_and_firing_rows() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 36890-2018")
    standard = definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
    assert len(standard.products) == 5
    assert [product.indicators[0].thresholds.level_3.value for product in standard.products] == [
        "740", "860", "1050", "640", "980",
    ]
    request = EvaluationRequest(
        evaluation_date=date(2019, 12, 1),
        standard_id=standard.id,
        product_id=standard.products[1].id,
        input_mode=InputMode.DETAIL,
        inputs={},
        energy_lines=[EnergyLine(
            line_id="e1", energy_name="日用瓷能源", amount="860", unit="kgce",
            standard_coal_coefficient="1", coefficient_unit="kgce/kgce",
        )],
        production_lines=[ProductionLine(line_id="p1", product_name="日用瓷", quantity="1", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("860")
    assert result.grade.value == "LEVEL_3"


def test_gb40878_refined_process_rows() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 40878-2021")
    standard = definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
    assert [product.name for product in standard.products] == [
        "以淀粉为原料发酵法", "以淀粉为原料酶法", "以葡萄糖为原料催化氧化法",
    ]
    assert [product.indicators[0].thresholds.level_1.value for product in standard.products] == ["272", "260", "156"]
    request = EvaluationRequest(
        evaluation_date=date(2022, 11, 1),
        standard_id=standard.id,
        product_id=standard.products[0].id,
        input_mode=InputMode.DETAIL,
        inputs={},
        energy_lines=[EnergyLine(
            line_id="e1", energy_name="葡萄糖酸钠能源", amount="280", unit="kgce",
            standard_coal_coefficient="1", coefficient_unit="kgce/kgce",
        )],
        production_lines=[ProductionLine(line_id="p1", product_name="葡萄糖酸钠", quantity="1", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("280")
    assert result.grade.value == "LEVEL_2"


def test_gb36887_refined_synthetic_leather_and_dmf_rows() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 36887-2018")
    standard = definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
    assert len(standard.products) == 6
    assert standard.products[-1].name == "DMF回收"
    assert standard.products[-1].indicators[0].unit == "kgce/tdmf"
    request = EvaluationRequest(
        evaluation_date=date(2019, 12, 1),
        standard_id=standard.id,
        product_id=standard.products[-1].id,
        input_mode=InputMode.DETAIL,
        inputs={},
        energy_lines=[EnergyLine(
            line_id="e1", energy_name="DMF回收能耗", amount="350", unit="kgce",
            standard_coal_coefficient="1", coefficient_unit="kgce/kgce",
        )],
        production_lines=[ProductionLine(line_id="p1", product_name="DMF", quantity="1", unit="tdmf")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("350")
    assert result.grade.value == "LEVEL_1"


def test_gb40877_refined_fiber_temperature_and_forming_rows() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 40877-2021")
    standard = definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
    assert len(standard.products) == 5
    assert [product.indicators[0].thresholds.level_3.value for product in standard.products] == [
        "263", "311", "85", "486", "836",
    ]
    request = EvaluationRequest(
        evaluation_date=date(2022, 11, 1),
        standard_id=standard.id,
        product_id=standard.products[2].id,
        input_mode=InputMode.DETAIL,
        inputs={},
        energy_lines=[EnergyLine(
            line_id="e1", energy_name="针刺毯能源", amount="85", unit="kgce",
            standard_coal_coefficient="1", coefficient_unit="kgce/kgce",
        )],
        production_lines=[ProductionLine(line_id="p1", product_name="针刺毯", quantity="1", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("85")
    assert result.grade.value == "LEVEL_3"


def test_gb32044_refined_sugar_process_rows() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 32044-2015")
    standard = definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
    assert [product.name for product in standard.products] == ["甘蔗制糖", "甜菜制糖", "炼糖"]
    assert [product.indicators[0].thresholds.level_1.value for product in standard.products] == ["225", "318", "200"]
    request = EvaluationRequest(
        evaluation_date=date(2016, 10, 1),
        standard_id=standard.id,
        product_id=standard.products[0].id,
        input_mode=InputMode.DETAIL,
        inputs={},
        energy_lines=[EnergyLine(
            line_id="e1", energy_name="甘蔗制糖能源", amount="225", unit="kgce",
            standard_coal_coefficient="1", coefficient_unit="kgce/kgce",
        )],
        production_lines=[ProductionLine(line_id="p1", product_name="糖", quantity="1", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("225")
    assert result.grade.value == "LEVEL_1"


def test_gb29435_refined_rare_earth_rows_and_tce_conversion() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 29435-2012")
    standard = definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
    assert len(standard.products) == 31
    assert standard.products[0].name == "氧化镧"
    assert standard.products[13].name == "灯用稀土三基色荧光粉（红）"
    assert standard.products[-1].name == "稀土抛光粉"
    assert standard.products[0].indicators[0].thresholds.level_1.value == "2.19"
    request = EvaluationRequest(
        evaluation_date=date(2013, 10, 1),
        standard_id=standard.id,
        product_id=standard.products[0].id,
        input_mode=InputMode.DETAIL,
        inputs={},
        energy_lines=[EnergyLine(
            line_id="e1", energy_name="氧化镧综合能耗", amount="2190", unit="kgce",
            standard_coal_coefficient="1", coefficient_unit="kgce/kgce",
        )],
        production_lines=[ProductionLine(line_id="p1", product_name="氧化镧", quantity="1", unit="t")],
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal("2.19")
    assert result.grade.value == "LEVEL_1"


def test_remaining_table_driven_rows_are_named_and_calculable() -> None:
    expected = {
        "GB 30185-2025": (7, "kgce/10^4m2", "铝塑复合板—热压复合装饰板", "2400"),
        "GB 30530-2024": (1, "kgce/t", "二甲基硅氧烷（水解物、环体和线性体）", "650"),
        "GB 31830-2024": (2, "kgce/t", "甲苯二异氰酸酯（TDI）", "340"),
        "GB 32051-2024": (6, "kgce/t", "钛白粉—金红石型（硫酸法）", "860"),
        "GB 45246-2025": (6, "kgce/m3", "中密度纤维板", "118"),
    }
    for number, (count, unit, first_name, first_level) in expected.items():
        definition = next(item for item in _definitions() if item.number == number)
        standard = definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})
        assert len(standard.products) == count
        assert standard.products[0].name == first_name
        indicator = standard.products[0].indicators[0]
        assert indicator.unit == unit
        assert indicator.thresholds.level_1.value == first_level
        request = EvaluationRequest(
            evaluation_date=standard.effective_date,
            standard_id=standard.id,
            product_id=standard.products[0].id,
            input_mode=InputMode.DETAIL,
            inputs={},
            energy_lines=[EnergyLine(
                line_id="e1", energy_name="综合能耗", amount=first_level, unit="kgce",
                standard_coal_coefficient="1", coefficient_unit="kgce/kgce",
            )],
            production_lines=[ProductionLine(
                line_id="p1", product_name=first_name, quantity="1", unit=indicator.detail_formula.args[1].unit,
            )],
        )
        result = EvaluationEngine().evaluate(standard, request).results[0]
        assert result.grade.value == "LEVEL_1"


def test_complex_draft_rows_block_unreviewed_detail_formulas() -> None:
    expected = {
        "GB 29145-2023": (6, "钨精矿—黑钨"),
        "GB 31823-2021": (3, "集装箱码头"),
        "GB 32032-2024": (16, "金矿开采—露天开采"),
    }
    for number, (count, first_name) in expected.items():
        definition = next(item for item in _definitions() if item.number == number)
        assert len(definition.products) == count
        assert definition.products[0].name == first_name
        assert all(indicator.detail_formula is None
                   for product in definition.products for indicator in product.indicators)
