from __future__ import annotations

"""Refine five remaining table-driven draft standards.

The source PDFs give one or more named product/process rows and three limits.
This utility replaces the generic extraction with those rows and a common
energy-total / qualified-output formula.  All definitions intentionally stay
``draft``; the confirmation workbook and independent review remain the only
publication gate.
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


# number: (row id, product name, unit, level1/2/3, production-unit)
CONFIG: dict[str, tuple[str, list[tuple[str, str, str, tuple[str, str, str], str]], tuple[int, str, str]]] = {
    "GB 30185-2025": ("kgce/10^4m2", [
        ("decorative-thermal", "铝塑复合板—热压复合装饰板", "kgce/10^4m2", ("2400", "3000", "4400"), "10^4m2"),
        ("decorative-coating-thermal", "铝塑复合板—化成涂装和热压复合", "kgce/10^4m2", ("3500", "5000", "6500"), "10^4m2"),
        ("curtainwall-thermal", "铝塑复合板—幕墙板热压复合", "kgce/10^4m2", ("2700", "3200", "4800"), "10^4m2"),
        ("curtainwall-coating-thermal", "铝塑复合板—幕墙板化成涂装和热压复合", "kgce/10^4m2", ("4400", "5600", "7600"), "10^4m2"),
        ("noncombustible", "不燃铝复合板", "kgce/10^4m2", ("3200", "3900", "5400"), "10^4m2"),
        ("aluminum-panel-powder", "装饰用铝单板—粉末喷涂", "kgce/10^4m2", ("7000", "8500", "10200"), "10^4m2"),
        ("aluminum-panel-liquid", "装饰用铝单板—液体喷涂", "kgce/10^4m2", ("12000", "14000", "17200"), "10^4m2"),
    ], (6, "第4章、表1", "表1")),
    "GB 30530-2024": ("kgce/t", [
        ("dimethylsiloxane", "二甲基硅氧烷（水解物、环体和线性体）", "kgce/t", ("650", "750", "1000"), "t"),
    ], (6, "第4章、表1", "表1")),
    "GB 31830-2024": ("kgce/t", [
        ("tdi", "甲苯二异氰酸酯（TDI）", "kgce/t", ("340", "500", "950"), "t"),
        ("mdi", "二苯基甲烷二异氰酸酯（MDI）", "kgce/t", ("175", "180", "190"), "t"),
    ], (6, "第4章、表1、表2", "表1、表2")),
    "GB 32051-2024": ("kgce/t", [
        ("titanium-dioxide-rutile", "钛白粉—金红石型（硫酸法）", "kgce/t", ("860", "1000", "1300"), "t"),
        ("titanium-dioxide-anatase", "钛白粉—锐钛型（硫酸法）", "kgce/t", ("700", "800", "1000"), "t"),
        ("titanium-dioxide-chloride", "钛白粉—氯化法", "kgce/t", ("700", "900", "950"), "t"),
        ("iron-oxide-red", "氧化铁颜料—氧化铁红", "kgce/t", ("580", "650", "780"), "t"),
        ("iron-oxide-yellow", "氧化铁颜料—氧化铁黄", "kgce/t", ("600", "750", "900"), "t"),
        ("iron-oxide-black", "氧化铁颜料—氧化铁黑", "kgce/t", ("410", "460", "600"), "t"),
    ], (6, "第4章、表1、表2", "表1、表2")),
    "GB 45246-2025": ("kgce/m3", [
        ("medium-density-fiberboard", "中密度纤维板", "kgce/m3", ("118", "130", "180"), "m3"),
        ("high-density-fiberboard", "高密度纤维板", "kgce/m3", ("200", "230", "260"), "m3"),
        ("plywood-full-process", "普通胶合板—全工序", "kgce/m3", ("170", "197", "223"), "m3"),
        ("plywood-front-process", "普通胶合板—前段工序", "kgce/m3", ("110", "130", "150"), "m3"),
        ("plywood-back-process", "普通胶合板—后段工序", "kgce/m3", ("60", "67", "73"), "m3"),
        ("particleboard", "普通型刨花板", "kgce/m3", ("100", "110", "150"), "m3"),
    ], (5, "第4章、表1", "表1")),
}


def refine_one(data_dir: Path, number: str) -> Path:
    unit, rows, (page, clause, table) = CONFIG[number]
    path = next(data_dir.joinpath("definitions").glob("*.json"), None)
    for candidate in data_dir.joinpath("definitions").glob("*.json"):
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        if payload.get("number") == number:
            path = candidate
            original = payload
            break
    if path is None or "original" not in locals():
        raise FileNotFoundError(f"未找到标准规则：{number}")
    if len(original.get("products", [])) != len(rows):
        raise ValueError(f"{number} 原规则产品行数不是{len(rows)}，拒绝静默覆盖")
    source_file, source_sha = original["source_file"], original["source_sha256"]
    references = [{"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                  "page": page, "clause": clause, "table": table,
                  "note": "产品/工序名称与三级限额按现行强制文本表格逐行转录。"},
                 {"standard_number": number, "source_file": source_file, "source_sha256": source_sha,
                  "page": page + 1, "clause": "第6章计算方法", "table": "公式",
                  "note": "明细模式暂按统计期综合能耗除以合格产量；生产边界和特殊修正仍需独立复核。"}]
    products: list[dict] = []
    for product_id, name, row_unit, levels, production_unit in rows:
        actual_key = f"actual.{number.replace(' ', '_')}.{product_id}.energy"
        indicator = {"id": f"{number.replace(' ', '_')}.{product_id}.comprehensive-energy",
                     "name": f"{name}单位产品综合能耗", "unit": row_unit, "comparison": "lte",
                     "input_definitions": [{"key": actual_key, "label": f"{name}单位产品能耗实际值",
                                             "data_type": "decimal", "unit": row_unit, "required": True,
                                             "required_if": None, "modes": ["DIRECT"], "minimum": "0",
                                             "maximum": None, "choices": [],
                                             "description": f"直接录入按{number}第6章核算的单位产品能耗。"}],
                     "applicability": {"op": "always"}, "direct_input_key": actual_key,
                     "detail_formula": node("per_unit", args=[
                         node("input", input_key="energy.total_standard_coal", unit="kgce", label="统计期综合能耗"),
                         node("input", input_key="production.total_equivalent", unit=production_unit, label=f"{name}合格产量"),
                     ], unit=row_unit, label=f"{name}单位产品综合能耗（第6章公式）"),
                     "base_thresholds": {f"level_{i}": node("constant", value=value, unit=row_unit)
                                         for i, value in enumerate(levels, 1)},
                     "thresholds": {f"level_{i}": node("constant", value=value, unit=row_unit)
                                    for i, value in enumerate(levels, 1)},
                     "display_places": 2, "source_references": references,
                     "notes": ["candidate_from_original_pdf", "not_for_formal_evaluation",
                               "requires_independent_review", "table_rows_transcribed_from_current_mandatory_text",
                               "special_process_boundary_or_product_conversion_requires_clause_review"]}
        products.append({"id": product_id, "name": name,
                         "description": f"{number}表格中的{name}产品/工序行。",
                         "input_definitions": [], "indicators": [indicator]})
    original["products"] = products
    original["publication_status"] = "draft"
    StandardDefinition.model_validate(original)
    path.write_text(json.dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化表格型草案标准（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-65/data"))
    parser.add_argument("--standard", choices=sorted(CONFIG), action="append")
    args = parser.parse_args()
    for number in args.standard or sorted(CONFIG):
        print(f"已精化 {number} 草案规则：{refine_one(args.data_dir.resolve(), number)}")


if __name__ == "__main__":
    main()
