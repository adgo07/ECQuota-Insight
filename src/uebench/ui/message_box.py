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
    labels = [
        (QMessageBox.StandardButton.Ok, "确定"),
        (QMessageBox.StandardButton.No, "取消(&N)"),
        (QMessageBox.StandardButton.Cancel, "取消"),
    ]
    action = {"确认删除": "删除记录(&Y)", "确认恢复": "恢复并替换(&Y)"}.get(box.windowTitle())
    if action:
        labels.append((QMessageBox.StandardButton.Yes, action))
    # 未登记的 Yes 操作沿用应用译器，不能静默发明“继续”动作。
    for code, label in labels:
        button = box.button(code)
        if button:
            button.setText(label)
