"""完整主应用链、真实签包启动对账以及独立开发入口。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
from contextlib import contextmanager
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from uebench.application.evaluation_support import development_evaluation_scope, supports_formal_evaluation, SUPPORTED_EVALUATION_STANDARD_IDS
from uebench.coke_candidate import isolated_coke_context, prepare_isolated_root, STANDARD_ID
from uebench.ui.main_window import MainWindow
from .test_coke_product import populate


@contextmanager
def application_context(root):
    from uebench.bootstrap import create_context
    from uebench.infrastructure.logging import close_logging
    from uebench.application.self_check import locate_public_key
    from uebench.main import reconcile_standard_package

    context = create_context(root, public_key_path=locate_public_key(), enforce_standard_library_readiness=True)
    try:
        reconcile_standard_package(context)
        context.package_reconciliation.require_formal_evaluation_ready()
        yield context
    finally:
        context.database.dispose()
        close_logging()


@pytest.fixture
def window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    for name in ("warning", "critical", "information"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: QMessageBox.Ok)
    with tempfile.TemporaryDirectory(prefix="ecq-coke-ui-test-") as directory:
        with application_context(Path(directory)) as context:
            widget = MainWindow(context)
            assert widget.eval_standard.currentData() == "gb-29446-2019"
            assert not widget.eval_standard.isHidden()
            widget.eval_standard.setCurrentIndex(widget.eval_standard.findData(STANDARD_ID))
            assert widget.current_standard.id == STANDARD_ID
            populate(widget.coke_form)
            widget.coke_form.fields["object_name"].setText("合成焦炭对象")
            widget.coke_form.fields["period"].setText("2026年10月")
            yield widget
            widget.close()
            app.processEvents()


def test_main_window_real_dispatch_single_save_history_and_word(window, monkeypatch, tmp_path):
    form = window.coke_form
    assert window.current_standard.id == STANDARD_ID
    assert window.generic_form_container.isHidden() and window.cement_form.isHidden()
    assert not form.isHidden()
    assert window.context.application.formal_evaluation_block_message() is None
    assert SUPPORTED_EVALUATION_STANDARD_IDS == frozenset({"gb-29446-2019", STANDARD_ID})
    calls = []
    original = window.context.application.evaluate
    def spy(request):
        calls.append(request)
        return original(request)
    monkeypatch.setattr(window.context.application, "evaluate", spy)
    before = window.context.evaluations.count()
    window.calculate_button.click()
    rid = window.last_result_id
    assert rid and len(calls) == 1 and window.context.evaluations.count() == before+1
    assert not window.calculate_button.isEnabled()
    window.calculate_evaluation()
    assert len(calls) == 1 and window.context.evaluations.count() == before+1
    loaded = window.context.application.get_evaluation(rid)
    assert loaded[0].notes == "2026年10月"
    assert loaded[0].organization_name == "合成焦炭对象"
    assert loaded[1].results[0].grade.value == "LEVEL_1"
    assert "待确定" in form.output.toPlainText()  # 低等级未知不阻断最高等级已确定。
    form.view_record.click()
    assert window.record_detail_page.tabs.count() == 2
    assert "1级" in window.record_detail_page.result_content.toPlainText()
    target = tmp_path/"焦炭主应用.docx"
    names = []
    def dialog(*args, **kwargs):
        names.append(args[2])
        return str(target), "Word"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", dialog)
    window.record_detail_page.export_button.click()
    assert target.is_file() and names == ["焦炭能耗对标报告.docx"]
    form.fields["raw_coal_energy_kgce"].setText("113")
    assert window.last_result_id is None and window.calculate_button.isEnabled()
    assert not form.view_record.isEnabled() and not form.export_word.isEnabled()
    assert not form.output.toPlainText() and "数据已修改" in form.notice.text()


@pytest.mark.parametrize("condition", ["partial", "not_applicable"])
def test_partial_and_not_applicable_keep_preview_without_record(window, condition):
    form = window.coke_form
    if condition == "partial":
        form.fields["dry_volatile_pct"].clear()
    else:
        form.choices["conventional_oven"].setCurrentIndex(form.choices["conventional_oven"].findData(False))
    before = window.context.evaluations.count()
    window.calculate_button.click()
    assert window.context.evaluations.count() == before and window.last_result_id is None
    assert "尚未生成记录" in form.notice.text()
    assert "实际能耗" in form.output.toPlainText()
    assert ("不完整" if condition == "partial" else "不适用") in form.output.toPlainText()
    assert window.calculate_button.isEnabled() and not form.export_word.isEnabled()


@pytest.mark.parametrize("key,label", [("period","统计期"), ("object_name","对象名称")])
def test_required_product_metadata_errors_are_inline(window, key, label):
    window.coke_form.fields[key].setText("   ")
    before = window.context.evaluations.count()
    window.calculate_button.click()
    assert label in window.coke_form.notice.text()
    assert window.last_result_id is None and window.context.evaluations.count() == before
    assert window.calculate_button.isEnabled()


def test_flow_mode_real_main_application_ignores_hidden_totals_and_syncs_oven(window):
    form = window.coke_form
    oven = form.choices["oven_type"]
    oven.setCurrentIndex(oven.findData("stamp_charging"))
    assert window.eval_product.currentData() == "stamp-charging-coke-oven"
    assert window._collect_request().product_id == "stamp-charging-coke-oven"
    window.eval_product.setCurrentIndex(window.eval_product.findData("top-charging-coke-oven"))
    assert oven.currentData() == "top_charging"
    form.energy_mode.setCurrentIndex(form.energy_mode.findData("flows"))
    flows = form.flows_form
    flows.add()
    for column,value in ((0,"processing_energy_kgce"),(1,"electricity"),(3,"kWh")):
        combo = flows.table.cellWidget(0,column)
        combo.setCurrentIndex(combo.findData(value))
    flows.table.item(0,2).setText("1000")
    for key,box in flows.zeros.items():
        box.setChecked(key != "processing_energy_kgce")
    form.fields["dry_coke_output_t"].setText("2")
    window.calculate_button.click()
    result = window.context.application.get_evaluation(window.last_result_id)[1]
    assert str(result.results[0].actual_value) == "61.4500"
    assert "0.1229" in form.details.toPlainText()


def test_development_scope_restores_after_exception_and_never_changes_formal_set():
    cement_id = "gb-16780-2021"
    assert not supports_formal_evaluation(cement_id)
    with pytest.raises(RuntimeError):
        with development_evaluation_scope({cement_id}):
            assert supports_formal_evaluation(cement_id)
            assert SUPPORTED_EVALUATION_STANDARD_IDS == frozenset({"gb-29446-2019", STANDARD_ID})
            raise RuntimeError("合成异常")
    assert not supports_formal_evaluation(cement_id)


def test_isolation_rejects_unmarked_and_user_data(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="ecq-coke-boundary-") as directory:
        root = Path(directory)
        (root/"unrelated.txt").write_text("keep",encoding="utf-8")
        with pytest.raises(ValueError,match="已标记"):
            prepare_isolated_root(root)
        assert (root/"unrelated.txt").read_text() == "keep"
        protected = root/"user-data"
        monkeypatch.setenv("UEBENCH_DATA_DIR", str(protected))
        with pytest.raises(ValueError,match="正式用户"):
            prepare_isolated_root(protected/"child")


def test_source_smoke_reopens_saved_snapshots_without_calculator(tmp_path, monkeypatch):
    from uebench.coke_candidate import _smoke, _readback
    from uebench.application import coke_records
    with tempfile.TemporaryDirectory(prefix="ecq-coke-reopen-") as directory:
        root = Path(directory)
        result = _smoke(root)
        from uebench.domain import coke_flows
        from uebench.domain.engine import EvaluationEngine
        def forbidden(*args, **kwargs):
            pytest.fail("历史不得重算")
        monkeypatch.setattr(coke_records, "preview_coke", forbidden)
        monkeypatch.setattr(coke_records, "assess_coke", forbidden)
        monkeypatch.setattr(coke_flows, "aggregate_flows", forbidden)
        monkeypatch.setattr(EvaluationEngine, "evaluate", forbidden)
        reopened = _readback(root)
        assert reopened["snapshots_unchanged"] and reopened["record_id"] == result["record_id"]


def test_transaction_failure_keeps_preview_no_record_and_allows_retry(window, monkeypatch, caplog):
    context = window.context
    before = context.evaluations.count()
    audit_before = context.audit.list_recent()
    original = context.audit.append
    def fail(*args, **kwargs):
        original(*args, **kwargs)  # 连已加入事务的审计行也必须回滚。
        raise RuntimeError("合成审计失败，技术细节不得显示给用户")
    monkeypatch.setattr(context.audit, "append", fail)
    window.calculate_button.click()
    assert context.evaluations.count() == before and window.last_result_id is None
    assert context.audit.list_recent() == audit_before
    form = window.coke_form
    assert "保存失败，未生成记录，可重试" in form.notice.text()
    assert "技术细节" not in form.notice.text() and "已生成一条" not in form.notice.text()
    assert "实际能耗" in form.output.toPlainText() and "111" in form.output.toPlainText()
    assert "1级" in form.output.toPlainText() and form.details.toPlainText()
    assert form.result is not None
    assert "保留本次计算预览" in caplog.text and "合成审计失败" in caplog.text
    assert window.calculate_button.isEnabled()
    assert not form.export_word.isEnabled() and not form.view_record.isEnabled()
    monkeypatch.setattr(context.audit, "append", original)
    window.calculate_button.click()
    assert window.last_result_id and context.evaluations.count() == before+1
    assert len(context.audit.list_recent()) == len(audit_before)+1
    window.calculate_evaluation()
    assert context.evaluations.count() == before+1


def test_application_save_error_retains_cause_and_single_computed_preview(window, monkeypatch):
    from uebench.application.coke_records import CokeRecordSaveError
    from uebench.application import coke_records
    context = window.context
    request = window.coke_form.collect_request(window._selection_mode())
    failure = RuntimeError("合成保存异常")
    computed = []
    original = coke_records.assess_coke
    def calculate(*args, **kwargs):
        result = original(*args, **kwargs)
        computed.append(result)
        return result
    def save_fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(coke_records, "assess_coke", calculate)
    monkeypatch.setattr(context.evaluations, "save", save_fail)
    before = context.evaluations.count()
    with pytest.raises(CokeRecordSaveError) as caught:
        context.application.evaluate(request)
    assert caught.value.__cause__ is failure and len(computed) == 1
    preview = caught.value.preview_result
    assert preview.results[0].grade.value == "LEVEL_1"
    assert preview.coke_payload["assessment"]["energy"]["actual_energy_kgce_per_t"] == "111"
    assert context.evaluations.count() == before


def test_real_readiness_without_reconciliation_blocks_even_development_scope(monkeypatch):
    from uebench.bootstrap import create_context
    from uebench.application.coke_records import candidate_snapshot
    from uebench.domain.models import StandardDefinition
    app = QApplication.instance() or QApplication([])
    base = StandardDefinition.model_validate_json((Path(__file__).resolve().parents[1]/"data/definitions/gb-21342-2025.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="ecq-coke-not-ready-") as directory:
        context = create_context(Path(directory), enforce_standard_library_readiness=True)  # 显式启用，避免conftest隔离默认覆盖。
        with development_evaluation_scope({STANDARD_ID}):
            context.standards.install(candidate_snapshot(base))
            widget = MainWindow(context)
            try:
                assert widget.open_evaluation_for_standard(STANDARD_ID)
                assert not widget.calculate_button.isEnabled()
                assert widget.evaluation_readiness_notice.text()
                assert context.application.formal_evaluation_block_message()
            finally:
                widget.close()
                context.database.dispose()
                from uebench.infrastructure.logging import close_logging
                close_logging()



def test_formal_service_requires_coke_payload(window):
    request = window.coke_form.collect_request(window._selection_mode())
    request.coke_payload = None
    before = window.context.evaluations.count()
    with pytest.raises(ValueError, match="焦炭输入载荷版本"):
        window.context.application.evaluate(request)
    assert window.context.evaluations.count() == before


def test_formal_badge_official_source_and_short_unit_placeholder(window):
    from uebench.ui.presentation import software_support_text
    assert window.eval_support_label.text() == "正式支持"
    with development_evaluation_scope({STANDARD_ID}):
        assert software_support_text(STANDARD_ID) == "开发验收专用，尚未正式支持"
    assert software_support_text("gb-29446-2019") == "正式支持"
    assert software_support_text("gb-21340-2019") == "未开放"
    assert window.eval_standard_open.isEnabled()
    assert window.eval_standard_open.toolTip() == "https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=5DB2AFADA4980285095D82F5A23D947A"
    assert window.eval_official_status.text() == "国家标准全文公开系统"
    form = window.coke_form
    form.energy_mode.setCurrentIndex(form.energy_mode.findData("flows"))
    form.flows_form.add()
    combo = form.flows_form.table.cellWidget(0, 12)
    assert combo.currentText() == "选择单位"
    window.show()
    QApplication.processEvents()
    assert combo.fontMetrics().horizontalAdvance(combo.currentText()) + 32 <= combo.width()
