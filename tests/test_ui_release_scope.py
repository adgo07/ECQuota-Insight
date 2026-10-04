"""ECQ-RS05 §二(UI) / §三 / §四 / §六 / §七 — Windows V1 release-scope UI gates.

These tests drive the **real widgets** offscreen against a real application context
(the pattern established by ``tests/test_gb29446_evaluate_wiring.py``): no modal box
may hang the run, and every assertion goes through Qt signals, table cells and
buttons rather than through the private helpers alone.

What is fenced here:

* §二 时间显示 — every ordinary page renders stored-UTC timestamps in local time to
  the second (:func:`uebench.ui.presentation.format_local_datetime`), never with
  microseconds and never with a second offset added.
* §三 正式评价范围 — the 「新建评价」 combo offers exactly the formally supported
  standards, and an unsupported standard cannot reach a formal evaluation through
  the combo, the library, the home page or the Excel entry.
* §四 官方来源 — 「查看标准原文」 opens the pre-registered official page from
  :mod:`uebench.application.official_sources`; the ordinary UI never opens a local
  PDF, and an unregistered standard disables the control.
* §六 标准库信息结构 — support status, evaluation scope and official source are
  visible; internal traceability noise is gone; the scope of an un-surveyed
  standard is reported as pending instead of invented.
* §七 新建评价 — the combo is wide enough to read, the duplicated standard name is
  gone, and the library can jump into the page with the supported standard selected.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QTextEdit

from uebench.application.evaluation_support import (
    FORMAL_EVALUATION_SUPPORTED_LABEL,
    FORMAL_EVALUATION_UNSUPPORTED_LABEL,
    SUPPORTED_EVALUATION_STANDARD_IDS,
    supports_formal_evaluation,
)
from uebench.application.official_sources import (
    NO_OFFICIAL_SOURCE_LABEL,
    OFFICIAL_SOURCE_PLATFORM_NAME,
    VIEW_OFFICIAL_SOURCE_BUTTON_TEXT,
    official_source_url,
)
from uebench.bootstrap import create_context
from uebench.domain.models import StandardDefinition
from uebench.ui.main_window import MainWindow, gb29446_rule_is_compatible
from uebench.ui.presentation import format_local_datetime

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = ROOT / "src" / "uebench" / "resources" / "update_public_key.pem"
BUNDLED_PACKAGE = ROOT / "release" / "standard-packages" / "initial-standard-package-published.uebench"
GB29446_DEFINITION = ROOT / "data" / "definitions" / "gb-29446-2019.json"

GB29446_ID = "gb-29446-2019"
#: ``YYYY-MM-DD HH:MM:SS`` — the ordinary user-facing timestamp shape.
SECONDS_PRECISION = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
#: Microseconds, i.e. the reported defect ``2026-10-04 15:31:39.338366``.
MICROSECONDS = re.compile(r"\.\d{3,}")

#: 标准库表格中本任务新增/保留的列（顺序即用户看到的顺序）。
COLUMN_SUPPORT_STATUS = 5
COLUMN_EVALUATION_SCOPE = 6
COLUMN_OFFICIAL_SOURCE = 7


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _silence_dialogs(monkeypatch):
    """No modal box may block: the ordinary flows really do open message boxes.

    ``QMessageBox.warning/information/critical`` run a nested event loop, which
    would hang an offscreen run forever.  Individual tests re-patch these when
    they care about the text.
    """
    for name in ("warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.Ok))
    yield


def _gb29446_definition() -> StandardDefinition:
    """The repo's authoritative GB 29446—2019 r2 definition (source of scope metadata)."""

    return StandardDefinition.model_validate_json(GB29446_DEFINITION.read_text(encoding="utf-8"))


def _unsupported_definition(index: int) -> StandardDefinition:
    """A valid, published, currently effective standard that is **not** formally evaluable.

    It is structurally a copy of the GB 29446 definition with a different identity, so
    the library really does hold "many more" standards than the combo offers without
    depending on the content of the release package.
    """

    data = copy.deepcopy(json.loads(GB29446_DEFINITION.read_text(encoding="utf-8")))
    data.update(
        {
            "id": f"gb-0000{index}-2026",
            "number": f"GB 0000{index}-2026",
            "version": "2026",
            "title": f"未梳理对照标准{index}",
            "standard_family_id": f"GB 0000{index}",
            "rule_revision": 1,
            "publication_status": "published",
            "publication_date": "2025-06-01",
            "effective_date": "2026-01-01",
        }
    )
    return StandardDefinition.model_validate(data)


def _install_library(context) -> None:
    """Install a realistic library: the release package when available, plus fixtures."""

    application = context.application
    if BUNDLED_PACKAGE.is_file() and application.has_package_service():
        application.install_package(BUNDLED_PACKAGE)
    installed_gb = next(
        (item for item in application.list_library_standards() if item.id == GB29446_ID), None
    )
    if installed_gb is None or not gb29446_rule_is_compatible(installed_gb):
        # The bundle is the release artifact; when it is unavailable (or still carries
        # the legacy GB 29446 revision) fall back to the repo's authoritative r2 file.
        context.standards.install(_gb29446_definition())
    for index in (1, 2):
        context.standards.install(_unsupported_definition(index))


@pytest.fixture()
def window(qt_app: QApplication, tmp_path: Path):
    context = create_context(tmp_path / "appdata", public_key_path=PUBLIC_KEY)
    _install_library(context)
    win = MainWindow(context)
    try:
        yield win
    finally:
        win.close()
        context.database.dispose()


def _library_row(window: MainWindow, standard_id: str) -> int:
    """Row index of ``standard_id`` in the standard-library table."""

    for row in range(window.standard_table.rowCount()):
        item = window.standard_table.item(row, 0)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) == standard_id:
            return row
    pytest.fail(f"标准库中找不到 {standard_id}")


def _first_unsupported_id(window: MainWindow) -> str:
    for standard in window.context.application.list_library_standards():
        if not supports_formal_evaluation(standard.id):
            return standard.id
    pytest.fail("标准库中应至少存在一个未纳入正式评价范围的标准")


def _evaluate_gb29446(window: MainWindow, *, electricity: str = "560", raw_coal: str = "100") -> None:
    """Fill the real GB 29446 form and press the real 计算并判级 button."""

    coal = window.gb29446_coal_type
    index = coal.findText("炼焦煤")
    assert index >= 0, "煤种下拉框缺少炼焦煤"
    coal.setCurrentIndex(index)
    process = window.gb29446_process
    index = process.findData("重介")
    assert index >= 0, "选煤工艺下拉框缺少重介"
    process.setCurrentIndex(index)
    window.gb29446_electricity.setText(electricity)
    window.gb29446_raw_coal.setText(raw_coal)
    window.calculate_button.click()
    assert window.last_result_id is not None, window.gb29446_result_message.text()


# ---------------------------------------------------------------------------
# §三 正式评价范围 = GB 29446—2019
# ---------------------------------------------------------------------------


def test_new_evaluation_combo_offers_exactly_the_formally_supported_standards(window) -> None:
    library_ids = {item.id for item in window.context.application.list_library_standards()}
    assert GB29446_ID in library_ids
    assert len(library_ids) > 3, "标准库应远多于正式评价范围内的标准"

    offered = {window.eval_standard.itemData(index) for index in range(window.eval_standard.count())}
    assert offered == set(SUPPORTED_EVALUATION_STANDARD_IDS) == {GB29446_ID}
    assert window.eval_standard.currentData() == GB29446_ID
    assert window.eval_support_label.text() == FORMAL_EVALUATION_SUPPORTED_LABEL


def test_unsupported_standard_cannot_reach_formal_evaluation(window) -> None:
    unsupported_id = _first_unsupported_id(window)
    assert not supports_formal_evaluation(unsupported_id)
    # “库里有”不等于“能正式评价”：它在下拉框里根本不被提供。
    assert window.eval_standard.findData(unsupported_id) == -1
    window.navigation.setCurrentRow(1)
    assert window.open_evaluation_for_standard(unsupported_id) is False
    assert window.navigation.currentRow() == 1, "被拒绝的标准不得跳进新建评价"
    assert window.eval_standard.findData(unsupported_id) == -1
    assert window.eval_standard.currentData() == GB29446_ID


def test_home_page_affords_formal_evaluation_only_from_the_registry(window) -> None:
    assert window.home_formal_scope_count.text() == "1 项"
    assert "GB 29446-2019" in window.home_scope_label.text()
    assert window.home_start_evaluation.isEnabled()
    window.home_start_evaluation.click()
    assert window.navigation.currentRow() == 2
    assert window.eval_standard.currentData() == GB29446_ID


# ---------------------------------------------------------------------------
# §二 时间显示（A：报障缺陷）
# ---------------------------------------------------------------------------


def test_record_list_renders_local_seconds_precision(window) -> None:
    _evaluate_gb29446(window)
    window.refresh_records()
    assert window.record_table.rowCount() == 1
    stored = window.context.application.list_recent_evaluations(1)[0]

    rendered = window.record_table.item(0, 0).text()
    assert SECONDS_PRECISION.fullmatch(rendered), rendered
    assert "." not in rendered, f"普通列表不得显示微秒：{rendered}"
    assert rendered == format_local_datetime(stored.created_at)
    assert window.record_table.item(0, 1).text() == stored.evaluation_date.strftime("%Y-%m-%d")

    window.refresh_home()
    home_rendered = window.home_recent.item(0, 0).text()
    assert SECONDS_PRECISION.fullmatch(home_rendered), home_rendered
    assert home_rendered == format_local_datetime(stored.created_at)


def test_record_detail_renders_local_seconds_precision(window) -> None:
    _evaluate_gb29446(window)
    window.refresh_records()
    window.record_table.selectRow(0)
    window.view_selected_record()

    dialog = window.record_detail_dialog
    content = dialog.findChild(QTextEdit, "record_detail_content")
    assert content is not None
    text = content.toPlainText()
    stored = window.context.application.get_evaluation(window.last_result_id)[1]
    expected = format_local_datetime(stored.evaluated_at)
    assert SECONDS_PRECISION.fullmatch(expected), expected

    time_lines = [line for line in text.splitlines() if line.startswith("评价时间：")]
    assert time_lines == [f"评价时间：{expected}"]
    assert MICROSECONDS.search(time_lines[0]) is None
    date_lines = [line for line in text.splitlines() if line.startswith("评价日期：")]
    assert date_lines and MICROSECONDS.search(date_lines[0]) is None


def test_audit_and_package_history_render_local_seconds_precision(window) -> None:
    _evaluate_gb29446(window)
    window.navigation.setCurrentRow(5)

    assert window.audit_table.rowCount() >= 1
    audit_entry = window.context.application.list_audit(500)[0]
    audit_cell = window.audit_table.item(0, 0).text()
    assert SECONDS_PRECISION.fullmatch(audit_cell), audit_cell
    assert audit_cell == format_local_datetime(audit_entry.created_at)

    history = window.context.application.list_package_history(100)
    if not history:  # pragma: no cover - depends on the release package being present
        pytest.skip("本机没有已安装标准包历史，跳过该列的时间显示检查")
    installed_cell = window.package_history_table.item(0, 0).text()
    assert SECONDS_PRECISION.fullmatch(installed_cell), installed_cell
    assert installed_cell == format_local_datetime(history[0].installed_at)


# ---------------------------------------------------------------------------
# §六 标准库信息结构
# ---------------------------------------------------------------------------


def test_library_shows_support_status_scope_and_unsurveyed_state(window) -> None:
    gb_row = _library_row(window, GB29446_ID)
    assert window.standard_table.item(gb_row, COLUMN_SUPPORT_STATUS).text() == (
        FORMAL_EVALUATION_SUPPORTED_LABEL
    )
    gb_scope = window.standard_table.item(gb_row, COLUMN_EVALUATION_SCOPE).text()
    assert "炼焦煤" in gb_scope and "动力煤" in gb_scope
    assert "统计边界按标准第5.1条" in gb_scope
    assert "尚待梳理" not in gb_scope
    assert window.standard_table.item(gb_row, COLUMN_OFFICIAL_SOURCE).text() == (
        OFFICIAL_SOURCE_PLATFORM_NAME
    )

    unsupported_id = _first_unsupported_id(window)
    other_row = _library_row(window, unsupported_id)
    assert window.standard_table.item(other_row, COLUMN_SUPPORT_STATUS).text() == (
        FORMAL_EVALUATION_UNSUPPORTED_LABEL
    )
    # 未重新梳理的标准只能如实显示“待梳理”，不得由 UI 代写范围文字。
    assert window.standard_table.item(other_row, COLUMN_EVALUATION_SCOPE).text() == "评价范围尚待梳理"
    window.standard_table.selectRow(other_row)
    assert "评价范围尚待梳理" in window.standard_detail_label.text()

    window.standard_table.selectRow(gb_row)
    assert FORMAL_EVALUATION_SUPPORTED_LABEL in window.standard_detail_label.text()
    assert "统计边界" in window.standard_detail_label.text()


def test_library_no_longer_shows_internal_traceability_noise(window) -> None:
    headers = [
        window.standard_table.horizontalHeaderItem(column).text()
        for column in range(window.standard_table.columnCount())
    ]
    assert headers == [
        "标准编号",
        "标准名称",
        "标准状态",
        "版本",
        "实施日期",
        "软件评价支持状态",
        "评价范围",
        "官方来源",
    ]
    indicator_headers = [
        window.standard_indicator_table.horizontalHeaderItem(column).text()
        for column in range(window.standard_indicator_table.columnCount())
    ]
    assert "页码" not in indicator_headers
    assert "条款/表号" not in indicator_headers
    assert "原文SHA-256" not in headers
    assert "产品/工序数" not in headers


def test_library_can_jump_into_new_evaluation_with_the_supported_standard(window) -> None:
    window.navigation.setCurrentRow(1)
    window.standard_table.selectRow(_library_row(window, GB29446_ID))
    assert window.standard_evaluate_button.isEnabled()
    window.standard_evaluate_button.click()
    assert window.navigation.currentRow() == 2
    assert window.eval_standard.currentData() == GB29446_ID
    assert window.current_standard is not None and window.current_standard.id == GB29446_ID

    # 未纳入正式评价范围的标准没有可执行的评价入口。
    window.navigation.setCurrentRow(1)
    window.standard_table.selectRow(_library_row(window, _first_unsupported_id(window)))
    assert window.standard_evaluate_button.isEnabled() is False
    window.standard_evaluate_button.click()
    assert window.navigation.currentRow() == 1


# ---------------------------------------------------------------------------
# §四 官方来源（不再打开本机 PDF）
# ---------------------------------------------------------------------------


def test_view_official_source_opens_the_registry_url_from_both_pages(window, monkeypatch) -> None:
    opened: list[QUrl] = []
    monkeypatch.setattr(
        "uebench.ui.main_window.QDesktopServices.openUrl",
        lambda url: opened.append(url) or True,
    )
    expected = official_source_url(GB29446_ID)
    assert expected is not None

    window.navigation.setCurrentRow(1)
    window.standard_table.selectRow(_library_row(window, GB29446_ID))
    assert window.standard_official_button.text() == VIEW_OFFICIAL_SOURCE_BUTTON_TEXT
    window.standard_official_button.click()

    window.navigation.setCurrentRow(2)
    assert window.eval_standard_open.text() == VIEW_OFFICIAL_SOURCE_BUTTON_TEXT
    window.eval_standard_open.click()

    assert [url.toString() for url in opened] == [expected, expected]
    assert QUrl(expected).host() == "std.samr.gov.cn"
    assert opened[0].host() == "std.samr.gov.cn"


def test_unregistered_standard_disables_the_official_source_control(window, monkeypatch) -> None:
    opened: list[QUrl] = []
    monkeypatch.setattr(
        "uebench.ui.main_window.QDesktopServices.openUrl",
        lambda url: opened.append(url) or True,
    )
    unsupported_id = _first_unsupported_id(window)
    row = _library_row(window, unsupported_id)
    window.navigation.setCurrentRow(1)
    window.standard_table.selectRow(row)

    assert official_source_url(unsupported_id) is None
    assert window.standard_table.item(row, COLUMN_OFFICIAL_SOURCE).text() == NO_OFFICIAL_SOURCE_LABEL
    assert window.standard_official_status.text() == NO_OFFICIAL_SOURCE_LABEL
    assert window.standard_official_button.isEnabled() is False
    window.standard_official_button.click()
    assert opened == [], "未登记官方来源时不得尝试打开任何地址"


def test_ordinary_ui_never_opens_a_local_pdf(tmp_path: Path, qt_app: QApplication, monkeypatch) -> None:
    """Guard: a matching local PDF exists, yet the ordinary UI opens only the registry page."""

    context = create_context(tmp_path / "pdf-appdata", public_key_path=PUBLIC_KEY)
    standard = _gb29446_definition()
    source = context.paths.standards / "gb29446-local-source.pdf"
    source.write_bytes(b"local PDF the ordinary UI must no longer open")
    standard.source_file = source.name
    standard.source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    for product in standard.products:
        for indicator in product.indicators:
            for reference in indicator.source_references:
                reference.source_file = source.name
                reference.source_sha256 = standard.source_sha256
    context.standards.install(standard)

    window = MainWindow(context)
    opened: list[QUrl] = []
    monkeypatch.setattr(
        "uebench.ui.main_window.QDesktopServices.openUrl",
        lambda url: opened.append(url) or True,
    )
    try:
        # 旧行为之所以危险：本机确实存在与该标准版本 SHA-256 一致的 PDF。
        assert context.application.find_standard_source(GB29446_ID) == source.resolve()

        window.navigation.setCurrentRow(1)
        window.standard_table.selectRow(_library_row(window, GB29446_ID))
        window.standard_official_button.click()

        window.navigation.setCurrentRow(2)
        window.eval_standard_open.click()

        _evaluate_gb29446(window)
        window.navigation.setCurrentRow(3)
        window.refresh_records()
        window.record_table.selectRow(0)
        window.view_selected_record()
        record_button = window.record_detail_dialog.findChild(QPushButton, "recordOfficialSourceButton")
        assert record_button is not None and record_button.isEnabled()
        record_button.click()

        assert opened, "普通界面必须能够打开官方来源页面"
        for url in opened:
            text = url.toString()
            assert url.scheme() == "https", text
            assert url.isLocalFile() is False, text
            assert "file://" not in text.lower(), text
            assert ".pdf" not in text.lower(), text
        assert {url.toString() for url in opened} == {official_source_url(GB29446_ID)}
    finally:
        window.close()
        context.database.dispose()


# ---------------------------------------------------------------------------
# §七 新建评价页面
# ---------------------------------------------------------------------------


def test_new_evaluation_page_reads_the_full_standard_and_is_not_duplicated(window) -> None:
    text = window.eval_standard.itemText(0)
    assert "GB 29446-2019" in text and "选煤电力消耗限额" in text
    # 下拉框足够宽，编号与名称都能读完。
    assert window.eval_standard.minimumWidth() >= 360
    # 「当前有效」旁不再重复标准编号/名称。
    assert window.eval_standard_status.text() == "当前有效"
    assert "GB 29446-2019" not in window.eval_standard_status.text()
    # 页面右上角有官方来源入口与支持状态。
    assert window.eval_standard_open.text() == VIEW_OFFICIAL_SOURCE_BUTTON_TEXT
    assert window.eval_official_status.text() == OFFICIAL_SOURCE_PLATFORM_NAME
    assert window.eval_support_label.text() == FORMAL_EVALUATION_SUPPORTED_LABEL


def test_calculation_explanation_keeps_the_basis_in_plain_language(window) -> None:
    _evaluate_gb29446(window)
    explanation = window.gb29446_explanation.text()
    # 输入的 E_d、m、选煤工艺与 k、公式、最终值与等级、标准依据都必须保留。
    assert "统计期选煤电力消耗量 E_d" in explanation and "560" in explanation
    assert "统计期入选原煤量 m" in explanation and "100" in explanation
    assert "重介" in explanation and "折算系数 k" in explanation and "1.12" in explanation
    assert "e_d = 560 × 1.12 / 100 = 6.272 kW·h/t" in explanation
    assert "本次电耗 e_d = 6.27 kW·h/t；判级结果：2级" in explanation
    assert "原始计算值（未修约）：6.272 kW·h/t" in explanation
    assert "判级比较：6.272 ≤ 7；结果：2级" in explanation
    assert "标准依据：" in explanation and "第5.2条" in explanation and "附录A表A.1" in explanation
    # 不堆叠内部追踪术语。
    for internal in ("rule_id", "numeric_behavior", "CalculationStep", "field_id", "calculator_version"):
        assert internal not in explanation
