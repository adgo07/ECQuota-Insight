from __future__ import annotations

"""Build and validate an index of the single editable definition source.

``data/definitions`` is current. Both scope-63 and scope-65 remain immutable
historical test snapshots and are never publication inputs.
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
DEFAULT_SCOPE = ROOT / "data" / "definitions"
DEFAULT_OUTPUT = DEVELOPMENT_ROOT / "library-index.json"
DELIVERY_SCOPE = ROOT / "data" / "delivery-scope.json"


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
        relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise DevelopmentLibraryError(f"定义文件不在仓库目录内：{path}") from exc
    item = {
        "number": number,
        "id": standard_id,
        "title": str(payload.get("title", "")).strip(),
        "version": version,
        "standard_family_id": family_id,
        "rule_revision": revision,
        "publication_status": str(payload.get("publication_status", "")).strip(),
        "lifecycle_status": str(payload.get("lifecycle_status") or "active").strip(),
        "scope": scope,
        "definition_path": relative,
        "definition_sha256": _sha256(path),
    }
    if not item["title"] or not item["publication_status"] or not item["lifecycle_status"]:
        raise DevelopmentLibraryError(f"标准定义展示/状态字段不完整：{path}")
    return item, (standard_id, version, revision)


def build_manifest(scope_root: Path, *, generated_at: str | None = None) -> dict[str, Any]:
    scope_root = scope_root.resolve()
    if scope_root != DEFAULT_SCOPE.resolve():
        raise DevelopmentLibraryError(f"唯一可编辑定义入口必须是data/definitions：{scope_root}")
    delivery = _read_json(DELIVERY_SCOPE)
    bundled = delivery.get("bundled_definition_ids")
    formal = delivery.get("formal_evaluation_standard_ids")
    if not isinstance(bundled, list) or len(bundled) != 48 or len(set(bundled)) != 48:
        raise DevelopmentLibraryError("随包范围必须是明确的48项")
    if formal != ["gb-29446-2019"] or formal[0] not in bundled:
        raise DevelopmentLibraryError("正式评价范围必须且只能是GB29446—2019")

    current_paths = sorted(scope_root.glob("*.json"))
    entries: list[dict[str, Any]] = []
    keys: set[tuple[str, str, int]] = set()
    for path in current_paths:
        standard_id = path.stem
        item, key = _entry(path, "bundled" if standard_id in bundled else "draft")
        if item["id"] != standard_id:
            raise DevelopmentLibraryError(f"文件名与标准ID不一致：{path}")
        if key in keys:
            raise DevelopmentLibraryError(f"开发库存在重复标准版本：{key}")
        keys.add(key)
        entries.append(item)
        if item["scope"] == "bundled" and item["publication_status"] != "published":
            raise DevelopmentLibraryError(f"草稿不得纳入随包范围：{standard_id}")
        if item["scope"] == "draft" and item["publication_status"] != "draft":
            raise DevelopmentLibraryError(f"非随包定义必须保持draft：{standard_id}")
    missing = sorted(set(bundled) - {item["id"] for item in entries})
    if missing:
        raise DevelopmentLibraryError(f"随包定义缺失：{missing}")

    return {
        "schema_version": "2.0",
        "library_id": "uebench-development",
        "generated_at": generated_at or date.today().isoformat(),
        "canonical_source": "data/definitions",
        "delivery_scope_file": "data/delivery-scope.json",
        "comparison_snapshots": ["standards/development/scope-63", "standards/development/scope-65"],
        "current_standard_count": len(entries),
        "bundled_standard_count": len(bundled),
        "draft_standard_count": len(entries) - len(bundled),
        "formal_evaluation_standard_ids": formal,
        "standard_count": len(entries),
        "standards": entries,
    }


def validate_manifest(path: Path) -> dict[str, Any]:
    path = path.resolve()
    actual = _read_json(path)
    expected = build_manifest(DEFAULT_SCOPE, generated_at=str(actual.get("generated_at", "")))
    valid = actual == expected
    return {
        "path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
        "valid": valid,
        "current_standard_count": expected["current_standard_count"],
        "draft_standard_count": expected["draft_standard_count"],
        "standard_count": expected["standard_count"],
        "reason": "" if valid else "manifest与data/definitions及交付范围不一致",
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
            "draft_standard_count": payload["draft_standard_count"],
            "standard_count": payload["standard_count"],
        }, ensure_ascii=False, indent=2))
        return 0
    except (OSError, DevelopmentLibraryError) as exc:
        print(f"统一开发库索引失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
