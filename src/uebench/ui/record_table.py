"""记录列表按可用宽度分配长文本列；窄窗保留表内横向滚动。"""
from PySide6.QtCore import Qt, QRect
from PySide6.QtWidgets import QTableWidget


class ResponsiveTable(QTableWidget):
    minimum_widths = ()
    width_weights = ()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("compactBusinessTable")
        self.setStyleSheet("""
            QTableWidget#compactBusinessTable { font-size: 13px; }
            QTableWidget#compactBusinessTable::item { padding: 6px; }
            QTableWidget#compactBusinessTable QHeaderView::section { font-size: 13px; padding: 8px 6px; }
            QTableWidget#compactBusinessTable QPushButton { font-size: 13px; padding: 6px 12px; }
        """)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_columns()

    def fit_columns(self):
        if self.columnCount() != len(self.minimum_widths):
            return
        widths = list(self.minimum_widths)
        spare = max(0, self.viewport().width() - sum(widths))
        remaining = spare
        for i, weight in enumerate(self.width_weights):
            share = spare * weight // sum(self.width_weights)
            widths[i] += share
            remaining -= share
        widths[1] += remaining
        for column, width in enumerate(widths):
            if self.columnWidth(column) != width:
                self.setColumnWidth(column, width)
        self.resizeRowsToContents()
        for row in range(self.rowCount()):
            height = max(44, self.rowHeight(row))
            # Qt 的默认 sizeHint 会省略长中文的末行；按实际列宽测量完整正文。
            for column in range(self.columnCount()):
                item = self.item(row, column)
                if item:
                    rect = self.fontMetrics().boundingRect(
                        QRect(0, 0, max(1, widths[column] - 16), 100000),
                        Qt.TextFlag.TextWordWrap, item.text(),
                    )
                    height = max(height, rect.height() + 16)
            self.setRowHeight(row, height)


class RecordTable(ResponsiveTable):
    minimum_widths = (125, 96, 230, 94, 72, 160, 88)
    width_weights = (2, 0, 6, 0, 0, 0, 0)


class StandardTable(ResponsiveTable):
    minimum_widths = (125, 320, 120, 92, 165)
    width_weights = (1, 7, 1, 1, 3)
