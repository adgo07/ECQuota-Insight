"""历史结构只读投影，不运行旧计算器。"""
import json
from pathlib import Path
import pytest
from uebench.domain.models import EvaluationRequest, StandardDefinition
from uebench.domain.cement_history import parse_saved, original_hash, HistoricalCementStandard
from uebench.application.reporting import build_report_view
from .test_gb16780_core import golden_request

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("mode", ["integrated", "partial_purchased", "clinker_only", "grinding_station"])
def test_real_pr36_saved_snapshot_report(mode):
    from uebench.domain.models import EvaluationResult
    base = ROOT / "tests/fixtures/gb16780/pr36-records"
    request = parse_saved(EvaluationRequest, (base / (mode + "-request.json")).read_text(encoding="utf-8"))
    snapshot = parse_saved(StandardDefinition, (base / (mode + "-snapshot.json")).read_text(encoding="utf-8"))
    result = EvaluationResult.model_validate_json((base / (mode + "-result.json")).read_text(encoding="utf-8"))
    assert result.rule_snapshot_sha256 == original_hash(snapshot)
    before = result.model_dump_json()
    view = build_report_view(request, result, snapshot)
    assert view.saved_rule_snapshot_sha256 == result.rule_snapshot_sha256
    assert result.model_dump_json() == before
    if mode != "grinding_station":
        assert any(field.key == "fuel" for field in view.lines[0].inputs)
    result.rule_snapshot_sha256 = "0" * 64
    with pytest.raises(ValueError, match="哈希"):
        build_report_view(request, result, snapshot)

@pytest.mark.parametrize("payload", ["null", "[]", '\"string\"'])
def test_non_object_saved_payload_is_validation_error(payload):
    with pytest.raises(ValueError):
        parse_saved(EvaluationRequest, payload)


def test_unknown_legacy_field_stays_rejected():
    payload = json.loads((ROOT / "tests/fixtures/gb16780/pr36-r2-source.json").read_text(encoding="utf-8"))
    payload["invented"] = True
    with pytest.raises(ValueError):
        parse_saved(StandardDefinition, json.dumps(payload))



@pytest.mark.parametrize("mode", ["integrated", "partial_purchased", "clinker_only", "grinding_station"])
def test_raw_sqlite_read_list_word_preserves_all_three_payloads(tmp_path, mode):
    from uebench.bootstrap import create_context
    from uebench.domain.models import EvaluationResult, StorageCorruptionError
    from uebench.infrastructure.database import EvaluationRow
    from uebench.infrastructure.word_report import WordReportWriter
    base = ROOT / "tests/fixtures/gb16780/pr36-records"
    raw = {name: (base / (mode + "-" + name + ".json")).read_text(encoding="utf-8")
           for name in ("request", "result", "snapshot")}
    request = parse_saved(EvaluationRequest, raw["request"])
    result = EvaluationResult.model_validate_json(raw["result"])
    context = create_context(tmp_path / "isolated", enforce_standard_library_readiness=False)
    try:
        with context.database.session() as session:
            session.add(EvaluationRow(evaluation_id=result.evaluation_id, created_at=result.evaluated_at,
                evaluation_date=request.evaluation_date, standard_id=result.standard_id,
                standard_number=result.standard_number, product_id=result.product_id,
                request_json=raw["request"], result_json=raw["result"], rule_snapshot_json=raw["snapshot"]))
        loaded = context.evaluations.get(result.evaluation_id)
        assert loaded[1].rule_snapshot_sha256 == original_hash(loaded[2])
        page = context.evaluations.query_page()
        assert page.total == 1 and "无法读取" not in page.items[0].core_result
        WordReportWriter().write(build_report_view(*loaded), tmp_path / "historical.docx")
        assert (tmp_path / "historical.docx").is_file()
        with pytest.raises(ValueError, match="只读"):
            context.evaluations.save(*loaded)
        with context.database.session() as session:
            row = session.get(EvaluationRow, result.evaluation_id)
            assert (row.request_json, row.result_json, row.rule_snapshot_json) == (raw["request"], raw["result"], raw["snapshot"])
            row.rule_snapshot_json = "null"
        with pytest.raises(StorageCorruptionError):
            context.evaluations.get(result.evaluation_id)
    finally:
        context.database.dispose()



def test_stored_pr36_standard_is_browsable_without_new_package_admission(tmp_path):
    from uebench.bootstrap import create_context
    from uebench.infrastructure.database import StandardRow
    from uebench.domain.engine import EvaluationEngine, EvaluationValidationError
    from uebench.domain.models import EvaluationRequest
    payload = (ROOT / "tests/fixtures/gb16780/pr36-records/integrated-snapshot.json").read_text(encoding="utf-8")
    context = create_context(tmp_path / "legacy-library", enforce_standard_library_readiness=False)
    try:
        old = parse_saved(StandardDefinition, payload)
        # Installation of the historical shape is exercised through its original
        # stored JSON; this is not permission for a new package to admit r2.
        context.standards.install(old)
        loaded = context.standards.get_published(old.id)
        assert loaded.rule_revision == 2
        assert len(loaded.cement_calculation_nodes) == 15
        assert context.standards.list_all()
        candidate = StandardDefinition.model_validate_json((ROOT / "standards/development/GB16780-2021/gb-16780-2021-r3-candidate.json").read_text(encoding="utf-8"))
        context.standards.install(candidate)
        assert {(item.id, item.rule_revision) for item in context.standards.list_by_id(old.id)} == {(old.id, 2), (old.id, 3)}
        assert context.standards.get_published(old.id).rule_revision == 3
        request_payload = (ROOT / "tests/fixtures/gb16780/pr36-records/integrated-request.json").read_text(encoding="utf-8")
        request = parse_saved(EvaluationRequest, request_payload)
        with pytest.raises(EvaluationValidationError):
            EvaluationEngine().evaluate(loaded, request)
    finally:
        context.database.dispose()



def test_mutated_historical_model_cannot_reuse_original_hash():
    snapshot = parse_saved(StandardDefinition, (ROOT / "tests/fixtures/gb16780/pr36-records/integrated-snapshot.json").read_text(encoding="utf-8"))
    digest = original_hash(snapshot)
    snapshot.products[0].indicators[0].name = "altered"
    with pytest.raises(ValueError, match="字段被改变"):
        original_hash(snapshot)
