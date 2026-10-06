from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from uuid import uuid4

from .backup_paths import (
    PRE_MIGRATION_PREFIX,
    PRE_PACKAGE_PREFIX,
    PRE_RESTORE_PREFIX,
    BackupPathError,
    claim_reserved_backup_path,
    reserve_unique_backup_path,
)
from .database import DatabaseManager
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
    "claim_reserved_backup_path",
    "create_sqlite_snapshot",
    "reserve_unique_backup_path",
]


class BackupValidationError(ValueError):
    pass


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
        """
        manifest = self.validate(path)
        # The pre-restore safety backup is a *safety* backup: its name comes from
        # the one shared namer (microsecond stamp + short uuid) and the name is
        # exclusively reserved before it is written, so two restores in the same
        # second — or two at the same microsecond — can never target the same
        # file and destroy the earlier safety backup.
        pre_restore = reserve_unique_backup_path(self.paths.backups, PRE_RESTORE_PREFIX)
        self.create(pre_restore, reserve=True)
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
            self.database.dispose()
            shutil.copy2(restored_database, self.database.path)
            # Import workbooks and logs may be open in the running process, and
            # the standards tree is rebuildable.  Merge in place rather than
            # deleting locked files or a subtree this archive does not own.
            for root_name in self.APPLICATION_DATA_ROOTS:
                restored_root = temporary_path / root_name
                if not restored_root.exists():
                    continue
                target_root = getattr(self.paths, root_name)
                target_root.mkdir(parents=True, exist_ok=True)
                shutil.copytree(restored_root, target_root, dirs_exist_ok=True)
            self.database.reconnect()
            self.database.initialize()
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
