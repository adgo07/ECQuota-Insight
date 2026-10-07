from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterator
from uuid import uuid4

from alembic.script import ScriptDirectory

from .backup_paths import (
    PRE_MIGRATION_PREFIX,
    PRE_PACKAGE_PREFIX,
    PRE_RESTORE_PREFIX,
    BackupPathError,
    claim_reserved_backup_path,
    reserve_unique_backup_path,
)
from .database import MANAGED_TABLES, DatabaseManager, alembic_config
from .paths import AppPaths
from .repositories import AuditRepository

__all__ = [
    "APPLICATION_DATA_ROOTS",
    "BackupPathError",
    "BackupScope",
    "BackupService",
    "BackupValidationError",
    "PRE_MIGRATION_PREFIX",
    "PRE_PACKAGE_PREFIX",
    "PRE_RESTORE_PREFIX",
    "RestoreSafetyError",
    "claim_reserved_backup_path",
    "create_sqlite_snapshot",
    "reserve_unique_backup_path",
    "restore_exclusive_lock",
    "validate_restorable_database",
]

logger = logging.getLogger(__name__)

#: The 16-byte file header every SQLite database starts with.  Checking it
#: first lets a non-SQLite payload be rejected with a precise Chinese message
#: instead of a raw ``sqlite3.DatabaseError`` from deep inside the API.
SQLITE_MAGIC = b"SQLite format 3\x00"


class BackupValidationError(ValueError):
    pass


class RestoreSafetyError(BackupValidationError):
    """恢复操作的安全条件不满足，或切换之后的步骤失败（活库始终受保护）。

    恢复链在覆盖活库**之前**的拒绝（排他条件拿不到、容器/数据库校验不通过）
    与切换**之后**的失败（初始化、应用数据合并）都会走到这里。两类情况的共同
    契约是：**活库内容要么完全未改变，要么已自动回滚成恢复前状态**，并带一条
    能直接显示给用户的中文消息。继承 ``BackupValidationError`` 是为了让既有的
    ``pytest.raises(BackupValidationError)`` 与 UI 的 ``_friendly_error`` 中文
    前缀继续成立。
    """


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_sqlite_snapshot(source_path: Path, destination_path: Path) -> None:
    """Write a transactionally consistent copy of ``source_path`` to ``destination_path``.

    The live database runs in WAL mode with ``synchronous=FULL``, so the
    ``-wal``/``-shm`` sidecar files hold committed data that a raw file copy
    would silently drop (or capture torn).  The sqlite3 online backup API
    instead reads through a normal connection, which is the only safe way to
    snapshot an active database.  Both backup creation and pre-migration
    backups share this single implementation.
    """

    destination_path = Path(destination_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(Path(source_path))
    destination = sqlite3.connect(destination_path)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def _sidecar_paths(database_path: Path) -> tuple[Path, ...]:
    """The ``-wal`` / ``-shm`` sidecars that belong to ``database_path``."""

    return tuple(Path(str(database_path) + suffix) for suffix in ("-wal", "-shm"))


def require_exclusive_database_access(database_path: Path) -> None:
    """Obtain the exclusivity a restore needs before it may replace ``database_path``.

    ECQ-RS05 M1（H01）：恢复成功但数据还是旧的，根因是覆盖活库时旧的 WAL 残留
    会叠加到新主库上，或者别的连接仍握着旧文件。本函数用一层只读、只会把已提交
    WAL 折叠回主库的检测阶梯，**拿不到排他条件就以中文 ``RestoreSafetyError``
    拒绝，活库一个字节都不变**：

    1. ``PRAGMA wal_checkpoint(TRUNCATE)``：有其他连接正在读含数据的 WAL 或正在
       写 → 返回 busy。折叠成功则 WAL 内容已进主库，后续删边车不会丢数据；
    2. ``BEGIN IMMEDIATE``：有其他连接正在写 → ``database is locked``；
    3. 关闭本方探测连接之后，``-wal`` / ``-shm`` 仍删除不掉 → 还有别的连接握着它。

    最后一层兜底是切换本身的 ``os.replace``：Windows 上任何仍被打开的文件都无法
    被替换，由 :meth:`BackupService.restore` 转成同一条中文拒绝。

    平台说明：Windows（第一交付平台）上三个层次分别能拦下“读事务 / 写事务 /
    只打开没读过的空闲连接”。POSIX 上“已打开但从未使用”的空闲连接无法可靠检出
    —— 它既不建边车也拿不到锁，属于已知限制，详见交付报告。
    """

    if not database_path.exists():
        return
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA busy_timeout=2000")
        try:
            busy = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]
        except sqlite3.DatabaseError as exc:
            raise RestoreSafetyError(
                "恢复被拒绝：无法安全检查数据库当前状态（数据库可能已损坏）。原数据库未被修改。"
            ) from exc
        if busy:
            raise RestoreSafetyError(
                "恢复被拒绝：其他窗口或程序正在读写数据库，请关闭后重试。原数据库未被修改。"
            )
        try:
            connection.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            raise RestoreSafetyError(
                "恢复被拒绝：其他窗口或程序正在写入数据库，请关闭后重试。原数据库未被修改。"
            ) from exc
        connection.execute("ROLLBACK")
    finally:
        connection.close()
    # 本方探测连接关闭时，若我们是最后一个连接，SQLite 会自动删掉这两个边车；
    # 它们还在，就说明还有别的连接，而 Windows 上这些文件删不掉（WinError 5/32）。
    for sidecar in _sidecar_paths(database_path):
        if not sidecar.exists():
            continue
        try:
            sidecar.unlink()
        except OSError as exc:
            raise RestoreSafetyError(
                f"恢复被拒绝：数据库工作文件 {sidecar.name} 仍被其他窗口或程序占用，"
                "请关闭后重试。原数据库未被修改。"
            ) from exc


def validate_restorable_database(database_path: Path) -> None:
    """Validate the candidate SQLite database **in a temporary location** (H02).

    在恢复链里它跑在解包之后、创建恢复前安全备份与覆盖活库**之前**，所以任何
    拒绝都不可能改变现有数据，也不存在“先覆盖再发现问题”的窗口：

    * 文件头不是 ``SQLite format 3\\x00`` → 拒绝（根本不是 SQLite 文件）；
    * ``PRAGMA integrity_check`` 不通过 → 拒绝（已损坏的 SQLite）；
    * 缺少本应用的受管数据表 → 拒绝（不是本软件的数据库 / 不完整）；
    * ``alembic_version`` 里的结构版本不在本软件迁移脚本中 → 拒绝，并明确提示
      **不会降级、请安装匹配或更新版本的软件**；绝不尝试 downgrade。

    没有 ``alembic_version`` 标记但受管表齐全的库视为可迁移的旧 Schema，交给
    切换之后的 ``DatabaseManager.initialize()`` 按既有规则接管。
    """

    try:
        with database_path.open("rb") as stream:
            magic = stream.read(len(SQLITE_MAGIC))
    except OSError as exc:
        raise BackupValidationError("无法读取备份中的数据库文件") from exc
    if magic != SQLITE_MAGIC:
        raise BackupValidationError("备份中的数据库不是有效的 SQLite 文件")

    revisions: list[str] = []
    try:
        connection = sqlite3.connect(database_path)
        try:
            connection.execute("PRAGMA busy_timeout=2000")
            try:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()
            except sqlite3.DatabaseError as exc:
                raise BackupValidationError("备份中的数据库已损坏（无法读取）") from exc
            if integrity is None or tuple(integrity) != ("ok",):
                raise BackupValidationError("备份中的数据库未通过完整性检查（已损坏）")
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            missing = sorted(set(MANAGED_TABLES) - tables)
            if missing:
                raise BackupValidationError(
                    "备份中的数据库不属于本软件（缺少应用数据表：" + ", ".join(missing) + "）"
                )
            if "alembic_version" in tables:
                revisions = sorted(
                    {str(row[0]) for row in connection.execute("SELECT version_num FROM alembic_version") if row[0]}
                )
        finally:
            connection.close()
    except sqlite3.DatabaseError as exc:
        raise BackupValidationError("备份中的数据库已损坏（无法读取）") from exc

    if not revisions:
        # 旧版无 Alembic 标记的完整库：由切换之后的 initialize() 按既有规则接管。
        return
    script = ScriptDirectory.from_config(alembic_config(database_path))
    known = {str(item.revision) for item in script.walk_revisions("base", "head")}
    unknown = sorted(set(revisions) - known)
    if unknown:
        raise BackupValidationError(
            "备份中的数据库结构版本（"
            + "、".join(unknown)
            + "）无法被当前软件识别，可能由更高版本的软件创建；当前软件不会降级该数据库。"
            "请安装能够读取该版本的软件（匹配或更新的版本）后重试。"
        )


def _lock_handle_nonblocking(handle: BinaryIO) -> None:
    """Take an OS-level exclusive lock on ``handle`` without blocking (Windows ``msvcrt`` / POSIX ``fcntl``)."""

    if sys.platform == "win32":
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_handle(handle: BinaryIO) -> None:
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:  # pragma: no cover - 句柄关闭同样会释放锁，这里只求显式
        logger.debug("恢复期互斥锁释放失败（关闭句柄仍会释放）", exc_info=True)


@contextmanager
def restore_exclusive_lock(database_path: Path) -> Iterator[None]:
    """恢复期互斥：同一数据目录同一时刻只允许一次 ``restore``（H01 防御纵深）。

    操作系统级文件锁，拿不到就以中文 ``RestoreSafetyError`` 拒绝，而不是排队
    等待——排队意味着“先等 A 恢复完再覆盖”，那不是安全语义。进程退出时系统
    自动释放，因此崩溃不会留下永远锁死的残留文件；锁文件本身只是空文件，不属于
    任何 ``.uebackup`` 归档内容。
    """

    lock_path = database_path.with_name(database_path.name + ".restore.lock")
    try:
        handle = lock_path.open("a+b")
    except OSError as exc:
        raise RestoreSafetyError(
            "恢复被拒绝：无法在数据目录创建恢复锁文件，原数据库未被修改。请检查数据目录的写入权限后重试。"
        ) from exc
    try:
        try:
            _lock_handle_nonblocking(handle)
        except OSError as exc:
            raise RestoreSafetyError(
                "恢复被拒绝：同一数据目录已有一个恢复操作正在进行，请稍后再试。原数据库未被修改。"
            ) from exc
        try:
            yield
        finally:
            _unlock_handle(handle)
    finally:
        handle.close()


class BackupScope(str, Enum):
    """What one ``.uebackup`` archive is responsible for (owner contract, Phase 7).

    The distinction is between data the product **owns** and data the product can
    **re-obtain**:

    USER DATA (用户业务数据)
        Only the SQLite database, and inside it everything that cannot be
        rebuilt: formal evaluation records plus the rule snapshots those records
        reference, the installed standard definitions, import batches and the
        audit trail.  A *safety* backup — the migration, pre-install and
        pre-restore snapshot — is responsible for this and **only** this.

    REBUILDABLE APPLICATION DATA (可重建应用数据)
        Standard packages, standard原文 PDFs, bundled resources, caches and
        logs.  A standard package can be re-installed from the signed
        ``.uebench`` file, and a PDF is never written into the user data
        directory any more, so none of this belongs in a safety backup.  The
        rule snapshots historical evaluations need already live in the database
        itself; no second snapshot store is invented here.
    """

    #: Safety backup: the user's business data (database only).  Default for
    #: every internal safety call site (pre-migration / pre-install / pre-restore).
    USER_DATA = "user-data"
    #: Explicit, user-initiated full environment backup: database **plus** the
    #: rebuildable application data (``standards/``, ``imports/``, ``logs/``).
    FULL_ENVIRONMENT = "full-environment"


#: Archive members that only a full-environment backup may carry.  Used by
#: ``BackupService.validate`` to keep a self-declared safety backup safe.
APPLICATION_DATA_ROOTS: tuple[str, ...] = ("standards", "imports", "logs")


def _safe_member(name: str) -> bool:
    pure = PurePosixPath(name)
    # ZIP member names are POSIX paths.  Reject Windows separators as well so
    # a name such as ``standards\\..\\uebench.sqlite3`` cannot be interpreted
    # differently by ``zipfile`` on a Windows host.
    return (
        bool(name)
        and not pure.is_absolute()
        and ".." not in pure.parts
        and "\\" not in name
        and ":" not in pure.parts[0]
    )


class BackupService:
    #: The rebuildable application subtrees: never core content of a safety
    #: backup, only ever added by an explicit full-environment backup.
    APPLICATION_DATA_ROOTS = APPLICATION_DATA_ROOTS

    def __init__(
        self,
        paths: AppPaths | None,
        database: DatabaseManager,
        audit: AuditRepository | None = None,
    ) -> None:
        self.paths = paths
        self.database = database
        self.audit = audit or AuditRepository(database)

    def create(
        self,
        path: Path,
        *,
        scope: BackupScope = BackupScope.USER_DATA,
        reserve: bool = False,
    ) -> Path:
        """Write a backup archive and return its path.

        ``scope=BackupScope.USER_DATA`` (the default, and what every *safety*
        call site uses — pre-migration, pre-install, pre-restore) writes the
        transactionally consistent database snapshot **only**.  Standard
        packages, standard原文 PDFs, bundled resources, caches and logs are
        rebuildable application data and are deliberately excluded: copying the
        whole ``standards/`` tree into a migration safety backup is exactly the
        historical defect this contract removes (a safety backup still carrying
        the standard PDFs it exists to protect the data *around*).

        ``scope=BackupScope.FULL_ENVIRONMENT`` additionally archives the
        application data subtrees.  It is the explicit user-initiated "full
        environment backup" and is only reachable through
        :meth:`create_full_environment`.

        ``reserve=True`` is the *safety* write path and only accepts a path
        returned by
        :func:`~uebench.infrastructure.backup_paths.reserve_unique_backup_path`
        (the file that helper exclusively created and stamped with its
        reservation token).  :func:`~uebench.infrastructure.backup_paths.claim_reserved_backup_path`
        proves that ownership, so an existing ``.uebackup`` archive can never be
        taken over as if it were a reservation.  The archive itself is built in
        a sibling temporary file and moved onto the reserved name with
        :func:`os.replace`.  A process killed before that rename leaves the
        reservation behind — a name that fails ``validate`` — never a
        half-written, corrupt ``.uebackup``.
        """
        scope = BackupScope(scope)
        path = Path(path)
        if reserve:
            path = claim_reserved_backup_path(path)
        else:
            path = path.resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="uebench-backup-") as temporary:
            temporary_path = Path(temporary)
            database_copy = temporary_path / "uebench.sqlite3"
            create_sqlite_snapshot(self.database.path, database_copy)

            files: dict[str, str] = {"uebench.sqlite3": _sha256(database_copy)}
            source_files: list[tuple[str, Path]] = []
            if scope is BackupScope.FULL_ENVIRONMENT and self.paths is not None:
                for root_name in self.APPLICATION_DATA_ROOTS:
                    root = getattr(self.paths, root_name)
                    if not root.exists():
                        continue
                    for item in root.rglob("*"):
                        if not item.is_file():
                            continue
                        archive_name = (PurePosixPath(root_name) / item.relative_to(root).as_posix()).as_posix()
                        source_files.append((archive_name, item))
                        files[archive_name] = _sha256(item)
            manifest = {
                "schema_version": "1.0",
                "backup_id": str(uuid4()),
                "created_at": datetime.now(timezone.utc).isoformat(),
                # Self-describing: a consumer (and ``validate``) can tell a
                # user-data safety backup from a full environment backup
                # without guessing, and pre-split archives (no ``scope`` key)
                # are correctly read as full-environment backups.
                "scope": scope.value,
                "files": files,
            }
            destination = path
            if reserve:
                # Build the archive beside the reservation, then let ``os.replace``
                # take the reserved name over in one step.  A crash between the
                # two leaves the reservation placeholder behind (which
                # ``validate`` rejects), never a truncated archive.
                handle, staged = tempfile.mkstemp(
                    prefix=f".{path.name}.", suffix=".partial", dir=path.parent
                )
                os.close(handle)
                destination = Path(staged)
            try:
                with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.write(database_copy, "uebench.sqlite3")
                    for archive_name, item in source_files:
                        archive.write(item, archive_name)
                    archive.writestr(
                        "manifest.json",
                        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    )
                if reserve:
                    os.replace(destination, path)
            except BaseException:
                if reserve:
                    destination.unlink(missing_ok=True)
                raise
        self.audit.append(
            "BACKUP_CREATE",
            "backup",
            str(path),
            {"backup_id": manifest["backup_id"], "scope": scope.value},
        )
        return path

    def create_full_environment(self, path: Path) -> Path:
        """Explicit user-initiated full environment backup (database + app data).

        Separate from the safety backups on purpose: a migration/install/restore
        safety backup exists to protect the *user's business data*, while this
        one is a user asking for one self-contained archive of the whole data
        directory.  Both share one implementation, so there is exactly one
        archive format, one manifest and one ``restore``.
        """
        return self.create(path, scope=BackupScope.FULL_ENVIRONMENT)

    def validate(self, path: Path) -> dict:
        with zipfile.ZipFile(path, "r") as archive:
            names = archive.namelist()
            if any(not _safe_member(name) for name in names):
                raise BackupValidationError("备份包包含不安全路径")
            duplicate_names = sorted(name for name, count in Counter(names).items() if count > 1)
            if duplicate_names:
                raise BackupValidationError("备份包包含重复文件：" + ", ".join(duplicate_names))
            try:
                manifest = json.loads(archive.read("manifest.json"))
            except (KeyError, json.JSONDecodeError) as exc:
                raise BackupValidationError("备份清单缺失或损坏") from exc
            if manifest.get("schema_version") != "1.0":
                raise BackupValidationError("不支持的备份版本")
            # Archives written before the scope split always contained the whole
            # ``standards/`` tree, so an absent field really means
            # full-environment; it must not be read as a safety backup.
            raw_scope = manifest.get("scope", BackupScope.FULL_ENVIRONMENT.value)
            try:
                scope = BackupScope(raw_scope)
            except ValueError as exc:
                raise BackupValidationError(f"不支持的备份范围：{raw_scope}") from exc
            files = manifest.get("files")
            if not isinstance(files, dict) or not files:
                raise BackupValidationError("备份清单中的 files 无效")
            if any(not isinstance(name, str) or not _safe_member(name) for name in files):
                raise BackupValidationError("备份清单包含不安全路径")
            allowed_roots = ("standards/", "imports/", "logs/")
            if any(name != "uebench.sqlite3" and not name.startswith(allowed_roots) for name in files):
                raise BackupValidationError("备份清单包含不允许的文件根目录")
            if scope is BackupScope.USER_DATA:
                # A safety backup is contractually the user's business data
                # (the database) only; an application-data member in a
                # self-declared safety backup means the archive was produced by
                # a broken writer, so it is rejected instead of silently
                # restored as if it were complete.
                unexpected = sorted(set(files) - {"uebench.sqlite3"})
                if unexpected:
                    raise BackupValidationError(
                        "安全备份（user-data）不得包含可重建的应用数据：" + ", ".join(unexpected)
                    )
            expected_names = set(files) | {"manifest.json"}
            extras = sorted(set(names) - expected_names)
            missing = sorted(expected_names - set(names))
            if extras:
                raise BackupValidationError("备份包含未登记文件：" + ", ".join(extras))
            if missing:
                raise BackupValidationError("备份缺少文件：" + ", ".join(missing))
            for name, expected in files.items():
                try:
                    actual = hashlib.sha256(archive.read(name)).hexdigest()
                except KeyError as exc:
                    raise BackupValidationError(f"备份缺少文件：{name}") from exc
                if actual != expected:
                    raise BackupValidationError(f"备份文件哈希错误：{name}")
            if "uebench.sqlite3" not in files:
                raise BackupValidationError("备份缺少数据库")
            # Normalise the resolved scope into the returned manifest so callers
            # never have to re-derive it (a pre-split archive has no such key).
            manifest["scope"] = scope.value
            return manifest

    def restore(self, path: Path) -> None:
        """Restore ``path`` onto the live data directory.

        Coherent with :class:`BackupScope`:

        * the **database** is always restored — that is where the user's
          business records live, and it is the whole content of a safety
          backup;
        * the application-data subtrees (``standards/``, ``imports/``,
          ``logs/``) are restored **only if the archive actually carries
          them** (a full-environment backup), and then as an in-place merge.
          A safety backup that does not own them never deletes them, and the
          merge never removes a live subtree: standard packages and PDFs are
          rebuildable, and the startup legacy原文 cleanup already guarantees a
          live ``standards/`` tree stays free of full standard PDFs.

        The pre-restore safety backup is a user-data (database) backup, for the
        same reason: the only thing a restore overwrites irreversibly is the
        database.

        ECQ-RS05 M1 恢复链（顺序经过验证，不宜调换）::

            备份包校验 → 临时位置验证待恢复 SQLite（格式/完整性/身份/Schema）
            → 恢复期互斥 + 数据库排他条件（含 WAL/SHM 处理）→ 恢复前安全备份
            → 原子切换 → 就地合并应用数据 → 重连并初始化/必要迁移
            → （门面层）标准库对账 → 界面刷新

        **任何一步失败都不会破坏原数据库、不留半恢复状态、也不会被显示为成功**：
        切换之前的失败原库一个字节都没动；切换之后的失败自动回滚成切换前的原库
        并重新建立连接，最后以中文 ``RestoreSafetyError`` 抛出。
        """
        manifest = self.validate(path)
        try:
            with tempfile.TemporaryDirectory(prefix="uebench-restore-") as temporary:
                temporary_path = Path(temporary)
                with zipfile.ZipFile(path, "r") as archive:
                    # ``validate`` has already checked the manifest and hashes;
                    # extract only registered files and verify the resolved target
                    # remains inside the temporary directory as a second guard.
                    for member in archive.namelist():
                        if member == "manifest.json":
                            continue
                        if not _safe_member(member):
                            raise BackupValidationError("备份包包含不安全路径")
                        target = (temporary_path / PurePosixPath(member)).resolve()
                        if temporary_path.resolve() not in target.parents:
                            raise BackupValidationError("备份文件路径越界")
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(archive.read(member))
                restored_database = temporary_path / "uebench.sqlite3"
                # 在临时位置把候选库验干净：不是 SQLite、损坏、不是本应用、
                # 或者结构版本高于当前软件，都在**覆盖活库之前**拒绝，
                # 并且绝不降级。
                validate_restorable_database(restored_database)
                database_path = self.database.path
                # 恢复期互斥拿不到就直接拒绝：排队等待不是安全语义。
                with restore_exclusive_lock(database_path):
                    # 先取得排他条件、再创建恢复前安全备份——顺序有两条硬理由：
                    # 1. 安全备份自己会写一条 ``BACKUP_CREATE`` 审计（经过本进程
                    #    引擎），有人正在写库时它只会撞上 “database is locked”；
                    #    先做排他检查，才能给出“请关闭其他窗口”这条准确的中文拒绝。
                    # 2. 被拒绝的恢复不该在备份目录里留下垃圾安全备份。
                    # 安全备份依然保证在**任何破坏性动作之前**完成。
                    #
                    # 关掉本进程的连接再检测：否则我们自己的引擎连接会把排他检测
                    # 变成永远 busy（也会把旧 WAL 揉进切换后的状态）。
                    self.database.dispose()
                    require_exclusive_database_access(database_path)
                    # The pre-restore safety backup is a *safety* backup: its name comes
                    # from the one shared namer (microsecond stamp + short uuid) and the
                    # name is exclusively reserved before it is written, so two restores
                    # in the same second — or two at the same microsecond — can never
                    # target the same file and destroy the earlier safety backup.
                    pre_restore = reserve_unique_backup_path(self.paths.backups, PRE_RESTORE_PREFIX)
                    try:
                        self.create(pre_restore, reserve=True)
                    except OSError as exc:
                        # 磁盘写满 / 目录只读 / 文件被占用：安全备份没写出来就绝不动活库。
                        raise RestoreSafetyError(
                            "恢复失败：无法创建恢复前的安全备份，原数据库未被修改。"
                            "请检查磁盘空间与文件权限后重试。"
                        ) from exc
                    # 安全备份的审计写入会重新占用引擎连接；切换前再次释放，让
                    # ``os.replace`` 面对一个没有本进程句柄的数据库文件。
                    self.database.dispose()
                    original_copy: Path | None = None
                    staged: Path | None = None
                    switched = False
                    try:
                        # 原库自包含副本（排他条件已确认、WAL 已折叠），供切换之后失败时回滚。
                        original_copy = database_path.with_name(database_path.name + ".pre-restore-original")
                        # 候选库先落到目标**同目录**：跨卷 os.replace 在 Windows 上会失败。
                        staged = database_path.with_name(database_path.name + ".restore-staging")
                        original_copy.unlink(missing_ok=True)
                        staged.unlink(missing_ok=True)
                        shutil.copy2(database_path, original_copy)
                        shutil.copy2(restored_database, staged)
                        try:
                            # 原子切换：Windows 上任何仍被打开的文件都会让 rename 失败，
                            # 失败时目标文件保持原样，正好是最后一层排他兜底。
                            os.replace(staged, database_path)
                        except OSError as exc:
                            raise RestoreSafetyError(
                                "恢复被拒绝：无法安全替换数据库文件（可能有其他窗口或程序正在使用数据库，"
                                "或目标目录不可写）。原数据库未被修改，请关闭其他窗口后重试。"
                            ) from exc
                        switched = True
                        # Import workbooks and logs may be open in the running process, and
                        # the standards tree is rebuildable.  Merge in place rather than
                        # deleting locked files or a subtree this archive does not own.
                        self._merge_application_data(temporary_path)
                        self.database.reconnect()
                        self.database.initialize()
                    except BaseException as exc:
                        if staged is not None:
                            staged.unlink(missing_ok=True)
                        if switched:
                            try:
                                self._rollback_database(original_copy, pre_restore)
                            except RestoreSafetyError as rollback_exc:
                                raise rollback_exc from exc
                            if isinstance(exc, RestoreSafetyError):
                                raise
                            raise RestoreSafetyError(
                                "恢复失败：后续步骤未完成，已自动回滚为恢复前状态，原数据库未被修改。"
                            ) from exc
                        if original_copy is not None:
                            original_copy.unlink(missing_ok=True)
                        if isinstance(exc, RestoreSafetyError):
                            raise
                        raise RestoreSafetyError("恢复失败：原数据库未被修改。") from exc
                    # 切换与初始化都成功，回滚副本完成使命。
                    if original_copy is not None:
                        original_copy.unlink(missing_ok=True)
        except BaseException:
            # 无论在哪一步失败，本进程的连接都必须回到可用状态再抛出
            # （回滚路径自己已经重连过，这里是幂等兜底，保证每个出口一致）。
            self.database.reconnect()
            raise
        self.audit.append(
            "BACKUP_RESTORE",
            "backup",
            str(path),
            {
                "backup_id": manifest["backup_id"],
                # ``validate`` normalises this, including for historical
                # archives written before the scope split.
                "scope": manifest["scope"],
            },
        )

    def _merge_application_data(self, temporary_path: Path) -> None:
        """Merge the archive's application-data subtrees into the live directory (in place, additive only)."""

        for root_name in self.APPLICATION_DATA_ROOTS:
            restored_root = temporary_path / root_name
            if not restored_root.exists():
                continue
            target_root = getattr(self.paths, root_name)
            target_root.mkdir(parents=True, exist_ok=True)
            shutil.copytree(restored_root, target_root, dirs_exist_ok=True)

    def _rollback_database(self, original_copy: Path | None, pre_restore: Path) -> None:
        """切换之后任何一步失败：把活库恢复成切换前的原库，并重新建立连接。

        必须先删掉属于刚切换进来的那个库的 ``-wal``/``-shm`` —— 它们叠在原库上
        就是 H01 的“恢复成功但数据是旧的”。边车删不掉或回滚副本缺失/替换失败时，
        不做半吊子回滚，直接把恢复前安全备份的路径连同中文原因一起抛出来。
        """

        database_path = self.database.path
        self.database.dispose()
        for sidecar in _sidecar_paths(database_path):
            if not sidecar.exists():
                continue
            try:
                sidecar.unlink()
            except OSError as exc:
                raise RestoreSafetyError(
                    f"恢复失败，且无法自动回滚原数据库（{sidecar.name} 仍被占用）。"
                    f"请先关闭其他窗口后重试，也可用恢复前安全备份恢复：{pre_restore}"
                ) from exc
        if original_copy is None or not original_copy.exists():
            raise RestoreSafetyError(
                f"恢复失败，且无法自动回滚原数据库（回滚副本缺失）。"
                f"请勿继续写入，可用恢复前安全备份恢复：{pre_restore}"
            )
        try:
            os.replace(original_copy, database_path)
        except OSError as exc:
            raise RestoreSafetyError(
                f"恢复失败，且无法自动回滚原数据库（文件被占用）。"
                f"请先关闭其他窗口后重试，也可用恢复前安全备份恢复：{pre_restore}"
            ) from exc
        self.database.reconnect()
