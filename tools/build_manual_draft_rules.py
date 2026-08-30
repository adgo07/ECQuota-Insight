from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from uebench.domain.models import StandardDefinition

from build_original_draft_rules import constant, node, slug


def make_indicator(number: str, name: str, unit: str, values: list[str], source_file: str,
                   sha256: str, page: int, table: str, index: int) -> dict:
    key = f"actual.{slug(number)}.manual_{index}"
    return {
        "id": f"{slug(number)}.manual_candidate_{index}",
        "name": name,
        "unit": unit,
        "comparison": "lte",
        "input_definitions": [{"key": key, "label": f"{name}实际值", "data_type": "decimal",
            "unit": unit, "required": True, "required_if": None, "modes": ["DIRECT"],
            "minimum": None, "maximum": None, "choices": [],
            "description": "原文人工整理候选；需第二轮独立复核后才能发布。"}],
        "applicability": {"op": "always"},
        "direct_input_key": key,
        "detail_formula": node("per_unit", args=[node("input", input_key="energy.total_standard_coal"),
            node("input", input_key="production.total_equivalent")], unit=unit,
            label="单位产品实际能耗（候选通用公式，待原文复核）"),
        "base_thresholds": {f"level_{i}": constant(values[i - 1], unit) for i in (1, 2, 3)},
        "thresholds": {f"level_{i}": constant(values[i - 1], unit) for i in (1, 2, 3)},
        "display_places": 2,
        "source_references": [{"standard_number": number, "source_file": source_file,
            "source_sha256": sha256, "page": page, "clause": "第4章技术要求（候选）",
            "table": table, "note": "候选规则；需对照原文适用条件、统计边界和公式复核。"}],
        "notes": ["candidate_from_original_pdf", "not_for_formal_evaluation", "requires_independent_review"],
    }


def definition(path: Path, catalog: dict, number: str, indicators: list[dict]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("products") or data.get("publication_status") != "draft":
        return
    data["products"] = [{"id": f"manual-candidate-{i}", "name": item["name"],
        "description": "标准原文人工整理候选，待规则确认表复核。", "input_definitions": [],
        "indicators": [item]} for i, item in enumerate(indicators, 1)]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    root = args.data_dir.resolve()
    catalog = {x["number"]: x for x in json.loads((root / "catalog.json").read_text(encoding="utf-8"))["standards"]}

    def src(number: str) -> tuple[str, str]:
        row = catalog[number]
        return row["source_file"], row["source_sha256"]

    # GB 29141—2012: Table 1 existing, Table 2 access, Table 3 advanced.
    # The three levels are mapped as 1=advanced, 2=access, 3=existing.
    number = "GB 29141-2012"; file, sha = src(number)
    feedstocks = [
        ("硫磺", ["-180", "-140", "-115"], ["60", "70", "85"]),
        ("硫铁矿", ["-135", "-120", "-100"], ["110", "120", "130"]),
        ("铜、镍冶炼烟气", ["-30", "3", "16"], ["100", "110", "130"]),
        ("铅冶炼烟气", ["5", "19", "22"], ["130", "150", "180"]),
        ("锌冶炼烟气", ["-120", "-95", "-85"], ["110", "120", "130"]),
        ("其他有色金属冶炼烟气", ["-42", "-4", "34"], ["210", "240", "270"]),
    ]
    inds = []
    for i, (feed, energy, elec) in enumerate(feedstocks, 1):
        inds += [make_indicator(number, f"{feed}单位产品综合能耗", "kgce/t", energy, file, sha, 2, "表1、表2、表3", i * 2 - 1),
                 make_indicator(number, f"{feed}吨酸电耗", "kWh/t", elec, file, sha, 2, "表1、表2、表3", i * 2)]
    definition(root / "definitions" / "gb-29141-2012.json", catalog, number, inds)

    number = "GB 29438-2012"; file, sha = src(number)
    definition(root / "definitions" / "gb-29438-2012.json", catalog, number,
               [make_indicator(number, "聚甲醛单位产品能耗", "kgce/t", ["2000", "2100", "2800"], file, sha, 2, "4.1～4.3", 1)])

    number = "GB 30183-2013"; file, sha = src(number)
    definition(root / "definitions" / "gb-30183-2013.json", catalog, number, [
        make_indicator(number, "岩棉、矿渣棉及其制品单位产品可比综合能耗", "kgce/t", ["400.0", "450.0", "490.0"], file, sha, 2, "表1～表3", 1),
        make_indicator(number, "岩棉、矿渣棉及其制品单位产品可比熔融焦耗", "kgce/t", ["210.0", "240.0", "260.0"], file, sha, 2, "表1～表3", 2),
    ])

    number = "GB 38263-2019"; file, sha = src(number)
    rows = [("预制混凝土桩", ["32.3", "38.8", "56.6"]), ("环形混凝土电杆", ["40.4", "48.5", "72.2"]),
            ("混凝土和钢筋混凝土排水管", ["27.5", "33.0", "49.5"]), ("预应力钢筒混凝土管", ["37.5", "45.0", "66.4"]),
            ("加气混凝土", ["21.0", "25.2", "37.3"]), ("硅酸钙板", ["77.5", "93.0", "131.0"]),
            ("预制混凝土衬砌管片", ["12.5", "15.0", "21.0"])]
    definition(root / "definitions" / "gb-38263-2019.json", catalog, number,
               [make_indicator(number, f"{name}单位产品综合能耗", "kgce/m³", values, file, sha, 8, "表1", i)
                for i, (name, values) in enumerate(rows, 1)])

    # GB 21370—2017: the two original-PDF tables are legible page images.
    number = "GB 21370-2017"; file, sha = src(number)
    carbon_rows = [
        ("普通功率石墨电极单位产品综合能耗", "kgce/t", ["2060", "2170", "2410"]),
        ("普通功率石墨电极单位产品电耗", "kWh/t", ["5630", "5800", "6440"]),
        ("高功率石墨电极单位产品综合能耗", "kgce/t", ["2620", "2740", "3050"]),
        ("高功率石墨电极单位产品电耗", "kWh/t", ["6160", "6640", "6820"]),
        ("超高功率石墨电极单位产品综合能耗", "kgce/t", ["3230", "3425", "3780"]),
        ("超高功率石墨电极单位产品电耗", "kWh/t", ["6800", "6865", "7260"]),
        ("炭电极（产品直径≤1000 mm）单位产品综合能耗", "kgce/t", ["720", "765", "895"]),
        ("炭电极（产品直径＞1000 mm）单位产品综合能耗", "kgce/t", ["1325", "1375", "1575"]),
        ("炭块（半石墨质炭块）单位产品综合能耗", "kgce/t", ["1130", "1200", "1330"]),
        ("炭块（微孔炭块）单位产品综合能耗", "kgce/t", ["1280", "1350", "1500"]),
        ("焙烧工序（产品直径≤500 mm）单位产品能耗", "kgce/t", ["385", "455", "530"]),
        ("焙烧工序（500 mm＜产品直径≤1000 mm）单位产品能耗", "kgce/t", ["450", "525", "610"]),
        ("焙烧工序（产品直径＞1000 mm）单位产品能耗", "kgce/t", ["900", "1120", "1260"]),
        ("石墨化工序普通功率石墨电极单位产品综合能耗", "kgce/t", ["1035", "1105", "1170"]),
        ("石墨化工序普通功率石墨电极单位产品电耗", "kWh/t", ["4080", "4330", "4770"]),
        ("石墨化工序高功率石墨电极单位产品综合能耗", "kgce/t", ["1140", "1215", "1285"]),
        ("石墨化工序高功率石墨电极单位产品电耗", "kWh/t", ["4480", "4765", "4970"]),
        ("石墨化工序超高功率石墨电极单位产品综合能耗", "kgce/t", ["1200", "1280", "1345"]),
        ("石墨化工序超高功率石墨电极单位产品电耗", "kWh/t", ["4685", "4930", "5480"]),
    ]
    definition(root / "definitions" / "gb-21370-2017.json", catalog, number,
               [make_indicator(number, name, unit, values, file, sha, 4, "表1、表2", i)
                for i, (name, unit, values) in enumerate(carbon_rows, 1)])

    # GB 21350—2023: tables 2–9 contain three comparable comprehensive-energy
    # indicators per alloy/category; table 10 contains electrical copper wire.
    number = "GB 21350-2023"; file, sha = src(number)
    alloy = ["紫铜", "普通黄铜", "复杂黄铜", "青铜、高铜", "白铜"]
    table_rows: dict[str, list[list[list[str]]]] = {
        "表2": [
            [["55", "60", "70"], ["120", "130", "160"], ["190", "200", "250"]],
            [["60", "68", "80"], ["155", "160", "185"], ["270", "290", "320"]],
            [["90", "95", "110"], ["195", "200", "210"], ["400", "450", "510"]],
            [["98", "100", "105"], ["158", "160", "175"], ["480", "490", "530"]],
            [["90", "100", "115"], ["195", "200", "210"], ["430", "450", "500"]],
        ],
        "表3": [
            [["68", "73", "79"], ["117", "125", "152"], ["199", "215", "270"]],
            [["58", "62", "76"], ["134", "145", "183"], ["197", "212", "274"]],
            [["64", "70", "87"], ["134", "146", "184"], ["211", "219", "284"]],
            [["110", "118", "146"], ["218", "223", "286"], ["340", "366", "458"]],
            [["112", "120", "148"], ["200", "214", "263"], ["318", "342", "428"]],
        ],
        "表4": [
            [["68", "73", "79"], ["34", "37", "41"], ["106", "117", "129"]],
            [["58", "62", "76"], ["125", "131", "141"], ["179", "212", "232"]],
            [["45", "55", "69"], ["72", "93", "119"], ["135", "164", "194"]],
            [["67", "70", "75"], ["120", "129", "140"], ["194", "206", "218"]],
            [["90", "98", "109"], ["108", "119", "132"], ["203", "226", "247"]],
        ],
        "表5": [
            [["41", "43", "47"], ["26", "31", "37"], ["70", "80", "90"]],
            [["45", "48", "53"], ["31", "35", "40"], ["91", "106", "119"]],
            [["41", "46", "54"], ["35", "42", "52"], ["91", "106", "119"]],
            [["95", "107", "121"], ["66", "78", "93"], ["172", "194", "215"]],
            [["74", "78", "84"], ["76", "83", "92"], ["159", "173", "185"]],
        ],
        "表6": [
            [["45", "47", "51"], ["43", "52", "63"], ["100", "114", "129"]],
            [["50", "54", "59"], ["71", "79", "89"], ["130", "151", "170"]],
            [["45", "52", "60"], ["78", "96", "116"], ["130", "151", "170"]],
            [["106", "118", "133"], ["94", "112", "133"], ["229", "257", "286"]],
            [["82", "87", "93"], ["109", "119", "131"], ["199", "216", "231"]],
        ],
        "表7": [
            [["58", "63", "73"], ["115", "120", "155"], ["190", "200", "270"]],
            [["53", "55", "63"], ["210", "220", "250"], ["280", "290", "350"]],
            [["77", "80", "93"], ["280", "290", "330"], ["460", "480", "540"]],
            [["133", "138", "155"], ["275", "290", "315"], ["540", "570", "620"]],
            [["133", "138", "155"], ["270", "285", "315"], ["500", "520", "580"]],
        ],
        "表8": [
            [["53", "58", "68"], ["100", "110", "125"], ["170", "180", "200"]],
            [["45", "50", "60"], ["110", "115", "130"], ["170", "180", "210"]],
            [["90", "95", "110"], ["210", "220", "260"], ["370", "400", "430"]],
            [["90", "100", "130"], ["230", "240", "285"], ["430", "450", "500"]],
        ],
        "表9": [[["40", "42", "46"], ["110", "120", "130"], ["160", "170", "185"]]],
    }
    alloy_inds = []
    counter = 1
    metric_names = ["熔铸工序单位产品综合能耗", "加工工序单位产品综合能耗", "全工序单位产品综合能耗"]
    for table, rows_for_table in table_rows.items():
        for row_index, metrics in enumerate(rows_for_table):
            category = alloy[row_index] if row_index < len(alloy) else "紫铜"
            for metric_name, values in zip(metric_names, metrics):
                alloy_inds.append(make_indicator(number, f"{table}{category}{metric_name}", "kgce/t", values, file, sha,
                                                  5 if table in ("表2", "表3") else (6 if table in ("表4", "表5") else (7 if table == "表6" else 8)), table, counter))
                counter += 1
    wire_rows = [("上引连铸/阴极铜", ["45", "52", "56"]), ("连铸连轧/阴极铜", ["54", "57", "66"]),
                 ("连铸连轧/再生铜", ["100", "130", "180"])]
    alloy_inds.extend(make_indicator(number, f"表10 {name}电工用铜线坯单位产品综合能耗", "kgce/t", values, file, sha, 8, "表10", counter + i)
                      for i, (name, values) in enumerate(wire_rows))
    definition(root / "definitions" / "gb-21350-2023.json", catalog, number, alloy_inds)

    number = "GB 30526-2019"; file, sha = src(number)
    sinter_rows = [("烧结多孔砖和多孔砌块", ["46", "48", "53"]),
                   ("烧结空心砖和空心砌块", ["47", "50", "55"]),
                   ("烧结保温砖和保温砌块", ["50", "52", "57"]),
                   ("烧结实心制品", ["44", "46", "51"]),
                   ("泡沫玻璃（外购熔容玻璃）", ["360", "425", "480"]),
                   ("泡沫玻璃（自制熔容玻璃）", ["520", "635", "730"]),
                   ("泡沫玻璃（Ⅱ型）", ["250", "280", "300"])]
    definition(root / "definitions" / "gb-30526-2019.json", catalog, number,
               [make_indicator(number, name, "kgce/t", values, file, sha, 4, "表1、表2", i)
                for i, (name, values) in enumerate(sinter_rows, 1)])

    number = "GB 33654-2017"; file, sha = src(number)
    definition(root / "definitions" / "gb-33654-2017.json", catalog, number,
               [make_indicator(number, "建筑石膏单位产品可比综合能耗", "kgce/t", ["30.0", "39.0", "43.0"], file, sha, 4, "表1", 1)])

    number = "GB 45247-2025"; file, sha = src(number)
    # Table 1 values are exact.  The heat-rate columns are shown as class-level
    # merged cells in the source; the draft repeats the class values per capacity
    # row and records the need to confirm the merge semantics.
    power_rows = [("H级/500MW", ["201", "210", "215"]), ("F级/400MW", ["203", "215", "223"]),
                  ("F级/300MW", ["206", "219", "227"]), ("F级/100MW", ["220", "232", "241"]),
                  ("E级/100MW", ["232", "245", "259"])]
    power_inds = []
    for i, (label, values) in enumerate(power_rows, 1):
        power_inds.append(make_indicator(number, f"{label}供电煤耗率", "gce/(kW·h)", values, file, sha, 6, "表1", i * 2 - 1))
        power_inds.append(make_indicator(number, f"{label}供热煤耗率", "kgce/GJ", ["38", "38.5", "39"], file, sha, 6, "表1（热耗率合并单元格候选）", i * 2))
    definition(root / "definitions" / "gb-45247-2025.json", catalog, number, power_inds)

    number = "GB 25323-2023"; file, sha = src(number)
    # Tables 1–12 of the original PDF were visually transcribed into draft
    # candidates.  Conditions in the table labels are preserved in each name;
    # formula/branch confirmation remains a separate review task.
    heavy_rows = [
        ("表1 粗铜工艺单位产品综合能耗（铜精矿-粗铜）", ["100", "125", "175"]),
        ("表1 阳极铜工艺单位产品综合能耗（铜精矿-阳极铜）", ["125", "140", "235"]),
        ("表1 铜电解工序单位产品综合能耗（阳极铜-阴极铜）", ["70", "85", "110"]),
        ("表1 铜冶炼单位产品综合能耗（铜精矿-阴极铜）", ["210", "230", "340"]),
        ("表2 粗铜冶炼工艺阳极铜（粗铜-阳极铜）", ["140", "190", "240"]),
        ("表2 粗铜冶炼工艺粗铜（粗铜-阴极铜）", ["240", "280", "330"]),
        ("表2 杂铜冶炼工艺粗铜（杂铜-粗铜）", ["140", "170", "220"]),
        ("表2 杂铜冶炼工艺阳极铜（杂铜-阳极铜）", ["160", "190", "250"]),
        ("表2 杂铜冶炼工艺杂铜（杂铜-阴极铜）", ["290", "310", "370"]),
        ("表3 火法炼锌粗锌锭工序（精矿-粗锌锭）", ["1250", "1400", "1470"]),
        ("表3 火法炼锌粗精锌锭工序（粗锌锭-精锌锭）", ["290", "300", "420"]),
        ("表3 火法炼锌精锌锭（精矿-精锌锭）", ["1540", "1700", "1890"]),
        ("表3 湿法炼锌电锌锭（含渣处理）（精矿-电锌锭）", ["1010", "1040", "1260"]),
        ("表3 湿法炼锌电锌锭（无渣处理）（精矿-电锌锭）", ["550", "660", "820"]),
        ("表4 富集氧化锌工序（二次资源含锌12%）", ["1300", "1600", "2000"]),
        ("表4 富集氧化锌工序（二次资源含锌8%）", ["2200", "2500", "2800"]),
        ("表4 富集氧化锌工序（二次资源含锌5%）", ["2500", "2800", "3000"]),
        ("表4 富集锌焙砂工序（进一步富集并脱除氟、氯）", ["300", "330", "350"]),
        ("表4 富集锌焙砂工序（二次资源含锌12%）", ["1600", "1930", "2350"]),
        ("表4 富集锌焙砂工序（二次资源含锌8%）", ["2500", "2830", "3150"]),
        ("表4 富集锌焙砂工序（二次资源含锌5%）", ["2800", "3130", "3350"]),
        ("表4 湿法炼锌（不含渣处理）（富集氧化锌-电锌锭）", ["750", "800", "860"]),
        ("表4 湿法炼锌（含渣处理）（富集氧化锌-电锌锭）", ["1100", "1200", "1400"]),
        ("表5 粗铅工艺（铅精矿-粗铅）", ["220", "230", "300"]),
        ("表5 铅电解精炼工序（粗铅-铅锭）", ["80", "100", "120"]),
        ("表5 铅冶炼（铅精矿-铅锭）", ["300", "330", "420"]),
        ("表6 废电池预处理工序（废电池-铅屑、铅膏）", ["3", "3.5", "4"]),
        ("表6 铅膏冶炼工序（铅膏-再生粗铅）", ["145", "180", "250"]),
        ("表6 铅屑冶炼工序（铅屑-再生粗铅）", ["12", "13", "15"]),
        ("表6 火法精炼工艺（再生粗铅-再生铅）", ["10", "16", "22"]),
        ("表6 再生铅单位产品综合能耗（废电池-再生铅）", ["120", "150", "210"]),
        ("表6 金属态铅废料-再生铅工艺", ["15", "18", "20"]),
        ("表7 高镍锍工艺（镍精矿-高镍锍）", ["540", "1160", "1400"]),
        ("表7 镍精炼工艺（高镍锍-电解镍）", ["1300", "1380", "2000"]),
        ("表7 电解工序（阳极镍-电解镍）", ["1040", "1150", "1300"]),
        ("表7 镍冶炼（镍精矿-电解镍）", ["3450", "3650", "4680"]),
        ("表8 熔前处理工序（硫精矿-锡焙砂、焙烧渣）沸腾炉处理", ["25", "35", "45"]),
        ("表8 熔前处理工序（硫精矿-锡焙砂、焙烧渣）回转窑处理", ["60", "70", "90"]),
        ("表8 还原熔炼工序（锡焙砂、锡精矿-粗锡）", ["600", "750", "900"]),
        ("表8 精炼工序（粗锡-锡锭、焊锡）", ["120", "160", "200"]),
        ("表8 炼渣工序（含锡渣料-含锡烟尘）", ["2200", "2600", "3200"]),
        ("表8 锡冶炼（锡精矿-锡锭、焊锡）", ["1500", "1800", "2200"]),
        ("表9 粗炼工序（锑低品位矿-锑氧）（硫化锑矿）", ["1600", "1800", "1950"]),
        ("表9 粗炼工序（锑精矿-锑氧）（硫化锑矿）", ["560", "620", "700"]),
        ("表9 精炼工序（锑氧-锑锭）（硫化锑矿）", ["370", "410", "440"]),
        ("表9 锑冶炼（锑低品位矿-锑锭）（硫化锑矿）", ["1970", "2210", "2390"]),
        ("表9 锑冶炼（锑精矿-锑锭）（硫化锑矿）", ["950", "1100", "1250"]),
        ("表10 粗炼、吹炼工序（脆硫铅锑精矿-锑氧、底铅）", ["836", "890", "950"]),
        ("表10 炼渣工序（鼓风炉渣-锑氧、铅锑粗合金）", ["500", "540", "600"]),
        ("表10 精炼工序（锑氧、底铅-锑锭、高铅锑锭、铅锭）", ["390", "440", "500"]),
        ("表10 脆硫铅锑矿冶炼（脆硫铅锑精矿-锑锭、高铅锑锭、铅锭）", ["1710", "1820", "2100"]),
        ("表11 氯化锆工艺（锆原料-氯化锆溶液）", ["1300", "1700", "2050"]),
        ("表11 电积锆工艺（氯化锆溶液-电积锆）", ["1380", "1510", "1540"]),
        ("表11 锆冶炼（锆原料-电积锆）", ["3350", "3400", "3600"]),
        ("表11 四氧化二锆工艺（氯化锆溶液或硝酸锆溶液或硫酸锆溶液-四氧化二锆）", ["1200", "1350", "2000"]),
        ("表11 氯化锆（锆原料-氯化锆晶体）", ["2100", "2350", "2500"]),
        ("表11 硫酸锆（锆原料-硫酸锆晶体）", ["2700", "2790", "2900"]),
        ("表12 硫化钛精矿冶炼（硫化钛精矿-钛锭）", ["2500", "2800", "3300"]),
        ("表12 氧化钛原料冶炼（氧化钛原料-钛锭）", ["2100", "2300", "2800"]),
    ]
    definition(root / "definitions" / "gb-25323-2023.json", catalog, number,
               [make_indicator(number, name, "kgce/t", values, file, sha,
                               6 if name.startswith(("表1", "表2")) else (7 if name.startswith(("表3", "表4")) else (8 if name.startswith(("表5", "表6")) else (9 if name.startswith(("表7", "表8")) else (10 if name.startswith(("表9", "表10")) else 11)))),
                               name[:3], i)
                for i, (name, values) in enumerate(heavy_rows, 1)])

    # Validate all definitions after the write.  These remain draft candidates.
    for path in (root / "definitions").glob("gb-*.json"):
        StandardDefinition.model_validate(json.loads(path.read_text(encoding="utf-8")))
    print("已补充原文视觉复核候选规则；全部仍为 draft，必须经过独立复核后才能发布。")


if __name__ == "__main__":
    main()
