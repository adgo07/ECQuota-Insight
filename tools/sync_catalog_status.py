from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="同步目录中的规则状态，不改变目录范围或来源哈希")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    root = args.data_dir.resolve()
    definitions = {
        json.loads(path.read_text(encoding="utf-8"))["number"]: json.loads(path.read_text(encoding="utf-8"))
        for path in (root / "definitions").glob("gb-*.json")
    }
    catalog_path = root / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    for row in catalog["standards"]:
        definition = definitions.get(row["number"])
        if definition:
            row["status"] = definition["publication_status"]
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("catalog statuses synchronized")


if __name__ == "__main__":
    main()
