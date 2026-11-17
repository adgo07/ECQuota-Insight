from dataclasses import replace
from decimal import Decimal as D, localcontext, ROUND_DOWN
import pytest

from uebench.domain.coke_flows import CokeFlow, aggregate_flows, normalize_energy, COMPONENTS, REFERENCES
from uebench.domain.coke_reference import SATURATED_STEAM, SUPERHEATED_STEAM
from uebench.domain.gb21342 import CokeCalculationError


def flow(**changes):
    args = dict(flow_id="physical-1", component=COMPONENTS[1], energy_id="electricity", quantity="1000", unit="kWh")
    args.update(changes)
    return CokeFlow(**args)


def test_independent_energy_golden_and_measured_priority():
    r = aggregate_flows([flow(), flow(flow_id="n-main", energy_id="nitrogen_main", unit="m³"),
                         flow(flow_id="n-by", energy_id="nitrogen_byproduct", unit="m³")])
    assert [row.energy_kgce for row in r.rows] == [D("122.9"), D("671.4"), D("400")]
    assert r.totals[COMPONENTS[1]] == D("1194.3")
    assert r.totals[COMPONENTS[0]] is None
    assert aggregate_flows([flow(measured_coefficient="0.2", coefficient_unit="kgce/kWh", source="报告期实测")]).rows[0].energy_kgce == D(200)
    assert aggregate_flows([flow(energy_id="dry_clean_coal", quantity="1", unit="t", measured_coefficient="99")]).rows[0].energy_kgce == D("1014.3")


@pytest.mark.parametrize("table,kind", [(SATURATED_STEAM,"saturated_steam"),(SUPERHEATED_STEAM,"superheated_steam")])
def test_every_verified_steam_node(table, kind):
    for p,t,h,c in table:
        result = aggregate_flows([flow(energy_id=kind,quantity="1",unit="t",pressure_mpa=p,temperature_c=t)])
        assert result.rows[0].energy_kgce == D(c)*1000
    assert len(SATURATED_STEAM) == 20 and len(SUPERHEATED_STEAM) == 84


def test_unknown_steam_and_gas_are_partial_not_zero():
    assert aggregate_flows([flow(energy_id="saturated_steam", pressure_mpa="0.15",temperature_c="110",unit="kg")]).rows[0].energy_kgce is None
    assert aggregate_flows([flow(energy_id="驰放气")]).rows[0].energy_kgce is None
    with pytest.raises(CokeCalculationError,match="绝对压力"):
        aggregate_flows([flow(energy_id="saturated_steam", pressure_basis="gauge")])


@pytest.mark.parametrize("value", [0.1, True, "NaN", "Infinity"])
def test_reject_inexact_nonfinite(value):
    with pytest.raises(CokeCalculationError):
        aggregate_flows([flow(quantity=value)])


def test_exclusivity_missing_zero_duplicate_and_context():
    with pytest.raises(CokeCalculationError,match="重复"):
        aggregate_flows([flow(),flow()])
    with pytest.raises(CokeCalculationError,match="冲突"):
        aggregate_flows([flow()],zero_components=[COMPONENTS[1]])
    r = aggregate_flows([],zero_components=COMPONENTS)
    assert r.energy_input("1","included_or_not_external").raw_coal_energy_kgce == 0
    with pytest.raises(CokeCalculationError,match="待确定"):
        aggregate_flows([]).energy_input("1","included_or_not_external")
    with pytest.raises(CokeCalculationError,match="同时生效"):
        normalize_energy(mode="flows", totals={},flows=[],dry_coke_output_t="1", external_services_status="partial_or_unknown")
    with localcontext() as ctx:
        ctx.prec=3
        ctx.rounding=ROUND_DOWN
        assert aggregate_flows([flow(quantity="1234.56789")]).rows[0].energy_kgce == D("151.728393681")


@pytest.fixture
def page():
    from PySide6.QtWidgets import QApplication
    from uebench.ui.coke_preview import CokePreviewPage
    app = QApplication.instance() or QApplication([])
    page = CokePreviewPage()
    yield page
    page.close()


def populate(page):
    values = dict(raw_coal_energy_kgce="111",processing_energy_kgce="0",coke_energy_kgce="0",
                  chemical_products_energy_kgce="0",recovered_heat_energy_kgce="0",dry_coke_output_t="1",
                  dry_volatile_pct="23",total_moisture_pct="10",oven_age_years="20")
    for key,value in values.items():
        page.fields[key].setText(value)
    for key,value in dict(oven_type="top_charging", heating_fuel="coke_oven_gas", conventional_oven=True,
                          quenching_method="mixed",purification=False,wastewater=False).items():
        page.choices[key].setCurrentIndex(page.choices[key].findData(value))


def test_preview_partial_stale_and_literal_text(page):
    populate(page)
    page.run_preview()
    assert page.result.grade.value == "LEVEL_1"
    assert page.result.levels[2].threshold is None
    assert "待确定" in page.output.toPlainText()
    assert "最高满足级别" not in page.details.toPlainText()
    page.fields["raw_coal_energy_kgce"].setText("111.000000000000000000001")
    assert page.result is None and "过期" in page.notice.text()
    page.run_preview()
    assert str(page.result.inputs.energy.raw_coal_energy_kgce) == "111.000000000000000000001"
    page.fields["dry_coke_output_t"].clear()
    page.run_preview()
    assert page.result is None and "干全焦产量" in page.notice.text()
    assert page.calculate.isEnabled()


def test_percent_and_not_applicable(page):
    populate(page)
    page.choices["heating_fuel"].setCurrentIndex(page.choices["heating_fuel"].findData("mixed_gas"))
    page.fields["mixed_gas_percent"].setText("50")
    assert page.collect().mixed_gas_ratio == D("0.5")
    page.choices["conventional_oven"].setCurrentIndex(page.choices["conventional_oven"].findData(False))
    page.run_preview()
    assert page.result.grade.value == "NOT_APPLICABLE"
