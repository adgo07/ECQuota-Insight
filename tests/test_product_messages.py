"""C-DEF-001/002：真实 Qt 弹窗、取消语义与合成数据恢复保护。"""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from zipfile import BadZipFile, ZipFile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import text

from uebench.application.backup_errors import BackupValidationError, RestoreSafetyError
from uebench.bootstrap import create_context
from uebench.ui.main_window import MainWindow, _restore_failure_message
from uebench.ui.message_box_text import install_chinese_message_box_buttons
from .test_gb29446_record_lifecycle import request_r2, standard_r2


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    install_chinese_message_box_buttons()
    return application


def interact_with_modal(callback, errors):
    """真实事件循环内执行检查；失败也关闭弹窗，避免测试永远等待。"""
    def interact():
        box = QApplication.activeModalWidget()
        try:
            assert isinstance(box, QMessageBox)
            box.activateWindow()
            box.windowHandle().requestActivate()
            assert QTest.qWaitForWindowActive(box, 1000)
            callback(box)
            def watchdog():
                try:
                    if box.isVisible():
                        errors.append(AssertionError("模拟输入未关闭弹窗"))
                        box.done(QMessageBox.StandardButton.No)
                except RuntimeError:
                    pass  # 静态 QMessageBox 已释放。
            QTimer.singleShot(1500, watchdog)
        except BaseException as exc:
            errors.append(exc)
            if isinstance(box, QMessageBox):
                box.done(QMessageBox.StandardButton.No)
    QTimer.singleShot(10, interact)


@pytest.mark.parametrize("action,expected", [
    ("return", QMessageBox.StandardButton.No),
    ("escape", QMessageBox.StandardButton.No),
    ("close", QMessageBox.StandardButton.No),
    ("mouse_yes", QMessageBox.StandardButton.Yes),
    ("mouse_no", QMessageBox.StandardButton.No),
    ("alt_y", QMessageBox.StandardButton.Yes),
    ("alt_n", QMessageBox.StandardButton.No),
])
def test_real_chinese_confirmation_keeps_default_cancel_and_input_semantics(app, action, expected):
    errors = []
    def respond(box):
        yes = box.button(QMessageBox.StandardButton.Yes)
        no = box.button(QMessageBox.StandardButton.No)
        assert yes.text() == "确认(&Y)" and no.text() == "取消(&N)"
        assert box.defaultButton() is no
        assert box.buttonRole(yes) == QMessageBox.ButtonRole.YesRole
        assert box.buttonRole(no) == QMessageBox.ButtonRole.NoRole
        if action == "return": QTest.keyClick(box, Qt.Key.Key_Return)
        elif action == "escape": QTest.keyClick(box, Qt.Key.Key_Escape)
        elif action == "close": box.close()
        elif action == "mouse_yes": QTest.mouseClick(yes, Qt.MouseButton.LeftButton)
        elif action == "mouse_no": QTest.mouseClick(no, Qt.MouseButton.LeftButton)
        elif action == "alt_y": QTest.keyClick(box, Qt.Key.Key_Y, Qt.KeyboardModifier.AltModifier)
        elif action == "alt_n": QTest.keyClick(box, Qt.Key.Key_N, Qt.KeyboardModifier.AltModifier)
    interact_with_modal(respond, errors)
    result = QMessageBox.question(None, "确认恢复", "是否继续？",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
    assert not errors, errors
    assert result == expected


@pytest.mark.parametrize("kind,title", [("information", "计算完成"), ("warning", "导出提示"), ("critical", "恢复失败")])
def test_real_notice_and_error_buttons_are_chinese(app, kind, title):
    errors = []
    def respond(box):
        button = box.button(QMessageBox.StandardButton.Ok)
        assert button.text() == "确定"
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    interact_with_modal(respond, errors)
    result = getattr(QMessageBox, kind)(None, title, "提示正文")
    assert not errors, errors
    assert result == QMessageBox.StandardButton.Ok


@pytest.mark.parametrize("exception,expected", [
    (BadZipFile("File is not a zip file"), "备份无效"),
    (BackupValidationError("备份文件哈希错误：private-path"), "备份无效"),
    (PermissionError("Access denied private-path"), "读取和写入权限"),
    (FileNotFoundError("private-path"), "路径不可用"),
    (NotADirectoryError("private-path"), "路径不可用"),
    (IsADirectoryError("private-path"), "路径不可用"),
    (OSError(28, "No space left on device private-path"), "磁盘空间"),
    (RuntimeError("Traceback 技术错误 private-path"), "核对当前记录状态"),
])
def test_restore_errors_are_classified_without_evaluation_or_technical_details(exception, expected):
    message = _restore_failure_message(exception)
    assert expected in message
    for fragment in ("输入数据", "单位", "适用条件", "private-path", "Traceback", "未被修改", "数据未变"):
        assert fragment not in message


def test_restore_safety_error_keeps_the_actual_rollback_instructions():
    # 原导入路径仍指向同一类型；UI 无须穿透 infrastructure 层。
    from uebench.infrastructure.backup import RestoreSafetyError as OriginalError
    assert OriginalError is RestoreSafetyError
    message = "恢复失败，且无法自动回滚原数据库。请勿继续写入，可用恢复前安全备份恢复。"
    assert _restore_failure_message(RestoreSafetyError(message)) == message


@pytest.fixture
def window_context(tmp_path, app):
    context = create_context(tmp_path / "独立 合成数据")
    standard = standard_r2()
    context.standards.install(standard)
    for electricity in ("560", "600"):
        context.application.evaluate(request_r2(standard, electricity))
    window = MainWindow(context)
    try:
        yield window, context, standard
    finally:
        window.close()
        context.database.dispose()


def evaluation_rows(context):
    with context.database.engine.connect() as connection:
        return [tuple(row) for row in connection.execute(text("SELECT * FROM evaluations ORDER BY evaluation_id"))]


def select_backup(monkeypatch, archive):
    monkeypatch.setattr("uebench.ui.main_window.QFileDialog.getOpenFileName", lambda *a: (str(archive), ""))


def test_bad_backup_real_ui_shows_actionable_error_and_preserves_all_record_bytes(window_context, tmp_path, monkeypatch):
    window, context, _ = window_context
    archive = tmp_path / "损坏 合成备份.uebackup"
    archive.write_text("INTENTIONALLY INVALID SYNTHETIC BACKUP", encoding="utf-8")
    select_backup(monkeypatch, archive)
    before = evaluation_rows(context)
    backups = set(context.paths.backups.glob("*.uebackup"))
    errors, dialogs = [], []
    def confirm(box):
        assert box.windowTitle() == "确认恢复"
        assert box.defaultButton() is box.button(QMessageBox.StandardButton.No)
        assert box.button(QMessageBox.StandardButton.Yes).text() == "恢复并替换(&Y)"
        interact_with_modal(dismiss_error, errors)
        QTest.mouseClick(box.button(QMessageBox.StandardButton.Yes), Qt.MouseButton.LeftButton)
    def dismiss_error(box):
        dialogs.append((box.windowTitle(), box.text()))
        assert box.button(QMessageBox.StandardButton.Ok).text() == "确定"
        QTest.mouseClick(box.button(QMessageBox.StandardButton.Ok), Qt.MouseButton.LeftButton)
    interact_with_modal(confirm, errors)
    window.restore_backup()
    assert not errors, errors
    assert len(dialogs) == 1 and dialogs[0][0] == "恢复失败"
    assert "备份无效" in dialogs[0][1] and ".uebackup" in dialogs[0][1]
    assert evaluation_rows(context) == before
    assert set(context.paths.backups.glob("*.uebackup")) == backups


@pytest.mark.parametrize("action", ["return", "escape", "close"])
def test_restore_cancellation_never_calls_the_restore_service(window_context, tmp_path, monkeypatch, action):
    window, context, _ = window_context
    select_backup(monkeypatch, tmp_path / "未实际读取.uebackup")
    monkeypatch.setattr(context.application, "restore_backup", lambda *_: pytest.fail("取消不得调用恢复服务"))
    before = evaluation_rows(context)
    errors = []
    def cancel(box):
        assert box.defaultButton() is box.button(QMessageBox.StandardButton.No)
        if action == "return": QTest.keyClick(box, Qt.Key.Key_Return)
        elif action == "escape": QTest.keyClick(box, Qt.Key.Key_Escape)
        else: box.close()
    interact_with_modal(cancel, errors)
    window.restore_backup()
    assert not errors, errors
    assert evaluation_rows(context) == before


@pytest.mark.parametrize("action", ["return", "escape", "close", "confirm"])
def test_delete_confirmation_keeps_cancel_and_soft_delete_semantics(window_context, action):
    window, context, _ = window_context
    window.refresh_records()
    window.record_table.selectRow(0)
    before = evaluation_rows(context)
    errors = []
    def respond(box):
        assert box.windowTitle() == "确认删除"
        assert box.defaultButton() is box.button(QMessageBox.StandardButton.No)
        assert box.button(QMessageBox.StandardButton.Yes).text() == "删除记录(&Y)"
        assert box.button(QMessageBox.StandardButton.No).text() == "取消(&N)"
        if action == "return": QTest.keyClick(box, Qt.Key.Key_Return)
        elif action == "escape": QTest.keyClick(box, Qt.Key.Key_Escape)
        elif action == "close": box.close()
        else: QTest.mouseClick(box.button(QMessageBox.StandardButton.Yes), Qt.MouseButton.LeftButton)
    interact_with_modal(respond, errors)
    window.delete_selected_record()
    assert not errors, errors
    if action == "confirm":
        assert context.application.count_evaluations() == 1
        assert len(evaluation_rows(context)) == len(before)  # 仍然是软删除。
    else:
        assert evaluation_rows(context) == before


@pytest.mark.parametrize("refresh_fails", [False, True])
def test_valid_ui_restore_keeps_safety_backup_and_does_not_overpromise_post_failure(
    window_context, tmp_path, monkeypatch, refresh_fails
):
    window, context, standard = window_context
    expected = evaluation_rows(context)
    archive = context.application.create_backup(tmp_path / "有效 合成备份.uebackup")
    context.application.evaluate(request_r2(standard, "700"))
    assert len(evaluation_rows(context)) == 3
    select_backup(monkeypatch, archive)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    errors, notices = [], []
    monkeypatch.setattr(QMessageBox, "critical", lambda parent, title, message: errors.append(message))
    monkeypatch.setattr(QMessageBox, "information", lambda parent, title, message: notices.append((title, message)))
    if refresh_fails:
        def fail_refresh(): raise RuntimeError("Traceback private-path")
        monkeypatch.setattr(window, "refresh_all", fail_refresh)
    before_backups = set(context.paths.backups.glob("pre-restore-*.uebackup"))
    window.restore_backup()
    assert evaluation_rows(context) == expected
    safety = set(context.paths.backups.glob("pre-restore-*.uebackup")) - before_backups
    assert len(safety) == 1
    safety_file = safety.pop()
    assert context.backup_service.validate(safety_file)["scope"] == "user-data"
    safety_database = tmp_path / "恢复前安全副本.sqlite3"
    with ZipFile(safety_file) as backup:
        safety_database.write_bytes(backup.read("uebench.sqlite3"))
    with closing(sqlite3.connect(safety_database)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] == 3
    if refresh_fails:
        assert not notices and len(errors) == 1
        assert "核对当前记录状态" in errors[0]
        assert "未被修改" not in errors[0] and "数据未变" not in errors[0]
    else:
        assert not errors and notices == [("恢复完成", "数据已恢复。")]
