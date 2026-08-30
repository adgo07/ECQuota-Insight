from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from uebench.bootstrap import create_context
from uebench.ui.main_window import MainWindow
from uebench.domain.models import EvaluationRequest, InputMode, InputValue

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
