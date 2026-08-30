from __future__ import annotations

"""Refine the three GB 40878-2021 process rows from Table 1."""

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
    path = data_dir / "definitions" / "gb-40878-2021.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    number = "GB 40878-2021"
    if data.get("number") != number:
        raise ValueError(f"规则文件标准号不符：{data.get('number')}")
    source_file, source_sha = data["source_file"], data["source_sha256"]
    rows = [
        ("starch-fermentation", "以淀粉为原料发酵法", ("272", "280", "324")),
        ("starch-enzymatic", "以淀粉为原料酶法", ("260", "268", "290")),
        ("glucose-catalytic-oxidation", "以葡萄糖为原料催化氧化法", ("156", "156", "160")),
    ]
    products = []
    for product_id, name, levels in rows:
        actual_key = f"actual.GB_40878_2021.{product_id}.comprehensive_energy"
        indicator = {
            "id": f"GB_40878_2021.{product_id}.comprehensive-energy",
            "name": f"{name}葡萄糖酸钠单位产品综合能耗", "unit": "kgce/t",
            "comparison": "lte",
            "input_definitions": [{
                "key": actual_key, "label": f"{name}葡萄糖酸钠单位产品综合能耗实际值",
                "data_type": "decimal", "unit": "kgce/t", "required": True,
                "required_if": None, "modes": ["DIRECT"], "minimum": "0",
                "maximum": None, "choices": [],
                "description": "直接录入按GB 40878-2021第6.2节核算的单位产品综合能耗。",
            }],
            "applicability": {"op": "always"}, "direct_input_key": actual_key,
            "detail_formula": node("per_unit", args=[
                node("input", input_key="energy.total_standard_coal", unit="kgce"),
                node("input", input_key="production.total_equivalent", unit="t"),
            ], unit="kgce/t", label="葡萄糖酸钠单位产品综合能耗 e（公式1、2）"),
            "base_thresholds": {f"level_{i}": node("constant", value=value, unit="kgce/t") for i, value in enumerate(levels, 1)},
            "thresholds": {f"level_{i}": node("constant", value=value, unit="kgce/t") for i, value in enumerate(levels, 1)},
            "display_places": 2,
            "source_references": [
                {"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                 "page": 4, "clause": "4.1", "table": "表1",
                 "note": "按淀粉原料发酵、淀粉原料酶法或葡萄糖原料催化氧化工艺选择。"},
                {"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                 "page": 5, "clause": "6.2.1～6.2.2", "table": "公式（1）、（2）",
                 "note": "综合能耗按输入能源折标量求和后除以产品产量。"},
            ],
            "notes": ["candidate_from_original_pdf", "not_for_formal_evaluation", "requires_independent_review",
                      "process_route_is_encoded_in_product_name_and_must_be_confirmed"],
        }
        products.append({"id": product_id, "name": name,
                         "description": "葡萄糖酸钠产品按工艺路线和合格产量计。",
                         "input_definitions": [], "indicators": [indicator]})
    data["publication_status"] = "draft"
    data["products"] = products
    StandardDefinition.model_validate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 40878-2021草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-65/data"))
    args = parser.parse_args()
    print(f"已精化GB 40878-2021草案规则：{refine(args.data_dir.resolve())}")


if __name__ == "__main__":
    main()
