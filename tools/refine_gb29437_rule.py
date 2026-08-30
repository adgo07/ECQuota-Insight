from __future__ import annotations

"""Refine the four GB 29437-2012 process rows from Tables 1--3."""

import argparse
import json
import re
from pathlib import Path

from uebench.domain.models import StandardDefinition


def node(op: str, *, value: str | None = None, input_key: str | None = None,
         args: list[dict] | None = None, unit: str | None = None,
         label: str | None = None) -> dict:
    return {"op": op, "value": value, "input_key": input_key, "args": args or [],
            "cases": [], "rows": [], "default": None, "label": label,
            "unit": unit, "round_places": None}


def slug(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z一-龥]+", "_", value).strip("_").lower()


def refine(data_dir: Path) -> Path:
    path = data_dir / "definitions" / "gb-29437-2012.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    number = "GB 29437-2012"
    if data.get("number") != number:
        raise ValueError(f"规则文件标准号不符：{data.get('number')}")
    source_file = data["source_file"]
    source_sha = data["source_sha256"]
    rows = [
        ("羰基法（年产20万t及以上醋酸）", "carbonyl_200kt", "106", "124", "176"),
        ("酒精法—空气氧化乙醛", "ethanol_air", "418", "418", "500"),
        ("酒精法—氧气氧化乙醛", "ethanol_oxygen", "429", "429", "505"),
        ("乙烯法", "ethylene", "300", "300", "429"),
    ]
    products = []
    for name, product_id, level1, level2, level3 in rows:
        actual_key = f"actual.GB_29437_2012.{product_id}.comprehensive_energy"
        indicator = {
            "id": f"GB_29437_2012.{product_id}.comprehensive-energy",
            "name": f"{name}工业冰醋酸单位产品综合能耗",
            "unit": "kgce/t",
            "comparison": "lte",
            "input_definitions": [{
                "key": actual_key,
                "label": f"{name}工业冰醋酸单位产品综合能耗实际值",
                "data_type": "decimal",
                "unit": "kgce/t",
                "required": True,
                "required_if": None,
                "modes": ["DIRECT"],
                "minimum": "0",
                "maximum": None,
                "choices": [],
                "description": "直接录入按GB 29437-2012第5.2节核算的单位产品综合能耗。",
            }],
            "applicability": {"op": "always"},
            "direct_input_key": actual_key,
            "detail_formula": node(
                "per_unit",
                args=[
                    node("input", input_key="energy.total_standard_coal", unit="kgce"),
                    node("input", input_key="production.total_equivalent", unit="t"),
                ],
                unit="kgce/t",
                label="工业冰醋酸单位产品综合能耗 EZH（公式1）",
            ),
            "base_thresholds": {f"level_{i}": node("constant", value=value, unit="kgce/t") for i, value in enumerate((level1, level2, level3), 1)},
            "thresholds": {f"level_{i}": node("constant", value=value, unit="kgce/t") for i, value in enumerate((level1, level2, level3), 1)},
            "display_places": 2,
            "source_references": [
                {
                    "standard_number": number,
                    "source_file": source_file,
                    "source_sha256": source_sha,
                    "page": 4,
                    "clause": "4.1、4.2",
                    "table": "表1、表2",
                    "note": "分别对应现有装置限定值和新建装置准入值。",
                },
                {
                    "standard_number": number,
                    "source_file": source_file,
                    "source_sha256": source_sha,
                    "page": 5,
                    "clause": "4.3、5.2",
                    "table": "表3、公式（1）",
                    "note": "先进值及输入能源减输出能源后除以成品产量。",
                },
            ],
            "notes": [
                "candidate_from_original_pdf",
                "not_for_formal_evaluation",
                "requires_independent_review",
                "standard_scope_excludes_raw_material_energy_and_excludes_self-produced_secondary_energy",
            ],
        }
        products.append({
            "id": product_id,
            "name": name,
            "description": "工业冰醋酸产品按折100%醋酸合格产量计。",
            "input_definitions": [],
            "indicators": [indicator],
        })
    data["publication_status"] = "draft"
    data["products"] = products
    StandardDefinition.model_validate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 29437-2012草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-65/data"))
    args = parser.parse_args()
    print(f"已精化GB 29437-2012草案规则：{refine(args.data_dir.resolve())}")


if __name__ == "__main__":
    main()
