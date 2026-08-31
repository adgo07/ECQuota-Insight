from __future__ import annotations

from datetime import date

from uebench.domain.engine import EvaluationEngine
from uebench.domain.models import EvaluationRequest, InputMode, InputValue

from .test_engine import make_standard


def test_legacy_standard_derives_stable_family_id() -> None:
    standard = make_standard()
    assert standard.standard_family_id is None
    assert standard.family_id == "GB 00000"
    standard.standard_family_id = "custom-family"
    assert standard.family_id == "custom-family"


def test_evaluation_result_records_family_and_rule_revision() -> None:
    standard = make_standard()
    standard.rule_revision = 3
    request = EvaluationRequest(
        evaluation_date=date(2026, 3, 1),
        standard_id=standard.id,
        product_id="product",
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="10", unit="kgce/t")},
    )
    result = EvaluationEngine().evaluate(standard, request)
    assert result.standard_family_id == "GB 00000"
    assert result.rule_revision == 3
