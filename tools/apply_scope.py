from __future__ import annotations

import argparse
import json
from pathlib import Path


def apply_scope(data_dir: Path, scope_path: Path) -> None:
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    target = list(scope["standards"])
    expected_count = len(target)
    if len(target) != expected_count or len(set(target)) != expected_count:
        raise ValueError(f"范围必须包含{expected_count}个唯一标准编号")
    catalog_path = data_dir / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    by_number = {item["number"]: item for item in catalog["standards"]}
    missing = [number for number in target if number not in by_number]
    if missing:
        raise ValueError(f"目录中找不到范围标准：{missing}")
    catalog["catalog_name"] = scope["scope_name"]
    catalog["scope_version"] = str(expected_count)
    catalog["standard_count"] = expected_count
    catalog["standards"] = [by_number[number] for number in target]
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    definitions_dir = data_dir / "definitions"
    for path in definitions_dir.glob("*.json"):
        definition = json.loads(path.read_text(encoding="utf-8"))
        if definition["number"] not in target:
            path.unlink()
    remaining = list(definitions_dir.glob("*.json"))
    if len(remaining) != expected_count:
        raise ValueError(f"范围应用后定义数量不是{expected_count}：{len(remaining)}")
    print(f"已应用范围：{len(remaining)}项")


def main() -> None:
    parser = argparse.ArgumentParser(description="将当前标准数据切换到用户确认的范围")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--scope", type=Path, default=Path("data/scope-44.json"))
    args = parser.parse_args()
    apply_scope(args.data_dir.resolve(), args.scope.resolve())


if __name__ == "__main__":
    main()
