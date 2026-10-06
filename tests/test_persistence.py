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


def test_safety_backup_carries_only_user_business_data(tmp_path: Path) -> None:
    """安全备份（``create`` 默认范围）只含用户业务数据：数据库，别的一律不带。

    这是 Phase 7 的备份语义契约：迁移前 / 安装前 / 恢复前的安全备份只负责不可重建的
    用户业务数据；标准包、标准原文 PDF、bundled 资源、缓存和日志都是可重建的应用数据，
    不再因为「整棵 ``standards/`` 被复制」而进入安全备份。
    """
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    standard = make_standard()
    standards.install(standard)
    # 活目录里确实存在可重建的应用数据（旧版遗留 PDF 就是这样被打包进备份的）。
    (paths.standards / "source.pdf").write_bytes(b"pdf-placeholder")
    (paths.imports / "input.xlsx").write_bytes(b"import-placeholder")
    (paths.logs / "old.log").write_bytes(b"log-placeholder")

    service = BackupService(paths, database, audit)
    backup = service.create(tmp_path / "safety.uebackup")

    with zipfile.ZipFile(backup) as archive:
        members = set(archive.namelist())
    assert members == {"uebench.sqlite3", "manifest.json"}, members
    manifest = service.validate(backup)
    assert manifest["scope"] == "user-data"
    assert manifest["schema_version"] == "1.0"
    assert set(manifest["files"]) == {"uebench.sqlite3"}

    # 恢复：用户业务记录回来，而安全备份不拥有的活目录内容不被删除。
    with database.session() as session:
        from uebench.infrastructure.database import StandardRow

        session.query(StandardRow).delete()
    assert standards.list_published() == []

    service.restore(backup)
    assert standards.get_published(standard.id) is not None
    assert (paths.standards / "source.pdf").read_bytes() == b"pdf-placeholder"
    assert (paths.imports / "input.xlsx").read_bytes() == b"import-placeholder"
    assert (paths.logs / "old.log").read_bytes() == b"log-placeholder"
    # 恢复前的安全备份同样只含数据库：恢复本身也不会把 PDF 带进任何安全备份。
    pre_restore = sorted(paths.backups.glob("pre-restore-*.uebackup"))
    assert len(pre_restore) == 1, [path.name for path in pre_restore]
    with zipfile.ZipFile(pre_restore[0]) as archive:
        assert set(archive.namelist()) == {"uebench.sqlite3", "manifest.json"}


def test_full_environment_backup_keeps_and_restores_application_data(tmp_path: Path) -> None:
    """用户主动的全环境备份（``create_full_environment``）仍然是一份自包含归档。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    standard = make_standard()
    standards.install(standard)
    (paths.standards / "source.pdf").write_bytes(b"pdf-placeholder")
    (paths.imports / "input.xlsx").write_bytes(b"import-placeholder")
    (paths.logs / "old.log").write_bytes(b"log-placeholder")

    service = BackupService(paths, database, audit)
    backup = service.create_full_environment(tmp_path / "full.uebackup")

    manifest = service.validate(backup)
    assert manifest["scope"] == "full-environment"
    assert {"standards/source.pdf", "imports/input.xlsx", "logs/old.log"} <= set(
        manifest["files"]
    )

    # 破坏恢复目标：数据库行与活目录里的应用数据全部删掉。
    with database.session() as session:
        from uebench.infrastructure.database import StandardRow

        session.query(StandardRow).delete()
    (paths.standards / "source.pdf").unlink()
    (paths.imports / "input.xlsx").unlink()
    (paths.logs / "old.log").unlink()

    service.restore(backup)
    assert standards.get_published(standard.id) is not None
    assert (paths.standards / "source.pdf").read_bytes() == b"pdf-placeholder"
    assert (paths.imports / "input.xlsx").read_bytes() == b"import-placeholder"
    assert (paths.logs / "old.log").read_bytes() == b"log-placeholder"


def test_restore_never_deletes_live_application_data_it_does_not_own(tmp_path: Path) -> None:
    """全环境备份恢复是「就地合并」：归档之后新产生的可重建数据不被删除。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    standards.install(make_standard())
    (paths.standards / "source.pdf").write_bytes(b"pdf-placeholder")

    service = BackupService(paths, database, audit)
    backup = service.create_full_environment(tmp_path / "full.uebackup")
    later = paths.standards / "installed-after-the-backup" / "corrections.json"
    later.parent.mkdir(parents=True)
    later.write_bytes(b'{"corrections":[]}')

    service.restore(backup)

    assert later.read_bytes() == b'{"corrections":[]}'
    assert (paths.standards / "source.pdf").read_bytes() == b"pdf-placeholder"


def test_validate_rejects_a_safety_backup_that_carries_application_data(tmp_path: Path) -> None:
    """自述为安全备份（user-data）却带应用数据 → 拒绝；旧归档按全环境读。"""
    _paths, database, audit = setup_database(tmp_path)
    service = BackupService(AppPaths.from_root(tmp_path / "appdata"), database, audit)

    payload = b"%PDF-1.4 legacy"
    inconsistent = tmp_path / "inconsistent.uebackup"
    manifest = {
        "schema_version": "1.0",
        "backup_id": "inconsistent",
        "scope": "user-data",
        "files": {"uebench.sqlite3": "0" * 64, "standards/legacy.pdf": "1" * 64},
    }
    with zipfile.ZipFile(inconsistent, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("uebench.sqlite3", b"db")
        archive.writestr("standards/legacy.pdf", payload)
    with pytest.raises(BackupValidationError, match="不得包含可重建的应用数据"):
        service.validate(inconsistent)

    # 拆分之前写下的归档没有 scope 字段：它们确实带整棵 standards/，按全环境读。
    historical = tmp_path / "historical.uebackup"
    historical_manifest = {
        "schema_version": "1.0",
        "backup_id": "historical",
        "files": {"uebench.sqlite3": "0" * 64},
    }
    with zipfile.ZipFile(historical, "w") as archive:
        archive.writestr("manifest.json", json.dumps(historical_manifest))
        archive.writestr("uebench.sqlite3", b"db")
    # 哈希不匹配才是这里的失败原因，范围本身被接受（不再是「不支持的备份范围」）。
    with pytest.raises(BackupValidationError, match="哈希错误|备份缺少文件"):
        service.validate(historical)


def test_restore_still_reads_a_pre_split_full_archive(tmp_path: Path) -> None:
    """拆分之前写下的归档（无 ``scope`` 字段）仍按全环境读取并真实恢复。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    standard = make_standard()
    standards.install(standard)
    (paths.standards / "legacy-source.pdf").write_bytes(b"%PDF-1.4 legacy")

    service = BackupService(paths, database, audit)
    modern = service.create_full_environment(tmp_path / "modern.uebackup")
    historical = tmp_path / "historical.uebackup"
    with zipfile.ZipFile(modern) as source, zipfile.ZipFile(historical, "w") as target:
        for name in source.namelist():
            payload = source.read(name)
            if name == "manifest.json":
                document = json.loads(payload)
                document.pop("scope", None)
                payload = json.dumps(
                    document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            target.writestr(name, payload)
    stored = json.loads(zipfile.ZipFile(historical).read("manifest.json"))
    assert "scope" not in stored, "用例前提：模拟拆分之前写下的归档"

    # 范围由校验层归一化为 full-environment（缺字段不得读成安全备份）。
    assert service.validate(historical)["scope"] == "full-environment"

    with database.session() as session:
        from uebench.infrastructure.database import StandardRow

        session.query(StandardRow).delete()
    (paths.standards / "legacy-source.pdf").unlink()

    service.restore(historical)
    assert standards.get_published(standard.id) is not None
    assert (paths.standards / "legacy-source.pdf").read_bytes() == b"%PDF-1.4 legacy"
    # 恢复行为与归档范围一致地记入审计。
    restore_rows = [entry for entry in audit.list_recent(50) if entry.action == "BACKUP_RESTORE"]
    assert restore_rows and json.loads(restore_rows[0].details_json)["scope"] == "full-environment"


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