"""Derive GB 29446 display coefficient rows from each product's formula.

For each product, the sole editable k table is the lookup.rows under its
indicator's detail_formula. The two lookups under display_calculations are
generated copies. Keep this within the existing StandardDefinition schema;
do not create a second full definition or alter Decimal lexical strings.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_DEFINITION = Path(__file__).resolve().parents[1] / "data/definitions/gb-29446-2019.json"


def _lookups(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, dict):
        result = [node] if node.get("op") == "lookup" else []
        for value in node.values():
            result.extend(_lookups(value))
        return result
    if isinstance(node, list):
        return [lookup for value in node for lookup in _lookups(value)]
    return []


def synchronize(payload: dict[str, Any]) -> list[str]:
    """Replace only derived lookup rows; return human-readable drift locations."""
    if payload.get("id") != "gb-29446-2019":
        raise ValueError("只接受 GB 29446—2019 定义")
    products = payload.get("products")
    if not isinstance(products, list) or len(products) != 2:
        raise ValueError("选煤定义应包含两个产品")
    seen: set[str] = set()
    drift: list[str] = []
    for product in products:
        product_id = product.get("id")
        if not isinstance(product_id, str) or not product_id or product_id in seen:
            raise ValueError("产品 ID 缺失或重复")
        seen.add(product_id)
        indicators = product.get("indicators")
        if not isinstance(indicators, list) or len(indicators) != 1:
            raise ValueError(f"{product_id} 必须有一个评价指标")
        indicator = indicators[0]
        source = _lookups(indicator.get("detail_formula"))
        derived = _lookups(indicator.get("display_calculations"))
        if len(source) != 1 or len(derived) != 2:
            raise ValueError(f"{product_id} 的系数 lookup 应为公式一处、展示两处")
        rows = source[0].get("rows")
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{product_id} 的公式系数表为空")
        conditions = [json.dumps(row.get("condition"), ensure_ascii=False, sort_keys=True) for row in rows]
        if len(conditions) != len(set(conditions)):
            raise ValueError(f"{product_id} 的公式系数条件重复")
        for index, lookup in enumerate(derived, start=1):
            if lookup.get("rows") != rows:
                drift.append(f"{product_id}/display_calculations/lookup-{index}")
                lookup["rows"] = deepcopy(rows)
    return drift


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验或派生 GB 29446 系数展示副本")
    parser.add_argument("--definition", type=Path, default=DEFAULT_DEFINITION)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="仅检查派生副本")
    mode.add_argument("--write", action="store_true", help="从公式系数表重生派生副本")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.definition.read_text(encoding="utf-8"))
        drift = synchronize(payload)
        if args.check:
            if drift:
                print("选煤系数派生副本不一致：" + "、".join(drift), file=sys.stderr)
                return 1
            print("选煤系数派生副本一致")
            return 0
        if drift:
            args.definition.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已同步 {len(drift)} 处系数派生副本")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"选煤系数派生校验失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
