"""记录列表按可用宽度分配长文本列；窄窗保留表内横向滚动。"""
from PySide6.QtWidgets import QTableWidget


class RecordTable(QTableWidget):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_columns()

    def fit_columns(self):
        if self.columnCount() != 7:
            return
        widths = [160, 125, 210, 155, 100, 180, 88]
        spare = max(0, self.viewport().width() - sum(widths))
        widths[0] += spare // 3
        widths[2] += spare - spare // 3
        for column, width in enumerate(widths):
            if self.columnWidth(column) != width:
                self.setColumnWidth(column, width)
        self.resizeRowsToContents()
        for row in range(self.rowCount()):
            self.setRowHeight(row, max(60, self.rowHeight(row)))
