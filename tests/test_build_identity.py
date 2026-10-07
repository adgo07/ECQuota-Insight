"""ECQ-RS05 Part 2 — build identity reader and 诊断信息 rendering.

Covers the identity source contract (packaged payload first, development build
info second, unknown placeholder otherwise), the malformed-file tolerance, and
the read-only diagnostics text the 关于 / 诊断信息 dialog shows and copies.

The reader lives in ``uebench.application.build_identity`` and must stay
UI-neutral; the dialog only formats.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from uebench.application.build_identity import (
    RECONCILIATION_NOT_EXECUTED,
    UNKNOWN_BUILD_IDENTITY,
    BuildIdentity,
    DiagnosticsFacts,
    identity_file_candidates,
    load_build_identity,
    read_build_identity,
    reconciliation_facts,
    render_diagnostics,
)

ROOT = Path(__file__).resolve().parents[1]
DEFINITION_PATH = ROOT / "data" / "definitions" / "gb-29446-2019.json"
STANDARD_ID = "gb-29446-2019"

WELL_FORMED_IDENTITY = {
    "schema": "ecq.build-identity.v1",
    "product_version": "0.2.0",
    "candidate_id": "cand-rs05-20261004-1",
    "source_commit": "a" * 40,
    "source_dirty": False,
    "standard_package_id": "pkg-bundled-initial",
    "standard_data_version": "2026.09-published.2",
    "standard_package_sha256": "b" * 64,
    "build_time_utc": "2026-10-04T00:00:00Z",
}


def _write_identity(directory: Path, document: dict, *, name: str = "build-identity.json") -> Path:
    path = directory / name
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 1. Well-formed identity file
# ---------------------------------------------------------------------------


def test_reads_well_formed_build_identity_from_temp_dir(tmp_path: Path) -> None:
    path = _write_identity(tmp_path, WELL_FORMED_IDENTITY)

    identity = read_build_identity(path)

    assert identity.embedded is True
    assert identity.source_path == path
    assert identity.schema == "ecq.build-identity.v1"
    assert identity.product_version == "0.2.0"
    assert identity.candidate_id == "cand-rs05-20261004-1"
    assert identity.source_commit == "a" * 40
    assert len(identity.source_commit) == 40
    assert identity.source_dirty is False
    assert identity.source_dirty_text == "否"
    assert identity.standard_package_id == "pkg-bundled-initial"
    assert identity.standard_data_version == "2026.09-published.2"
    assert identity.standard_package_sha256 == "b" * 64
    assert identity.build_time_utc == "2026-10-04T00:00:00Z"

    # The priority-based loader returns the same fields for a supplied candidate.
    loaded = load_build_identity([tmp_path / "missing.json", path])
    assert loaded == identity


def test_identity_files_may_be_loaded_without_a_payload_tree_sha(tmp_path: Path) -> None:
    """The embedded subset deliberately has no ``payload_tree_sha256`` key."""

    assert "payload_tree_sha256" not in WELL_FORMED_IDENTITY
    identity = read_build_identity(_write_identity(tmp_path, WELL_FORMED_IDENTITY))
    assert identity.embedded is True


# ---------------------------------------------------------------------------
# 2. No identity file anywhere → unknown placeholder, never an exception
# ---------------------------------------------------------------------------


def test_missing_identity_reports_unknown_placeholder(tmp_path: Path) -> None:
    identity = load_build_identity(
        [tmp_path / "build-identity.json", tmp_path / "nested" / "release-build-info.json"]
    )

    assert identity.embedded is False
    assert identity.source_path is None
    for value in (
        identity.product_version,
        identity.candidate_id,
        identity.source_commit,
        identity.standard_package_id,
        identity.standard_data_version,
        identity.standard_package_sha256,
        identity.build_time_utc,
    ):
        assert value == UNKNOWN_BUILD_IDENTITY

    text = render_diagnostics(identity, DiagnosticsFacts())
    assert UNKNOWN_BUILD_IDENTITY in text

    # The default candidates must never raise either, whatever the checkout has.
    assert isinstance(load_build_identity(), BuildIdentity)


def test_identity_candidate_order_prefers_packaged_payload() -> None:
    candidates = identity_file_candidates()

    assert candidates[0].name == "build-identity.json"
    assert candidates[0].parent.name == "resources"
    assert candidates[0].parent.parent.name == "uebench"
    assert candidates[-1] == ROOT / "dist" / "release" / "release-build-info.json"


# ---------------------------------------------------------------------------
# 3. Malformed identity files are ignored without raising
# ---------------------------------------------------------------------------


def test_malformed_identity_file_is_ignored(tmp_path: Path) -> None:
    broken = tmp_path / "broken" / "build-identity.json"
    broken.parent.mkdir()
    broken.write_text("{ this is not json", encoding="utf-8")
    assert read_build_identity(broken).embedded is False

    not_an_object = tmp_path / "array.json"
    not_an_object.write_text("[1, 2, 3]", encoding="utf-8")
    assert read_build_identity(not_an_object) == BuildIdentity()

    # A directory (or any unreadable path) is treated exactly like a missing file.
    assert read_build_identity(tmp_path).embedded is False

    # A later valid candidate still wins over a malformed earlier one.
    valid = _write_identity(tmp_path, WELL_FORMED_IDENTITY, name="good.json")
    assert load_build_identity([broken, valid]).embedded is True


def test_partial_identity_falls_back_per_field(tmp_path: Path) -> None:
    path = _write_identity(tmp_path, {"schema": "ecq.build-identity.v1", "candidate_id": "cand-only"})

    identity = read_build_identity(path)

    assert identity.embedded is True
    assert identity.candidate_id == "cand-only"
    assert identity.source_commit == UNKNOWN_BUILD_IDENTITY
    assert identity.source_dirty is None
    assert identity.source_dirty_text == UNKNOWN_BUILD_IDENTITY


# ---------------------------------------------------------------------------
# 4. Rendered diagnostics text
# ---------------------------------------------------------------------------


def test_rendered_diagnostics_text_has_all_required_fields(tmp_path: Path) -> None:
    identity = BuildIdentity(
        schema="ecq.build-identity.v1",
        product_version="0.2.0",
        candidate_id="cand-render",
        source_commit="c" * 40,
        source_dirty=True,
        standard_package_id="pkg-bundled",
        standard_data_version="2026.09-published.2",
        standard_package_sha256="d" * 64,
        build_time_utc="2026-10-04T00:00:00Z",
        embedded=True,
        source_path=tmp_path / "build-identity.json",
    )
    facts = DiagnosticsFacts(
        product_version="9.9.9",
        data_directory=str(tmp_path),
        db_schema_revision="0007",
        gb29446_rule_revision="3",
        bundled_package_id="pkg-bundled",
        bundled_package_data_version="2026.09-published.2",
        installed_package_id="pkg-installed",
        installed_package_data_version="2026.10-published.1",
        installed_package_sha256="e" * 64,
    )

    text = render_diagnostics(identity, facts)

    assert "9.9.9" in text
    assert str(tmp_path) in text
    assert "0007" in text
    assert "rule_revision：3" in text
    assert "pkg-bundled" in text
    assert "pkg-installed" in text
    assert "2026.10-published.1" in text
    assert "e" * 64 in text
    assert "c" * 40 in text
    assert "（source_dirty）：是" in text
    assert "BEGIN PRIVATE KEY" not in text
    assert "PRIVATE KEY" not in text


def test_window_diagnostics_report_contains_live_facts_without_private_keys(
    tmp_path: Path,
) -> None:
    """Drive the real window: 数据目录 / 产品版本 / DB schema / GB29446 rule_revision."""

    from PySide6.QtWidgets import QApplication

    from uebench import __version__
    from uebench.bootstrap import create_context
    from uebench.domain.models import StandardDefinition
    from uebench.ui.main_window import MainWindow

    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    definition = StandardDefinition.model_validate_json(
        DEFINITION_PATH.read_text(encoding="utf-8")
    )
    context.standards.install(definition)

    window = MainWindow(context)
    try:
        text = window.diagnostics_report()

        assert str(context.paths.root) in text
        assert f"产品版本：{__version__}" in text
        revision = context.database.current_revision()
        assert revision, "隔离数据目录应写入 Alembic 版本标记"
        assert revision in text
        assert f"rule_revision：{definition.rule_revision}" in text
        assert "PRIVATE KEY" not in text
        assert "-----BEGIN" not in text

        # Copy-to-clipboard surface is plain text with exactly the shown content.
        window._copy_diagnostics(text)
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            assert clipboard.text() == text

        # 诊断信息仅从默认折叠的「设置 → 高级」进入。
        window.navigation.setCurrentRow(4)
        assert window.settings_page.advanced_toggle.isChecked() is False
        window.settings_page.advanced_toggle.click()
        window.settings_page.view_diagnostics_button.click()
        application.processEvents()
        assert window.diagnostics_content.toPlainText() == text
        assert window.diagnostics_content.isReadOnly()
        assert window.diagnostics_dialog.windowTitle() == "关于 / 诊断信息"
    finally:
        window.close()
        context.database.dispose()


# ---------------------------------------------------------------------------
# 5. 最近一次标准包对账（ECQ-RS05 §三 E/F）
# ---------------------------------------------------------------------------


def _conflict_outcome():
    """A synthetic ``conflict`` outcome, built from the real application type."""

    from uebench.application.package_reconciliation import (
        BundledPackageIdentity,
        InstalledPackageIdentity,
        ReconciliationAction,
        ReconciliationOutcome,
        ReconciliationReason,
    )

    bundled = BundledPackageIdentity(
        path="C:/payload/uebench/resources/initial-standard-package-published.uebench",
        package_id="pkg-bundled-2026.10",
        data_version="2026.10-published.3",
        package_sha256="b" * 64,
    )
    installed = InstalledPackageIdentity(
        package_id="pkg-installed-conflict",
        data_version="2026.10-published.3",
        package_sha256="c" * 64,
    )
    return ReconciliationOutcome(
        action=ReconciliationAction.CONFLICT,
        reason=ReconciliationReason.SAME_DATA_VERSION_DIFFERENT_IDENTITY,
        message="数据版本相同（2026.10-published.3）但包身份不同（已安装=pkg-installed-conflict，"
        "内置=pkg-bundled-2026.10），不覆盖已安装标准包。",
        installed_before=installed,
        bundled=bundled,
    )


def _noop_outcome():
    from uebench.application.package_reconciliation import (
        BundledPackageIdentity,
        InstalledPackageIdentity,
        ReconciliationAction,
        ReconciliationOutcome,
        ReconciliationReason,
    )

    bundled = BundledPackageIdentity(
        path="C:/payload/uebench/resources/initial-standard-package-published.uebench",
        package_id="pkg-same",
        data_version="2026.09-published.2",
        package_sha256="d" * 64,
    )
    installed = InstalledPackageIdentity(
        package_id="pkg-same",
        data_version="2026.09-published.2",
        package_sha256="d" * 64,
    )
    return ReconciliationOutcome(
        action=ReconciliationAction.NOOP,
        reason=ReconciliationReason.IDENTICAL_PACKAGE,
        message="内置标准包与已安装包完全相同（pkg-same / 2026.09-published.2），无需处理。",
        installed_before=installed,
        bundled=bundled,
    )


def test_diagnostics_text_includes_package_reconciliation_outcome() -> None:
    outcome = _conflict_outcome()
    facts = reconciliation_facts(outcome)

    text = render_diagnostics(BuildIdentity(), DiagnosticsFacts(), facts)

    assert "最近一次标准包对账" in text
    assert f"对账动作（action）：{outcome.action.value}" in text
    assert f"对账原因（reason）：{outcome.reason.value}" in text
    assert outcome.message in text
    assert "已安装标准包 package_id：pkg-installed-conflict" in text
    assert "已安装标准包 data_version：2026.10-published.3" in text
    assert "内置标准包 package_id：pkg-bundled-2026.10" in text
    assert "内置标准包 data_version：2026.10-published.3" in text
    # No backup was created for a refusal, so no backup path is claimed.
    assert "升级前备份路径" not in text
    assert "未达到期望状态" in text


def test_diagnostics_text_reports_backup_path_when_present() -> None:
    outcome = _conflict_outcome().model_copy(update={"backup_path": r"C:\data\backups\pre-upgrade.uebackup"})

    text = render_diagnostics(BuildIdentity(), DiagnosticsFacts(), reconciliation_facts(outcome))

    assert r"升级前备份路径：C:\data\backups\pre-upgrade.uebackup" in text


def test_diagnostics_text_reports_not_executed_when_facade_has_no_outcome() -> None:
    assert reconciliation_facts(None) is None

    text = render_diagnostics(BuildIdentity(), DiagnosticsFacts(), None)

    assert "最近一次标准包对账" in text
    assert RECONCILIATION_NOT_EXECUTED in text
    assert "未知" in text and "未执行" in text


def test_window_keeps_package_details_advanced_and_blocks_new_evaluations(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication

    from uebench.application.package_reconciliation import FORMAL_EVALUATION_MISMATCH_MESSAGE
    from uebench.bootstrap import create_context
    from uebench.domain.models import StandardDefinition
    from uebench.ui.main_window import MainWindow

    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata", enforce_standard_library_readiness=True)
    definition = StandardDefinition.model_validate_json(DEFINITION_PATH.read_text(encoding="utf-8"))
    context.standards.install(definition)
    from .test_gb29446 import _request
    historical_request = _request(definition, "炼焦煤", process="重介", electricity="560", raw_coal="100")
    historical_result = context.application.preview_evaluation(historical_request)
    context.evaluations.save(historical_request, historical_result, definition)
    outcome = _conflict_outcome()
    context.package_reconciliation._last_outcome = outcome
    context.application.record_package_reconciliation(outcome)

    window = MainWindow(context)
    try:
        assert window.context.application.formal_evaluation_block_message() == FORMAL_EVALUATION_MISMATCH_MESSAGE
        assert window.home_compatibility_notice.text() == FORMAL_EVALUATION_MISMATCH_MESSAGE
        assert not window.home_start_evaluation.isEnabled()
        assert not window.calculate_button.isEnabled()
        assert "package_id" not in window.home_compatibility_notice.text()
        assert "SHA" not in window.home_compatibility_notice.text()

        window.navigation.setCurrentRow(4)
        assert window.settings_page.advanced_toggle.isChecked() is False
        assert window.settings_page.advanced_content.isHidden()
        assert not hasattr(window, "package_history_table")
        assert not hasattr(window, "audit_table")
        window.settings_page.advanced_toggle.click()
        window.settings_page.view_diagnostics_button.click()
        application.processEvents()
        diagnostic_text = window.diagnostics_content.toPlainText()
        assert f"对账动作（action）：{outcome.action.value}" in diagnostic_text
        assert "pkg-installed-conflict" in diagnostic_text
        assert "package_id" in diagnostic_text

        # 错配仅暂停新正式评价；历史记录仍可列出并按已保存结果查看。
        from unittest.mock import patch
        from PySide6.QtWidgets import QTextEdit
        window.navigation.setCurrentRow(3)
        assert window.record_table.rowCount() == 1
        window.record_table.selectRow(0)
        with patch("uebench.domain.engine.EvaluationEngine.evaluate", side_effect=AssertionError("history view ran Engine")):
            window.view_selected_record()
        detail = window.record_detail_dialog.findChild(QTextEdit, "record_detail_content")
        assert detail is not None
        assert "选煤电力单耗" in detail.toPlainText()
        assert str(historical_result.results[0].actual_value) in detail.toPlainText()
    finally:
        window.close()
        context.database.dispose()


@pytest.mark.parametrize(
    ("action", "expected_message"),
    [
        ("noop", None),
        ("install", None),
        ("upgrade", None),
        ("no-downgrade", "mismatch"),
        ("conflict", "mismatch"),
        ("invalid", "install"),
        ("missing", "install"),
        ("unavailable", "install"),
    ],
)
def test_readiness_message_classifies_reconciliation_outcomes(action: str, expected_message: str | None) -> None:
    from uebench.application.package_reconciliation import (
        FORMAL_EVALUATION_INSTALLATION_MESSAGE,
        FORMAL_EVALUATION_MISMATCH_MESSAGE,
        PackageReconciliationService,
        ReconciliationAction,
        ReconciliationOutcome,
        ReconciliationReason,
    )

    reason_by_action = {
        "noop": ReconciliationReason.IDENTICAL_PACKAGE,
        "install": ReconciliationReason.NO_INSTALLED_PACKAGE,
        "upgrade": ReconciliationReason.BUNDLED_NEWER,
        "no-downgrade": ReconciliationReason.INSTALLED_NEWER,
        "conflict": ReconciliationReason.SAME_DATA_VERSION_DIFFERENT_IDENTITY,
        "invalid": ReconciliationReason.BUNDLED_INVALID,
        "missing": ReconciliationReason.NO_BUNDLED_PACKAGE,
        "unavailable": ReconciliationReason.PACKAGE_SERVICE_UNAVAILABLE,
    }
    service = PackageReconciliationService(None, data_version_key=lambda _value: None)
    service._last_outcome = ReconciliationOutcome(
        action=ReconciliationAction(action), reason=reason_by_action[action], message="diagnostic detail"
    )
    actual = service.formal_evaluation_block_message()
    if expected_message == "mismatch":
        assert actual == FORMAL_EVALUATION_MISMATCH_MESSAGE
    elif expected_message == "install":
        assert actual == FORMAL_EVALUATION_INSTALLATION_MESSAGE
    else:
        assert actual is None


@pytest.mark.parametrize(
    ("action", "reason", "message_kind"),
    [
        ("no-downgrade", "installed-data-version-newer", "mismatch"),
        ("conflict", "same-data-version-different-identity", "mismatch"),
        ("invalid", "bundled-invalid", "installation"),
    ],
)
def test_application_and_excel_formal_paths_stop_before_engine_when_library_is_blocked(
    action: str, reason: str, message_kind: str
) -> None:
    from types import SimpleNamespace
    from unittest.mock import Mock

    from uebench.application.facade import ApplicationFacade
    from uebench.application.package_reconciliation import (
        FORMAL_EVALUATION_INSTALLATION_MESSAGE,
        FORMAL_EVALUATION_MISMATCH_MESSAGE,
        PackageReconciliationService,
        ReconciliationAction,
        ReconciliationOutcome,
        ReconciliationReason,
    )
    from uebench.application.services import EvaluationService
    from uebench.domain.models import StandardDefinition
    from .test_gb29446 import _request

    standard = StandardDefinition.model_validate_json(DEFINITION_PATH.read_text(encoding="utf-8"))
    request = _request(standard, "炼焦煤", process="重介", electricity="560", raw_coal="100")
    expected_message = (
        FORMAL_EVALUATION_MISMATCH_MESSAGE
        if message_kind == "mismatch"
        else FORMAL_EVALUATION_INSTALLATION_MESSAGE
    )
    reconciliation = PackageReconciliationService(None, data_version_key=lambda _value: None)
    reconciliation._last_outcome = ReconciliationOutcome(
        action=ReconciliationAction(action),
        reason=ReconciliationReason(reason),
        message="diagnostic detail",
    )
    standards = Mock()
    evaluations = Mock()
    engine = Mock()
    service = EvaluationService(
        standards,
        evaluations,
        engine=engine,
        formal_evaluation_block=reconciliation.formal_evaluation_block_message,
    )
    importer = Mock()
    importer.prepare.return_value = SimpleNamespace(request=request)
    facade = ApplicationFacade(
        standards=standards,
        evaluations=evaluations,
        evaluation_service=service,
        import_service=importer,
    )

    assert facade.formal_evaluation_block_message() == expected_message
    phrase = "暂时不能新建评价" if message_kind == "mismatch" else "重新安装完整版本"
    with pytest.raises(ValueError, match=phrase):
        facade.evaluate(request)
    with pytest.raises(ValueError, match=phrase):
        facade.evaluate_workbook("batch-1")
    standards.get_for_evaluation.assert_not_called()
    engine.evaluate.assert_not_called()
    evaluations.save.assert_not_called()
    importer.mark_evaluated.assert_not_called()
