"""只重排已有控件，保留输入、焦点和信号连接。"""
from PySide6.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QLabel, QSizePolicy


class ResponsiveFields(QWidget):
    def __init__(self, fields, parent=None):
        super().__init__(parent)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(24)
        self.grid.setVerticalSpacing(14)
        self.blocks = []
        self.labels = {}
        for text, field, wide in fields:
            block = QWidget()
            body = QVBoxLayout(block)
            body.setContentsMargins(0, 0, 0, 0)
            body.setSpacing(6)
            label = QLabel(text)
            label.setWordWrap(True)
            body.addWidget(label)
            body.addWidget(field)
            self.labels[field] = label
            self.blocks.append((block, wide))
        self.columns = 0
        self._reflow(2)

    def _reflow(self, columns):
        if columns == self.columns:
            return
        self.columns = columns
        for block, _ in self.blocks:
            self.grid.removeWidget(block)
        row = col = 0
        for block, wide in self.blocks:
            if wide and col:
                row += 1
                col = 0
            span = columns if wide else 1
            self.grid.addWidget(block, row, col, 1, span)
            col += span
            if col >= columns:
                row += 1
                col = 0
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1 if columns == 2 else 0)
        self.grid.activate()
        self.setMinimumHeight(self.grid.sizeHint().height())
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.updateGeometry()

    def resizeEvent(self, event):
        self._reflow(2 if self.width() >= 900 else 1)
        super().resizeEvent(event)
