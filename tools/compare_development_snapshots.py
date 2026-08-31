from __future__ import annotations

"""Compare the canonical and legacy development rule snapshots.

The current development baseline is kept in scope-63.  scope-65 is a
historical comparison snapshot and must never silently become a publish input.
This tool produces an auditable report so replacements and content changes are
explicit before either snapshot is changed.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _load_snapshot(root: Path) -> dict[str, Any]:
    root = root.resolve()
    scope_path = root / f"{root.name}.json"
    if not scope_path.exists():
        raise ValueError(f"找不到范围清单：{scope_path}")
    payload = json.loads(scope_path.read_text(encoding="utf-8"))
    numbers = [str(item).strip() for item in payload.get("standards", []) if str(item).strip()]
    if not numbers:
        raise ValueError(f"范围清单没有标准编号：{scope_path}")
    duplicate_scope = sorted(number for number, count in Counter(numbers).items() if count > 1)
    if duplicate_scope:
        raise ValueError(f"范围清单存在重复标准编号：{', '.join(duplicate_scope)}")

    definitions_dir = root / "definitions"
    paths = sorted(definitions_dir.glob("*.json"))
    definitions: dict[str, dict[str, Any]] = {}
    duplicate_definitions: list[str] = []
    for path in paths:
        definition = json.loads(path.read_text(encoding="utf-8"))
        number = str(definition.get("number", "")).strip()
        if not number:
            raise ValueError(f"规则定义缺少标准编号：{path}")
        if number in definitions:
            duplicate_definitions.append(number)
        definitions[number] = definition
    if duplicate_definitions:
        raise ValueError(
            f"规则定义存在重复标准编号：{', '.join(sorted(set(duplicate_definitions)))}"
        )

    expected = set(numbers)
    actual = set(definitions)
    return {
        "root": str(root),
        "scope_file": str(scope_path),
        "scope_name": payload.get("scope_name", root.name),
        "numbers": numbers,
        "definitions": definitions,
        "missing_definitions": sorted(expected - actual),
        "extra_definitions": sorted(actual - expected),
        "status_counts": dict(
            Counter(
                str(definition.get("publication_status", "unknown"))
                for definition in definitions.values()
                if definition.get("number") in expected
            )
        ),
    }


def _load_replacements(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    if not path.exists():
        raise ValueError(f"找不到替代关系文件：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict[str, Any]] = {}
    for item in payload.get("replacements", []):
        obsolete = str(item.get("obsolete_number", "")).strip()
        if obsolete:
            result[obsolete] = item
    return result


def compare_snapshots(
    canonical_root: Path,
    legacy_root: Path,
    replacements_path: Path | None = Path("data/standard-replacements.json"),
) -> dict[str, Any]:
    canonical = _load_snapshot(canonical_root)
    legacy = _load_snapshot(legacy_root)
    replacements = _load_replacements(replacements_path.resolve() if replacements_path else None)

    canonical_numbers = set(canonical["numbers"])
    legacy_numbers = set(legacy["numbers"])
    common = sorted(canonical_numbers & legacy_numbers)
    canonical_only = sorted(canonical_numbers - legacy_numbers)
    legacy_only = sorted(legacy_numbers - canonical_numbers)
    different = [
        number
        for number in common
        if canonical["definitions"][number] != legacy["definitions"][number]
    ]
    changed_fields = Counter(
        field
        for number in different
        for field in set(canonical["definitions"][number]) | set(legacy["definitions"][number])
        if canonical["definitions"][number].get(field) != legacy["definitions"][number].get(field)
    )

    legacy_mappings = []
    unresolved: list[str] = []
    for number in legacy_only:
        mapping = replacements.get(number)
        replacement = str(mapping.get("replacement_number", "")).strip() if mapping else ""
        in_canonical = bool(replacement and replacement in canonical_numbers)
        legacy_mappings.append(
            {
                "obsolete_number": number,
                "replacement_number": replacement or None,
                "replacement_in_canonical_scope": in_canonical,
                "status": mapping.get("status") if mapping else None,
            }
        )
        if not in_canonical:
            unresolved.append(number)

    canonical_valid = not canonical["missing_definitions"] and not canonical["extra_definitions"]
    legacy_valid = not legacy["missing_definitions"] and not legacy["extra_definitions"]
    return {
        "canonical": {
            key: value
            for key, value in canonical.items()
            if key != "definitions"
        },
        "legacy": {
            key: value
            for key, value in legacy.items()
            if key != "definitions"
        },
        "comparison": {
            "common_count": len(common),
            "identical_definition_count": len(common) - len(different),
            "different_definition_count": len(different),
            "different_definition_numbers": different,
            "canonical_only": canonical_only,
            "legacy_only": legacy_only,
            "legacy_mappings": legacy_mappings,
            "unresolved_legacy_only": unresolved,
            "changed_top_level_fields": dict(sorted(changed_fields.items())),
        },
        "valid": canonical_valid and legacy_valid and not unresolved,
        "merge_decision": (
            "scope-63是唯一开发基线；scope-65仅保留用于历史追溯，旧版标准必须通过替代关系进入历史目录。"
            if canonical_valid and legacy_valid and not unresolved
            else "不能合并：先修复范围/定义缺失或补齐旧版标准替代关系。"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="比较63项与65项开发标准快照并检查替代关系")
    parser.add_argument("--canonical", type=Path, default=Path("standards/development/scope-63"))
    parser.add_argument("--legacy", type=Path, default=Path("standards/development/scope-65"))
    parser.add_argument(
        "--replacements",
        type=Path,
        default=Path("data/standard-replacements.json"),
        help="标准替代关系文件；传空字符串可跳过",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = compare_snapshots(
            args.canonical,
            args.legacy,
            None if str(args.replacements) == "" else args.replacements,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"快照比较失败：{exc}", file=sys.stderr)
        return 2
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.output.resolve().write_text(payload + "\n", encoding="utf-8")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
