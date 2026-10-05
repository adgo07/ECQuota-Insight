from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Literal
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from packaging.version import Version
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import desc, select

from uebench import RULE_ENGINE_VERSION, __version__
from uebench.domain.models import PackageHistoryEntry, PublicationStatus, StandardDefinition

from .backup import BackupService
from .database import DatabaseManager, PackageRow, StandardRow
from .paths import AppPaths
from .repositories import AuditRepository, SqlStandardRepository

logger = logging.getLogger(__name__)

#: Audit action recorded when install removes ``sources`` directories that an
#: earlier version of this product wrote under the user data directory.
AUDIT_LEGACY_SOURCES_REMOVED = "STANDARD_PACKAGE_LEGACY_SOURCES_REMOVED"

#: Glob-compatible prefix of the pre-install safety backup.  Existing callers
#: and tools glob ``pre-package-*.uebackup``.
BACKUP_NAME_PREFIX = "pre-package-"


class StandardPackageError(ValueError):
    pass


class PackageFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size: int = Field(ge=0)
    kind: Literal["definition", "source", "correction"]

    @model_validator(mode="after")
    def validate_path_kind(self) -> "PackageFile":
        pure = PurePosixPath(self.path)
        if (
            not self.path
            or self.path.endswith("/")
            or pure.is_absolute()
            or "\\" in self.path
            or ":" in self.path
            or ".." in pure.parts
            or pure.name in {"", ".", ".."}
        ):
            raise ValueError("标准包文件路径不安全或为空")
        if self.kind == "definition" and not (
            self.path.startswith("definitions/") and self.path.endswith(".json")
        ):
            raise ValueError("definition 文件必须位于 definitions/ 且为 JSON")
        if self.kind == "source" and not self.path.startswith("sources/"):
            raise ValueError("source 文件必须位于 sources/")
        if self.kind == "correction" and self.path != "corrections.json":
            raise ValueError("correction 文件必须为 corrections.json")
        return self


#: How a package relates to the standard source documents its definitions cite.
#:
#: ``embedded``
#:     The package ships ``sources/*`` members next to the definitions.  This is
#:     the historical behaviour and remains the default, so every already
#:     published/archived package keeps loading and installing unchanged.
#: ``provenance-only``
#:     The package ships **no** ``sources/*`` member.  Every definition still
#:     carries its ``source_file`` / ``source_sha256`` provenance, but the
#:     standard原文 itself is never distributed, stored or opened by the product
#:     (owner decision, 0.2.0: full standard PDFs must not be distributed).
SourcePolicy = Literal["embedded", "provenance-only"]


class PackageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    package_id: str
    data_version: str
    issued_at: datetime
    minimum_app_version: str
    package_mode: Literal["full", "incremental"] = "full"
    rule_engine_version: str = RULE_ENGINE_VERSION
    parent_package_id: str | None = None
    #: Self-describing distribution mode of the standard原文 (see SourcePolicy).
    #: Defaults to the legacy value: a manifest without this field is an
    #: ``embedded`` package and is verified exactly as before.
    source_policy: SourcePolicy = "embedded"
    standard_count: int = Field(ge=0)
    rule_count: int = Field(ge=0)
    files: list[PackageFile]

    @model_validator(mode="after")
    def validate_lineage(self) -> "PackageManifest":
        if self.package_mode == "full" and self.parent_package_id:
            raise ValueError("完整标准包不应包含 parent_package_id")
        if self.package_mode == "incremental" and self.parent_package_id == self.package_id:
            raise ValueError("增量标准包不能把自己作为父包")
        return self


class PackageValidationReport(BaseModel):
    valid: bool
    manifest: PackageManifest | None = None
    definitions: list[StandardDefinition] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    package_sha256: str | None = None


class PackageInstallResult(BaseModel):
    package_id: str
    data_version: str
    standards_installed: int
    backup_path: str
    #: Number of legacy product-installed ``sources`` directories removed from
    #: the user data directory before the safety backup was taken.  ``0`` for a
    #: data directory that never held them.  This is the *verified* count: it is
    #: only ever reported after a post-deletion re-scan proved the targets gone.
    removed_source_directory_count: int = 0
    #: Number of files that lived inside those directories.
    removed_source_file_count: int = 0
    #: Number of legacy standard原文 PDFs that older versions left **flat** in
    #: ``standards/<package_id>/`` (no ``sources`` sub-directory).  Also a
    #: verified count.
    removed_flat_source_file_count: int = 0


def _backup_path(directory: Path) -> Path:
    """Return a **new** pre-install safety backup path that does not yet exist.

    The name is unique to the microsecond *and* guarded against collision: if
    the computed path already exists (same microsecond, restored directory, or
    a clock that does not advance) a ``-1``/``-2``/… suffix is appended until a
    free name is found.  A safety backup is never silently replaced.

    ``BackupService.create`` writes to the path it is given, so choosing the
    name here is what keeps two back-to-back installs from destroying the first
    backup — the previous implementation was precise only to the second.
    """
    directory = Path(directory)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    candidate = directory / f"{BACKUP_NAME_PREFIX}{stamp}.uebackup"
    if not candidate.exists():
        return candidate
    sequence = 1
    while True:
        distinct = directory / f"{BACKUP_NAME_PREFIX}{stamp}-{sequence}.uebackup"
        if not distinct.exists():
            return distinct
        sequence += 1


def _canonical_json(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(name: str) -> bool:
    pure = PurePosixPath(name)
    return (
        bool(name)
        and not pure.is_absolute()
        and ".." not in pure.parts
        and "\\" not in name
        and ":" not in pure.parts[0]
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _data_version_key(value: str) -> tuple[int, int, int, int] | None:
    """Parse the package's sortable YYYY.MM-channel.revision convention."""
    match = re.fullmatch(
        r"(?P<year>\d{4})\.(?P<minor>\d+)(?:-(?P<channel>[A-Za-z][A-Za-z0-9_-]*))?(?:\.(?P<revision>\d+))?",
        value.strip(),
    )
    if match is None:
        return None
    channel = (match.group("channel") or "").lower()
    channel_rank = {"draft": 0, "reviewed": 1, "published": 2}.get(channel)
    if channel_rank is None:
        channel_rank = 1 if not channel else None
    if channel_rank is None:
        return None
    return (
        int(match.group("year")),
        int(match.group("minor")),
        channel_rank,
        int(match.group("revision") or 0),
    )

def _definition_matches(payload: str, incoming: StandardDefinition) -> bool:
    """Return true only when an installed rule has identical canonical JSON."""
    try:
        installed = StandardDefinition.model_validate_json(payload)
    except ValueError:
        return False
    return _sha256_bytes(_canonical_json(installed.model_dump(mode="json"))) == _sha256_bytes(
        _canonical_json(incoming.model_dump(mode="json"))
    )




def _load_parent_package(path: Path) -> tuple[PackageManifest, list[StandardDefinition], bytes | None]:
    """Load definitions from a previously built package for developer-side diffing.

    This helper is intentionally used only while creating a new package. The
    runtime installation path still verifies the incoming package signature and
    every listed file independently.
    """
    path = path.resolve()
    if not path.exists() or not path.is_file():
        raise StandardPackageError(f"父标准包不存在或不是文件：{path}")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise StandardPackageError("父标准包包含重复文件")
            manifest = PackageManifest.model_validate_json(archive.read("manifest.json"))
            definitions: list[StandardDefinition] = []
            corrections_data: bytes | None = None
            for item in manifest.files:
                if item.kind == "definition":
                    definitions.append(StandardDefinition.model_validate_json(archive.read(item.path)))
                elif item.kind == "correction":
                    corrections_data = archive.read(item.path)
            if len(definitions) != manifest.standard_count:
                raise StandardPackageError("父标准包定义数量与清单不一致")
            return manifest, definitions, corrections_data
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, ValueError) as exc:
        raise StandardPackageError(f"无法读取父标准包：{path}") from exc

class StandardPackageBuilder:
    """Developer-side package builder; the private key is never shipped with the app."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self.private_key = private_key

    def build_incremental(
        self,
        output: Path,
        definitions: list[StandardDefinition],
        source_files: dict[str, Path] | None = None,
        *,
        parent_package: Path,
        data_version: str,
        minimum_app_version: str = "0.1.0",
        rule_engine_version: str = RULE_ENGINE_VERSION,
        corrections: list[dict] | None = None,
        package_id: str | None = None,
        issued_at: datetime | None = None,
        distribute_sources: bool = True,
    ) -> Path:
        """Build a signed package containing only definitions changed from parent.

        Incremental packages cannot remove a definition; publishing a removed
        or replaced complete catalogue must use the full build method.
        The parent package id is copied from the inspected manifest so callers
        cannot accidentally attach the diff to another lineage.

        ``distribute_sources=False`` builds a **provenance-only** incremental
        package: no ``sources/*`` member is written, and ``source_files`` may be
        omitted entirely.
        """
        parent_manifest, parent_definitions, parent_corrections_data = _load_parent_package(parent_package)
        parent_by_key = {
            (definition.id, definition.version, definition.rule_revision): _canonical_json(
                definition.model_dump(mode="json")
            )
            for definition in parent_definitions
        }
        current_keys = {
            (definition.id, definition.version, definition.rule_revision)
            for definition in definitions
        }
        removed = sorted(
            parent_key
            for parent_key in set(parent_by_key) - current_keys
            if not any(
                current_key[:2] == parent_key[:2] and current_key[2] > parent_key[2]
                for current_key in current_keys
            )
        )
        if removed:
            removed_text = "、".join(
                f"{standard_id}@{version}/r{revision}"
                for standard_id, version, revision in removed
            )
            raise StandardPackageError(
                "增量包不能删除父包已有规则：" + removed_text + "；请生成完整包"
            )
        changed = [
            definition
            for definition in definitions
            if parent_by_key.get((definition.id, definition.version, definition.rule_revision))
            != _canonical_json(definition.model_dump(mode="json"))
        ]
        correction_changed = False
        if corrections is not None:
            correction_changed = _canonical_json({"corrections": corrections}) != (parent_corrections_data or b"")
        if not changed and not correction_changed:
            raise StandardPackageError("当前规则与父标准包完全相同，无需生成增量包")
        return self.build(
            output,
            changed,
            source_files,
            data_version=data_version,
            minimum_app_version=minimum_app_version,
            package_mode="incremental",
            rule_engine_version=rule_engine_version,
            parent_package_id=parent_manifest.package_id,
            corrections=corrections,
            package_id=package_id,
            issued_at=issued_at,
            distribute_sources=distribute_sources,
        )
    def build(
        self,
        output: Path,
        definitions: list[StandardDefinition],
        source_files: dict[str, Path] | None = None,
        *,
        data_version: str,
        minimum_app_version: str = "0.1.0",
        package_mode: Literal["full", "incremental"] = "full",
        rule_engine_version: str = RULE_ENGINE_VERSION,
        parent_package_id: str | None = None,
        corrections: list[dict] | None = None,
        package_id: str | None = None,
        issued_at: datetime | None = None,
        distribute_sources: bool = True,
    ) -> Path:
        """Build a signed standard package.

        Two distribution modes exist and are both recorded in the manifest as
        ``source_policy`` (self-describing, so a consumer can tell them apart
        without guessing):

        * ``distribute_sources=True`` (default) — ``embedded``: every definition
          must have its standard原文 provided in ``source_files`` and it is
          written to a ``sources/*`` member.  This is the historical behaviour
          and is unchanged.
        * ``distribute_sources=False`` — ``provenance-only``: definitions keep
          their ``source_file`` / ``source_sha256`` provenance, but **no**
          ``sources/*`` member is written and no standard原文 is required.  The
          owner decision for 0.2.0 is that a formal package must not distribute,
          store or open full standard PDFs.

        A definition is never silently dropped: an ``embedded`` package still
        hard-fails on a missing or hash-mismatching原文.
        """
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        package_id = package_id or str(uuid4())
        issued_at = issued_at or datetime.now(timezone.utc)
        if not distribute_sources and source_files:
            raise StandardPackageError(
                "provenance-only 标准包不写入 sources/*，不得提供标准原文文件"
            )
        entries: dict[str, bytes] = {}
        rule_count = 0
        definition_keys: set[tuple[str, str, int]] = set()
        for definition in definitions:
            definition_key = (definition.id, definition.version, definition.rule_revision)
            if definition_key in definition_keys:
                raise StandardPackageError(
                    f"标准包包含重复标准版本：{definition.id}@{definition.version}/r{definition.rule_revision}"
                )
            definition_keys.add(definition_key)
            revision_suffix = "" if definition.rule_revision == 1 else f"-r{definition.rule_revision}"
            path = f"definitions/{definition.id}-{definition.version}{revision_suffix}.json"
            data = _canonical_json(definition.model_dump(mode="json"))
            entries[path] = data
            rule_count += sum(len(product.indicators) for product in definition.products)
            if not distribute_sources:
                # Provenance stays on the definition; only the file is not shipped.
                continue
            source = (source_files or {}).get(definition.source_file)
            if source is None:
                raise StandardPackageError(f"缺少标准原文：{definition.source_file}")
            source_data = source.read_bytes()
            if _sha256_bytes(source_data) != definition.source_sha256.lower():
                raise StandardPackageError(f"标准原文哈希与定义不一致：{definition.source_file}")
            source_path = f"sources/{definition.source_file}"
            if not _safe_name(definition.source_file):
                raise StandardPackageError(f"标准原文文件名不安全：{definition.source_file}")
            existing_source = entries.get(source_path)
            if existing_source is not None and existing_source != source_data:
                raise StandardPackageError(f"不同标准使用同一原文文件名但内容不同：{definition.source_file}")
            entries[source_path] = source_data
        corrections_data = _canonical_json({"corrections": corrections or []})
        entries["corrections.json"] = corrections_data

        package_files = []
        for path, data in sorted(entries.items()):
            if path.startswith("definitions/"):
                kind = "definition"
            elif path.startswith("sources/"):
                kind = "source"
            else:
                kind = "correction"
            package_files.append(PackageFile(path=path, sha256=_sha256_bytes(data), size=len(data), kind=kind))
        manifest = PackageManifest(
            package_id=package_id,
            data_version=data_version,
            issued_at=issued_at,
            minimum_app_version=minimum_app_version,
            package_mode=package_mode,
            rule_engine_version=rule_engine_version,
            parent_package_id=parent_package_id,
            source_policy="embedded" if distribute_sources else "provenance-only",
            standard_count=len(definitions),
            rule_count=rule_count,
            files=package_files,
        )
        manifest_bytes = _canonical_json(manifest.model_dump(mode="json"))
        signature = self.private_key.sign(manifest_bytes)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", manifest_bytes)
            archive.writestr("signature.ed25519", signature)
            for path, data in entries.items():
                archive.writestr(path, data)
        return output


class StandardPackageService:
    def __init__(
        self,
        paths: AppPaths,
        database: DatabaseManager,
        public_key: Ed25519PublicKey,
        backup: BackupService,
        standards: SqlStandardRepository | None = None,
        audit: AuditRepository | None = None,
    ) -> None:
        self.paths = paths
        self.database = database
        self.public_key = public_key
        self.audit = audit or AuditRepository(database)
        self.standards = standards or SqlStandardRepository(database, self.audit)
        self.backup = backup

    @staticmethod
    def load_public_key(path: Path) -> Ed25519PublicKey:
        key = serialization.load_pem_public_key(path.read_bytes())
        if not isinstance(key, Ed25519PublicKey):
            raise StandardPackageError("更新公钥不是 Ed25519 公钥")
        return key

    def discover(self, directory: Path, *, recursive: bool = False) -> list[Path]:
        """List candidate .uebench files from a local or mounted shared directory.

        Discovery never verifies or installs a package. Call ``preview`` for
        each returned path before showing it as an update or passing it to
        ``install``. A mounted NAS/UNC path is treated like any other Path.
        """
        directory = directory.expanduser().resolve()
        if not directory.exists():
            raise FileNotFoundError(f"标准包目录不存在：{directory}")
        if not directory.is_dir():
            raise NotADirectoryError(f"标准包路径不是目录：{directory}")
        candidates = directory.rglob("*") if recursive else directory.iterdir()
        paths = [path.resolve() for path in candidates if path.is_file() and path.suffix.lower() == ".uebench"]
        return sorted(paths, key=lambda path: (path.name.casefold(), str(path).casefold()))

    def latest_manifest(self) -> PackageManifest | None:
        """返回最近一次成功安装的标准包清单，供应用层展示。"""
        with self.database.session() as session:
            row = session.scalar(
                select(PackageRow)
                .order_by(desc(PackageRow.issued_at), desc(PackageRow.installed_at))
                .limit(1)
            )
        if row is None:
            return None
        return PackageManifest.model_validate_json(row.manifest_json)

    def list_history(self, limit: int = 50) -> list[PackageHistoryEntry]:
        """Return successful package installs newest first as domain DTOs."""
        if limit < 1:
            return []
        limit = min(limit, 1000)
        with self.database.session() as session:
            rows = session.scalars(
                select(PackageRow)
                .order_by(desc(PackageRow.installed_at), desc(PackageRow.issued_at))
                .limit(limit)
            ).all()
        entries: list[PackageHistoryEntry] = []
        for row in rows:
            manifest = PackageManifest.model_validate_json(row.manifest_json)
            entries.append(
                PackageHistoryEntry(
                    package_id=manifest.package_id,
                    data_version=manifest.data_version,
                    package_mode=manifest.package_mode,
                    issued_at=manifest.issued_at,
                    installed_at=row.installed_at,
                    parent_package_id=manifest.parent_package_id,
                    standard_count=manifest.standard_count,
                    rule_count=manifest.rule_count,
                    package_sha256=row.package_sha256,
                )
            )
        return entries
    def preview(self, path: Path) -> PackageValidationReport:
        path = path.resolve()
        errors: list[str] = []
        warnings: list[str] = []
        definitions: list[StandardDefinition] = []
        manifest: PackageManifest | None = None
        if path.exists() and not path.is_file():
            errors.append("标准包路径不是文件")
        package_sha256 = _sha256_path(path) if path.is_file() else None
        if path.suffix.lower() != ".uebench":
            errors.append("标准包扩展名必须为 .uebench")
        if not path.exists():
            errors.append("标准包文件不存在")
            return PackageValidationReport(valid=False, errors=errors)
        if not path.is_file():
            return PackageValidationReport(valid=False, errors=errors)
        try:
            with zipfile.ZipFile(path, "r") as archive:
                names = archive.namelist()
                if any(not _safe_name(name) for name in names):
                    raise StandardPackageError("标准包包含不安全路径")
                duplicate_names = sorted(name for name, count in Counter(names).items() if count > 1)
                if duplicate_names:
                    errors.append(f"标准包包含重复文件：{', '.join(duplicate_names)}")
                manifest_bytes = archive.read("manifest.json")
                signature = archive.read("signature.ed25519")
                try:
                    self.public_key.verify(signature, manifest_bytes)
                except InvalidSignature as exc:
                    raise StandardPackageError("标准包签名无效") from exc
                manifest = PackageManifest.model_validate_json(manifest_bytes)
                if not _safe_name(manifest.package_id):
                    errors.append("标准包 package_id 包含不安全路径字符")
                if Version(manifest.minimum_app_version) > Version(__version__):
                    errors.append(
                        f"标准包要求软件版本 {manifest.minimum_app_version}，当前版本为 {__version__}"
                    )
                if manifest.rule_engine_version != RULE_ENGINE_VERSION:
                    errors.append(
                        f"标准包规则引擎版本为 {manifest.rule_engine_version}，当前软件为 {RULE_ENGINE_VERSION}"
                    )
                listed = {item.path: item for item in manifest.files}
                manifest_duplicate_paths = sorted(
                    path for path, count in Counter(item.path for item in manifest.files).items() if count > 1
                )
                if manifest_duplicate_paths:
                    errors.append(
                        "清单包含重复文件路径：" + ", ".join(manifest_duplicate_paths)
                    )
                expected_names = set(listed) | {"manifest.json", "signature.ed25519"}
                extras = set(names) - expected_names
                missing = expected_names - set(names)
                if extras:
                    errors.append(f"标准包包含未登记文件：{', '.join(sorted(extras))}")
                if missing:
                    errors.append(f"标准包缺少文件：{', '.join(sorted(missing))}")
                listed_source_paths = sorted(
                    item.path for item in manifest.files if item.kind == "source"
                )
                if manifest.source_policy == "provenance-only" and listed_source_paths:
                    errors.append(
                        "标准包自述不随包分发标准原文（source_policy=provenance-only），"
                        f"但清单仍登记原文：{', '.join(listed_source_paths)}"
                    )
                for item in manifest.files:
                    data = archive.read(item.path)
                    if len(data) != item.size or _sha256_bytes(data) != item.sha256:
                        errors.append(f"文件大小或哈希不匹配：{item.path}")
                    if item.kind == "definition":
                        definition = StandardDefinition.model_validate_json(data)
                        definitions.append(definition)
                        for product in definition.products:
                            for indicator in product.indicators:
                                if not indicator.source_references:
                                    errors.append(f"标准 {definition.number}/{indicator.id} 缺少原文依据")
                                for reference in indicator.source_references:
                                    if reference.standard_number != definition.number:
                                        errors.append(
                                            f"标准 {definition.number}/{indicator.id} 的来源标准号不一致："
                                            f"{reference.standard_number}"
                                        )
                                    if reference.source_file != definition.source_file:
                                        errors.append(
                                            f"标准 {definition.number}/{indicator.id} 的来源文件不一致："
                                            f"{reference.source_file}"
                                        )
                                    if reference.source_sha256.lower() != definition.source_sha256.lower():
                                        errors.append(
                                            f"标准 {definition.number}/{indicator.id} 的来源哈希不一致："
                                            f"{reference.source_file}"
                                        )
                        if definition.publication_status is not PublicationStatus.PUBLISHED:
                            errors.append(
                                f"标准 {definition.number} 的规则状态为 {definition.publication_status.value}，"
                                "标准包只能包含 published 规则"
                            )
                if len(definitions) != manifest.standard_count:
                    errors.append("标准定义数量与清单不一致")
                actual_rules = sum(
                    len(product.indicators) for definition in definitions for product in definition.products
                )
                if actual_rules != manifest.rule_count:
                    errors.append("指标规则数量与清单不一致")
                source_entries = {
                    PurePosixPath(item.path).name: item for item in manifest.files if item.kind == "source"
                }
                source_names = [PurePosixPath(item.path).name for item in manifest.files if item.kind == "source"]
                duplicate_source_names = sorted(
                    name for name, count in Counter(source_names).items() if count > 1
                )
                if duplicate_source_names:
                    errors.append(
                        "标准包原文文件名冲突，安装时会覆盖：" + ", ".join(duplicate_source_names)
                    )
                definition_keys = [
                    (definition.id, definition.version, definition.rule_revision) for definition in definitions
                ]
                duplicate_definitions = sorted(
                    f"{standard_id}@{version}/r{rule_revision}"
                    for (standard_id, version, rule_revision), count in Counter(definition_keys).items()
                    if count > 1
                )
                if duplicate_definitions:
                    errors.append(
                        "标准包包含重复标准版本：" + ", ".join(duplicate_definitions)
                    )
                numbers = [definition.number for definition in definitions]
                duplicate_numbers = sorted(number for number, count in Counter(numbers).items() if count > 1)
                if duplicate_numbers:
                    errors.append("标准包包含重复标准编号：" + ", ".join(duplicate_numbers))
                definition_numbers = set(numbers)
                for definition in definitions:
                    if definition.lifecycle_status.value == "obsolete" and definition.obsolete_date is None:
                        errors.append(f"标准 {definition.number} 标记为已替代但缺少 obsolete_date")
                    for replacement in definition.replaced_by:
                        if replacement not in definition_numbers:
                            warnings.append(f"标准 {definition.number} 的替代标准 {replacement} 不在本包中；安装后仍保留历史关系")
                    for superseded in definition.supersedes:
                        if superseded not in definition_numbers:
                            warnings.append(f"标准 {definition.number} 声明替代 {superseded} 不在本包中；请确认是否另包提供")
                for definition in definitions:
                    source = source_entries.get(definition.source_file)
                    if manifest.source_policy == "provenance-only":
                        # No standard原文 is distributed with this package.  The
                        # definition's provenance (source_file/source_sha256 and
                        # per-indicator source_references) is still verified above
                        # and below; only the file's presence/hash is not demanded.
                        if source is not None and source.sha256 != definition.source_sha256.lower():
                            errors.append(
                                f"标准原文哈希与定义不一致：{definition.source_file}"
                            )
                        continue
                    if source is None:
                        errors.append(f"标准定义缺少原文：{definition.source_file}")
                    elif source.sha256 != definition.source_sha256.lower():
                        errors.append(f"标准原文哈希与定义不一致：{definition.source_file}")
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, StandardPackageError, ValueError) as exc:
            errors.append(str(exc))

        if manifest is not None:
            with self.database.session() as session:
                for definition in definitions:
                    existing_version = session.scalar(
                        select(StandardRow).where(
                            StandardRow.standard_id == definition.id,
                            StandardRow.version == definition.version,
                            StandardRow.rule_revision == definition.rule_revision,
                        )
                    )
                    if existing_version is not None and not _definition_matches(
                        existing_version.definition_json, definition
                    ):
                        errors.append(
                            f"标准版本已存在：{definition.number} {definition.version}，"
                            "如需变更必须递增标准包/规则版本"
                        )
                    elif existing_version is not None:
                        warnings.append(
                            f"标准版本已存在且内容一致：{definition.number} {definition.version}，"
                            "安装时将保留同一规则内容"
                        )
                existing = session.get(PackageRow, manifest.package_id)
                if existing is not None:
                    errors.append("该标准包已安装")
                latest = session.scalar(
                    select(PackageRow)
                    .order_by(desc(PackageRow.issued_at), desc(PackageRow.installed_at))
                    .limit(1)
                )
                if manifest.package_mode == "incremental":
                    if not manifest.parent_package_id:
                        errors.append("增量标准包缺少 parent_package_id")
                    else:
                        parent = session.get(PackageRow, manifest.parent_package_id)
                        if parent is None:
                            errors.append(f"增量标准包依赖的父包未安装：{manifest.parent_package_id}")
                        elif latest is not None and latest.package_id != manifest.parent_package_id:
                            errors.append(
                                f"增量标准包父包不是当前最新包：要求 {manifest.parent_package_id}，当前为 {latest.package_id}"
                            )
                if latest is not None:
                    if _as_utc(manifest.issued_at) < _as_utc(latest.issued_at):
                        errors.append("标准包发布时间早于当前已安装版本，禁止降级")
                    try:
                        latest_manifest = PackageManifest.model_validate_json(latest.manifest_json)
                    except ValueError:
                        latest_manifest = None
                    incoming_key = _data_version_key(manifest.data_version)
                    latest_key = _data_version_key(latest_manifest.data_version) if latest_manifest else None
                    if incoming_key is not None and latest_key is not None and incoming_key < latest_key:
                        errors.append("标准包数据版本早于当前已安装版本，禁止降级")
                    elif manifest.data_version != (latest_manifest.data_version if latest_manifest else None) and (incoming_key is None or latest_key is None):
                        warnings.append("标准包数据版本格式无法排序，将仅按发布时间防止降级")
        return PackageValidationReport(
            valid=not errors,
            manifest=manifest,
            definitions=definitions,
            errors=errors,
            warnings=warnings,
            package_sha256=package_sha256,
        )

    #: How many times a failed legacy原文 deletion is retried before the install
    #: is aborted.  Windows transient locks (indexer, anti-virus scanner, a
    #: shell thumbnail handler) routinely release within milliseconds, so a few
    #: short retries turn a spurious abort into a clean install.  A *permanent*
    #: lock is never retried into success: the retry is only allowed to make the
    #: cleanup more robust, never to record a success the filesystem denies.
    LEGACY_CLEANUP_ATTEMPTS = 3
    #: Seconds between the deletion attempts above.
    LEGACY_CLEANUP_RETRY_DELAY = 0.2

    def _scan_legacy_targets(self) -> tuple[list[Path], list[Path], int]:
        """Detect legacy product-installed standard原文 under ``paths.standards``.

        Two historical layouts really shipped, and both are still found in the
        field (an old install may even hold both at once, for example when the
        package changed its layout between two upgrades):

        ``standards/<package_id>/*.pdf``
            the **flat** layout an early version wrote;
        ``standards/<package_id>/sources/**``
            the later layout, where the whole原文 directory was copied.

        Scope is deliberately narrow.  Only directories that are **direct**
        children of ``paths.standards`` are considered a package directory, and
        inside one only (a) a direct ``sources`` directory and (b) direct
        ``*.pdf`` children are legacy products of this software.  Nothing else
        is a target: not a PDF at the standards root, not one inside a user
        sub-directory, not a deeper ``sources`` directory.

        Symlinks and junctions are never followed out of the standards tree:
        a package directory whose resolved path leaves ``paths.standards`` is
        skipped entirely, ``sources`` is never entered or deleted through a
        link, and link members are neither counted nor dereferenced (the
        ``rglob`` walk does not descend into them).

        This function only **reads** the filesystem; it is used both as the
        pre-deletion detector and as the post-deletion verifier, so that "what
        must be gone" and "what is still there" are measured by the same rule
        and no target can escape verification by being described differently.

        Returns ``(sources_directories, flat_pdf_files, files_inside_directories)``.
        """
        standards = Path(self.paths.standards)
        if not standards.is_dir():
            return [], [], 0
        resolved_standards = standards.resolve()
        sources_directories: list[Path] = []
        flat_pdfs: list[Path] = []
        files_inside = 0
        for package_directory in sorted(standards.iterdir()):
            if not package_directory.is_dir() or package_directory.is_symlink():
                continue
            resolved_package = package_directory.resolve()
            # Never follow a package directory out of ``paths.standards`` (on
            # Windows a junction is not reported by ``is_symlink``).
            if not resolved_package.is_relative_to(resolved_standards):
                continue
            candidate = package_directory / "sources"
            if candidate.is_dir() and not candidate.is_symlink():
                # A package directory is a direct child of ``paths.standards``,
                # so the candidate must stay strictly inside the standards root.
                resolved_candidate = candidate.resolve()
                if resolved_candidate.parent == resolved_package and resolved_candidate.is_relative_to(
                    resolved_standards
                ):
                    sources_directories.append(candidate)
                    files_inside += sum(
                        1
                        for item in candidate.rglob("*")
                        # Symlinks are never followed and never counted: the
                        # reported count must describe the files this cleanup
                        # removes.
                        if not item.is_symlink() and item.is_file()
                    )
            for sibling in sorted(package_directory.iterdir()):
                if sibling.is_symlink():
                    continue
                if (
                    sibling.is_file()
                    and sibling.suffix.lower() == ".pdf"
                    and sibling.resolve().is_relative_to(resolved_package)
                ):
                    flat_pdfs.append(sibling)
        return sources_directories, flat_pdfs, files_inside

    @staticmethod
    def _delete_legacy_targets(
        directories: list[Path], flat_files: list[Path]
    ) -> list[tuple[Path, str]]:
        """Attempt every removal; return ``(path, reason)`` for what would not go.

        Deletion is best-effort per target and **never** silently ignored: each
        failure is captured with the underlying OS error so the caller can
        report a precise reason after its own verification.  ``rmtree`` is
        called without ``ignore_errors``/``onerror``, so the first failure —
        a locked PDF, a denied permission — raises ``PermissionError``/
        ``OSError`` instead of leaving a directory that quietly survives.
        """
        failures: list[tuple[Path, str]] = []
        for directory in directories:
            if not directory.exists():
                continue
            # Last-line guard: never remove through a link that resolves out of
            # its own package directory (the scanner already skips those).
            if not directory.is_symlink() and not directory.resolve().parent == directory.parent.resolve():
                failures.append((directory, "拒绝删除解析到包目录之外的目标"))
                continue
            try:
                shutil.rmtree(directory)
            except OSError as exc:
                failures.append((directory, f"{type(exc).__name__}: {exc}"))
        for path in flat_files:
            if not path.exists():
                continue
            try:
                os.remove(path)
            except OSError as exc:
                failures.append((path, f"{type(exc).__name__}: {exc}"))
        return failures

    def _remove_legacy_source_directories(
        self, *, attempts: int | None = None, retry_delay: float | None = None
    ) -> tuple[int, int, int]:
        """Remove legacy standard原文 from the user data directory — **fail-closed**.

        The owner requirement is that the software must not keep full standard
        PDFs in the user data directory.  ``install`` no longer copies
        ``sources/*`` anywhere, but a data directory written by an earlier
        version still holds them, in either historical layout (see
        ``_scan_legacy_targets``).  Those are removed so the *live* directory —
        and the pre-upgrade safety backup taken immediately afterwards — no
        longer carry the standard原文.

        The contract, in order, is:

        1. detect every legacy target;
        2. attempt deletion, retrying the whole set a few times to ride out
           transient Windows locks;
        3. re-scan with the **same** detector and require that every target is
           really gone;
        4. only then record the success audit and return the **real** counts.

        If anything is still present after the last attempt, a Chinese
        ``StandardPackageError`` is raised.  Nothing has been written at this
        point, so the caller aborts before the safety backup and before any
        install work: no success audit, no new ``pre-package-*.uebackup`` that
        would still carry the old PDFs, and no half-upgraded package directory
        or database.  A no-op (no legacy target at all) records no audit and
        returns zeros, so the cleanup stays idempotent.
        """
        resolved_standards = Path(self.paths.standards).resolve()
        directories, flat_files, files_inside = self._scan_legacy_targets()
        if not directories and not flat_files:
            return 0, 0, 0
        remaining = len(directories) + len(flat_files)
        failures: list[tuple[Path, str]] = []
        total_attempts = max(1, self.LEGACY_CLEANUP_ATTEMPTS if attempts is None else attempts)
        delay = self.LEGACY_CLEANUP_RETRY_DELAY if retry_delay is None else retry_delay
        for attempt in range(total_attempts):
            failures = self._delete_legacy_targets(directories, flat_files)            # Verify with the detector, not with an "if it did not raise" belief:
            # the re-scan is what decides whether this cleanup succeeded.
            remaining_targets = self._scan_legacy_targets()
            remaining = len(remaining_targets[0]) + len(remaining_targets[1])
            if remaining == 0:
                break
            if attempt + 1 < total_attempts:
                logger.warning(
                    "旧版本标准原文删除后仍存在 %d 项，稍后重试（%d/%d）：%s",
                    remaining,
                    attempt + 1,
                    total_attempts,
                    "、".join(str(item) for item in remaining_targets[0] + remaining_targets[1]),
                )
                time.sleep(delay)
        if remaining:
            surviving = self._scan_legacy_targets()
            blocked = surviving[0] + surviving[1]
            reasons = "；".join(f"{path}（{reason}）" for path, reason in failures) or "未知原因"
            raise StandardPackageError(
                "无法删除旧版本遗留在用户数据目录中的标准原文，安装已中止："
                f"尝试 {total_attempts} 次后仍有 {remaining} 项存在。"
                f"删除失败的目标：{reasons}。"
                "旧标准原文未清理干净时不得继续安装，否则本次安全备份会继续携带标准原文；"
                "现有数据库与业务数据保持可用、未做任何改动。"
                "请关闭可能占用这些 PDF 的程序（例如 PDF 阅读器、同步盘或杀毒软件）后重试。"
                f"标准数据目录：{resolved_standards}。"
                f"仍存在的目标：{'、'.join(str(path) for path in blocked)}"
            )

        # Reaching here means the re-scan proved the targets gone; the audit
        # counts below are the measured pre-cleanup targets, not an estimate.
        logger.warning(
            "移除旧版本写入用户数据目录的标准原文：%d 个目录、%d 个文件（另有 %d 个平铺 PDF），"
            "全部位于 %s 内；目录：%s；平铺文件：%s",
            len(directories),
            files_inside,
            len(flat_files),
            resolved_standards,
            "、".join(str(directory) for directory in directories) or "无",
            "、".join(str(path) for path in flat_files) or "无",
        )
        self.audit.append(
            AUDIT_LEGACY_SOURCES_REMOVED,
            "standard_package",
            None,
            {
                "directories_removed": len(directories),
                "files_removed": files_inside,
                "flat_files_removed": len(flat_files),
                "scope": str(resolved_standards),
                "verified": True,
            },
        )
        return len(directories), files_inside, len(flat_files)

    def cleanup_legacy_sources(self) -> tuple[int, int, int]:
        """Public face of the legacy原文 cleanup gate — the *same* implementation.

        ``install`` runs this privately as its first step (before it takes the
        pre-upgrade safety backup), which means a data directory that never needs
        an install — the NOOP case, and in particular a data directory that a
        ``BackupService.restore`` just filled with the old ``sources/*`` PDFs —
        would never be cleaned.  The application-layer reconciliation therefore
        calls this method on **every** startup, before its decision table, so
        both call sites pass through one gate.

        The delegate is deliberate: there is exactly one detector
        (``_scan_legacy_targets``), one deletion/verification loop, one audit row
        and one failure path, so the install path and the startup path can never
        drift apart.  The failure semantics are unchanged and stay fail-closed —
        a target that cannot be removed raises the Chinese ``StandardPackageError``
        from ``_remove_legacy_source_directories``, writes no success audit, and
        leaves the database and business data untouched.  A no-op records nothing
        and returns ``(0, 0, 0)``.
        """
        return self._remove_legacy_source_directories()

    def install(self, path: Path) -> PackageInstallResult:
        report = self.preview(path)
        if not report.valid or report.manifest is None or report.package_sha256 is None:
            raise StandardPackageError("；".join(report.errors) or "标准包验证失败")
        manifest = report.manifest
        # Order matters, and it is fail-closed:
        #   detect legacy原文 -> attempt deletion -> verify -> audit success
        #   -> *then* the safety backup -> *then* install the new package.
        # The cleanup runs before the backup so the backup itself already
        # satisfies "no full standard PDFs in the user data directory"; it runs
        # before *any* write, so a cleanup that cannot be verified aborts the
        # install with the database and business data untouched.
        removed_directories, removed_files, removed_flat_files = (
            self._remove_legacy_source_directories()
        )
        backup_path = _backup_path(self.paths.backups)
        self.backup.create(backup_path)
        destination = (self.paths.standards / manifest.package_id).resolve()
        if destination.parent != self.paths.standards.resolve():
            raise StandardPackageError("标准包目标目录不安全")
        if destination.exists():
            raise StandardPackageError("标准包目标目录已存在")
        try:
            with tempfile.TemporaryDirectory(prefix="uebench-package-", dir=self.paths.root) as temporary:
                temporary_path = Path(temporary)
                with zipfile.ZipFile(path, "r") as archive:
                    for item in manifest.files:
                        # Only non-original artefacts are materialised into the
                        # user data directory.  ``sources/*`` members stay inside
                        # the package archive: the product verifies them on
                        # preview/install but must never store full standard
                        # PDFs next to the user's data.
                        if item.kind == "correction":
                            target = temporary_path / PurePosixPath(item.path).name
                            target.write_bytes(archive.read(item.path))
                shutil.copytree(temporary_path, destination)
            with self.database.session() as session:
                for definition in report.definitions:
                    self.standards.install(definition, manifest.package_id, session=session)
                session.add(
                    PackageRow(
                        package_id=manifest.package_id,
                        schema_version=manifest.schema_version,
                        issued_at=manifest.issued_at,
                        manifest_json=manifest.model_dump_json(),
                        package_sha256=report.package_sha256,
                    )
                )
                self.audit.append(
                    "STANDARD_PACKAGE_INSTALL",
                    "standard_package",
                    manifest.package_id,
                    {"data_version": manifest.data_version, "package_mode": manifest.package_mode, "rule_engine_version": manifest.rule_engine_version, "parent_package_id": manifest.parent_package_id, "standard_count": manifest.standard_count, "source_policy": manifest.source_policy},
                    session=session,
                )
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise
        return PackageInstallResult(
            package_id=manifest.package_id,
            data_version=manifest.data_version,
            standards_installed=len(report.definitions),
            backup_path=str(backup_path),
            removed_source_directory_count=removed_directories,
            removed_source_file_count=removed_files,
            removed_flat_source_file_count=removed_flat_files,
        )
