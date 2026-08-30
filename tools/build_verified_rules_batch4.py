"""Normalize the 38 source rows of GB 31825-2024 from tables 1 and 2."""
from __future__ import annotations

from build_verified_rules_batch1 import input_def, input_node, node, one_product, indicator
from build_verified_rules_batch2 import custom_indicator, write_definition


def build_31825() -> None:
    number = "GB 31825-2024"
    pulp_rows = [
        ("bleached-chemical-wood-self", "漂白化学木浆（自用浆）", ["180", "220", "260"]),
        ("bleached-chemical-wood-market", "漂白化学木浆（商品浆）", ["300", "340", "380"]),
        ("unbleached-chemical-wood-self", "未漂化学木浆（自用浆）", ["130", "160", "200"]),
        ("unbleached-chemical-wood-market", "未漂化学木浆（商品浆）", ["250", "280", "320"]),
        ("bleached-chemical-nonwood-self", "漂白化学非木浆（自用浆）", ["250", "280", "370"]),
        ("bleached-chemical-nonwood-market", "漂白化学非木浆（商品浆）", ["370", "400", "490"]),
        ("unbleached-chemical-nonwood-self", "未漂化学非木浆（自用浆）", ["200", "230", "320"]),
        ("unbleached-chemical-nonwood-market", "未漂化学非木浆（商品浆）", ["320", "350", "440"]),
        ("chemical-mechanical-self", "化学机械浆及机械浆（自用浆）", ["200", "250", "300"]),
        ("chemical-mechanical-market", "化学机械浆及机械浆（商品浆）", ["320", "370", "420"]),
        ("dissolving-wood-self", "溶解木浆（自用浆）", ["250", "310", "360"]),
        ("dissolving-wood-market", "溶解木浆（商品浆）", ["380", "430", "480"]),
        ("dissolving-nonwood-self", "溶解非木浆（自用浆）", ["330", "390", "440"]),
        ("dissolving-nonwood-market", "溶解非木浆（商品浆）", ["450", "510", "560"]),
        ("non-deinked-waste-self", "未脱墨废纸浆（自用浆）", ["40", "55", "70"]),
        ("deinked-waste-self", "脱墨废纸浆（自用浆）", ["100", "120", "140"]),
    ]
    paper_rows = [
        ("newsprint", "新闻纸", ["210", "240", "270"]),
        ("uncoated-printing-writing", "非涂布印刷书写纸", ["300", "360", "430"]),
        ("coated-printing", "涂布印刷纸", ["300", "350", "410"]),
        ("tissue-wood", "卫生纸原纸、纸巾原纸、吸水衬纸（木浆）", ["380", "450", "520"]),
        ("tissue-nonwood", "卫生纸原纸、纸巾原纸、吸水衬纸（非木浆）", ["420", "510", "560"]),
        ("wiping-wood", "擦拭用纸（木浆）", ["360", "430", "500"]),
        ("wiping-nonwood", "擦拭用纸（非木浆）", ["400", "470", "540"]),
        ("white-grey-board", "白纸板、灰板纸", ["220", "270", "320"]),
        ("liner-gypsum-board", "箱纸板、石膏板护面纸板", ["210", "240", "280"]),
        ("corrugating-tube-board", "瓦楞原纸、纸管纸板", ["200", "230", "260"]),
        ("coated-board", "涂布纸板", ["230", "280", "330"]),
        ("paper-bag", "纸袋纸", ["320", "380", "440"]),
        ("decorative-wallpaper-base", "装饰原纸、壁纸原纸", ["450", "500", "530"]),
        ("glassine", "格拉辛纸", ["420", "460", "500"]),
        ("cigarette", "卷烟纸", ["800", "850", "900"]),
        ("watermarked", "水松原纸", ["500", "600", "700"]),
        ("aluminum-foil-liner", "铝箔衬纸", ["350", "400", "450"]),
        ("stainless-liner", "不锈钢衬纸", ["520", "600", "680"]),
        ("thermal-carbon", "热敏原纸、无碳复写纸原纸", ["400", "450", "500"]),
        ("medical-packaging", "医用包装纸", ["570", "600", "630"]),
        ("fruit-bag", "育果袋纸", ["550", "580", "620"]),
        ("sublimation-transfer", "热升华转印原纸", ["430", "460", "500"]),
    ]
    products = []
    for ident, name, values in pulp_rows:
        products.append(one_product(indicator(number, ident, name, "kgce/Adt", values, page=6, table="表1"), name))
    modifier_key = "condition.paper_process_modifier"
    modifier = input_def(modifier_key, "机制纸特殊工艺修正量", "kgce/t", description="按表2注a、注b填写；无特殊工艺时填0，TAD填320或100，同时生产热敏/无碳/热升华产品时加200。")
    for ident, name, values in paper_rows:
        thresholds = [node("add", args=[node("constant", value=v, unit="kgce/t"), input_node(modifier_key)], unit="kgce/t", label="机制纸特殊工艺修正") for v in values]
        ind = custom_indicator(number, ident, name, "kgce/t", values, page=7, table="表2", extra_inputs=[modifier], threshold_exprs=thresholds,
                               notes=["original_pdf_transcribed", "paper_process_modifier_from_table_2_notes", "requires_independent_review"])
        products.append(one_product(ind, name))
    write_definition(number, products)


if __name__ == "__main__":
    build_31825()
    print("已按GB 31825-2024表1、表2重建38条规则；状态为reviewed，尚未published。")
