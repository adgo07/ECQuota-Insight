from __future__ import annotations

"""Create explicitly non-published draft rules from original-PDF table candidates.

This tool is deliberately conservative: it only fills definitions that are empty,
keeps publication_status=draft, and annotates every generated indicator with the
original PDF page/table candidate and a mandatory manual-review note.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

from uebench.domain.models import StandardDefinition


TARGETS = {
    "GB 29445-2025": "kgce/t",
    "GB 29995-2024": "kgce/t",
    "GB 31825-2024": "kgce/Adt",
    "GB 32047-2025": "kgce/kL",
    "GB 36889-2025": "kgce/t",
    "GB 46029-2025": "kgce/t",
}


def slug(text: str) -> str:
    value = re.sub(r"[^0-9A-Za-z一-龥]+", "_", text).strip("_")
    return value[:70] or "item"


def node(op: str, *, value: str | None = None, input_key: str | None = None,
         args: list[dict] | None = None, unit: str | None = None,
         label: str | None = None) -> dict:
    return {"op": op, "value": value, "input_key": input_key, "args": args or [],
            "cases": [], "rows": [], "default": None, "label": label,
            "unit": unit, "round_places": None}


def constant(value: str, unit: str) -> dict:
    return node("constant", value=str(value), unit=unit)


def indicator(number: str, row: dict, source_file: str, sha256: str, index: int,
              unit: str) -> dict:
    product_label = str(row.get("row_prefix") or "标准产品/工序候选").strip()
    # Keep duplicate labels distinguishable until a reviewer maps them to the
    # exact product/condition row in the source table.
    name = f"{product_label}（原文候选#{index}）"
    key = f"actual.{slug(number)}.original_{index}"
    values = [str(v) for v in row.get("numbers", [])][:3]
    if len(values) != 3:
        raise ValueError(f"candidate {number} #{index} does not have 3 thresholds")
    return {
        "id": f"{slug(number)}.original_candidate_{index}",
        "name": name,
        "unit": unit,
        "comparison": "lte",
        "input_definitions": [{
            "key": key, "label": f"{name}实际值", "data_type": "decimal", "unit": unit,
            "required": True, "required_if": None, "modes": ["DIRECT"],
            "minimum": "0", "maximum": None, "choices": [],
            "description": "原文表格候选值；完成页码、条款、产品条件和计算边界复核前不得用于正式评价。",
        }],
        "applicability": {"op": "always"},
        "direct_input_key": key,
        "detail_formula": node("per_unit", args=[
            node("input", input_key="energy.total_standard_coal"),
            node("input", input_key="production.total_equivalent"),
        ], unit=unit, label="单位产品实际能耗（通用候选公式，待原文复核）"),
        "base_thresholds": {f"level_{i}": constant(values[i - 1], unit) for i in (1, 2, 3)},
        "thresholds": {f"level_{i}": constant(values[i - 1], unit) for i in (1, 2, 3)},
        "display_places": 2,
        "source_references": [{
            "standard_number": number, "source_file": source_file, "source_sha256": sha256,
            "page": max(1, int(row.get("page") or 1)),
            "clause": "第4章/附录表格（候选，待复核）",
            "table": None,
            "note": "原文PDF自动提取候选；必须人工对照原文产品、适用条件、单位、表号和公式后才能发布。",
        }],
        "notes": ["candidate_from_original_pdf", "not_for_formal_evaluation", "requires_independent_review"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--candidates", type=Path, default=Path("work/verification/table-candidates-pages.json"))
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    candidates = json.loads(args.candidates.resolve().read_text(encoding="utf-8"))
    catalog = {row["number"]: row for row in json.loads((data_dir / "catalog.json").read_text(encoding="utf-8"))["standards"]}
    generated = 0
    for number, unit in TARGETS.items():
        if number not in catalog:
            continue
        stem = catalog[number]["source_file"].rsplit(".", 1)[0]
        rows = list(candidates.get(stem, []))
        if not rows:
            continue
        path = data_dir / "definitions" / f"{re.sub(r'[^a-z0-9]+', '-', number.lower()).strip('-')}.json"
        definition = json.loads(path.read_text(encoding="utf-8"))
        if definition.get("publication_status") != "draft" or definition.get("products"):
            continue
        indicators = [indicator(number, row, catalog[number]["source_file"], catalog[number]["source_sha256"], i, unit)
                      for i, row in enumerate(rows, 1)]
        definition["products"] = [{
            "id": f"original-candidate-{i}",
            "name": item["name"],
            "description": "原文PDF自动提取候选，待标准规则确认表逐项复核。",
            "input_definitions": [],
            "indicators": [item],
        } for i, item in enumerate(indicators, 1)]
        definition["publication_status"] = "draft"
        path.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        generated += len(indicators)
        print(f"{number}: {len(indicators)}")
    # Validate every changed definition against the same Pydantic contract used
    # by the application before reporting success.
    for number in TARGETS:
        path = data_dir / "definitions" / f"{re.sub(r'[^a-z0-9]+', '-', number.lower()).strip('-')}.json"
        if path.exists():
            StandardDefinition.model_validate(json.loads(path.read_text(encoding="utf-8")))
    print(f"已从原文PDF生成 {generated} 个draft候选指标；没有任何规则被标为published。")


if __name__ == "__main__":
    main()
