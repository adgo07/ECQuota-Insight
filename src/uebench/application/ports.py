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
    """Create an import template.

    ``standard_definition`` selects the adapter profile: ``None`` produces the
    generic multi-standard template, while a resolved standard produces that
    standard's dedicated template.  The application layer resolves the
    definition and passes it in, so the template service never queries a
    repository itself.
    """

    def create_template(self, path: Path, standard_definition: StandardDefinition | None = None) -> Path: ...


class ImportIssuePort(Protocol):
    severity: str
    sheet: str
    cell: str
    message: str


class ImportReportPort(Protocol):
    import_id: str
    valid: bool
    profile_id: str
    issues: list[ImportIssuePort]
    request: EvaluationRequest | None


class EvaluationDraftPort(Protocol):
    import_id: str
    request: EvaluationRequest


class WorkbookImportPort(Protocol):
    def validate(self, path: Path) -> ImportReportPort: ...

    def prepare(self, import_id: str) -> EvaluationDraftPort:
        """Return the canonical request for a validated batch.

        Implementations must re-verify source integrity (path still readable and
        content hash unchanged) and must leave the batch retryable on failure.
        """
        ...

    def mark_evaluated(self, import_id: str, evaluation_id: str) -> None: ...

    def commit(self, import_id: str) -> EvaluationDraftPort: ...


class WorkbookExportPort(Protocol):
    def export(self, evaluation_id: str, path: Path) -> Path: ...


class StandardSourcePort(Protocol):
    """Locate a standard source file without exposing storage details to the UI."""

    def find(self, source_file: str, source_sha256: str) -> Path | None: ...


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

    def cleanup_legacy_sources(self) -> tuple[int, int, int]:
        """Remove legacy standard原文 an older version left in the *live* directory.

        Returns the counts the post-deletion re-scan **proved** removed, as
        ``(sources_directories_removed, files_removed_inside_them, flat_pdf_files_removed)``.
        A target the re-scan still finds is not counted as removed.

        This is the same gate ``install`` runs immediately before it takes its
        pre-upgrade safety backup: detect every legacy target under
        ``paths.standards`` (both the early flat layout
        ``standards/<package_id>/*.pdf`` and the later
        ``standards/<package_id>/sources/**`` layout), attempt deletion, re-scan
        with the *same* detector, and only then record the success audit with the
        measured counts.  Nothing at all is recorded for a data directory that
        holds no legacy target: the call is idempotent and returns ``(0, 0, 0)``.

        Implementations must be **warn-only, never fail-closed**: when a target
        cannot be removed (Windows file lock, permission, residue) they log a
        WARNING, return the verified-removed counts, must not record a success
        audit, must not raise, and must leave the database and the business state
        untouched.  A locked legacy PDF must never block software startup,
        package install, formal evaluation or saving — the next startup retries.

        The application layer calls this on **every** startup reconciliation —
        before the decision table, so it also runs for a NOOP decision.  That is
        what closes the gap where a backup restored the old ``sources/*`` PDFs
        back into the live directory and the already-installed bundled package
        made reconciliation decide NOOP, so ``install`` (and with it the only
        cleanup call site) never ran.  It exists as a port method so the
        application layer never has to import the infrastructure adapter; the
        only implementation is :class:`uebench.infrastructure.packages.StandardPackageService`,
        which delegates to the very same code ``install`` uses, so there is
        exactly one cleanup implementation and one set of failure semantics.
        """
        ...

    def latest_manifest(self) -> PackageManifestPort | None: ...

    def list_history(self, limit: int = 50) -> list[PackageHistoryEntry]: ...


class BackupPort(Protocol):
    def create(self, path: Path) -> Path:
        """Write a **safety** backup of the user's business data.

        A safety backup (pre-migration, pre-install, pre-restore) is
        responsible for the non-rebuildable user data only: the database with
        the formal evaluation records, their rule snapshots, the installed
        standard definitions, import batches and the audit trail.  Standard
        packages, standard原文 PDFs, bundled resources, caches and logs are
        rebuildable application data and are deliberately **not** part of it.
        """
        ...

    def create_full_environment(self, path: Path) -> Path:
        """Write the explicit, user-initiated **full environment** backup.

        Same archive format and the same ``restore``; on top of the database it
        also archives the rebuildable application data (``standards/``,
        ``imports/``, ``logs/``) so a user can carry one self-contained archive
        to another machine.  Kept as a separate method so the two semantics
        never have to mean the same thing again.
        """
        ...

    def restore(self, path: Path) -> None: ...


class AuditPort(Protocol):
    def list_recent(self, limit: int = 200) -> list[AuditEntry]: ...