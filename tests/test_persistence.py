from datetime import date, datetime, timezone
import json
from pathlib import Path
import zipfile

import pytest
from sqlalchemy import text

from uebench.application import evaluation_support
from uebench.application.services import EvaluationService
from uebench.domain.models import AuditEntry, EvaluationRequest, EvaluationSummary, Grade, InputMode, InputValue
from uebench.infrastructure.backup import BackupService, BackupValidationError
from uebench.infrastructure.database import DatabaseManager, StandardRow
from uebench.infrastructure.paths import AppPaths
from uebench.infrastructure.repositories import (
    AuditRepository,
    SqlEvaluationRepository,
    SqlStandardRepository,
)

from .test_engine import make_standard


def _in_formal_scope(monkeypatch, *standard_ids: str) -> None:
    """把 ``standard_ids`` 声明为正式可评价（与 ``test_ui.py::_in_formal_scope`` 同模式）。

    正式评价范围是应用层的固定常量，**与“标准库里有没有这个标准”无关**（RS05 §三）。
    本文件覆盖的是**持久化**——往返一致、软删除可见性、备份恢复——不是范围本身；需要经
    ``EvaluationService.evaluate`` 真正落库的用例必须显式扩展真正的注册表。这里改的是
    注册表本身，因此产品行为仍然完全由注册表驱动。
    """
    extended = set(evaluation_support.SUPPORTED_EVALUATION_STANDARD_IDS) | set(standard_ids)
    monkeypatch.setattr(
        evaluation_support, "SUPPORTED_EVALUATION_STANDARD_IDS", frozenset(extended)
    )


def setup_database(tmp_path: Path):
    paths = AppPaths.from_root(tmp_path / "appdata")
    paths.ensure()
    database = DatabaseManager(paths.database)
    database.initialize()
    audit = AuditRepository(database)
    return paths, database, audit


def test_standard_and_evaluation_round_trip(tmp_path: Path, monkeypatch) -> None:
    _, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    evaluations = SqlEvaluationRepository(database, audit)
    standard = make_standard()
    standards.install(standard, "test-package")
    # 往返一致需要一条**正式**记录，因此把夹具标准显式放进注册表（RS05 §三）。
    _in_formal_scope(monkeypatch, standard.id)

    request = EvaluationRequest(
        evaluation_date=date(2026, 2, 2),
        standard_id=standard.id,
        product_id="product",
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="20", unit="kgce/t")},
    )
    result = EvaluationService(standards, evaluations).evaluate(request)
    loaded = evaluations.get(result.evaluation_id)
    assert loaded is not None
    assert loaded[1].results[0].grade is Grade.LEVEL_2
    assert loaded[2].source_sha256 == standard.source_sha256
    summaries = evaluations.list_recent()
    assert summaries and isinstance(summaries[0], EvaluationSummary)
    audit_entries = audit.list_recent()
    assert audit_entries and isinstance(audit_entries[0], AuditEntry)
    assert len(audit_entries) >= 2


def test_initialize_adopts_complete_pre_alembic_database(tmp_path: Path) -> None:
    paths = AppPaths.from_root(tmp_path / "legacy")
    paths.ensure()
    legacy = DatabaseManager(paths.database)
    from uebench.infrastructure.database import Base

    Base.metadata.create_all(legacy.engine)
    legacy.dispose()
    migrated = DatabaseManager(paths.database)
    migrated.initialize()
    with migrated.engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0003"
    migrated.dispose()


def test_list_published_returns_latest_version_per_standard(tmp_path: Path) -> None:
    _, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    first = make_standard()
    newer = first.model_copy(update={"number": "GB 00000-2027", "version": "2027", "effective_date": date(2027, 1, 1)})
    standards.install(first, "package-old")
    standards.install(newer, "package-new")
    published = standards.list_published()
    assert len(published) == 1
    assert published[0].version == "2027"
    assert standards.get_published(first.id).version == "2027"


def test_soft_delete_hides_evaluation(tmp_path: Path, monkeypatch) -> None:
    _, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    evaluations = SqlEvaluationRepository(database, audit)
    standard = make_standard()
    standards.install(standard)
    # 软删除需要一条**正式**记录，因此把夹具标准显式放进注册表（RS05 §三）。
    _in_formal_scope(monkeypatch, standard.id)
    request = EvaluationRequest(
        evaluation_date=date(2026, 2, 2),
        standard_id=standard.id,
        product_id="product",
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="20", unit="kgce/t")},
    )
    result = EvaluationService(standards, evaluations).evaluate(request)
    assert evaluations.soft_delete(result.evaluation_id)
    assert evaluations.get(result.evaluation_id) is None


def test_backup_and_restore(tmp_path: Path) -> None:
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    standard = make_standard()
    standards.install(standard)
    (paths.standards / "source.pdf").write_bytes(b"pdf-placeholder")
    (paths.imports / "input.xlsx").write_bytes(b"import-placeholder")
    (paths.logs / "old.log").write_bytes(b"log-placeholder")

    service = BackupService(paths, database, audit)
    backup = service.create(tmp_path / "snapshot.uebackup")
    assert service.validate(backup)["schema_version"] == "1.0"

    with database.session() as session:
        from uebench.infrastructure.database import StandardRow

        session.query(StandardRow).delete()
    assert standards.list_published() == []

    service.restore(backup)
    assert standards.get_published(standard.id) is not None
    assert (paths.standards / "source.pdf").read_bytes() == b"pdf-placeholder"
    assert (paths.imports / "input.xlsx").read_bytes() == b"import-placeholder"
    assert (paths.logs / "old.log").read_bytes() == b"log-placeholder"


def test_backup_rejects_windows_path_traversal(tmp_path: Path) -> None:
    _paths, database, audit = setup_database(tmp_path)
    service = BackupService(AppPaths.from_root(tmp_path / "appdata"), database, audit)
    malicious = tmp_path / "malicious.uebackup"
    manifest = {
        "schema_version": "1.0",
        "backup_id": "malicious",
        "files": {"uebench.sqlite3": "0" * 64},
    }
    with zipfile.ZipFile(malicious, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr(r"standards\..\outside.txt", b"bad")
    with pytest.raises(BackupValidationError, match="不安全路径|未登记文件"):
        service.validate(malicious)


def test_backup_rejects_duplicate_members(tmp_path: Path) -> None:
    _paths, database, audit = setup_database(tmp_path)
    service = BackupService(AppPaths.from_root(tmp_path / "appdata"), database, audit)
    malicious = tmp_path / "duplicate.uebackup"
    manifest = {
        "schema_version": "1.0",
        "backup_id": "duplicate",
        "files": {"uebench.sqlite3": "0" * 64},
    }
    with zipfile.ZipFile(malicious, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("uebench.sqlite3", b"one")
        archive.writestr("uebench.sqlite3", b"two")
    with pytest.raises(BackupValidationError, match="重复文件"):
        service.validate(malicious)


def test_same_edition_prefers_higher_rule_revision_when_install_times_tie(tmp_path: Path) -> None:
    _, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    first = make_standard()
    second = first.model_copy(deep=True, update={"rule_revision": 2})
    second.products[0].indicators[0].thresholds.level_1.value = "11"
    standards.install(first, "package-r1")
    standards.install(second, "package-r2")

    tied_time = datetime(2026, 8, 1, tzinfo=timezone.utc)
    with database.session() as session:
        for row in session.query(StandardRow).all():
            row.installed_at = tied_time

    selected = standards.get_for_evaluation(first.id, date(2026, 8, 2))
    assert selected is not None
    assert selected.rule_revision == 2
    assert standards.list_current(date(2026, 8, 2))[0].rule_revision == 2
    assert standards.list_published()[0].rule_revision == 2