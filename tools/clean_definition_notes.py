"""Normalize rule-note arrays after rule-generation batches."""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    changed = 0
    for path in sorted(Path("data/definitions").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        touched = False
        for product in data.get("products", []):
            for indicator in product.get("indicators", []):
                notes = [note for note in indicator.get("notes", []) if str(note).strip()]
                if notes != indicator.get("notes", []):
                    indicator["notes"] = notes
                    touched = True
        if touched:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
    print(f"cleaned_definition_files={changed}")


if __name__ == "__main__":
    main()
