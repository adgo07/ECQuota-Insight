import hashlib
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

def test_facade_uses_application_standard_selection_service():
    facade, standards, _evaluations, _evaluation = _facade()
    standards.list_future.return_value = ["future"]

    assert facade.list_standards_for_selection(date(2026, 8, 31), StandardSelectionMode.FUTURE) == ["future"]
    standards.list_future.assert_called_once_with(date(2026, 8, 31))


def test_facade_exposes_preview_evaluation():
    facade, _standards, _evaluations, evaluation = _facade()
    request = object()
    expected = object()
    evaluation.preview.return_value = expected

    assert facade.preview_evaluation(request) is expected
    evaluation.preview.assert_called_once_with(request)

def test_facade_discovers_standard_packages_without_installing():
    package = Mock()
    package.discover.return_value = [Path("/share/a.uebench")]
    facade, _standards, _evaluations, _evaluation = _facade(package=package)

    directory = Path("/share")
    assert facade.discover_package_paths(directory, recursive=True) == [Path("/share/a.uebench")]
    package.discover.assert_called_once_with(directory, recursive=True)


def test_facade_scans_standard_package_directory():
    package = Mock()
    package.discover.return_value = []
    facade, _standards, _evaluations, _evaluation = _facade(package=package)

    assert facade.scan_package_directory(Path("/share"), recursive=True) == []
    package.discover.assert_called_once_with(Path("/share"), recursive=True)
def test_facade_lists_package_history_through_application_port():
    package = Mock()
    package.list_history.return_value = [{"package_id": "pkg-1"}]
    facade, _standards, _evaluations, _evaluation = _facade(package=package)

    assert facade.list_package_history(12) == [{"package_id": "pkg-1"}]
    package.list_history.assert_called_once_with(12)

def test_facade_finds_selected_source_by_hash_and_selection_mode(tmp_path: Path):
    source_root = tmp_path / "standards"
    stale = source_root / "old-package" / "same.pdf"
    current = source_root / "new-package" / "same.pdf"
    stale.parent.mkdir(parents=True)
    current.parent.mkdir(parents=True)
    stale.write_bytes(b"old source")
    current.write_bytes(b"selected source")

    standard = Mock()
    standard.source_file = "same.pdf"
    standard.source_sha256 = hashlib.sha256(b"selected source").hexdigest()
    standards = Mock()
    standards.get_for_evaluation.return_value = standard
    facade = ApplicationFacade(
        standards=standards,
        evaluations=Mock(),
        evaluation_service=Mock(),
        source_root=source_root,
    )

    evaluation_date = date(2026, 9, 5)
    assert facade.find_standard_source(
        "std-1",
        evaluation_date=evaluation_date,
        selection_mode=StandardSelectionMode.FUTURE,
    ) == current
    standards.get_for_evaluation.assert_called_once_with(
        "std-1", evaluation_date, StandardSelectionMode.FUTURE
    )
