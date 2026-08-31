from datetime import date
from pathlib import Path
from unittest.mock import Mock

from uebench.application.facade import ApplicationFacade
from uebench.domain.models import StandardSelectionMode


def _facade(*, package=None):
    standards = Mock()
    evaluations = Mock()
    evaluation = Mock()
    facade = ApplicationFacade(
        standards=standards,
        evaluations=evaluations,
        evaluation_service=evaluation,
        package_service=package,
    )
    return facade, standards, evaluations, evaluation


def test_facade_delegates_evaluation_and_standard_selection():
    facade, standards, _evaluations, evaluation = _facade()
    request = object()
    expected = object()
    evaluation.evaluate.return_value = expected
    standards.get_for_evaluation.return_value = "standard"

    assert facade.evaluate(request) is expected
    assert facade.get_standard_for_evaluation(
        "std-1", date(2026, 8, 31), StandardSelectionMode.HISTORICAL
    ) == "standard"
    evaluation.evaluate.assert_called_once_with(request)
    standards.get_for_evaluation.assert_called_once_with(
        "std-1", date(2026, 8, 31), StandardSelectionMode.HISTORICAL
    )


def test_facade_exposes_read_and_write_use_cases_without_infrastructure_objects():
    package = Mock()
    package.latest_manifest.return_value = {"data_version": "2026.08"}
    facade, standards, evaluations, _evaluation = _facade(package=package)
    standards.list_current.return_value = ["current"]
    evaluations.list_recent.return_value = ["record"]
    evaluations.soft_delete.return_value = True

    assert facade.list_current_standards(date(2026, 8, 31)) == ["current"]
    assert facade.list_recent_evaluations(3) == ["record"]
    assert facade.delete_evaluation("eval-1") is True
    assert facade.latest_package_manifest() == {"data_version": "2026.08"}
    assert facade.has_package_service() is True
    standards.list_current.assert_called_once_with(date(2026, 8, 31))
    evaluations.list_recent.assert_called_once_with(3)
    evaluations.soft_delete.assert_called_once_with("eval-1")


def test_facade_reports_optional_services_cleanly():
    facade, _standards, _evaluations, _evaluation = _facade()
    assert facade.has_package_service() is False
    assert facade.latest_package_manifest() is None
    try:
        facade.create_template(Path("template.xlsx"))
    except RuntimeError as exc:
        assert "Excel模板服务未配置" in str(exc)
    else:
        raise AssertionError("未配置模板服务时应明确报错")
