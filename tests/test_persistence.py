from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import zipfile

import pytest
from alembic import command
from sqlalchemy import text

from uebench.application import evaluation_support
from uebench.application.services import EvaluationService
from uebench.domain.models import AuditEntry, EvaluationRequest, EvaluationSummary, Grade, InputMode, InputValue
from uebench.infrastructure.backup import (
    BackupService,
    BackupValidationError,
    RestoreSafetyError,
    create_sqlite_snapshot,
)
from uebench.infrastructure.database import DatabaseManager, StandardRow
from uebench.infrastructure.paths import AppPaths
from uebench.infrastructure.repositories import (
    AuditRepository,
    SqlEvaluationRepository,
    SqlStandardRepository,
)

from .test_engine import make_standard
from .test_migration_backup import migrations_config, revision_of


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


# ---------------------------------------------------------------------------
# ECQ-RS05 M1：恢复链安全（H01 / H02）
#
# H01 = 恢复报告成功但数据还是旧的；H02 = 备份容器合法但内部 SQLite 无效、
# 不是本应用、或者是未来版本的 Schema。下面每个用例都是**真实**执行：
# 真实 SQLite、真实 .uebackup、真实 Alembic 迁移、真实子进程。
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]

#: 第二个真实进程：打开数据库并**读住**一个快照（真连接、真进程、真锁）。
_SECOND_PROCESS_READER = """
import sqlite3, sys, time

connection = sqlite3.connect(sys.argv[1], timeout=0.5)
connection.execute("PRAGMA busy_timeout=500")
connection.execute("BEGIN")
connection.execute("SELECT COUNT(*) FROM standards").fetchall()
print("ready", flush=True)
time.sleep(120)
"""

#: 第二个真实进程：持有同数据目录的恢复期互斥锁。
_SECOND_PROCESS_LOCK_HOLDER = """
import sys, time
from pathlib import Path

from uebench.infrastructure.backup import restore_exclusive_lock

with restore_exclusive_lock(Path(sys.argv[1])):
    print("held", flush=True)
    time.sleep(120)
"""


def _installed_numbers(database: DatabaseManager) -> list[str]:
    """活库当前的标准编号（排序），用来断言“恢复前后数据到底是什么”。"""
    with database.session() as session:
        rows = session.execute(text("SELECT number FROM standards ORDER BY number")).fetchall()
    return [str(row[0]) for row in rows]


def _archive_with_database(payload: bytes, destination: Path) -> Path:
    """构造一个**容器完全合法**（manifest + SHA256 都对）但数据库内容由用例决定的归档。

    H02 的前提就是“容器校验能过”：``validate()`` 只看清单与哈希，真正判断
    ``payload`` 能不能恢复，只能靠恢复链里的临时位置校验。
    """
    manifest = {
        "schema_version": "1.0",
        "backup_id": "crafted-by-test",
        "scope": "user-data",
        "files": {"uebench.sqlite3": hashlib.sha256(payload).hexdigest()},
    }
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("uebench.sqlite3", payload)
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
    return destination


def _snapshot_database(database: DatabaseManager, destination: Path) -> Path:
    """把活库快照成独立文件（候选库 payload 的来源）；快照用 online backup API。"""
    create_sqlite_snapshot(database.path, destination)
    return destination


def _leftover_restore_files(paths: AppPaths) -> list[str]:
    """恢复链必须自己收拾干净：不留半恢复的中间文件。"""
    return sorted(
        item.name
        for item in paths.root.iterdir()
        if item.name.endswith((".restore-staging", ".pre-restore-original"))
    )


def test_restore_returns_to_backup_state_after_restart(tmp_path: Path) -> None:
    """正常路径回归（H01）：备份 → 修改 → 恢复 → **重启**后确实回到备份状态。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    original = make_standard()
    standards.install(original, "test-package")
    service = BackupService(paths, database, audit)
    backup = service.create(tmp_path / "state.uebackup")

    # 备份之后的修改：真实写入，会在 WAL 里留下数据。
    with database.session() as session:
        session.query(StandardRow).delete()
    later = make_standard(standard_id="gb-99999-2026", standard_number="GB 99999-2026")
    standards.install(later, "later-package")
    assert _installed_numbers(database) == ["GB 99999-2026"]

    service.restore(backup)
    assert _installed_numbers(database) == [original.number]

    # 重启：关掉连接，换一个全新的 DatabaseManager 打开同一个文件。
    database.dispose()
    restarted = DatabaseManager(paths.database, paths=paths)
    try:
        restarted.initialize()
        with restarted.engine.connect() as connection:
            numbers = sorted(
                str(row[0]) for row in connection.execute(text("SELECT number FROM standards"))
            )
        assert numbers == [original.number]

        # 恢复后继续写入并再重启一次：既不能有旧 WAL 把备份后的数据“复活”，
        # 也不能有残留边车把新数据吃掉。
        SqlStandardRepository(restarted, AuditRepository(restarted)).install(
            make_standard(standard_id="gb-88888-2026", standard_number="GB 88888-2026"),
            "post-restore",
        )
    finally:
        restarted.dispose()

    again = DatabaseManager(paths.database, paths=paths)
    try:
        again.initialize()
        assert _installed_numbers(again) == sorted([original.number, "GB 88888-2026"])
    finally:
        again.dispose()


def test_restore_refuses_while_another_connection_reads_the_database(tmp_path: Path) -> None:
    """第二个真实连接持有读事务 → 拒绝恢复，原库不变，重试可用（H01）。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    original = make_standard()
    standards.install(original, "test-package")
    service = BackupService(paths, database, audit)
    backup = service.create(tmp_path / "state.uebackup")

    with database.session() as session:
        session.query(StandardRow).delete()
    standards.install(
        make_standard(standard_id="gb-99999-2026", standard_number="GB 99999-2026"),
        "later-package",
    )
    live_before = _installed_numbers(database)
    assert live_before == ["GB 99999-2026"]

    holder = sqlite3.connect(paths.database, timeout=0.5)
    holder.execute("PRAGMA busy_timeout=500")
    holder.execute("BEGIN")
    holder.execute("SELECT COUNT(*) FROM standards").fetchall()
    try:
        with pytest.raises(RestoreSafetyError) as caught:
            service.restore(backup)
        # 必须是能直接给用户看的中文拒绝理由。
        assert any("\u4e00" <= char <= "\u9fff" for char in str(caught.value))
        # 拒绝之后：活库内容一字未改，应用仍可用（连接已重建，无需手工修复）。
        assert _installed_numbers(database) == live_before
        assert _leftover_restore_files(paths) == []
    finally:
        holder.rollback()
        holder.close()

    # 持有者离开后，同一个归档可以正常恢复。
    service.restore(backup)
    assert _installed_numbers(database) == [original.number]
    assert _leftover_restore_files(paths) == []


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="已打开但从未读过的空闲连接只有 Windows 的文件句柄语义能检出（POSIX 已知限制）",
)
def test_restore_refuses_while_another_idle_connection_is_open(tmp_path: Path) -> None:
    """空闲连接（已打开、没读过、不建边车）→ 靠原子替换这一层拒绝（H01 兜底）。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    original = make_standard()
    standards.install(original, "test-package")
    service = BackupService(paths, database, audit)
    backup = service.create(tmp_path / "state.uebackup")

    with database.session() as session:
        session.query(StandardRow).delete()
    live_before = _installed_numbers(database)
    assert live_before == []

    idle = sqlite3.connect(paths.database, timeout=0.5)
    try:
        with pytest.raises(RestoreSafetyError, match="原数据库未被修改"):
            service.restore(backup)
        assert _installed_numbers(database) == live_before
        assert _leftover_restore_files(paths) == []
    finally:
        idle.close()

    service.restore(backup)
    assert _installed_numbers(database) == [original.number]


def test_restore_refuses_while_another_connection_writes_the_database(tmp_path: Path) -> None:
    """第二个连接正在写（写事务未提交）→ 拒绝恢复，原库不变（H01）。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    original = make_standard()
    standards.install(original, "test-package")
    service = BackupService(paths, database, audit)
    backup = service.create(tmp_path / "state.uebackup")

    live_before = _installed_numbers(database)
    writer = sqlite3.connect(paths.database, timeout=0.5)
    writer.execute("PRAGMA busy_timeout=500")
    writer.execute("BEGIN IMMEDIATE")
    writer.execute(
        "INSERT INTO audit_log (created_at, actor, action, entity_type, entity_id, details_json) "
        "VALUES (?, 'LocalUser', 'HOLDER_WRITE', 'backup', NULL, '{}')",
        (datetime.now(timezone.utc).isoformat(),),
    )
    try:
        with pytest.raises(RestoreSafetyError, match="恢复被拒绝"):
            service.restore(backup)
        assert _installed_numbers(database) == live_before
        assert _leftover_restore_files(paths) == []
    finally:
        writer.rollback()
        writer.close()

    service.restore(backup)
    assert _installed_numbers(database) == [original.number]


def _spawn_reader_process(database_path: Path) -> subprocess.Popen:
    process = subprocess.Popen(
        [sys.executable, "-c", _SECOND_PROCESS_READER, str(database_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    line = process.stdout.readline()
    assert "ready" in line, f"第二进程未就绪：{line!r}"
    return process


def test_restore_refuses_while_another_process_reads_the_database(tmp_path: Path) -> None:
    """第二个**真实进程**持有读快照 → 拒绝恢复，原库不变；进程退出后可恢复（H01）。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    original = make_standard()
    standards.install(original, "test-package")
    service = BackupService(paths, database, audit)
    backup = service.create(tmp_path / "state.uebackup")

    with database.session() as session:
        session.query(StandardRow).delete()
    standards.install(
        make_standard(standard_id="gb-99999-2026", standard_number="GB 99999-2026"),
        "later-package",
    )
    live_before = _installed_numbers(database)

    process = _spawn_reader_process(paths.database)
    try:
        with pytest.raises(RestoreSafetyError, match="恢复被拒绝"):
            service.restore(backup)
        assert _installed_numbers(database) == live_before
        assert _leftover_restore_files(paths) == []
    finally:
        process.kill()
        process.wait(timeout=30)

    service.restore(backup)
    assert _installed_numbers(database) == [original.number]


def test_restore_refuses_while_another_process_holds_the_restore_lock(tmp_path: Path) -> None:
    """同数据目录已有一次恢复在进行 → 拒绝排队，原库不变（H01 恢复期互斥）。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    original = make_standard()
    standards.install(original, "test-package")
    service = BackupService(paths, database, audit)
    backup = service.create(tmp_path / "state.uebackup")

    with database.session() as session:
        session.query(StandardRow).delete()
    live_before = _installed_numbers(database)

    process = subprocess.Popen(
        [sys.executable, "-c", _SECOND_PROCESS_LOCK_HOLDER, str(paths.database)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    try:
        line = process.stdout.readline()
        assert "held" in line, f"第二进程未拿到锁：{line!r}"
        with pytest.raises(RestoreSafetyError, match="恢复操作正在进行"):
            service.restore(backup)
        assert _installed_numbers(database) == live_before
    finally:
        process.kill()
        process.wait(timeout=30)

    # 进程退出即由操作系统释放锁，恢复可以继续。
    service.restore(backup)
    assert _installed_numbers(database) == [original.number]


def test_restore_rejects_a_non_sqlite_payload(tmp_path: Path) -> None:
    """H02：容器合法但内部根本不是 SQLite → 拒绝，原库不变。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    standards.install(make_standard(), "test-package")
    service = BackupService(paths, database, audit)
    live_before = _installed_numbers(database)

    archive = _archive_with_database(b"this is not a sqlite database at all", tmp_path / "foreign.uebackup")
    assert service.validate(archive)["scope"] == "user-data"  # 容器层放行

    with pytest.raises(BackupValidationError, match="不是有效的 SQLite 文件"):
        service.restore(archive)
    assert _installed_numbers(database) == live_before
    assert _leftover_restore_files(paths) == []


def test_restore_rejects_a_corrupted_sqlite_payload(tmp_path: Path) -> None:
    """H02：文件头合法但内容被破坏的 SQLite → 拒绝，原库不变。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    standards.install(make_standard(), "test-package")
    service = BackupService(paths, database, audit)
    live_before = _installed_numbers(database)

    snapshot = _snapshot_database(database, tmp_path / "snapshot.sqlite3")
    raw = bytearray(snapshot.read_bytes())
    assert bytes(raw[:16]) == b"SQLite format 3\x00"
    # 保留 16 字节文件头与文件头其余字段，把首页 btree 头往后全部打烂：
    # integrity_check 必须失败，而不是“看起来还能读”。
    raw[100:] = b"\xff" * (len(raw) - 100)
    archive = _archive_with_database(bytes(raw), tmp_path / "corrupt.uebackup")
    assert service.validate(archive)["scope"] == "user-data"  # 容器层放行

    with pytest.raises(BackupValidationError, match="损坏"):
        service.restore(archive)
    assert _installed_numbers(database) == live_before
    assert _leftover_restore_files(paths) == []


def test_restore_rejects_a_foreign_sqlite_payload(tmp_path: Path) -> None:
    """H02：是合法 SQLite，但不是本应用的库（同名表也不认）→ 拒绝，原库不变。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    standards.install(make_standard(), "test-package")
    service = BackupService(paths, database, audit)
    live_before = _installed_numbers(database)

    # (a) 完全无关的应用数据库。
    unrelated = tmp_path / "unrelated.sqlite3"
    connection = sqlite3.connect(unrelated)
    connection.execute("CREATE TABLE other_app_data (id INTEGER PRIMARY KEY, payload TEXT)")
    connection.execute("INSERT INTO other_app_data (payload) VALUES ('someone else')")
    connection.commit()
    connection.close()

    # (b) 只有部分同名表的“半套”数据库：缺受管表同样不算本应用。
    partial = tmp_path / "partial.sqlite3"
    connection = sqlite3.connect(partial)
    connection.execute("CREATE TABLE standards (number TEXT)")
    connection.execute("CREATE TABLE evaluations (id TEXT)")
    connection.execute("INSERT INTO standards VALUES ('GB 00000-1900')")
    connection.commit()
    connection.close()

    for index, candidate in enumerate((unrelated, partial)):
        archive = _archive_with_database(candidate.read_bytes(), tmp_path / f"foreign-{index}.uebackup")
        assert service.validate(archive)["scope"] == "user-data"  # 容器层放行
        with pytest.raises(BackupValidationError, match="不属于本软件"):
            service.restore(archive)
        assert _installed_numbers(database) == live_before

    assert _leftover_restore_files(paths) == []


def test_restore_rejects_a_future_schema_and_never_downgrades(tmp_path: Path) -> None:
    """H02：未来版本 Schema → 明确拒绝、不降级、提示安装匹配/更新版本。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    original = make_standard()
    standards.install(original, "test-package")
    service = BackupService(paths, database, audit)
    live_before = _installed_numbers(database)

    candidate = _snapshot_database(database, tmp_path / "future.sqlite3")
    connection = sqlite3.connect(candidate)
    connection.execute("UPDATE alembic_version SET version_num = '0004'")
    connection.commit()
    connection.close()
    archive = _archive_with_database(candidate.read_bytes(), tmp_path / "future.uebackup")
    assert service.validate(archive)["scope"] == "user-data"  # 容器层放行

    with pytest.raises(BackupValidationError, match="不会降级") as caught:
        service.restore(archive)
    message = str(caught.value)
    assert "0004" in message and "匹配或更新" in message

    # 活库既没有被换成未来版本，也没有被降级。
    assert revision_of(paths.database) == "0003"
    assert _installed_numbers(database) == live_before
    assert _leftover_restore_files(paths) == []


@pytest.mark.parametrize("variant", ["no-alembic-marker", "revision-0001"])
def test_restore_accepts_a_migratable_legacy_schema(tmp_path: Path, variant: str) -> None:
    """H02 正面：可迁移的旧 Schema 必须恢复成功，并在恢复后迁移到 head。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    original = make_standard()
    standards.install(original, "test-package")

    candidate = _snapshot_database(database, tmp_path / "legacy.sqlite3")
    if variant == "no-alembic-marker":
        # 早期用 SQLAlchemy 建表、还没接 Alembic 的完整数据库。
        connection = sqlite3.connect(candidate)
        connection.execute("DROP TABLE alembic_version")
        connection.commit()
        connection.close()
        with sqlite3.connect(candidate) as check:
            tables = {row[0] for row in check.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert "alembic_version" not in tables
    else:
        # 真实 Alembic downgrade 出来的 0001 结构。
        command.downgrade(migrations_config(candidate), "0001")
        assert revision_of(candidate) == "0001"
    archive = _archive_with_database(candidate.read_bytes(), tmp_path / "legacy.uebackup")
    service = BackupService(paths, database, audit)
    assert service.validate(archive)["scope"] == "user-data"  # 容器层放行

    with database.session() as session:
        session.query(StandardRow).delete()
    assert _installed_numbers(database) == []

    service.restore(archive)
    assert _installed_numbers(database) == [original.number]
    # 恢复之后由 initialize() 接管并迁移到 head。
    assert revision_of(paths.database) == "0003"
    assert _leftover_restore_files(paths) == []


def test_restore_staging_failure_leaves_the_database_untouched(
    tmp_path: Path, monkeypatch
) -> None:
    """磁盘写满（候选库落盘失败）→ 拒绝，原库不变，引擎仍可用（H01 注入）。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    original = make_standard()
    standards.install(original, "test-package")
    service = BackupService(paths, database, audit)
    backup = service.create(tmp_path / "state.uebackup")

    with database.session() as session:
        session.query(StandardRow).delete()
    live_before = _installed_numbers(database)

    real_copy2 = shutil.copy2

    def _no_space(source, destination, *args, **kwargs):
        if ".restore-staging" in str(destination):
            raise OSError(28, "No space left on device")
        return real_copy2(source, destination, *args, **kwargs)

    monkeypatch.setattr("uebench.infrastructure.backup.shutil.copy2", _no_space)
    with pytest.raises(RestoreSafetyError, match="原数据库未被修改"):
        service.restore(backup)
    monkeypatch.undo()

    assert _installed_numbers(database) == live_before
    assert _leftover_restore_files(paths) == []


def test_restore_switch_failure_leaves_the_database_untouched(
    tmp_path: Path, monkeypatch
) -> None:
    """原子切换被权限拒绝 → 拒绝，原库不变，引擎仍可用（H01 注入）。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    original = make_standard()
    standards.install(original, "test-package")
    service = BackupService(paths, database, audit)
    backup = service.create(tmp_path / "state.uebackup")

    with database.session() as session:
        session.query(StandardRow).delete()
    live_before = _installed_numbers(database)
    target = paths.database.resolve()

    real_replace = os.replace

    def _denied(source, destination, *args, **kwargs):
        if Path(str(destination)) == target:
            raise PermissionError(13, "Access is denied")
        return real_replace(source, destination, *args, **kwargs)

    monkeypatch.setattr("uebench.infrastructure.backup.os.replace", _denied)
    with pytest.raises(RestoreSafetyError, match="原数据库未被修改"):
        service.restore(backup)
    monkeypatch.undo()

    assert _installed_numbers(database) == live_before
    assert _leftover_restore_files(paths) == []


def test_restore_initialize_failure_rolls_back_the_original_database(
    tmp_path: Path, monkeypatch
) -> None:
    """切换之后初始化失败 → 自动回滚成恢复前的原库，不留半恢复状态（H01 注入）。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    original = make_standard()
    standards.install(original, "test-package")
    service = BackupService(paths, database, audit)
    backup = service.create(tmp_path / "state.uebackup")

    with database.session() as session:
        session.query(StandardRow).delete()
    standards.install(
        make_standard(standard_id="gb-99999-2026", standard_number="GB 99999-2026"),
        "later-package",
    )
    live_before = _installed_numbers(database)
    live_revision = revision_of(paths.database)

    def _boom(self, **kwargs):
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(DatabaseManager, "initialize", _boom)
    with pytest.raises(RestoreSafetyError, match="已自动回滚") as caught:
        service.restore(backup)
    monkeypatch.undo()

    # 中文提示优先，技术细节只进日志。
    assert any("\u4e00" <= char <= "\u9fff" for char in str(caught.value))
    # 回滚结果 = 恢复前的活状态，而不是备份里的状态。
    assert _installed_numbers(database) == live_before
    assert revision_of(paths.database) == live_revision
    assert _leftover_restore_files(paths) == []

    # 再“重启”一次确认：切换进来的那个库没有靠残留的 -wal/-shm 复活。
    database.dispose()
    restarted = DatabaseManager(paths.database, paths=paths)
    try:
        restarted.initialize()
        assert _installed_numbers(restarted) == live_before
        assert revision_of(paths.database) == live_revision
    finally:
        restarted.dispose()


def test_restore_application_data_failure_rolls_back_the_original_database(
    tmp_path: Path, monkeypatch
) -> None:
    """全环境备份恢复时合并应用数据失败 → 数据库同样回滚（H01 注入）。"""
    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    original = make_standard()
    standards.install(original, "test-package")
    (paths.standards / "source.pdf").write_bytes(b"pdf-placeholder")
    service = BackupService(paths, database, audit)
    backup = service.create_full_environment(tmp_path / "full.uebackup")

    with database.session() as session:
        session.query(StandardRow).delete()
    live_before = _installed_numbers(database)

    def _denied(src, dst, *args, **kwargs):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr("uebench.infrastructure.backup.shutil.copytree", _denied)
    with pytest.raises(RestoreSafetyError, match="已自动回滚"):
        service.restore(backup)
    monkeypatch.undo()

    assert _installed_numbers(database) == live_before
    assert _leftover_restore_files(paths) == []