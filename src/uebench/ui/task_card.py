"""键盘可操作的任务卡；标题与说明独立排版，业务动作仍由调用方接线。"""
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QIcon
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget, QGridLayout


class IconLabel(QLabel):
    def __init__(self, icon):
        super().__init__()
        self.icon = icon
        self.setFixedSize(24, 24)

    def paintEvent(self, event):
        painter = QPainter(self)
        self.icon.paint(painter, QRect(0, 0, 24, 24), Qt.AlignmentFlag.AlignCenter,
                        QIcon.Mode.Normal if self.isEnabled() else QIcon.Mode.Disabled)


class TaskCard(QPushButton):
    def __init__(self, title, description, icon, *, emphasized=False):
        super().__init__()
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)
        self.setProperty("role", "task")
        if emphasized:
            self.setObjectName("standardTask")
        body = QVBoxLayout(self)
        body.setContentsMargins(22, 22, 22, 22)
        body.setSpacing(10)
        image = IconLabel(icon)
        heading = QLabel(title)
        heading.setProperty("class", "taskTitle")
        detail = QLabel(description)
        detail.setProperty("class", "taskDescription")
        for label in (image, heading, detail):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            label.setWordWrap(True)
            body.addWidget(label)
        body.addStretch()
        self.setMinimumHeight(172)


class TaskCardGrid(QWidget):
    def __init__(self):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(16)
        self.cards = []
        self.columns = 0

    def add_card(self, card):
        self.cards.append(card)
        self.columns = 0
        self._reflow()

    def _reflow(self):
        columns = 5 if self.width() >= 1100 else 3 if self.width() >= 750 else 2
        if columns == self.columns:
            return
        self.columns = columns
        for card in self.cards:
            self.grid.removeWidget(card)
        for index, card in enumerate(self.cards):
            self.grid.addWidget(card, index // columns, index % columns)
        for column in range(5):
            self.grid.setColumnStretch(column, (147 if column == 0 else 100) if columns == 5 else 1 if column < columns else 0)
        rows = (len(self.cards) + columns - 1) // columns
        self.setMinimumHeight(rows * 174 + max(0, rows - 1) * 16)
        self.updateGeometry()

    def resizeEvent(self, event):
        self._reflow()
        super().resizeEvent(event)
