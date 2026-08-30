"""Run a deterministic direct-entry smoke check for every published rule.

This is an acceptance aid rather than a replacement for source-based boundary
tests.  It fills declared inputs with conservative values, probes each rule at
its first constant threshold when possible, and reports indicators that remain
incomplete because their source-specific conditions need a real case.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

from uebench.domain.engine import EvaluationEngine
from uebench.domain.models import (
    ComparisonDirection,
    DataType,
    EvaluationRequest,
    Grade,
    InputMode,
    InputValue,
    PublicationStatus,
    StandardDefinition,
)


def _value(definition):
    if definition.data_type is DataType.BOOLEAN:
        return False
    if definition.data_type is DataType.TEXT:
        return definition.choices[0] if definition.choices else "测试"
    if definition.minimum is not None:
        return definition.minimum
    return Decimal("0")


def _inputs(product, indicator):
    definitions = {item.key: item for item in product.input_definitions}
    definitions.update({item.key: item for item in indicator.input_definitions})
    return {
        key: InputValue(value=_value(item), unit=item.unit)
        for key, item in definitions.items()
        if InputMode.DIRECT in item.modes
    }


def _definition_for(product, indicator, key):
    for item in [*product.input_definitions, *indicator.input_definitions]:
        if item.key == key:
            return item
    return None


def _constant_value(expression):
    if expression is not None and expression.op == "constant":
        return Decimal(str(expression.value))
    return None


def _expected_grade(actual: Decimal, limits: dict[str, Decimal], direction: ComparisonDirection) -> Grade:
    predicate = (lambda left, right: left <= right) if direction is ComparisonDirection.LTE else (
        lambda left, right: left >= right
    )
    for key, grade in (("LEVEL_1", Grade.LEVEL_1), ("LEVEL_2", Grade.LEVEL_2), ("LEVEL_3", Grade.LEVEL_3)):
        if key in limits and predicate(actual, limits[key]):
            return grade
    return Grade.NOT_QUALIFIED


def check(data_dir: Path) -> dict:
    engine = EvaluationEngine()
    counters = Counter()
    incomplete: list[dict[str, str]] = []
    boundary_errors: list[dict[str, str]] = []
    total = 0
    for path in sorted(data_dir.glob("*.json")):
        standard = StandardDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        if standard.publication_status is not PublicationStatus.PUBLISHED:
            continue
        for product in standard.products:
            for indicator in product.indicators:
                total += 1
                inputs = _inputs(product, indicator)
                probe = _constant_value(indicator.thresholds.level_1)
                if probe is None:
                    probe = Decimal("0")
                direct_definition = _definition_for(product, indicator, indicator.direct_input_key)
                if direct_definition is not None and direct_definition.minimum is not None:
                    probe = max(probe, direct_definition.minimum)
                inputs[indicator.direct_input_key] = InputValue(value=probe, unit=indicator.unit)
                request = EvaluationRequest(
                    evaluation_date=max(standard.effective_date, date.today()),
                    standard_id=standard.id,
                    product_id=product.id,
                    input_mode=InputMode.DIRECT,
                    inputs=inputs,
                )
                evaluated = engine.evaluate(standard, request)
                result = next(item for item in evaluated.results if item.indicator_id == indicator.id)
                counters[result.grade.value] += 1
                if result.grade is Grade.INCOMPLETE:
                    incomplete.append(
                        {
                            "standard": standard.number,
                            "product": product.id,
                            "indicator": indicator.id,
                            "warning": "; ".join(result.warnings),
                        }
                    )
                    continue
                limits = result.corrected_thresholds
                ordered = [limits[key] for key in ("LEVEL_1", "LEVEL_2", "LEVEL_3") if key in limits]
                # Only probe intervals when the source's available limits are
                # monotone; some mandatory tables intentionally contain a
                # non-monotone row and must be preserved as published.
                if len(ordered) == 3 and all(left <= right for left, right in zip(ordered, ordered[1:])):
                    probes = ordered[:]
                    probes.append((ordered[0] + ordered[1]) / Decimal("2"))
                    probes.append((ordered[1] + ordered[2]) / Decimal("2"))
                    delta = Decimal("0.01")
                    probes.append(ordered[-1] + delta if indicator.comparison is ComparisonDirection.LTE else ordered[-1] - delta)
                    for probe in probes:
                        if direct_definition is not None and direct_definition.minimum is not None and probe < direct_definition.minimum:
                            continue
                        if direct_definition is not None and direct_definition.maximum is not None and probe > direct_definition.maximum:
                            continue
                        candidate = request.model_copy(deep=True)
                        candidate.inputs[indicator.direct_input_key] = InputValue(value=probe, unit=indicator.unit)
                        checked = next(
                            item for item in engine.evaluate(standard, candidate).results if item.indicator_id == indicator.id
                        )
                        expected = _expected_grade(probe, limits, indicator.comparison)
                        if checked.grade is not expected:
                            boundary_errors.append(
                                {
                                    "standard": standard.number,
                                    "indicator": indicator.id,
                                    "probe": str(probe),
                                    "expected": expected.value,
                                    "actual": checked.grade.value,
                                }
                            )
    return {
        "total_indicators": total,
        "grades": dict(counters),
        "incomplete": incomplete,
        "boundary_errors": boundary_errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/definitions"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = check(args.data_dir)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
