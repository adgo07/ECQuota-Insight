from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from uebench.bootstrap import create_context
from uebench.ui.main_window import MainWindow
from uebench.domain.models import (
    EvaluationRequest,
    InputMode,
    InputValue,
    PackageHistoryEntry,
    PublicationStatus,
    StandardSelectionMode,
)

from .test_engine import make_standard


def test_main_window_starts_with_empty_database(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    window = MainWindow(context)
    assert window.navigation.count() == 6
    assert window.home_standard_count.text() == "0/0"
    window.close()
    context.database.dispose()


def test_main_window_lists_published_standard(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    context.standards.install(make_standard())
    window = MainWindow(context)
    window.refresh_all()
    assert window.home_standard_count.text() == "1/1"
    assert window.standard_table.rowCount() == 1
    assert window.eval_standard.count() == 1
    window.navigation.setCurrentRow(1)
    assert window.pages.currentIndex() == 1
    window.standard_table.selectRow(0)
    window.refresh_standard_detail()
    assert window.standard_indicator_table.rowCount() == 1
    assert window.standard_indicator_table.item(0, 1).text() == "单位产品能耗"
    window.close()
    context.database.dispose()


def test_record_request_can_be_loaded_for_copy_or_recalculation(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = make_standard()
    context.standards.install(standard)
    request = EvaluationRequest(
        evaluation_date=standard.effective_date,
        standard_id=standard.id,
        product_id="product",
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="15", unit="kgce/t")},
        notes="回归测试备注",
    )
    context.evaluation_service.evaluate(request)
    window = MainWindow(context)
    window.refresh_records()
    assert window._load_request_into_form(request)
    assert window.eval_standard.currentData() == standard.id
    assert window.eval_product.currentData() == "product"
    assert window.eval_inputs.item(0, 2).text() == "15"
    assert window.eval_notes.text() == "回归测试备注"
    window.close()
    context.database.dispose()


def test_result_view_shows_grade_count_without_overall_grade(tmp_path: Path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = make_standard()
    context.standards.install(standard)
    window = MainWindow(context)
    monkeypatch.setattr("uebench.ui.main_window.QMessageBox.information", lambda *args, **kwargs: None)
    request = EvaluationRequest(
        evaluation_date=standard.effective_date,
        standard_id=standard.id,
        product_id="product",
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="20", unit="kgce/t")},
    )
    window.calculate_evaluation(request)
    assert "2级 1 项" in window.eval_summary.text()
    assert "不生成总体等级" in window.eval_summary.text()
    window.close()
    context.database.dispose()

def test_duplicate_product_names_show_indicator_hint(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = make_standard()
    duplicate = standard.products[0].model_copy(deep=True)
    duplicate.id = "product-2"
    duplicate.name = standard.products[0].name
    duplicate.indicators[0].id = "energy-2"
    duplicate.indicators[0].name = "单位产品电耗"
    standard.products.append(duplicate)
    context.standards.install(standard)
    window = MainWindow(context)
    labels = [window.eval_product.itemText(index) for index in range(window.eval_product.count())]
    assert any("测试产品（指标：单位产品能耗）" == label for label in labels)
    assert any("测试产品（指标：单位产品电耗）" == label for label in labels)
    assert [window.eval_product.itemData(index) for index in range(window.eval_product.count())] == ["product", "product-2"]
    window.close()
    context.database.dispose()
def test_future_standard_calculation_is_preview_only(tmp_path: Path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    future = make_standard().model_copy(update={
        "id": "gb-future-ui",
        "number": "GB 00004-2027",
        "version": "2027",
        "effective_date": date(2027, 1, 1),
    })
    context.standards.install(future)
    window = MainWindow(context)
    monkeypatch.setattr("uebench.ui.main_window.QMessageBox.information", lambda *args, **kwargs: None)
    request = EvaluationRequest(
        evaluation_date=date(2026, 9, 1),
        standard_id=future.id,
        product_id="product",
        selection_mode=StandardSelectionMode.FUTURE,
        input_mode=InputMode.DIRECT,
        inputs={"actual": InputValue(value="20", unit="kgce/t")},
    )
    window.calculate_evaluation(request)
    assert window.last_result_id is None
    assert context.application.list_recent_evaluations() == []
    assert window.eval_results.rowCount() == 1
    window.close()
    context.database.dispose()

def test_maintenance_page_shows_package_history_from_application_layer(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    entry = PackageHistoryEntry(
        package_id="pkg-history",
        data_version="2026.09-published.1",
        package_mode="incremental",
        issued_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        installed_at=datetime(2026, 9, 2, 12, 34, 56, tzinfo=timezone.utc),
        parent_package_id="pkg-parent",
        standard_count=63,
        rule_count=900,
        package_sha256="a" * 64,
    )
    context.application.list_package_history = lambda limit=50: [entry]
    window = MainWindow(context)
    window.navigation.setCurrentRow(5)
    assert window.package_history_table.rowCount() == 1
    assert window.package_history_table.item(0, 1).text() == "2026.09-published.1"
    assert window.package_history_table.item(0, 2).text() == "增量包"
    assert window.package_history_table.item(0, 3).text() == "pkg-parent"
    assert window.package_history_table.item(0, 7).text() == "a" * 64
    window.close()
    context.database.dispose()


def test_standard_library_shows_pending_standard_in_chinese(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    pending = make_standard().model_copy(update={
        "id": "gb-pending-2027",
        "number": "GB 00005-2027",
        "version": "2027",
        "title": "待确认测试标准",
        "publication_status": PublicationStatus.DRAFT,
        "effective_date": date(2027, 1, 1),
    })
    pending.products[0].indicators[0].notes = ["requires_independent_review"]
    context.standards.install(pending)
    window = MainWindow(context)
    assert window.standard_table.rowCount() == 1
    assert window.standard_table.item(0, 2).text() == "待确认（不可正式评价）"
    window.standard_table.selectRow(0)
    assert "需独立复核后使用" in window.standard_indicator_table.item(0, 6).text()
    assert "requires_independent_review" not in window.standard_indicator_table.item(0, 6).text()
    window.close()
    context.database.dispose()


def test_evaluation_hides_date_and_project_and_uses_mode_buttons(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    context.standards.install(make_standard())
    window = MainWindow(context)
    assert not window.eval_date.isVisible()
    assert not window.eval_project.isVisible()
    window.detail_mode_button.click()
    assert window.eval_mode.currentData() == InputMode.DETAIL.value
    window.direct_mode_button.click()
    assert window.eval_mode.currentData() == InputMode.DIRECT.value
    window.close()
    context.database.dispose()
