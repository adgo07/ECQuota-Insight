from __future__ import annotations

"""Normalize stable standard-family identities and rule revisions.

A standard number identifies one published edition, while standard_family_id groups editions and explicit replacement chains.
Missing rule_revision values are initialized to 1 and existing positive values are preserved.
The tool can update formal data and development snapshots; it never changes publication status or rule values.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = (
    ROOT / "standards" / "development" / "scope-63",
    ROOT / "standards" / "development" / "scope-65",
)
DEFAULT_REPLACEMENTS = ROOT / "data" / "standard-replacements.json"
_NUMBER_RE = re.compile(r"^(?P<prefix>[A-Z]+(?:/[A-Z]+)?\s+\d+)(?:-(?P<year>\d{4}))?$", re.IGNORECASE)


class IdentityError(ValueError):
    """The family graph or a definition cannot be normalized safely."""


def normalize_number(value: object) -> str:
    text = " ".join(str(value or "").strip().split()).upper()
    if not text:
        raise IdentityError("标准编号不能为空")
    return text


def own_family_id(number: str) -> str:
    normalized = normalize_number(number)
    match = _NUMBER_RE.fullmatch(normalized)
    if match:
        return match.group("prefix")
    # Keep support for a future non-GB identifier without inventing a new
    # delimiter convention; the current 63/65 snapshots all match the regex.
    return normalized.rsplit("-", 1)[0].strip()


def load_replacements(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for item in payload.get("replacements", []):
        obsolete = item.get("obsolete_number")
        replacement = item.get("replacement_number")
        if not obsolete or not replacement:
            continue
        old = normalize_number(obsolete)
        new = normalize_number(replacement)
        previous = mapping.get(old)
        if previous is not None and previous != new:
            raise IdentityError(f"一个旧标准存在多个替代标准：{old} -> {previous} / {new}")
        mapping[old] = new
    return mapping


def resolve_family_id(number: str, replacements: dict[str, str]) -> str:
    current = normalize_number(number)
    visited: list[str] = []
    while current in replacements:
        if current in visited:
            cycle = " -> ".join(visited + [current])
            raise IdentityError(f"标准替代关系存在循环：{cycle}")
        visited.append(current)
        current = replacements[current]
    return own_family_id(current)


def definition_paths(root: Path, *, include_retired: bool) -> list[Path]:
    paths = sorted((root / "definitions").glob("*.json"))
    if include_retired:
        paths.extend(sorted((root / "retired-definitions").glob("*.json")))
    return paths


def normalize_catalog(
    path: Path,
    replacements: dict[str, str],
    *,
    apply: bool,
) -> dict[str, Any]:
    """Normalize family and revision fields in a catalog JSON file."""
    path = path.resolve()
    if not path.exists():
        raise IdentityError(f"目录文件不存在：{path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    changed: list[str] = []
    for collection_name in ("standards", "historical_standards"):
        collection = data.get(collection_name, [])
        if not isinstance(collection, list):
            raise IdentityError(f"{path} 的{collection_name}必须是数组")
        for index, item in enumerate(collection):
            if not isinstance(item, dict):
                raise IdentityError(f"{path} 的{collection_name}[{index}]不是对象")
            number = normalize_number(item.get("number"))
            expected = resolve_family_id(number, replacements)
            existing = item.get("standard_family_id")
            if existing and normalize_number(existing) != expected:
                raise IdentityError(
                    f"{path} 的{collection_name}[{index}] family_id={existing!r}，应为 {expected!r}"
                )
            existing_revision = item.get("rule_revision")
            if existing_revision is not None:
                try:
                    revision = int(existing_revision)
                except (TypeError, ValueError) as exc:
                    raise IdentityError(
                        f"{path} 的{collection_name}[{index}] rule_revision不是整数：{existing_revision!r}"
                    ) from exc
                if revision < 1:
                    raise IdentityError(
                        f"{path} 的{collection_name}[{index}] rule_revision必须大于等于1：{revision}"
                    )
            if existing and existing_revision is not None:
                continue
            item["standard_family_id"] = existing or expected
            item["rule_revision"] = 1 if existing_revision is None else int(existing_revision)
            changed.append(f"{collection_name}[{index}]")
    if apply and changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "path": str(path),
        "item_count": sum(len(data.get(name, [])) for name in ("standards", "historical_standards")),
        "changed_count": len(changed),
        "changed": changed,
        "applied": apply,
    }


def normalize_root(
    root: Path,
    replacements: dict[str, str],
    *,
    apply: bool,
    include_retired: bool,
) -> dict[str, Any]:
    root = root.resolve()
    if not root.exists():
        raise IdentityError(f"快照目录不存在：{root}")
    changed: list[str] = []
    already_normalized: list[str] = []
    for path in definition_paths(root, include_retired=include_retired):
        data = json.loads(path.read_text(encoding="utf-8"))
        number = normalize_number(data.get("number"))
        expected = resolve_family_id(number, replacements)
        existing = data.get("standard_family_id")
        if existing and normalize_number(existing) != expected:
            raise IdentityError(f"{path} 的standard_family_id={existing!r}，应为 {expected!r}")
        existing_revision = data.get("rule_revision")
        if existing_revision is not None:
            try:
                revision = int(existing_revision)
            except (TypeError, ValueError) as exc:
                raise IdentityError(f"{path} 的rule_revision不是整数：{existing_revision!r}") from exc
            if revision < 1:
                raise IdentityError(f"{path} 的rule_revision必须大于等于1：{revision}")
        needs_family = not existing
        needs_revision = existing_revision is None
        if not needs_family and not needs_revision:
            already_normalized.append(str(path))
            continue
        updated: dict[str, Any] = {}
        inserted = False
        for key, value in data.items():
            updated[key] = value
            if key == "version":
                if needs_family:
                    updated["standard_family_id"] = expected
                if needs_revision:
                    updated["rule_revision"] = 1
                inserted = True
        if not inserted:
            if needs_family:
                updated["standard_family_id"] = expected
            if needs_revision:
                updated["rule_revision"] = 1
        changed.append(str(path))
        if apply:
            path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "root": str(root),
        "definition_count": len(changed) + len(already_normalized),
        "changed_count": len(changed),
        "already_normalized_count": len(already_normalized),
        "changed": changed,
        "include_retired": include_retired,
        "applied": apply,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="补全标准家族ID和规则修订号（适用于正式库或开发快照）")
    parser.add_argument("--root", dest="roots", action="append", type=Path, help="快照目录；可重复指定")
    parser.add_argument("--catalog", dest="catalogs", action="append", type=Path, help="目录JSON文件；可重复指定")
    parser.add_argument("--replacements", type=Path, default=DEFAULT_REPLACEMENTS)
    parser.add_argument("--check", action="store_true", help="只检查，不写文件；发现未补全时返回1")
    parser.add_argument("--include-retired", action="store_true", help="同时处理scope-63/retired-definitions")
    args = parser.parse_args()
    roots = [root.resolve() for root in (args.roots or DEFAULT_ROOTS)]
    catalogs = [path.resolve() for path in (args.catalogs or [])]
    try:
        replacements = load_replacements(args.replacements.resolve())
        reports = [
            normalize_root(
                root,
                replacements,
                apply=not args.check,
                include_retired=args.include_retired,
            )
            for root in roots
        ]
        catalog_reports = [
            normalize_catalog(path, replacements, apply=not args.check)
            for path in catalogs
        ]
    except (OSError, json.JSONDecodeError, IdentityError) as exc:
        print(f"标准家族ID处理失败：{exc}", file=sys.stderr)
        return 2
    print(json.dumps({"replacements": replacements, "reports": reports, "catalog_reports": catalog_reports}, ensure_ascii=False, indent=2))
    if args.check:
        return 0 if all(report["changed_count"] == 0 for report in reports + catalog_reports) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
