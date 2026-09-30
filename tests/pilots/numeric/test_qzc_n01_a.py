from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pytest
from pydantic import ValidationError

from uebench.bootstrap import create_context
from uebench.domain.engine import GB29446_NUMERIC_BEHAVIOR_VERSION, EvaluationEngine
from uebench.domain.models import EvaluationRequest, Grade, InputMode, InputValue, StandardDefinition


ROOT = Path(__file__).resolve().parents[3]
STANDARD_PATH = ROOT / "data" / "definitions" / "gb-29446-2019.json"
VECTORS_PATH = Path(__file__).with_name("qzc_n01_a_vectors.json")
VECTORS = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
LEGACY_THRESHOLDS = {
    "炼焦煤": ("5.0", "7.0", "8.5"),
    "动力煤": ("2.0", "3.0", "4.5"),
}
PROCESSES = {"炼焦煤": "跳汰、浮选联合", "动力煤": "干法选煤"}


@pytest.fixture(scope="module")
def standard() -> StandardDefinition:
    return StandardDefinition.model_validate_json(STANDARD_PATH.read_text(encoding="utf-8"))


def _product(standard: StandardDefinition, coal_type: str):
    return next(item for item in standard.products if item.selection_values["coal_type"] == coal_type)


def _direct_request(standard: StandardDefinition, coal_type: str, actual) -> EvaluationRequest:
    product = _product(standard, coal_type)
    direct_key = product.indicators[0].direct_input_key
    return EvaluationRequest(
        evaluation_date=max(standard.effective_date, date(2026, 9, 30)),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DIRECT,
        inputs={
            "washing_process": InputValue(value=PROCESSES[coal_type]),
            direct_key: InputValue(value=actual, unit="kW·h/t"),
        },
    )


def _legacy_round6_grade(coal_type: str, actual: str) -> Grade:
    quantum = Decimal("0.000001")
    compared_actual = Decimal(actual).quantize(quantum, rounding=ROUND_HALF_UP)
    for threshold, grade in zip(
        LEGACY_THRESHOLDS[coal_type],
        (Grade.LEVEL_1, Grade.LEVEL_2, Grade.LEVEL_3),
        strict=True,
    ):
        compared_threshold = Decimal(threshold).quantize(quantum, rounding=ROUND_HALF_UP)
        if compared_actual <= compared_threshold:
            return grade
    return Grade.NOT_QUALIFIED


@pytest.mark.parametrize("vector", VECTORS["boundary_vectors"], ids=lambda item: item["id"])
def test_boundary_vectors_execute_full_value_semantics(standard, vector):
    result = EvaluationEngine().evaluate(
        standard,
        _direct_request(standard, vector["coal_type"], vector["actual"]),
    ).results[0]

    expected_new = Grade[vector["expected_new_grade"]]
    expected_legacy = Grade[vector["expected_legacy_grade"]]
    assert result.actual_value == Decimal(vector["actual"])
    assert result.grade is expected_new
    assert _legacy_round6_grade(vector["coal_type"], vector["actual"]) is expected_legacy
    if vector["breaking"]:
        assert expected_new is not expected_legacy

    comparisons = [step for step in result.calculation_trace if step.operation == "grade_comparison"]
    assert comparisons
    assert all("ROUND(" not in step.expression for step in comparisons)
    assert all(GB29446_NUMERIC_BEHAVIOR_VERSION in step.expression for step in comparisons)


def test_required_breaking_values_are_present_and_changed():
    required = {
        "5.0000004": ("LEVEL_1", "LEVEL_2"),
        "7.0000004": ("LEVEL_2", "LEVEL_3"),
        "8.5000004": ("LEVEL_3", "NOT_QUALIFIED"),
        "2.0000004": ("LEVEL_1", "LEVEL_2"),
        "3.0000004": ("LEVEL_2", "LEVEL_3"),
        "4.5000004": ("LEVEL_3", "NOT_QUALIFIED"),
    }
    actual = {
        item["actual"]: (item["expected_legacy_grade"], item["expected_new_grade"])
        for item in VECTORS["boundary_vectors"]
        if item["breaking"]
    }
    assert actual == required


@pytest.mark.parametrize(
    ("lexical", "expected"),
    [("5", Decimal("5")), ("5.125", Decimal("5.125")), ("5.0000", Decimal("5.0000"))],
)
def test_exact_decimal_lexical_forms_round_trip(standard, lexical, expected):
    result = EvaluationEngine().evaluate(
        standard,
        _direct_request(standard, "炼焦煤", lexical),
    ).results[0]
    assert result.actual_value == expected
    assert str(result.actual_value) == lexical


@pytest.mark.parametrize("invalid", ["0", "-0.0001"])
def test_gb29446_zero_and_negative_inputs_are_business_invalid(standard, invalid):
    result = EvaluationEngine().evaluate(
        standard,
        _direct_request(standard, "炼焦煤", invalid),
    ).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert result.actual_value is None
    assert "必须大于 0" in result.warnings[0]


def test_python_float_is_rejected_at_domain_ingress():
    with pytest.raises((TypeError, ValidationError)):
        InputValue(value=5.0000004, unit="kW·h/t")


def test_json_number_is_rejected_before_authoritative_calculation(standard):
    product = _product(standard, "炼焦煤")
    payload = {
        "evaluation_date": "2026-09-30",
        "standard_id": standard.id,
        "product_id": product.id,
        "input_mode": "DIRECT",
        "inputs": {
            "washing_process": {"value": "跳汰、浮选联合"},
            product.indicators[0].direct_input_key: {"value": 5.0000004, "unit": "kW·h/t"},
        },
    }
    with pytest.raises((TypeError, ValidationError)):
        EvaluationRequest.model_validate_json(json.dumps(payload, ensure_ascii=False))


def test_detail_e2e_keeps_calculation_comparison_and_display_separate(standard):
    vector = VECTORS["e2e_vectors"][0]
    product = _product(standard, vector["coal_type"])
    request = EvaluationRequest(
        evaluation_date=max(standard.effective_date, date(2026, 9, 30)),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs={
            "washing_process": InputValue(value=vector["process"]),
            "electricity_consumption": InputValue(value=vector["electricity"], unit="kW·h"),
            "raw_coal_input": InputValue(value=vector["raw_coal"], unit="t"),
        },
    )
    indicator = EvaluationEngine().evaluate(standard, request).results[0]
    assert indicator.actual_value == Decimal(vector["expected_calculation_value"])
    assert indicator.grade is Grade[vector["expected_grade"]]

    display_value = indicator.actual_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert format(display_value, "f") == vector["expected_display_2dp"]
    assert indicator.grade is Grade.LEVEL_2

    comparisons = [step for step in indicator.calculation_trace if step.operation == "grade_comparison"]
    assert comparisons[0].value is False
    assert "5.0000004 <= 5" in comparisons[0].expression
    assert comparisons[1].value is True
    assert "5.0000004 <= 7" in comparisons[1].expression
    assert all("ROUND(" not in step.expression for step in comparisons)


def test_saved_result_preserves_numeric_behavior_trace(tmp_path: Path, standard):
    context = create_context(tmp_path / "n01-a-record")
    try:
        context.standards.install(standard)
        saved = context.application.evaluate(_direct_request(standard, "炼焦煤", "5.0000004"))
        loaded = context.application.get_evaluation(saved.evaluation_id)
        assert loaded is not None
        _, loaded_result, _ = loaded
        comparisons = [
            step
            for step in loaded_result.results[0].calculation_trace
            if step.operation == "grade_comparison"
        ]
        assert comparisons
        assert all(GB29446_NUMERIC_BEHAVIOR_VERSION in step.expression for step in comparisons)
        assert all("ROUND(" not in step.expression for step in comparisons)
    finally:
        context.database.dispose()
