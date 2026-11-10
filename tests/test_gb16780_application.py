"""未开放水泥的隔离依赖注入门禁；不修改生产正式支持集合。"""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from sqlalchemy import text

from uebench.application import evaluation_support
from uebench.application.gb16780 import IncompleteCementEvaluationError
from uebench.application.reporting import CementReportView
from uebench.bootstrap import create_context
from uebench.domain.models import Grade, InputMode, StandardDefinition
from uebench.domain.models import CementSharedEnergy, InputValue
from .test_gb16780_core import golden_request, IDS, put

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cement_context(tmp_path, monkeypatch):
    # 仅此测试夹具允许受测应用路径；默认生产门禁仍不含水泥。
    monkeypatch.setattr(evaluation_support, "SUPPORTED_EVALUATION_STANDARD_IDS", frozenset({"gb-29446-2019", "gb-16780-2021"}))
    context = create_context(tmp_path / "隔离水泥", enforce_standard_library_readiness=False)
    standard = StandardDefinition.model_validate_json((ROOT / "standards/development/GB16780-2021/gb-16780-2021-r2-candidate.json").read_text(encoding="utf-8"))
    context.standards.install(standard)
    yield context
    context.database.dispose()


def request():
    value = golden_request()
    value.notes = "核算周期：全年"
    return value


def state(context):
    with context.database.engine.connect() as connection:
        return (connection.execute(text("SELECT COUNT(*) FROM evaluations")).scalar_one(),
                connection.execute(text("SELECT COUNT(*) FROM audit_log WHERE action='EVALUATION_CREATE'")).scalar_one())


def test_complete_not_qualified_is_saved_once_with_all_lines_and_snapshots(cement_context):
    result = cement_context.application.evaluate(request())
    assert state(cement_context) == (1, 1)
    assert any(item.grade is Grade.NOT_QUALIFIED for item in result.results)
    loaded = cement_context.application.get_evaluation(result.evaluation_id)
    assert len(loaded[1].results) == 5 and loaded[1].results[0].line_id == "kiln-1"
    assert loaded[1].results[0].display_values["K"] == 1


def test_incomplete_exception_survives_facade_with_preview_and_no_save_audit(cement_context):
    value = request()
    value.cement_lines[0].fuels[0].mass_kg = None
    with pytest.raises(IncompleteCementEvaluationError) as caught:
        cement_context.application.evaluate(value)
    preview = caught.value.preview_result
    assert state(cement_context) == (0, 0)
    assert next(i for i in preview.results if i.indicator_id == IDS[2]).grade is Grade.LEVEL_2
    assert next(i for i in preview.results if i.indicator_id == IDS[4]).grade is Grade.LEVEL_3
    assert "未生成记录" in str(caught.value)
    # preview显式入口也永不保存，仍保留同样的局部结果。
    again = cement_context.application.preview_evaluation(value)
    assert [(i.actual_value, i.grade) for i in again.results] == [(i.actual_value, i.grade) for i in preview.results]
    assert state(cement_context) == (0, 0)


def test_multi_line_any_applicable_missing_prevents_entire_save(cement_context):
    value = request()
    second = value.cement_lines[0].model_copy(deep=True, update={"line_id": "second", "line_name": "第二线"})
    second.inputs.pop("cement.preparation_electricity_kwh")
    value.cement_lines.append(second)
    with pytest.raises(IncompleteCementEvaluationError) as caught:
        cement_context.application.evaluate(value)
    assert len(caught.value.preview_result.results) == 10
    assert all(i.grade is not Grade.INCOMPLETE for i in caught.value.preview_result.results[:5])
    assert state(cement_context) == (0, 0)


def test_pure_grinding_only_table3_completeness_and_period(cement_context):
    value = request()
    line = value.cement_lines[0]
    line.production_mode = "purchased_clinker_grinding"
    line.fuels = []
    line.inputs = {}
    put(line, "cement.production_t", "1000")
    put(line, "cement.preparation_electricity_kwh", "29000")
    result = cement_context.application.evaluate(value)
    assert state(cement_context) == (1, 1)
    assert [i.grade for i in result.results].count(Grade.NOT_APPLICABLE) == 4
    assert result.results[-1].grade is Grade.LEVEL_2


@pytest.mark.parametrize("bad", ["DIRECT", "missing-period", "bad-custom-period"])
def test_direct_and_missing_period_cannot_form_formal_record(cement_context, bad):
    value = request()
    if bad == "DIRECT":
        value.input_mode = InputMode.DIRECT
    else:
        value.notes = None if bad == "missing-period" else "核算周期：自定义\n自定义周期："
    with pytest.raises(ValueError):
        cement_context.application.evaluate(value)
    assert state(cement_context) == (0, 0)


@pytest.mark.parametrize("tamper", ["omit", "duplicate", "fake-not-applicable", "bad-hash", "numeric-version"])
def test_application_verifies_result_set_before_save(cement_context, monkeypatch, tamper):
    engine = cement_context.evaluation_service.engine
    original = engine.evaluate

    def altered(*args, **kwargs):
        result = original(*args, **kwargs)
        if tamper == "omit":
            result.results.pop()
        elif tamper == "duplicate":
            result.results.append(result.results[0].model_copy(deep=True))
        elif tamper == "fake-not-applicable":
            result.results[0].grade = Grade.NOT_APPLICABLE
        elif tamper == "bad-hash":
            result.rule_snapshot_sha256 = "0" * 64
        else:
            result.numeric_contract_version = "v2"
        return result

    monkeypatch.setattr(engine, "evaluate", altered)
    with pytest.raises(IncompleteCementEvaluationError):
        cement_context.application.evaluate(request())
    assert state(cement_context) == (0, 0)


def test_report_view_and_word_are_snapshot_only_after_current_rule_change(cement_context, monkeypatch, tmp_path):
    value = request()
    result = cement_context.application.evaluate(value)
    with cement_context.database.engine.connect() as connection:
        before = tuple(connection.execute(text("SELECT request_json,result_json,rule_snapshot_json FROM evaluations")).one())
    current = cement_context.application.get_published_standard(value.standard_id).model_copy(deep=True)
    current.rule_revision += 1
    current.title = "不可用于历史报告的新名称"
    cement_context.standards.install(current)

    def forbidden(*args, **kwargs):
        raise AssertionError("历史只读不得运行计算器/查询当前规则")

    monkeypatch.setattr(cement_context.evaluation_service.engine, "evaluate", forbidden)
    monkeypatch.setattr(cement_context.standards, "get_published", forbidden)
    view = cement_context.application.get_report_view(result.evaluation_id)
    assert isinstance(view, CementReportView)
    assert view.lines[0].metrics[0].full_value == "93.32515"
    assert any("系数K" in line and "：1" in line for line in view.lines[0].calculations)
    path = cement_context.application.export_word_report(result.evaluation_id, tmp_path / "水泥历史.docx")
    assert path.is_file()
    with cement_context.database.engine.connect() as connection:
        after = tuple(connection.execute(text("SELECT request_json,result_json,rule_snapshot_json FROM evaluations")).one())
    assert before == after and state(cement_context) == (1, 1)
    from docx import Document
    doc = Document(path)
    content = "\n".join([p.text for p in doc.paragraphs] + [c.text for t in doc.tables for row in t.rows for c in row.cells])
    assert "93.32515" in content and "不可用于历史报告" not in content
    assert "内部解释" in content and "2019(C.7)不用于" in content
    assert "P_shx" not in content or "生产水泥" in content
    assert "未填（无需软件额外扣除）" not in content  # 本例四项明确有值。


def test_word_reports_blank_deductions_and_repeat_headers(cement_context, tmp_path):
    value = request()
    for key in list(value.cement_lines[0].inputs):
        if key.startswith("deduction."):
            value.cement_lines[0].inputs.pop(key)
    result = cement_context.application.evaluate(value)
    path = cement_context.application.export_word_report(result.evaluation_id, tmp_path / "未填.docx")
    from zipfile import ZipFile
    with ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
        footer = archive.read("word/footer1.xml").decode("utf-8")
    assert "未填（无需软件额外扣除）" in xml
    assert "tblHeader" in xml and "cantSplit" in xml and 'w:instr="PAGE"' in footer


def test_default_production_scope_is_unchanged(tmp_path):
    # 不使用上面的DI fixture，证明新增实现未自行扩大正式范围。
    assert not evaluation_support.supports_formal_evaluation("gb-16780-2021")


def test_restart_saved_r2_is_readonly_even_when_scope_is_closed(cement_context, monkeypatch):
    result = cement_context.application.evaluate(request())
    data_root = cement_context.paths.root
    with cement_context.database.engine.connect() as connection:
        before = tuple(connection.execute(text("SELECT request_json,result_json,rule_snapshot_json FROM evaluations")).one())
    cement_context.database.dispose()
    monkeypatch.setattr(evaluation_support, "SUPPORTED_EVALUATION_STANDARD_IDS", frozenset({"gb-29446-2019"}))
    reopened = create_context(data_root, enforce_standard_library_readiness=False)
    try:
        loaded = reopened.application.get_evaluation(result.evaluation_id)
        assert loaded[1].results[0].actual_value == result.results[0].actual_value
        assert reopened.application.get_report_view(result.evaluation_id).lines[0].metrics[0].full_value == "93.32515"
        with reopened.database.engine.connect() as connection:
            after = tuple(connection.execute(text("SELECT request_json,result_json,rule_snapshot_json FROM evaluations")).one())
        assert before == after and state(reopened) == (1, 1)
    finally:
        reopened.database.dispose()


def test_shared_internal_ids_stay_in_audit_trace_not_history_or_word(cement_context, tmp_path):
    value = request()
    internal_id = "internal-shared-4aa5c791ac874f2b"
    value.cement_shared_energy = [CementSharedEnergy(shared_id=internal_id, target="cement_auxiliary",
        line_ids=["kiln-1"], amount=InputValue(value="1200", unit="kWh"))]
    result = cement_context.application.evaluate(value)
    assert any(internal_id in s.label for i in result.results for s in i.calculation_trace)
    view = cement_context.application.get_report_view(result.evaluation_id)
    from uebench.ui.cement_presentation import report_inputs_html
    html = report_inputs_html(view)
    assert internal_id not in html and "共用系统1" in html and "e_sh_before" not in html
    path = cement_context.application.export_word_report(result.evaluation_id, tmp_path / "共用分摊.docx")
    from zipfile import ZipFile
    with ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    assert internal_id not in xml and "共用系统1" in xml and "e_sh_before" not in xml
