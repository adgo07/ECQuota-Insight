from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


NUMBER = r"(?:-?\d+(?:\.\d+)?)"
TRAILING = re.compile(rf"((?:[≤<]?\s*{NUMBER}\s+){{2,}}[≤<]?\s*{NUMBER})\s*$")
PAGE = re.compile(r"^(\d+)\s*$")


def extract_lines(raw_lines: list[str], page: int | None = None) -> list[dict[str, object]]:
    lines = [line.strip() for line in raw_lines]
    candidates: list[dict[str, object]] = []
    in_limits = False
    for index, line in enumerate(lines):
        if re.match(r"^4(?:\.|\s)\S", line) or "能耗限额等级" in line:
            in_limits = True
        if re.match(r"^5(?:\.|\s)\S", line) or line.startswith("5 技术要求"):
            in_limits = False
        if not in_limits or not line:
            continue
        match = TRAILING.search(line)
        if not match:
            continue
        raw_values = match.group(1)
        numbers = re.findall(NUMBER, raw_values)
        if len(numbers) < 3:
            continue
        candidates.append(
            {
                "line": index + 1,
                "page": page,
                "numbers": numbers,
                "row_prefix": line[: match.start()].strip(),
                "raw_context": lines[max(0, index - 8) : index + 1],
                "kind": "multi" if len(numbers) > 3 else "triple",
            }
        )
    return candidates


def extract_file(path: Path) -> list[dict[str, object]]:
    return extract_lines(path.read_text(encoding="utf-8").replace("\\n", "\n").splitlines())


def extract_pages(path: Path) -> list[dict[str, object]]:
    pages = json.loads(path.read_text(encoding="utf-8"))
    results: list[dict[str, object]] = []
    for page_number, text in enumerate(pages, start=1):
        results.extend(extract_lines(text.replace("\\n", "\n").splitlines(), page_number))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="从标准原文第4章提取限额表候选行，不直接发布规则")
    parser.add_argument("text_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pages-dir", type=Path)
    args = parser.parse_args()
    payload: dict[str, list[dict[str, object]]] = {}
    # When page-level extraction is supplied, it is the authoritative input
    # list.  This also supports a pages-only directory produced directly from
    # the original PDFs (there may be no companion .txt files).
    if args.pages_dir:
        inputs = sorted(args.pages_dir.glob("*.json"))
        for page_path in inputs:
            payload[page_path.stem] = extract_pages(page_path)
    else:
        for path in sorted(args.text_dir.glob("*.txt")):
            payload[path.stem] = extract_file(path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已提取 {len(payload)} 个标准，共 {sum(len(rows) for rows in payload.values())} 行候选")


if __name__ == "__main__":
    main()
