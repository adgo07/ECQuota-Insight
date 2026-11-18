"""生成未发布焦炭隔离链证据；规则仅在内存夹具采用，不生成候选规则JSON。"""
import argparse
from datetime import date
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def fixture_snapshot():
    from uebench.domain.models import StandardDefinition
    from uebench.application.coke_records import candidate_snapshot
    snapshot = StandardDefinition.model_validate_json((ROOT / "data/definitions/gb-21342-2025.json").read_text(encoding="utf-8"))
    return candidate_snapshot(snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,required=True,help="必须为全新目录，不覆盖旧证据")
    args = parser.parse_args()
    root = args.output_dir.resolve()
    if root.exists():
        parser.error("证据目录必须不存在，不覆盖旧数据")
    from uebench.bootstrap import create_context
    from uebench.application.evaluation_support import development_evaluation_scope
    from uebench.application.coke_records import input_payload
    from uebench.domain.gb21342 import CokeAssessmentInput, CokeEnergyInput
    from uebench.domain.coke_flows import CokeFlow, aggregate_flows, COMPONENTS
    from uebench.domain.models import EvaluationRequest, InputMode
    root.mkdir(parents=True)
    head = subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    dirty = bool(subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip())
    rows = []
    context = create_context(root / "isolated-data",enforce_standard_library_readiness=False)
    with development_evaluation_scope({"gb-21342-2025"}):
        try:
            context.standards.install(fixture_snapshot())
            for energy,quench,expected in (("111","mixed","LEVEL_1"),("113","dry","LEVEL_3"),("138","dry","NOT_QUALIFIED")):
                flows = aggregate_flows([CokeFlow("synthetic-electricity-"+energy, COMPONENTS[1], "electricity", "1000", "kWh")], zero_components=[k for k in COMPONENTS if k != COMPONENTS[1]]) if energy == "111" else None
                energy_input = flows.energy_input("2", "included_or_not_external") if flows else CokeEnergyInput(energy,"0","0","0","0","1","included_or_not_external")
                assessment = CokeAssessmentInput(energy_input,
                    oven_type="top_charging",heating_fuel="coke_oven_gas",dry_volatile_pct="23",total_moisture_pct="10",
                    oven_age_years="20",quenching_method=quench,conventional_oven=True)
                request = EvaluationRequest(evaluation_date=date(2026,11,17),standard_id="gb-21342-2025",
                    product_id="top-charging-coke-oven",input_mode=InputMode.DETAIL,inputs={},coke_payload=input_payload(assessment, flow_result=flows),
                    organization_name="合成焦炭隔离验收对象",notes="2026年10月 合成数据")
                result = context.application.evaluate(request)
                assert result.results[0].grade.value == expected
                loaded = context.application.get_evaluation(result.evaluation_id)
                assert loaded[0].coke_payload == request.coke_payload
                view = context.application.get_report_view(result.evaluation_id)
                if flows:
                    assert "表A.2" in str(view) and "0.1229" in str(view)
                path = root / f"coke-{energy}.docx"
                context.application.export_word_report(result.evaluation_id,path)
                rows.append({"record_id":result.evaluation_id,"sample_id":energy,"evaluation_energy_kgce_per_t":str(result.results[0].actual_value),"grade":expected,"docx":path.name,
                             "input_mode":"flows" if flows else "totals", "flow_rows":len(flows.rows) if flows else 0,
                             "docx_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"rule_snapshot_sha256":result.rule_snapshot_sha256})
        finally:
            context.database.dispose()
    evidence = {"source_commit":head,"source_dirty":dirty,"kind":"UNPUBLISHED_ISOLATED_FIXTURE",
                "production_rules_changed":False,"production_scope_changed":False,"records":rows}
    (root / "evidence.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(evidence,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
