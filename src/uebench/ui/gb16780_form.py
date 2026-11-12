"""水泥原始明细表单；熟料配比辅助输入复用Domain。"""
from datetime import date
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QListWidget, QListWidgetItem, QAbstractItemView, QTextEdit,
)
from .wheel_safe_combo import WheelSafeComboBox as QComboBox
from uebench.application.gb16780 import MODE_LABELS
from uebench.application.gb29446 import GB29446_PERIOD_OPTIONS, encode_period_notes, decode_period_notes
from uebench.domain.gb16780 import (
    INPUTS, DEDUCTIONS, PRODUCT_ID, STANDARD_ID, RATIO_MODES,
    NodeError, clinker_ratio, clinker_ratio_warning,
)
from uebench.domain.models import (
    CementFuelInput, CementLineInput, CementSharedEnergy, EvaluationRequest, InputMode, InputValue,
)


def mode_keys(mode):
    if mode == "purchased_clinker_grinding":
        return {"cement.production_t", "cement.preparation_electricity_kwh"}
    return {k for k in INPUTS if not (mode == "clinker_only" and k.startswith("cement."))}


class FieldGroup(QGroupBox):
    def __init__(self, title, keys, changed):
        super().__init__(title)
        self.grid = QGridLayout(self)
        self.grid.setHorizontalSpacing(24)
        self.grid.setVerticalSpacing(10)
        self.fields, self.labels = {}, {}
        self.active = set(keys)
        self.columns = 0
        for key in keys:
            label, unit, _ = INPUTS[key]
            if key == "site.pressure_pa":
                label += "（海拔>1500m时填写）"
            elif key not in DEDUCTIONS:
                label += " *"
            self.labels[key] = QLabel(f"{label}（{unit.replace('kWh', 'kW·h')}）")
            self.labels[key].setWordWrap(True)
            field = QLineEdit()
            field.setObjectName("cement_" + key.replace(".", "_"))
            if key in DEDUCTIONS:
                field.setPlaceholderText("若已扣除，则不填")
            field.textChanged.connect(lambda *_: changed())
            self.fields[key] = field
        self.reflow(1)

    def show_keys(self, keys):
        self.active = set(self.fields) & set(keys)
        self.reflow(self.columns or 1)
        self.setVisible(bool(self.active))

    def reflow(self, columns):
        self.columns = columns
        for key in self.fields:
            for widget in (self.labels[key], self.fields[key]):
                self.grid.removeWidget(widget)
                widget.setVisible(key in self.active)
        for index, key in enumerate(k for k in self.fields if k in self.active):
            row, col = divmod(index, columns)
            self.grid.addWidget(self.labels[key], row * 2, col)
            self.grid.addWidget(self.fields[key], row * 2 + 1, col)
        for col in range(2):
            self.grid.setColumnStretch(col, 1 if col < columns else 0)
        self.setMinimumHeight(self.grid.sizeHint().height())

    def resizeEvent(self, event):
        columns = 2 if self.width() >= 700 else 1
        if columns != self.columns:
            self.reflow(columns)
        super().resizeEvent(event)


class FuelTable(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        body = QVBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["燃料名称", "消耗量（kg）", "低位发热量（kJ/kg）"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setMinimumHeight(150)
        self.table.setMaximumHeight(250)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemChanged.connect(lambda *_: self.changed.emit())
        body.addWidget(self.table)
        actions = QHBoxLayout()
        add, remove = QPushButton("添加燃料"), QPushButton("移除所选燃料")
        add.clicked.connect(lambda: self.add())
        remove.clicked.connect(self.remove)
        actions.addWidget(add)
        actions.addWidget(remove)
        actions.addStretch()
        body.addLayout(actions)

    def add(self, fuel=None):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, value in enumerate((fuel.energy_name, fuel.mass_kg, fuel.low_calorific_value_kj_per_kg) if fuel else ("", "", "")):
            item = QTableWidgetItem("" if value is None else str(value))
            if col == 0:
                item.setData(Qt.ItemDataRole.UserRole, fuel.line_id if fuel else uuid4().hex)
            self.table.setItem(row, col, item)
        self.changed.emit()

    def remove(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self.changed.emit()

    def collect(self):
        result = []
        for row in range(self.table.rowCount()):
            items = [self.table.item(row, col) for col in range(3)]
            text = [item.text().strip() if item else "" for item in items]
            # 用户确实添加但没填的一行保留缺失，不自动当成0。
            result.append(CementFuelInput(line_id=items[0].data(Qt.ItemDataRole.UserRole), energy_name=text[0] or "燃料",
                mass_kg=text[1] or None, low_calorific_value_kj_per_kg=text[2] or None))
        return result


class CementLineForm(QWidget):
    changed = Signal()
    removed = Signal(object)

    def __init__(self, number=1, line_id=None):
        super().__init__()
        self.line_id = line_id or uuid4().hex
        self._loading = False
        body = QVBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self.name = QLineEdit(f"生产线{number}")
        self.name.setPlaceholderText("生产线名称")
        self.mode = QComboBox()
        for key, label in MODE_LABELS.items():
            self.mode.addItem(label, key)
        remove = QPushButton("移除此线")
        remove.clicked.connect(lambda: self.removed.emit(self))
        header.addWidget(self.name, 1)
        header.addWidget(self.mode, 2)
        header.addWidget(remove)
        body.addLayout(header)
        keygroups = (
            ("产量与修正", ("clinker.production_t", "cement.production_t", "cement.clinker_consumption_t", "cement.clinker_percent", "site.altitude_m", "site.pressure_pa")),
            ("熟料燃料参数", ("fuel.standard_coal_heat_kj_per_kgce",)),
            ("熟料用电与余热", ("clinker.electricity_kwh", "heat.generation_kwh", "heat.own_use_kwh")),
            ("窑系统分项扣除", DEDUCTIONS),
            ("水泥生产", tuple(k for k in INPUTS if k.startswith("cement.") and k not in {"cement.production_t", "cement.clinker_consumption_t", "cement.clinker_percent"})),
        )
        self.groups, self.fields = [], {}
        for title, keys in keygroups:
            group = FieldGroup(title, keys, self.changed.emit)
            self.groups.append(group)
            self.fields.update(group.fields)
            body.addWidget(group)
        self.ratio_controls = QWidget()
        ratio_layout = QVBoxLayout(self.ratio_controls)
        ratio_layout.setContentsMargins(0, 0, 0, 0)
        self.ratio_mode = QComboBox()
        self.ratio_mode.addItem("熟料配比：按消耗量和水泥产量自动计算", "automatic")
        self.ratio_mode.addItem("熟料配比：手工输入", "manual")
        self.ratio_notice = QLabel()
        self.ratio_notice.setWordWrap(True)
        ratio_layout.addWidget(self.ratio_mode)
        ratio_layout.addWidget(self.ratio_notice)
        body.insertWidget(2, self.ratio_controls)
        self.ratio_mode.currentIndexChanged.connect(self._refresh_ratio)
        for key in ("cement.production_t", "cement.clinker_consumption_t", "cement.clinker_percent"):
            self.fields[key].textChanged.connect(self._refresh_ratio)
        self.fuels = FuelTable()
        self.groups[1].grid.addWidget(self.fuels, 2, 0, 1, 2)
        self.fuels.changed.connect(self.changed.emit)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.name.textChanged.connect(lambda *_: self.changed.emit())
        self._mode_changed()

    def _mode_changed(self):
        keys = mode_keys(self.mode.currentData())
        for group in self.groups:
            group.show_keys(keys)
        self._refresh_ratio()
        self.changed.emit()

    def _refresh_ratio(self, *_):
        if self._loading:
            return
        applicable = self.mode.currentData() in RATIO_MODES
        self.ratio_controls.setVisible(applicable)
        automatic = self.ratio_mode.currentData() == "automatic"
        field = self.fields["cement.clinker_percent"]
        field.setReadOnly(automatic)
        if not applicable:
            self.ratio_notice.clear()
        elif automatic:
            inputs = {k: InputValue(value=self.fields[k].text().strip(), unit=INPUTS[k][1])
                      for k in ("cement.production_t", "cement.clinker_consumption_t")}
            try:
                text = str(clinker_ratio(inputs))
                notice = "按生产水泥消耗的熟料总量÷水泥总产量×100计算。"
            except NodeError as exc:
                text, notice = "", str(exc)
            field.blockSignals(True)
            field.setText(text)
            field.blockSignals(False)
            self.ratio_notice.setText(notice)
        else:
            self.ratio_notice.setText(clinker_ratio_warning(self.collect()) or "")
        self.changed.emit()

    def collect(self):
        mode = self.mode.currentData()
        return CementLineInput(line_id=self.line_id, line_name=self.name.text().strip() or "生产线",
            production_mode=mode, clinker_ratio_mode=self.ratio_mode.currentData(),
            inputs={k: InputValue(value=self.fields[k].text().strip(), unit=INPUTS[k][1])
                for k in mode_keys(mode) if self.fields[k].text().strip()},
            fuels=self.fuels.collect() if mode != "purchased_clinker_grinding" else [])

    def load(self, line):
        self._loading = True
        self.name.setText(line.line_name)
        self.mode.setCurrentIndex(self.mode.findData(line.production_mode))
        # 加载原始值，无论来自哪一代请求都不静默重算；切回自动由用户明确选择。
        self.ratio_mode.setCurrentIndex(self.ratio_mode.findData("manual"))
        for field in self.fields.values():
            field.clear()
        self.fuels.table.setRowCount(0)
        for key, value in line.inputs.items():
            if key in self.fields:
                self.fields[key].setText("" if value.value is None else str(value.value))
        for fuel in line.fuels:
            self.fuels.add(fuel)
        self._loading = False
        self._refresh_ratio()


class SharedEnergyForm(QGroupBox):
    changed = Signal()
    removed = Signal(object)

    def __init__(self, lines, shared=None):
        super().__init__("共用系统用量")
        self.shared_id = shared.shared_id if shared else uuid4().hex
        self.lines = lines
        body = QVBoxLayout(self)
        top = QHBoxLayout()
        self.target = QComboBox()
        for key, label in (("clinker_electricity", "熟料综合用电"), ("clinker_fuel", "熟料原始燃料"), ("cement_auxiliary", "水泥辅助用电"), ("cement_preparation", "水泥制备工段用电")):
            self.target.addItem(label, key)
        remove = QPushButton("移除此共用量")
        remove.clicked.connect(lambda: self.removed.emit(self))
        top.addWidget(self.target, 1)
        top.addWidget(remove)
        body.addLayout(top)
        self.participants = QListWidget()
        self.participants.setMaximumHeight(130)
        self.participants.setMinimumHeight(85)
        body.addWidget(QLabel("参与生产线（按相应产品产量分摊）"))
        body.addWidget(self.participants)
        self.amount_label = QLabel("共用电量（kW·h）")
        self.amount = QLineEdit()
        self.fuels = FuelTable()
        body.addWidget(self.amount_label)
        body.addWidget(self.amount)
        body.addWidget(self.fuels)
        self.target.currentIndexChanged.connect(self.refresh_lines)
        self.amount.textChanged.connect(lambda *_: self.changed.emit())
        self.participants.itemChanged.connect(lambda *_: self.changed.emit())
        self.fuels.changed.connect(self.changed.emit)
        if shared:
            self.target.setCurrentIndex(self.target.findData(shared.target))
            if shared.amount:
                self.amount.setText("" if shared.amount.value is None else str(shared.amount.value))
            for fuel in shared.fuels:
                self.fuels.add(fuel)
        self.refresh_lines(selected=set(shared.line_ids) if shared else set())

    def refresh_lines(self, _index=0, selected=None):
        if selected is None:
            selected = {self.participants.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.participants.count()) if self.participants.item(i).checkState() == Qt.CheckState.Checked}
        self.participants.blockSignals(True)
        self.participants.clear()
        clinker = self.target.currentData() in {"clinker_fuel", "clinker_electricity"}
        for line in self.lines():
            mode = line.mode.currentData()
            if (clinker and mode == "purchased_clinker_grinding") or (not clinker and mode == "clinker_only"):
                continue
            item = QListWidgetItem(line.name.text() or "生产线")
            item.setData(Qt.ItemDataRole.UserRole, line.line_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if line.line_id in selected else Qt.CheckState.Unchecked)
            self.participants.addItem(item)
        self.participants.blockSignals(False)
        fuel = self.target.currentData() == "clinker_fuel"
        self.fuels.setVisible(fuel)
        self.amount.setVisible(not fuel)
        self.amount_label.setVisible(not fuel)
        self.changed.emit()

    def collect(self):
        ids = [self.participants.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.participants.count()) if self.participants.item(i).checkState() == Qt.CheckState.Checked]
        if not ids:
            raise ValueError("请选择共用系统参与生产线。")
        fuel = self.target.currentData() == "clinker_fuel"
        return CementSharedEnergy(shared_id=self.shared_id, target=self.target.currentData(), line_ids=ids,
            amount=None if fuel else InputValue(value=self.amount.text().strip() or None, unit="kWh"),
            fuels=self.fuels.collect() if fuel else [])


class CementForm(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        body = QVBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self.organization = QLineEdit()
        self.organization.setPlaceholderText("企业名称（选填）")
        self.period = QComboBox()
        self.period.addItems(GB29446_PERIOD_OPTIONS)
        self.custom_period = QLineEdit()
        self.custom_period.setPlaceholderText("填写统计期")
        header.addWidget(self.organization, 2)
        header.addWidget(QLabel("统计期"))
        header.addWidget(self.period, 1)
        header.addWidget(self.custom_period, 1)
        body.addLayout(header)
        self.line_container = QVBoxLayout()
        self.shared_container = QVBoxLayout()
        body.addLayout(self.line_container)
        add = QPushButton("添加生产线")
        add.clicked.connect(lambda: self.add_line())
        body.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)
        body.addLayout(self.shared_container)
        shared = QPushButton("添加共用系统用量")
        shared.clicked.connect(lambda: self.add_shared())
        body.addWidget(shared, 0, Qt.AlignmentFlag.AlignLeft)
        hint = QLabel("熟料自产产量与生产水泥消耗的熟料量分别填写；共用量仅在共用系统中填写一次。")
        hint.setWordWrap(True)
        body.addWidget(hint)
        self.lines, self.shared = [], []
        self.organization.textChanged.connect(lambda *_: self.changed.emit())
        self.period.currentTextChanged.connect(self._period_changed)
        self.custom_period.textChanged.connect(lambda *_: self.changed.emit())
        self._period_changed()
        self.add_line()

    def _period_changed(self, *_):
        self.custom_period.setVisible(self.period.currentText() == "自定义")
        self.changed.emit()

    def add_line(self, line=None):
        widget = CementLineForm(len(self.lines) + 1, line.line_id if line else None)
        if line:
            widget.load(line)
        self.lines.append(widget)
        self.line_container.addWidget(widget)
        widget.changed.connect(self._line_changed)
        widget.removed.connect(self.remove_line)
        self._line_changed()
        return widget

    def remove_line(self, widget):
        self.lines.remove(widget)
        self.line_container.removeWidget(widget)
        widget.deleteLater()
        self._line_changed()

    def _line_changed(self):
        for shared in self.shared:
            shared.refresh_lines()
        self.changed.emit()

    def add_shared(self, value=None):
        widget = SharedEnergyForm(lambda: self.lines, value)
        self.shared.append(widget)
        self.shared_container.addWidget(widget)
        widget.changed.connect(self.changed.emit)
        widget.removed.connect(self.remove_shared)
        self.changed.emit()

    def remove_shared(self, widget):
        self.shared.remove(widget)
        self.shared_container.removeWidget(widget)
        widget.deleteLater()
        self.changed.emit()

    def collect(self, selection_mode):
        if not self.lines:
            raise ValueError("请至少添加一条生产线。")
        if self.period.currentText() == "自定义" and not self.custom_period.text().strip():
            self.custom_period.setFocus()
            raise ValueError("请填写自定义统计期。")
        return EvaluationRequest(evaluation_date=date.today(), standard_id=STANDARD_ID, product_id=PRODUCT_ID,
            selection_mode=selection_mode, input_mode=InputMode.DETAIL, inputs={},
            organization_name=self.organization.text().strip() or None,
            notes=encode_period_notes(self.period.currentText(), self.custom_period.text(), ""),
            cement_lines=[line.collect() for line in self.lines], cement_shared_energy=[shared.collect() for shared in self.shared])

    def load(self, request):
        for widget in self.lines + self.shared:
            widget.setParent(None)
            widget.deleteLater()
        self.lines, self.shared = [], []
        self.organization.setText(request.organization_name or "")
        code, custom, _ = decode_period_notes(request.notes)
        self.period.setCurrentText(code)
        self.custom_period.setText(custom)
        for line in request.cement_lines:
            self.add_line(line)
        for shared in request.cement_shared_energy:
            self.add_shared(shared)
