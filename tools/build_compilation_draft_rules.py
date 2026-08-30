from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from uebench.domain.models import StandardDefinition


NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
UNIT = re.compile(r"(kgce\s*/\s*(?:t|m³|m3|㎡|平方米|吨)|kW[·.]?h\s*/\s*(?:t|㎡|m³|m3)|tce\s*/\s*t)", re.I)


def slug(text: str) -> str:
    text = re.sub(r"[^0-9A-Za-z一-龥]+", "_", text).strip("_")
    return text[:80] or "item"


def unit_for(lines: list[str]) -> str:
    match = UNIT.search(" ".join(lines))
    if not match:
        return "kgce/t"
    value = re.sub(r"\s+", "", match.group(1))
    return {"kgce/吨": "kgce/t", "kgce/平方米": "kgce/m²", "kgce/㎡": "kgce/m²", "kW.h/t": "kWh/t"}.get(value, value)


def labels(lines: list[str]) -> tuple[str, str]:
    cleaned = []
    for line in lines:
        line = re.sub(r"\s+", "", line)
        if not line or line.startswith(("《", "（GB", "GB ", "标准名称", "标杆水平", "限额标准")):
            continue
        if re.fullmatch(r"[A-Z]?\d{2,5}", line):
            continue
        cleaned.append(line)
    joined = "".join(cleaned)
    metric_tokens = ("单位产品", "单位能耗", "电力单耗", "综合能耗", "产品能耗", "能源消耗")
    split_at = min((joined.find(token) for token in metric_tokens if joined.find(token) >= 0), default=-1)
    if split_at > 0:
        product = joined[:split_at].strip(" ：:")
        indicator = joined[split_at:].strip()
    else:
        product = joined[:80] or "标准产品/工序"
        indicator = "单位产品能源消耗"
    if not product:
        product = "标准产品/工序"
    return product, indicator


def constant(value: str, unit: str) -> dict[str, object]:
    return {"op": "constant", "value": value, "input_key": None, "args": [], "cases": [], "rows": [], "default": None, "label": None, "unit": unit, "round_places": None}


def build_indicator(number: str, row: dict[str, object], source_file: str, source_sha256: str, index: int) -> dict[str, object]:
    numbers = [str(value) for value in row["numbers"]]
    thresholds = numbers[:3]
    product_name, indicator_name = labels(list(row.get("label_lines", [])))
    unit = unit_for(list(row.get("label_lines", [])))
    base = f"{slug(product_name)}_{index}"
    input_key = f"actual.{slug(number)}.{index}"
    return {
        "id": f"{slug(number)}.candidate_{index}",
        "name": indicator_name,
        "unit": unit,
        "comparison": "lte",
        "input_definitions": [{"key": input_key, "label": f"{product_name}{indicator_name}实际值", "data_type": "decimal", "unit": unit, "required": True, "required_if": None, "modes": ["DIRECT"], "minimum": None, "maximum": None, "choices": [], "description": "汇编候选值，待按标准原文复核。"}],
        "applicability": {"op": "always", "field": None, "value": None, "values": [], "minimum": None, "maximum": None, "include_minimum": True, "include_maximum": True, "args": []},
        "direct_input_key": input_key,
        "detail_formula": None,
        "base_thresholds": {"level_1": constant(thresholds[0], unit), "level_2": constant(thresholds[1], unit), "level_3": constant(thresholds[2], unit)},
        "thresholds": {"level_1": constant(thresholds[0], unit), "level_2": constant(thresholds[1], unit), "level_3": constant(thresholds[2], unit)},
        "display_places": 2,
        "source_references": [{"standard_number": number, "source_file": source_file, "source_sha256": source_sha256, "page": max(1, int(row.get("page") or 1)), "clause": "第4章 能耗限额等级", "table": None, "note": "汇编候选数据，必须回到标准原文复核后才能发布。"}],
        "notes": ["candidate_from_compilation", "not_for_formal_evaluation"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="从汇编候选生成draft规则；不会生成published规则")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--candidates", type=Path, default=Path("work/verification/compilation-candidates.json"))
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    candidates = json.loads(args.candidates.resolve().read_text(encoding="utf-8"))["rows"]
    catalog = json.loads((data_dir / "catalog.json").read_text(encoding="utf-8"))["standards"]
    by_number = {item["number"]: item for item in catalog}
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in candidates:
        grouped.setdefault(str(row["standard_number"]), []).append(row)
    generated = 0
    for number, rows in grouped.items():
        if number not in by_number:
            continue
        path = data_dir / "definitions" / f"{re.sub(r'[^a-z0-9]+', '-', number.lower()).strip('-')}.json"
        definition = json.loads(path.read_text(encoding="utf-8"))
        if definition.get("publication_status") != "draft" or definition.get("products"):
            continue
        indicators = [build_indicator(number, row, by_number[number]["source_file"], by_number[number]["source_sha256"], i + 1) for i, row in enumerate(rows)]
        products = []
        for i, indicator in enumerate(indicators, start=1):
            label = indicator["input_definitions"][0]["label"].replace("实际值", "")
            products.append({"id": f"candidate_{i}", "name": label, "description": "汇编候选，待标准原文复核。", "input_definitions": [], "indicators": [indicator]})
        definition["products"] = products
        definition["publication_status"] = "draft"
        path.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        generated += len(indicators)
    print(f"已生成 {generated} 个draft候选指标，未改变任何规则为published。")


if __name__ == "__main__":
    main()
