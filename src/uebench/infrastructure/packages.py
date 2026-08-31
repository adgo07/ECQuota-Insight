from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
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
from uebench.domain.models import PublicationStatus, StandardDefinition

from .backup import BackupService
from .database import DatabaseManager, PackageRow, StandardRow
from .paths import AppPaths
from .repositories import AuditRepository, SqlStandardRepository


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
        if self.kind == "definition" and not (
            self.path.startswith("definitions/") and self.path.endswith(".json")
        ):
            raise ValueError("definition 文件必须位于 definitions/ 且为 JSON")
        if self.kind == "source" and not self.path.startswith("sources/"):
            raise ValueError("source 文件必须位于 sources/")
        if self.kind == "correction" and self.path != "corrections.json":
            raise ValueError("correction 文件必须为 corrections.json")
        return self


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
def _definition_matches(payload: str, incoming: StandardDefinition) -> bool:
    """Return true only when an installed rule has identical canonical JSON."""
    try:
        installed = StandardDefinition.model_validate_json(payload)
    except ValueError:
        return False
    return _sha256_bytes(_canonical_json(installed.model_dump(mode="json"))) == _sha256_bytes(
        _canonical_json(incoming.model_dump(mode="json"))
    )




class StandardPackageBuilder:
    """Developer-side package builder; the private key is never shipped with the app."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self.private_key = private_key

    def build(
        self,
        output: Path,
        definitions: list[StandardDefinition],
        source_files: dict[str, Path],
        *,
        data_version: str,
        minimum_app_version: str = "0.1.0",
        package_mode: Literal["full", "incremental"] = "full",
        rule_engine_version: str = RULE_ENGINE_VERSION,
        parent_package_id: str | None = None,
        corrections: list[dict] | None = None,
        package_id: str | None = None,
        issued_at: datetime | None = None,
    ) -> Path:
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        package_id = package_id or str(uuid4())
        issued_at = issued_at or datetime.now(timezone.utc)
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
            source = source_files.get(definition.source_file)
            if source is None:
                raise StandardPackageError(f"缺少标准原文：{definition.source_file}")
            source_data = source.read_bytes()
            if _sha256_bytes(source_data) != definition.source_sha256.lower():
                raise StandardPackageError(f"标准原文哈希与定义不一致：{definition.source_file}")
            entries[f"sources/{definition.source_file}"] = source_data
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

    def preview(self, path: Path) -> PackageValidationReport:
        path = path.resolve()
        errors: list[str] = []
        warnings: list[str] = []
        definitions: list[StandardDefinition] = []
        manifest: PackageManifest | None = None
        package_sha256 = _sha256_path(path) if path.exists() else None
        if path.suffix.lower() != ".uebench":
            errors.append("标准包扩展名必须为 .uebench")
        if not path.exists():
            errors.append("标准包文件不存在")
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
                for item in manifest.files:
                    data = archive.read(item.path)
                    if len(data) != item.size or _sha256_bytes(data) != item.sha256:
                        errors.append(f"文件大小或哈希不匹配：{item.path}")
                    if item.kind == "definition":
                        definition = StandardDefinition.model_validate_json(data)
                        definitions.append(definition)
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
                if latest is not None and _as_utc(manifest.issued_at) < _as_utc(latest.issued_at):
                    errors.append("标准包发布时间早于当前已安装版本，禁止降级")
        return PackageValidationReport(
            valid=not errors,
            manifest=manifest,
            definitions=definitions,
            errors=errors,
            warnings=warnings,
            package_sha256=package_sha256,
        )

    def install(self, path: Path) -> PackageInstallResult:
        report = self.preview(path)
        if not report.valid or report.manifest is None or report.package_sha256 is None:
            raise StandardPackageError("；".join(report.errors) or "标准包验证失败")
        manifest = report.manifest
        backup_path = self.paths.backups / f"pre-package-{datetime.now():%Y%m%d-%H%M%S}.uebackup"
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
                        if item.kind in {"source", "correction"}:
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
                    {"data_version": manifest.data_version, "package_mode": manifest.package_mode, "rule_engine_version": manifest.rule_engine_version, "parent_package_id": manifest.parent_package_id, "standard_count": manifest.standard_count},
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
        )
