from __future__ import annotations

"""Refine GB 36887-2018 synthetic-leather and DMF-recovery rows."""

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
    path = data_dir / "definitions" / "gb-36887-2018.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    number = "GB 36887-2018"
    if data.get("number") != number:
        raise ValueError(f"规则文件标准号不符：{data.get('number')}")
    source_file, source_sha = data["source_file"], data["source_sha256"]
    rows = [
        ("synthetic-leather-class-1", "合成革第1类", "kgce/tsl", ("250", "275", "400"), "tsl"),
        ("synthetic-leather-class-2", "合成革第2类", "kgce/tsl", ("200", "220", "320"), "tsl"),
        ("synthetic-leather-class-3", "合成革第3类", "kgce/tsl", ("50", "55", "80"), "tsl"),
        ("synthetic-leather-class-4", "合成革第4类", "kgce/tsl", ("250", "275", "400"), "tsl"),
        ("synthetic-leather-class-5", "合成革第5类", "kgce/tsl", ("500", "550", "800"), "tsl"),
        ("dmf-recovery", "DMF回收", "kgce/tdmf", ("350", "380", "500"), "tdmf"),
    ]
    products = []
    for product_id, name, unit, levels, production_unit in rows:
        actual_key = f"actual.GB_36887_2018.{product_id}.energy"
        indicator = {
            "id": f"GB_36887_2018.{product_id}.comprehensive-energy",
            "name": f"{name}单位产品综合能耗", "unit": unit, "comparison": "lte",
            "input_definitions": [{
                "key": actual_key, "label": f"{name}单位产品综合能耗实际值",
                "data_type": "decimal", "unit": unit, "required": True,
                "required_if": None, "modes": ["DIRECT"], "minimum": "0",
                "maximum": None, "choices": [],
                "description": f"直接录入按GB 36887-2018第8章核算的{unit}指标。",
            }],
            "applicability": {"op": "always"}, "direct_input_key": actual_key,
            "detail_formula": node("per_unit", args=[
                node("input", input_key="energy.total_standard_coal", unit="kgce"),
                node("input", input_key="production.total_equivalent", unit=production_unit),
            ], unit=unit, label="合成革/DMF单位产品综合能耗（第8章公式）"),
            "base_thresholds": {f"level_{i}": node("constant", value=value, unit=unit) for i, value in enumerate(levels, 1)},
            "thresholds": {f"level_{i}": node("constant", value=value, unit=unit) for i, value in enumerate(levels, 1)},
            "display_places": 2,
            "source_references": [
                {"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                 "page": 4, "clause": "4.1～4.5", "table": "表1～表5",
                 "note": "按合成革类别或DMF回收产品选择相应三等级限额。"},
                {"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                 "page": 7, "clause": "8.1～8.4", "table": "公式（1）～（4）",
                 "note": "综合能耗按输入能源折标量减输出能源折标量，再按对应产品产量折算。"},
            ],
            "notes": ["candidate_from_original_pdf", "not_for_formal_evaluation", "requires_independent_review",
                      "product_class_definition_must_be_checked_against_clause_4_and_table_1"],
        }
        products.append({"id": product_id, "name": name,
                         "description": "按GB 36887-2018类别定义和合格产量计。",
                         "input_definitions": [], "indicators": [indicator]})
    data["publication_status"] = "draft"
    data["products"] = products
    StandardDefinition.model_validate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 36887-2018草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-65/data"))
    args = parser.parse_args()
    print(f"已精化GB 36887-2018草案规则：{refine(args.data_dir.resolve())}")


if __name__ == "__main__":
    main()
