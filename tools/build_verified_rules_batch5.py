"""Transcribe the grade tables of GB 30251-2024."""
from __future__ import annotations

from build_verified_rules_batch1 import indicator, one_product
from build_verified_rules_batch2 import custom_indicator, write_definition


def build_30251() -> None:
    number = "GB 30251-2024"
    rows = [
        ("refinery", "炼油单位能量因数能耗", "kgoe/(t·能量因数)", ["6.85", "7.50", "8.50"], "表1", 7),
        ("ethylene", "乙烯装置单位产品综合能耗", "kgoe/t", ["580", "590", "640"], "表2", 7),
        ("polypropylene-gas", "聚丙烯单位产品综合能耗（连续气相法）", "kgoe/t", ["48", "54", "79"], "表3", 7),
        ("polypropylene-liquid", "聚丙烯单位产品综合能耗（连续液相本体法）", "kgoe/t", ["51", "64", "95"], "表3", 7),
        ("styrene-dehydrogenation", "苯乙烯单位产品综合能耗（纯乙烯法、乙苯脱氢法）", "kgoe/t", ["238", "260", "362"], "表4", 8),
        ("styrene-dry-gas", "苯乙烯单位产品综合能耗（干气法）", "kgoe/t", ["424", "480", "545"], "表4", 8),
        ("styrene-cooxidation", "苯乙烯单位产品综合能耗（乙苯共氧化法）", "kgoe/t", ["270", "315", "320"], "表4", 8),
        ("p-xylene", "对二甲苯单位产品综合能耗", "kgoe/t", ["370", "380", "550"], "表5", 8),
        ("pta", "精对苯二甲酸单位产品综合能耗", "kgce/t", ["70", "80", "180"], "表6", 8),
        ("propylene-oxide-cooxidation", "环氧丙烷单位产品综合能耗（乙苯共氧化法）", "kgce/t", ["386", "450", "457"], "表7", 9),
        ("propylene-oxide-isobutane", "环氧丙烷单位产品综合能耗（异丁烷共氧化法）", "kgce/t", ["280", "345", "390"], "表7", 9),
        ("propylene-oxide-hydrogen-peroxide", "环氧丙烷单位产品综合能耗（过氧化氢法）", "kgce/t", ["480", "545", "550"], "表7", 9),
        ("phthalic-anhydride", "邻苯二甲酸酐单位产品综合能耗", "kgce/t", ["-296", "-249", "-111"], "表8", 9),
    ]
    products = [one_product(indicator(number, ident, name, unit, vals, page=page, table=table), name)
                for ident, name, unit, vals, table, page in rows]
    # Chlorohydrin PO has no level-1 or level-2 limit; the source explicitly
    # uses em dashes, so keep it as a separate product with a null gap.
    chlorohydrin = custom_indicator(number, "propylene-oxide-chlorohydrin", "环氧丙烷单位产品综合能耗（氯醇法）", "kgce/t", [None, None, "380"], page=9, table="表7", notes=["original_pdf_transcribed", "缺级：原文1级、2级为—，保留空值", "requires_independent_review"])
    products.insert(8, one_product(chlorohydrin, "环氧丙烷单位产品综合能耗（氯醇法）"))
    write_definition(number, products)


if __name__ == "__main__":
    build_30251()
    print("已按GB 30251-2024表1至表8重建规则；状态为reviewed，尚未published。")
