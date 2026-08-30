"""Transcribe GB 25324-2022 from the original tables (pages 1-2)."""
from __future__ import annotations

from build_verified_rules_batch1 import indicator, one_product, write_definition


def main() -> None:
    number = "GB 25324-2022"
    rows = [
        ("prebaked-anode-calcination", "铝电解用预焙阳极煅烧工序单位产品综合能源消耗", ["190", "210", "250"], "表1", 3),
        ("prebaked-anode-forming", "铝电解用预焙阳极成型工序单位产品综合能源消耗", ["7", "10", "20"], "表1", 3),
        ("prebaked-anode-roasting", "铝电解用预焙阳极焙烧工序单位产品综合能源消耗", ["170", "180", "230"], "表1", 3),
        ("prebaked-anode-assembly", "铝电解用预焙阳极组装工序单位产品综合能源消耗", ["9", "11", "15"], "表1", 3),
        ("graphitic-cathode-calcination", "铝电解用石墨质阴极炭块煅烧工序单位产品综合能源消耗", ["230", "290", "350"], "表2", 4),
        ("graphitic-cathode-forming-roasting", "铝电解用石墨质阴极炭块成型焙烧加工工序单位产品综合能源消耗", ["290", "340", "400"], "表2", 4),
        ("graphitized-cathode-calcination", "铝电解用石墨化阴极炭块煅烧工序单位产品综合能源消耗", ["200", "300", "370"], "表3", 4),
        ("graphitized-cathode-forming-roasting", "铝电解用石墨化阴极炭块成型焙烧工序单位产品综合能源消耗", ["220", "260", "400"], "表3", 4),
        ("graphitized-cathode-graphitization", "铝电解用石墨化阴极炭块石墨化加工工序单位产品综合能源消耗", ["460", "480", "660"], "表3", 4),
        ("cathode-paste-calcination", "铝电解用阴极糊煅烧工序单位产品综合能源消耗", ["270", "290", "350"], "表4", 4),
        ("cathode-paste-kneading", "铝电解用阴极糊混捏工序单位产品综合能源消耗", ["15", "18", "32"], "表4", 4),
    ]
    products = []
    for ident, name, values, table, page in rows:
        products.append(one_product(indicator(
            number, ident, name, "kgce/t", values, page=page, table=table,
            notes=[
                "original_pdf_transcribed",
                "table_note_requires_process_count_weighted_sum",
                "requires_independent_review",
            ],
        ), name))
    write_definition(number, products)
    print("已按GB 25324-2022原文表1至表4重建11项规则；状态为reviewed，尚未published。")


if __name__ == "__main__":
    main()
