from __future__ import annotations

"""Refine the 31 product rows of GB 29435-2012.

The source tables provide three limits for every product: advanced (level 1),
access (level 2) and existing (level 3).  This script gives each row its
product name and models the standard's tce/t result from the engine's kgce
energy input.  The definition deliberately remains ``draft`` until the
confirmation workbook is completed and independently reviewed.
"""

import argparse
import json
from pathlib import Path

from uebench.domain.models import StandardDefinition


NUMBER = "GB 29435-2012"


def node(op: str, *, value: str | None = None, input_key: str | None = None,
         args: list[dict] | None = None, unit: str | None = None,
         label: str | None = None) -> dict:
    return {
        "op": op, "value": value, "input_key": input_key, "args": args or [],
        "cases": [], "rows": [], "default": None, "label": label,
        "unit": unit, "round_places": None,
    }


def refine(data_dir: Path) -> Path:
    path = data_dir / "definitions" / "gb-29435-2012.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    if original.get("number") != NUMBER:
        raise ValueError(f"规则文件标准号不符：{original.get('number')}")

    # Table 1 (existing), Table 2 (access) and Table 3 (advanced), in the
    # exact row order of the standard.  Values are tce/t.
    rows = [
        ("lanthanum-oxide", "氧化镧", ("2.19", "2.31", "2.54")),
        ("cerium-oxide", "氧化铈", ("2.47", "2.60", "2.86")),
        ("praseodymium-oxide", "氧化镨", ("2.49", "2.62", "2.88")),
        ("neodymium-oxide", "氧化钕", ("2.45", "2.58", "2.84")),
        ("samarium-oxide", "氧化钐", ("2.25", "2.37", "2.61")),
        ("europium-oxide", "氧化铕", ("2.58", "2.72", "2.99")),
        ("gadolinium-oxide", "氧化钆", ("1.94", "2.04", "2.25")),
        ("terbium-oxide", "氧化铽", ("2.16", "2.27", "2.50")),
        ("dysprosium-oxide", "氧化镝", ("2.16", "2.27", "2.50")),
        ("holmium-oxide", "氧化钬", ("1.98", "2.08", "2.29")),
        ("erbium-oxide", "氧化铒", ("1.97", "2.07", "2.27")),
        ("thulium-oxide", "氧化铥", ("2.02", "2.13", "2.35")),
        ("ytterbium-oxide", "氧化镱", ("2.09", "2.20", "2.41")),
        ("rare-earth-tricolor-red", "灯用稀土三基色荧光粉（红）", ("0.81", "0.85", "0.94")),
        ("rare-earth-tricolor-green", "灯用稀土三基色荧光粉（绿）", ("2.67", "2.81", "3.09")),
        ("rare-earth-tricolor-blue", "灯用稀土三基色荧光粉（蓝）", ("3.87", "4.07", "4.48")),
        ("lutetium-oxide", "氧化镥", ("2.18", "2.29", "2.52")),
        ("yttrium-oxide", "氧化钇", ("2.06", "2.17", "2.39")),
        ("yttrium-europium-oxide", "荧光级氧化钇铕", ("1.96", "2.06", "2.26")),
        ("praseodymium-neodymium-oxide", "镨钕氧化物", ("2.35", "2.47", "2.71")),
        ("lanthanum-metal", "金属镧", ("1.32", "1.39", "1.53")),
        ("cerium-metal", "金属铈", ("1.10", "1.16", "1.28")),
        ("praseodymium-metal", "金属镨", ("1.23", "1.29", "1.42")),
        ("neodymium-metal", "金属钕", ("1.15", "1.21", "1.33")),
        ("samarium-metal", "金属钐", ("3.15", "3.32", "3.65")),
        ("dysprosium-metal", "金属镝", ("2.24", "2.36", "2.60")),
        ("praseodymium-neodymium-alloy", "镨钕合金", ("1.23", "1.29", "1.42")),
        ("gadolinium-iron-alloy", "钆铁合金", ("1.31", "1.38", "1.52")),
        ("dysprosium-iron-alloy", "镝铁合金", ("1.37", "1.44", "1.58")),
        ("mixed-rare-earth-metal", "混合稀土金属", ("1.62", "1.70", "1.87")),
        ("rare-earth-polishing-powder", "稀土抛光粉", ("1.56", "1.64", "1.80")),
    ]
    if len(original.get("products", [])) != len(rows):
        raise ValueError("原规则产品行数不是31，拒绝静默覆盖")

    source_file, source_sha = original["source_file"], original["source_sha256"]
    references = [
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 4, "clause": "第4章、表1、表2", "table": "表1、表2",
         "note": "表1为现有水平、表2为准入值；本规则按表中产品行逐一映射。"},
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 5, "clause": "第4章、表3", "table": "表3",
         "note": "表3为先进值；等级比较方向为单位产品综合能耗越低越好。"},
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 7, "clause": "5.2、6.1～6.3", "table": "公式及统计范围",
         "note": "综合能耗按标准规定的生产系统边界折标后除以合格产品产量；具体工序边界仍需复核。"},
    ]

    products: list[dict] = []
    for product_id, name, levels in rows:
        actual_key = f"actual.GB_29435_2012.{product_id}.energy"
        energy = node("input", input_key="energy.total_standard_coal", unit="kgce",
                      label="统计期综合能耗（标准煤）")
        production = node("input", input_key="production.total_equivalent", unit="t",
                          label=f"{name}合格产品产量")
        # The domain engine stores standard coal in kgce; the standard table
        # reports tce/t, so divide the energy numerator by 1000 first.
        detail = node("divide", args=[
            node("divide", args=[energy, node("constant", value="1000", unit="kgce/tce")],
                 unit="tce", label="综合能耗折算为吨标准煤"),
            production], unit="tce/t", label=f"{name}单位产品综合能耗（第5.2节）")
        defs = [{
            "key": actual_key, "label": f"{name}单位产品综合能耗实际值",
            "data_type": "decimal", "unit": "tce/t", "required": True,
            "required_if": None, "modes": ["DIRECT"], "minimum": "0",
            "maximum": None, "choices": [],
            "description": f"直接录入按GB 29435-2012第5章核算的{name}单位产品综合能耗。",
        }]
        indicator = {
            "id": f"GB_29435_2012.{product_id}.comprehensive-energy",
            "name": f"{name}单位产品综合能耗", "unit": "tce/t", "comparison": "lte",
            "input_definitions": defs, "applicability": {"op": "always"},
            "direct_input_key": actual_key, "detail_formula": detail,
            "base_thresholds": {f"level_{i}": node("constant", value=value, unit="tce/t")
                                for i, value in enumerate(levels, 1)},
            "thresholds": {f"level_{i}": node("constant", value=value, unit="tce/t")
                           for i, value in enumerate(levels, 1)},
            "display_places": 2, "source_references": references,
            "notes": ["candidate_from_original_pdf", "not_for_formal_evaluation",
                      "requires_independent_review",
                      "product_name_and_three_levels_transcribed_from_tables_1_2_3",
                      "production_boundary_and_qualified_output_definition_require_clause_5_review"],
        }
        products.append({"id": product_id, "name": name,
                         "description": f"GB 29435-2012表1～表3的{name}产品行。",
                         "input_definitions": [], "indicators": [indicator]})

    original["products"] = products
    original["publication_status"] = "draft"
    StandardDefinition.model_validate(original)
    path.write_text(json.dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 29435-2012草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-65/data"))
    args = parser.parse_args()
    print(f"已精化 {NUMBER} 草案规则：{refine(args.data_dir.resolve())}")


if __name__ == "__main__":
    main()
