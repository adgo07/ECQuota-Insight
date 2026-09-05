from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from uebench.application.services import EvaluationService
from uebench.domain.models import EvaluationRequest, InputMode, InputValue, LifecycleStatus, StandardSelectionMode
from uebench.infrastructure.database import DatabaseManager
from uebench.infrastructure.paths import AppPaths
from uebench.infrastructure.repositories import AuditRepository, SqlEvaluationRepository, SqlStandardRepository

from .test_engine import make_standard


def test_obsolete_standard_is_excluded_from_current_but_available_for_history(tmp_path: Path) -> None:
    paths = AppPaths.from_root(tmp_path / "appdata")
    paths.ensure()
    database = DatabaseManager(paths.database)
    database.initialize()
    audit = AuditRepository(database)
    standards = SqlStandardRepository(database, audit)
    evaluations = SqlEvaluationRepository(database, audit)
    old = make_standard().model_copy(update={
        "id": "gb-old-test",
        "number": "GB 00001-2012",
        "version": "2012",
        "lifecycle_status": LifecycleStatus.OBSOLETE,
        "obsolete_date": date(2025, 6, 1),
        "replaced_by": ["GB 00001-2026"],
    })
    standards.install(old)
    assert standards.list_current(date(2026, 8, 30)) == []
    history = standards.list_historical()
    assert [item.number for item in history] == ["GB 00001-2012"]
    selected = standards.get_for_evaluation(old.id, date(2026, 8, 30), StandardSelectionMode.HISTORICAL)
    assert selected is not None and selected.number == "GB 00001-2012"
    request = EvaluationRequest(
        evaluation_date=date(2026, 8, 30),
        standard_id=old.id,
        product_id="product",
        selection_mode=StandardSelectionMode.HISTORICAL,
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="20", unit="kgce/t")},
    )
    result = EvaluationService(standards, evaluations).evaluate(request)
    assert result.results[0].grade.value == "LEVEL_2"
    database.dispose()


def test_same_product_name_can_have_multiple_indicator_rules() -> None:
    standard = make_standard()
    product = standard.products[0].model_copy(update={
        "indicators": [
            standard.products[0].indicators[0],
            standard.products[0].indicators[0].model_copy(update={"id": "electricity", "name": "电耗", "unit": "kWh/t"}),
        ]
    })
    updated = standard.model_copy(update={"products": [product]})
    assert len(updated.products[0].indicators) == 2
    assert updated.products[0].name == "测试产品"
    assert len({item.id for item in updated.products[0].indicators}) == 2
def test_future_selection_never_falls_back_to_current(tmp_path: Path) -> None:
    paths = AppPaths.from_root(tmp_path / "appdata")
    paths.ensure()
    database = DatabaseManager(paths.database)
    database.initialize()
    audit = AuditRepository(database)
    standards = SqlStandardRepository(database, audit)
    current = make_standard().model_copy(update={"id": "gb-current-test", "number": "GB 00002-2020", "version": "2020"})
    future = make_standard().model_copy(update={
        "id": "gb-future-test",
        "number": "GB 00002-2027",
        "version": "2027",
        "effective_date": date(2027, 1, 1),
    })
    standards.install(current)
    standards.install(future)

    assert standards.get_for_evaluation("gb-current-test", date(2026, 8, 31), StandardSelectionMode.FUTURE) is None
    selected = standards.get_for_evaluation("gb-future-test", date(2026, 8, 31), StandardSelectionMode.FUTURE)
    assert selected is not None and selected.number == "GB 00002-2027"
    database.dispose()
def test_future_evaluation_is_preview_only(tmp_path: Path) -> None:
    paths = AppPaths.from_root(tmp_path / "appdata")
    paths.ensure()
    database = DatabaseManager(paths.database)
    database.initialize()
    audit = AuditRepository(database)
    standards = SqlStandardRepository(database, audit)
    evaluations = SqlEvaluationRepository(database, audit)
    future = make_standard().model_copy(update={
        "id": "gb-future-preview",
        "number": "GB 00003-2027",
        "version": "2027",
        "effective_date": date(2027, 1, 1),
    })
    standards.install(future)
    request = EvaluationRequest(
        evaluation_date=date(2026, 8, 31),
        standard_id=future.id,
        product_id="product",
        selection_mode=StandardSelectionMode.FUTURE,
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="20", unit="kgce/t")},
    )
    service = EvaluationService(standards, evaluations)
    with pytest.raises(ValueError, match="只能预览"):
        service.evaluate(request)
    preview = service.preview(request)
    assert preview.results[0].grade.value == "LEVEL_2"
    assert evaluations.list_recent() == []
    database.dispose()
