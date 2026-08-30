from __future__ import annotations

"""Refine GB 30182-2013's comprehensive-energy and electricity indicators."""

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


def direct_definition(key: str, label: str, unit: str) -> dict:
    return {
        "key": key, "label": label, "data_type": "decimal", "unit": unit,
        "required": True, "required_if": None, "modes": ["DIRECT"],
        "minimum": "0", "maximum": None, "choices": [],
        "description": "直接录入按GB 30182-2013第5.3节核算的单位产品指标。",
    }


def indicator(number: str, source_file: str, source_sha: str, *, key_suffix: str,
              name: str, unit: str, threshold_values: tuple[str, str, str],
              detail_input: str, detail_label: str) -> dict:
    actual_key = f"actual.GB_30182_2013.{key_suffix}"
    return {
        "id": f"GB_30182_2013.friction-material.{key_suffix}",
        "name": name,
        "unit": unit,
        "comparison": "lte",
        "input_definitions": [direct_definition(actual_key, f"{name}实际值", unit)],
        "applicability": {"op": "always"},
        "direct_input_key": actual_key,
        "detail_formula": node("per_unit", args=[
            node("input", input_key=detail_input, unit=unit),
            node("input", input_key="production.total_equivalent", unit="t"),
        ], unit=unit, label=detail_label),
        "base_thresholds": {f"level_{i}": node("constant", value=value, unit=unit) for i, value in enumerate(threshold_values, 1)},
        "thresholds": {f"level_{i}": node("constant", value=value, unit=unit) for i, value in enumerate(threshold_values, 1)},
        "display_places": 2,
        "source_references": [
            {
                "standard_number": number,
                "source_file": source_file,
                "source_sha256": source_sha,
                "page": 4,
                "clause": "4.1～4.3",
                "table": "表1、表2、表3",
                "note": "现有限定值、新建准入值和先进值分别映射为3级、2级、1级。",
            },
            {
                "standard_number": number,
                "source_file": source_file,
                "source_sha256": source_sha,
                "page": 5,
                "clause": "5.3.2～5.3.4",
                "table": "公式（1）～（3）",
                "note": "综合能耗或综合电耗除以合格产品产量。",
            },
        ],
        "notes": [
            "candidate_from_original_pdf",
            "not_for_formal_evaluation",
            "requires_independent_review",
            f"detail_input_category: {detail_label}",
            "standard_scope_excludes_steel_back_or_brake_shoe_and_testing_equipment_over_15kW",
        ],
    }


def refine(data_dir: Path) -> Path:
    path = data_dir / "definitions" / "gb-30182-2013.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    number = "GB 30182-2013"
    if data.get("number") != number:
        raise ValueError(f"规则文件标准号不符：{data.get('number')}")
    source_file, source_sha = data["source_file"], data["source_sha256"]
    products = [{
        "id": "friction-material-molded",
        "name": "不带钢背（或蹄铁）的模压型摩擦材料",
        "description": "适用于GB 30182-2013范围内的摩擦材料；按合格产品产量计。",
        "input_definitions": [],
        "indicators": [
            indicator(number, source_file, source_sha,
                      key_suffix="comprehensive_energy",
                      name="摩擦材料单位产品综合能耗",
                      unit="kgce/t", threshold_values=("115", "135", "175"),
                      detail_input="energy.total_standard_coal",
                      detail_label="摩擦材料综合能耗 EZN"),
            indicator(number, source_file, source_sha,
                      key_suffix="electricity",
                      name="摩擦材料单位产品电耗",
                      unit="kWh/t", threshold_values=("800", "1000", "1300"),
                      detail_input="energy.category.direct_electricity.net_amount",
                      detail_label="摩擦材料产品综合电耗 QZD（direct_electricity分类）"),
        ],
    }]
    data["publication_status"] = "draft"
    data["products"] = products
    StandardDefinition.model_validate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 30182-2013草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-65/data"))
    args = parser.parse_args()
    print(f"已精化GB 30182-2013草案规则：{refine(args.data_dir.resolve())}")


if __name__ == "__main__":
    main()
