"""Rebuild GB 21258-2024 Table 1 with exact capacity/pressure rows."""
from __future__ import annotations

from build_verified_rules_batch1 import constant, input_def, input_node, node, one_product, write_definition
from build_verified_rules_batch2 import custom_indicator


def scaled(value: str | None, unit: str, factor_key: str) -> dict | None:
    if value is None:
        return None
    return node("multiply", args=[constant(value, unit), input_node(factor_key)], unit=unit)


def power_thresholds(values: list[str | None], unit: str, factor_key: str, addition_key: str) -> list[dict | None]:
    result: list[dict | None] = []
    for level, value in enumerate(values, 1):
        if value is None:
            result.append(None)
            continue
        base = scaled(value, unit, factor_key)
        if level in (1, 3):
            base = node("add", args=[base, input_node(addition_key)], unit=unit)
        result.append(base)
    return result


def main() -> None:
    number = "GB 21258-2024"
    factor_key = "condition.gb21258.total_factor"
    addition_key = "condition.gb21258.power_addition"
    factors = [
        input_def(factor_key, "影响因素总修正系数", "1", description="按表3～表6及5.3.4、5.3.6计算；无法确定时不得猜测。"),
        input_def(addition_key, "供电煤耗率增加值", "gce/(kW·h)", description="常规空冷、“W”火焰炉或循环流化床机组按表2取值；不适用时填0。"),
    ]
    products = []
    power_rows = [
        ("超超临界", "1000", ["268", "276", "283"]),
        ("超超临界", "600", ["275", "282", "291"]),
        ("超临界", "600", ["286", "285", "299"]),
        ("超临界", "300", ["290", "285", "308"]),
        ("亚临界", "600", ["303", "285", "312"]),
        ("亚临界", "300", ["309", "285", "321"]),
        ("超高压", "200及以下", [None, None, "352"]),
    ]
    for index, (pressure, capacity, values) in enumerate(power_rows, 1):
        name = f"燃煤发电机组（{pressure}·{capacity}MW）供电煤耗率"
        ind = custom_indicator(
            number, f"power-{index}", name, "gce/(kW·h)", values, page=8, table="表1",
            extra_inputs=factors,
            threshold_exprs=power_thresholds(values, "gce/(kW·h)", factor_key, addition_key),
            notes=["original_pdf_transcribed", "power_addition_from_table_2", "influence_factor_formula_clause_5_3"] + (["缺级：超高压200 MW及以下原文1级、2级为—，保留空值"] if values[0] is None else []) + (["non_monotonic_source_values_preserved"] if values[1] and values[0] and values[0] > values[1] else []) + ["requires_independent_review"],
        )
        products.append(one_product(ind, name))

    heat_rows = [
        ("超超临界", "1000", ["40", "40.5", "42"]),
        ("超超临界", "600", ["40", "40.5", "42"]),
        ("超临界", "600", ["40", "40.5", "42"]),
        ("超临界", "300", ["40", "40.5", "42"]),
        ("亚临界", "600", ["40", "40.5", "42.5"]),
        ("亚临界", "300", ["40", "40.5", "42.5"]),
    ]
    for index, (pressure, capacity, values) in enumerate(heat_rows, 1):
        name = f"燃煤发电机组（{pressure}·{capacity}MW）供热煤耗率"
        threshold_exprs = [scaled(value, "kgce/GJ", factor_key) for value in values]
        ind = custom_indicator(
            number, f"heat-{index}", name, "kgce/GJ", values, page=8, table="表1",
            extra_inputs=[factors[0]], threshold_exprs=threshold_exprs,
            notes=["original_pdf_transcribed", "fuel_composition_correction_from_table_3", "heating_ratio_correction_clause_5_3_6", "requires_independent_review"],
        )
        products.append(one_product(ind, name))
    assert len(products) == 13
    write_definition(number, products)
    print("已按GB 21258-2024原文表1重建13项规则；状态为reviewed，尚未published。")


if __name__ == "__main__":
    main()
