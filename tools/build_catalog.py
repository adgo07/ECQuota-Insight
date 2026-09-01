from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


CATALOG_CORRECTIONS: dict[str, dict[str, Any]] = {
    "GB 21342-2025": {
        "remark": "代替GB 21342-2015",
        "reason": "目录备注误写为代替同版本；按标准原文封面订正。",
        "source": "GB 21342-2025 原文封面",
    },
    "GB 29436-2023": {
        "title": "甲醇、乙二醇和二甲醚单位产品能源消耗限额",
        "reason": "目录标准名称遗漏“醇”字；按标准原文标题订正。",
        "source": "GB 29436-2023 原文封面",
    },
    "GB 30526-2019": {
        "publication_date": "2019-10-14",
        "effective_date": "2020-05-01",
        "reason": "目录发布日期和实施日期均误录为2021-10-11；按标准原文封面订正。",
        "source": "GB 30526-2019 原文封面",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    parts = [part for part in re.split(r"[^0-9]+", text) if part]
    if len(parts) == 3:
        year, month, day = (int(part) for part in parts)
        return date(year, month, day)
    if len(parts) == 2 and len(parts[0]) == 4 and len(parts[1]) == 4:
        return date(int(parts[0]), int(parts[1][:2]), int(parts[1][2:]))
    digits = "".join(parts)
    if len(digits) == 8:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
    raise ValueError(f"无法识别日期：{value!r}")


def standard_id(number: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", number.lower()).strip("-")


def standard_family_id(number: str) -> str:
    """Return the stable family key shared by editions of one standard."""
    return number.rsplit("-", 1)[0].strip()


def standard_version(number: str) -> str:
    """Return the edition year recorded in a GB standard number."""
    return number.rsplit("-", 1)[-1].strip()


def find_pdf(source_dir: Path, sequence: int) -> Path:
    prefix_pattern = re.compile(rf"^0*{sequence}(?:\.|\s)")
    matches = [path for path in source_dir.glob("*.pdf") if prefix_pattern.match(path.name)]
    if len(matches) != 1:
        raise ValueError(f"序号 {sequence} 对应PDF数量不是1：{[path.name for path in matches]}")
    return matches[0]


def build(catalog_path: Path, source_dir: Path, output_dir: Path, scope_path: Path | None = None) -> None:
    scope_numbers: set[str] | None = None
    scope_name = "现有强制性能耗限额标准目录（2025年9月初）"
    if scope_path is not None:
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
        scope_numbers = set(scope["standards"])
        scope_name = str(scope.get("scope_name", scope_name))
    workbook = load_workbook(catalog_path, read_only=True, data_only=True)
    sheet = workbook.active
    catalog_rows: list[dict[str, Any]] = []
    definitions_dir = output_dir / "definitions"
    corrections_dir = output_dir / "corrections"
    definitions_dir.mkdir(parents=True, exist_ok=True)
    corrections_dir.mkdir(parents=True, exist_ok=True)
    correction_records: list[dict[str, Any]] = []

    for values in sheet.iter_rows(min_row=4, values_only=True):
        sequence, number, title, publication_raw, effective_raw, remark = values[:6]
        if sequence is None:
            continue
        sequence = int(sequence)
        number = str(number).strip()
        if scope_numbers is not None and number not in scope_numbers:
            continue
        title = str(title).strip()
        publication = parse_date(publication_raw)
        effective = parse_date(effective_raw)
        remark_text = "" if remark is None else re.sub(r"\s+", "", str(remark))
        pdf_path = find_pdf(source_dir, sequence)
        correction = CATALOG_CORRECTIONS.get(number)
        applied: list[str] = []
        if correction:
            originals = {
                "title": title,
                "publication_date": publication.isoformat(),
                "effective_date": effective.isoformat(),
                "remark": remark_text,
            }
            if "title" in correction:
                title = correction["title"]
                applied.append("title")
            if "publication_date" in correction:
                publication = date.fromisoformat(correction["publication_date"])
                applied.append("publication_date")
            if "effective_date" in correction:
                effective = date.fromisoformat(correction["effective_date"])
                applied.append("effective_date")
            if "remark" in correction:
                remark_text = correction["remark"]
                applied.append("remark")
            correction_records.append(
                {
                    "id": f"CAT-{sequence:03d}",
                    "standard_number": number,
                    "fields": applied,
                    "original": {field: originals[field] for field in applied},
                    "corrected": {
                        "title": title,
                        "publication_date": publication.isoformat(),
                        "effective_date": effective.isoformat(),
                        "remark": remark_text,
                    },
                    "reason": correction["reason"],
                    "source": correction["source"],
                }
            )
        digest = sha256(pdf_path)
        sid = standard_id(number)
        family_id = standard_family_id(number)
        version = standard_version(number)
        item = {
            "sequence": sequence,
            "id": sid,
            "number": number,
            "title": title,
            "version": version,
            "standard_family_id": family_id,
            "rule_revision": 1,
            "publication_date": publication.isoformat(),
            "effective_date": effective.isoformat(),
            "remark": remark_text,
            "source_file": pdf_path.name,
            "source_sha256": digest,
            "status": "draft",
        }
        catalog_rows.append(item)
        definition = {
            "schema_version": "1.0",
            "id": sid,
            "number": number,
            "title": title,
            "version": version,
            "standard_family_id": family_id,
            "rule_revision": 1,
            "publication_status": "draft",
            "publication_date": publication.isoformat(),
            "effective_date": effective.isoformat(),
            "source_file": pdf_path.name,
            "source_sha256": digest,
            "products": [],
            "corrections": [record["id"] for record in correction_records if record["standard_number"] == number],
        }
        (definitions_dir / f"{sid}.json").write_text(
            json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    expected_count = len(scope_numbers) if scope_numbers is not None else 63
    if len(catalog_rows) != expected_count:
        raise ValueError(f"目录应包含{expected_count}项标准，实际为{len(catalog_rows)}项")
    payload = {
        "schema_version": "1.0",
        "catalog_name": scope_name,
        "catalog_sha256": sha256(catalog_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "standard_count": len(catalog_rows),
        "scope_version": str(expected_count),
        "standards": catalog_rows,
    }
    (output_dir / "catalog.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (corrections_dir / "catalog-corrections.json").write_text(
        json.dumps({"schema_version": "1.0", "corrections": correction_records}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"已生成 {len(catalog_rows)} 项目录定义，订正 {len(correction_records)} 项。")


def main() -> None:
    parser = argparse.ArgumentParser(description="从权威目录和现行强制文本建立标准元数据")
    parser.add_argument("catalog", type=Path)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--scope", type=Path, help="可选范围 JSON；本项目当前范围为46项")
    args = parser.parse_args()
    build(args.catalog.resolve(), args.source_dir.resolve(), args.output_dir.resolve(), args.scope.resolve() if args.scope else None)


if __name__ == "__main__":
    main()
