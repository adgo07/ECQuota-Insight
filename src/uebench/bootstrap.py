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
from uebench.infrastructure.sources import StandardSourceService
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
    source_service = StandardSourceService(paths.standards)
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
        source_service=source_service,
        # The normal executable (root=None) exposes bundled, read-only
        # catalogue entries such as pending GB 29435-2025.  Tests and callers
        # that supply an explicit isolated root remain deterministic and only
        # see the standards they install into that root.
        catalogue_dir=(
            Path(__file__).resolve().parent / "resources" / "catalogue"
            if root is None
            else None
        ),
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
