from __future__ import annotations

"""Refine the GB 29441-2012 draft using the normative clauses in the PDF.

The standard has one product and one unit-energy indicator.  The definition is
kept as ``draft`` until the confirmation workbook is signed.
"""

import argparse
import json
from pathlib import Path

from uebench.domain.models import StandardDefinition


def node(op: str, *, value: str | None = None, input_key: str | None = None,
         args: list[dict] | None = None, unit: str | None = None,
         label: str | None = None) -> dict:
    return {
        "op": op, "value": value, "input_key": input_key, "args": args or [],
        "cases": [], "rows": [], "default": None, "label": label,
        "unit": unit, "round_places": None,
    }


def refine(data_dir: Path) -> Path:
    path = data_dir / "definitions" / "gb-29441-2012.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    number = "GB 29441-2012"
    if data.get("number") != number:
        raise ValueError(f"规则文件标准号不符：{data.get('number')}")
    actual_key = "actual.GB_29441_2012.dilute_nitric_acid_comprehensive_energy"
    source_file = data["source_file"]
    source_sha = data["source_sha256"]
    indicator = {
        "id": "GB_29441_2012.dilute-nitric-acid.comprehensive-energy",
        "name": "稀硝酸单位产品综合能耗",
        "unit": "kgce/t",
        "comparison": "lte",
        "input_definitions": [
            {
                "key": actual_key,
                "label": "稀硝酸单位产品综合能耗实际值",
                "data_type": "decimal",
                "unit": "kgce/t",
                "required": True,
                "required_if": None,
                "modes": ["DIRECT"],
                "minimum": "0",
                "maximum": None,
                "choices": [],
                "description": "直接录入已按GB 29441-2012第5.2节核算的单位产品综合能耗。",
            }
        ],
        "applicability": {"op": "always"},
        "direct_input_key": actual_key,
        "detail_formula": node(
            "per_unit",
            args=[
                node("input", input_key="energy.total_standard_coal", unit="kgce"),
                node("input", input_key="production.total_equivalent", unit="t"),
            ],
            unit="kgce/t",
            label="稀硝酸单位产品综合能耗 e（公式1、2）",
        ),
        "base_thresholds": {
            "level_1": node("constant", value="0", unit="kgce/t"),
            "level_2": node("constant", value="20", unit="kgce/t"),
            "level_3": node("constant", value="160", unit="kgce/t"),
        },
        "thresholds": {
            "level_1": node("constant", value="0", unit="kgce/t"),
            "level_2": node("constant", value="20", unit="kgce/t"),
            "level_3": node("constant", value="160", unit="kgce/t"),
        },
        "display_places": 2,
        "source_references": [
            {
                "standard_number": number,
                "source_file": source_file,
                "source_sha256": source_sha,
                "page": 4,
                "clause": "4.1～4.3",
                "table": "正文限定值、准入值、先进值",
                "note": "原文明确给出160、20、0 kgce/t；分别映射为3级、2级、1级。",
            },
            {
                "standard_number": number,
                "source_file": source_file,
                "source_sha256": source_sha,
                "page": 5,
                "clause": "5.2.1～5.2.2",
                "table": "公式（1）、（2）",
                "note": "综合能耗为输入能源折标量减输出能源折标量，单位产品值为综合能耗除以产量。",
            },
        ],
        "notes": [
            "candidate_from_original_pdf",
            "not_for_formal_evaluation",
            "requires_independent_review",
            "detail_formula_uses_energy_lines_and_qualified_production_lines",
            "standard_scope_excludes_ammonia_energy_and_sodium_nitrate_or_nitrite_energy",
        ],
    }
    data["publication_status"] = "draft"
    data["products"] = [{
        "id": "dilute-nitric-acid",
        "name": "稀硝酸（折HNO3 100%）",
        "description": "以合成氨为原料的稀硝酸生产；产量按折HNO3 100%计。",
        "input_definitions": [],
        "indicators": [indicator],
    }]
    StandardDefinition.model_validate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 29441-2012草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-65/data"))
    args = parser.parse_args()
    print(f"已精化GB 29441-2012草案规则：{refine(args.data_dir.resolve())}")


if __name__ == "__main__":
    main()
