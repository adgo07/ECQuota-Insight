from __future__ import annotations

"""Refine the five product/temperature rows in GB 36890-2018 Table 1."""

import argparse
import json
from pathlib import Path

from uebench.domain.models import StandardDefinition


def node(op: str, *, value: str | None = None, input_key: str | None = None,
         args: list[dict] | None = None, unit: str | None = None,
         label: str | None = None) -> dict:
    return {"op": op, "value": value, "input_key": input_key, "args": args or [],
            "cases": [], "rows": [], "default": None, "label": label,
            "unit": unit, "round_places": None}


def refine(data_dir: Path) -> Path:
    path = data_dir / "definitions" / "gb-36890-2018.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    number = "GB 36890-2018"
    if data.get("number") != number:
        raise ValueError(f"规则文件标准号不符：{data.get('number')}")
    source_file, source_sha = data["source_file"], data["source_sha256"]
    rows = [
        ("daily-porcelain-single-le1280", "日用瓷一次（烧成温度≤1280℃）", ("500", "630", "740")),
        ("daily-porcelain-single-gt1280", "日用瓷一次（烧成温度＞1280℃）", ("600", "730", "860")),
        ("daily-porcelain-multi", "日用瓷二次（含二次以上）", ("740", "890", "1050")),
        ("daily-pottery-single-le1280", "日用陶器一次（烧成温度≤1280℃）", ("430", "550", "640")),
        ("daily-pottery-multi", "日用陶器二次（含二次以上）", ("660", "830", "980")),
    ]
    products = []
    for product_id, name, levels in rows:
        actual_key = f"actual.GB_36890_2018.{product_id}.comprehensive_energy"
        indicator = {
            "id": f"GB_36890_2018.{product_id}.comprehensive-energy",
            "name": f"{name}单位产品综合能耗", "unit": "kgce/t", "comparison": "lte",
            "input_definitions": [{
                "key": actual_key, "label": f"{name}单位产品综合能耗实际值",
                "data_type": "decimal", "unit": "kgce/t", "required": True,
                "required_if": None, "modes": ["DIRECT"], "minimum": "0",
                "maximum": None, "choices": [],
                "description": "直接录入按GB 36890-2018第7章核算的单位产品综合能耗。",
            }],
            "applicability": {"op": "always"}, "direct_input_key": actual_key,
            "detail_formula": node("per_unit", args=[
                node("input", input_key="energy.total_standard_coal", unit="kgce"),
                node("input", input_key="production.total_equivalent", unit="t"),
            ], unit="kgce/t", label="日用陶瓷单位产品综合能耗（第7章公式）"),
            "base_thresholds": {f"level_{i}": node("constant", value=value, unit="kgce/t") for i, value in enumerate(levels, 1)},
            "thresholds": {f"level_{i}": node("constant", value=value, unit="kgce/t") for i, value in enumerate(levels, 1)},
            "display_places": 2,
            "source_references": [
                {"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                 "page": 4, "clause": "4.1～4.3", "table": "表1、表2、表3",
                 "note": "按产品类型、烧成次数和烧成温度条件对应表中三等级限额。"},
                {"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                 "page": 5, "clause": "7.1～7.4", "table": "公式（1）～（3）",
                 "note": "综合能耗按输入能源减输出能源后除以合格产品产量。"},
            ],
            "notes": ["candidate_from_original_pdf", "not_for_formal_evaluation", "requires_independent_review",
                      "temperature_and_firing_count_are_encoded_in_product_name_and_must_be_confirmed"],
        }
        products.append({"id": product_id, "name": name,
                         "description": "日用陶瓷产品按标准表1的烧成条件和合格产量计。",
                         "input_definitions": [], "indicators": [indicator]})
    data["publication_status"] = "draft"
    data["products"] = products
    StandardDefinition.model_validate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 36890-2018草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-63/data"))
    args = parser.parse_args()
    print(f"已精化GB 36890-2018草案规则：{refine(args.data_dir.resolve())}")


if __name__ == "__main__":
    main()
