from __future__ import annotations

"""Refine GB 32044-2015's three sugar process rows."""

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
    path = data_dir / "definitions" / "gb-32044-2015.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    number = "GB 32044-2015"
    if data.get("number") != number:
        raise ValueError(f"规则文件标准号不符：{data.get('number')}")
    source_file, source_sha = data["source_file"], data["source_sha256"]
    rows = [
        ("sugarcane", "甘蔗制糖", ("225", "320", "550")),
        ("beet", "甜菜制糖", ("318", "360", "630")),
        ("refining", "炼糖", ("200", "220", "320")),
    ]
    products = []
    for product_id, name, levels in rows:
        actual_key = f"actual.GB_32044_2015.{product_id}.comprehensive_energy"
        indicator = {
            "id": f"GB_32044_2015.{product_id}.comprehensive-energy",
            "name": f"{name}单位产品能耗", "unit": "kgce/t", "comparison": "lte",
            "input_definitions": [{
                "key": actual_key, "label": f"{name}单位产品能耗实际值",
                "data_type": "decimal", "unit": "kgce/t", "required": True,
                "required_if": None, "modes": ["DIRECT"], "minimum": "0",
                "maximum": None, "choices": [],
                "description": "直接录入按GB 32044-2015第5.2节核算的单位产品能耗。",
            }],
            "applicability": {"op": "always"}, "direct_input_key": actual_key,
            "detail_formula": node("per_unit", args=[
                node("input", input_key="energy.total_standard_coal", unit="kgce"),
                node("input", input_key="production.total_equivalent", unit="t"),
            ], unit="kgce/t", label="糖单位产品能耗 e（公式1、2）"),
            "base_thresholds": {f"level_{i}": node("constant", value=value, unit="kgce/t") for i, value in enumerate(levels, 1)},
            "thresholds": {f"level_{i}": node("constant", value=value, unit="kgce/t") for i, value in enumerate(levels, 1)},
            "display_places": 2,
            "source_references": [
                {"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                 "page": 3, "clause": "4.1", "table": "表1",
                 "note": "现有糖生产企业单位产品能耗限定值。"},
                {"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                 "page": 4, "clause": "4.2～4.3", "table": "表2、表3",
                 "note": "新建/改扩建准入值与先进值对应1级、2级、3级。"},
                {"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                 "page": 5, "clause": "5.2.3～5.2.4", "table": "公式（1）、（2）",
                 "note": "输入能源折标量减输出能源折标量后除以等折一级白砂糖产量。"},
            ],
            "notes": ["candidate_from_original_pdf", "not_for_formal_evaluation", "requires_independent_review",
                      "qualified_output_is_equivalent_first_grade_white_sugar_per_clause_5_2_2"],
        }
        products.append({"id": product_id, "name": name,
                         "description": "糖产品按工艺类型、合格产量和等折一级白砂糖口径计。",
                         "input_definitions": [], "indicators": [indicator]})
    data["publication_status"] = "draft"
    data["products"] = products
    StandardDefinition.model_validate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 32044-2015草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-63/data"))
    args = parser.parse_args()
    print(f"已精化GB 32044-2015草案规则：{refine(args.data_dir.resolve())}")


if __name__ == "__main__":
    main()
