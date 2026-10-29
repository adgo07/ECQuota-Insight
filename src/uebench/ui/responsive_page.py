"""业务正文只在外层增加弹性边距。"""
from PySide6.QtWidgets import QWidget


class ResponsivePage(QWidget):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.layout():
            margin = round(max(22, min(48, self.width() * .034)))
            self.layout().setContentsMargins(margin, 22, margin, 22)
