from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Protocol

from uebench.domain.engine import EvaluationEngine
from uebench.domain.numeric import ECQUOTA_DECIMAL_FULL_VALUE_V1
from uebench.domain.models import (
    EvaluationRequest,
    EvaluationResult,
    EvaluationSummary,
    StandardDefinition,
    StandardSelectionMode,
)

from .evaluation_support import evaluation_support_label, supports_formal_evaluation


class StandardRepository(Protocol):
    def get_published(self, standard_id: str) -> StandardDefinition | None: ...

    def list_published(self) -> list[StandardDefinition]: ...

    def list_all(self) -> list[StandardDefinition]: ...

    def list_by_id(self, standard_id: str) -> list[StandardDefinition]: ...

    def list_current(self, evaluation_date: date) -> list[StandardDefinition]: ...

    def list_historical(self) -> list[StandardDefinition]: ...

    def list_future(self, evaluation_date: date) -> list[StandardDefinition]: ...

    def get_for_evaluation(
        self,
        standard_id: str,
        evaluation_date: date,
        selection_mode: StandardSelectionMode = StandardSelectionMode.CURRENT,
    ) -> StandardDefinition | None: ...


class EvaluationRepository(Protocol):
    def save(
        self,
        request: EvaluationRequest,
        result: EvaluationResult,
        standard_snapshot: StandardDefinition,
    ) -> None: ...

    def list_recent(self, limit: int = 100) -> list[EvaluationSummary]: ...

    def get(
        self, evaluation_id: str
    ) -> tuple[EvaluationRequest, EvaluationResult, StandardDefinition] | None: ...

    def count(self) -> int: ...

    def soft_delete(self, evaluation_id: str) -> bool: ...


class StandardCatalogService:
    """Application-layer standard selection shared by every UI adapter."""

    def __init__(self, standards: StandardRepository) -> None:
        self.standards = standards

    def list_for_selection(
        self,
        evaluation_date: date,
        selection_mode: StandardSelectionMode = StandardSelectionMode.CURRENT,
    ) -> list[StandardDefinition]:
        if selection_mode is StandardSelectionMode.HISTORICAL:
            return self.standards.list_historical()
        if selection_mode is StandardSelectionMode.FUTURE:
            return self.standards.list_future(evaluation_date)
        return self.standards.list_current(evaluation_date)

    def resolve(
        self,
        standard_id: str,
        evaluation_date: date,
        selection_mode: StandardSelectionMode = StandardSelectionMode.CURRENT,
    ) -> StandardDefinition | None:
        return self.standards.get_for_evaluation(standard_id, evaluation_date, selection_mode)


class EvaluationService:
    def __init__(
        self,
        standards: StandardRepository,
        evaluations: EvaluationRepository,
        engine: EvaluationEngine | None = None,
        formal_evaluation_block: Callable[[], str | None] | None = None,
    ) -> None:
        self.standards = standards
        self.evaluations = evaluations
        self.engine = engine or EvaluationEngine(ECQUOTA_DECIMAL_FULL_VALUE_V1)
        self._formal_evaluation_block = formal_evaluation_block

    def _resolve_standard(self, request: EvaluationRequest) -> StandardDefinition:
        standard = self.standards.get_for_evaluation(
            request.standard_id,
            request.evaluation_date,
            request.selection_mode,
        )
        if standard is None:
            fallback = self.standards.get_published(request.standard_id)
            if fallback is None:
                raise LookupError(f"未找到已发布标准：{request.standard_id}")
            raise ValueError(fallback.selection_warning(request.evaluation_date) or "所选标准不适用于当前评价日期。")
        return standard

    def _calculate(self, request: EvaluationRequest, standard: StandardDefinition) -> EvaluationResult:
        result = self.engine.evaluate(
            standard,
            request,
            allow_pre_effective=request.selection_mode is StandardSelectionMode.FUTURE,
        )
        selection_warning = standard.selection_warning(request.evaluation_date)
        if selection_warning and selection_warning not in result.warnings:
            result.warnings.append(selection_warning)
            for indicator_result in result.results:
                if selection_warning not in indicator_result.warnings:
                    indicator_result.warnings.append(selection_warning)
        return result

    def formal_evaluation_block_message(self) -> str | None:
        """Return the user-facing readiness message, if formal evaluation is paused."""
        if self._formal_evaluation_block is None:
            return None
        return self._formal_evaluation_block()

    def preview(self, request: EvaluationRequest) -> EvaluationResult:
        """Calculate a result without creating a formal evaluation record.

        Deliberately **open to every installed standard**, including the ones the
        software does not formally support: preview writes nothing, so an
        out-of-scope standard can still be inspected without claiming a verified
        formal evaluation capability.  Only :meth:`evaluate` is gated by the
        formal-scope registry.
        """
        standard = self._resolve_standard(request)
        return self._calculate(request, standard)

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        """Formal evaluation: the only path that writes an evaluation record.

        It is gated by the application-layer formal-scope registry
        (:mod:`uebench.application.evaluation_support`) *before* the standard is
        resolved, calculated or saved, so no adapter -- UI, Excel or a future one
        -- can produce a formal record for a standard outside the scope.  The
        check reads ``request.standard_id`` directly rather than the resolved
        definition, so changing ``selection_mode`` cannot slip an out-of-scope
        standard past it.
        """
        readiness_message = self.formal_evaluation_block_message()
        if readiness_message:
            raise ValueError(readiness_message)
        if not supports_formal_evaluation(request.standard_id):
            raise ValueError(
                f"{evaluation_support_label(request.standard_id)}：该标准不能形成正式评价记录，仅可预览。"
            )
        if request.selection_mode is StandardSelectionMode.FUTURE:
            raise ValueError("尚未实施标准只能预览，不能形成正式判定或保存评价记录。")
        standard = self._resolve_standard(request)
        result = self._calculate(request, standard)
        self.evaluations.save(request, result, standard)
        return result