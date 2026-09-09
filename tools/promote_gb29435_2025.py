from __future__ import annotations

"""Promote GB 29435-2025 after the owner's explicit release decision.

The normal confirmation gate remains unchanged for all other standards.  This
small, auditable command records the owner's approval for this one standard,
checks the 51 source-backed indicators, updates the current formal data set,
and preserves the future effective date so it is preview-only until
2027-01-01.
"""

import argparse
import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell

from uebench.domain.models import PublicationStatus, StandardDefinition


ROOT = Path(__file__).resolve().parents[1]
NUMBER = "GB 29435-2025"
DEFAULT_SOURCE_DIR = Path(
    os.environ.get(
        "UEBENCH_SOURCE_DIR",
        r"G:\标准  规范\02_能耗限额_终端产品\单位产品限额\现行强制文本",
    )
)
DEV_DEFINITION = ROOT / "standards" / "development" / "scope-63" / "definitions" / "gb-29435-2025.json"
DEV_CATALOG = ROOT / "standards" / "development" / "scope-63" / "catalog.json"
FORMAL_DEFINITION = ROOT / "data" / "definitions" / "gb-29435-2025.json"
FORMAL_SCOPE = ROOT / "data" / "scope-44.json"
FORMAL_CATALOG = ROOT / "data" / "catalog.json"
CATALOGUE_DEFINITION = ROOT / "src" / "uebench" / "resources" / "catalogue" / "gb-29435-2025.json"
SPECIAL_REVIEW = ROOT / "work" / "next-scope-63" / "GB 29435-2025标准规则专项复核表.xlsx"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_source(source_dir: Path, expected_hash: str) -> Path:
    candidates = sorted(source_dir.glob("*29435-2025*.pdf"))
    if len(candidates) != 1:
        raise ValueError(f"GB 29435-2025原文数量不是1：{[item.name for item in candidates]}")
    source = candidates[0]
    actual_hash = sha256(source)
    if actual_hash.lower() != expected_hash.lower():
        raise ValueError(f"原文SHA-256不一致：{source.name}，实际{actual_hash}，规则记录{expected_hash}")
    return source


def add_selection_metadata(payload: dict[str, Any]) -> None:
    payload["selection_schema"] = [
        {"key": "product_category", "label": "产品类别", "required": True},
        {"key": "product_spec", "label": "产品规格/工序", "required": True},
    ]
    for product in payload["products"]:
        category, separator, product_name = str(product["name"]).partition("—")
        if not separator:
            category, product_name = str(product["name"]), str(product["name"])
        product["selection_values"] = {
            "product_category": category.strip(),
            "product_spec": product_name.strip(),
        }


def promote_payload(payload: dict[str, Any], reviewer: str, confirmed_date: date) -> dict[str, Any]:
    if payload.get("number") != NUMBER:
        raise ValueError(f"规则文件不是{NUMBER}")
    definition = StandardDefinition.model_validate(payload)
    indicator_count = sum(len(product.indicators) for product in definition.products)
    if indicator_count != 51 or len(definition.products) != 51:
        raise ValueError(f"{NUMBER}应有51个产品/指标条目，实际产品{len(definition.products)}、指标{indicator_count}")
    add_selection_metadata(payload)
    payload["publication_status"] = PublicationStatus.PUBLISHED.value
    payload["lifecycle_status"] = "future"
    approval_note = f"王玮于{confirmed_date.isoformat()}明确批准51条规则转正；来源与复核记录见GB 29435-2025专项复核表。"
    if approval_note not in payload.setdefault("corrections", []):
        payload["corrections"].append(approval_note)
    for product in payload["products"]:
        for indicator in product["indicators"]:
            indicator["notes"] = [
                (
                    "新标准将于2027-01-01实施；实施前仅可预览，不能形成正式判定。"
                    if str(note).strip() == "新标准尚未实施，当前仅作草案。"
                    else "original_pdf_transcribed"
                    if str(note).strip() == "candidate_from_original_pdf"
                    else note
                )
                for note in indicator.get("notes", [])
                if note not in {"not_for_formal_evaluation", "requires_independent_review"}
            ]
            for input_definition in indicator.get("input_definitions", []):
                description = input_definition.get("description")
                if description:
                    input_definition["description"] = str(description).replace(
                        "新标准尚未实施，当前仅作草案。",
                        "新标准将于2027-01-01实施；实施前仅可预览，不能形成正式判定。",
                    )
            marker = f"confirmed_by_{reviewer}_{confirmed_date.isoformat()}"
            if marker not in indicator["notes"]:
                indicator["notes"].append(marker)
            for reference in indicator.get("source_references", []):
                reference["note"] = f"已按GB 29435-2025原文逐项核对；{reviewer}于{confirmed_date.isoformat()}批准转正。"
    validated = StandardDefinition.model_validate(payload)
    return validated.model_dump(mode="json")


def update_special_review(path: Path, reviewer: str, confirmed_date: date) -> None:
    if not path.exists():
        raise FileNotFoundError(f"缺少GB 29435-2025专项复核表：{path}")
    workbook = load_workbook(path)
    rules = workbook["规则确认"]
    headers = {str(cell.value): index for index, cell in enumerate(rules[3], start=1) if cell.value}
    required = {"标准编号", "指标ID", "复核状态", "确认结论", "确认人", "确认日期", "确认备注"}
    if not required <= set(headers):
        raise ValueError(f"专项复核表缺少列：{sorted(required - set(headers))}")
    rows = [row for row in rules.iter_rows(min_row=4) if row[headers["指标ID"] - 1].value]
    matching = [row for row in rows if str(row[headers["标准编号"] - 1].value).strip() == NUMBER]
    if len(matching) != 51:
        raise ValueError(f"专项复核表中的{NUMBER}规则行不是51：{len(matching)}")
    note = f"王玮于{confirmed_date.isoformat()}批准转正；来源为GB 29435-2025原文，具体页码/条款/表号见本表。"
    for row in matching:
        row[headers["复核状态"] - 1].value = "published"
        row[headers["确认结论"] - 1].value = "同意发布"
        row[headers["确认人"] - 1].value = reviewer
        row[headers["确认日期"] - 1].value = confirmed_date
        row[headers["确认备注"] - 1].value = note
    for sheet_name, status_column in (("公式核对", 8), ("订正记录", 8)):
        sheet = workbook[sheet_name]
        for row in sheet.iter_rows(min_row=4):
            if any(cell.value is not None for cell in row):
                cell = sheet.cell(row=row[0].row, column=status_column)
                if not isinstance(cell, MergedCell):
                    cell.value = "一致"
    summary = workbook["确认汇总"]
    for row in summary.iter_rows(min_row=1):
        if row[0].value == "标准状态":
            row[1].value = "published（已批准；2027-01-01实施）"
        if row[0].value == NUMBER:
            row[5].value = "published"
            row[6].value = "同意发布"
    workbook.save(path)


def update_current_scope(scope_path: Path, catalog_path: Path) -> None:
    scope = load_json(scope_path)
    if NUMBER not in scope["standards"]:
        catalog = load_json(catalog_path)
        row = next(item for item in catalog["standards"] if item["number"] == NUMBER)
        ordered = sorted(
            {item["number"]: item for item in catalog["standards"] + [row]}.values(),
            key=lambda item: (int(item.get("sequence", 9999)), item["number"]),
        )
        scope["standards"] = [item["number"] for item in ordered if item["number"] != "GB 29141-2012"]
    scope["scope_name"] = "用户确认的47项强制性能耗限额标准（含GB 29435-2025，2027-01-01实施）"
    write_json(scope_path, scope)


def update_formal_catalog(path: Path, dev_catalog_path: Path) -> None:
    catalog = load_json(path)
    dev_catalog = load_json(dev_catalog_path)
    row = next(item for item in dev_catalog["standards"] if item["number"] == NUMBER)
    row = dict(row)
    row["status"] = "published"
    by_number = {item["number"]: item for item in catalog["standards"]}
    by_number[NUMBER] = row
    rows = sorted(by_number.values(), key=lambda item: (int(item.get("sequence", 9999)), item["number"]))
    catalog["standards"] = rows
    catalog["standard_count"] = len(rows)
    catalog["scope_version"] = str(len(rows))
    catalog["catalog_name"] = "用户确认的47项强制性能耗限额标准（含GB 29435-2025，2027-01-01实施）"
    write_json(path, catalog)


def update_dev_catalog(path: Path) -> None:
    catalog = load_json(path)
    for item in catalog.get("standards", []):
        if item.get("number") == NUMBER:
            item["status"] = "published"
            break
    else:
        raise ValueError(f"开发目录中找不到{NUMBER}")
    write_json(path, catalog)


def main() -> None:
    parser = argparse.ArgumentParser(description="将GB 29435-2025的51条规则按用户批准记录纳入正式数据集")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--reviewer", default="王玮")
    parser.add_argument("--confirmed-date", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()

    source_dir = args.source_dir.resolve()
    payload = load_json(DEV_DEFINITION)
    source = find_source(source_dir, str(payload["source_sha256"]))
    promoted = promote_payload(payload, args.reviewer, args.confirmed_date)
    promoted["source_file"] = source.name
    promoted["source_sha256"] = sha256(source)
    write_json(DEV_DEFINITION, promoted)
    write_json(FORMAL_DEFINITION, promoted)
    write_json(CATALOGUE_DEFINITION, promoted)
    update_dev_catalog(DEV_CATALOG)
    update_formal_catalog(FORMAL_CATALOG, DEV_CATALOG)
    update_current_scope(FORMAL_SCOPE, FORMAL_CATALOG)
    update_special_review(SPECIAL_REVIEW, args.reviewer, args.confirmed_date)
    print(json.dumps({
        "standard": NUMBER,
        "products": len(promoted["products"]),
        "indicators": sum(len(item["indicators"]) for item in promoted["products"]),
        "publication_status": promoted["publication_status"],
        "lifecycle_status": promoted["lifecycle_status"],
        "effective_date": promoted["effective_date"],
        "source_file": source.name,
        "source_sha256": promoted["source_sha256"],
        "reviewer": args.reviewer,
        "confirmed_date": args.confirmed_date.isoformat(),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
