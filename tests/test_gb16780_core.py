"""冻结映射驱动的独立期望；不由生产计算器生成Golden。"""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import pytest

from uebench.domain.engine import EvaluationContext, EvaluationEngine, EvaluationValidationError
from uebench.domain.gb16780 import ADOPTION_MARKER, INPUTS, NODE_LABELS
from uebench.domain.models import (
    CementFuelInput, CementLineInput, CementSharedEnergy, EvaluationRequest,
    Grade, InputMode, InputValue, StandardDefinition,
    Expression, ThresholdSet,
)

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = json.loads((ROOT / "tests/golden/gb16780_candidates_v1.json").read_text(encoding="utf-8"))["cases"][0]
IDS = ("cement.comprehensive_energy", "clinker.comprehensive", "clinker.electricity", "clinker.coal", "cement-preparation.electricity")
BASES = (("80", "87", "94"), ("100", "107", "117"), ("48", "57", "61"), ("94", "100", "109"), ("26", "29", "34"))


@pytest.fixture
def standard():
    return StandardDefinition.model_validate_json((ROOT / "data/definitions/gb-16780-2021.json").read_text(encoding="utf-8"))


def golden_request():
    return EvaluationRequest.model_validate(deepcopy(GOLDEN["inputs"]))


def values(result):
    return {item.indicator_id: item for item in result.results}


def put(line, key, value, unit=None):
    line.inputs[key] = InputValue(value=value, unit=unit)


def zero_request():
    request = golden_request()
    line = request.cement_lines[0]
    line.fuels[0].mass_kg = "0"
    for key in list(line.inputs):
        if key not in {"clinker.production_t", "cement.production_t", "cement.clinker_consumption_t", "fuel.standard_coal_heat_kj_per_kgce", "cement.clinker_percent"}:
            put(line, key, "0")
    return request


def evaluate(standard, request):
    return EvaluationEngine().evaluate(standard, request)


def test_golden_identity_and_independent_rational_evidence(standard):
    assert standard.rule_revision == GOLDEN["rule_revision"] == 2
    assert standard.version == GOLDEN["standard_version"] == "2021"
    assert hashlib.sha256((ROOT / "standards/mappings/GB16780-2021/标准映射表_V1.2_修订稿.md").read_bytes()).hexdigest() == GOLDEN["mapping_sha256"]
    assert standard.source_sha256 == "c50768dbca219aeee201a2ef9a79093a2b8e1d384560b31de045aa2cef843a5c"
    # 整数/有理数独立手算，不导入生产公式或阈值求expected。
    heat_credit = Fraction(1229, 10000) * Fraction(10000 - 1000, 1000)
    coal = Fraction(120000, 1000) - heat_credit - Fraction(1000 * (2 + 3), 1000)
    electricity = Fraction(60000 - 1000 - 2000, 1000)
    total_kwh = 30000 + electricity * 1500 + 2000 + 1000 + 2000
    cement = coal * Fraction(75, 100) + Fraction(1000, 2000) + Fraction(1229, 10000) * total_kwh / 2000
    for key, exact in {"E_he": heat_credit, "e_sh": coal, "W_sh": electricity,
                       "E_sh": coal + Fraction(1229, 10000) * electricity,
                       "w_s": total_kwh, "W_s": total_kwh / 2000, "E_s": cement}.items():
        assert Fraction(GOLDEN["expected_intermediates"][key]) == exact
    assert cement != (coal + Fraction(1229, 10000) * electricity) * Fraction(75, 100) + Fraction(1, 2) + Fraction(1229, 10000) * total_kwh / 2000


def test_golden_core_all_five_independent_grades_and_trace(standard):
    result = evaluate(standard, golden_request())
    assert result.calculator_version == GOLDEN["calculator_version"]
    assert result.numeric_profile_id == GOLDEN["numeric_profile_id"]
    assert result.numeric_contract_version == GOLDEN["numeric_contract_version"]
    assert result.numeric_behavior_version == "gb16780-v1.2-full-value-v1"
    assert len(result.results) == 5
    intermediates = {}
    for item in result.results:
        expected = GOLDEN["expected_results"][item.indicator_id]
        assert item.actual_value == Decimal(expected["actual"])
        assert item.grade.value == expected["grade"]
        assert list(item.corrected_thresholds.values()) == [Decimal(v) for v in expected["thresholds"]]
        assert item.line_id == "kiln-1"
        assert item.compliance_result is None
        assert [step.sequence for step in item.calculation_trace] == list(range(1, len(item.calculation_trace) + 1))
        intermediates.update(item.display_values)
        # 依赖trace内每项扣除只发生一次，不在下游整体再扣。
        assert sum(s.label == NODE_LABELS["e_fc"] for s in item.calculation_trace) <= 1
        assert sum(s.label == NODE_LABELS["w_fc"] for s in item.calculation_trace) <= 1
    assert {key: intermediates[key] for key in GOLDEN["expected_intermediates"]} == {
        key: Decimal(value) for key, value in GOLDEN["expected_intermediates"].items()}


def test_definition_metadata_units_and_canonical_contract_are_consistent(standard):
    definitions = {d.key: d for d in standard.products[0].input_definitions}
    assert set(definitions) == set(INPUTS)
    for key, (label, unit, _) in INPUTS.items():
        assert (definitions[key].label, definitions[key].unit) == (label, unit)
        assert definitions[key].modes == [InputMode.DETAIL]
    assert len(standard.products) == 1
    assert {i.id for i in standard.products[0].indicators} == set(IDS)
    assert all(i.compliance_rule is None and i.source_references for i in standard.products[0].indicators)


@pytest.mark.parametrize("index", range(5), ids=IDS)
def test_all_five_threshold_sets_come_from_rule_not_calculator_constants(standard, index):
    standard.products[0].indicators[index].thresholds = ThresholdSet(
        level_1=Expression(op="constant", value="200"),
        level_2=Expression(op="constant", value="201"),
        level_3=Expression(op="constant", value="202"))
    item = values(evaluate(standard, golden_request()))[IDS[index]]
    assert item.grade is Grade.LEVEL_1
    assert list(item.corrected_thresholds.values()) == list(map(Decimal, (200, 201, 202)))


@pytest.mark.parametrize("mode,applicable", [
    ("integrated", set(IDS)), ("partial_purchase", set(IDS)),
    ("clinker_only", set(IDS[1:4])), ("purchased_clinker_grinding", {IDS[4]}),
])
def test_four_mode_applicability(standard, mode, applicable):
    request = zero_request()
    request.cement_lines[0].production_mode = mode
    if mode == "purchased_clinker_grinding":
        request.cement_lines[0].inputs = {"cement.production_t": InputValue(value="1000"),
                                          "cement.preparation_electricity_kwh": InputValue(value="29000")}
        request.cement_lines[0].fuels = []
    result = evaluate(standard, request)
    for item in result.results:
        assert (item.grade is not Grade.NOT_APPLICABLE) == (item.indicator_id in applicable)
        assert item.grade is not Grade.INCOMPLETE, item.warnings
    if mode == "purchased_clinker_grinding":
        assert values(result)[IDS[4]].grade is Grade.LEVEL_2


@pytest.mark.parametrize("altitude,pressure,complete", [
    ("1500", None, True), ("1500", "0", True), ("1500.0001", None, False),
    ("1500.0001", "0", False), ("1500.0001", "60000", True),
])
def test_altitude_strict_boundary_and_pressure_dependency(standard, altitude, pressure, complete):
    request = golden_request()
    line = request.cement_lines[0]
    put(line, "site.altitude_m", altitude)
    if pressure is not None:
        put(line, "site.pressure_pa", pressure, "Pa")
    result = evaluate(standard, request)
    for item in result.results:
        assert item.actual_value == Decimal(GOLDEN["expected_results"][item.indicator_id]["actual"])
        assert (item.grade is not Grade.INCOMPLETE) == (complete or item.indicator_id == IDS[4])
    assert list(values(result)[IDS[4]].corrected_thresholds.values()) == list(map(Decimal, BASES[4]))
    if complete and altitude == "1500":
        assert values(result)[IDS[0]].corrected_thresholds["LEVEL_3"] == Decimal(94)


def test_double_correction_10470_not_10500_and_pressure_end_to_end(standard):
    engine = EvaluationEngine()
    # 独立K fixture仅验证阈值结构，正式DETAIL不接受K/单位实际值输入。
    threshold = standard.products[0].indicators[0].thresholds
    assert threshold.level_3.op == "add"
    base_times_k = threshold.level_3.args[0]
    assert base_times_k.op == "multiply" and base_times_k.args[0].value == "94"
    assert base_times_k.args[1].input_key == "calculated.K"
    limits = engine._evaluate_threshold_set(threshold, EvaluationContext({"calculated.K": Decimal("1.05"), "cement.clinker_percent": Decimal(80)}, {}), [], "fixture")
    assert list(limits.values()) == [Decimal("85.50"), Decimal("92.75"), Decimal("104.70")]
    request = golden_request()
    put(request.cement_lines[0], "site.altitude_m", "2000")
    put(request.cement_lines[0], "site.pressure_pa", "60000")
    put(request.cement_lines[0], "cement.clinker_percent", "80")
    with localcontext() as context:
        context.prec, context.rounding = 28, ROUND_HALF_EVEN
        k = Decimal("1.179") - Decimal("0.211") * (Decimal(60000) / Decimal(101325))
        expected = Decimal(94) * k + Decimal("1.20") * Decimal(5)
    assert values(evaluate(standard, request))[IDS[0]].corrected_thresholds["LEVEL_3"] == expected


@pytest.mark.parametrize("high", [False, True])
def test_named_k_is_calculated_once_per_line_and_saved_for_history(standard, high, monkeypatch):
    engine = EvaluationEngine()
    formula = standard.products[0].indicators[0].display_calculations[0].formula
    original = engine.expressions.evaluate
    calls = []

    def track(expression, *args, **kwargs):
        if expression is formula:
            calls.append(expression)
        return original(expression, *args, **kwargs)

    monkeypatch.setattr(engine.expressions, "evaluate", track)
    request = golden_request()
    if high:
        put(request.cement_lines[0], "site.altitude_m", "2000")
        put(request.cement_lines[0], "site.pressure_pa", "60000")
    result = engine.evaluate(standard, request)
    assert len(calls) == 1
    with localcontext() as context:
        context.prec, context.rounding = 28, ROUND_HALF_EVEN
        expected = Decimal("1.179") - Decimal("0.211") * (Decimal(60000) / Decimal(101325)) if high else Decimal(1)
    for item in result.results[:4]:
        assert item.display_values["K"] == expected
        assert sum(s.label == "海拔修正系数K" for s in item.calculation_trace) == 1
    assert "K" not in result.results[4].display_values
    saved = result.model_validate_json(result.model_dump_json())
    assert all(i.display_values["K"] == expected for i in saved.results[:4])


def test_missing_r2_product_is_readable_rule_error(standard):
    standard.products[0].id = "broken"
    with pytest.raises(EvaluationValidationError, match="缺少配套评价产品"):
        evaluate(standard, golden_request())


@pytest.mark.parametrize("index", range(5), ids=IDS)
@pytest.mark.parametrize("level", range(3))
@pytest.mark.parametrize("delta", ["-0.0000001", "0", "0.0000001"])
@pytest.mark.parametrize("high", [False, True], ids=["baseline", "altitude-and-g"])
def test_all_thresholds_full_value_via_detail(standard, index, level, delta, high):
    request = zero_request()
    line = request.cement_lines[0]
    with localcontext() as context:
        context.prec, context.rounding = 28, ROUND_HALF_EVEN
        limits = list(map(Decimal, BASES[index]))
        if high:
            put(line, "site.altitude_m", "2000")
            put(line, "site.pressure_pa", "101325")  # 精确K=.968；不虚构气压正常范围。
            if index < 4:
                limits[2] *= Decimal("0.968")
            if index == 0:
                put(line, "cement.clinker_percent", "80")
                limits = [v + Decimal(c) * 5 for v, c in zip(limits, ("1.10", "1.15", "1.20"))]
        target = limits[level] + Decimal(delta)
        if index in (1, 3):
            line.fuels[0].mass_kg = target * Decimal(1000)
        elif index == 2:
            put(line, "clinker.electricity_kwh", target * Decimal(1000))
        elif index == 0:
            put(line, "cement.preparation_fuel_kgce", target * Decimal(2000))
        else:
            put(line, "cement.preparation_electricity_kwh", target * Decimal(2000))
    item = values(evaluate(standard, request))[IDS[index]]
    assert item.actual_value == target
    assert list(item.corrected_thresholds.values()) == limits
    expected = next((grade for t, grade in zip(limits, (Grade.LEVEL_1, Grade.LEVEL_2, Grade.LEVEL_3)) if target <= t), Grade.NOT_QUALIFIED)
    assert item.grade is expected


@pytest.mark.parametrize("missing,incomplete", [
    ("fuel", {IDS[0], IDS[1], IDS[3]}),
    ("fuel.standard_coal_heat_kj_per_kgce", {IDS[0], IDS[1], IDS[3]}),
    ("clinker.electricity_kwh", {IDS[0], IDS[1], IDS[2]}),
    ("cement.preparation_electricity_kwh", {IDS[4]}),
    ("cement.clinker_consumption_t", {IDS[0]}),
    ("site.pressure_pa", set(IDS[:4])),
])
def test_missing_only_propagates_through_dependencies(standard, missing, incomplete):
    request = golden_request()
    line = request.cement_lines[0]
    if missing == "fuel":
        line.fuels[0].mass_kg = None
    elif missing == "site.pressure_pa":
        put(line, "site.altitude_m", "2000")
    else:
        line.inputs.pop(missing)
    for item in evaluate(standard, request).results:
        assert (item.grade is Grade.INCOMPLETE) == (item.indicator_id in incomplete)
        if item.indicator_id not in incomplete:
            assert item.actual_value == Decimal(GOLDEN["expected_results"][item.indicator_id]["actual"])


def test_blank_and_explicit_zero_preserve_distinct_trace_and_snapshot(standard):
    blank, zero = zero_request(), zero_request()
    for key in tuple(blank.cement_lines[0].inputs):
        if key.startswith("deduction."):
            blank.cement_lines[0].inputs.pop(key)
    r_blank, r_zero = evaluate(standard, blank), evaluate(standard, zero)
    assert [(i.actual_value, i.grade) for i in r_blank.results] == [(i.actual_value, i.grade) for i in r_zero.results]
    blank_steps = [s for i in r_blank.results for s in i.calculation_trace if s.label == "协同处置燃料折标煤量"]
    assert blank_steps and all(s.value is None and "未填" in s.expression for s in blank_steps)
    assert "deduction.co_processing_fuel_tce" not in blank.cement_lines[0].inputs
    assert zero.cement_lines[0].inputs["deduction.co_processing_fuel_tce"].value == "0"


@pytest.mark.parametrize("key,bad,incomplete", [
    ("deduction.co_processing_fuel_tce", "120", {IDS[0], IDS[1], IDS[3]}),
    ("deduction.co_processing_electricity_kwh", "60001", {IDS[0], IDS[1], IDS[2]}),
    ("heat.own_use_kwh", "10001", {IDS[0], IDS[1], IDS[3]}),
    ("fuel.standard_coal_heat_kj_per_kgce", "0", {IDS[0], IDS[1], IDS[3]}),
    ("cement.production_t", "0", {IDS[0], IDS[4]}),
    ("cement.clinker_percent", "101", {IDS[0]}),
    ("cement.preparation_electricity_kwh", "NaN", {IDS[4]}),
    ("cement.preparation_electricity_kwh", "Infinity", {IDS[4]}),
    ("cement.preparation_electricity_kwh", "-1", {IDS[4]}),
])
def test_invalid_values_block_only_relevant_indicators(standard, key, bad, incomplete):
    request = golden_request()
    put(request.cement_lines[0], key, bad)
    assert {i.indicator_id for i in evaluate(standard, request).results if i.grade is Grade.INCOMPLETE} == incomplete


def test_wrong_unit_does_not_poison_independent_table3(standard):
    request = golden_request()
    put(request.cement_lines[0], "deduction.co_processing_electricity_kwh", "1000", "tce")
    result = values(evaluate(standard, request))
    assert result[IDS[2]].grade is Grade.INCOMPLETE
    assert result[IDS[3]].grade is not Grade.INCOMPLETE
    assert result[IDS[4]].grade is Grade.LEVEL_3


def test_profile_ambient_independence_including_shared_allocation(standard):
    request = golden_request()
    request.cement_shared_energy = [CementSharedEnergy(shared_id="shared", target="cement_auxiliary", line_ids=["kiln-1"], amount=InputValue(value="0.123456789123456789"))]
    baseline = evaluate(standard, request)
    with localcontext() as context:
        context.prec = 6
        context.rounding = "ROUND_DOWN"
        altered = evaluate(standard, request)
    assert [(i.actual_value, i.corrected_thresholds, i.grade, i.display_values) for i in baseline.results] == [
        (i.actual_value, i.corrected_thresholds, i.grade, i.display_values) for i in altered.results]


def multi_request():
    request = zero_request()
    a = request.cement_lines[0]
    a.production_mode = "clinker_only"
    a.fuels[0].mass_kg = "94000"
    put(a, "clinker.electricity_kwh", "48000")
    b = a.model_copy(deep=True, update={"line_id": "kiln-2", "line_name": "二号线"})
    put(b, "clinker.production_t", "3000")
    b.fuels[0].mass_kg = "282000"
    put(b, "clinker.electricity_kwh", "144000")
    request.cement_lines.append(b)
    request.cement_shared_energy = [CementSharedEnergy(shared_id="power", target="clinker_electricity", line_ids=["kiln-1", "kiln-2"], amount=InputValue(value="8000", unit="kWh"))]
    return request


def test_shared_production_allocation_independent_lines_and_no_total_grade(standard):
    result = evaluate(standard, multi_request())
    assert len(result.results) == 10
    for line_id, expected_extra in (("kiln-1", "2000"), ("kiln-2", "6000")):
        item = next(i for i in result.results if i.line_id == line_id and i.indicator_id == IDS[2])
        assert item.actual_value == 50 and item.grade is Grade.LEVEL_2
        assert [s.value for s in item.calculation_trace if s.operation == "allocation"] == [Decimal(expected_extra)]
    assert not hasattr(result, "grade")


def test_shared_allocation_does_not_round_or_patch_last_line(standard):
    request = multi_request()
    for line in request.cement_lines:
        put(line, "clinker.production_t", "1")
        put(line, "clinker.electricity_kwh", "0")
    c = request.cement_lines[0].model_copy(deep=True, update={"line_id": "kiln-3"})
    request.cement_lines.append(c)
    request.cement_shared_energy[0].line_ids.append("kiln-3")
    request.cement_shared_energy[0].amount.value = "1"
    outputs = [i.actual_value for i in evaluate(standard, request).results if i.indicator_id == IDS[2]]
    assert outputs == [Decimal("0.3333333333333333333333333333")] * 3
    assert sum(outputs) != 1


@pytest.mark.parametrize("invalid", ["NaN", "Infinity", "-1", None])
def test_bad_shared_electricity_propagates_only_to_consumers(standard, invalid):
    request = multi_request()
    request.cement_shared_energy[0].amount.value = invalid
    result = evaluate(standard, request)
    for item in result.results:
        assert (item.grade is Grade.INCOMPLETE) == (item.indicator_id in (IDS[1], IDS[2]))


def test_shared_fuel_uses_raw_mass_heat_and_each_lines_qbm(standard):
    request = multi_request()
    for line in request.cement_lines:
        line.fuels = []
    request.cement_shared_energy = [CementSharedEnergy(
        shared_id="fuel", target="clinker_fuel", line_ids=["kiln-1", "kiln-2"],
        fuels=[CementFuelInput(line_id="f", mass_kg="120000", low_calorific_value_kj_per_kg="29307")])]
    result = evaluate(standard, request)
    assert [i.actual_value for i in result.results if i.indicator_id == IDS[3]] == [Decimal(30)] * 2
    request.cement_lines[0].inputs.pop("fuel.standard_coal_heat_kj_per_kgce")
    result = evaluate(standard, request)
    assert next(i for i in result.results if i.line_id == "kiln-1" and i.indicator_id == IDS[3]).grade is Grade.INCOMPLETE
    assert next(i for i in result.results if i.line_id == "kiln-2" and i.indicator_id == IDS[3]).actual_value == 30


def test_missing_shared_participant_output_propagates_to_all_consumers_only(standard):
    request = multi_request()
    request.cement_lines[0].inputs.pop("clinker.production_t")
    result = evaluate(standard, request)
    # 一号线自身三项缺分母；二号线煤耗仍完整，共用电量无法分摊只影响电/能耗。
    for item in result.results:
        if item.line_id == "kiln-2" and item.indicator_id == IDS[3]:
            assert item.actual_value == 94 and item.grade is Grade.LEVEL_1
        elif item.indicator_id in IDS[1:4]:
            assert item.grade is Grade.INCOMPLETE


def test_no_double_deduction_when_raw_inputs_are_already_net(standard):
    gross = golden_request()
    net = golden_request()
    line = net.cement_lines[0]
    # 仅四项已扣净，余热仍按式（3）一次扣除。
    line.fuels[0].mass_kg = "115000"
    put(line, "clinker.electricity_kwh", "57000")
    for key in list(line.inputs):
        if key.startswith("deduction."):
            line.inputs.pop(key)
    assert [(i.actual_value, i.grade) for i in evaluate(standard, gross).results] == [
        (i.actual_value, i.grade) for i in evaluate(standard, net).results]


def test_bad_threshold_order_does_not_change_actual_or_table3(standard):
    request = golden_request()
    put(request.cement_lines[0], "site.altitude_m", "2000")
    put(request.cement_lines[0], "site.pressure_pa", "900000")
    result = values(evaluate(standard, request))
    assert all(result[i].grade is Grade.INCOMPLETE for i in IDS[:4])
    assert all(result[i].actual_value is not None for i in IDS[:4])
    assert result[IDS[4]].grade is Grade.LEVEL_3


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-1", None])
def test_shared_and_local_fuel_use_same_decimal_validation(standard, bad):
    request = multi_request()
    request.cement_shared_energy = [CementSharedEnergy(
        shared_id="fuel", target="clinker_fuel", line_ids=["kiln-1", "kiln-2"],
        fuels=[CementFuelInput(line_id="f", mass_kg=bad, low_calorific_value_kj_per_kg="29307")])]
    for item in evaluate(standard, request).results:
        assert (item.grade is Grade.INCOMPLETE) == (item.indicator_id in (IDS[1], IDS[3]))


def test_raw_float_rejected_even_on_nested_shared_fuel():
    data = deepcopy(GOLDEN["inputs"])
    data["cement_lines"][0]["fuels"][0]["mass_kg"] = 0.1
    with pytest.raises(TypeError, match="浮点数"):
        EvaluationRequest.model_validate(data)
    data = deepcopy(GOLDEN["inputs"])
    data["cement_shared_energy"] = [{"shared_id": "f", "target": "clinker_fuel", "line_ids": ["kiln-1"], "fuels": [{"line_id": "f", "mass_kg": "0", "low_calorific_value_kj_per_kg": 29307.0}]}]
    with pytest.raises(TypeError, match="浮点数"):
        EvaluationRequest.model_validate(data)


@pytest.mark.parametrize("revision,marker", [(1, True), (2, False), (3, True)])
def test_exact_r2_adoption_dispatch_cannot_relabel_history(standard, revision, marker):
    standard.rule_revision = revision
    if not marker:
        standard.corrections.remove(ADOPTION_MARKER)
    with pytest.raises(EvaluationValidationError, match="不匹配"):
        evaluate(standard, golden_request())


def test_historical_r1_still_uses_its_saved_legacy_algorithm():
    old = StandardDefinition.model_validate_json((ROOT / "tests/fixtures/gb16780/r1_legacy.json").read_text(encoding="utf-8"))
    request = EvaluationRequest(evaluation_date="2026-11-11", standard_id=old.id, product_id="cement", input_mode=InputMode.DIRECT, inputs={
        "site.altitude_m": InputValue(value="2000"), "site.pressure_pa": InputValue(value="80000"),
        "cement.clinker_ratio_pct": InputValue(value="76"), "actual.cement_comprehensive_energy": InputValue(value="94"),
    })
    # 历史机器键以其快照为准，不由新规则回填。
    request.inputs[old.products[0].indicators[0].direct_input_key] = InputValue(value="94")
    for definition in old.products[0].indicators[0].input_definitions:
        request.inputs[definition.key].unit = definition.unit
    result = evaluate(old, request)
    with localcontext() as context:
        context.prec, context.rounding = 28, ROUND_HALF_EVEN
        legacy = Decimal("95.20") * (Decimal("1.179") - Decimal("0.211") * (Decimal(80000) / Decimal(101325)))
    assert result.rule_revision == 1 and result.calculator_version != "gb16780-calculator-v1"
    assert result.results[0].corrected_thresholds["LEVEL_3"] == legacy
    assert old.rule_revision == 1 and ADOPTION_MARKER not in old.corrections


def test_direct_and_generic_totals_cannot_bypass_detail(standard):
    request = golden_request()
    request.input_mode = InputMode.DIRECT
    with pytest.raises(EvaluationValidationError, match="仅支持原始明细"):
        evaluate(standard, request)
    request = golden_request()
    request.inputs["actual.E_s"] = InputValue(value="1")
    with pytest.raises(EvaluationValidationError, match="不能混入"):
        evaluate(standard, request)


def test_unknown_or_duplicate_shared_boundaries_fail_request(standard):
    request = multi_request()
    request.cement_shared_energy[0].line_ids = ["kiln-1", "unknown"]
    with pytest.raises(EvaluationValidationError, match="重复或不存在"):
        evaluate(standard, request)
    request = multi_request()
    request.cement_shared_energy *= 2
    with pytest.raises(EvaluationValidationError, match="重复"):
        evaluate(standard, request)
