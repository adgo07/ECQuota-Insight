from __future__ import annotations

import hashlib
import json
import os
import re
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
from uebench.domain.models import PackageHistoryEntry, PublicationStatus, StandardDefinition

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
        source_files: dict[str, Path],
        *,
        parent_package: Path,
        data_version: str,
        minimum_app_version: str = "0.1.0",
        rule_engine_version: str = RULE_ENGINE_VERSION,
        corrections: list[dict] | None = None,
        package_id: str | None = None,
        issued_at: datetime | None = None,
    ) -> Path:
        """Build a signed package containing only definitions changed from parent.

        Incremental packages cannot remove a definition; publishing a removed
        or replaced complete catalogue must use the full build method.
        The parent package id is copied from the inspected manifest so callers
        cannot accidentally attach the diff to another lineage.
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
        )
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
            definition_payload = definition.model_dump(mode="json")
            for product_payload in definition_payload.get("products", []):
                for indicator_payload in product_payload.get("indicators", []):
                    for optional_legacy_key in ("direct_input_key", "compliance_rule"):
                        if indicator_payload.get(optional_legacy_key) is None:
                            indicator_payload.pop(optional_legacy_key, None)
            data = _canonical_json(definition_payload)
            entries[path] = data
            rule_count += sum(len(product.indicators) for product in definition.products)
            source = source_files.get(definition.source_file)
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
