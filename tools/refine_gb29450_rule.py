from __future__ import annotations

"""Refine the two three-level GB 29450-2012 pool-kiln yarn rows.

The other products in Table 1 do not have all three level values in Tables
2--3, so they remain outside this candidate set until their grade mapping is
explicitly confirmed.
"""

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
    path = data_dir / "definitions" / "gb-29450-2012.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    number = "GB 29450-2012"
    if data.get("number") != number:
        raise ValueError(f"规则文件标准号不符：{data.get('number')}")
    source_file, source_sha = data["source_file"], data["source_sha256"]
    rows = [
        ("pool-e-gt5", "池窑法E玻璃纤维纱（纤维直径≤9μm）", ("750", "750", "900"), True),
        ("pool-ecr-gt9", "池窑法E(ECR)玻璃纤维纱（纤维直径＞9μm）", ("550", "550", "700"), False),
    ]
    products = []
    for product_id, name, levels, fine_yarn in rows:
        actual_key = f"actual.GB_29450_2012.{product_id}.comprehensive_energy"
        definitions = [{
            "key": actual_key,
            "label": f"{name}单位产品综合能耗实际值",
            "data_type": "decimal",
            "unit": "kgce/t",
            "required": True,
            "required_if": None,
            "modes": ["DIRECT"],
            "minimum": "0",
            "maximum": None,
            "choices": [],
            "description": "直接录入按GB 29450-2012第5.2节核算的单位产品综合能耗。",
        }]
        if fine_yarn:
            definitions.extend([
                {
                    "key": "glass_fiber.fine_yarn.gt5um_t",
                    "label": "合格玻璃纤维细纱（纤维直径＞5μm）产量",
                    "data_type": "decimal", "unit": "t", "required": True,
                    "required_if": None, "modes": ["DETAIL"], "minimum": "0",
                    "maximum": None, "choices": [], "description": "公式（3）中的Gy9。",
                },
                {
                    "key": "glass_fiber.fine_yarn.le5um_t",
                    "label": "合格玻璃纤维细纱（纤维直径≤5μm）产量",
                    "data_type": "decimal", "unit": "t", "required": True,
                    "required_if": None, "modes": ["DETAIL"], "minimum": "0",
                    "maximum": None, "choices": [], "description": "公式（3）中的Gy5。",
                },
            ])
            production = node("add", args=[
                node("input", input_key="glass_fiber.fine_yarn.gt5um_t", unit="t"),
                node("multiply", args=[node("constant", value="1.5"), node("input", input_key="glass_fiber.fine_yarn.le5um_t", unit="t")], unit="t"),
            ], unit="t", label="细纱折算产量 Gyz9（公式3）")
        else:
            production = node("input", input_key="production.total_equivalent", unit="t")
        indicator = {
            "id": f"GB_29450_2012.{product_id}.comprehensive-energy",
            "name": f"{name}单位产品综合能耗",
            "unit": "kgce/t", "comparison": "lte", "input_definitions": definitions,
            "applicability": {"op": "always"}, "direct_input_key": actual_key,
            "detail_formula": node("per_unit", args=[
                node("input", input_key="energy.total_standard_coal", unit="kgce"), production,
            ], unit="kgce/t", label="玻璃纤维纱单位产品综合能耗（公式7、8）"),
            "base_thresholds": {f"level_{i}": node("constant", value=value, unit="kgce/t") for i, value in enumerate(levels, 1)},
            "thresholds": {f"level_{i}": node("constant", value=value, unit="kgce/t") for i, value in enumerate(levels, 1)},
            "display_places": 2,
            "source_references": [
                {"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                 "page": 4, "clause": "4.1～4.3", "table": "表1、表2、表3",
                 "note": "三等级限额按原文现有限定值、准入值、先进值对应录入。"},
                {"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                 "page": 7, "clause": "5.2.2.1～5.2.2.3", "table": "公式（3）～（8）",
                 "note": "能耗为输入能源减输出能源，产量按对应工艺的合格折算产量计算。"},
            ],
            "notes": ["candidate_from_original_pdf", "not_for_formal_evaluation", "requires_independent_review",
                      "standard_scope_excludes_special_glass_fibers", "detail_energy_lines_are_scoped_to_the_selected_product"],
        }
        products.append({"id": product_id, "name": name,
                         "description": "池窑法玻璃纤维纱，按标准折算合格产量计。",
                         "input_definitions": [], "indicators": [indicator]})
    data["publication_status"] = "draft"
    data["products"] = products
    StandardDefinition.model_validate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 29450-2012草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-65/data"))
    args = parser.parse_args()
    print(f"已精化GB 29450-2012草案规则：{refine(args.data_dir.resolve())}")


if __name__ == "__main__":
    main()
