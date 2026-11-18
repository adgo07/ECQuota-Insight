"""原始能流明细录入；所有算术由Domain执行。"""
from uuid import uuid4
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QCheckBox, QLabel
from .wheel_safe_combo import WheelSafeComboBox
from uebench.domain.coke_flows import CokeFlow, COMPONENTS, REFERENCES, FUEL_IDS, STEAM_IDS
from uebench.domain.gb21342 import LABELS
from uebench.domain.coke_reference import SATURATED_STEAM, SUPERHEATED_STEAM


class CokeFlowsForm(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        body = QVBoxLayout(self)
        hint = QLabel("干洗精煤、干全焦采用附录A；其他燃料可选实测有效系数或收到基低位热值，蒸汽可选实测热焓，三种渠道互斥；未填时采用表列参考。蒸汽查表使用绝对压力，每股能流只计一次。驰/弛放气对应关系待确认，暂不自动提供表列系数；请选其他并填写有效系数及来源。")
        hint.setWordWrap(True)
        body.addWidget(hint)
        self.table = QTableWidget(0, 14)
        self.table.setHorizontalHeaderLabels(["分量", "能源/工质", "数量", "单位", "实测系数", "系数单位", "实测来源", "绝对压力（MPa）", "温度（℃）", "压力基准", "蒸汽表列节点", "实测收到基低位热值", "热值单位", "实测蒸汽热焓（kJ/kg）"])
        self.table.setColumnWidth(10, 215)
        for col in (11, 12, 13):
            self.table.setColumnWidth(col, 175)
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
                             (1, [(v[0], k) for k, v in REFERENCES.items()] + [("饱和蒸汽", "saturated_steam"), ("过热蒸汽", "superheated_steam"), ("其他燃料（实测热值或系数）", "other_fuel"), ("其他（需有效系数）", "other"), ("已折标能流", "standard_coal")]),
                             (3, [(u, u) for u in ("kg", "t", "m³", "kWh", "MWh", "MJ", "GJ", "kgce", "tce")]),
                             (9, [("绝对压力", "absolute"), ("表压（不能查表）", "gauge")]),
                             (12, [("选择单位", None), ("kJ/kg", "kJ/kg"), ("kJ/m³", "kJ/m³")])):
            combo = WheelSafeComboBox()
            for label, value in options:
                combo.addItem(label, value)
            combo.currentIndexChanged.connect(lambda *_: self.changed.emit())
            self.table.setCellWidget(row, col, combo)
        for col in (2, 4, 5, 6, 7, 8, 11, 13):
            self.table.setItem(row, col, QTableWidgetItem(""))
        nodes = WheelSafeComboBox()
        nodes.setAccessibleName("蒸汽表列节点")
        self.table.setCellWidget(row, 10, nodes)
        energy = self.table.cellWidget(row, 1)
        def choose_node(index):
            node = nodes.itemData(index)
            row = next((r for r in range(self.table.rowCount()) if self.table.cellWidget(r, 10) is nodes), -1)
            if node is not None and row >= 0:
                self.table.item(row, 7).setText(node[0])
                self.table.item(row, 8).setText(node[1])
                self.table.cellWidget(row, 9).setCurrentIndex(0)
                nodes.setCurrentIndex(0)
        def update_nodes():
            nodes.blockSignals(True)
            nodes.clear()
            nodes.addItem("填入表列节点…", None)
            table = {"saturated_steam":SATURATED_STEAM, "superheated_steam":SUPERHEATED_STEAM}.get(energy.currentData(), ())
            for p, t, _, _ in table:
                nodes.addItem(f"{p} MPa / {t} ℃", (p, t))
            nodes.setEnabled(bool(table))
            nodes.blockSignals(False)
        nodes.currentIndexChanged.connect(choose_node)
        energy.currentIndexChanged.connect(update_nodes)
        def update_measurements():
            row = next((r for r in range(self.table.rowCount()) if self.table.cellWidget(r, 1) is energy), -1)
            if row < 0:
                return
            kind = energy.currentData()
            fixed = kind in {"dry_clean_coal", "dry_coke", "standard_coal"}
            enabled = {4: not fixed, 5: not fixed, 6: not fixed, 11: kind in FUEL_IDS, 13: kind in STEAM_IDS}
            for col, active in enabled.items():
                item = self.table.item(row, col)
                if not active:
                    item.setText("")
                flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled
                item.setFlags(flags if active else Qt.NoItemFlags)
            self.table.cellWidget(row, 12).setEnabled(kind in FUEL_IDS)
            if kind not in FUEL_IDS:
                self.table.cellWidget(row, 12).setCurrentIndex(0)
        energy.currentIndexChanged.connect(update_measurements)
        update_nodes()
        update_measurements()
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
                text(4), text(5), text(6) or "", text(7), text(8), choice(9),
                text(11), choice(12), text(13)))
        return rows, tuple(key for key, box in self.zeros.items() if box.isChecked())
