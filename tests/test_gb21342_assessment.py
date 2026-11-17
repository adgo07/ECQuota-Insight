"""独立节点/中点及组合手算来源见焦炭判级Golden文档。"""
from dataclasses import fields, replace
from decimal import Decimal as D, DefaultContext, Inexact, ROUND_DOWN, localcontext

import pytest

from uebench.domain.gb21342 import (
    CokeAssessmentInput, CokeEnergyInput, CokeCalculationError,
    ExternalServicesStatus as External, assess_coke,
)
from uebench.domain.models import Grade
from uebench.application.gb21342 import preview_coke


def request(actual="110", **changes):
    energy = CokeEnergyInput(actual,"0","0","0","0","1",External.INCLUDED_OR_NOT_EXTERNAL)
    values = dict(energy=energy,oven_type="top_charging",heating_fuel="coke_oven_gas",
                  dry_volatile_pct="23",total_moisture_pct="10",oven_age_years="15",
                  quenching_method="dry",conventional_oven=True)
    values.update(changes)
    return CokeAssessmentInput(**values)


TOP = [
    ("21","101.70","126.70"),("21.5","103.75","128.75"),("22","105.80","130.80"),
    ("22.5","107.90","132.90"),("23","110","135"),("23.5","112.125","137.125"),
    ("24","114.25","139.25"),("24.5","116.40","141.40"),("25","118.55","143.55"),
    ("25.5","119.775","144.775"),("26","121","146"),("26.5","122.54","147.54"),
    ("27","124.08","149.08"),("27.5","126.395","151.395"),("28","128.71","153.71"),
]
STAMP = [
    ("25","115","140"),("25.5","116.60","141.60"),("26","118.20","143.20"),
    ("26.5","119.82","144.82"),("27","121.44","146.44"),("27.5","123.92","148.92"),
    ("28","126.40","151.40"),("28.5","128.025","153.025"),("29","129.65","154.65"),
    ("29.5","131.29","156.29"),("30","132.93","157.93"),("30.5","134.58","159.58"),
    ("31","136.23","161.23"),("31.5","137.865","162.865"),("32","139.50","164.50"),
]


@pytest.mark.parametrize("oven,node,l1,l3", [("top_charging",*row) for row in TOP]+[("stamp_charging",*row) for row in STAMP])
@pytest.mark.parametrize("boundary,offset,grade", [(0,"-0.0000001",Grade.LEVEL_1),(0,"0",Grade.LEVEL_1),(0,"0.0000001",Grade.LEVEL_3),(1,"-0.0000001",Grade.LEVEL_3),(1,"0",Grade.LEVEL_3),(1,"0.0000001",Grade.NOT_QUALIFIED)])
def test_all_nodes_midpoints_and_exact_boundaries(oven,node,l1,l3,boundary,offset,grade):
    actual = (D(l1),D(l3))[boundary]+D(offset)
    result = assess_coke(request(actual,oven_type=oven,dry_volatile_pct=node,total_moisture_pct="10" if oven=="top_charging" else "10.5"))
    assert [level.threshold for level in result.levels] == [D(l1),D(l1),D(l3)]
    assert result.grade is grade
    assert [level.matched for level in result.levels] == [actual<=D(l1),actual<=D(l1),actual<=D(l3)]


@pytest.mark.parametrize("actual,changes,limits,grade", [
    ("125",dict(heating_fuel="mixed_gas",mixed_gas_ratio="0.5",dry_volatile_pct="24.5",total_moisture_pct="11",quenching_method="wet",oven_age_years="20"),("126.57","124.07","198.03"),Grade.LEVEL_1),
    ("136",dict(oven_type="stamp_charging",heating_fuel="mixed_gas",mixed_gas_ratio="1",dry_volatile_pct="26",total_moisture_pct="11.5",quenching_method="wet",oven_age_years="26"),("139.41","133.91","210.87"),Grade.LEVEL_1),
    ("140",dict(oven_type="stamp_charging",heating_fuel="mixed_gas",mixed_gas_ratio="1",dry_volatile_pct="26",total_moisture_pct="11.5",quenching_method="wet",oven_age_years="26"),("139.41","133.91","210.87"),Grade.LEVEL_3),
    ("111",dict(oven_age_years="20"),("112.5","110","137.5"),Grade.LEVEL_1),
    ("110",dict(oven_age_years="20"),("112.5","110","137.5"),Grade.LEVEL_1),
    ("113",dict(oven_age_years="20"),("112.5","110","137.5"),Grade.LEVEL_3),
    ("138",dict(oven_age_years="20"),("112.5","110","137.5"),Grade.NOT_QUALIFIED),
    ("111",dict(oven_age_years="15"),("110","110","135"),Grade.LEVEL_3),
    ("111",dict(oven_age_years="15.0000001"),("112.5","110","137.5"),Grade.LEVEL_1),
    ("114",dict(oven_age_years="25"),("112.5","110","137.5"),Grade.LEVEL_3),
    ("114",dict(oven_age_years="25.0000001"),("115.5","110","140.5"),Grade.LEVEL_1),
    ("106.33",dict(total_moisture_pct="9"),("106.33","106.33","131.33"),Grade.LEVEL_1),
    ("113.67",dict(total_moisture_pct="11"),("113.67","113.67","138.67"),Grade.LEVEL_1),
])
def test_independent_combinations(actual,changes,limits,grade):
    result = assess_coke(request(actual,**changes))
    assert tuple(level.threshold for level in result.levels)==tuple(map(D,limits))
    assert result.grade is grade


@pytest.mark.parametrize("method", [None,"mixed","unknown"])
def test_lower_unknown_does_not_block_known_highest(method):
    result = assess_coke(request("111",oven_age_years="20",quenching_method=method))
    assert result.grade is Grade.LEVEL_1
    assert result.levels[2].threshold is None
    assert [level.matched for level in result.levels]==[True,False,None]
    assert assess_coke(request("113",oven_age_years="20",quenching_method=method)).grade is Grade.INCOMPLETE


@pytest.mark.parametrize("changes", [dict(oven_age_years=None),dict(dry_volatile_pct=None),dict(total_moisture_pct=None),dict(oven_type=None),dict(heating_fuel=None),dict(heating_fuel="other"),dict(heating_fuel="mixed_gas"),dict(conventional_oven=None)])
def test_missing_highest_is_not_skipped(changes):
    result=assess_coke(request("100",**changes))
    assert result.energy.actual_energy_kgce_per_t==100
    assert result.grade is Grade.INCOMPLETE


def test_optional_fields_can_be_omitted_without_forcing_adapter_fillers():
    result=assess_coke(CokeAssessmentInput(request().energy))
    assert result.grade is Grade.INCOMPLETE
    assert result.energy.actual_energy_kgce_per_t==110
    assert all(level.undetermined_reasons for level in result.levels)


@pytest.mark.parametrize("oven,volatile", [("top_charging","20.9999999"),("top_charging","28.0000001"),("stamp_charging","24.9999999"),("stamp_charging","32.0000001")])
def test_outside_volatile_is_unknown_not_clamped(oven,volatile):
    result=assess_coke(request("1",oven_type=oven,dry_volatile_pct=volatile))
    assert result.grade is Grade.INCOMPLETE
    assert all(level.threshold is None for level in result.levels)
    assert any("超出表列" in reason for level in result.levels for reason in level.undetermined_reasons)


def test_external_partial_and_not_applicable_do_not_create_grade():
    supplied=request("150")
    partial=replace(supplied,energy=replace(supplied.energy,external_services_status=External.PARTIAL_OR_UNKNOWN))
    result=assess_coke(partial)
    assert result.energy.actual_energy_kgce_per_t==150
    assert all(level.threshold is not None and level.matched is None for level in result.levels)
    assert all(any("外属调整未定" in reason for reason in level.undetermined_reasons) for level in result.levels)
    assert result.grade is Grade.INCOMPLETE
    assert assess_coke(replace(supplied,conventional_oven=False)).grade is Grade.NOT_APPLICABLE
    triggered=assess_coke(replace(request("100"),energy=replace(request("100").energy,external_services_status=External.BOTH_EXTERNAL_EXCLUDED)))
    assert triggered.energy.evaluation_energy_kgce_per_t==126
    assert triggered.grade is Grade.LEVEL_3


@pytest.mark.parametrize("key", ["dry_volatile_pct","total_moisture_pct","oven_age_years","mixed_gas_ratio"])
@pytest.mark.parametrize("bad", [True,0.0,"NaN","Infinity",D("sNaN"),"abc",object()])
def test_strict_correction_numbers(key,bad):
    with pytest.raises(CokeCalculationError):
        request(**{key:bad})


@pytest.mark.parametrize("changes", [dict(dry_volatile_pct="101"),dict(total_moisture_pct="-1"),dict(oven_age_years="-1"),dict(mixed_gas_ratio="1.1"),dict(oven_type="other"),dict(heating_fuel=False),dict(quenching_method=[]),dict(conventional_oven=1)])
def test_invalid_ranges_and_enums(changes):
    with pytest.raises(CokeCalculationError):
        request(**changes)


@pytest.mark.parametrize("oven,ratio,expected", [("top_charging","0","110"),("top_charging","1","118"),("stamp_charging","0","115"),("stamp_charging","1","127")])
def test_mixed_gas_time_ratio_endpoints(oven,ratio,expected):
    result=assess_coke(request(expected,oven_type=oven,heating_fuel="mixed_gas",mixed_gas_ratio=ratio,dry_volatile_pct="23" if oven=="top_charging" else "25",total_moisture_pct="10" if oven=="top_charging" else "10.5"))
    assert result.levels[0].threshold==D(expected)
    assert result.grade is Grade.LEVEL_1


def test_context_trace_identity_and_application():
    supplied=request("125",heating_fuel="mixed_gas",mixed_gas_ratio="0.5",dry_volatile_pct="24.5",total_moisture_pct="11",quenching_method="wet",oven_age_years="20")
    expected=assess_coke(supplied)
    original=DefaultContext.copy()
    try:
        DefaultContext.prec=3
        DefaultContext.traps[Inexact]=True
        with localcontext() as ambient:
            ambient.prec=4
            ambient.rounding=ROUND_DOWN
            ambient.Emax,ambient.Emin=2,-2
            ambient.traps[Inexact]=True
            assert preview_coke(supplied)==expected
    finally:
        DefaultContext.prec=original.prec
        DefaultContext.traps=original.traps
    assert expected.numeric_profile_id==expected.energy.numeric_profile_id
    assert expected.numeric_contract_version=="v1"
    assert "assessment" in expected.calculator_version
    assert [s.sequence for s in expected.calculation_trace]==list(range(1,len(expected.calculation_trace)+1))
    assert len([s for s in expected.calculation_trace if "级比较" in s.label])==3
    assert {"oven_type","heating_fuel","mixed_gas_ratio","dry_volatile_pct","total_moisture_pct","oven_age_years","quenching_method","conventional_oven"} <= {s.expression for s in expected.calculation_trace}
    assert set(dict(expected.levels[0].corrections))=={"F","V","M","A"}
    assert set(dict(expected.levels[1].corrections))=={"F","V","M"}
    assert set(dict(expected.levels[2].corrections))=={"F","V","M","A","Q"}
    assert not any("企业" in field.name or "enterprise" in field.name for field in fields(supplied))
    assert not any("软件解释" in str(s.value) or "准入" in str(s.value) for s in expected.calculation_trace)


def test_facade_preview_is_read_only_thin_application_entry():
    from uebench.application.facade import ApplicationFacade
    class Forbidden:
        def __getattr__(self,name):
            raise AssertionError("预览不得访问生产规则或存储")
    facade=ApplicationFacade(standards=Forbidden(),evaluations=Forbidden(),evaluation_service=Forbidden())
    assert facade.preview_coke(request())==preview_coke(request())


def test_new_preview_does_not_open_formal_scope():
    from uebench.application.evaluation_support import supports_formal_evaluation
    assert not supports_formal_evaluation("gb-21342-2025")
