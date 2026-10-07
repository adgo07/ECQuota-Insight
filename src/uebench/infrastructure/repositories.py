from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone

from sqlalchemy import desc, func, select

from uebench.domain.models import (
    RECORD_CORRUPTED_LABEL,
    AuditEntry,
    EvaluationRequest,
    EvaluationResult,
    EvaluationSummary,
    LifecycleStatus,
    StandardDefinition,
    StandardSelectionMode,
    StorageCorruptionError,
)

from .database import AuditRow, DatabaseManager, EvaluationRow, StandardRow


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


#: Human labels for the three persisted payloads of one evaluation row.
_PAYLOAD_LABELS = {
    "request_json": "评价输入数据",
    "result_json": "评价结论数据",
    "rule_snapshot_json": "规则快照",
}


def _corruption_reason(field: str) -> str:
    """Describe one unreadable payload without leaking an ASCII pydantic message."""
    label = _PAYLOAD_LABELS.get(field, field)
    return f"{RECORD_CORRUPTED_LABEL}：{label}无法解析，该记录仅按数据库原始字段降级展示。"


def _log_corruption(evaluation_id: str, field: str, exc: Exception) -> None:
    """Report one unreadable stored payload.

    The raw pydantic message stays in the log for support; user-facing text is
    built by :func:`_corruption_reason` so the UI never blames input data.
    """
    logging.getLogger(__name__).warning(
        "评价记录 %s 的 %s 无法解析，已按降级记录处理：%s",
        evaluation_id,
        _PAYLOAD_LABELS.get(field, field),
        exc,
    )


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
        #: Parsed definitions reused inside one caller-scoped read burst; ``None``
        #: while no snapshot is active.  See :meth:`begin_definition_snapshot`.
        self._definition_snapshot: dict[str, StandardDefinition] | None = None
        self._definition_snapshot_depth = 0

    # -- short-lived definition reuse (ECQ-RS05 M3) -------------------------

    def begin_definition_snapshot(self) -> None:
        """Reuse already-parsed definitions until :meth:`end_definition_snapshot`.

        One UI refresh reads the same installed rows for several projections (the
        current count, the all/scoped count and the formal evaluation scope), and
        each read used to re-run ``model_validate_json`` on payloads that had been
        parsed microseconds earlier.  Re-reading the rows stays as it was; only
        the duplicate parse is removed.

        The scope is opened and closed around a single refresh, so nothing
        outlives it: a package install, a restore or a rule replacement between
        two refreshes is always read from the database again.  Scopes nest, and
        only the outermost one clears the snapshot.
        """
        if self._definition_snapshot is None:
            self._definition_snapshot = {}
        self._definition_snapshot_depth += 1

    def end_definition_snapshot(self) -> None:
        if self._definition_snapshot_depth == 0:
            return
        self._definition_snapshot_depth -= 1
        if self._definition_snapshot_depth == 0:
            self._definition_snapshot = None

    def _definition(self, payload: str) -> StandardDefinition:
        """Parse one stored definition, reusing the active snapshot when there is one."""
        snapshot = self._definition_snapshot
        if snapshot is None:
            return StandardDefinition.model_validate_json(payload)
        parsed = snapshot.get(payload)
        if parsed is None:
            parsed = StandardDefinition.model_validate_json(payload)
            snapshot[payload] = parsed
        # Every caller keeps getting its own instance, exactly as a fresh parse did.
        return parsed.model_copy()

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
                .order_by(desc(StandardRow.effective_date), desc(StandardRow.rule_revision), desc(StandardRow.installed_at))
            )
            definitions = [self._definition(row.definition_json) for row in rows]
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
                    desc(StandardRow.rule_revision),
                    desc(StandardRow.installed_at),
                )
            )
            definitions = [self._definition(row.definition_json) for row in rows]
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
            rows = session.scalars(select(StandardRow).where(StandardRow.status == "published").order_by(StandardRow.number, desc(StandardRow.effective_date), desc(StandardRow.rule_revision), desc(StandardRow.installed_at)))
            definitions = [self._definition(row.definition_json) for row in rows]
        return [item for item in definitions if item.lifecycle_status is LifecycleStatus.OBSOLETE or item.obsolete_date is not None]

    def list_future(self, evaluation_date: date) -> list[StandardDefinition]:
        with self.database.session() as session:
            rows = session.scalars(select(StandardRow).where(StandardRow.status == "published").order_by(StandardRow.number, StandardRow.effective_date, desc(StandardRow.rule_revision), desc(StandardRow.installed_at)))
            definitions = [self._definition(row.definition_json) for row in rows]
        return [item for item in definitions if item.effective_date > evaluation_date and item.lifecycle_status is not LifecycleStatus.OBSOLETE]

    def get_published(self, standard_id: str) -> StandardDefinition | None:
        with self.database.session() as session:
            statement = (
                select(StandardRow)
                .where(StandardRow.standard_id == standard_id, StandardRow.status == "published")
                .order_by(desc(StandardRow.effective_date), desc(StandardRow.rule_revision), desc(StandardRow.installed_at))
                .limit(1)
            )
            row = session.scalar(statement)
            return self._definition(row.definition_json) if row else None

    def list_by_id(self, standard_id: str) -> list[StandardDefinition]:
        """Read every installed revision of one standard id only.

        Minimal by-id read for catalogue lookups: reading the whole library (one
        parse per installed row) just to pick one standard out of it is duplicate
        work.  Ordering is deliberately left to the caller's own selection rule,
        which is where "newest revision wins" already lives.
        """
        with self.database.session() as session:
            rows = session.scalars(
                select(StandardRow).where(StandardRow.standard_id == standard_id)
            )
            return [self._definition(row.definition_json) for row in rows]

    def list_published(self) -> list[StandardDefinition]:
        with self.database.session() as session:
            rows = session.scalars(
                select(StandardRow)
                .where(StandardRow.status == "published")
                .order_by(
                    StandardRow.standard_family_id,
                    desc(StandardRow.effective_date),
                    desc(StandardRow.rule_revision),
                    desc(StandardRow.installed_at),
                )
            )
            definitions: list[StandardDefinition] = []
            seen_families: set[str] = set()
            for row in rows:
                item = self._definition(row.definition_json)
                if item.family_id in seen_families:
                    continue
                seen_families.add(item.family_id)
                definitions.append(item)
            return definitions

    def list_all(self) -> list[StandardDefinition]:
        with self.database.session() as session:
            rows = session.scalars(select(StandardRow).order_by(StandardRow.number, StandardRow.effective_date, desc(StandardRow.rule_revision), desc(StandardRow.installed_at)))
            return [self._definition(row.definition_json) for row in rows]

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
        """Load one stored evaluation.

        ``None`` keeps its original meaning only: the record does not exist or was
        soft-deleted.  A record that exists but whose stored payload can no longer
        be parsed raises :class:`StorageCorruptionError`, so callers can never
        mistake storage damage for a deletion and never silently degrade a
        business projection that other code compares against stored expectations.
        """
        with self.database.session() as session:
            row = session.get(EvaluationRow, evaluation_id)
            if row is None or row.deleted_at is not None:
                return None
            return (
                self._parse_payload(evaluation_id, "request_json", row.request_json, EvaluationRequest),
                self._parse_payload(evaluation_id, "result_json", row.result_json, EvaluationResult),
                self._parse_payload(evaluation_id, "rule_snapshot_json", row.rule_snapshot_json, StandardDefinition),
            )

    @staticmethod
    def _parse_payload(evaluation_id: str, field: str, payload: str, model):
        try:
            return model.model_validate_json(payload)
        except ValueError as exc:
            _log_corruption(evaluation_id, field, exc)
            raise StorageCorruptionError(
                f"{RECORD_CORRUPTED_LABEL}：评价记录（{evaluation_id}）的"
                f"{_PAYLOAD_LABELS.get(field, field)}无法解析，无法打开该记录。"
                "记录已保留，未被修改或删除；请联系技术支持并保留数据目录。"
            ) from exc

    def list_recent(self, limit: int = 100) -> list[EvaluationSummary]:
        """List recent records, degrading unreadable rows instead of failing.

        One malformed ``result_json`` must not discard the whole page.  The
        damaged row stays in the list with ``is_corrupted=True`` and falls back to
        the database columns that do not depend on the saved payload, so the
        record is explicitly degraded rather than silently skipped or shown as a
        normal record.
        """
        with self.database.session() as session:
            statement = (
                select(EvaluationRow)
                .where(EvaluationRow.deleted_at.is_(None))
                .order_by(desc(EvaluationRow.created_at))
                .limit(limit)
            )
            rows = session.scalars(statement)
            summaries = []
            for row in rows:
                try:
                    saved_result = EvaluationResult.model_validate_json(row.result_json)
                except ValueError as exc:
                    _log_corruption(row.evaluation_id, "result_json", exc)
                    summaries.append(EvaluationSummary(
                        evaluation_id=row.evaluation_id,
                        created_at=row.created_at,
                        evaluation_date=row.evaluation_date,
                        standard_id=row.standard_id,
                        standard_number=row.standard_number,
                        product_id=row.product_id,
                        organization_name=row.organization_name,
                        project_name=row.project_name,
                        is_corrupted=True,
                        corruption_reason=_corruption_reason("result_json"),
                    ))
                    continue
                summaries.append(EvaluationSummary(
                    evaluation_id=row.evaluation_id,
                    created_at=row.created_at,
                    evaluation_date=row.evaluation_date,
                    standard_id=row.standard_id,
                    standard_number=saved_result.standard_number,
                    standard_title=saved_result.standard_title,
                    product_id=row.product_id,
                    product_name=saved_result.product_name,
                    organization_name=row.organization_name,
                    project_name=row.project_name,
                ))
            return summaries

    def count(self) -> int:
        with self.database.session() as session:
            return session.scalar(
                select(func.count()).select_from(EvaluationRow).where(EvaluationRow.deleted_at.is_(None))
            ) or 0

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
