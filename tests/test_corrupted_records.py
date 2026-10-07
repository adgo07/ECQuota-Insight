"""RS05 阻断缺陷回归：单条损坏记录不得阻止应用启动。

覆盖范围：

1. ``list_recent`` 遇到损坏的 ``result_json`` 仍返回全部记录，损坏行显式降级；
2. 每条损坏行产生 WARNING（``caplog``）；
3. 全部记录损坏时仍返回降级条目，不抛异常；
4. ``get_evaluation`` 对损坏记录抛出可区分的类型化信号（不是 ``None``，消息含“损坏”），
   软删除仍返回 ``None``；
5. 损坏行存在时 ``MainWindow(dialog)`` / ``refresh_all()`` 不抛异常，记录页显式标记；
6. 导出损坏记录报“损坏”，不再误报为输入数据错误；
7. 全部为完好记录时列表完整且不产生 WARNING。
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, datetime, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QTextEdit
from sqlalchemy import text

from uebench.application import evaluation_support
from uebench.bootstrap import create_context
from uebench.domain.models import (
    RECORD_CORRUPTED_LABEL,
    EvaluationRequest,
    EvaluationSummary,
    InputMode,
    InputValue,
    StorageCorruptionError,
)
from uebench.infrastructure.repositories import SqlEvaluationRepository
from uebench.ui.main_window import MainWindow, _friendly_error

from .test_engine import make_standard

CORRUPTED_RESULT_JSON = '{"evaluation_id": "truncated", "results": ['
GENERIC_INPUT_MESSAGE = "导出Excel失败，请检查输入数据、单位和适用条件后重试。"

#: 本文件统一使用的夹具标准（``make_standard()`` 的 id）。
FIXTURE_STANDARD_ID = "gb-00000-2026"


@pytest.fixture(autouse=True)
def _fixture_standard_is_formally_evaluable(monkeypatch):
    """把夹具标准放进**真正的**正式评价范围注册表（与 ``test_ui.py::_in_formal_scope`` 同模式）。

    本文件覆盖的是损坏记录的读取降级、导出、备份与界面表现，全部需要经
    ``ctx.application.evaluate`` 走**正式**落库路径来造数据；它不覆盖范围本身。RS05 §三
    之后，范围外标准无法形成正式记录，因此这里显式扩展注册表本身——产品的正式评价判定
    仍然完全由注册表驱动，测试没有绕过它。
    """
    extended = set(evaluation_support.SUPPORTED_EVALUATION_STANDARD_IDS) | {FIXTURE_STANDARD_ID}
    monkeypatch.setattr(
        evaluation_support, "SUPPORTED_EVALUATION_STANDARD_IDS", frozenset(extended)
    )


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def context(tmp_path, qt_app):
    ctx = create_context(tmp_path / "中文数据")
    ctx.standards.install(make_standard())
    try:
        yield ctx
    finally:
        ctx.database.dispose()


def build_request(standard, electricity: str = "15") -> EvaluationRequest:
    return EvaluationRequest(
        evaluation_date=standard.effective_date,
        standard_id=standard.id,
        product_id="product",
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value=electricity, unit="kgce/t")},
        organization_name="损坏记录测试企业",
    )


def save_evaluation(ctx, electricity: str = "15"):
    """Save one record through the real application use case (no private API)."""
    standard = ctx.application.get_published_standard("gb-00000-2026")
    result = ctx.application.evaluate(build_request(standard, electricity))
    time.sleep(0.002)  # created_at ordering stays unambiguous on fast disks
    return result


def corrupt_result_json(ctx, evaluation_id: str, payload: str = CORRUPTED_RESULT_JSON) -> None:
    """Damage exactly one stored payload with raw SQL, as the incident did."""
    with ctx.database.session() as session:
        session.execute(
            text("UPDATE evaluations SET result_json = :payload WHERE evaluation_id = :eid"),
            {"payload": payload, "eid": evaluation_id},
        )
        session.commit()


def stored_result_json(ctx, evaluation_id: str) -> str:
    with ctx.database.engine.connect() as connection:
        return connection.execute(
            text("SELECT result_json FROM evaluations WHERE evaluation_id=:eid"),
            {"eid": evaluation_id},
        ).scalar_one()


def corrupt_all(ctx) -> list[str]:
    ids = [summary.evaluation_id for summary in ctx.application.list_recent_evaluations()]
    for evaluation_id in ids:
        corrupt_result_json(ctx, evaluation_id)
    return ids


def select_record(window: MainWindow, evaluation_id: str) -> None:
    window.refresh_records()
    for row in range(window.record_table.rowCount()):
        if window.record_table.item(row, 0).data(Qt.ItemDataRole.UserRole) == evaluation_id:
            window.record_table.selectRow(row)
            return
    raise AssertionError("记录未出现在评价记录页")


# ---------------------------------------------------------------------------
# 1 + 2 + 7. 混合损坏行：好记录照常展示，坏记录显式降级并记录 WARNING
# ---------------------------------------------------------------------------

def test_list_recent_keeps_good_rows_and_degrades_corrupted_row(context, caplog):
    good_before = save_evaluation(context, "15")
    corrupted = save_evaluation(context, "25")
    good_after = save_evaluation(context, "35")
    corrupt_result_json(context, corrupted.evaluation_id)

    with caplog.at_level(logging.WARNING):
        summaries = context.application.list_recent_evaluations()

    assert [item.evaluation_id for item in summaries] == [
        good_after.evaluation_id,
        corrupted.evaluation_id,
        good_before.evaluation_id,
    ], "损坏行不得丢页，也不得改变记录顺序"
    by_id = {item.evaluation_id: item for item in summaries}

    damaged = by_id[corrupted.evaluation_id]
    assert damaged.is_corrupted is True
    assert RECORD_CORRUPTED_LABEL in damaged.corruption_reason
    assert damaged.product_name == "", "降级行不得伪造业务结论"
    assert damaged.standard_number == "GB 00000-2026", "降级行回退到数据库原始列"
    assert damaged.project_name is None

    for good in (good_before, good_after):
        healthy = by_id[good.evaluation_id]
        assert healthy.is_corrupted is False
        assert healthy.product_name == good.product_name
        assert healthy.standard_title == good.standard_title
        assert healthy.corruption_reason == ""

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1, "每条损坏行恰好一条 WARNING"
    assert warnings[0].name == "uebench.infrastructure.repositories"
    assert corrupted.evaluation_id in warnings[0].getMessage()
    assert "评价结论数据" in warnings[0].getMessage(), "日志应使用中文列语义，而不是裸列名"


def test_corrupted_row_is_never_rewritten_or_deleted(context, caplog):
    record = save_evaluation(context)
    corrupt_result_json(context, record.evaluation_id)
    before = stored_result_json(context, record.evaluation_id)

    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            assert context.application.list_recent_evaluations()
            with pytest.raises(StorageCorruptionError):
                context.application.get_evaluation(record.evaluation_id)

    assert stored_result_json(context, record.evaluation_id) == before, "不得自动改写损坏行"
    assert context.application.count_evaluations() == 1, "不得自动删除损坏行"


# ---------------------------------------------------------------------------
# 3. 全部损坏：仍返回降级条目
# ---------------------------------------------------------------------------

def test_list_recent_with_only_corrupted_rows_returns_degraded_entries(context, caplog):
    first = save_evaluation(context, "15")
    second = save_evaluation(context, "25")
    corrupted_ids = corrupt_all(context)
    assert sorted(corrupted_ids) == sorted([first.evaluation_id, second.evaluation_id])

    with caplog.at_level(logging.WARNING):
        summaries = context.application.list_recent_evaluations()

    assert len(summaries) == 2
    assert all(item.is_corrupted for item in summaries)
    assert all(RECORD_CORRUPTED_LABEL in item.corruption_reason for item in summaries)
    assert all(item.product_name == "" for item in summaries)
    assert len([record for record in caplog.records if record.levelno == logging.WARNING]) == 2


# ---------------------------------------------------------------------------
# 4. get(): 损坏 ≠ 不存在
# ---------------------------------------------------------------------------

def test_get_reports_corruption_and_soft_delete_still_returns_none(context):
    corrupted = save_evaluation(context, "15")
    deleted = save_evaluation(context, "25")
    healthy = save_evaluation(context, "35")
    corrupt_result_json(context, corrupted.evaluation_id)

    with pytest.raises(StorageCorruptionError) as caught:
        context.application.get_evaluation(corrupted.evaluation_id)
    message = str(caught.value)
    assert "损坏" in message
    assert "已被删除或不存在" not in message
    assert caught.value is not None, "损坏信号必须与 None 可区分"

    assert context.application.delete_evaluation(deleted.evaluation_id) is True
    assert context.application.get_evaluation(deleted.evaluation_id) is None, "软删除契约不变"
    assert context.application.get_evaluation("does-not-exist") is None, "缺失契约不变"

    loaded = context.application.get_evaluation(healthy.evaluation_id)
    assert loaded is not None and loaded[1].evaluation_id == healthy.evaluation_id


def test_corrupted_request_json_and_snapshot_also_raise(context, caplog):
    broken = save_evaluation(context, "15")
    with context.database.session() as session:
        session.execute(
            text("UPDATE evaluations SET rule_snapshot_json = :payload WHERE evaluation_id = :eid"),
            {"payload": "{not json", "eid": broken.evaluation_id},
        )
        session.commit()

    with caplog.at_level(logging.WARNING):
        with pytest.raises(StorageCorruptionError) as caught:
            context.application.get_evaluation(broken.evaluation_id)
    assert "损坏" in str(caught.value)
    assert any("规则快照" in record.getMessage() for record in caplog.records)

    # 只有 result_json 损坏不影响 list_recent 的数据库列回退
    summaries = context.application.list_recent_evaluations()
    assert [item.evaluation_id for item in summaries] == [broken.evaluation_id]
    assert summaries[0].is_corrupted is False, "list_recent 只解析 result_json"


# ---------------------------------------------------------------------------
# 5. UI: 启动 / refresh_all / 记录页 / 详情页
# ---------------------------------------------------------------------------

def test_main_window_starts_and_refreshes_with_corrupted_row(context, qt_app, monkeypatch):
    good = save_evaluation(context, "15")
    corrupted = save_evaluation(context, "25")
    corrupt_result_json(context, corrupted.evaluation_id)

    window = MainWindow(context)  # __init__ 调用 refresh_all()
    window.refresh_all()
    try:
        assert window.home_recent.rowCount() == 2, "损坏行不得从首页消失"
        # ECQ-RS05 M3：refresh_all 不再为从未打开过的「评价记录」页读取 200 条；
        # 该页在首次进入时加载。断言内容与强度不变。
        window.navigation.setCurrentRow(3)
        assert window.record_table.rowCount() == 2, "损坏行不得从评价记录页消失"

        select_record(window, corrupted.evaluation_id)
        marker = window.record_table.item(window.record_table.currentRow(), 5).text()
        assert RECORD_CORRUPTED_LABEL in marker

        select_record(window, good.evaluation_id)
        good_marker = window.record_table.item(window.record_table.currentRow(), 5).text()
        assert RECORD_CORRUPTED_LABEL not in good_marker
    finally:
        window.close()

    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, title, message: warnings.append(message))
    monkeypatch.setattr(
        QMessageBox, "critical", lambda _parent, _title, message: pytest.fail(message)
    )

    window = MainWindow(context)
    try:
        select_record(window, corrupted.evaluation_id)
        window.view_selected_record()
    finally:
        window.close()

    assert warnings, "损坏记录必须显式告知用户"
    assert any("损坏" in message for message in warnings)
    assert not any("已被删除或不存在" in message for message in warnings), (
        "损坏不得复用删除措辞"
    )


def test_recalculate_corrupted_record_warns_and_does_not_raise(context, qt_app, monkeypatch):
    corrupted = save_evaluation(context, "15")
    corrupt_result_json(context, corrupted.evaluation_id)
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, title, message: warnings.append(message))

    window = MainWindow(context)
    try:
        select_record(window, corrupted.evaluation_id)
        window.recalculate_selected_record()
    finally:
        window.close()

    assert any("损坏" in message for message in warnings)
    assert window.last_result_id is None


# ---------------------------------------------------------------------------
# 6. 导出：损坏，而不是“输入数据错误”
# ---------------------------------------------------------------------------

def test_export_corrupted_record_reports_corruption_not_bad_input(context, qt_app, monkeypatch, tmp_path):
    corrupted = save_evaluation(context, "15")
    corrupt_result_json(context, corrupted.evaluation_id)
    target = tmp_path / "损坏记录导出.xlsx"

    with pytest.raises(StorageCorruptionError) as caught:
        context.application.export_evaluation(corrupted.evaluation_id, target)

    friendly = _friendly_error(caught.value, "导出Excel")
    assert "损坏" in friendly
    assert friendly != GENERIC_INPUT_MESSAGE
    assert "请检查输入数据" not in friendly
    assert not target.exists(), "损坏记录不得产出半成品工作簿"
    assert corrupted.evaluation_id not in [
        event.entity_id
        for event in context.audit.list_recent()
        if event.action == "WORKBOOK_EXPORT"
    ]

    captured: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "critical", lambda _parent, _title, message: captured.append(message)
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda _parent, _title, message: pytest.fail("不应报告导出成功")
    )
    monkeypatch.setattr(
        "uebench.ui.main_window.QFileDialog.getSaveFileName", lambda *args: (str(target), "")
    )
    window = MainWindow(context)
    try:
        select_record(window, corrupted.evaluation_id)
        window.export_selected_record()
    finally:
        window.close()

    assert captured and "损坏" in captured[0]
    assert captured[0] != GENERIC_INPUT_MESSAGE


def test_export_missing_record_keeps_its_own_message(context, tmp_path):
    with pytest.raises(LookupError) as caught:
        context.application.export_evaluation("does-not-exist", tmp_path / "不存在.xlsx")
    assert "不存在" in str(caught.value)
    assert not isinstance(caught.value, StorageCorruptionError)


def test_backup_and_restore_still_work_with_a_corrupted_row(context, tmp_path):
    """备份链路本来就只复制文件，损坏行不得让整条链路崩溃。"""
    corrupted = save_evaluation(context, "15")
    save_evaluation(context, "25")
    corrupt_result_json(context, corrupted.evaluation_id)
    archive = tmp_path / "损坏数据备份.uebackup"

    assert context.application.create_backup(archive) == archive.resolve()
    assert context.backup_service.validate(archive)["backup_id"]

    summaries = context.application.list_recent_evaluations()
    assert len(summaries) == 2
    assert any(item.is_corrupted for item in summaries)


# ---------------------------------------------------------------------------
# 7. 回归：全部完好记录时行为不变，且无 WARNING
# ---------------------------------------------------------------------------

def test_healthy_database_lists_everything_without_warnings(context, caplog):
    saved = [save_evaluation(context, value) for value in ("15", "25", "35")]

    with caplog.at_level(logging.WARNING):
        summaries = context.application.list_recent_evaluations(200)
        loaded = context.application.get_evaluation(saved[0].evaluation_id)

    assert [item.evaluation_id for item in summaries] == [
        item.evaluation_id for item in reversed(saved)
    ]
    assert all(item.is_corrupted is False for item in summaries)
    assert all(item.corruption_reason == "" for item in summaries)
    assert all(item.product_name == saved[0].product_name for item in summaries)
    assert loaded is not None and loaded[0].inputs["actual"].value == "15"
    assert [record for record in caplog.records if record.levelno == logging.WARNING] == []


def test_evaluation_summary_remains_backward_compatible():
    summary = EvaluationSummary(
        evaluation_id="id",
        created_at=datetime.now(timezone.utc),
        evaluation_date=date(2026, 2, 1),
        standard_id="gb-00000-2026",
        standard_number="GB 00000-2026",
        product_id="product",
    )
    assert summary.is_corrupted is False
    assert summary.corruption_reason == ""
    assert summary.standard_title == "" and summary.product_name == ""


def test_repository_exposes_corruption_only_for_damaged_rows(context, caplog):
    """Repository-level contract: 好行不受坏行影响，坏行标记 + WARNING。"""
    good = save_evaluation(context, "15")
    corrupted = save_evaluation(context, "25")
    corrupt_result_json(context, corrupted.evaluation_id)
    repository = SqlEvaluationRepository(context.database, context.audit)

    with caplog.at_level(logging.WARNING):
        summaries = repository.list_recent()

    flags = {item.evaluation_id: item.is_corrupted for item in summaries}
    assert flags == {good.evaluation_id: False, corrupted.evaluation_id: True}
    assert len([record for record in caplog.records if record.levelno == logging.WARNING]) == 1

    with pytest.raises(StorageCorruptionError):
        repository.get(corrupted.evaluation_id)


def test_detail_dialog_not_opened_for_corrupted_record(context, qt_app, monkeypatch):
    corrupted = save_evaluation(context, "15")
    corrupt_result_json(context, corrupted.evaluation_id)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)

    window = MainWindow(context)
    try:
        select_record(window, corrupted.evaluation_id)
        window.view_selected_record()
        dialog = getattr(window, "record_detail_dialog", None)
        assert dialog is None or not dialog.findChild(QTextEdit, "record_detail_content")
    finally:
        window.close()


def test_lifecycle_payload_untouched_for_soft_deleted_neighbour(context):
    """删除 + 损坏并存时，各自语义互不干扰。"""
    corrupted = save_evaluation(context, "15")
    deleted = save_evaluation(context, "25")
    healthy = save_evaluation(context, "35")
    corrupt_result_json(context, corrupted.evaluation_id)
    context.application.delete_evaluation(deleted.evaluation_id)

    summaries = context.application.list_recent_evaluations()
    assert [item.evaluation_id for item in summaries] == [
        healthy.evaluation_id,
        corrupted.evaluation_id,
    ]
    assert summaries[1].is_corrupted is True
    assert all(item.evaluation_id != deleted.evaluation_id for item in summaries)


def test_degraded_row_still_uses_original_database_columns(context):
    """降级展示只回退到数据库原始列，不重算、不改写其它 JSON。"""
    corrupted = save_evaluation(context, "15")
    corrupt_result_json(context, corrupted.evaluation_id)

    summary = context.application.list_recent_evaluations()[0]
    assert summary.evaluation_id == corrupted.evaluation_id
    assert summary.standard_id == "gb-00000-2026"
    assert summary.standard_number == "GB 00000-2026"
    assert summary.product_id == "product"
    assert summary.evaluation_date == make_standard().effective_date
    assert summary.organization_name == "损坏记录测试企业"

    with context.database.engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT request_json, rule_snapshot_json, deleted_at FROM evaluations "
                "WHERE evaluation_id=:eid"
            ),
            {"eid": corrupted.evaluation_id},
        ).one()
    assert json.loads(row.request_json)["product_id"] == "product"
    assert json.loads(row.rule_snapshot_json)["id"] == "gb-00000-2026"
    assert row.deleted_at is None


def test_corruption_reason_is_chinese_and_reaches_the_ui_message(context):
    corrupted = save_evaluation(context, "15")
    corrupt_result_json(context, corrupted.evaluation_id)
    reason = context.application.list_recent_evaluations()[0].corruption_reason
    assert any("\u4e00" <= char <= "\u9fff" for char in reason), "不得把 ASCII pydantic 文本直接给 UI"
    assert _friendly_error(StorageCorruptionError(reason), "导出Excel") == f"导出Excel：{reason}"
