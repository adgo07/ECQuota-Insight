"""Rebuild GB 21351-2023 from the original tables 2-19."""
from __future__ import annotations

from build_verified_rules_batch1 import indicator, input_def, input_node, node, one_product, write_definition


def _forging_indicator(number: str, ident: str, name: str, values: list[str], page: int, table: str, increments: list[str]):
    ind = indicator(number, ident, name, "kgce/t", values, page=page, table=table,
                    extra_inputs=[input_def(
                        f"condition.{ident}.heats", "统计期平均锻造火次", "次",
                        description="标准脚注规定：按实际锻造火次计；至少填写1。"
                    )], notes=["original_pdf_transcribed", "forging_heat_increment_from_table_footnote", "requires_independent_review"])
    heat_key = f"condition.{ident}.heats"
    # One forging heat is represented by the table value.  Each additional heat
    # adds the grade-specific increment stated in the source footnote.
    extra = node("max", args=[
        node("subtract", args=[input_node(heat_key), node("constant", value="1", unit="次")]),
        node("constant", value="0", unit="次"),
    ])
    ind["thresholds"] = {
        f"level_{level}": node("add", args=[
            node("constant", value=values[level - 1], unit="kgce/t"),
            node("multiply", args=[node("constant", value=increments[level - 1], unit="kgce/t"), extra], unit="kgce/t"),
        ], unit="kgce/t")
        for level in (1, 2, 3)
    }
    return ind


def main() -> None:
    number = "GB 21351-2023"
    rows: list[tuple[str, int, str, list[str], str | None]] = []

    def add(table: str, page: int, name: str, values: list[str], *, level_class: str | None = None) -> None:
        rows.append((table, page, f"{name}{f'（{level_class}）' if level_class else ''}", values, None))

    # 表2 扁铸锭（I类四行，II类后两行）
    add("表2", 6, "扁铸锭/熔融态铝及铝合金为主原料/熔铸", ["70", "85", "100"], level_class="I类")
    add("表2", 6, "扁铸锭/熔融态铝及铝合金为主原料/熔铸+均匀化处理", ["110", "130", "150"], level_class="I类")
    add("表2", 6, "扁铸锭/重熔用铝锭及固态回收铝为主原料/熔铸", ["125", "145", "185"], level_class="I类")
    add("表2", 6, "扁铸锭/重熔用铝锭及固态回收铝为主原料/熔铸+均匀化处理", ["165", "190", "235"], level_class="I类")
    add("表2", 6, "扁铸锭/重熔用铝锭及固态回收铝为主原料/熔铸", ["175", "200", "240"], level_class="II类")
    add("表2", 6, "扁铸锭/重熔用铝锭及固态回收铝为主原料/熔铸+均匀化处理", ["225", "255", "300"], level_class="II类")

    # 表3 实心圆铸锭
    add("表3", 7, "实心圆铸锭/建筑型材/熔融态铝及铝合金为主原料/熔铸", ["10", "30", "50"], level_class="I类")
    add("表3", 7, "实心圆铸锭/建筑型材/熔融态铝及铝合金为主原料/熔铸+均匀化处理", ["45", "65", "85"], level_class="I类")
    add("表3", 7, "实心圆铸锭/建筑型材/重熔用铝锭及固态回收铝为主原料/熔铸", ["55", "85", "125"], level_class="I类")
    add("表3", 7, "实心圆铸锭/建筑型材/重熔用铝锭及固态回收铝为主原料/熔铸+均匀化处理", ["90", "120", "160"], level_class="I类")
    add("表3", 7, "实心圆铸锭/其他/熔融态铝及铝合金为主原料/熔铸", ["45", "65", "85"], level_class="I类")
    add("表3", 7, "实心圆铸锭/其他/熔融态铝及铝合金为主原料/熔铸+均匀化处理", ["85", "110", "135"], level_class="I类")
    add("表3", 7, "实心圆铸锭/其他/重熔用铝锭及固态回收铝为主原料/熔铸", ["110", "130", "170"], level_class="I类")
    add("表3", 7, "实心圆铸锭/其他/重熔用铝锭及固态回收铝为主原料/熔铸+均匀化处理", ["150", "175", "220"], level_class="I类")
    add("表3", 7, "实心圆铸锭/其他/重熔用铝锭及固态回收铝为主原料/熔铸", ["160", "190", "220"], level_class="II类")
    add("表3", 7, "实心圆铸锭/其他/重熔用铝锭及固态回收铝为主原料/熔铸+均匀化处理", ["210", "245", "280"], level_class="II类")

    # 表4 空心圆铸锭
    add("表4", 7, "空心圆铸锭/重熔用铝锭及固态回收铝为主原料/熔铸", ["215", "240", "275"], level_class="I类")
    add("表4", 7, "空心圆铸锭/重熔用铝锭及固态回收铝为主原料/熔铸+均匀化处理", ["255", "285", "325"], level_class="I类")
    add("表4", 7, "空心圆铸锭/重熔用铝锭及固态回收铝为主原料/熔铸", ["250", "285", "330"], level_class="II类")
    add("表4", 7, "空心圆铸锭/重熔用铝锭及固态回收铝为主原料/熔铸+均匀化处理", ["300", "340", "390"], level_class="II类")

    # 表5--表8 板材、带材
    for table, page, title, data in [
        ("表5", 8, "热轧板材", [
            ("热轧", ["100", "120", "140"], ["120", "160", "200"]),
            ("热轧+退火", ["135", "160", "185"], ["160", "205", "250"]),
            ("热轧+固溶热处理", ["185", "215", "245"], ["220", "270", "320"]),
            ("热轧+固溶热处理+人工时效", ["215", "250", "285"], ["250", "310", "360"]),
        ]),
        ("表6", 8, "冷轧板材", [
            ("冷轧", ["90", "120", "145"], ["140", "180", "210"]),
            ("冷轧+退火", ["135", "170", "200"], ["195", "245", "285"]),
            ("冷轧+固溶热处理", ["200", "235", "265"], ["260", "305", "340"]),
            ("冷轧+固溶热处理+人工时效", ["230", "270", "305"], ["290", "340", "380"]),
        ]),
        ("表7", 8, "热轧带材", [
            ("热轧", ["75", "95", "120"], ["120", "150", "170"]),
            ("热轧+退火", ["105", "130", "160"], ["155", "190", "215"]),
        ]),
        ("表8", 9, "冷轧带材", [
            ("冷轧", ["70", "90", "110"], ["100", "120", "140"]),
            ("冷轧+退火", ["110", "135", "160"], ["150", "190", "230"]),
            ("冷轧+固溶热处理", ["170", "195", "220"], ["210", "235", "260"]),
            ("冷轧+固溶热处理+人工时效", ["200", "230", "260"], ["240", "270", "290"]),
        ]),
    ]:
        for process, i_values, ii_values in data:
            add(table, page, f"{title}/{process}", i_values, level_class="I类")
            add(table, page, f"{title}/{process}", ii_values, level_class="II类")

    # 表9、表10
    add("表9", 9, "铸轧带材/熔融态铝及铝合金为主原料", ["80", "100", "120"])
    add("表9", 9, "铸轧带材/重熔用铝锭及固态回收铝为主原料", ["130", "160", "180"])
    for product, process, values in [
        ("无零箔", "冷轧", ["45", "55", "65"]), ("无零箔", "冷轧+退火", ["75", "90", "105"]),
        ("单零箔", "冷轧", ["80", "115", "150"]), ("单零箔", "冷轧+退火", ["110", "150", "190"]),
        ("双零箔", "冷轧", ["120", "150", "230"]), ("双零箔", "冷轧+退火", ["150", "185", "270"]),
    ]:
        add("表10", 10, f"箔材/{product}/{process}", values)

    # 表11--表13 挤压材
    for table, page, title, processes in [
        ("表11", 10, "挤压无缝管材", [
            ("挤压", ["160", "190", "220"], ["250", "300", "350"]),
            ("挤压+退火", ["220", "260", "300"], ["310", "370", "430"]),
            ("挤压+固溶热处理", ["245", "285", "330"], ["335", "395", "460"]),
            ("挤压+固溶热处理+人工时效", ["275", "320", "370"], ["365", "430", "500"]),
        ]),
        ("表12", 11, "挤压棒材、板材、线材", [
            ("挤压", ["120", "140", "160"], ["180", "205", "240"]),
            ("挤压+退火", ["180", "195", "210"], ["240", "275", "320"]),
            ("挤压+固溶热处理", ["205", "220", "240"], ["265", "300", "350"]),
            ("挤压+固溶热处理+人工时效", ["235", "255", "280"], ["295", "335", "390"]),
        ]),
        ("表13", 11, "一般工业用挤压型材", [
            ("挤压", ["135", "160", "190"], ["220", "255", "305"]),
            ("挤压+退火", ["195", "230", "270"], ["280", "325", "385"]),
            ("挤压+固溶热处理", ["220", "255", "300"], ["305", "350", "415"]),
            ("挤压+固溶热处理+人工时效", ["250", "290", "340"], ["335", "385", "455"]),
        ]),
    ]:
        for process, i_values, ii_values in processes:
            add(table, page, f"{title}/{process}", i_values, level_class="I类")
            add(table, page, f"{title}/{process}", ii_values, level_class="II类")
    add("表13", 11, "建筑型材/挤压", ["100", "125", "150"], level_class="I类")

    # 表14、表15 拉（轧）制材
    for thickness, processes in [("壁厚＞3 mm", [
        ("拉（轧）制", ["130", "145", "170"]), ("拉（轧）制+固溶热处理", ["210", "225", "250"]),
        ("拉（轧）制+固溶热处理+人工时效", ["270", "285", "310"]),
    ]), ("壁厚≤3 mm", [
        ("拉（轧）制", ["200", "220", "240"]), ("拉（轧）制+固溶热处理", ["290", "310", "330"]),
        ("拉（轧）制+固溶热处理+人工时效", ["360", "380", "400"]),
    ])]:
        for process, values in processes:
            add("表14", 12, f"拉（轧）制管材/{thickness}/{process}", values)
    add("表15", 12, "连铸连轧线材", ["130", "150", "235"])
    for diameter, values in [("直径＞10 mm", ["140", "160", "180"]), ("5 mm＜直径≤10 mm", ["175", "195", "215"]), ("直径≤5 mm", ["220", "240", "260"]),
                             ("5 mm＜直径≤10 mm（其他线材）", ["20", "25", "35"]), ("3 mm＜直径≤5 mm（其他线材）", ["35", "50", "75"]),
                             ("1 mm＜直径≤3 mm（其他线材）", ["60", "80", "125"]), ("0.5 mm＜直径≤1 mm（其他线材）", ["98", "115", "165"]),
                             ("0.25 mm＜直径≤0.5 mm（其他线材）", ["110", "145", "195"]), ("0.10 mm＜直径≤0.25 mm（其他线材）", ["140", "195", "235"])]:
        add("表15", 12, f"拉制棒材、紧固件（含钢钉）用线材/{diameter}", values)

    # 表16、表17、表18、表19
    for name, values in [("阳极氧化产品", ["115", "125", "150"]), ("电泳涂漆产品", ["155", "170", "200"]),
                          ("喷粉产品", ["55", "65", "90"]), ("喷漆产品", ["150", "180", "230"])]:
        add("表16", 13, f"经表面处理的管、棒、型材/{name}", values)
    add("表17", 13, "复合型材", ["3", "4", "5"])
    for name, values in [("锻造", ["440", "490", "540"]), ("锻造+退火", ["540", "600", "660"]), ("锻造+固溶热处理+时效", ["610", "680", "750"])]:
        rows.append(("表18", 14, f"自由锻件/{name}", values, "260,290,320"))
    for name, values in [("锻造", ["480", "530", "590"]), ("锻造+退火", ["590", "650", "725"]), ("锻造+固溶热处理+时效", ["670", "740", "825"])]:
        rows.append(("表19", 14, f"模锻件/{name}", values, "300,330,370"))

    products = []
    for index, (table, page, name, values, increment_text) in enumerate(rows, 1):
        ident = f"table-{table[1:]}-row-{index}"
        if increment_text:
            increments = increment_text.split(",")
            ind = _forging_indicator(number, ident, name, values, page, table, increments)
        else:
            ind = indicator(number, ident, name, "kgce/t", values, page=page, table=table,
                            notes=["original_pdf_transcribed", "winter_heating_scope_note_in_table", "requires_independent_review"])
        products.append(one_product(ind, name))
    assert len(products) == 108, len(products)
    write_definition(number, products)
    print("已按GB 21351-2023原文表2至表19重建108项规则；状态为reviewed，尚未published。")


if __name__ == "__main__":
    main()
