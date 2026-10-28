"""只本地化本窗口的消息按钮，保留 Qt 标准返回值。"""
from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QApplication, QMessageBox


class ChineseMessageButtons(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Show and isinstance(watched, QMessageBox):
            parent = watched.parentWidget()
            if parent is self.window or (parent is not None and self.window.isAncestorOf(parent)):
                localize_buttons(watched)
        return super().eventFilter(watched, event)


def localize_buttons(box):
    for code, label in (
        (QMessageBox.StandardButton.Ok, "确定"),
        (QMessageBox.StandardButton.Yes, "删除记录" if box.windowTitle() == "确认删除" else "恢复并替换" if box.windowTitle() == "确认恢复" else "继续"),
        (QMessageBox.StandardButton.No, "取消"),
        (QMessageBox.StandardButton.Cancel, "取消"),
    ):
        button = box.button(code)
        if button:
            button.setText(label)
