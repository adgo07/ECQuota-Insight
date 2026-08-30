"""Rebuild GB 21340-2019 from the original tables (pages 2-4)."""
from __future__ import annotations

from build_verified_rules_batch1 import constant, indicator, input_def, input_node, node, one_product, write_definition, source
from build_verified_rules_batch2 import custom_indicator


def corrected_thresholds(values: list[str], factor_keys: list[str]) -> list[dict]:
    factors = [input_node(key) for key in factor_keys]
    return [node("multiply", args=[constant(value, "kgce/重箱"), *factors], unit="kgce/重箱") for value in values]


def main() -> None:
    number = "GB 21340-2019"
    factor_defs = [
        input_def("condition.gb21340.a", "年平均产能利用率修正系数 a", "1", description="年平均产能利用率大于85%时按标准表2取1.1，否则填1.0。"),
        input_def("condition.gb21340.b", "厚度修正系数 b", "1", description="按表2厚度区间和产量占比加权；不适用时填1.0。"),
        input_def("condition.gb21340.c", "玻璃中铁含量修正系数 c", "1", description="按表2铁含量区间和产量占比加权；不适用时填1.0。"),
        input_def("condition.gb21340.d", "生产线调整修正系数 d", "1", description="生产线调整引起非正常生产时按标准表2取1.1，否则填1.0。"),
    ]
    products = []
    # 表1 has capacity-dependent rows.  The source gives no level 1/2 value
    # for <=500 t/d; preserve that gap rather than inventing a number.
    for ident, name, values in [
        ("flat-capacity-le-500", "平板玻璃（生产线设计生产能力≤500 t/d）", [None, None, "14.0"]),
        ("flat-capacity-500-800", "平板玻璃（500 t/d＜生产线设计生产能力≤800 t/d）", ["9.5", "11.5", "13.5"]),
        ("flat-capacity-gt-800", "平板玻璃（生产线设计生产能力＞800 t/d）", ["8.0", "10.0", "12.0"]),
    ]:
        base_expr = [constant(value, "kgce/重箱") if value is not None else None for value in values]
        thresholds = [expr for expr in corrected_thresholds([value or "0" for value in values], [x["key"] for x in factor_defs])]
        for i, value in enumerate(values):
            if value is None:
                thresholds[i] = None
        ind = custom_indicator(
            number, ident, name, "kgce/重箱", values, page=4, table="表1、表2",
            extra_inputs=factor_defs, threshold_exprs=thresholds,
            notes=["original_pdf_transcribed", "capacity_band_from_table_1", "correction_factor_formula_Vc=a×b×c×d", "缺级：≤500 t/d原文1级、2级为—，保留空值", "requires_independent_review"],
        )
        products.append(one_product(ind, name))

    glass_rows = [
        ("平面普通钢化玻璃", [["2.20", "2.30", "2.64", "3.22", "4.00", "5.38", "5.98", "7.18", "10.38"],
                           ["2.75", "2.87", "3.30", "4.02", "5.00", "6.73", "7.48", "8.98", "12.97"],
                           ["3.46", "3.58", "3.98", "4.39", "5.95", "7.43", "8.51", "10.01", "14.22"]]),
        ("平面低辐射镀膜钢化玻璃", [["2.73", "2.85", "3.27", "3.99", "4.96", "6.67", "7.42", "8.90", "12.87"],
                                  ["3.41", "3.56", "4.09", "4.98", "6.20", "8.35", "9.28", "11.14", "16.08"],
                                  ["4.29", "4.44", "4.94", "5.44", "7.38", "9.21", "10.55", "12.41", "17.63"]]),
        ("曲面普通钢化玻璃", [["2.88", "3.01", "3.46", "4.22", "5.24", "7.05", "7.83", "9.41", "13.60"],
                           ["3.60", "3.76", "4.32", "5.27", "6.55", "8.82", "9.80", "11.76", "16.99"],
                           ["4.53", "4.69", "5.21", "5.75", "7.79", "9.73", "11.15", "13.11", "18.63"]]),
        ("曲面低辐射镀膜钢化玻璃", [["3.56", "3.73", "4.28", "5.22", "6.48", "8.72", "9.69", "11.63", "16.82"],
                                  ["4.46", "4.65", "5.35", "6.51", "8.10", "10.90", "12.12", "14.55", "21.01"],
                                  ["5.61", "5.80", "6.45", "7.11", "9.64", "12.04", "13.79", "16.22", "23.04"]]),
    ]
    thicknesses = ["3", "4", "5", "6", "8", "10", "12", "15", "19"]
    for glass_name, level_rows in glass_rows:
        for thickness, values in zip(thicknesses, zip(*level_rows), strict=True):
            name = f"钢化玻璃/{glass_name}/{thickness} mm厚度"
            ind = indicator(number, f"tempered-{len(products)+1}", name, "kW·h/m²", list(values), page=5, table="表3",
                            notes=["original_pdf_transcribed", "thickness_column_from_table_3", "requires_independent_review"])
            products.append(one_product(ind, name))

    for ident, name, values in [
        ("rolled-solar-le-300", "光伏压延玻璃（生产线设计生产能力≤300 t/d）", ["300", "300", "400"]),
        ("rolled-solar-gt-300", "光伏压延玻璃（生产线设计生产能力＞300 t/d）", ["260", "260", "370"]),
        ("cast-stone", "铸石", ["540", "700", "800"]),
    ]:
        ind = indicator(number, ident, name, "kgce/t", values, page=6, table="表4" if "光伏" in name else "表5",
                        notes=["original_pdf_transcribed", "requires_independent_review"])
        products.append(one_product(ind, name))
    assert len(products) == 42, len(products)
    write_definition(number, products)
    print("已按GB 21340-2019原文表1至表5重建42项规则；状态为reviewed，尚未published。")


if __name__ == "__main__":
    main()
