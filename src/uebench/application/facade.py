from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Callable

from uebench.domain.models import (
    AuditEntry,
    EvaluationRequest,
    EvaluationResult,
    EvaluationSummary,
    PackageHistoryEntry,
    StandardDefinition,
    StandardSelectionMode,
)

from .ports import (
    AuditPort,
    BackupPort,
    EvaluationDraftPort,
    ImportReportPort,
    PackageInstallResultPort,
    PackageValidationReportPort,
    StandardPackagePort,
    TemplatePort,
    WorkbookExportPort,
    WorkbookImportPort,
)
from .services import EvaluationRepository, EvaluationService, StandardCatalogService, StandardRepository
from .package_updates import PackageDirectoryService, PackageScanItem


class ApplicationFacade:
    """UI-neutral application use cases shared by desktop and future adapters."""

    def __init__(
        self,
        *,
        standards: StandardRepository,
        evaluations: EvaluationRepository,
        evaluation_service: EvaluationService,
        template_service: TemplatePort | None = None,
        import_service: WorkbookImportPort | None = None,
        export_service: WorkbookExportPort | None = None,
        package_service: StandardPackagePort | None = None,
        backup_service: BackupPort | None = None,
        audit: AuditPort | None = None,
        source_root: Path | None = None,
    ) -> None:
        self._standards = standards
        self._evaluations = evaluations
        self._evaluation = evaluation_service
        self._template = template_service
        self._import = import_service
        self._export = export_service
        self._package = package_service
        self._package_updates = PackageDirectoryService(package_service) if package_service is not None else None
        self._backup = backup_service
        self._audit = audit
        self._source_root = source_root
        self._catalog = StandardCatalogService(standards)

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        return self._evaluation.evaluate(request)

    def preview_evaluation(self, request: EvaluationRequest) -> EvaluationResult:
        return self._evaluation.preview(request)

    def list_current_standards(self, evaluation_date: date) -> list[StandardDefinition]:
        return self._standards.list_current(evaluation_date)

    def list_all_standards(self) -> list[StandardDefinition]:
        return self._standards.list_all()

    def list_historical_standards(self) -> list[StandardDefinition]:
        return self._standards.list_historical()

    def list_future_standards(self, evaluation_date: date) -> list[StandardDefinition]:
        return self._standards.list_future(evaluation_date)

    def get_standard_for_evaluation(
        self,
        standard_id: str,
        evaluation_date: date,
        selection_mode: StandardSelectionMode = StandardSelectionMode.CURRENT,
    ) -> StandardDefinition | None:
        return self._catalog.resolve(standard_id, evaluation_date, selection_mode)

    def list_standards_for_selection(
        self,
        evaluation_date: date,
        selection_mode: StandardSelectionMode = StandardSelectionMode.CURRENT,
    ) -> list[StandardDefinition]:
        return self._catalog.list_for_selection(evaluation_date, selection_mode)

    def get_published_standard(self, standard_id: str) -> StandardDefinition | None:
        return self._standards.get_published(standard_id)

    def list_recent_evaluations(self, limit: int = 100) -> list[EvaluationSummary]:
        return self._evaluations.list_recent(limit)

    def get_evaluation(
        self,
        evaluation_id: str,
    ) -> tuple[EvaluationRequest, EvaluationResult, StandardDefinition] | None:
        return self._evaluations.get(evaluation_id)

    def delete_evaluation(self, evaluation_id: str) -> bool:
        return self._evaluations.soft_delete(evaluation_id)

    def create_template(self, path: Path) -> Path:
        if self._template is None:
            raise RuntimeError("Excel模板服务未配置")
        return self._template.create_template(path)

    def validate_workbook(self, path: Path) -> ImportReportPort:
        if self._import is None:
            raise RuntimeError("Excel导入服务未配置")
        return self._import.validate(path)

    def commit_workbook(self, import_id: str) -> EvaluationDraftPort:
        if self._import is None:
            raise RuntimeError("Excel导入服务未配置")
        return self._import.commit(import_id)

    def export_evaluation(self, evaluation_id: str, path: Path) -> Path:
        if self._export is None:
            raise RuntimeError("Excel导出服务未配置")
        return self._export.export(evaluation_id, path)

    def has_package_service(self) -> bool:
        return self._package is not None

    def list_audit(self, limit: int = 200) -> list[AuditEntry]:
        if self._audit is None:
            return []
        return self._audit.list_recent(limit)

    def scan_package_directory(self, directory: Path, *, recursive: bool = False) -> list[PackageScanItem]:
        if self._package_updates is None:
            raise RuntimeError('标准包服务未配置')
        return self._package_updates.scan(directory, recursive=recursive)

    def discover_package_paths(self, directory: Path, *, recursive: bool = False) -> list[Path]:
        if self._package is None:
            raise RuntimeError("标准包服务未配置")
        discover = getattr(self._package, "discover", None)
        if discover is None:
            return []
        return list(discover(directory, recursive=recursive))

    def preview_package(self, path: Path) -> PackageValidationReportPort:
        if self._package is None:
            raise RuntimeError("标准包服务未配置")
        return self._package.preview(path)

    def install_package(self, path: Path) -> PackageInstallResultPort:
        if self._package is None:
            raise RuntimeError("标准包服务未配置")
        return self._package.install(path)

    def create_backup(self, path: Path) -> Path:
        if self._backup is None:
            raise RuntimeError("备份服务未配置")
        return self._backup.create(path)

    def restore_backup(self, path: Path) -> None:
        if self._backup is None:
            raise RuntimeError("备份服务未配置")
        self._backup.restore(path)

    def latest_package_manifest(self) -> dict[str, object] | None:
        if self._package is None:
            return None
        loader: Callable[[], object] | None = getattr(self._package, "latest_manifest", None)
        if loader is None:
            return None
        manifest = loader()
        if manifest is None:
            return None
        if hasattr(manifest, "model_dump"):
            return manifest.model_dump(mode="json")
        if isinstance(manifest, dict):
            return manifest
        return json.loads(manifest)

    def list_package_history(self, limit: int = 50) -> list[PackageHistoryEntry]:
        """Return installed package history without exposing database rows to the UI."""
        if self._package is None:
            return []
        loader = getattr(self._package, "list_history", None)
        if loader is None:
            return []
        return list(loader(limit))
    def find_standard_source(
        self,
        standard_id: str,
        *,
        evaluation_date: date | None = None,
        selection_mode: StandardSelectionMode = StandardSelectionMode.CURRENT,
    ) -> Path | None:
        """Find the selected standard's source PDF and verify its SHA-256.

        A package upgrade can leave several copies with the same filename in
        different package directories. Matching the hash prevents opening an
        older PDF merely because it happens to be found first.
        """
        standard = (
            self.get_published_standard(standard_id)
            if evaluation_date is None
            else self.get_standard_for_evaluation(standard_id, evaluation_date, selection_mode)
        )
        if standard is None or self._source_root is None:
            return None
        expected_hash = standard.source_sha256.lower()
        candidates = sorted(
            self._source_root.rglob(standard.source_file),
            key=lambda item: str(item).casefold(),
        )
        for candidate in candidates:
            if not candidate.is_file():
                continue
            digest = hashlib.sha256()
            try:
                with candidate.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
            except OSError:
                continue
            if digest.hexdigest() == expected_hash:
                return candidate
        return None
