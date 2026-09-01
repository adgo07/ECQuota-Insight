from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

from uebench.domain.models import (
    EvaluationRequest,
    EvaluationResult,
    StandardDefinition,
    StandardSelectionMode,
)

from .ports import (
    AuditPort,
    BackupPort,
    StandardPackagePort,
    TemplatePort,
    WorkbookExportPort,
    WorkbookImportPort,
)
from .services import EvaluationRepository, EvaluationService, StandardCatalogService, StandardRepository


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
        self._backup = backup_service
        self._audit = audit
        self._source_root = source_root
        self._catalog = StandardCatalogService(standards)

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        return self._evaluation.evaluate(request)

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

    def list_recent_evaluations(self, limit: int = 100) -> list[Any]:
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

    def validate_workbook(self, path: Path) -> Any:
        if self._import is None:
            raise RuntimeError("Excel导入服务未配置")
        return self._import.validate(path)

    def commit_workbook(self, import_id: str) -> Any:
        if self._import is None:
            raise RuntimeError("Excel导入服务未配置")
        return self._import.commit(import_id)

    def export_evaluation(self, evaluation_id: str, path: Path) -> Path:
        if self._export is None:
            raise RuntimeError("Excel导出服务未配置")
        return self._export.export(evaluation_id, path)

    def has_package_service(self) -> bool:
        return self._package is not None

    def list_audit(self, limit: int = 200) -> list[Any]:
        if self._audit is None:
            return []
        return self._audit.list_recent(limit)

    def preview_package(self, path: Path) -> Any:
        if self._package is None:
            raise RuntimeError("标准包服务未配置")
        return self._package.preview(path)

    def install_package(self, path: Path) -> Any:
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

    def latest_package_manifest(self) -> dict[str, Any] | None:
        if self._package is None:
            return None
        loader: Callable[[], Any] | None = getattr(self._package, "latest_manifest", None)
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

    def find_standard_source(self, standard_id: str) -> Path | None:
        standard = self.get_published_standard(standard_id)
        if standard is None or self._source_root is None:
            return None
        return next(self._source_root.rglob(standard.source_file), None)

