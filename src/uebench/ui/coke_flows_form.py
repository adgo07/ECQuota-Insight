"""原始能流明细录入；所有算术由Domain执行。"""
from uuid import uuid4
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QCheckBox, QLabel
from .wheel_safe_combo import WheelSafeComboBox
from uebench.domain.coke_flows import CokeFlow, COMPONENTS, REFERENCES
from uebench.domain.gb21342 import LABELS


class CokeFlowsForm(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        body = QVBoxLayout(self)
        hint = QLabel("实测栏填写有效折标系数；留空采用表列参考。蒸汽压力为绝对压力。每股能流只计一次。")
        hint.setWordWrap(True)
        body.addWidget(hint)
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(["分量", "能源/工质", "数量", "单位", "实测系数", "系数单位", "系数来源", "绝对压力（MPa）", "温度（℃）", "压力基准"])
        self.table.setMinimumHeight(240)
        self.table.setMaximumHeight(360)
        self.table.itemChanged.connect(lambda *_: self.changed.emit())
        for col, width in enumerate((170, 185, 110, 85, 110, 100, 160, 120, 100, 100)):
            self.table.setColumnWidth(col, width)
        body.addWidget(self.table)
        actions = QHBoxLayout()
        add, remove = QPushButton("添加能流"), QPushButton("移除所选能流")
        add.clicked.connect(self.add)
        remove.clicked.connect(self.remove)
        actions.addWidget(add)
        actions.addWidget(remove)
        actions.addStretch()
        body.addLayout(actions)
        self.zeros = {}
        for key in COMPONENTS:
            box = QCheckBox(LABELS[key] + "无发生量（明确为0）")
            box.toggled.connect(lambda *_: self.changed.emit())
            self.zeros[key] = box
            body.addWidget(box)

    def add(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, options in ((0, [(LABELS[k], k) for k in COMPONENTS]),
                             (1, [(v[0], k) for k, v in REFERENCES.items()] + [("饱和蒸汽", "saturated_steam"), ("过热蒸汽", "superheated_steam"), ("其他（需有效系数）", "other"), ("已折标能流", "standard_coal")]),
                             (3, [(u, u) for u in ("kg", "t", "m³", "kWh", "MWh", "MJ", "GJ", "kgce", "tce")]),
                             (9, [("绝对压力", "absolute"), ("表压（不能查表）", "gauge")])):
            combo = WheelSafeComboBox()
            for label, value in options:
                combo.addItem(label, value)
            combo.currentIndexChanged.connect(lambda *_: self.changed.emit())
            self.table.setCellWidget(row, col, combo)
        for col in (2, 4, 5, 6, 7, 8):
            self.table.setItem(row, col, QTableWidgetItem(""))
        self.table.item(row, 2).setData(256, uuid4().hex)
        self.changed.emit()

    def remove(self):
        if self.table.currentRow() >= 0:
            self.table.removeRow(self.table.currentRow())
            self.changed.emit()

    def collect(self):
        rows = []
        for row in range(self.table.rowCount()):
            def text(col):
                return self.table.item(row, col).text().strip() or None
            def choice(col):
                return self.table.cellWidget(row, col).currentData()
            rows.append(CokeFlow(self.table.item(row, 2).data(256), choice(0), choice(1), text(2), choice(3),
                text(4), text(5), text(6) or "", text(7), text(8), choice(9)))
        return rows, tuple(key for key, box in self.zeros.items() if box.isChecked())
