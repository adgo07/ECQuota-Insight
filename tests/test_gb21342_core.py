"""预期来自docs/golden/GB21342_CORE_INDEPENDENT_GOLDEN_CANDIDATES_20261112.md。"""
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, DefaultContext, Inexact, InvalidOperation, ROUND_UP, localcontext

import pytest

from uebench.domain.gb21342 import (
    CokeCalculationError, CokeEnergyInput, ExternalServicesStatus, calculate_energy,
    LABELS, PARTIAL_ISSUE,
)
from uebench.domain.numeric import ECQUOTA_DECIMAL_FULL_VALUE_V1

N, T, U = tuple(ExternalServicesStatus)
BASE = ("100000", "20000", "80000", "20000", "5000")


def supplied(amounts=BASE, production="100", status=N):
    return CokeEnergyInput(*amounts, production, status)


@pytest.mark.parametrize("amounts,production,status,net,actual,evaluation", [
    (BASE,"100",N,"15000","150","150"),
    (BASE,"100",T,"15000","150","176"),
    (BASE,"100",U,"15000","150",None),
    (("100","20","80","30","10"),"5",N,"0","0","0"),
    (("100","20","80","30","10"),"5",T,"0","0","26"),
    (("100","20","100","30","10"),"4",N,"-20","-5","-5"),
    (("100","20","100","30","10"),"4",T,"-20","-5","21"),
    (("1","0","0","0","0"),"3",N,"1","0.3333333333333333333333333333","0.3333333333333333333333333333"),
    (("1","0","0","0","0"),"3",T,"1","0.3333333333333333333333333333","26.33333333333333333333333333"),
    (("2","0","0","0","0"),"3",T,"2","0.6666666666666666666666666667","26.66666666666666666666666667"),
    (("0.0000001","0","0","0","0"),"1",N,"0.0000001","0.0000001","0.0000001"),
    (("5E400","3E400","2E400","1E400","1E400"),"2E399",T,"4E400","20","46"),
    (("10","-2","3","0","0"),"1",N,"5","5","5"),
    (("1","0","0","0","0"),"1",N,"1","1","1"),
    (("0","0","0","0","0"),"1",U,"0","0",None),
])
def test_independent_golden(amounts, production, status, net, actual, evaluation):
    result = calculate_energy(supplied(amounts, production, status))
    assert result.net_energy_kgce == Decimal(net)
    assert result.actual_energy_kgce_per_t == Decimal(actual)
    assert result.evaluation_energy_kgce_per_t == (Decimal(evaluation) if evaluation is not None else None)
    assert result.adjustment_kgce_per_t == (None if status is U else Decimal(26 if status is T else 0))
    assert result.adjustment_status == ("UNDETERMINED" if status is U else "DETERMINED")
    if Decimal(actual) < 0 or any(Decimal(value) < 0 for value in amounts):
        assert any("核查" in warning for warning in result.warnings)


@pytest.mark.parametrize("key", list(LABELS))
@pytest.mark.parametrize("bad", [None, True, False, 0.0, 1.25, "NaN", "sNaN", "Infinity", "-Infinity", Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"), "", "  ", "abc", "1 tce", {"value":1,"unit":"tce"}, object()])
def test_strict_input_rejection_each_field(key, bad):
    values = dict(zip(LABELS, (*BASE, "100")))
    values[key] = bad
    with pytest.raises(CokeCalculationError):
        CokeEnergyInput(**values, external_services_status=N)


@pytest.mark.parametrize("key", list(LABELS))
def test_required_field_is_not_zero(key):
    values = dict(zip(LABELS, (*BASE, "100")))
    del values[key]
    with pytest.raises(TypeError):
        CokeEnergyInput(**values, external_services_status=N)


@pytest.mark.parametrize("production", ["0", "-1"])
def test_positive_production(production):
    with pytest.raises(CokeCalculationError, match="产量必须大于0"):
        supplied(production=production)


@pytest.mark.parametrize("status", [None, "", "unknown", False, 0, object()])
def test_explicit_external_status(status):
    with pytest.raises(CokeCalculationError):
        supplied(status=status)


def test_integer_decimal_text_equivalence_and_immutability():
    a = calculate_energy(supplied())
    b = calculate_energy(supplied(tuple(int(value) for value in BASE), 100))
    c = calculate_energy(supplied(tuple(Decimal(value) for value in BASE), Decimal(100)))
    assert a == b == c
    with pytest.raises(FrozenInstanceError):
        a.inputs.dry_coke_output_t = Decimal(1)


def test_trace_identity_partial_and_no_call_state_leak():
    triggered = calculate_energy(supplied(status=T))
    partial = calculate_energy(supplied(status=U))
    normal = calculate_energy(supplied())
    assert triggered.evaluation_energy_kgce_per_t == 176
    assert partial.evaluation_energy_kgce_per_t is None
    assert normal.evaluation_energy_kgce_per_t == 150
    assert normal.warnings == ()
    assert partial.numeric_profile == ECQUOTA_DECIMAL_FULL_VALUE_V1
    assert partial.numeric_profile_id == partial.numeric_profile.numeric_profile_id
    assert partial.numeric_contract_version == "v1"
    assert "unpublished" in partial.rule_revision
    assert "unpublished" in partial.calculator_version
    assert len(partial.source_sha256) == 64
    steps = partial.calculation_trace
    assert [s.sequence for s in steps] == list(range(1, len(steps)+1))
    assert [s.value for s in steps[:6]] == [Decimal(v) for v in (*BASE,"100")]
    assert [s.unit for s in steps[:6]] == ["kgce"]*5 + ["t"]
    assert steps[6].value == 15000 and steps[7].value == 150
    assert steps[-1].expression == PARTIAL_ISSUE


def test_ambient_context_independence_and_no_pollution():
    data = supplied(("2","0","0","0","0"),"3",T)
    expected = calculate_energy(data)
    with localcontext() as ambient:
        ambient.prec = 6
        ambient.rounding = ROUND_UP
        ambient.Emax, ambient.Emin = 5, -5
        ambient.traps[Inexact] = True
        ambient.flags[Inexact] = True
        before = (ambient.copy(), dict(ambient.flags))
        assert calculate_energy(data) == expected
        large = calculate_energy(supplied(("5E400","3E400","2E400","1E400","1E400"),"2E399",T))
        assert large.evaluation_energy_kgce_per_t == 46
        assert ambient.prec == before[0].prec and ambient.rounding == before[0].rounding
        assert ambient.Emax == 5 and ambient.Emin == -5 and ambient.traps[Inexact]
        assert dict(ambient.flags) == before[1]


@pytest.mark.parametrize("amount,production", [("9E999999","0.1"),("1E-999999","1E999999"),("1E-1000027","1")])
def test_arithmetic_range_errors_do_not_become_infinity_or_zero(amount, production):
    with pytest.raises(CokeCalculationError, match="有效范围"):
        calculate_energy(supplied((amount,"0","0","0","0"),production))


def test_unsupported_profile_or_input_cannot_silently_fallback():
    with pytest.raises(CokeCalculationError, match="数值配置"):
        calculate_energy(supplied(), profile=replace(ECQUOTA_DECIMAL_FULL_VALUE_V1, working_precision=6))
    with pytest.raises(CokeCalculationError):
        calculate_energy(supplied(), profile=None)
    with pytest.raises(CokeCalculationError):
        calculate_energy({})


def test_default_context_cannot_change_declared_scope():
    data = supplied(("2","0","0","0","0"),"3",T)
    expected = calculate_energy(data)
    original = DefaultContext.copy()
    try:
        DefaultContext.prec = 3
        DefaultContext.Emax, DefaultContext.Emin = 2, -2
        DefaultContext.rounding = ROUND_UP
        DefaultContext.clamp = 1
        DefaultContext.traps[Inexact] = True
        DefaultContext.flags[Inexact] = True
        assert calculate_energy(data) == expected
        assert calculate_energy(supplied(("5E400","3E400","2E400","1E400","1E400"),"2E399",T)).evaluation_energy_kgce_per_t == 46
        assert DefaultContext.Emax == 2 and DefaultContext.flags[Inexact]
    finally:
        for attr in ("prec", "Emax", "Emin", "rounding", "capitals", "clamp"):
            setattr(DefaultContext, attr, getattr(original, attr))
        DefaultContext.traps = original.traps
        DefaultContext.flags = original.flags


def test_invalid_lexical_input_does_not_pollute_caller_flags():
    with localcontext() as ambient:
        ambient.clear_flags()
        ambient.traps[InvalidOperation] = False
        before = dict(ambient.flags)
        with pytest.raises(CokeCalculationError):
            supplied(("abc", "0", "0", "0", "0"))
        assert dict(ambient.flags) == before


@pytest.mark.parametrize("zero", ["0E-1000027", "-0E-1000027", "0E999999999"])
def test_true_zero_exponent_is_not_underflow(zero):
    result = calculate_energy(supplied((zero,"0","0","0","0"),"1",T))
    assert result.actual_energy_kgce_per_t == 0
    assert result.evaluation_energy_kgce_per_t == 26
    assert result.calculation_trace[0].value.as_tuple() == Decimal(zero).as_tuple()


@pytest.mark.parametrize("production", ["1E1000027", "1E-1000027"])
def test_true_zero_quotient_does_not_require_exponent_clamping(production):
    result = calculate_energy(supplied(("0",)*5,production,T))
    assert result.actual_energy_kgce_per_t == 0
    assert result.evaluation_energy_kgce_per_t == 26
    assert result.calculation_trace[5].value == Decimal(production)
