"""依据原文常数独立给定的热值/焓Golden及界面/保存报告验证。"""
from dataclasses import replace
from datetime import date
from decimal import Decimal as D, localcontext, ROUND_DOWN
from pathlib import Path
from copy import deepcopy
import pytest
from uebench.domain.coke_flows import CokeFlow, aggregate_flows, COMPONENTS, verified_flow_reference_payload
from uebench.domain.gb21342 import CokeCalculationError, CokeAssessmentInput


def fuel(**changes):
    data=dict(flow_id="fuel-1",component=COMPONENTS[1],energy_id="natural_gas",quantity="1000",unit="m³",
              measured_calorific_value="14653.8",calorific_value_unit="kJ/m³",source="报告期实测低位热值")
    data.update(changes)
    return CokeFlow(**data)


@pytest.mark.parametrize("q,quantity,expected",[("29307.6","1","1"),("14653.8","1000","500"),("0","1000","0")])
def test_independent_q_golden(q,quantity,expected):
    row=aggregate_flows([fuel(measured_calorific_value=q,quantity=quantity)]).rows[0]
    assert row.energy_kgce==D(expected)
    assert row.conversion_trace["denominator_kj_per_kgce"]=="29307.6"
    assert q in row.conversion_trace["expression"]
    assert "收到基" in row.conversion_trace["method"]


def test_independent_h_golden_reference_distinction_and_context():
    h=fuel(energy_id="saturated_steam",quantity="1",unit="t",measured_calorific_value=None,calorific_value_unit=None,
           measured_enthalpy_kj_per_kg="2930.76",pressure_basis="gauge")
    with localcontext() as ctx:
        ctx.prec=3;ctx.rounding=ROUND_DOWN
        assert aggregate_flows([h]).rows[0].energy_kgce==D("100")
    ref=replace(h,measured_enthalpy_kj_per_kg=None,pressure_basis="absolute",pressure_mpa="0.1",temperature_c="99.634")
    assert aggregate_flows([ref]).rows[0].energy_kgce==D("91.3")
    measured=aggregate_flows([replace(h,measured_enthalpy_kj_per_kg="2675.14")]).rows[0]
    assert measured.coefficient != D("0.0913")
    assert measured.conversion_trace["expression"]=="2675.14 / 29307.6"


@pytest.mark.parametrize("changes,match",[
    ({"measured_coefficient":"0.2","coefficient_unit":"kgce/m³"},"同时生效"),
    ({"measured_enthalpy_kj_per_kg":"100"},"同时生效"),
    ({"energy_id":"electricity","unit":"kWh"},"燃料能源"),
    ({"energy_id":"fresh_water","unit":"t"},"燃料能源"),
    ({"calorific_value_unit":"MJ/kg"},"热值单位"),
    ({"unit":"kg"},"不能转换"),
    ({"energy_id":"dry_clean_coal","unit":"kg"},"固定系数"),
    ({"measured_calorific_value":None,"measured_enthalpy_kj_per_kg":"10"},"只适用于蒸汽"),
])
def test_reject_conflicting_channel_wrong_category_and_dimensions(changes,match):
    with pytest.raises(CokeCalculationError,match=match):aggregate_flows([fuel(**changes)])


def test_missing_source_warning_and_parameter_tampering():
    result=aggregate_flows([fuel(source="")]);assert result.rows[0].energy_kgce==500
    assert any("来源待补" in x for x in result.warnings)
    params=deepcopy(verified_flow_reference_payload());params["standard_coal_heat_kj_per_kgce"]="29271.2"
    with pytest.raises(CokeCalculationError,match="参数"):
        aggregate_flows([fuel()],flow_parameters=params)


def test_form_q_h_dimensions_and_modified_result_stale():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from uebench.ui.coke_preview import CokePreviewPage
    app=QApplication.instance() or QApplication([]);page=CokePreviewPage();form=page.flows_form
    try:
        form.add();energy=form.table.cellWidget(0,1)
        assert not form.table.item(0,11).flags() & Qt.ItemIsEnabled
        energy.setCurrentIndex(energy.findData("other_fuel"))
        assert form.table.item(0,11).flags() & Qt.ItemIsEnabled
        assert not form.table.item(0,13).flags() & Qt.ItemIsEnabled
        form.table.item(0,11).setText("14653.8");units=form.table.cellWidget(0,12);units.setCurrentIndex(units.findData("kJ/kg"))
        form.table.item(0,2).setText("1000")
        assert form.collect()[0][0].measured_calorific_value=="14653.8"
        energy.setCurrentIndex(energy.findData("superheated_steam"))
        assert form.table.item(0,11).text()=="" and not units.isEnabled()
        assert form.table.item(0,13).flags() & Qt.ItemIsEnabled
        energy.setCurrentIndex(energy.findData("electricity"))
        assert not form.table.item(0,13).flags() & Qt.ItemIsEnabled
    finally:page.close()


def test_saved_report_retains_q_h_without_recalculation(tmp_path,monkeypatch):
    from uebench.application.coke_records import candidate_snapshot,input_payload,calculate_record
    from uebench.application import coke_records
    from uebench.domain.models import StandardDefinition,EvaluationRequest,InputMode
    from uebench.bootstrap import create_context
    from docx import Document
    root=Path(__file__).resolve().parents[1]
    snapshot=candidate_snapshot(StandardDefinition.model_validate_json((root/'data/definitions/gb-21342-2025.json').read_text(encoding='utf-8')))
    flows=aggregate_flows([fuel(quantity="200")],zero_components=[k for k in COMPONENTS if k != COMPONENTS[1]])
    assessment=CokeAssessmentInput(flows.energy_input("1","included_or_not_external"),oven_type="top_charging",heating_fuel="coke_oven_gas",dry_volatile_pct="23",total_moisture_pct="10",oven_age_years="20",quenching_method="dry",conventional_oven=True)
    request=EvaluationRequest(evaluation_date=date(2026,11,18),standard_id=snapshot.id,product_id="top-charging-coke-oven",input_mode=InputMode.DETAIL,inputs={},coke_payload=input_payload(assessment,flow_result=flows),notes="2026年11月（合成数据）")
    result=calculate_record(request,snapshot);context=create_context(tmp_path/'isolated',enforce_standard_library_readiness=False)
    try:
        context.evaluations.save(request,result,snapshot)
        def fail(*args, **kwargs):
            pytest.fail("历史不得调用当前判级、能流归集或公共Engine")
        monkeypatch.setattr(coke_records, 'preview_coke', fail)
        monkeypatch.setattr(coke_records, 'assess_coke', fail)
        monkeypatch.setattr('uebench.domain.coke_flows.aggregate_flows', fail)
        monkeypatch.setattr('uebench.domain.engine.EvaluationEngine.evaluate', fail)
        from uebench.domain.coke_flows import REFERENCES
        monkeypatch.setitem(REFERENCES, 'natural_gas', ('未来改名气体', 'm³', '999', 'future'))
        view=context.application.get_report_view(result.evaluation_id)
        assert '14653.8' in str(view) and '29307.6' in str(view) and '收到基低位热值' in str(view)
        assert '天然气' in str(view) and '未来改名气体' not in str(view)
        path=tmp_path/'q.docx';context.application.export_word_report(result.evaluation_id,path)
        doc=Document(path);content='\n'.join(c.text for t in doc.tables for r in t.rows for c in r.cells)
        assert '14653.8' in content and '29307.6' in content and '报告期实测' in content
    finally:context.database.dispose()

