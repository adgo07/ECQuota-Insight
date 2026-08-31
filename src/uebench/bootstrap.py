from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from uebench.application.facade import ApplicationFacade
from uebench.application.services import EvaluationService
from uebench.infrastructure.backup import BackupService
from uebench.infrastructure.database import DatabaseManager
from uebench.infrastructure.logging import configure_logging
from uebench.infrastructure.excel import WorkbookExportService, WorkbookImportService, WorkbookTemplateService
from uebench.infrastructure.packages import StandardPackageService
from uebench.infrastructure.paths import AppPaths
from uebench.infrastructure.repositories import AuditRepository, SqlEvaluationRepository, SqlStandardRepository


@dataclass
class AppContext:
    paths: AppPaths
    database: DatabaseManager
    audit: AuditRepository
    standards: SqlStandardRepository
    evaluations: SqlEvaluationRepository
    evaluation_service: EvaluationService
    application: ApplicationFacade
    template_service: WorkbookTemplateService
    import_service: WorkbookImportService
    export_service: WorkbookExportService
    backup_service: BackupService
    package_service: StandardPackageService | None


def create_context(root: Path | None = None, public_key_path: Path | None = None) -> AppContext:
    paths = AppPaths.from_root(root) if root is not None else AppPaths.default()
    paths.ensure()
    configure_logging(paths.logs)
    database = DatabaseManager(paths.database)
    database.initialize()
    audit = AuditRepository(database)
    standards = SqlStandardRepository(database, audit)
    evaluations = SqlEvaluationRepository(database, audit)
    evaluation_service = EvaluationService(standards, evaluations)
    template_service = WorkbookTemplateService()
    import_service = WorkbookImportService(database, audit, standards)
    export_service = WorkbookExportService(evaluations, audit)
    backup_service = BackupService(paths, database, audit)
    package_service = None
    if public_key_path is not None and public_key_path.exists():
        public_key = StandardPackageService.load_public_key(public_key_path)
        package_service = StandardPackageService(
            paths,
            database,
            public_key,
            backup_service,
            standards,
            audit,
        )
    application = ApplicationFacade(
        standards=standards,
        evaluations=evaluations,
        evaluation_service=evaluation_service,
        template_service=template_service,
        import_service=import_service,
        export_service=export_service,
        package_service=package_service,
        backup_service=backup_service,
        audit=audit,
        source_root=paths.standards,
    )
    return AppContext(
        paths=paths,
        database=database,
        audit=audit,
        standards=standards,
        evaluations=evaluations,
        evaluation_service=evaluation_service,
        application=application,
        template_service=template_service,
        import_service=import_service,
        export_service=export_service,
        backup_service=backup_service,
        package_service=package_service,
    )
