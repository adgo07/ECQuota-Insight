from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from uebench.bootstrap import create_context
from uebench.domain.engine import EvaluationEngine
from uebench.domain.models import (
    EvaluationRequest,
    Grade,
    InputMode,
    InputValue,
    StandardDefinition,
)
from uebench.infrastructure.packages import PackageManifest, StandardPackageBuilder


STANDARD_PATH = Path(__file__).parents[1] / "data" / "definitions" / "gb-29446-2019.json"
OUTSIDE_PROCESS = "附录A外工艺（需人工确认）"
GOLDEN_PATH = Path(__file__).parent / "fixtures" / "gb29446_golden_cases.json"
GOLDEN = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
PROCESSES = {}
for _case in GOLDEN["classification_cases"]:
    PROCESSES.setdefault(_case["coal_type"], {})[_case["process"]] = _case["k"]
THRESHOLDS = {
    item["coal_type"]: [
        (item["level_1"], Grade.LEVEL_1),
        (str(Decimal(item["level_1"]) + Decimal("0.0001")), Grade.LEVEL_2),
        (item["level_2"], Grade.LEVEL_2),
        (str(Decimal(item["level_2"]) + Decimal("0.0001")), Grade.LEVEL_3),
        (item["level_3"], Grade.LEVEL_3),
        (str(Decimal(item["level_3"]) + Decimal("0.0001")), Grade.NOT_QUALIFIED),
    ]
    for item in GOLDEN["limits"]
}
_DEFAULT_PROCESS = object()

@pytest.fixture(scope="module")
def standard() -> StandardDefinition:
    return StandardDefinition.model_validate_json(STANDARD_PATH.read_text(encoding="utf-8"))


def _product(standard: StandardDefinition, coal_type: str):
    return next(product for product in standard.products if product.selection_values["coal_type"] == coal_type)


def _request(
    standard: StandardDefinition,
    coal_type: str,
    *,
    process: str | None | object = _DEFAULT_PROCESS,
    electricity: str | None = "100",
    raw_coal: str | None = "100",
    electricity_unit: str = "kW·h",
    raw_coal_unit: str = "t",
) -> EvaluationRequest:
    product = _product(standard, coal_type)
    if process is _DEFAULT_PROCESS:
        process = next(iter(PROCESSES[coal_type]))
    inputs = {}
    if process is not None:
        inputs["washing_process"] = InputValue(value=process)
    if electricity is not None:
        inputs["electricity_consumption"] = InputValue(value=electricity, unit=electricity_unit)
    if raw_coal is not None:
        inputs["raw_coal_input"] = InputValue(value=raw_coal, unit=raw_coal_unit)
    return EvaluationRequest(
        evaluation_date=max(standard.effective_date, date(2026, 9, 26)),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=InputMode.DETAIL,
        inputs=inputs,
    )


@pytest.mark.parametrize(
    ("coal_type", "process", "expected_factor"),
    [
        (case["coal_type"], case["process"], case["k"])
        for case in GOLDEN["classification_cases"]
    ],
)
def test_appendix_a_has_all_twelve_exact_factors(standard, coal_type, process, expected_factor):
    request = _request(standard, coal_type, process=process, electricity="1", raw_coal="1")
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal(expected_factor)
    assert result.display_values["process_factor"] == Decimal(expected_factor)
    assert any("附录A 表A.1" in step.label for step in result.calculation_trace)


def test_unadjusted_e0_is_explanatory_and_grade_uses_adjusted_ed(standard):
    request = _request(
        standard,
        "炼焦煤",
        process="跳汰",
        electricity="410",
        raw_coal="100",
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.display_values["unadjusted_power_consumption"] == Decimal("4.1")
    assert result.actual_value == Decimal("5.166")
    assert result.grade is Grade.LEVEL_2


@pytest.mark.parametrize(("coal_type", "actual", "expected"), [(coal, actual, grade) for coal, values in THRESHOLDS.items() for actual, grade in values])
def test_each_coal_grade_boundaries_include_threshold_and_values_on_both_sides(standard, coal_type, actual, expected):
    process, factor = next(iter(PROCESSES[coal_type].items()))
    actual_value = Decimal(actual)
    factor_value = Decimal(factor)
    request = _request(
        standard,
        coal_type,
        process=process,
        electricity=str(actual_value * Decimal("100")),
        raw_coal=str(factor_value * Decimal("100")),
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == actual_value
    assert result.grade is expected


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        (case["electricity"], Grade[case["expected_grade"]])
        for case in GOLDEN["round6_cases"]
    ],
)
def test_gb29446_grade_threshold_comparisons_round_both_values_to_six_places(standard, actual, expected):
    actual_value = Decimal(actual)
    request = _request(
        standard,
        "炼焦煤",
        process="跳汰、浮选联合",
        electricity=str(actual_value * Decimal("100")),
        raw_coal="100",
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == actual_value
    assert result.grade is expected


@pytest.mark.parametrize(
    ("electricity", "expected", "rounded_comparison"),
    [
        ("5.0000004", Grade.LEVEL_1, "5.000000 <= 5.000000"),
        ("8.5000004", Grade.LEVEL_3, "8.500000 <= 8.500000"),
    ],
)
def test_detail_formula_grade_trace_shows_six_place_comparison(standard, electricity, expected, rounded_comparison):
    request = _request(
        standard,
        "炼焦煤",
        process="跳汰、浮选联合",
        electricity=electricity,
        raw_coal="1",
    )
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.actual_value == Decimal(electricity)
    assert result.grade is expected
    comparison_step = next(step for step in result.calculation_trace if step.operation == "grade_comparison")
    assert rounded_comparison in comparison_step.expression


@pytest.mark.parametrize(
    ("changes", "warning"),
    [
        ({"electricity": None}, "缺少输入"),
        ({"raw_coal": None}, "缺少输入"),
        ({"electricity": "-1"}, "必须大于 0"),
        ({"raw_coal": "-1"}, "必须大于 0"),
        ({"electricity": "0"}, "必须大于 0"),
        ({"raw_coal": "0"}, "必须大于 0"),
        ({"electricity_unit": "kWh"}, "单位应为"),
        ({"raw_coal_unit": "kg"}, "单位应为"),
    ],
)
def test_invalid_detail_inputs_are_incomplete(standard, changes, warning):
    request = _request(standard, "炼焦煤", **changes)
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert any(warning in item for item in result.warnings)


@pytest.mark.parametrize(
    ("changes", "label", "internal_key"),
    [
        ({"electricity": None}, "统计期选煤电力消耗量 E_d", "electricity_consumption"),
        ({"raw_coal": None}, "统计期入选原煤量 m", "raw_coal_input"),
    ],
)
def test_missing_detail_warnings_use_chinese_rule_labels(standard, changes, label, internal_key):
    request = _request(standard, "炼焦煤", **changes)
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert label in result.warnings[0]
    assert internal_key not in result.warnings[0]


def test_process_mismatch_and_appendix_external_process_require_manual_review(standard):
    mismatch = _request(standard, "炼焦煤", process="干法选煤")
    result = EvaluationEngine().evaluate(standard, mismatch).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert "不在允许选项中" in result.warnings[0]

    outside = _request(standard, "炼焦煤", process=OUTSIDE_PROCESS)
    result = EvaluationEngine().evaluate(standard, outside).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert "附录A未列出" in result.warnings[0]
    assert result.compliance_result is None


def test_explicit_multiple_coal_input_is_rejected(standard):
    request = _request(standard, "炼焦煤", electricity="500", raw_coal="100")
    request.inputs["coal_type"] = InputValue(value="炼焦煤、动力煤")
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert "不接受多种煤种" in result.warnings[0]
    assert result.actual_value is None


def test_source_references_cover_limits_formula_and_appendix_a(standard):
    coking = _product(standard, "炼焦煤").indicators[0]
    assert {(item.page, item.clause, item.table) for item in coking.source_references} >= {
        (3, "3.1 炼焦煤选煤企业选煤电力单耗限额等级", "表1"),
        (4, "5.2 选煤电力单耗计算方法", "式（1）"),
        (5, "附录A 选煤工艺类型折算系数", "表A.1"),
    }


def test_result_and_request_survive_save_and_read(tmp_path: Path, standard):
    context = create_context(tmp_path / "isolated-data")
    try:
        context.standards.install(standard)
        request = _request(standard, "炼焦煤", process="重介", electricity="560", raw_coal="100")
        request.notes = "核算周期：全年\n备注：保存测试"
        saved = context.application.evaluate(request)
        loaded = context.application.get_evaluation(saved.evaluation_id)
        assert loaded is not None
        loaded_request, loaded_result, snapshot = loaded
        loaded_indicator = loaded_result.results[0]
        assert loaded_request.inputs["washing_process"].value == "重介"
        assert "enterprise_status" not in loaded_request.inputs
        assert "single_coal_single_process" not in loaded_request.inputs
        assert loaded_request.notes == "核算周期：全年\n备注：保存测试"
        assert loaded_indicator.actual_value == Decimal("6.272")
        assert loaded_indicator.display_values["unadjusted_power_consumption"] == Decimal("5.6")
        assert loaded_indicator.compliance_requirement is None
        assert loaded_indicator.compliance_limit is None
        assert loaded_indicator.compliance_result is None
        assert loaded_indicator.calculation_trace
        assert loaded_indicator.source_references[-1].table == "表A.1"
        assert snapshot.rule_revision == 2
    finally:
        context.database.dispose()


def test_gb29446_definition_round_trips_through_signed_package_builder(tmp_path: Path, standard):
    package_definition = standard.model_copy(deep=True)
    package_definition.source_file = "source.pdf"
    source = tmp_path / "source.pdf"
    source.write_bytes(b"isolated GB 29446 package test source")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    package_definition.source_sha256 = source_hash
    for product in package_definition.products:
        for indicator in product.indicators:
            for reference in indicator.source_references:
                reference.source_file = "source.pdf"
                reference.source_sha256 = source_hash
    output = tmp_path / "gb29446-sample.uebench"
    StandardPackageBuilder(Ed25519PrivateKey.generate()).build(
        output,
        [package_definition],
        {"source.pdf": source},
        data_version="2026.09-published.3",
    )
    with zipfile.ZipFile(output) as package:
        manifest = PackageManifest.model_validate_json(package.read("manifest.json"))
        packaged_definition_data = json.loads(package.read("definitions/gb-29446-2019-2019-r2.json"))
        packaged_definition = StandardDefinition.model_validate(packaged_definition_data)
    packaged_indicator_data = packaged_definition_data["products"][0]["indicators"][0]
    assert "direct_input_key" not in packaged_indicator_data
    assert "compliance_rule" not in packaged_indicator_data
    assert manifest.standard_count == 1
    assert manifest.rule_count == 2
    assert packaged_definition.rule_revision == 2
    assert packaged_definition.products[0].indicators[0].compliance_rule is None
    assert packaged_definition.products[0].indicators[0].display_calculations


def test_golden_standard_data_is_complete_canonical_and_source_bound():
    for group_name in ("normal_cases", "formula_cases", "boundary_cases", "round6_cases", "anomaly_cases"):
        case_ids = [case["id"] for case in GOLDEN[group_name]]
        assert len(case_ids) == len(set(case_ids)), f"duplicate case id in {group_name}"
    factor_keys = [(case["coal_type"], case["process"]) for case in GOLDEN["classification_cases"]]
    assert len(factor_keys) == len(set(factor_keys))
    canonical_bytes = STANDARD_PATH.read_bytes()
    mirror_path = Path(__file__).parents[1] / GOLDEN["standard"]["development_mirror"]
    assert canonical_bytes == mirror_path.read_bytes()

    payload = json.loads(canonical_bytes)
    standard = StandardDefinition.model_validate(payload)
    assert standard.id == GOLDEN["standard"]["id"]
    assert standard.number == GOLDEN["standard"]["number"]
    assert standard.source_sha256 == GOLDEN["standard"]["normative_sha256"]
    coal_types = {product.selection_values["coal_type"] for product in standard.products}
    assert coal_types == {item["coal_type"] for item in GOLDEN["limits"]}
    assert set(PROCESSES) == coal_types
    for product in standard.products:
        indicator = product.indicators[0]
        assert indicator.thresholds.level_1.value == next(x["level_1"] for x in GOLDEN["limits"] if x["coal_type"] == product.selection_values["coal_type"])
        assert indicator.thresholds.level_2.value == next(x["level_2"] for x in GOLDEN["limits"] if x["coal_type"] == product.selection_values["coal_type"])
        assert indicator.thresholds.level_3.value == next(x["level_3"] for x in GOLDEN["limits"] if x["coal_type"] == product.selection_values["coal_type"])
        actual_factors = _ui_factor_map(product)
        assert actual_factors == {
            case["process"]: Decimal(case["k"])
            for case in GOLDEN["classification_cases"]
            if case["coal_type"] == product.selection_values["coal_type"]
        }
        references = {(ref.page, ref.clause, ref.table) for ref in indicator.source_references}
        assert any(page == 4 and table == "式（1）" for page, _clause, table in references)
        assert any(page == 5 and table == "表A.1" for page, _clause, table in references)
        assert indicator.compliance_rule is None
    all_references = {
        (reference.page, reference.clause, reference.table)
        for product in standard.products
        for indicator in product.indicators
        for reference in indicator.source_references
    }
    for reference in GOLDEN["standard"]["source_references"]:
        assert any(
            page == reference["page"] and table == reference["table"]
            for page, _clause, table in all_references
        )
    encoded = canonical_bytes.decode("utf-8")
    for key in GOLDEN["standard"]["forbidden_rule_keys"]:
        assert key not in encoded



def test_golden_contract_uses_only_the_standard_formula_and_engine_grade():
    payload = json.loads(STANDARD_PATH.read_text(encoding="utf-8"))
    expected_inputs = set(GOLDEN["ui_contract"]["formal_input_keys"])
    for product in payload["products"]:
        product_inputs = product["input_definitions"]
        indicator = product["indicators"][0]
        assert {item["key"] for item in product_inputs + indicator["input_definitions"]} == expected_inputs
        assert all(item["modes"] == ["DETAIL"] for item in product_inputs + indicator["input_definitions"])
        assert "direct_input_key" not in indicator
        assert all(item["modes"] == ["DETAIL"] for item in indicator["display_calculations"])
        assert {item["key"] for item in indicator["display_calculations"]} == {
            "process_factor",
            "unadjusted_power_consumption",
            "electricity_consumption",
            "raw_coal_input",
        }

    from inspect import getsource
    from uebench.ui.main_window import MainWindow

    collect_source = getsource(MainWindow._collect_gb29446_request)
    calculate_source = getsource(MainWindow.calculate_evaluation)
    display_source = getsource(MainWindow._show_gb29446_result)
    assert "InputMode.DETAIL" in collect_source
    assert "InputMode.DIRECT" not in collect_source
    assert "self.context.application.evaluate(request)" in calculate_source
    assert "self._show_gb29446_result(request, result)" in calculate_source
    assert "Grade." not in display_source
    assert "EvaluationEngine" not in display_source
    assert "comparison_step.expression" in display_source


def _ui_factor_map(product):
    # Keep the UI selector contract tied to the display lookup in canonical rule data.
    from uebench.ui.main_window import MainWindow
    return MainWindow._gb29446_factor_map(product)


@pytest.mark.parametrize(
    "case",
    GOLDEN["normal_cases"],
    ids=[case["id"] for case in GOLDEN["normal_cases"]],
)
def test_golden_normal_cases_match_engine(case, standard):
    inputs = case["input"]
    result = EvaluationEngine().evaluate(
        standard,
        _request(
            standard,
            inputs["coal_type"],
            process=inputs["process"],
            electricity=inputs["electricity"],
            raw_coal=inputs["raw_coal"],
        ),
    ).results[0]
    expected = case["expected"]
    assert result.display_values["process_factor"] == Decimal(expected["k"])
    assert result.display_values["unadjusted_power_consumption"] == Decimal(expected["unadjusted"])
    assert result.actual_value == Decimal(expected["actual"])
    assert result.grade is Grade[expected["grade"]]


@pytest.mark.parametrize(
    "case",
    GOLDEN["formula_cases"],
    ids=[case["id"] for case in GOLDEN["formula_cases"]],
)
def test_golden_formula_cases_preserve_decimal_calculation(case, standard):
    inputs = case["input"]
    result = EvaluationEngine().evaluate(
        standard,
        _request(
            standard,
            inputs["coal_type"],
            process=inputs["process"],
            electricity=inputs["electricity"],
            raw_coal=inputs["raw_coal"],
        ),
    ).results[0]
    assert result.display_values["process_factor"] == Decimal(case["expected"]["k"])
    assert result.display_values["unadjusted_power_consumption"] == Decimal(case["expected"]["unadjusted"])
    assert result.actual_value == Decimal(case["expected"]["actual"])
    assert result.grade is Grade[case["expected"]["grade"]]


@pytest.mark.parametrize(
    "case",
    GOLDEN["boundary_cases"],
    ids=[case["id"] for case in GOLDEN["boundary_cases"]],
)
def test_golden_all_limit_equality_and_just_over_cases(case, standard):
    result = EvaluationEngine().evaluate(
        standard,
        _request(
            standard,
            case["coal_type"],
            process=case["process"],
            electricity=case["electricity"],
            raw_coal=case["raw_coal"],
        ),
    ).results[0]
    assert result.actual_value == Decimal(case["expected_actual"])
    assert result.grade is Grade[case["expected_grade"]]


@pytest.mark.parametrize(
    "case",
    GOLDEN["anomaly_cases"],
    ids=[case["id"] for case in GOLDEN["anomaly_cases"]],
)
def test_golden_invalid_and_extreme_inputs(case, standard):
    process = case.get("process", _DEFAULT_PROCESS)
    result = EvaluationEngine().evaluate(
        standard,
        _request(
            standard,
            case["coal_type"],
            process=process,
            electricity=case.get("electricity"),
            raw_coal=case.get("raw_coal"),
        ),
    ).results[0]
    assert result.grade is Grade[case["expected_grade"]]
    warning = case.get("warning_contains")
    if warning:
        assert any(warning in item for item in result.warnings)
