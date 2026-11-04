from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from uebench.application.services import EvaluationService
from uebench.domain.engine import EvaluationEngine, EvaluationValidationError
from uebench.domain.gb16780 import Gb16780Calculator, MODE_INDICATORS, is_complete, validate_graph
from uebench.domain.models import (CementDetails, CementFuelLine, CementSharedAllocation,
    EvaluationRequest, Grade, InputMode, InputValue, StandardDefinition)

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def standard():
    return StandardDefinition.model_validate_json((ROOT / 'data/definitions/gb-16780-2021.json').read_text(encoding='utf-8'))

def request(mode='integrated', **changes):
    fields = {
        'production_mode': (mode,None), 'evaluation_period':('2025年',None), 'production_line_id':('A',None),
        'altitude_m':('1500','m'), 'clinker_production_t':('1000','t'),
        'clinker_consumption_t':('750','t'), 'cement_production_t':('1000','t'), 'clinker_ratio_percent':('75','%'),
        'clinker_electricity_kwh':('50000','kW·h'), 'waste_heat_generation_kwh':('10000','kW·h'),
        'waste_heat_self_use_kwh':('0','kW·h'), 'cement_grinding_packaging_kwh':('20000','kW·h'),
        'admixture_preparation_kwh':('1000','kW·h'), 'gypsum_preparation_kwh':('1000','kW·h'),
        'auxiliary_electricity_kwh':('2000','kW·h'), 'cement_fuel_kgce':('1000','kgce'),
        'grinding_electricity_kwh':('23000','kW·h'),
        'deduction.co_processing_fuel_tce':('1','tce'), 'deduction.alternative_fuel_tce':('1','tce'),
        'deduction.co_processing_electricity_kwh':('1000','kW·h'), 'deduction.alternative_fuel_electricity_kwh':('1000','kW·h'),
    }
    from uebench.domain.gb16780 import MODE_INPUT_KEYS
    fields = {k:v for k,v in fields.items() if k=='production_mode' or k in MODE_INPUT_KEYS[mode]}
    for k,v in changes.items():
        if v is None: fields.pop(k,None)
        else: fields[k]=(v,fields[k][1])
    return EvaluationRequest(evaluation_date=date(2026,10,29), standard_id='gb-16780-2021', product_id='cement',
        input_mode=InputMode.DETAIL, inputs={k:InputValue(value=v,unit=u)for k,(v,u)in fields.items()},
        cement_details=CementDetails(fuel_lines=[] if mode=='grinding_station' else [CementFuelLine(line_id='f1',name='燃煤',amount_kg='100000',low_heat_kj_per_kg='29307.6')]))

def by_id(result): return {x.indicator_id:x for x in result.results}

def test_independent_hand_calculation(standard):
    # Independent V1.2 hand derivation: 100000/1000 - .1229*10000/1000 - 2000/1000.
    result=Gb16780Calculator().evaluate(standard,request())
    values=by_id(result)
    assert values['clinker.coal'].actual_value == Decimal('96.771')
    assert values['clinker.electricity'].actual_value == Decimal('48')
    assert values['clinker.comprehensive'].actual_value == Decimal('102.6702')
    assert values['cement.comprehensive_energy'].actual_value == Decimal('80.95225')
    assert values['cement-preparation.electricity'].actual_value == Decimal('23')
    assert values['cement.comprehensive_energy'].display_values['cement_electricity']==60
    assert is_complete(result)
    assert result.rule_snapshot_sha256==EvaluationEngine._snapshot_sha256(standard)
    import json
    catalogue=json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
    metadata=next(item for item in catalogue["standards"] if item["id"]==standard.id)
    assert metadata["rule_revision"]==standard.rule_revision

@pytest.mark.parametrize('mode',MODE_INDICATORS)
def test_four_mode_applicability(standard,mode):
    result=Gb16780Calculator().evaluate(standard,request(mode))
    assert {x.indicator_id for x in result.results if x.grade is not Grade.NOT_APPLICABLE}==set(MODE_INDICATORS[mode])
    assert is_complete(result)

def test_local_preview_and_direct_guard(standard):
    result=Gb16780Calculator().evaluate(standard,request(grinding_electricity_kwh=None))
    assert by_id(result)['cement-preparation.electricity'].grade is Grade.INCOMPLETE
    assert by_id(result)['cement.comprehensive_energy'].actual_value==Decimal('80.95225')
    assert not is_complete(result)
    with pytest.raises(EvaluationValidationError,match='明细'):
        Gb16780Calculator().evaluate(standard,request().model_copy(update={'input_mode':InputMode.DIRECT}))

def test_decimal_context_and_blank_zero_preserved(standard):
    req=request(**{'deduction.co_processing_fuel_tce':None})
    with localcontext() as ctx:
        ctx.prec=6
        result=Gb16780Calculator().evaluate(standard,req)
    assert by_id(result)['clinker.coal'].actual_value==Decimal('97.771')
    assert 'deduction.co_processing_fuel_tce' not in req.inputs
    zero=request(**{'deduction.co_processing_fuel_tce':'0'})
    assert Gb16780Calculator().evaluate(standard,zero).results[0].actual_value==result.results[0].actual_value
    assert zero.inputs['deduction.co_processing_fuel_tce'].value=='0'

@pytest.mark.parametrize('kind',['duplicate','cycle','unknown'])
def test_invalid_dependency_graph_fails(standard,kind):
    nodes=standard.cement_calculation_nodes
    if kind=='duplicate': nodes.append(nodes[0].model_copy())
    else:
        nodes[0].formula.op='input'
        nodes[0].formula.input_key='computed.standard_coal_heat' if kind=='cycle' else 'computed.nonexistent'
    with pytest.raises(ValueError):validate_graph(standard)

def test_injection_and_hidden_mode_rejected(standard):
    req=request();req.inputs['computed.clinker_coal']=InputValue(value='1')
    with pytest.raises(ValueError,match='派生'): Gb16780Calculator().evaluate(standard,req)
    req=request('grinding_station');req.inputs['clinker_production_t']=InputValue(value='1',unit='t')
    with pytest.raises(ValueError,match='不适用'):Gb16780Calculator().evaluate(standard,req)

def test_negative_heat_only_blocks_dependent_indicators(standard):
    result=Gb16780Calculator().evaluate(standard,request(waste_heat_self_use_kwh='20000'))
    assert by_id(result)['clinker.coal'].grade is Grade.INCOMPLETE
    assert by_id(result)['clinker.electricity'].grade is Grade.LEVEL_1
    assert by_id(result)['cement-preparation.electricity'].grade is Grade.LEVEL_1

def test_shared_allocation_residual_does_not_block(standard):
    req=request('grinding_station', cement_production_t='1')
    req.cement_details.shared_allocations=[CementSharedAllocation(allocation_id='s1',product='cement',target_input_key='grinding_electricity_kwh',target_line_id='A',original_amount='1',unit='kW·h',line_production_t={'A':'1','B':'1','C':'1'})]
    result=Gb16780Calculator().evaluate(standard,req)
    assert is_complete(result)
    audits=[x for x in result.results[-1].calculation_trace if x.operation=='allocation_audit']
    assert len(audits)==1 and audits[0].value==Decimal('1e-28')
    assert req.inputs['grinding_electricity_kwh'].value=='23000'

def test_service_scope_and_save_guard(standard):
    class Standards:
        def get_for_evaluation(self,*a):return standard
    class Records:
        saved=[]
        def save(self,*a):self.saved.append(a)
    records=Records(); service=EvaluationService(Standards(),records,formal_standard_ids=frozenset(['gb-16780-2021']))
    with pytest.raises(ValueError,match='未保存'):service.evaluate(request(grinding_electricity_kwh=None))
    assert records.saved==[]
    service.evaluate(request()); assert len(records.saved)==1
    with pytest.raises(ValueError,match='不能用该标准'):EvaluationService(Standards(),records).evaluate(request())

def test_thresholds_percent_order_and_pressure(standard):
    req=request(clinker_ratio_percent='80');req.inputs['altitude_m']=InputValue(value='1600',unit='m')
    # Exactly K=1.05 under the governed Decimal operations.
    req.inputs['pressure_pa']=InputValue(value=str(Decimal('101325')*Decimal('.129')/Decimal('.211')),unit='Pa')
    result=Gb16780Calculator().evaluate(standard,req)
    limits=by_id(result)['cement.comprehensive_energy'].corrected_thresholds
    assert abs(limits['LEVEL_3']-Decimal('104.70')) < Decimal('1e-24')
    req.inputs['clinker_ratio_percent']=InputValue(value='101',unit='%')
    assert by_id(Gb16780Calculator().evaluate(standard,req))['cement.comprehensive_energy'].grade is Grade.INCOMPLETE

def test_legacy_models_keep_serialized_shape():
    payload=EvaluationRequest(evaluation_date=date(2026,1,1),standard_id='legacy',product_id='p',input_mode=InputMode.DETAIL,inputs={}).model_dump(mode='json')
    assert 'cement_details' not in payload

@pytest.mark.parametrize('kind',['unknown_target','wrong_product','wrong_mode','wrong_production'])
def test_allocation_structure_blocks_save_without_erasing_preview(standard,kind):
    req=request('grinding_station')
    target='grinding_electricity_kwh'
    product='cement'
    if kind=='unknown_target':target='computed.anything'
    if kind=='wrong_product':product='clinker'
    if kind=='wrong_mode':target='clinker_electricity_kwh';product='clinker'
    req.cement_details.shared_allocations=[CementSharedAllocation(allocation_id='s',product=product,
        target_input_key=target,target_line_id='A',original_amount='1',unit='kW·h',
        line_production_t={'A':'999','B':'1000'})]
    result=Gb16780Calculator().evaluate(standard,req)
    assert not is_complete(result)
    assert result.warnings
    if kind in ('unknown_target','wrong_mode'):
        assert by_id(result)['cement-preparation.electricity'].actual_value==23

def test_draft_rules_and_applicability_drift_rejected(standard):
    from uebench.domain.models import PublicationStatus
    standard.publication_status=PublicationStatus.DRAFT
    with pytest.raises(ValueError,match='published'):Gb16780Calculator().evaluate(standard,request())
    standard.publication_status=PublicationStatus.PUBLISHED
    standard.products[0].indicators[0].applicability.values=['clinker_only']
    with pytest.raises(ValueError,match='适用性'):validate_graph(standard)

def test_engine_entry_uses_same_opt_in_calculator(standard):
    assert by_id(EvaluationEngine().evaluate(standard,request()))['cement.comprehensive_energy'].actual_value==Decimal('80.95225')

@pytest.mark.parametrize('field,value,affected,unaffected',[
    ('clinker_electricity_kwh','-1','clinker.electricity','clinker.coal'),
    ('clinker_production_t','0','clinker.coal','cement-preparation.electricity'),
    ('deduction.co_processing_fuel_tce','10000','clinker.coal','clinker.electricity'),
    ('deduction.co_processing_electricity_kwh','100000','clinker.electricity','clinker.coal'),
])
def test_local_input_and_deduction_failures(standard,field,value,affected,unaffected):
    result=by_id(Gb16780Calculator().evaluate(standard,request(**{field:value})))
    assert result[affected].grade is Grade.INCOMPLETE
    assert result[unaffected].grade not in (Grade.INCOMPLETE,Grade.NOT_APPLICABLE)

def test_exact_full_value_grinding_boundary(standard):
    req=request('grinding_station',cement_production_t='1',grinding_electricity_kwh='34.00000000000000000000000001')
    result=by_id(Gb16780Calculator().evaluate(standard,req))['cement-preparation.electricity']
    assert result.grade is Grade.NOT_QUALIFIED

@pytest.mark.parametrize('missing',['altitude_m','clinker_ratio_percent','pressure_pa'])
def test_missing_dynamic_limit_input_never_defaults_to_zero_or_one(standard,missing):
    req=request(**{missing:None}) if missing!='pressure_pa' else request(altitude_m='1500.0001')
    result=by_id(Gb16780Calculator().evaluate(standard,req))
    assert result['cement.comprehensive_energy'].grade is Grade.INCOMPLETE
    assert result['cement-preparation.electricity'].grade is Grade.LEVEL_1
    if missing=='clinker_ratio_percent':
        assert result['clinker.coal'].grade is Grade.LEVEL_2
    else:
        assert result['clinker.coal'].grade is Grade.INCOMPLETE

def test_real_sqlite_r2_roundtrip_and_new_revision_preserves_snapshot(standard,tmp_path):
    """r2请求保存读回及r3覆盖保真；不代表真实r1包或旧EXE记录升级。"""
    from uebench.bootstrap import create_context
    context=create_context(tmp_path/'cement-records',enforce_standard_library_readiness=False)
    try:
        context.standards.install(standard)
        service=EvaluationService(context.standards,context.evaluations,formal_standard_ids=frozenset(['gb-16780-2021']))
        req=request(); req.inputs['deduction.co_processing_fuel_tce']=InputValue(value=None,unit='tce')
        saved=service.evaluate(req)
        before=context.evaluations.get(saved.evaluation_id)
        assert before[0].inputs['deduction.co_processing_fuel_tce'].value is None
        assert before[0].cement_details.fuel_lines[0].low_heat_kj_per_kg=='29307.6'
        assert before[1].rule_snapshot_sha256==EvaluationEngine._snapshot_sha256(before[2])
        baseline=tuple(x.model_dump_json() for x in before)
        standard.rule_revision=3
        standard.cement_calculation_nodes[0].formula.value='1'
        context.standards.install(standard)
        assert tuple(x.model_dump_json() for x in context.evaluations.get(saved.evaluation_id))==baseline
    finally:context.database.dispose()


def test_signed_r1_package_seeded_history_survives_current_r2_package(tmp_path):
    """真实已签r1定义构造的隔离历史行，不是旧EXE或真实用户旧记录验收。"""
    import hashlib
    import json
    from sqlalchemy import text
    from uebench.application.evaluation_support import FORMAL_EVALUATION_UNSUPPORTED_LABEL
    from uebench.bootstrap import create_context

    legacy_package=ROOT/'tests/fixtures/standard-packages/2026.10-published.5.uebench'
    assert legacy_package.is_file()
    assert hashlib.sha256(legacy_package.read_bytes()).hexdigest()=='9547e8214124cd76e999c2949dcdcf45738282a56cc0d725df08cea2a49fa2b5'
    pin=json.loads((ROOT/'release/standard-packages/PIN.json').read_text(encoding='utf-8'))
    assert pin['data_version']=='2026.10-published.6'
    current_package=ROOT/'release/standard-packages'/pin['file']
    assert hashlib.sha256(current_package.read_bytes()).hexdigest()==pin['sha256']
    context=create_context(tmp_path/'signed-r1-history',
        public_key_path=ROOT/'src/uebench/resources/update_public_key.pem',
        enforce_standard_library_readiness=False)
    try:
        # Both installs use the normal signature-verifying application path.
        context.application.install_package(legacy_package)
        legacy_standard=context.standards.get_published('gb-16780-2021')
        assert legacy_standard.rule_revision==1
        legacy_request=EvaluationRequest(evaluation_date=date(2026,10,29),
            standard_id='gb-16780-2021',product_id='cement',input_mode=InputMode.DIRECT,
            inputs={
                'actual.cement_comprehensive_energy':InputValue(value='75',unit='kgce/t'),
                'cement.clinker_ratio_pct':InputValue(value='75',unit='%'),
                'site.altitude_m':InputValue(value='1000',unit='m'),
                'site.pressure_pa':InputValue(value='90000',unit='Pa'),
            })
        legacy_result=context.application.preview_evaluation(legacy_request)
        assert len(legacy_result.results)==1
        assert legacy_result.results[0].actual_value==Decimal('75')
        assert legacy_result.results[0].grade is Grade.LEVEL_1
        assert legacy_result.rule_snapshot_sha256==EvaluationEngine._snapshot_sha256(legacy_standard)
        assert context.evaluations.count()==0
        # Explicit historical fixture seed: no production formal-scope bypass.
        context.evaluations.save(legacy_request,legacy_result,legacy_standard)
        def persisted_json():
            with context.database.engine.connect() as connection:
                row=connection.execute(text(
                    'SELECT request_json, result_json, rule_snapshot_json FROM evaluations '
                    'WHERE evaluation_id=:evaluation_id'),
                    {'evaluation_id':legacy_result.evaluation_id}).one()
                return tuple(row)
        before=persisted_json()
        snapshot_before=context.evaluations.get(legacy_result.evaluation_id)
        assert snapshot_before[2].rule_revision==1
        before_hash=snapshot_before[1].rule_snapshot_sha256

        context.application.install_package(current_package)
        selected=context.standards.get_for_evaluation('gb-16780-2021',date(2026,10,29))
        assert selected.rule_revision==2
        assert selected.cement_calculation_nodes
        assert persisted_json()==before
        snapshot_after=context.evaluations.get(legacy_result.evaluation_id)
        assert snapshot_after[2].rule_revision==1
        assert snapshot_after[1].rule_snapshot_sha256==before_hash
        assert snapshot_after[1].rule_snapshot_sha256==EvaluationEngine._snapshot_sha256(snapshot_after[2])
        assert snapshot_after[1].results[0].actual_value==Decimal('75')
        assert snapshot_after[1].results[0].grade is Grade.LEVEL_1
        assert snapshot_after[0].inputs['actual.cement_comprehensive_energy'].value=='75'

        with pytest.raises(ValueError) as caught:
            context.application.evaluate(request('grinding_station'))
        assert FORMAL_EVALUATION_UNSUPPORTED_LABEL in str(caught.value)
        assert context.evaluations.count()==1
        assert persisted_json()==before
    finally:context.database.dispose()
