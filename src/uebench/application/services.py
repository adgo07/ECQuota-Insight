from __future__ import annotations

from typing import Protocol

from uebench.domain.engine import EvaluationEngine
from uebench.domain.models import EvaluationRequest, EvaluationResult, StandardDefinition


class StandardRepository(Protocol):
    def get_published(self, standard_id: str) -> StandardDefinition | None: ...

    def list_published(self) -> list[StandardDefinition]: ...


class EvaluationRepository(Protocol):
    def save(
        self,
        request: EvaluationRequest,
        result: EvaluationResult,
        standard_snapshot: StandardDefinition,
    ) -> None: ...


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

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        standard = self.standards.get_published(request.standard_id)
        if standard is None:
            raise LookupError(f"未找到已发布标准：{request.standard_id}")
        result = self.engine.evaluate(standard, request)
        self.evaluations.save(request, result, standard)
        return result

