from __future__ import annotations

import argparse
import json
from pathlib import Path

from uebench.domain.models import StandardDefinition


NUMBERS = {
    "GB 21370-2017": "visual_reviewed_2026-08-26_original_pdf_tables_1-3",
    "GB 25323-2023": "visual_reviewed_2026-08-26_original_pdf_tables_1-12",
    "GB 29141-2012": "visual_reviewed_2026-08-26_original_pdf_tables_1-3",
    "GB 29438-2012": "visual_reviewed_2026-08-26_original_pdf_clause_4",
    "GB 30526-2019": "visual_reviewed_2026-08-26_original_pdf_tables_1-2",
    "GB 33654-2017": "visual_reviewed_2026-08-26_original_pdf_table_1",
    "GB 38263-2019": "visual_reviewed_2026-08-26_original_pdf_table_1",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    root = args.data_dir.resolve()
    for path in sorted((root / "definitions").glob("gb-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        note = NUMBERS.get(data.get("number"))
        if note is None:
            continue
        data["publication_status"] = "reviewed"
        for product in data.get("products", []):
            product["description"] = "已对照标准原文表格逐项复核；待用户确认后发布。"
            for indicator in product.get("indicators", []):
                notes = [x for x in indicator.get("notes", []) if x != "requires_independent_review"]
                if note not in notes:
                    notes.append(note)
                indicator["notes"] = notes
                for ref in indicator.get("source_references", []):
                    ref["note"] = "已对照标准原文表格复核；待用户确认后发布。"
        StandardDefinition.model_validate(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"reviewed: {data['number']}")


if __name__ == "__main__":
    main()
