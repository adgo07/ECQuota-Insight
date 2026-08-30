"""Rebuild small standards whose tables were visually checked in the original PDFs."""
from __future__ import annotations

from build_verified_rules_batch1 import indicator, one_product, write_definition


def build(number: str, rows: list[tuple[str, str, str, list[str], str, int]]) -> None:
    products = [
        one_product(indicator(number, ident, name, unit, values, page=page, table=table), name)
        for ident, name, unit, values, table, page in rows
    ]
    write_definition(number, products)


def main() -> None:
    build("GB 21347-2023", [
        ("industrial-silicon-charcoal", "工业硅（主还原剂为木炭）单位产品综合能耗", "kgce/t", ["2500", "2800", "3300"], "表1", 3),
        ("industrial-silicon-petcoke-coal", "工业硅（主还原剂为石油焦和煤混合）单位产品综合能耗", "kgce/t", ["2700", "3000", "3500"], "表1", 3),
        ("industrial-silicon-coal", "工业硅（主还原剂为煤）单位产品综合能耗", "kgce/t", ["2800", "3100", "3600"], "表1", 3),
        ("magnesium", "镁单位产品综合能耗", "kgce/t", ["3500", "4000", "5000"], "表1", 3),
    ])
    build("GB 29446-2019", [
        ("coking-coal", "炼焦煤选煤企业选煤电力单耗", "kW·h/t", ["5.0", "7.0", "8.5"], "表1", 3),
        ("power-coal", "动力煤选煤企业选煤电力单耗", "kW·h/t", ["2.0", "3.0", "4.5"], "表2", 3),
    ])
    # GB 29447-2022 was superseded by GB 29447-2026.  Its former hand-
    # transcribed rows are intentionally not rebuilt here: the 2026 rule
    # definition is maintained by tools/update_scope_46.py from the current
    # compulsory text and must not be silently overwritten with old values.
    build("GB 29448-2022", [
        ("sponge-titanium-full", "海绵钛全流程生产单位产品综合能耗", "kgce/t", ["4400", "4820", "5080"], "表1", 5),
        ("sponge-titanium-half", "海绵钛半流程生产单位产品综合能耗", "kgce/t", ["1000", "1100", "1230"], "表1", 5),
        ("titanium-ingot-two-melt", "钛锭二次真空自耗电弧熔炼单位产品综合能耗", "kgce/t", ["420", "480", "580"], "表2", 6),
        ("titanium-ingot-three-melt", "钛锭三次真空自耗电弧熔炼单位产品综合能耗", "kgce/t", ["790", "910", "1100"], "表2", 6),
    ])
    build("GB 30183-2013", [
        ("comparable-energy", "岩棉、矿渣棉及其制品单位产品可比综合能耗", "kgce/t", ["400.0", "450.0", "490.0"], "表1～表3", 4),
        ("comparable-coke", "岩棉、矿渣棉及其制品单位产品可比熔融焦耗", "kgce/t", ["210.0", "240.0", "260.0"], "表1～表3", 4),
    ])
    build("GB 30184-2013", [
        ("bituminous-with-carrier", "沥青基防水卷材（有胎）单位产品综合能耗", "kgce/km²", ["180", "200", "220"], "表1～表3", 4),
        ("bituminous-without-carrier", "沥青基防水卷材（无胎）单位产品综合能耗", "kgce/km²", ["90", "100", "130"], "表1～表3", 4),
    ])
    build("GB 36888-2018", [
        ("production", "预拌混凝土单位产品生产能耗", "kgce/m³", ["0.30", "0.70", "1.10"], "表1", 4),
        ("transport", "预拌混凝土单位产品运输能耗", "kgce/m³", ["1.85", "2.65", "2.90"], "表1", 4),
    ])
    build("GB 36891-2018", [
        ("sintered-mullite", "烧结莫来石单位产品能耗", "kgce/t", ["94", "135", "252"], "表1", 3),
        ("fused-mullite", "电熔莫来石单位产品电耗", "kW·h/t", ["1320", "1400", "1600"], "表2", 3),
    ])
    build("GB 36892-2018", [
        ("brown-fused-alumina", "棕刚玉单位产品电耗", "kW·h/t", ["2100", "2300", "2400"], "表1", 3),
        ("white-fused-alumina", "白刚玉单位产品电耗", "kW·h/t", ["1200", "1500", "1680"], "表1", 3),
        ("sub-white-fused-alumina", "亚白刚玉单位产品电耗", "kW·h/t", ["2750", "2800", "2950"], "表1", 3),
        ("dense-fused-alumina", "致密刚玉单位产品电耗", "kW·h/t", ["2300", "2400", "2600"], "表1", 3),
        ("sintered-corundum", "烧结刚玉单位产品能耗", "kgce/t", ["94", "109", "202"], "表2", 4),
    ])
    print("已按原文表格重建8项标准；状态为reviewed，尚未published。GB 29447-2026未由本脚本覆盖。")


if __name__ == "__main__":
    main()
