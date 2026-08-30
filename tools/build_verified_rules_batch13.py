"""Rebuild GB 45247-2025 Table 1 and preserve its correction-factor inputs."""
from __future__ import annotations

from build_verified_rules_batch1 import constant, input_def, input_node, indicator, node, one_product, write_definition


def main() -> None:
    number = "GB 45247-2025"
    power_factor = input_def(
        "condition.gb45247.power_total_factor", "供电煤耗率影响因素总修正系数", "1",
        description="按5.3.1～5.3.7计算并相乘；供热机组还需包含供热修正系数。不能确定时不得猜测。",
    )
    air_addition = input_def(
        "condition.gb45247.air_cooling_addition", "空气冷却供电煤耗率增加值", "gce/(kW·h)",
        description="新建、扩建、改建且采用空气冷却时填5；其他情况填0。",
    )
    power_rows = [
        ("H级", "500", ["201", "210", "215"]),
        ("F级", "400", ["203", "215", "223"]),
        ("F级", "300", ["206", "219", "227"]),
        ("F级", "100", ["220", "232", "241"]),
        ("E级", "100", ["232", "245", "259"]),
    ]
    products = []
    for index, (kind, capacity, values) in enumerate(power_rows, 1):
        name = f"燃气-蒸汽联合循环发电机组（{kind}/{capacity}MW）供电煤耗率"
        threshold_exprs = [
            node("multiply", args=[constant(values[0], "gce/(kW·h)"), input_node(power_factor["key"])], unit="gce/(kW·h)"),
            node("add", args=[constant(values[1], "gce/(kW·h)"), input_node(air_addition["key"])], unit="gce/(kW·h)"),
            node("multiply", args=[constant(values[2], "gce/(kW·h)"), input_node(power_factor["key"])], unit="gce/(kW·h)"),
        ]
        ind = indicator(number, f"power-{index}", name, "gce/(kW·h)", values, page=6, table="表1",
                        extra_inputs=[power_factor, air_addition], notes=[
                            "original_pdf_transcribed", "power_correction_formula_clause_5_3", "air_cooling_addition_table_5_2", "requires_independent_review"
                        ])
        ind["thresholds"] = {f"level_{i}": expr for i, expr in enumerate(threshold_exprs, 1)}
        products.append(one_product(ind, name))
        heat_name = f"燃气-蒸汽联合循环发电机组（{kind}/{capacity}MW）供热煤耗率"
        heat_ind = indicator(number, f"heat-{index}", heat_name, "kgce/GJ", ["38", "38.5", "39"], page=6, table="表1",
                             notes=["original_pdf_transcribed", "heating_rate_is_not_corrected_clause_5_3", "requires_independent_review"])
        products.append(one_product(heat_ind, heat_name))
    assert len(products) == 10
    write_definition(number, products)
    print("已按GB 45247-2025原文表1重建10项规则；状态为reviewed，尚未published。")


if __name__ == "__main__":
    main()
