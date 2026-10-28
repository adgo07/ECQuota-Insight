"""本轮 UI 改动的轻量回归，不代替原生 Windows 桌面验收。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRect, Qt, QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QPushButton, QLineEdit, QComboBox
from .test_ui_phase1 import window, fill_and_calculate
from uebench.ui.brand import BrandLabel
from uebench.ui.message_box import localize_buttons
from uebench.ui.window_placement import bounded_rect, WindowPlacement


@pytest.mark.parametrize("rect,area", [
    (QRect(4000, -2000, 1280, 800), QRect(0, 0, 1366, 728)),
    (QRect(-1800, 30, 1280, 800), QRect(-1920, 0, 1920, 1040)),
    (QRect(0, 0, 1280, 800), QRect(0, 0, 800, 500)),
])
def test_outer_frame_fits_even_after_screen_is_removed(rect, area):
    result = bounded_rect(rect, area, 16, 40)
    assert area.contains(QRect(result.x(), result.y(), result.width() + 16, result.height() + 40))


def test_first_window_restore_and_maximized(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    class Screen:
        def availableGeometry(self):
            return QRect(0, 0, 1920, 1040)
    screen = Screen()
    monkeypatch.setattr(QApplication, "screens", lambda: [screen])
    win = QMainWindow()
    monkeypatch.setattr(win, "screen", lambda: screen)
    state = WindowPlacement(win, tmp_path)
    assert win.size().width() == 1280 and win.size().height() == 800
    assert win.geometry().center() == screen.availableGeometry().center()
    win.setGeometry(120, 80, 1100, 700)
    state.save()
    restored = QMainWindow()
    monkeypatch.setattr(restored, "screen", lambda: screen)
    state2 = WindowPlacement(restored, tmp_path)
    assert restored.geometry() == QRect(120, 80, 1100, 700)
    state2.settings.setValue("window/maximized", True)
    state2.settings.sync()
    maximized = QMainWindow()
    monkeypatch.setattr(maximized, "screen", lambda: screen)
    WindowPlacement(maximized, tmp_path)
    assert maximized.isMaximized()
    # 掉屏偏好读回后仍被约束到可用区。
    state2.settings.setValue("window/normal", QRect(5000, 4000, 1800, 1200))
    state2.settings.sync()
    WindowPlacement(restored, tmp_path)
    rect = restored.geometry()
    assert screen.availableGeometry().contains(QRect(rect.x(), rect.y(), rect.width() + 16, rect.height() + 40))


def test_settings_keeps_entry_context(window):
    window.navigate("settings")
    assert window.sidebar.isHidden()
    assert not window.settings_page.home_button.isHidden()
    window.settings_page.home_button.click()
    assert window.pages.currentWidget() is window.page_widgets["home"]
    window.navigate("records")
    window.navigate("settings")
    assert not window.sidebar.isHidden()
    assert window.settings_page.home_button.isHidden()


def test_controls_keep_40_dip_and_focus_does_not_change_size(window):
    window.start_formal_evaluation()
    app = QApplication.instance()
    app.processEvents()
    for widget in (window.gb29446_electricity, window.gb29446_raw_coal, window.gb29446_process, window.calculate_button):
        assert widget.height() == 40
        before = widget.size()
        widget.setFocus()
        app.processEvents()
        assert widget.size() == before
    text = "123456789.12345678901234567890123456789"
    window.gb29446_electricity.setText(text)
    window.gb29446_raw_coal.setFocus()
    assert window.gb29446_electricity.text() == text
    window.gb29446_electricity.clear()
    assert window.gb29446_electricity.text() == ""
    combo = window.gb29446_period
    combo.setFocus()
    previous = combo.currentIndex()
    QTest.keyClick(combo, Qt.Key.Key_Down)
    assert combo.currentIndex() != previous
    combo.showPopup()
    app.processEvents()
    index = combo.model().index(2, 0)
    QTest.mouseClick(combo.view().viewport(), Qt.MouseButton.LeftButton, pos=combo.view().visualRect(index).center())
    assert combo.currentIndex() == 2 and combo.height() == 40
    image = combo.grab().toImage()
    # 箭头位于右留白的中心区域，不把外框或业务文字当成可见箭头。
    ink = sum(image.pixelColor(x, y).lightness() < 220
              for x in range(image.width() - 26, image.width() - 8)
              for y in range(14, 26))
    assert ink > 8
    combo.setEnabled(False)
    QTest.keyClick(combo, Qt.Key.Key_Down)
    assert combo.currentIndex() == 2 and combo.height() == 40
    combo.setEnabled(True)
    assert window.navigation.visualItemRect(window.navigation.item(1)).height() == 46
    assert window.findChild(QPushButton, "sidebarSettings").height() == 46
    window.navigate("record_detail")
    app.processEvents()
    assert window.record_detail_page.tabs.tabBar().tabRect(0).height() == 36


def test_record_actions_follow_selection_and_refresh_failure(window, monkeypatch):
    window.navigate("records")
    assert not window.record_view_button.isEnabled()
    assert not window.record_delete_button.isEnabled()
    fill_and_calculate(window)
    window.navigate("records")
    window.record_table.selectRow(0)
    assert window.record_view_button.isEnabled() and window.record_delete_button.isEnabled()
    window.record_table.clearSelection()
    assert not window.record_view_button.isEnabled() and not window.record_delete_button.isEnabled()
    window.record_table.selectRow(0)
    monkeypatch.setattr(window.context.application, "query_evaluations", lambda **kw: (_ for _ in ()).throw(RuntimeError("read failed")))
    window.refresh_records()
    assert not window.record_view_button.isEnabled() and not window.record_delete_button.isEnabled()


def test_parameter_value_remains_editable_with_decimal_text(window, monkeypatch):
    from types import SimpleNamespace
    from uebench.domain.models import InputDefinition
    product = SimpleNamespace(input_definitions=[
        InputDefinition(key="amount", label="用电量", unit="kW·h"),
    ], indicators=[])
    monkeypatch.setattr(window, "_is_gb29446", lambda: False)
    monkeypatch.setattr(window, "_selected_product", lambda: product)
    window._refresh_input_table()
    table = window.eval_inputs
    assert table.item(0, 2).flags() & Qt.ItemFlag.ItemIsEditable
    for column in (0, 1, 3, 4):
        assert not table.item(0, column).flags() & Qt.ItemFlag.ItemIsEditable
    text = "123456789.12345678901234567890123456789"
    from PySide6.QtWidgets import QStyleOptionViewItem
    index = table.model().index(0, 2)
    delegate = table.itemDelegateForIndex(index)
    editor = delegate.createEditor(table.viewport(), QStyleOptionViewItem(), index)
    assert isinstance(editor, QLineEdit)
    QTest.keyClicks(editor, text)
    delegate.setModelData(editor, table.model(), index)
    assert table.item(0, 2).text() == text


def test_brand_rerenders_source_at_dpr(window, monkeypatch):
    label = window.findChildren(BrandLabel)[0]
    assert label._source.size().width() == 3060
    for dpr in (1.0, 1.5, 2.0):
        pixmap = label.pixmap_for_dpr(dpr)
        assert pixmap.width() == round(180 * dpr)
        assert pixmap.devicePixelRatioF() == dpr
        assert pixmap.deviceIndependentSize().width() == 180


def test_home_recent_rows_grow_for_long_chinese(window):
    fill_and_calculate(window)
    window.navigate("home")
    QApplication.processEvents()
    table = window.home_recent
    table.item(0, 0).setText("较长企业名称与保存时信息" * 12)
    table.fit_columns()
    QApplication.processEvents()
    assert table.rowHeight(0) > 48
    assert table.height() >= table.horizontalHeader().height() + table.rowHeight(0)


@pytest.mark.parametrize("title,action", [("确认删除", "删除记录"), ("确认恢复", "恢复并替换")])
def test_chinese_confirmation_preserves_safe_default(title, action):
    app = QApplication.instance() or QApplication([])
    box = QMessageBox()
    box.setWindowTitle(title)
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    box.setDefaultButton(QMessageBox.No)
    localize_buttons(box)
    assert box.button(QMessageBox.Yes).text() == action
    assert box.button(QMessageBox.No).text() == "取消"
    assert box.standardButton(box.defaultButton()) == QMessageBox.No
