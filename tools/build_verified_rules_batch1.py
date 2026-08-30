"""Build high-confidence rules directly from clearly readable original PDF tables.

This script intentionally marks generated definitions as ``reviewed`` rather than
``published``.  A human standards reviewer must still complete the confirmation
workbook before the signed package can be used for formal evaluation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def node(op: str, *, value: str | None = None, input_key: str | None = None,
         args: list[dict] | None = None, unit: str | None = None,
         label: str | None = None) -> dict:
    return {
        "op": op, "value": value, "input_key": input_key, "args": args or [],
        "cases": [], "rows": [], "default": None, "label": label,
        "unit": unit, "round_places": None,
    }


def constant(value: str, unit: str) -> dict:
    return node("constant", value=str(value), unit=unit)


def input_node(key: str) -> dict:
    return node("input", input_key=key)


def multiply(*args: dict, unit: str | None = None, label: str | None = None) -> dict:
    return node("multiply", args=list(args), unit=unit, label=label)


def source(number: str) -> tuple[str, str]:
    catalog = json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))["standards"]
    row = next(item for item in catalog if item["number"] == number)
    return row["source_file"], row["source_sha256"]


def input_def(key: str, label: str, unit: str, *, required: bool = True,
             description: str | None = None) -> dict:
    return {
        "key": key, "label": label, "data_type": "decimal", "unit": unit,
        "required": required, "required_if": None,
        "modes": ["DIRECT", "DETAIL"], "minimum": "0", "maximum": None,
        "choices": [], "description": description,
    }


def indicator(number: str, identifier: str, name: str, unit: str,
              values: list[str], *, page: int, table: str,
              extra_inputs: list[dict] | None = None,
              threshold_multiplier_key: str | None = None,
              notes: list[str] | None = None) -> dict:
    file, sha = source(number)
    actual_key = f"actual.{identifier}"
    inputs = [input_def(actual_key, f"{name}实际值", unit)]
    if extra_inputs:
        inputs.extend(extra_inputs)
    thresholds: dict[str, dict] = {}
    for level, value in zip((1, 2, 3), values, strict=True):
        base = constant(value, unit)
        thresholds[f"level_{level}"] = (
            multiply(base, input_node(threshold_multiplier_key), unit=unit,
                     label="厚度总体修正系数")
            if threshold_multiplier_key else base
        )
    return {
        "id": f"{number.replace(' ', '_')}.{identifier}",
        "name": name, "unit": unit, "comparison": "lte",
        "input_definitions": inputs,
        "applicability": {"op": "always"},
        "direct_input_key": actual_key,
        "detail_formula": node("per_unit", args=[
            input_node("energy.total_standard_coal"),
            input_node("production.total_equivalent"),
        ], unit=unit, label="单位产品综合能耗"),
        "base_thresholds": {f"level_{i}": constant(v, unit) for i, v in enumerate(values, 1)},
        "thresholds": thresholds,
        "display_places": 2,
        "source_references": [{
            "standard_number": number, "source_file": file, "source_sha256": sha,
            "page": page, "clause": "第4章 能耗限额等级", "table": table,
            "note": "已按强制性标准原文表格录入；待独立复核和确认表签署。",
        }],
        "notes": notes or ["original_pdf_transcribed", "requires_independent_review"],
    }


def write_definition(number: str, products: list[dict]) -> None:
    path = DATA / "definitions" / f"{re.sub(r'[^a-z0-9]+', '-', number.lower()).strip('-')}.json"
    old = json.loads(path.read_text(encoding="utf-8"))
    old["publication_status"] = "reviewed"
    old["products"] = products
    path.write_text(json.dumps(old, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def one_product(ind: dict, name: str | None = None) -> dict:
    return {
        "id": ind["id"].lower().replace(".", "-"),
        "name": name or ind["name"],
        "description": "依据强制性标准原文表格录入，待独立复核。",
        "input_definitions": [], "indicators": [ind],
    }


def build_21252() -> None:
    number = "GB 21252-2023"
    factor_key = "condition.thickness_factor"
    factor_input = input_def(
        factor_key, "厚度总体修正系数", "1", description="按表2以合格品产量占比加权计算；无15 mm及以上产品时填1.00。"
    )
    rows = [
        ("ceramic-tile-abs-le-0.2", "陶瓷砖（干压）/陶瓷瓦（干压），吸水率≤0.2%", "kgce/m²", ["4.5", "5.5", "7.0"], True, "表1、表2", 5),
        ("ceramic-tile-abs-0.2-0.5", "陶瓷砖（干压）/陶瓷瓦（干压），0.2%＜吸水率≤0.5%", "kgce/m²", ["4.0", "4.9", "6.5"], True, "表1、表2", 5),
        ("ceramic-tile-abs-0.5-10", "陶瓷砖（干压）/陶瓷瓦（干压），0.5%＜吸水率≤10%", "kgce/m²", ["3.4", "3.7", "4.6"], True, "表1、表2", 5),
        ("ceramic-tile-abs-gt-10", "陶瓷砖（干压）/陶瓷瓦（干压），吸水率＞10%", "kgce/m²", ["3.2", "3.5", "4.5"], True, "表1、表2", 5),
        ("ceramic-board", "陶瓷板", "kgce/m²", ["6.0", "8.7", "13.2"], True, "表3、表2", 6),
        ("dry-hung-hollow-board-extruded-tile", "干挂空心陶瓷板、陶瓷瓦（挤压）", "kgce/t", ["226", "238", "253"], False, "表4", 6),
        ("sanitary-ware-abs-le-0.3", "卫生陶瓷，吸水率≤0.3%", "kgce/t", ["350", "500", "630"], False, "表5", 6),
        ("sanitary-ware-abs-gt-0.3", "卫生陶瓷，吸水率＞0.3%", "kgce/t", ["300", "460", "610"], False, "表5", 6),
        ("alumina-grinding-ball-90-series", "耐磨氧化铝球（90系列）", "kgce/t", ["295", "320", "370"], False, "表6", 6),
    ]
    products = []
    for ident, name, unit, values, modified, table, page in rows:
        ind = indicator(number, ident, name, unit, values, page=page, table=table,
                        extra_inputs=[factor_input] if modified else None,
                        threshold_multiplier_key=factor_key if modified else None,
                        notes=["original_pdf_transcribed", "thickness_factor_from_table_2" if modified else "original_pdf_transcribed", "requires_independent_review"])
        products.append(one_product(ind, name))
    write_definition(number, products)


def build_21257() -> None:
    number = "GB 21257-2024"
    rows = [
        ("caustic-liquid-30", "液碱（质量分数≥30.0%）", "kgce/t", ["308", "315", "350"], "表1", 6),
        ("caustic-liquid-45", "液碱（质量分数≥45.0%）", "kgce/t", ["410", "420", "470"], "表1", 6),
        ("caustic-solid", "固碱（质量分数≥98.0%）", "kgce/t", ["600", "620", "685"], "表1", 6),
        ("pvc-carbide-general", "电石法聚氯乙烯树脂（通用型）", "kgce/t", ["185", "193", "270"], "表2", 6),
        ("pvc-carbide-paste", "电石法聚氯乙烯树脂（糊用型）", "kgce/t", ["430", "450", "480"], "表2", 6),
        ("pvc-ethylene-general", "乙烯法/联合法/姜钟法聚氯乙烯树脂（通用型）", "kgce/t", ["600", "620", "635"], "表2", 6),
        ("pvc-ethylene-paste", "乙烯法/联合法/姜钟法聚氯乙烯树脂（糊用型）", "kgce/t", ["900", "950", "1100"], "表2", 6),
        ("pvc-monomer-general", "单体法聚氯乙烯树脂（通用型）", "kgce/t", ["150", "175", "210"], "表2", 6),
        ("pvc-monomer-paste", "单体法聚氯乙烯树脂（糊用型）", "kgce/t", ["355", "385", "415"], "表2", 6),
        ("methane-chloride-no-entry", "甲烷氯化物，四氯化碳转化成其他产品不进入生产系统", "kgce/t", ["220", "250", "290"], "表3", 6),
        ("methane-chloride-methyl", "甲烷氯化物，四氯化碳转化成一氯甲烷并进入生产系统", "kgce/t", ["220", "250", "290"], "表3", 6),
        ("methane-chloride-chloroform", "甲烷氯化物，四氯化碳转化成三氯甲烷并进入生产系统", "kgce/t", ["255", "275", "320"], "表3", 6),
    ]
    write_definition(number, [one_product(indicator(number, ident, name, unit, vals, page=page, table=table))
                              for ident, name, unit, vals, table, page in rows])


if __name__ == "__main__":
    build_21252()
    build_21257()
    print("已按GB 21252-2023和GB 21257-2024原文表格重建规则；状态为reviewed，尚未published。")
