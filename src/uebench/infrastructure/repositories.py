from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlalchemy import desc, select

from uebench.domain.models import (
    AuditEntry,
    EvaluationRequest,
    EvaluationResult,
    EvaluationSummary,
    LifecycleStatus,
    StandardDefinition,
    StandardSelectionMode,
)

from .database import AuditRow, DatabaseManager, EvaluationRow, StandardRow


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class AuditRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def append(
        self,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        details: dict | None = None,
        *,
        session=None,
    ) -> None:
        row = AuditRow(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details_json=_canonical_json(details or {}),
        )
        if session is not None:
            session.add(row)
            return
        with self.database.session() as own_session:
            own_session.add(row)

    def list_recent(self, limit: int = 200) -> list[AuditEntry]:
        with self.database.session() as session:
            rows = session.scalars(select(AuditRow).order_by(desc(AuditRow.created_at)).limit(limit))
            return [
                AuditEntry(
                    id=row.id,
                    created_at=row.created_at,
                    actor=row.actor,
                    action=row.action,
                    entity_type=row.entity_type,
                    entity_id=row.entity_id,
                    details_json=row.details_json,
                )
                for row in rows
            ]


class SqlStandardRepository:
    def __init__(self, database: DatabaseManager, audit: AuditRepository | None = None) -> None:
        self.database = database
        self.audit = audit or AuditRepository(database)

    def get_for_evaluation(
        self,
        standard_id: str,
        evaluation_date: date,
        selection_mode: StandardSelectionMode = StandardSelectionMode.CURRENT,
    ) -> StandardDefinition | None:
        with self.database.session() as session:
            rows = session.scalars(
                select(StandardRow)
                .where(StandardRow.standard_id == standard_id, StandardRow.status == "published")
                .order_by(desc(StandardRow.effective_date), desc(StandardRow.installed_at))
            )
            definitions = [StandardDefinition.model_validate_json(row.definition_json) for row in rows]
            if selection_mode is StandardSelectionMode.CURRENT:
                return next((item for item in definitions if item.is_effective_on(evaluation_date)), None)
            if selection_mode is StandardSelectionMode.HISTORICAL:
                historical = [
                    item for item in definitions
                    if item.effective_date <= evaluation_date
                    and (item.lifecycle_status is LifecycleStatus.OBSOLETE or item.obsolete_date is not None)
                ]
                return max(historical, key=lambda item: item.effective_date, default=None)
            future = [
                item for item in definitions
                if item.effective_date > evaluation_date and item.lifecycle_status is not LifecycleStatus.OBSOLETE
            ]
            return min(future, key=lambda item: item.effective_date, default=None)

    def list_current(self, evaluation_date: date) -> list[StandardDefinition]:
        with self.database.session() as session:
            rows = session.scalars(
                select(StandardRow)
                .where(StandardRow.status == "published")
                .order_by(
                    StandardRow.standard_family_id,
                    desc(StandardRow.effective_date),
                    desc(StandardRow.installed_at),
                )
            )
            definitions = [StandardDefinition.model_validate_json(row.definition_json) for row in rows]
        result: list[StandardDefinition] = []
        seen_families: set[str] = set()
        for item in definitions:
            # A family can temporarily contain overlapping editions during an
            # update. The ordered query makes the first effective edition the
            # newest one; only one current edition is shown to the user.
            if not item.is_effective_on(evaluation_date) or item.family_id in seen_families:
                continue
            seen_families.add(item.family_id)
            result.append(item)
        return result

    def list_historical(self) -> list[StandardDefinition]:
        with self.database.session() as session:
            rows = session.scalars(select(StandardRow).where(StandardRow.status == "published").order_by(StandardRow.number, desc(StandardRow.effective_date)))
            definitions = [StandardDefinition.model_validate_json(row.definition_json) for row in rows]
        return [item for item in definitions if item.lifecycle_status is LifecycleStatus.OBSOLETE or item.obsolete_date is not None]

    def list_future(self, evaluation_date: date) -> list[StandardDefinition]:
        with self.database.session() as session:
            rows = session.scalars(select(StandardRow).where(StandardRow.status == "published").order_by(StandardRow.number, StandardRow.effective_date))
            definitions = [StandardDefinition.model_validate_json(row.definition_json) for row in rows]
        return [item for item in definitions if item.effective_date > evaluation_date and item.lifecycle_status is not LifecycleStatus.OBSOLETE]

    def get_published(self, standard_id: str) -> StandardDefinition | None:
        with self.database.session() as session:
            statement = (
                select(StandardRow)
                .where(StandardRow.standard_id == standard_id, StandardRow.status == "published")
                .order_by(desc(StandardRow.effective_date), desc(StandardRow.installed_at))
                .limit(1)
            )
            row = session.scalar(statement)
            return StandardDefinition.model_validate_json(row.definition_json) if row else None

    def list_published(self) -> list[StandardDefinition]:
        with self.database.session() as session:
            rows = session.scalars(
                select(StandardRow)
                .where(StandardRow.status == "published")
                .order_by(
                    StandardRow.standard_family_id,
                    desc(StandardRow.effective_date),
                    desc(StandardRow.installed_at),
                )
            )
            definitions: list[StandardDefinition] = []
            seen_families: set[str] = set()
            for row in rows:
                item = StandardDefinition.model_validate_json(row.definition_json)
                if item.family_id in seen_families:
                    continue
                seen_families.add(item.family_id)
                definitions.append(item)
            return definitions

    def list_all(self) -> list[StandardDefinition]:
        with self.database.session() as session:
            rows = session.scalars(select(StandardRow).order_by(StandardRow.number, StandardRow.effective_date))
            return [StandardDefinition.model_validate_json(row.definition_json) for row in rows]

    def install(self, definition: StandardDefinition, package_id: str | None = None, *, session=None) -> None:
        def upsert(target_session) -> None:
            statement = select(StandardRow).where(
                StandardRow.standard_id == definition.id,
                StandardRow.rule_revision == definition.rule_revision,
                StandardRow.version == definition.version,
            )
            row = target_session.scalar(statement)
            payload = definition.model_dump_json()
            if row is None:
                row = StandardRow(
                    standard_family_id=definition.family_id,
                    rule_revision=definition.rule_revision,
                    standard_id=definition.id,
                    number=definition.number,
                    title=definition.title,
                    version=definition.version,
                    status=definition.publication_status.value,
                    publication_date=definition.publication_date,
                    effective_date=definition.effective_date,
                    source_file=definition.source_file,
                    source_sha256=definition.source_sha256.lower(),
                    lifecycle_status=definition.lifecycle_status.value,
                    obsolete_date=definition.obsolete_date,
                    replaced_by_json=json.dumps(definition.replaced_by, ensure_ascii=False),
                    supersedes_json=json.dumps(definition.supersedes, ensure_ascii=False),
                    package_id=package_id,
                    definition_json=payload,
                )
                target_session.add(row)
            else:
                row.standard_family_id = definition.family_id
                row.rule_revision = definition.rule_revision
                row.number = definition.number
                row.title = definition.title
                row.status = definition.publication_status.value
                row.publication_date = definition.publication_date
                row.effective_date = definition.effective_date
                row.source_file = definition.source_file
                row.source_sha256 = definition.source_sha256.lower()
                row.lifecycle_status = definition.lifecycle_status.value
                row.obsolete_date = definition.obsolete_date
                row.replaced_by_json = json.dumps(definition.replaced_by, ensure_ascii=False)
                row.supersedes_json = json.dumps(definition.supersedes, ensure_ascii=False)
                row.package_id = package_id
                row.definition_json = payload
            self.audit.append(
                "STANDARD_INSTALL",
                "standard",
                f"{definition.id}:{definition.version}:r{definition.rule_revision}",
                {"number": definition.number, "package_id": package_id},
                session=target_session,
            )

        if session is not None:
            upsert(session)
        else:
            with self.database.session() as own_session:
                upsert(own_session)


class SqlEvaluationRepository:
    def __init__(self, database: DatabaseManager, audit: AuditRepository | None = None) -> None:
        self.database = database
        self.audit = audit or AuditRepository(database)

    def save(
        self,
        request: EvaluationRequest,
        result: EvaluationResult,
        standard_snapshot: StandardDefinition,
    ) -> None:
        with self.database.session() as session:
            session.add(
                EvaluationRow(
                    evaluation_id=result.evaluation_id,
                    created_at=result.evaluated_at,
                    evaluation_date=request.evaluation_date,
                    standard_id=result.standard_id,
                    standard_number=result.standard_number,
                    product_id=result.product_id,
                    organization_name=request.organization_name,
                    project_name=request.project_name,
                    request_json=request.model_dump_json(),
                    result_json=result.model_dump_json(),
                    rule_snapshot_json=standard_snapshot.model_dump_json(),
                )
            )
            self.audit.append(
                "EVALUATION_CREATE",
                "evaluation",
                result.evaluation_id,
                {"standard_number": result.standard_number, "product_id": result.product_id},
                session=session,
            )

    def get(self, evaluation_id: str) -> tuple[EvaluationRequest, EvaluationResult, StandardDefinition] | None:
        with self.database.session() as session:
            row = session.get(EvaluationRow, evaluation_id)
            if row is None or row.deleted_at is not None:
                return None
            return (
                EvaluationRequest.model_validate_json(row.request_json),
                EvaluationResult.model_validate_json(row.result_json),
                StandardDefinition.model_validate_json(row.rule_snapshot_json),
            )

    def list_recent(self, limit: int = 100) -> list[EvaluationSummary]:
        with self.database.session() as session:
            statement = (
                select(EvaluationRow)
                .where(EvaluationRow.deleted_at.is_(None))
                .order_by(desc(EvaluationRow.created_at))
                .limit(limit)
            )
            rows = session.scalars(statement)
            return [
                EvaluationSummary(
                    evaluation_id=row.evaluation_id,
                    created_at=row.created_at,
                    evaluation_date=row.evaluation_date,
                    standard_id=row.standard_id,
                    standard_number=row.standard_number,
                    product_id=row.product_id,
                    organization_name=row.organization_name,
                    project_name=row.project_name,
                )
                for row in rows
            ]

    def soft_delete(self, evaluation_id: str) -> bool:
        with self.database.session() as session:
            row = session.get(EvaluationRow, evaluation_id)
            if row is None or row.deleted_at is not None:
                return False
            row.deleted_at = datetime.now(timezone.utc)
            self.audit.append(
                "EVALUATION_DELETE",
                "evaluation",
                evaluation_id,
                session=session,
            )
            return True
