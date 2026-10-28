"""仅保存窗口偏好，不参与业务恢复或正式记录。"""
from PySide6.QtCore import QRect, QSettings, QTimer, Qt
from PySide6.QtWidgets import QApplication


def bounded_rect(rect, available, frame_width=0, frame_height=0):
    width = min(rect.width(), max(1, available.width() - frame_width))
    height = min(rect.height(), max(1, available.height() - frame_height))
    return QRect(
        max(available.left(), min(rect.x(), available.right() - width - frame_width + 1)),
        max(available.top(), min(rect.y(), available.bottom() - height - frame_height + 1)),
        width, height,
    )


class WindowPlacement:
    def __init__(self, window, data_root):
        self.window = window
        self.settings = QSettings(str(data_root / "window.ini"), QSettings.Format.IniFormat)
        self.connected = False
        screen = window.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry()
        saved = self.settings.value("window/normal")
        restored = isinstance(saved, QRect) and saved.width() > 0 and saved.height() > 0
        if restored:
            matching = [s for s in QApplication.screens() if s.availableGeometry().intersects(saved)]
            def overlap(candidate):
                part = candidate.availableGeometry().intersected(saved)
                return part.width() * part.height()
            available = (max(matching, key=overlap) if matching else screen).availableGeometry()
            rect = bounded_rect(saved, available, 16, 40)
        else:
            rect = bounded_rect(QRect(0, 0, 1280, 800), available, 16, 40)
            rect.moveCenter(available.center())
        window.setMinimumSize(min(960, rect.width()), min(600, rect.height()))
        window.setGeometry(rect)
        if restored and self.settings.value("window/maximized", False, type=bool):
            window.setWindowState(window.windowState() | Qt.WindowState.WindowMaximized)

    def shown(self):
        if not self.connected:
            self.connected = True
            self.window.windowHandle().screenChanged.connect(self.constrain)
            QApplication.instance().screenRemoved.connect(self.constrain)
            for screen in QApplication.screens():
                screen.availableGeometryChanged.connect(self.constrain)
        QTimer.singleShot(0, self.constrain)

    def constrain(self, *_):
        window = self.window
        screen = window.screen() or QApplication.primaryScreen()
        area = screen.availableGeometry()
        frame = window.frameGeometry()
        geometry = window.geometry()
        dw, dh = max(0, frame.width() - geometry.width()), max(0, frame.height() - geometry.height())
        window.setMinimumSize(min(960, max(1, area.width() - dw)), min(600, max(1, area.height() - dh)))
        if window.isMaximized() or window.isMinimized():
            return
        # 用外框原点约束，再转换回客户区坐标，标题栏与系统边框都留在工作区。
        result = bounded_rect(QRect(frame.topLeft(), geometry.size()), area, dw, dh)
        result.translate(geometry.topLeft() - frame.topLeft())
        if result != geometry:
            window.setGeometry(result)

    def save(self):
        window = self.window
        rect = window.normalGeometry() if window.isMaximized() or window.isMinimized() else window.geometry()
        self.settings.setValue("window/normal", rect)
        self.settings.setValue("window/maximized", window.isMaximized())
        self.settings.sync()
