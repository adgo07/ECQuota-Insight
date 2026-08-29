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
from pathlib import Path, PurePosixPath
from uuid import uuid4

from .database import DatabaseManager
from .paths import AppPaths
from .repositories import AuditRepository


class BackupValidationError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    BACKUP_ROOTS = ("standards", "imports", "logs")

    def __init__(self, paths: AppPaths, database: DatabaseManager, audit: AuditRepository | None = None) -> None:
        self.paths = paths
        self.database = database
        self.audit = audit or AuditRepository(database)

    def create(self, path: Path) -> Path:
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="uebench-backup-") as temporary:
            temporary_path = Path(temporary)
            database_copy = temporary_path / "uebench.sqlite3"
            source = sqlite3.connect(self.database.path)
            destination = sqlite3.connect(database_copy)
            try:
                source.backup(destination)
            finally:
                destination.close()
                source.close()

            files: dict[str, str] = {"uebench.sqlite3": _sha256(database_copy)}
            source_files: list[tuple[str, Path]] = []
            for root_name in self.BACKUP_ROOTS:
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
                "files": files,
            }
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(database_copy, "uebench.sqlite3")
                for archive_name, item in source_files:
                    archive.write(item, archive_name)
                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                )
        self.audit.append("BACKUP_CREATE", "backup", str(path), {"backup_id": manifest["backup_id"]})
        return path

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
            files = manifest.get("files")
            if not isinstance(files, dict) or not files:
                raise BackupValidationError("备份清单中的 files 无效")
            if any(not isinstance(name, str) or not _safe_member(name) for name in files):
                raise BackupValidationError("备份清单包含不安全路径")
            allowed_roots = ("standards/", "imports/", "logs/")
            if any(name != "uebench.sqlite3" and not name.startswith(allowed_roots) for name in files):
                raise BackupValidationError("备份清单包含不允许的文件根目录")
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
            return manifest

    def restore(self, path: Path) -> None:
        manifest = self.validate(path)
        pre_restore = self.paths.backups / f"pre-restore-{datetime.now():%Y%m%d-%H%M%S}.uebackup"
        self.create(pre_restore)
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
            restored_standards = temporary_path / "standards"
            self.database.dispose()
            shutil.copy2(restored_database, self.database.path)
            if self.paths.standards.exists():
                shutil.rmtree(self.paths.standards)
            if restored_standards.exists():
                shutil.copytree(restored_standards, self.paths.standards)
            else:
                self.paths.standards.mkdir(parents=True, exist_ok=True)
            # Import workbooks and logs may be open in the running process.
            # Merge them in place rather than deleting locked files; the
            # restored snapshot is still available and old extra log lines are
            # harmless audit history.
            for root_name in ("imports", "logs"):
                restored_root = temporary_path / root_name
                if restored_root.exists():
                    target_root = getattr(self.paths, root_name)
                    target_root.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(restored_root, target_root, dirs_exist_ok=True)
            self.database.reconnect()
            self.database.initialize()
        self.audit.append("BACKUP_RESTORE", "backup", str(path), {"backup_id": manifest["backup_id"]})
