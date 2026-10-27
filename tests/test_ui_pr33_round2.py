import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGroupBox, QFrame, QLabel
from .test_ui_phase1 import window, fill_and_calculate
from .test_record_query_ui import records
from uebench.application.official_sources import official_source_url


@pytest.fixture(autouse=True)
def desktop_font():
    # 与实际桌面入口一致，避免 offscreen 未加载系统中文字体时使用方块字度量。
    from uebench.main import configure_application_font
    app = QApplication.instance() or QApplication([])
    configure_application_font(app)
    yield


@pytest.mark.parametrize("size", [(1256, 624), (1180, 760), (1440, 900), (900, 600)])
def test_actual_size_table_columns_and_context(records, size):
    _, win = records
    win.resize(*size)
    for key, table in (("standards", win.standard_table), ("records", win.record_table)):
        win.navigate(key)
        QApplication.processEvents()
        table.fit_columns()
        QApplication.processEvents()
        if size[0] >= 1180:
            assert table.horizontalScrollBar().maximum() == 0
            assert sum(table.columnWidth(i) for i in range(table.columnCount())) <= table.viewport().width()
        else:
            assert table.horizontalScrollBar().maximum() > 0
        if key == "records" and size[0] >= 1180:
            # 普通保存行的日期/状态/标准等无需普遍换行，长名称另有专门样例。
            for column in range(6):
                assert table.fontMetrics().horizontalAdvance(table.item(0, column).text()) + 16 <= table.columnWidth(column)
            assert table.font().pixelSize() == 13
        assert table.columnCount() == (5 if key == "standards" else 7)
        assert all(table.item(0, i).text() for i in range(table.columnCount()))
    win.record_search.setText("企业")
    win._record_filters_changed()
    win._record_page = 2
    win.refresh_records()
    win.record_table.selectRow(3)
    selected = win._selected_record_id()
    win.resize(1180, 760)
    QApplication.processEvents()
    assert win._record_page == 2 and win._selected_record_id() == selected


@pytest.mark.parametrize("focused", [False, True])
def test_closed_combos_do_not_wheel_change_saved_result(window, focused):
    fill_and_calculate(window)
    QApplication.processEvents()
    before = (window.gb29446_process.currentIndex(), window.gb29446_factor.text(), window.last_result_id)
    for combo in (window.gb29446_process, window.gb29446_period):
        window.evaluation_scroll.ensureWidgetVisible(combo)
        window.evaluation_scroll.verticalScrollBar().setValue(0)
        QApplication.processEvents()
        if focused:
            combo.setFocus()
        else:
            window.gb29446_electricity.setFocus()
        index = combo.currentIndex()
        scroll_before = window.evaluation_scroll.verticalScrollBar().value()
        event = QWheelEvent(QPointF(combo.rect().center()), QPointF(combo.mapToGlobal(combo.rect().center())), QPoint(), QPoint(0, -120), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        QApplication.sendEvent(combo, event)
        QApplication.processEvents()
        assert combo.currentIndex() == index
        assert window.evaluation_scroll.verticalScrollBar().value() > scroll_before
    assert (window.gb29446_process.currentIndex(), window.gb29446_factor.text(), window.last_result_id) == before
    assert window.context.application.count_evaluations() == 1
    combo = window.gb29446_period
    combo.setFocus()
    old = combo.currentIndex()
    QTest.keyClick(combo, Qt.Key_Down)
    assert combo.currentIndex() != old
    combo.showPopup()
    QApplication.processEvents()
    candidate = combo.model().index(2, 0)
    QTest.mouseClick(combo.view().viewport(), Qt.LeftButton, pos=combo.view().visualRect(candidate).center())
    assert combo.currentIndex() == 2


def test_settings_titles_are_inside_cards_and_path_wraps(window):
    window.resize(1256, 624)
    window.navigate("settings")
    page = window.settings_page
    page.data_directory_value.setText("D:/隔离路径/" + "较长的路径段/" * 18)
    page.advanced_toggle.click()
    QApplication.processEvents()
    assert not page.findChildren(QGroupBox)
    cards = [c for c in page.findChildren(QFrame) if c.property("class") == "card"]
    assert len(cards) == 3
    for card in cards:
        heading = card.findChildren(QLabel)[0]
        assert heading.mapTo(card, QPoint()).y() >= 18
        assert heading.height() >= heading.fontMetrics().height()
    assert page.data_directory_value.wordWrap()
    assert page.data_directory_value.textInteractionFlags() & Qt.TextSelectableByMouse


@pytest.mark.parametrize("outcome", [True, False, RuntimeError("browser failed")])
def test_official_request_is_honest_and_always_copyable(window, monkeypatch, outcome):
    def opener(url):
        assert url.toString() == official_source_url("gb-29446-2019")
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr("uebench.ui.main_window.QDesktopServices.openUrl", opener)
    assert window.open_official_source("gb-29446-2019") == (outcome is True)
    dialog = window.official_source_dialog
    assert dialog.address.text() == official_source_url("gb-29446-2019")
    assert "打开成功" not in dialog.notice.text()
    dialog.copy_button.click()
    assert QApplication.clipboard().text() == dialog.address.text()
    dialog.close()


def test_radio_text_keyboard_and_visible_indicator(window):
    window.start_formal_evaluation()
    buttons = window.coal_button_group.buttons()
    for button in (buttons[1], buttons[0]):
        QTest.mouseClick(button, Qt.LeftButton, pos=QPoint(button.width() - 10, button.height() // 2))
        assert button.isChecked()
        assert sum(b.isChecked() for b in buttons) == 1
        assert window.gb29446_coal_type.currentText() == button.text()
    buttons[1].setFocus()
    QTest.keyClick(buttons[1], Qt.Key_Space)
    assert buttons[1].isChecked()
    # 指示器内有蓝色像素，不能仅以 isChecked 宣称可见。
    image = buttons[1].grab().toImage()
    blue = sum(image.pixelColor(x,y).blue() > image.pixelColor(x,y).red() + 40 for x in range(min(28,image.width())) for y in range(image.height()))
    assert blue > 12


@pytest.mark.parametrize("raise_inside", [False, True])
def test_frozen_browser_environment_is_restored(monkeypatch, tmp_path, raise_inside):
    import sys
    import ctypes
    from pathlib import Path
    from uebench.ui.external_browser import external_browser_environment
    if sys.platform != "win32":
        pytest.skip("Windows DLL 搜索路径专属检查")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    previous_path = str(bundle / "PySide6") + os.pathsep + os.environ.get("PATH", "")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("PATH", previous_path)
    def current_directory():
        buffer = ctypes.create_unicode_buffer(32768)
        ctypes.windll.kernel32.GetDllDirectoryW(len(buffer), buffer)
        return buffer.value
    before = current_directory()
    try:
        with external_browser_environment():
            assert str(bundle / "PySide6") not in os.environ["PATH"]
            assert current_directory() == ""
            if raise_inside:
                raise RuntimeError("external request")
    except RuntimeError:
        assert raise_inside
    assert os.environ["PATH"] == previous_path
    assert current_directory() == before
