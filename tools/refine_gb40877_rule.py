from __future__ import annotations

"""Refine the five GB 40877-2021 product rows in Table 1."""

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
    path = data_dir / "definitions" / "gb-40877-2021.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    number = "GB 40877-2021"
    if data.get("number") != number:
        raise ValueError(f"规则文件标准号不符：{data.get('number')}")
    source_file, source_sha = data["source_file"], data["source_sha256"]
    rows = [
        ("aluminosilicate-fiber-1000-1250", "硅酸铝纤维（1000℃、1200℃、1250℃）", ("208", "228", "263")),
        ("aluminosilicate-fiber-1350-1500", "硅酸铝纤维（1350℃、1400℃、1500℃）", ("245", "256", "311")),
        ("needle-punched-blanket", "硅酸铝纤维制品—针刺毯", ("65", "77", "85")),
        ("wet-continuous-rolled", "硅酸铝纤维制品—湿法制品（连续轧制）", ("410", "465", "486")),
        ("wet-vacuum-filtered", "硅酸铝纤维制品—湿法制品（真空吸滤）", ("750", "780", "836")),
    ]
    products = []
    for product_id, name, levels in rows:
        actual_key = f"actual.GB_40877_2021.{product_id}.comprehensive_energy"
        indicator = {
            "id": f"GB_40877_2021.{product_id}.comprehensive-energy",
            "name": f"{name}单位产品综合能耗", "unit": "kgce/t", "comparison": "lte",
            "input_definitions": [{
                "key": actual_key, "label": f"{name}单位产品综合能耗实际值",
                "data_type": "decimal", "unit": "kgce/t", "required": True,
                "required_if": None, "modes": ["DIRECT"], "minimum": "0",
                "maximum": None, "choices": [],
                "description": "直接录入按GB 40877-2021第6章核算的单位产品综合能耗。",
            }],
            "applicability": {"op": "always"}, "direct_input_key": actual_key,
            "detail_formula": node("per_unit", args=[
                node("input", input_key="energy.total_standard_coal", unit="kgce"),
                node("input", input_key="production.total_equivalent", unit="t"),
            ], unit="kgce/t", label="硅酸铝纤维及制品单位产品综合能耗 e（公式1、2）"),
            "base_thresholds": {f"level_{i}": node("constant", value=value, unit="kgce/t") for i, value in enumerate(levels, 1)},
            "thresholds": {f"level_{i}": node("constant", value=value, unit="kgce/t") for i, value in enumerate(levels, 1)},
            "display_places": 2,
            "source_references": [
                {"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                 "page": 4, "clause": "4.1", "table": "表1",
                 "note": "按纤维使用温度或制品成型工艺选择三等级限额。"},
                {"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                 "page": 6, "clause": "6.2.1～6.2.2", "table": "公式（1）、（2）",
                 "note": "综合能耗按输入能源折标量求和后除以合格产品产量。"},
            ],
            "notes": ["candidate_from_original_pdf", "not_for_formal_evaluation", "requires_independent_review",
                      "temperature_or_forming_process_is_encoded_in_product_name_and_must_be_confirmed"],
        }
        products.append({"id": product_id, "name": name,
                         "description": "按GB 40877-2021表1产品类型和合格产量计。",
                         "input_definitions": [], "indicators": [indicator]})
    data["publication_status"] = "draft"
    data["products"] = products
    StandardDefinition.model_validate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 40877-2021草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-63/data"))
    args = parser.parse_args()
    print(f"已精化GB 40877-2021草案规则：{refine(args.data_dir.resolve())}")


if __name__ == "__main__":
    main()
