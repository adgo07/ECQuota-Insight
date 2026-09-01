from __future__ import annotations

"""Name and complete table rows whose detail formula still needs factors.

GB 29145, GB 31823 and GB 32032 contain ore-grade, distance, scale, route or
other correction factors.  We therefore expose the exact table rows and direct
limits now, but deliberately leave ``detail_formula`` empty.  A detail-mode
calculation will return INCOMPLETE instead of silently applying an incorrect
generic formula; the factor model is a separate review task.
"""

import argparse
import json
from pathlib import Path

from uebench.domain.models import StandardDefinition


def make_input(key: str, label: str, unit: str) -> dict:
    return {"key": key, "label": label, "data_type": "decimal", "unit": unit,
            "required": True, "required_if": None, "modes": ["DIRECT"],
            "minimum": "0", "maximum": None, "choices": [],
            "description": "直接录入按标准原文统计范围和公式核算的单位产品能耗。"}


def constant(value: str, unit: str) -> dict:
    return {"op": "constant", "value": value, "input_key": None, "args": [],
            "cases": [], "rows": [], "default": None, "label": None,
            "unit": unit, "round_places": None}


CONFIG = {
    "GB 29145-2023": {
        "rows": [
            ("tungsten-black", "钨精矿—黑钨", "kgce/t", ("550", "1150", "1450")),
            ("tungsten-white", "钨精矿—白钨", "kgce/t", ("1640", "1750", "2050")),
            ("molybdenum-three-stage", "钼精矿—三段一闭路", "kgce/t", ("1250", "1390", "1475")),
            ("molybdenum-sabc", "钼精矿—SABC", "kgce/t", ("1900", "2060", "2150")),
            ("roasted-molybdenum-multi-hearth", "焙烧钼精矿—多膛炉", "kgce/t", ("210", "230", "260")),
            ("roasted-molybdenum-kiln", "焙烧钼精矿—内热式回转窑", "kgce/t", ("170", "180", "200")),
        ],
        "page": 4, "clause": "第4章、表1～表3", "table": "表1～表3",
        "note": "钨/钼精矿可比能耗还需按原矿品位折算系数修正；焙烧钼精矿按炉型选择。",
    },
    "GB 31823-2021": {
        "rows": [
            ("container-terminal", "集装箱码头", "tce/10^4TEU", ("24", "28", "45")),
            ("dry-bulk-terminal", "干散货码头", "tce/10^4t", ("1.8", "2.0", "2.7")),
            ("crude-oil-terminal", "原油码头", "tce/10^4t", ("0.36", "0.51", "0.88")),
        ],
        "page": 4, "clause": "第4章、表1～表3", "table": "表1～表3",
        "note": "码头类型还需应用吞吐量、距离、装卸工艺和能源折算修正系数。",
    },
    "GB 32032-2024": {
        "rows": [
            ("mining-open-pit", "金矿开采—露天开采", "kgce/t", ("0.45", "0.85", "1.05")),
            ("mining-underground-small", "金矿开采—地下开采（<3×10^4 t/a）", "kgce/t", ("6.30", "14.10", "16.60")),
            ("mining-underground-medium", "金矿开采—地下开采（3×10^4～6×10^4 t/a）", "kgce/t", ("5.00", "10.20", "12.80")),
            ("mining-underground-large", "金矿开采—地下开采（>6×10^4 t/a）", "kgce/t", ("3.10", "7.65", "9.55")),
            ("processing-dump-leach", "金矿选冶—堆浸", "kgce/t", ("0.60", "0.85", "0.95")),
            ("processing-flotation", "金矿选冶—浮选", "kgce/t", ("2.25", "4.50", "5.30")),
            ("processing-ore-slurry-cyanide", "金矿选冶—原矿全泥氰化", "kgce/t", ("4.30", "5.15", "5.80")),
            ("processing-concentrate-cyanide", "金矿选冶—金精矿氰化", "kgce/t", ("11.20", "13.30", "14.00")),
            ("processing-ore-roasting", "金矿选冶—原矿焙烧", "kgce/t", ("22.50", "27.00", "30.00")),
            ("processing-concentrate-roasting", "金矿选冶—金精矿焙烧", "kgce/t", ("22.00", "24.75", "27.50")),
            ("processing-matte-capture", "金矿选冶—造锍捕金", "kgce/t", ("26.10", "32.50", "36.55")),
            ("processing-bio-oxidation", "金矿选冶—生物氧化", "kgce/t", ("52.00", "60.35", "65.60")),
            ("processing-pressure-oxidation", "金矿选冶—压力氧化", "kgce/t", ("53.70", "61.15", "67.20")),
            ("refining-chemical", "金精炼—化学法", "kgce/kg", ("4.20", "4.85", "5.40")),
            ("refining-extraction", "金精炼—萃取法", "kgce/kg", ("4.50", "5.25", "5.85")),
            ("refining-electrolysis", "金精炼—电解法", "kgce/kg", ("4.10", "4.35", "4.55")),
        ],
        "page": 7, "clause": "第4章、表1～表3", "table": "表1～表3",
        "note": "开采、选冶和精炼均有工艺/规模/系数修正，未建模前明细模式必须返回不完整。",
    },
}


def refine_one(data_dir: Path, number: str) -> Path:
    cfg = CONFIG[number]
    path = next((p for p in data_dir.joinpath("definitions").glob("*.json")
                 if json.loads(p.read_text(encoding="utf-8")).get("number") == number), None)
    if path is None:
        raise FileNotFoundError(number)
    data = json.loads(path.read_text(encoding="utf-8"))
    source_file, source_sha = data["source_file"], data["source_sha256"]
    refs = [{"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
             "page": cfg["page"], "clause": cfg["clause"], "table": cfg["table"], "note": cfg["note"]}]
    products = []
    for product_id, name, unit, levels in cfg["rows"]:
        key = f"actual.{number.replace(' ', '_')}.{product_id}.energy"
        indicator = {"id": f"{number.replace(' ', '_')}.{product_id}.comprehensive-energy",
                     "name": f"{name}单位产品能耗", "unit": unit, "comparison": "lte",
                     "input_definitions": [make_input(key, f"{name}直接录入值", unit)],
                     "applicability": {"op": "always"}, "direct_input_key": key,
                     "detail_formula": None,
                     "base_thresholds": {f"level_{i}": constant(v, unit) for i, v in enumerate(levels, 1)},
                     "thresholds": {f"level_{i}": constant(v, unit) for i, v in enumerate(levels, 1)},
                     "display_places": 2, "source_references": refs,
                     "notes": ["candidate_from_original_pdf", "not_for_formal_evaluation",
                               "requires_independent_review", "detail_formula_blocked_until_factor_model_review",
                               cfg["note"]]}
        products.append({"id": product_id.replace(" ", "-"), "name": name,
                         "description": f"{number}表格产品/工序行；直接模式可录入，明细模式待系数模型复核。",
                         "input_definitions": [], "indicators": [indicator]})
    data["products"] = products
    data["publication_status"] = "draft"
    StandardDefinition.model_validate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化含修正系数的草案标准表格行")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-63/data"))
    parser.add_argument("--standard", choices=sorted(CONFIG), action="append")
    args = parser.parse_args()
    for number in args.standard or sorted(CONFIG):
        print(f"已精化 {number} 草案规则：{refine_one(args.data_dir.resolve(), number)}")


if __name__ == "__main__":
    main()
