from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from uebench.application import evaluation_support
from uebench.application.services import EvaluationService
from uebench.domain.models import EvaluationRequest, InputMode, InputValue, LifecycleStatus, StandardSelectionMode
from uebench.infrastructure.database import DatabaseManager
from uebench.infrastructure.paths import AppPaths
from uebench.infrastructure.repositories import AuditRepository, SqlEvaluationRepository, SqlStandardRepository

from .test_engine import make_standard


def _in_formal_scope(monkeypatch, *standard_ids: str) -> None:
    """把 ``standard_ids`` 声明为正式可评价（与 ``test_ui.py::_in_formal_scope`` 同模式）。

    正式评价范围是应用层的固定常量，**与“标准库里有没有这个标准”无关**（RS05 §三）。
    本文件覆盖的是标准的**生命周期与选择模式**（废止/历史、未来），不是范围本身，因此
    需要走正式评价落库的用例必须显式扩展真正的注册表；产品行为仍由注册表驱动。
    """
    extended = set(evaluation_support.SUPPORTED_EVALUATION_STANDARD_IDS) | set(standard_ids)
    monkeypatch.setattr(
        evaluation_support, "SUPPORTED_EVALUATION_STANDARD_IDS", frozenset(extended)
    )


def test_obsolete_standard_is_excluded_from_current_but_available_for_history(
    tmp_path: Path, monkeypatch
) -> None:
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
    # 本用例验证的是“废止标准仍可经历史模式正式评价”，不是范围，故显式扩展注册表。
    _in_formal_scope(monkeypatch, old.id)
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
def test_future_evaluation_is_preview_only(tmp_path: Path, monkeypatch) -> None:
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
    # 本用例验证的是 FUTURE 选择模式自身的“只能预览”门槛。若不把它放进正式评价范围，
    # 先触发的会是范围拒绝（另一条门槛），本用例就测不到自己要测的东西了（RS05 §三）。
    _in_formal_scope(monkeypatch, future.id)
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
