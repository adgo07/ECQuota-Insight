from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TARGET_RE = re.compile(r"GB\s*(\d{4,5})\s*[-—]\s*(\d{4})")
NUMBER = r"(?:-?\d+(?:\.\d+)?)"
TRAILING = re.compile(rf"((?:[≤<]?\s*{NUMBER}\s+){{2,}}[≤<]?\s*{NUMBER})\s*$")


def is_numeric_line(line: str) -> bool:
    return bool(TRAILING.search(line.strip()))


def clean_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    for line in lines:
        line = re.sub(r"\s+", " ", line.strip())
        if not line or line.startswith("第 ") or line.startswith("《现行主要"):
            continue
        if line in {"标准名称", "1级（先", "进值）", "2级（准", "入值）", "3级（限", "定值）标杆水平 基准水平"}:
            continue
        result.append(line)
    return result


def extract_rows(text: str, target_numbers: set[str]) -> list[dict[str, object]]:
    lines = text.replace("\r", "").splitlines()
    rows: list[dict[str, object]] = []
    block_start = 0
    for index, line in enumerate(lines):
        match = TRAILING.search(line.strip())
        if not match:
            continue
        block = clean_lines(lines[block_start : index + 1])
        block_start = index + 1
        citation = None
        for candidate in block:
            found = TARGET_RE.search(candidate)
            if found:
                citation = f"GB {found.group(1)}-{found.group(2)}"
                break
        if citation not in target_numbers:
            continue
        numbers = re.findall(NUMBER, match.group(1))
        if len(numbers) < 3:
            continue
        citation_index = next((i for i, item in enumerate(block) if TARGET_RE.search(item)), len(block))
        label_lines = block[:citation_index]
        label_lines = [item for item in label_lines if not item.startswith("《") and item != "）"]
        rows.append(
            {
                "standard_number": citation,
                "numbers": numbers,
                "label_lines": label_lines,
                "source_line": index + 1,
                "raw_block": block,
                "needs_review": len(numbers) != 3,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="从汇编提取44项标准的候选数据，结果必须回到原文复核")
    parser.add_argument("text", type=Path)
    parser.add_argument("scope", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    target = set(json.loads(args.scope.read_text(encoding="utf-8"))["standards"])
    rows = extract_rows(args.text.read_text(encoding="utf-8"), target)
    payload = {
        "schema_version": "1.0",
        "source": "《现行主要能耗限额标准汇编》（仅作候选线索）",
        "target_count": len(target),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已提取候选 {len(rows)} 行，涉及 {len({r['standard_number'] for r in rows})} 项标准")


if __name__ == "__main__":
    main()
