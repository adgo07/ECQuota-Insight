from __future__ import annotations

"""Build and validate one unified development-library index.

The index makes scope-63 the only current development entry point while
keeping superseded definitions in scope-63/retired-definitions.  scope-65 is
listed only as a comparison snapshot and is never merged into the current
library.
"""

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT_ROOT = ROOT / "standards" / "development"
DEFAULT_SCOPE = DEVELOPMENT_ROOT / "scope-63"
DEFAULT_OUTPUT = DEVELOPMENT_ROOT / "library-index.json"


class DevelopmentLibraryError(ValueError):
    """The development snapshots cannot be represented as one unique library."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DevelopmentLibraryError(f"无法读取JSON：{path}") from exc
    if not isinstance(value, dict):
        raise DevelopmentLibraryError(f"JSON根节点必须是对象：{path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _entry(path: Path, scope: str) -> tuple[dict[str, Any], tuple[str, str, int]]:
    payload = _read_json(path)
    number = str(payload.get("number", "")).strip()
    standard_id = str(payload.get("id", "")).strip()
    version = str(payload.get("version", "")).strip()
    family_id = str(payload.get("standard_family_id", "")).strip()
    if not number or not standard_id or not version or not family_id:
        raise DevelopmentLibraryError(f"标准定义身份字段不完整：{path}")
    try:
        revision = int(payload.get("rule_revision"))
    except (TypeError, ValueError) as exc:
        raise DevelopmentLibraryError(f"规则修订号不是整数：{path}") from exc
    if revision < 1:
        raise DevelopmentLibraryError(f"规则修订号必须大于等于1：{path}")
    try:
        relative = path.resolve().relative_to(DEVELOPMENT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise DevelopmentLibraryError(f"定义文件不在开发库目录内：{path}") from exc
    item = {
        "number": number,
        "id": standard_id,
        "title": str(payload.get("title", "")).strip(),
        "version": version,
        "standard_family_id": family_id,
        "rule_revision": revision,
        "publication_status": str(payload.get("publication_status", "")).strip(),
        "lifecycle_status": str(payload.get("lifecycle_status") or ("obsolete" if scope == "retired" else "active")).strip(),
        "scope": scope,
        "definition_path": relative,
        "definition_sha256": _sha256(path),
    }
    if not item["title"] or not item["publication_status"] or not item["lifecycle_status"]:
        raise DevelopmentLibraryError(f"标准定义展示/状态字段不完整：{path}")
    return item, (standard_id, version, revision)


def build_manifest(scope_root: Path, *, generated_at: str | None = None) -> dict[str, Any]:
    scope_root = scope_root.resolve()
    if scope_root.name != "scope-63":
        raise DevelopmentLibraryError(f"统一开发库当前入口必须是scope-63：{scope_root}")
    scope_path = scope_root / "scope-63.json"
    if not scope_path.exists():
        raise DevelopmentLibraryError(f"找不到当前范围清单：{scope_path}")
    scope_payload = _read_json(scope_path)
    numbers = [str(item).strip() for item in scope_payload.get("standards", []) if str(item).strip()]
    if not numbers or len(numbers) != len(set(numbers)):
        raise DevelopmentLibraryError("scope-63范围清单为空或存在重复标准编号")

    current_paths = sorted((scope_root / "definitions").glob("*.json"))
    retired_paths = sorted((scope_root / "retired-definitions").glob("*.json"))
    if len(current_paths) != len(numbers):
        raise DevelopmentLibraryError(
            f"scope-63定义数量为{len(current_paths)}，范围清单为{len(numbers)}"
        )

    current_by_number: dict[str, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    keys: set[tuple[str, str, int]] = set()
    for path in current_paths:
        item, key = _entry(path, "current")
        if item["number"] in current_by_number:
            raise DevelopmentLibraryError(f"当前开发库存在重复标准编号：{item['number']}")
        if key in keys:
            raise DevelopmentLibraryError(f"开发库存在重复标准版本：{key}")
        current_by_number[item["number"]] = item
        keys.add(key)
    missing = sorted(set(numbers) - set(current_by_number))
    extra = sorted(set(current_by_number) - set(numbers))
    if missing or extra:
        raise DevelopmentLibraryError(f"当前定义与scope-63不一致：缺少={missing}，多出={extra}")
    entries.extend(current_by_number[number] for number in numbers)

    retired_numbers: set[str] = set()
    for path in retired_paths:
        item, key = _entry(path, "retired")
        if item["number"] in current_by_number or item["number"] in retired_numbers:
            raise DevelopmentLibraryError(f"开发库存在重复归档标准：{item['number']}")
        if key in keys:
            raise DevelopmentLibraryError(f"开发库存在重复归档标准版本：{key}")
        retired_numbers.add(item["number"])
        keys.add(key)
        entries.append(item)

    return {
        "schema_version": "1.0",
        "library_id": "uebench-development",
        "generated_at": generated_at or date.today().isoformat(),
        "canonical_scope": "scope-63",
        "canonical_scope_file": "scope-63/scope-63.json",
        "canonical_catalog_file": "scope-63/catalog.json",
        "comparison_snapshots": ["scope-65"],
        "current_standard_count": len(numbers),
        "retired_standard_count": len(retired_numbers),
        "standard_count": len(entries),
        "standards": entries,
    }


def validate_manifest(path: Path) -> dict[str, Any]:
    path = path.resolve()
    actual = _read_json(path)
    expected = build_manifest(DEVELOPMENT_ROOT / "scope-63", generated_at=str(actual.get("generated_at", "")))
    valid = actual == expected
    return {
        "path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
        "valid": valid,
        "current_standard_count": expected["current_standard_count"],
        "retired_standard_count": expected["retired_standard_count"],
        "standard_count": expected["standard_count"],
        "reason": "" if valid else "manifest与scope-63定义或归档文件不一致",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成或校验统一开发标准库索引")
    parser.add_argument("--scope", type=Path, default=DEFAULT_SCOPE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="只校验，不写入索引")
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        if args.check:
            report = validate_manifest(output)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["valid"] else 1
        existing_generated_at = ""
        if output.exists():
            existing_generated_at = str(_read_json(output).get("generated_at", ""))
        payload = build_manifest(args.scope, generated_at=existing_generated_at or None)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({
            "path": output.relative_to(ROOT).as_posix() if output.is_relative_to(ROOT) else str(output),
            "valid": True,
            "current_standard_count": payload["current_standard_count"],
            "retired_standard_count": payload["retired_standard_count"],
            "standard_count": payload["standard_count"],
        }, ensure_ascii=False, indent=2))
        return 0
    except (OSError, DevelopmentLibraryError) as exc:
        print(f"统一开发库索引失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())