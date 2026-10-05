from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

import pytest

from uebench.application import evaluation_support
from uebench.application.evaluation_support import (
    FORMAL_EVALUATION_SUPPORTED_LABEL,
    FORMAL_EVALUATION_UNSUPPORTED_LABEL,
)
from uebench.bootstrap import create_context
from uebench.ui.main_window import MainWindow
from uebench.domain.models import (
    EvaluationRequest,
    InputMode,
    InputValue,
    PackageHistoryEntry,
    PublicationStatus,
    SelectionLevel,
    StandardSelectionMode,
)

from .test_engine import make_standard


def _in_formal_scope(monkeypatch, *standard_ids: str) -> None:
    """Declare ``standard_ids`` as formally evaluable for this test.

    正式评价范围是应用层的固定常量，**与“标准库里有没有这个标准”无关**。需要正式
    评价入口（「新建评价」下拉框、基于记录重新评价、选择控件联动）的用例必须显式把
    自己使用的标准放进注册表，而不是依赖夹具标准恰好落在范围内——那正是 RS05 §三
    修掉的缺陷。这里扩展的是真正的注册表本身，因此界面行为仍然完全由注册表驱动。
    """

    extended = set(evaluation_support.SUPPORTED_EVALUATION_STANDARD_IDS) | set(standard_ids)
    monkeypatch.setattr(
        evaluation_support, "SUPPORTED_EVALUATION_STANDARD_IDS", frozenset(extended)
    )


def _seed_legacy_record(context, request: EvaluationRequest):
    """直接写入一条**历史**正式记录，模拟 RS05 §三 之前版本留下的范围外记录。

    ``EvaluationService.evaluate`` 现在拒绝范围外标准，但真实用户的数据库里仍存有旧版本
    （把 ``published`` 当可评价）写下的记录——这正是本修复要保护的存量数据。要覆盖“这类
    记录不得经「基于此记录重新评价」回到正式评价”，记录就必须**绕过正式写入口**直接落到
    仓储，而不能靠临时放宽注册表去伪造一次正式评价——那恰恰是修复要禁止的行为。
    """
    standard = context.application.get_published_standard(request.standard_id)
    assert standard is not None, f"夹具标准应已安装：{request.standard_id}"
    result = context.application.preview_evaluation(request)
    context.evaluations.save(request, result, standard)
    return result


@pytest.fixture(autouse=True)
def _never_block_on_a_modal_dialog(monkeypatch):
    """兜底：任何用例都不得因**真实模态对话框**永久阻塞事件循环。

    ``QMessageBox.warning/critical/information`` 的静态方法会进入嵌套事件循环；offscreen
    下没有用户去点按钮，于是**永远**不返回——一次本应是断言失败的拒绝会变成整套挂死，
    pytest 连失败清单都写不出来。RS05 §三 新增了范围拒绝路径之后，这种风险从“不可能”变成
    “很容易”（任何驱动正式评价入口的用例都可能撞上）。

    这里只做**兜底**：需要断言对话框内容的用例在自己的函数体里再 ``monkeypatch.setattr``，
    函数体的补丁在后、优先级更高，仍然能捕获到标题与正文。
    """
    for name, button in (
        ("warning", QMessageBox.StandardButton.Ok),
        ("information", QMessageBox.StandardButton.Ok),
        ("critical", QMessageBox.StandardButton.Ok),
    ):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, _b=button, **k: _b))


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
    # 库里“有”这个标准 ≠ 软件“正式支持评价”这个标准（RS05 §三）：标准库照旧列出它，
    # 但「新建评价」下拉框一个都不提供，可评价性由独立的支持状态列承载。
    assert window.eval_standard.count() == 0
    assert window.eval_standard.currentData() is None
    assert window.standard_table.item(0, 5).text() == FORMAL_EVALUATION_UNSUPPORTED_LABEL
    window.navigation.setCurrentRow(1)
    assert window.pages.currentIndex() == 1
    window.standard_table.selectRow(0)
    window.refresh_standard_detail()
    assert window.standard_indicator_table.rowCount() == 1
    assert window.standard_indicator_table.item(0, 1).text() == "单位产品能耗"
    window.close()
    context.database.dispose()


def test_record_request_can_be_loaded_for_copy_or_recalculation(tmp_path: Path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = make_standard()
    context.standards.install(standard)
    # 重新评价属于正式评价入口，因此该标准必须在正式评价范围内。
    _in_formal_scope(monkeypatch, standard.id)
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
    assert window.eval_standard.findData(standard.id) >= 0
    window.refresh_records()
    assert window._load_request_into_form(request)
    assert window.eval_standard.currentData() == standard.id
    assert window.eval_product.currentData() == "product"
    assert window.eval_inputs.item(0, 2).text() == "15"
    assert window.eval_notes.text() == "回归测试备注"
    window.close()
    context.database.dispose()


def test_record_of_out_of_scope_standard_cannot_be_re_evaluated(
    tmp_path: Path, monkeypatch
) -> None:
    """RS05 §三：正式评价范围之外的标准不得经“基于此记录重新评价”回到正式评价。

    记录本身是**存量数据**：旧版本会为范围外标准写下正式记录，新版本必须保留它可查看，
    但不允许借它重新进入正式评价。因此这里直接把记录写进仓储（见 ``_seed_legacy_record``），
    而不是经已加门槛的 ``evaluate``。
    """

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
    )
    assert evaluation_support.supports_formal_evaluation(standard.id) is False
    _seed_legacy_record(context, request)
    window = MainWindow(context)
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _parent, _title, message: warnings.append(message)
    )
    window.refresh_records()
    window.record_table.selectRow(0)
    window.recalculate_selected_record()

    # 拒绝：没有进入表单、没有切换页面、没有生成新的结果。
    assert warnings, "被拒绝的重新评价必须给出明确原因"
    assert FORMAL_EVALUATION_UNSUPPORTED_LABEL in warnings[0]
    assert window.eval_standard.currentData() is None
    assert window.last_result_id is None
    assert window.navigation.currentRow() != 2
    window.close()
    context.database.dispose()


def test_result_view_shows_grade_count_without_overall_grade(tmp_path: Path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = make_standard()
    context.standards.install(standard)
    # 本用例覆盖的是「结果页等级计数」，不是范围；结果页需要一次**正式**评价，因此把夹具
    # 标准显式放进注册表（RS05 §三）。否则 evaluate 会被范围门槛拒绝，界面转而弹出真正的
    # 模态错误框——在 offscreen 下会永久阻塞事件循环（旧行为里没有这条拒绝路径）。
    _in_formal_scope(monkeypatch, standard.id)
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

def test_duplicate_product_names_show_indicator_hint(tmp_path: Path, monkeypatch) -> None:
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
    # 产品选择控件属于正式评价路径，标准必须在正式评价范围内。
    _in_formal_scope(monkeypatch, standard.id)
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
    # 「标准状态」只描述标准文档本身的效力；软件能否正式评价由独立列承载。
    assert window.standard_table.item(0, 2).text() == "待确认"
    assert window.standard_table.item(0, 5).text() == FORMAL_EVALUATION_UNSUPPORTED_LABEL
    window.standard_table.selectRow(0)
    assert "需独立复核后使用" in window.standard_indicator_table.item(0, 6).text()
    assert "requires_independent_review" not in window.standard_indicator_table.item(0, 6).text()
    window.close()
    context.database.dispose()


def test_evaluation_hides_date_and_project_and_uses_mode_buttons(tmp_path: Path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = make_standard()
    context.standards.install(standard)
    _in_formal_scope(monkeypatch, standard.id)
    window = MainWindow(context)
    assert not window.eval_date.isVisible()
    assert not window.eval_project.isVisible()
    assert window.eval_standard.isEditable()
    assert window.eval_standard_open.text() == "查看标准原文"
    # 下拉框要能完整读出“编号 + 名称”，状态标签只显示状态，不再重复编号/名称。
    assert window.eval_standard.itemText(0) == f"{standard.number} {standard.title}"
    assert window.eval_standard.minimumWidth() >= 360
    assert window.eval_standard_status.text() == "当前有效"
    assert standard.number not in window.eval_standard_status.text()
    assert window.eval_support_label.text() == FORMAL_EVALUATION_SUPPORTED_LABEL
    window.detail_mode_button.click()
    assert window.eval_mode.currentData() == InputMode.DETAIL.value
    window.direct_mode_button.click()
    assert window.eval_mode.currentData() == InputMode.DIRECT.value
    window.close()
    context.database.dispose()


def test_rule_declared_product_selection_cascades_and_keeps_product_id(tmp_path: Path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    standard = make_standard()
    standard.selection_schema = [
        SelectionLevel(key="product_category", label="产品类别"),
        SelectionLevel(key="product_spec", label="产品规格/工序"),
    ]
    standard.products[0].selection_values = {
        "product_category": "类别A",
        "product_spec": "规格A",
    }
    second = standard.products[0].model_copy(deep=True)
    second.id = "product-2"
    second.name = "产品B"
    second.indicators[0].id = "energy-2"
    second.selection_values = {
        "product_category": "类别B",
        "product_spec": "规格B",
    }
    standard.products.append(second)
    context.standards.install(standard)
    # 选择控件属于正式评价路径，标准必须在正式评价范围内。
    _in_formal_scope(monkeypatch, standard.id)
    window = MainWindow(context)

    assert [level.label for level, _combo in window.selection_widgets] == ["产品类别", "产品规格/工序"]
    category, specification = [combo for _level, combo in window.selection_widgets]
    assert [category.itemText(i) for i in range(category.count())] == ["类别A", "类别B"]
    assert [specification.itemText(i) for i in range(specification.count())] == ["规格A"]
    category.setCurrentIndex(category.findData("__value__:类别B"))
    assert [specification.itemText(i) for i in range(specification.count())] == ["规格B"]
    assert window.eval_product.currentData() == "product-2"
    window.close()
    context.database.dispose()


def test_standard_selector_restores_first_option_when_version_scope_changes(tmp_path: Path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    context = create_context(tmp_path / "appdata")
    current = make_standard()
    future = make_standard().model_copy(update={
        "id": "gb-future-selector",
        "number": "GB 00006-2027",
        "version": "2027",
        "effective_date": date(2027, 1, 1),
    })
    context.standards.install(current)
    context.standards.install(future)
    # 两个版本都要在正式评价范围内，才能在各自的版本选择方式里出现。
    _in_formal_scope(monkeypatch, current.id, future.id)
    window = MainWindow(context)
    assert window.eval_standard.currentData() == current.id
    window.eval_selection_mode.setCurrentIndex(2)
    assert window.eval_standard.currentData() == future.id
    assert "尚未实施" in window.eval_standard_status.text()
    window.close()
    context.database.dispose()
