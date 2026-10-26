"""键盘可操作的任务卡；标题与说明独立排版，业务动作仍由调用方接线。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout


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
        image = QLabel()
        image.setPixmap(icon.pixmap(24, 24))
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
