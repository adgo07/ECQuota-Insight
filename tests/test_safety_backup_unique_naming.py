"""Phase 7 发布阻塞项：**自动安全备份不得重名、不得覆盖**。

缺陷（修复前）
--------------
三条**自动**安全备份各自拼文件名：迁移前 ``pre-migration-%Y%m%d-%H%M%S``、
安装前 ``pre-package-%Y%m%d-%H%M%S``、恢复前 ``pre-restore-%Y%m%d-%H%M%S``。
它们只精确到**秒**，而 ``BackupService.create`` 会直接写入给定路径：同一秒内的两次
操作得到同一个文件名，第二次静默覆盖第一次，被保护的那个状态从此不可恢复。

修复契约
--------
1. 全部自动安全备份共用一个命名器
   （``uebench.infrastructure.backup_paths``）：``<prefix>YYYYMMDD-HHMMSS-ffffff-<短uuid>.uebackup``；
2. 名字通过 ``O_CREAT | O_EXCL`` **独占创建**预订，选择与占用是同一步操作，
   已存在的文件（含理论上的重名）永不覆盖，同名被抢占就换 uuid 重试，重试用尽显式失败；
3. 前缀 ``pre-restore-`` / ``pre-migration-`` / ``pre-package-`` 保持不变
   （既有代码与 ``tools/windows_runtime_evidence.py`` 按前缀 glob）；
4. 历史 ``.uebackup`` 归档不迁移、不改写，内容与 SHA256 不受后续恢复影响。

本模块的用例都是**真实**的：真实 SQLite、真实 ``BackupService``、真实 Alembic 迁移、
真实 Ed25519 签名包，不使用 mock 替换被测行为（只在需要「同一秒」时冻结时钟）。
"""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from uebench.domain.models import (
    EvaluationRequest,
    EvaluationResult,
    Grade,
    IndicatorResult,
    InputMode,
    InputValue,
    PublicationStatus,
    StandardDefinition,
)
from uebench.infrastructure import backup_paths
from uebench.infrastructure.backup import BackupService
from uebench.infrastructure.backup_paths import (
    PRE_MIGRATION_PREFIX,
    PRE_PACKAGE_PREFIX,
    PRE_RESTORE_PREFIX,
    RESERVATION_MARKER_PREFIX,
    BackupPathError,
    reserve_unique_backup_path,
)
from uebench.infrastructure.database import DatabaseManager
from uebench.infrastructure.packages import (
    BACKUP_NAME_PREFIX,
    StandardPackageBuilder,
    StandardPackageService,
    _backup_path,
)
from uebench.infrastructure.paths import AppPaths
from uebench.infrastructure.repositories import (
    AuditRepository,
    SqlEvaluationRepository,
    SqlStandardRepository,
)

from .test_engine import make_standard
from .test_migration_backup import (
    HEAD,
    insert_standard_sql,
    migrations_config,
    revision_of,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "uebench"
MIGRATIONS = ROOT / "migrations"

#: 自动安全备份的三个调用点对应的源码模块。
AUTO_BACKUP_CALL_SITES = (
    SRC / "infrastructure" / "backup.py",
    SRC / "infrastructure" / "database.py",
    SRC / "infrastructure" / "packages.py",
)


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def setup_database(tmp_path: Path):
    paths = AppPaths.from_root(tmp_path / "appdata")
    paths.ensure()
    database = DatabaseManager(paths.database)
    database.initialize()
    audit = AuditRepository(database)
    return paths, database, audit


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_database(archive: Path, destination: Path) -> Path:
    """把 ``.uebackup`` 里的数据库抽到 ``destination``（真实解包，不 mock）。"""

    import zipfile

    with zipfile.ZipFile(archive) as package:
        destination.write_bytes(package.read("uebench.sqlite3"))
    return destination


def backup_evaluation_ids(archive: Path, tmp_path: Path) -> list[str]:
    """备份归档里的正式评价记录 id（按 id 排序，抹掉插入顺序）。"""

    snapshot = backup_database(archive, tmp_path / f"{archive.stem}-{uuid4().hex[:6]}.sqlite3")
    with closing(sqlite3.connect(snapshot)) as connection:
        rows = connection.execute("SELECT evaluation_id FROM evaluations").fetchall()
    return sorted(str(row[0]) for row in rows)


def record_evaluation(
    evaluations: SqlEvaluationRepository,
    standard: StandardDefinition,
    record_id: str,
    *,
    value: str = "20",
) -> str:
    """真实写入一条正式评价记录，返回 ``evaluation_id``。"""

    request = EvaluationRequest(
        evaluation_date=date(2026, 3, 3),
        standard_id=standard.id,
        product_id=standard.products[0].id,
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value=value, unit="kgce/t")},
    )
    result = EvaluationResult(
        evaluation_id=record_id,
        evaluated_at=datetime(2026, 3, 3, 12, 0, tzinfo=timezone.utc),
        standard_id=standard.id,
        standard_number=standard.number,
        standard_title=standard.title,
        standard_version=standard.version,
        product_id=standard.products[0].id,
        product_name=standard.products[0].name,
        results=[
            IndicatorResult(
                indicator_id="energy",
                indicator_name="单位产品能耗",
                actual_value=None,
                unit="kgce/t",
                grade=Grade.LEVEL_2,
            )
        ],
        rule_snapshot_sha256=standard.source_sha256,
    )
    evaluations.save(request, result, standard)
    return record_id


def live_evaluation_ids(database: DatabaseManager) -> list[str]:
    with database.session() as session:
        from uebench.infrastructure.database import EvaluationRow

        return sorted(str(row[0]) for row in session.query(EvaluationRow.evaluation_id).all())


def automatic_backups(paths: AppPaths, prefix: str) -> list[Path]:
    return sorted(paths.backups.glob(f"{prefix}*.uebackup"))


# ---------------------------------------------------------------------------
# 命名器本身
# ---------------------------------------------------------------------------


def test_automatic_backup_name_has_microsecond_and_unique_token(tmp_path: Path) -> None:
    """命名契约：``<prefix>YYYYMMDD-HHMMSS-ffffff-<短uuid>.uebackup``。"""

    directory = tmp_path / "backups"
    first = reserve_unique_backup_path(directory, PRE_RESTORE_PREFIX)
    second = reserve_unique_backup_path(directory, PRE_MIGRATION_PREFIX)

    for path, prefix in ((first, PRE_RESTORE_PREFIX), (second, PRE_MIGRATION_PREFIX)):
        assert path.parent == directory
        assert path.suffix == ".uebackup"
        assert path.name.startswith(prefix)
        core = path.name[len(prefix) : -len(".uebackup")]
        parts = core.split("-")
        assert len(parts) == 4, core
        assert len(parts[0]) == 8 and parts[0].isdigit(), core
        assert len(parts[1]) == 6 and parts[1].isdigit(), core
        assert len(parts[2]) == 6 and parts[2].isdigit(), f"缺少微秒精度：{core}"
        assert len(parts[3]) == 8, core
        int(parts[3], 16)  # 短 uuid 必须是十六进制

    # 预订真的落盘占据名字（带本进程专属令牌的占位文件，由 ``create(reserve=True)``
    # 校验令牌后原子接管）。
    for path in (first, second):
        assert path.is_file()
        assert path.read_bytes().startswith(RESERVATION_MARKER_PREFIX)


def test_second_precision_collision_is_impossible(tmp_path: Path) -> None:
    """同一**秒**内（微秒不同）连续取名字必须得到不同文件名。

    这正是修复前的缺陷形状：当时名字只精确到秒，下面这两次调用会返回同一个路径，
    第二次随即覆盖第一次的安全备份。
    """

    directory = tmp_path / "backups"
    base = datetime(2026, 10, 5, 22, 0, 0)

    class FrozenClock:
        """同一个秒里的两个不同微秒（0µs 与 1µs）。"""

        ticks = 0

        @classmethod
        def now(cls) -> datetime:
            value = base + timedelta(microseconds=cls.ticks)
            cls.ticks += 1
            return value

    original = backup_paths.datetime
    backup_paths.datetime = FrozenClock
    try:
        first = reserve_unique_backup_path(directory, PRE_RESTORE_PREFIX)
        second = reserve_unique_backup_path(directory, PRE_RESTORE_PREFIX)
    finally:
        backup_paths.datetime = original

    assert first.name.startswith(f"{PRE_RESTORE_PREFIX}20261005-220000-000000-")
    assert second.name.startswith(f"{PRE_RESTORE_PREFIX}20261005-220000-000001-")
    assert first != second
    assert first.is_file() and second.is_file()


# ---------------------------------------------------------------------------
# C. 名字被占用时绝不覆盖：换名或显式失败
# ---------------------------------------------------------------------------


def test_reservation_never_overwrites_a_file_created_at_the_same_name(tmp_path: Path) -> None:
    """时钟 + uuid 都被冻结（最坏的理论重名）时，也不得覆盖既有文件。"""

    directory = tmp_path / "backups"
    base = datetime(2026, 10, 5, 22, 30, 0)

    class FrozenClock:
        @classmethod
        def now(cls) -> datetime:
            return base

    original_clock = backup_paths.datetime
    original_token = backup_paths._token
    backup_paths.datetime = FrozenClock
    backup_paths._token = lambda: "deadbeef"
    try:
        taken = reserve_unique_backup_path(directory, PRE_RESTORE_PREFIX)
        assert taken.name == f"{PRE_RESTORE_PREFIX}20261005-223000-000000-deadbeef.uebackup"
        # 名字已被独占占用（时钟 + uuid 还是同一个）：重试用尽即显式失败，
        # 绝不退化成打开已有文件做截断写入。
        with pytest.raises(BackupPathError):
            reserve_unique_backup_path(directory, PRE_RESTORE_PREFIX)
    finally:
        backup_paths.datetime = original_clock
        backup_paths._token = original_token

    # 第一份预订（本进程令牌）在重试失败后毫发无损。
    assert taken.read_bytes().startswith(RESERVATION_MARKER_PREFIX)
    assert taken.is_file()


def test_reservation_does_not_overwrite_a_real_backup_at_the_candidate_name(tmp_path: Path) -> None:
    """候选名上已经躺着一份**真实**安全备份时，字节和 SHA256 必须原封不动。"""

    directory = tmp_path / "backups"
    directory.mkdir(parents=True)
    occupied = directory / f"{PRE_PACKAGE_PREFIX}20261005-224500-123456-cafebabe.uebackup"
    occupied.write_bytes(b"existing safety backup payload")
    before = occupied.read_bytes()
    before_sha = sha256_file(occupied)

    reserved = reserve_unique_backup_path(directory, PRE_PACKAGE_PREFIX)

    assert reserved != occupied
    assert occupied.read_bytes() == before
    assert sha256_file(occupied) == before_sha
    # 已经存在的真实备份不会被当作预留接管（内容是 ZIP，不是预订令牌）。
    with pytest.raises(BackupPathError):
        backup_paths.claim_reserved_backup_path(occupied)
    assert occupied.read_bytes() == before


def test_reservation_fails_explicitly_when_every_name_is_occupied(tmp_path: Path) -> None:
    """重试用尽时显式失败（``BackupPathError``），而不是退化去覆盖已有文件。"""

    directory = tmp_path / "backups"
    base = datetime(2026, 10, 5, 23, 0, 0)

    class FrozenClock:
        @classmethod
        def now(cls) -> datetime:
            return base

    original_clock = backup_paths.datetime
    original_token = backup_paths._token
    backup_paths.datetime = FrozenClock
    backup_paths._token = lambda: "0123abcd"
    try:
        occupied = reserve_unique_backup_path(directory, PRE_RESTORE_PREFIX)
        payload = b"do not touch"
        occupied.write_bytes(payload)
        with pytest.raises(BackupPathError):
            reserve_unique_backup_path(directory, PRE_RESTORE_PREFIX)
    finally:
        backup_paths.datetime = original_clock
        backup_paths._token = original_token

    assert occupied.read_bytes() == payload


def test_safety_write_path_refuses_an_unreserved_existing_path(tmp_path: Path) -> None:
    """``create(..., reserve=True)`` 只接管本方法自己预订的 0 字节占位文件。"""

    paths, database, audit = setup_database(tmp_path)
    service = BackupService(paths, database, audit)
    someone_else = paths.backups / "pre-restore-20200101-000000-000000-aaaaaaaa.uebackup"
    someone_else.parent.mkdir(parents=True, exist_ok=True)
    someone_else.write_bytes(b"a real backup that must survive")
    before = someone_else.read_bytes()

    with pytest.raises(BackupPathError, match="未独占占用"):
        service.create(someone_else, reserve=True)

    assert someone_else.read_bytes() == before
    database.dispose()


# ---------------------------------------------------------------------------
# A / B. 连续两次恢复：两份不同的安全备份，第一份逐字节不变
# ---------------------------------------------------------------------------


def test_two_consecutive_restores_never_destroy_the_first_safety_backup(tmp_path: Path) -> None:
    """A + B：同一秒内连续两次恢复必须留下两份不同的恢复前安全备份。

    * A：记录 A → 全环境备份 → 记录 B → 第一次恢复 A
      → 自动恢复前安全备份必须同时含 A 和 B（取自**恢复前活状态**）；
    * B：**不 sleep** 立刻再恢复一次 A
      → 出现第二份不同的安全备份；第一份的路径 / 内容 / SHA256 完全不变；
        第二份反映「第二次恢复前」的状态（只有 A）。
    """

    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    evaluations = SqlEvaluationRepository(database, audit)
    standard = make_standard()
    standards.install(standard, "test-package")
    service = BackupService(paths, database, audit)

    record_a = record_evaluation(evaluations, standard, "record-a", value="11")
    source = service.create_full_environment(tmp_path / "full-environment.uebackup")
    assert service.validate(source)["scope"] == "full-environment"
    record_b = record_evaluation(evaluations, standard, "record-b", value="29")
    assert live_evaluation_ids(database) == [record_a, record_b]

    # ---- 第一次恢复 ------------------------------------------------------
    service.restore(source)
    assert live_evaluation_ids(database) == [record_a]
    first_backups = automatic_backups(paths, PRE_RESTORE_PREFIX)
    assert len(first_backups) == 1, [item.name for item in first_backups]
    first = first_backups[0]
    first_bytes = first.read_bytes()
    first_sha = sha256_file(first)
    assert backup_evaluation_ids(first, tmp_path) == [record_a, record_b], (
        "恢复前的安全备份必须来自恢复前的活状态（同时含 A 和 B）"
    )
    assert service.validate(first)["scope"] == "user-data"

    # ---- 第二次恢复：刻意不 sleep ---------------------------------------
    service.restore(source)
    assert live_evaluation_ids(database) == [record_a]

    second_backups = automatic_backups(paths, PRE_RESTORE_PREFIX)
    assert len(second_backups) == 2, [item.name for item in second_backups]
    second = [item for item in second_backups if item != first]
    assert len(second) == 1
    second = second[0]
    assert second.name != first.name

    # 第一份安全备份逐字节、逐 SHA256 未变（历史备份不得被改写）。
    assert first.read_bytes() == first_bytes
    assert sha256_file(first) == first_sha
    # 第二份反映「第二次恢复之前」的状态：第一次恢复已经把 B 抹掉了。
    assert backup_evaluation_ids(second, tmp_path) == [record_a]
    assert sha256_file(second) != first_sha
    assert second.parent == paths.backups
    assert second.name.startswith(PRE_RESTORE_PREFIX) and second.suffix == ".uebackup"
    # 两份都仍然是合法的 user-data 安全备份（数据库有，标准原文/应用数据没有）。
    for archive in second_backups:
        manifest = service.validate(archive)
        assert manifest["scope"] == "user-data"
        assert set(manifest["files"]) == {"uebench.sqlite3"}
        assert not any(name.startswith("standards/") for name in manifest["files"])

    database.dispose()


# ---------------------------------------------------------------------------
# D. 覆盖**每一个**自动安全备份调用点的性质（防止未来调用点回退）
# ---------------------------------------------------------------------------


def test_every_automatic_call_site_produces_two_distinct_backups(tmp_path: Path) -> None:
    """恢复前 / 迁移前 / 安装前 三个调用点各跑两次：两个不同路径，第一个不变。

    这是防止未来新增调用点（或某个调用点重新自己拼名字）回退的总闸门。
    """

    paths, database, audit = setup_database(tmp_path)
    standards = SqlStandardRepository(database, audit)
    evaluations = SqlEvaluationRepository(database, audit)
    standard = make_standard()
    standards.install(standard, "test-package")
    backup_service = BackupService(paths, database, audit)

    # 先落一条真实业务记录（安全备份必须保护它），再取一份全环境备份作为恢复源。
    record_evaluation(evaluations, standard, "gate-a", value="11")
    source = backup_service.create_full_environment(tmp_path / "gate-source.uebackup")

    # 1. pre-restore：连续两次恢复。
    backup_service.restore(source)
    backup_service.restore(source)

    # 2. pre-package：连续两次真实安装（真实 Ed25519 签名包）。
    private_key = Ed25519PrivateKey.generate()
    package_service = StandardPackageService(
        paths, database, private_key.public_key(), backup_service, standards, audit
    )
    for index in range(2):
        definition = make_standard()
        definition.id = f"gate-package-{index}"
        package = StandardPackageBuilder(private_key).build(
            tmp_path / f"gate-{index}.uebench",
            [definition],
            None,
            data_version=f"2026.10-published.{index + 20}",
            package_id=f"gate-package-{index}",
            issued_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
            distribute_sources=False,
        )
        package_service.install(package)

    # 3. pre-migration：连续两次真实迁移（降级到 0001，再各升级一次）。
    #    每次迁移前插一条**不同编号**的标准，因此两份迁移前备份必然不同，且各自
    #    反映各自那次迁移之前的状态。
    migrations = migrations_config(paths.database)
    numbers = ("GB 12345-2019", "GB 12346-2019")
    for number in numbers:
        database.dispose()
        command.downgrade(migrations, "0001")
        assert revision_of(paths.database) == "0001"
        insert_standard_sql(paths.database, number)
        created = database.initialize()
        assert created is not None
        assert revision_of(paths.database) == HEAD

    for prefix in (PRE_RESTORE_PREFIX, PRE_MIGRATION_PREFIX, PRE_PACKAGE_PREFIX):
        backups = automatic_backups(paths, prefix)
        assert len(backups) == 2, f"{prefix}: {[item.name for item in backups]}"
        assert all(item.suffix == ".uebackup" for item in backups)
        # 两份必须内容不同（各自反映各自操作前的状态），且都通过真实校验。
        assert sha256_file(backups[0]) != sha256_file(backups[1])
        for archive in backups:
            manifest = backup_service.validate(archive)
            assert manifest["scope"] == "user-data"
            assert set(manifest["files"]) == {"uebench.sqlite3"}

    # 两份迁移前备份各自反映「各自那次迁移之前」的状态：第二次迁移前，第一次插入
    # 的那条标准已经在库里（所以第二份比第一份多一条），而第二份不含第二次要插的那条。
    migration_backups = automatic_backups(paths, PRE_MIGRATION_PREFIX)
    first_snapshot = backup_database(
        migration_backups[0], tmp_path / "first-migration.sqlite3"
    )
    second_snapshot = backup_database(
        migration_backups[1], tmp_path / "second-migration.sqlite3"
    )
    with closing(sqlite3.connect(first_snapshot)) as connection:
        first_numbers = [str(row[0]) for row in connection.execute("SELECT number FROM standards")]
    with closing(sqlite3.connect(second_snapshot)) as connection:
        second_numbers = [str(row[0]) for row in connection.execute("SELECT number FROM standards")]
    assert first_numbers.count(numbers[0]) == 1
    assert first_numbers.count(numbers[1]) == 0
    assert second_numbers.count(numbers[0]) == 1
    assert second_numbers.count(numbers[1]) == 1

    database.dispose()


def test_only_the_shared_namer_builds_automatic_backup_filenames() -> None:
    """AST 闸门：基础设施层里只有 ``backup_paths.py`` 能拼 ``.uebackup`` 名字。

    这条守卫让「未来某个调用点又自己拼一个只精确到秒的时间戳」在静态上就不可能
    通过测试：任何非 ``backup_paths.py`` 模块里的 ``.uebackup`` 名字模板都会被点名。
    """

    violations: list[str] = []
    for path in sorted((SRC / "infrastructure").rglob("*.py")):
        if path.name == "backup_paths.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
            if not isinstance(node, ast.JoinedStr):
                continue
            literal = "".join(
                part.value for part in node.values if isinstance(part, ast.Constant)
                and isinstance(part.value, str)
            )
            if literal.endswith(".uebackup"):
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert violations == [], (
        "自动安全备份名只能在 uebench.infrastructure.backup_paths 中构造："
        + ", ".join(violations)
    )


def test_ui_and_tools_still_glob_the_unchanged_prefixes() -> None:
    """前缀契约：调用点只给前缀，名字前缀与既有 glob/工具保持一致。"""

    assert BACKUP_NAME_PREFIX == PRE_PACKAGE_PREFIX == "pre-package-"
    assert PRE_RESTORE_PREFIX == "pre-restore-"
    assert PRE_MIGRATION_PREFIX == "pre-migration-"

    directory = ROOT
    tool = (directory / "tools" / "windows_runtime_evidence.py").read_text(encoding="utf-8")
    assert 'glob("pre-package-*.uebackup")' in tool, (
        "tools/windows_runtime_evidence.py 仍按 pre-package-*.uebackup 解析备份名；"
        "前缀必须保持兼容（该脚本不在本次改动范围内）"
    )


def test_every_automatic_call_site_uses_the_shared_namer(tmp_path: Path) -> None:
    """三个调用点的源码里必须出现共享命名器，且不得再出现自己的时间戳格式。"""

    sources = {path.name: path.read_text(encoding="utf-8") for path in AUTO_BACKUP_CALL_SITES}
    assert "reserve_unique_backup_path" in sources["backup.py"]
    assert "reserve_unique_backup_path" in sources["database.py"]
    assert "_backup_path" in sources["packages.py"]
    for name, source in sources.items():
        assert "%Y%m%d-%H%M%S" not in source, f"{name} 仍在自己拼秒级时间戳"
        assert "_pre_migration_backup_path" not in source
    # ``packages._backup_path`` 只是共享命名器的薄封装（前缀由它给）。
    assert "reserve_unique_backup_path(directory, BACKUP_NAME_PREFIX)" in sources["packages.py"]
    assert _backup_path(tmp_path / "package-backups").name.startswith(PRE_PACKAGE_PREFIX)
