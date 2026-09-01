from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from uebench.domain.engine import EvaluationEngine
from uebench.domain.models import EvaluationRequest, EvaluationResult, StandardDefinition, StandardSelectionMode


class StandardRepository(Protocol):
    def get_published(self, standard_id: str) -> StandardDefinition | None: ...

    def list_published(self) -> list[StandardDefinition]: ...

    def list_all(self) -> list[StandardDefinition]: ...

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

    def list_recent(self, limit: int = 100) -> list[Any]: ...

    def get(
        self, evaluation_id: str
    ) -> tuple[EvaluationRequest, EvaluationResult, StandardDefinition] | None: ...

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
    ) -> None:
        self.standards = standards
        self.evaluations = evaluations
        self.engine = engine or EvaluationEngine()

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

    def preview(self, request: EvaluationRequest) -> EvaluationResult:
        """Calculate a result without creating a formal evaluation record."""
        standard = self._resolve_standard(request)
        return self._calculate(request, standard)

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        if request.selection_mode is StandardSelectionMode.FUTURE:
            raise ValueError("尚未实施标准只能预览，不能形成正式判定或保存评价记录。")
        standard = self._resolve_standard(request)
        result = self._calculate(request, standard)
        self.evaluations.save(request, result, standard)
        return result