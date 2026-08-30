"""Transcribe the 48 grade rows of GB 36889-2025 from its original tables."""
from __future__ import annotations

from build_verified_rules_batch1 import indicator, one_product, write_definition


def main() -> None:
    n = "GB 36889-2025"
    rows = [
        ("polyester-polymerization", "聚酯涤纶/聚合/聚酯熔体或切片", ["85", "90", "100"], "表1", 6),
        ("polyester-solid-phase", "聚酯涤纶/固相增黏/高黏度切片", ["40", "42", "45"], "表1", 6),
        ("polyester-liquid-phase", "聚酯涤纶/液相增黏/高黏度熔体", ["35", "37", "40"], "表1", 6),
        ("polyester-melt-poy", "聚酯涤纶/熔体直接纺丝/预取向丝(POY)", ["40", "45", "50"], "表1", 6),
        ("polyester-melt-fdy", "聚酯涤纶/熔体直接纺丝/全拉伸丝(FDY)", ["50", "60", "83"], "表1", 6),
        ("polyester-melt-industrial", "聚酯涤纶/熔体直接纺丝/工业长丝", ["120", "140", "145"], "表1", 6),
        ("polyester-melt-staple", "聚酯涤纶/熔体直接纺丝/短纤维", ["85", "100", "110"], "表1", 6),
        ("polyester-chip-poy", "聚酯涤纶/切片纺丝/预取向丝(POY)", ["90", "92", "95"], "表1", 6),
        ("polyester-chip-fdy", "聚酯涤纶/切片纺丝/全拉伸丝(FDY)", ["92", "95", "105"], "表1", 6),
        ("polyester-chip-industrial", "聚酯涤纶/切片纺丝/工业长丝", ["140", "160", "165"], "表1", 6),
        ("polyester-chip-staple", "聚酯涤纶/切片纺丝/短纤维", ["140", "160", "180"], "表1", 6),
        ("polyester-dty-low-pressure", "聚酯涤纶/加弹/拉伸变形丝(DTY)(网络喷嘴压力不大于0.12 MPa)", ["90", "105", "115"], "表1", 6),
        ("polyester-dty-mid-pressure", "聚酯涤纶/加弹/拉伸变形丝(DTY)(网络喷嘴压力小于0.35 MPa、大于0.12 MPa)", ["120", "130", "140"], "表1", 6),
        ("polyester-dty-high-pressure", "聚酯涤纶/加弹/拉伸变形丝(DTY)(网络喷嘴压力不小于0.35 MPa)", ["150", "160", "180"], "表1", 6),
        ("recycled-chip", "循环再利用涤纶(物理法、物理化学法)/切片(瓶片到切片)", ["55", "65", "75"], "表2", 7),
        ("recycled-poy", "循环再利用涤纶/预取向丝(POY)(瓶片纺/切片纺)", ["100", "115", "120"], "表2", 7),
        ("recycled-fdy-bottle", "循环再利用涤纶/全拉伸丝(FDY)/瓶片纺", ["130", "140", "150"], "表2", 7),
        ("recycled-fdy-chip", "循环再利用涤纶/全拉伸丝(FDY)/切片纺", ["100", "120", "130"], "表2", 7),
        ("recycled-dty-low", "循环再利用涤纶/拉伸变形丝(DTY)(网络喷嘴压力不大于0.12 MPa)", ["95", "110", "118"], "表2", 7),
        ("recycled-dty-mid", "循环再利用涤纶/拉伸变形丝(DTY)(网络喷嘴压力小于0.35 MPa、大于0.12 MPa)", ["130", "135", "145"], "表2", 7),
        ("recycled-dty-high", "循环再利用涤纶/拉伸变形丝(DTY)(网络喷嘴压力不小于0.35 MPa)", ["155", "167", "185"], "表2", 7),
        ("recycled-staple", "循环再利用涤纶/短纤维", ["150", "160", "185"], "表2", 7),
        ("bottle-polyester-chip", "瓶用聚酯/瓶用聚酯切片", ["100", "115", "120"], "表3", 7),
        ("viscose-staple", "粘胶纤维/粘胶短纤维", ["800", "900", "950"], "表4", 7),
        ("viscose-modal", "粘胶纤维/莫代尔短纤维", ["1150", "1170", "1200"], "表4", 7),
        ("viscose-filament", "粘胶纤维/粘胶长丝", ["2700", "2900", "3000"], "表4", 7),
        ("nylon6-civil-chip", "锦纶6/聚合/民用切片", ["100", "135", "145"], "表5", 8),
        ("nylon6-industrial-chip", "锦纶6/聚合/工业用切片", ["130", "160", "190"], "表5", 8),
        ("nylon6-poy-hoy", "锦纶6/纺丝/预取向丝(POY)、高取向丝(HOY)", ["115", "160", "200"], "表5", 8),
        ("nylon6-fdy", "锦纶6/纺丝/全拉伸丝(FDY)", ["180", "250", "270"], "表5", 8),
        ("nylon6-industrial", "锦纶6/纺丝/工业长丝", ["160", "180", "350"], "表5", 8),
        ("nylon6-dty", "锦纶6/加弹/拉伸变形丝(DTY)", ["165", "245", "285"], "表5", 8),
        ("spandex-dry", "氨纶(干法纺丝)", ["900", "1100", "1300"], "表6", 8),
        ("vinylon-high-strength", "维纶/高强高模聚乙烯醇超短纤维", ["800", "1070", "1200"], "表7", 8),
        ("vinylon-water-soluble", "维纶/水溶性聚乙烯醇短纤维", ["950", "1100", "1200"], "表7", 8),
        ("acrylic-dmac", "腈纶(DMAc湿法二步法)", ["950", "1000", "1050"], "表8", 9),
        ("polypropylene-fdy", "丙纶/丙纶全拉伸丝(FDY)", ["130", "150", "200"], "表9", 9),
        ("polypropylene-bcf", "丙纶/丙纶膨体长丝(BCF)", ["175", "200", "220"], "表9", 9),
        ("polypropylene-staple", "丙纶/丙纶短纤维", ["110", "130", "155"], "表9", 9),
        ("uhmwpe-halogen", "超高分子量聚乙烯纤维(湿法纺丝)/卤化烃萃取剂", ["3000", "3500", "4000"], "表10", 9),
        ("uhmwpe-hydrocarbon", "超高分子量聚乙烯纤维(湿法纺丝)/碳氢萃取剂", ["4000", "6000", "8000"], "表10", 9),
        ("bicomponent-polymer", "双组分复合纤维/双组分聚合熔体/切片", ["120", "130", "150"], "表11", 10),
        ("bicomponent-melt-poy", "双组分复合纤维/熔体直接纺/预取向丝(POY)", ["45", "55", "70"], "表11", 10),
        ("bicomponent-melt-fdy", "双组分复合纤维/熔体直接纺/全拉伸丝(FDY)", ["55", "65", "80"], "表11", 10),
        ("bicomponent-chip-poy", "双组分复合纤维/切片纺/预取向丝(POY)", ["120", "155", "180"], "表11", 10),
        ("bicomponent-chip-fdy", "双组分复合纤维/切片纺/全拉伸丝(FDY)", ["150", "170", "190"], "表11", 10),
        ("pe-pet-staple", "聚乙烯/聚对苯二甲酸乙二醇酯(PE/PET)复合短纤维", ["120", "130", "190"], "表11", 10),
        ("lmpet-pet-staple", "低熔点聚酯(LMPET)/聚酯(PET)复合短纤维", ["155", "165", "175"], "表11", 10),
    ]
    products = []
    for ident, name, values, table, page in rows:
        products.append(one_product(indicator(
            n, ident, name, "kgce/t", values, page=page, table=table,
            notes=["original_pdf_transcribed", "statistics_and_yield_conversion_in_clause_6", "requires_independent_review"],
        ), name))
    write_definition(n, products)
    print("已按GB 36889-2025原文表1至表11重建48项规则；状态为reviewed，尚未published。")


if __name__ == "__main__":
    main()
