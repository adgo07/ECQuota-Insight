from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_duplicate_product_names_have_distinct_indicator_names() -> None:
    """同名产品/工序可以并存，但指标名称必须能区分每一行。"""

    for path in sorted((ROOT / "standards" / "development" / "scope-63" / "definitions").glob("*.json")):
        definition = json.loads(path.read_text(encoding="utf-8"))
        by_product: dict[str, list[str]] = defaultdict(list)
        for product in definition.get("products", []):
            for indicator in product.get("indicators", []):
                by_product[product["name"]].append(indicator["name"])

        for product_name, indicator_names in by_product.items():
            if len(indicator_names) > 1:
                assert len(indicator_names) == len(set(indicator_names)), (
                    definition["number"],
                    product_name,
                    indicator_names,
                )