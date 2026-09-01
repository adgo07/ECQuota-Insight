"""Application ports for UI-neutral adapters.

The domain and application layers depend on these small protocols instead of
desktop-specific infrastructure classes. The current Windows composition root
uses the SQLite/Excel implementations; future Web, NAS, Android, iOS, or Linux
adapters can provide the same methods without changing use cases.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol

from uebench.domain.models import AuditEntry, EvaluationRequest, PackageHistoryEntry, StandardDefinition


class TemplatePort(Protocol):
    def create_template(self, path: Path) -> Path: ...


class ImportIssuePort(Protocol):
    severity: str
    sheet: str
    cell: str
    message: str


class ImportReportPort(Protocol):
    import_id: str
    valid: bool
    issues: list[ImportIssuePort]
    request: EvaluationRequest | None


class EvaluationDraftPort(Protocol):
    import_id: str
    request: EvaluationRequest


class WorkbookImportPort(Protocol):
    def validate(self, path: Path) -> ImportReportPort: ...

    def commit(self, import_id: str) -> EvaluationDraftPort: ...


class WorkbookExportPort(Protocol):
    def export(self, evaluation_id: str, path: Path) -> Path: ...


class PackageManifestPort(Protocol):
    package_id: str
    data_version: str
    issued_at: datetime
    package_mode: str
    parent_package_id: str | None
    standard_count: int
    rule_count: int


class PackageValidationReportPort(Protocol):
    valid: bool
    manifest: PackageManifestPort | None
    definitions: list[StandardDefinition]
    errors: list[str]
    warnings: list[str]
    package_sha256: str | None


class PackageInstallResultPort(Protocol):
    package_id: str
    data_version: str
    standards_installed: int
    backup_path: str


class PackageDiscoveryPort(Protocol):
    def discover(self, directory: Path, *, recursive: bool = False) -> list[Path]: ...

    def preview(self, path: Path) -> PackageValidationReportPort: ...


class StandardPackagePort(PackageDiscoveryPort, Protocol):
    def install(self, path: Path) -> PackageInstallResultPort: ...

    def latest_manifest(self) -> PackageManifestPort | None: ...

    def list_history(self, limit: int = 50) -> list[PackageHistoryEntry]: ...


class BackupPort(Protocol):
    def create(self, path: Path) -> Path: ...

    def restore(self, path: Path) -> None: ...


class AuditPort(Protocol):
    def list_recent(self, limit: int = 200) -> list[AuditEntry]: ...