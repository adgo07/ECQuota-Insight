from __future__ import annotations

import hashlib
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
PROCESSES = {
    "炼焦煤": {
        "跳汰": "1.26",
        "跳汰、浮选联合": "1.00",
        "重介": "1.12",
        "重介、浮选联合": "0.83",
        "重介、跳汰、浮选联合": "0.78",
    },
    "动力煤": {
        "干法选煤": "1.04",
        "跳汰": "0.94",
        "跳汰、浮选联合": "0.80",
        "跳汰、重介联合": "0.85",
        "重介": "0.89",
        "重介、浮选联合": "0.76",
        "重介、跳汰、浮选联合": "0.72",
    },
}
THRESHOLDS = {
    "炼焦煤": [("5.0", Grade.LEVEL_1), ("5.0001", Grade.LEVEL_2), ("7.0", Grade.LEVEL_2), ("7.0001", Grade.LEVEL_3), ("8.5", Grade.LEVEL_3), ("8.5001", Grade.NOT_QUALIFIED)],
    "动力煤": [("2.0", Grade.LEVEL_1), ("2.0001", Grade.LEVEL_2), ("3.0", Grade.LEVEL_2), ("3.0001", Grade.LEVEL_3), ("4.5", Grade.LEVEL_3), ("4.5001", Grade.NOT_QUALIFIED)],
}


@pytest.fixture(scope="module")
def standard() -> StandardDefinition:
    return StandardDefinition.model_validate_json(STANDARD_PATH.read_text(encoding="utf-8"))


def _product(standard: StandardDefinition, coal_type: str):
    return next(product for product in standard.products if product.selection_values["coal_type"] == coal_type)


def _request(
    standard: StandardDefinition,
    coal_type: str,
    *,
    process: str | None = None,
    mode: InputMode = InputMode.DETAIL,
    actual: str | None = None,
    electricity: str | None = "100",
    raw_coal: str | None = "100",
    electricity_unit: str = "kW·h",
    raw_coal_unit: str = "t",
    actual_unit: str = "kW·h/t",
) -> EvaluationRequest:
    product = _product(standard, coal_type)
    process = process or next(iter(PROCESSES[coal_type]))
    inputs = {"washing_process": InputValue(value=process)}
    if mode is InputMode.DIRECT:
        if actual is not None:
            inputs[product.indicators[0].direct_input_key] = InputValue(value=actual, unit=actual_unit)
    else:
        if electricity is not None:
            inputs["electricity_consumption"] = InputValue(value=electricity, unit=electricity_unit)
        if raw_coal is not None:
            inputs["raw_coal_input"] = InputValue(value=raw_coal, unit=raw_coal_unit)
    return EvaluationRequest(
        evaluation_date=max(standard.effective_date, date(2026, 9, 26)),
        standard_id=standard.id,
        product_id=product.id,
        input_mode=mode,
        inputs=inputs,
    )


@pytest.mark.parametrize(
    ("coal_type", "process", "expected_factor"),
    [
        (coal, process, factor)
        for coal, processes in PROCESSES.items()
        for process, factor in processes.items()
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


@pytest.mark.parametrize("enterprise", [None, "现有", "新建", "改扩建", "其他"])
def test_enterprise_status_never_affects_gb29446_level_or_result(standard, enterprise):
    request = _request(standard, "炼焦煤", mode=InputMode.DIRECT, actual="8.0")
    if enterprise is not None:
        request.inputs["enterprise_status"] = InputValue(value=enterprise)
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.LEVEL_3
    assert result.compliance_requirement is None
    assert result.compliance_limit is None
    assert result.compliance_result is None
    assert not any("企业建设属性" in warning for warning in result.warnings)


@pytest.mark.parametrize(("coal_type", "actual", "expected"), [(coal, actual, grade) for coal, values in THRESHOLDS.items() for actual, grade in values])
def test_each_coal_grade_boundaries_include_threshold_and_values_on_both_sides(standard, coal_type, actual, expected):
    request = _request(standard, coal_type, mode=InputMode.DIRECT, actual=actual)
    assert EvaluationEngine().evaluate(standard, request).results[0].grade is expected


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        ("5.0000004", Grade.LEVEL_1),
        ("5.0000005", Grade.LEVEL_2),
        ("8.5000004", Grade.LEVEL_3),
        ("8.5000005", Grade.NOT_QUALIFIED),
    ],
)
def test_gb29446_grade_threshold_comparisons_round_both_values_to_six_places(standard, actual, expected):
    request = _request(standard, "炼焦煤", mode=InputMode.DIRECT, actual=actual)
    result = EvaluationEngine().evaluate(standard, request).results[0]
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


def test_missing_or_false_single_coal_flag_does_not_block_grade(standard):
    request = _request(standard, "炼焦煤", mode=InputMode.DIRECT, actual="9")
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.NOT_QUALIFIED
    assert result.actual_value == Decimal("9")
    assert result.compliance_requirement is None
    assert result.compliance_limit is None
    assert result.compliance_result is None
    assert result.warnings == []

    request.inputs["single_coal_single_process"] = InputValue(value=False)
    result_with_legacy_flag = EvaluationEngine().evaluate(standard, request).results[0]
    assert result_with_legacy_flag.grade is result.grade
    assert result_with_legacy_flag.warnings == []

    request.inputs["single_coal_single_process"] = InputValue(value="无效旧值")
    result_with_invalid_legacy_flag = EvaluationEngine().evaluate(standard, request).results[0]
    assert result_with_invalid_legacy_flag.grade is result.grade
    assert result_with_invalid_legacy_flag.warnings == []


@pytest.mark.parametrize("coal_type,process,factor", [(coal, "重介", PROCESSES[coal]["重介"]) for coal in PROCESSES])
def test_direct_and_detail_inputs_agree_on_grade_and_compliance(standard, coal_type, process, factor):
    detail = _request(
        standard,
        coal_type,
        process=process,
        electricity=str(Decimal("7.0") * Decimal("100") / Decimal(factor)),
        raw_coal="100",
    )
    direct = _request(standard, coal_type, process=process, mode=InputMode.DIRECT, actual="7.0")
    detail_result = EvaluationEngine().evaluate(standard, detail).results[0]
    direct_result = EvaluationEngine().evaluate(standard, direct).results[0]
    assert detail_result.actual_value == direct_result.actual_value == Decimal("7.0")
    assert detail_result.grade is direct_result.grade
    assert detail_result.compliance_result is direct_result.compliance_result is None
    assert detail_result.display_values["unadjusted_power_consumption"] == Decimal("7.0") / Decimal(factor)
    assert direct_result.display_values["unadjusted_power_consumption"] == Decimal("7.0") / Decimal(factor)


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


@pytest.mark.parametrize("coal_type", ["炼焦煤", "动力煤"])
def test_direct_zero_power_consumption_is_incomplete(standard, coal_type):
    request = _request(standard, coal_type, mode=InputMode.DIRECT, actual="0")
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert result.actual_value is None
    assert "必须大于 0" in result.warnings[0]


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


def test_direct_wrong_unit_and_missing_value_are_incomplete(standard):
    request = _request(standard, "动力煤", mode=InputMode.DIRECT, actual="1", actual_unit="kWh/t")
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert "单位应为 kW·h/t" in result.warnings[0]

    request = _request(standard, "动力煤", mode=InputMode.DIRECT, actual=None)
    result = EvaluationEngine().evaluate(standard, request).results[0]
    assert result.grade is Grade.INCOMPLETE
    assert "缺少输入" in result.warnings[0]


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
    request = _request(standard, "炼焦煤", mode=InputMode.DIRECT, actual="5")
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
        packaged_definition = StandardDefinition.model_validate_json(
            package.read("definitions/gb-29446-2019-2019-r2.json")
        )
    assert manifest.standard_count == 1
    assert manifest.rule_count == 2
    assert packaged_definition.rule_revision == 2
    assert packaged_definition.products[0].indicators[0].compliance_rule is not None
    assert packaged_definition.products[0].indicators[0].display_calculations
