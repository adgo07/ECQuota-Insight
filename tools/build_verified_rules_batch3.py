"""Transcribe additional exact grade tables from the mandatory source PDFs."""
from __future__ import annotations

from build_verified_rules_batch1 import DATA, constant, input_def, input_node, node, one_product, indicator
from build_verified_rules_batch2 import custom_indicator, detail_input, write_definition


def build_30180() -> None:
    number = "GB 30180-2024"
    rows = [
        ("mto", "煤制烯烃（甲醇制烯烃MTO，原料用能不纳入）", "kgce/t", ["900", "1200", "1600"], 8, "表1"),
        ("mtp", "煤制烯烃（甲醇制丙烯MTP，原料用能不纳入）", "kgce/t", ["3200", "3450", "3800"], 8, "表1"),
        ("synthetic-natural-gas", "煤制天然气单位产品能耗", "kgce/m³", ["1.1", "1.2", "1.4"], 8, "表2"),
        ("direct-liquefaction-oil", "煤直接液化制油单位产品能耗", "kgce/toe", ["1150", "1300", "1500"], 8, "表3"),
        ("indirect-liquefaction-oil", "煤间接液化制油单位产品能耗", "kgce/toe", ["2000", "2200", "2700"], 8, "表4"),
        ("mto-feedstock-included", "煤制烯烃（甲醇制烯烃MTO，不扣除原料用能）", "kgce/t", ["2600", "2800", "3300"], 12, "附录A表A.1"),
        ("mtp-feedstock-included", "煤制烯烃（甲醇制丙烯MTP，不扣除原料用能）", "kgce/t", ["4500", "5200", "6000"], 12, "附录A表A.1"),
    ]
    write_definition(number, [one_product(indicator(number, ident, name, unit, values, page=page, table=table), name)
                              for ident, name, unit, values, page, table in rows])


def build_32047() -> None:
    number = "GB 32047-2025"
    ind = indicator(number, "beer", "啤酒单位产品综合能耗", "kgce/kL", ["26", "35", "60"], page=5, table="表1")
    write_definition(number, [one_product(ind, "啤酒单位产品综合能耗")])


def build_45549() -> None:
    number = "GB 45549-2025"
    rows = [
        ("flake-graphite", "鳞片石墨单位产品综合能耗", ["125", "155", "215"], "表1"),
        ("microcrystalline-graphite", "微晶石墨单位产品综合能耗", ["60", "75", "95"], "表1"),
        ("fluorite-lump", "萤石块矿单位产品综合能耗", ["8", "10", "13"], "表2"),
        ("fluorite-powder", "萤石粉矿单位产品综合能耗", ["15", "20", "25"], "表2"),
        ("fluorite-fine-two-stage", "萤石精粉单位产品综合能耗（两段磨矿工艺）", ["20", "25", "32"], "表2"),
        ("fluorite-fine-three-stage", "萤石精粉单位产品综合能耗（三段磨矿工艺）", ["55", "80", "110"], "表2"),
        ("fluorite-fine-comprehensive", "萤石精粉单位产品综合能耗（综合利用工艺）", ["35", "56", "75"], "表2"),
    ]
    write_definition(number, [one_product(indicator(number, ident, name, "kgce/t", values, page=6, table=table), name)
                              for ident, name, values, table in rows])


def build_46029() -> None:
    number = "GB 46029-2025"
    rows = [
        ("silver-process", "银法甲醛单位产品综合能耗", ["680", "700", "740"]),
        ("iron-molybdenum-process", "铁钼法甲醛单位产品综合能耗", ["615", "635", "670"]),
    ]
    write_definition(number, [one_product(indicator(number, ident, name, "kgce/t", values, page=6, table="表1"), name)
                              for ident, name, values in rows])


def build_31335() -> None:
    number = "GB 31335-2024"
    rows = [
        ("surface-medium-plus", "铁矿露天开采（中型及以上矿山）单位产品可比综合能耗", ["0.28", "0.45", "0.69"]),
        ("surface-small", "铁矿露天开采（小型矿山）单位产品可比综合能耗", ["0.36", "0.59", "0.90"]),
        ("underground-medium-plus", "铁矿地下开采（中型及以上矿山）单位产品可比综合能耗", ["1.45", "2.18", "3.36"]),
        ("underground-small", "铁矿地下开采（小型矿山）单位产品可比综合能耗", ["1.89", "2.83", "4.37"]),
        ("beneficiation-weak-magnetic", "铁矿选矿（弱磁选）单位产品可比综合能耗", ["1.80", "2.50", "3.46"]),
        ("beneficiation-combined", "铁矿选矿（联合选别）单位产品可比综合能耗", ["2.42", "3.70", "5.70"]),
        ("roasting-rotary-kiln", "铁矿选矿（焙烧选别，回转窑）单位产品可比综合能耗", ["49.70", "51.80", "54.30"]),
        ("roasting-shaft-furnace", "铁矿选矿（焙烧选别，竖炉）单位产品可比综合能耗", ["42.00", "44.00", "45.60"]),
        ("roasting-fluidized", "铁矿选矿（焙烧选别，流态化）单位产品可比综合能耗", ["40.00", "43.00", "45.00"]),
    ]
    adjustment_key = "condition.adjustment_factor"
    adjustment = detail_input(adjustment_key, "铁矿调整系数K", "1", "按附录A、B、C公式和查表区间计算，可采用内插或外延法。")
    base_detail = node("per_unit", args=[input_node("energy.total_standard_coal"), input_node("production.total_equivalent")], unit="kgce/t", label="单位产品综合能耗")
    detail = node("multiply", args=[base_detail, input_node(adjustment_key)], unit="kgce/t", label="调整系数修正后可比综合能耗")
    products = []
    for ident, name, vals in rows:
        extra = [adjustment] if not ident.startswith("roasting-") else []
        formula = detail if extra else base_detail
        notes = ["original_pdf_transcribed", "adjustment_factor_formula_clause_6.2.3", "requires_independent_review"]
        products.append(one_product(custom_indicator(number, ident, name, "kgce/t", vals, page=6, table="表1", detail_formula=formula, extra_inputs=extra, notes=notes), name))
    write_definition(number, products)


if __name__ == "__main__":
    build_30180(); build_32047(); build_45549(); build_46029(); build_31335()
    print("已按原文重建GB 30180、32047、31335、45549、46029；均为reviewed，尚未published。")
