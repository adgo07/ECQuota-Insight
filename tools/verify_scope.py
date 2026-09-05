from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path

from uebench.domain.models import StandardDefinition


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _display_path(path: Path) -> str:
    """Keep tracked verification reports portable across workstations."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pdf_page_count(path: Path) -> int | None:
    """Read the page tree marker without requiring a PDF runtime dependency.

    The source files are kept as supplied PDFs.  This lightweight check is only
    for page-reference bounds; it never extracts or interprets rule content.
    """
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data.startswith(b"%PDF-"):
        return None
    pages = re.findall(rb"/Type\s*/Page\b", data)
    return len(pages) or None


def _expression_input_keys(value) -> set[str]:
    """Collect input references without executing any rule expression."""
    if isinstance(value, dict):
        keys = {value["input_key"]} if value.get("op") == "input" and value.get("input_key") else set()
        for child in value.values():
            keys.update(_expression_input_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(_expression_input_keys(child))
        return keys
    return set()


def main() -> None:
    parser = argparse.ArgumentParser(description="验证标准范围、定义、原文引用和规则状态")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--scope-file", type=Path, help="范围清单；省略时依次使用scope-63.json、scope-65.json、scope-44.json")
    parser.add_argument("--output", type=Path, default=Path("work/verification/scope-report.json"))
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    if args.scope_file:
        scope_path = args.scope_file.resolve()
    else:
        scope_candidates = [data_dir / "scope-63.json", data_dir / "scope-65.json", data_dir / "scope-44.json"]
        scope_path = next((candidate for candidate in scope_candidates if candidate.exists()), scope_candidates[-1])
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    expected = set(scope["standards"])
    catalog = json.loads((data_dir / "catalog.json").read_text(encoding="utf-8"))["standards"]
    definitions: list[StandardDefinition] = []
    errors: list[str] = []
    for path in sorted((data_dir / "definitions").glob("*.json")):
        try:
            definition = StandardDefinition.model_validate_json(path.read_text(encoding="utf-8"))
            if definition.number in expected:
                definitions.append(definition)
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
    catalog_numbers = {item["number"] for item in catalog}
    definition_numbers = {item.number for item in definitions}
    expected_count = len(expected)
    if len(catalog) != expected_count:
        errors.append(f"目录数量不是{expected_count}：{len(catalog)}")
    if len(definitions) != expected_count:
        errors.append(f"定义数量不是{expected_count}：{len(definitions)}")
    if catalog_numbers != expected:
        errors.append(f"目录范围不一致：缺少={sorted(expected-catalog_numbers)} 多出={sorted(catalog_numbers-expected)}")
    if definition_numbers != expected:
        errors.append(f"定义范围不一致：缺少={sorted(expected-definition_numbers)} 多出={sorted(definition_numbers-expected)}")
    source_dir = args.source_dir.resolve()
    source_page_counts: dict[str, int | None] = {}
    for definition in definitions:
        source = source_dir / definition.source_file
        if not source.exists():
            errors.append(f"缺少原文：{definition.number} -> {definition.source_file}")
        elif _sha256(source) != definition.source_sha256.lower():
            errors.append(f"原文SHA-256不匹配：{definition.number} -> {definition.source_file}")
        else:
            source_page_counts[definition.source_file] = _pdf_page_count(source)
    indicators = [indicator for definition in definitions for product in definition.products for indicator in product.indicators]
    status = Counter(definition.publication_status.value for definition in definitions)
    draft_warnings: list[str] = []
    for definition in definitions:
        product_ids = [product.id for product in definition.products]
        if len(product_ids) != len(set(product_ids)):
            errors.append(f"{definition.number}: 产品/工序ID重复")
        for product in definition.products:
            indicator_ids = [indicator.id for indicator in product.indicators]
            if len(indicator_ids) != len(set(indicator_ids)):
                errors.append(f"{definition.number}/{product.id}: 指标ID重复")
            for indicator in product.indicators:
                input_definitions = list(product.input_definitions) + list(indicator.input_definitions)
                input_keys = [item.key for item in input_definitions]
                if len(input_keys) != len(set(input_keys)):
                    errors.append(f"{definition.number}/{indicator.id}: 输入键重复")
                allowed_input_keys = set(input_keys)
                allowed_input_keys.update({"energy.total_standard_coal", "production.total_equivalent"})
                if (
                    indicator.direct_input_key not in allowed_input_keys
                    and not indicator.direct_input_key.startswith(("energy.", "production."))
                ):
                    errors.append(
                        f"{definition.number}/{indicator.id}: direct_input_key 未定义：{indicator.direct_input_key}"
                    )
                expressions = [indicator.detail_formula, indicator.base_thresholds, indicator.thresholds]
                unknown = sorted(key for expression in expressions for key in _expression_input_keys(expression.model_dump(mode="json") if hasattr(expression, "model_dump") else expression) if key not in allowed_input_keys and not (key.startswith("energy.") or key.startswith("production.")))
                if unknown:
                    errors.append(f"{definition.number}/{indicator.id}: 规则引用未定义输入：{unknown}")
                for reference in indicator.source_references:
                    if not reference.table or not reference.clause:
                        errors.append(f"{definition.number}/{indicator.id}: 来源缺少条款或表号")
                    if reference.standard_number != definition.number:
                        errors.append(
                            f"{definition.number}/{indicator.id}: 来源标准号不一致：{reference.standard_number}"
                        )
                    page_count = source_page_counts.get(definition.source_file)
                    if reference.page < 1 or (page_count is not None and reference.page > page_count):
                        errors.append(
                            f"{definition.number}/{indicator.id}: PDF页码越界：第{reference.page}页"
                            f"（共{page_count or '未知'}页）"
                        )
                levels = [indicator.thresholds.level_1, indicator.thresholds.level_2, indicator.thresholds.level_3]
                if any(level is None for level in levels):
                    draft_warnings.append(f"{definition.number}/{indicator.id}: 原文存在缺级或未录入等级，需复核")
                if all(level is not None and level.op == "constant" for level in levels):
                    values = [Decimal(str(level.value)) for level in levels]
                    if indicator.comparison.value == "lte" and not values[0] <= values[1] <= values[2]:
                        draft_warnings.append(f"{definition.number}/{indicator.id}: 候选等级限额非单调 {values}")
                if definition.publication_status.value == "draft" and "not_for_formal_evaluation" not in indicator.notes:
                    draft_warnings.append(f"{definition.number}/{indicator.id}: draft规则缺少禁止正式评价标记")
    report = {
        "scope_file": _display_path(scope_path),
        "scope_count": len(expected),
        "catalog_count": len(catalog),
        "definition_count": len(definitions),
        "indicator_count": len(indicators),
        "standard_status": dict(status),
        "standards_with_rules": sum(bool(definition.products) for definition in definitions),
        "standards_without_rules": [definition.number for definition in definitions if not definition.products],
        "source_page_counts": {
            definition.number: source_page_counts.get(definition.source_file)
            for definition in definitions
        },
        "draft_quality_warning_count": len(draft_warnings),
        "draft_quality_warnings": draft_warnings,
        "valid": not errors,
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
