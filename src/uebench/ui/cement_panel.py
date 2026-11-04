"""水泥明细录入与只读结果；计算、完整性与保存均交给 Application。"""
from __future__ import annotations

from datetime import date
from uuid import uuid4
from decimal import Decimal, InvalidOperation
from time import monotonic

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit)

from uebench.domain.models import EvaluationRequest, InputValue, InputMode
from uebench.application.gb29446 import encode_period_notes
from uebench.application.cement_reporting import build_cement_report_view, SCOPE_NOTE


class SharedAllocationEditor(QWidget):
    changed = Signal()
    removed = Signal(object)

    def __init__(self, definitions, targets, parent=None):
        super().__init__(parent)
        self.allocation_id = str(uuid4())
        self.definitions = definitions
        self.targets = targets
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        self.target = QComboBox()
        for product, keys in targets.items():
            for key in sorted(keys):
                definition = definitions[key]
                self.target.addItem(definition.label + f"（{definition.unit}）", (product, key))
        self.amount = QLineEdit()
        self.source = QLineEdit()
        form.addRow("分摊统计项", self.target)
        form.addRow("原始共用量", self.amount)
        form.addRow("来源", self.source)
        layout.addLayout(form)
        hint = QLabel("目标统计项原始值不含该共用分摊量；填写同产品各参与线的同期产量。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.lines = QTableWidget(0, 2)
        self.lines.setHorizontalHeaderLabels(["参与生产线", "同期产品产量（t）"])
        self.lines.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.lines.setMinimumHeight(110)
        layout.addWidget(self.lines)
        actions = QHBoxLayout()
        add = QPushButton("新增参与线")
        remove_line = QPushButton("删除所选线")
        remove = QPushButton("删除此共用系统")
        add.clicked.connect(self.add_line)
        remove_line.clicked.connect(self.remove_line)
        remove.clicked.connect(lambda: self.removed.emit(self))
        for button in (add, remove_line, remove):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.target.currentIndexChanged.connect(self.changed)
        self.amount.textChanged.connect(self.changed)
        self.source.textChanged.connect(self.changed)
        self.lines.itemChanged.connect(self.changed)
        self.add_line()

    def add_line(self, *_):
        row = self.lines.rowCount()
        self.lines.insertRow(row)
        for column in range(2):
            self.lines.setItem(row, column, QTableWidgetItem(""))
        self.changed.emit()

    def remove_line(self, *_):
        if self.lines.currentRow() >= 0:
            self.lines.removeRow(self.lines.currentRow())
            self.changed.emit()

    def collect(self, target_line):
        from uebench.domain.models import CementSharedAllocation
        productions = {}
        for row in range(self.lines.rowCount()):
            line, amount = [self.lines.item(row, col).text().strip() if self.lines.item(row, col) else "" for col in range(2)]
            if not line and not amount:
                continue
            if not line or not amount:
                raise ValueError("请完整填写共用系统参与生产线及同期产品产量。")
            if line in productions:
                raise ValueError("同一共用系统的参与生产线重复，请核对。")
            productions[line] = amount
        product, key = self.target.currentData()
        return CementSharedAllocation(allocation_id=self.allocation_id, product=product,
            target_input_key=key, target_line_id=target_line, original_amount=self.amount.text().strip() or None,
            unit=self.definitions[key].unit, line_production_t=productions,
            source_note=self.source.text().strip() or None)


class CementEvaluationPanel(QWidget):
    saved = Signal(str)
    export_requested = Signal(str)

    def __init__(self, application, parent=None):
        super().__init__(parent)
        self.application = application
        self.standard = None
        self.record_id = None
        self._busy = False
        self._last_started = float("-inf")
        self.fields = {}
        self.field_rows = {}
        self.allocations = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        basic = QFormLayout()
        self.organization = QLineEdit()
        self.organization.setPlaceholderText("可选填写")
        self.line = QLineEdit()
        self.period = QLineEdit()
        self.period.setPlaceholderText("例如：2026年")
        self.mode = QComboBox()
        basic.addRow("企业名称", self.organization)
        basic.addRow("生产线", self.line)
        basic.addRow("统计期", self.period)
        basic.addRow("生产模式", self.mode)
        layout.addLayout(basic)
        self.form = QFormLayout()
        layout.addLayout(self.form)
        self.fuel_heading = QLabel("熟料燃料明细")
        self.fuel_heading.setProperty("class", "sectionTitle")
        layout.addWidget(self.fuel_heading)
        self.fuels = QTableWidget(0, 4)
        self.fuels.setHorizontalHeaderLabels(["燃料名称", "消耗量（kg）", "低位发热量（kJ/kg）", "来源"])
        self.fuels.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.fuels.verticalHeader().setDefaultSectionSize(40)
        self.fuels.setMinimumHeight(140)
        layout.addWidget(self.fuels)
        self.fuel_actions = QWidget()
        fuel_actions = QHBoxLayout(self.fuel_actions)
        fuel_actions.setContentsMargins(0, 0, 0, 0)
        add = QPushButton("新增燃料")
        remove = QPushButton("删除所选燃料")
        add.clicked.connect(self.add_fuel)
        remove.clicked.connect(self.remove_fuel)
        fuel_actions.addWidget(add)
        fuel_actions.addWidget(remove)
        fuel_actions.addStretch()
        layout.addWidget(self.fuel_actions)
        allocation_toggle = QPushButton("共用系统分摊")
        allocation_toggle.setCheckable(True)
        self.allocation_container = QWidget()
        self.allocation_layout = QVBoxLayout(self.allocation_container)
        self.allocation_layout.setContentsMargins(0, 0, 0, 0)
        add_allocation = QPushButton("新增共用系统")
        add_allocation.clicked.connect(self.add_allocation)
        self.allocation_layout.addWidget(add_allocation, 0, Qt.AlignmentFlag.AlignLeft)
        self.allocation_container.hide()
        allocation_toggle.toggled.connect(self.allocation_container.setVisible)
        layout.addWidget(allocation_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.allocation_container)
        self.message = QLabel("")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.results = QTableWidget(0, 6)
        self.results.setHorizontalHeaderLabels(["指标", "实际值", "等级", "1级上限", "2级上限", "3级上限"])
        self.results.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results.verticalHeader().hide()
        self.results.verticalHeader().setDefaultSectionSize(40)
        self.results.setMinimumHeight(120)
        layout.addWidget(self.results)
        self.scope = QLabel(SCOPE_NOTE.replace("本报告", "本次评价"))
        self.scope.setWordWrap(True)
        layout.addWidget(self.scope)
        self.disclosures = QLabel("")
        self.disclosures.setWordWrap(True)
        layout.addWidget(self.disclosures)
        details_toggle = QPushButton("计算依据")
        details_toggle.setCheckable(True)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.hide()
        details_toggle.toggled.connect(self.details.setVisible)
        layout.addWidget(details_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.details)
        self.export_button = QPushButton("导出Word报告")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(lambda: self.export_requested.emit(self.record_id) if self.record_id else None)
        layout.addWidget(self.export_button, 0, Qt.AlignmentFlag.AlignRight)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        for field in (self.organization, self.line, self.period):
            field.textChanged.connect(self._invalidate)
        self.fuels.itemChanged.connect(self._invalidate)

    def set_standard(self, standard):
        from uebench.domain.gb16780 import PRODUCTION_MODES
        self.standard = standard
        self.mode.blockSignals(True)
        self.mode.clear()
        for key, label in PRODUCTION_MODES.items():
            self.mode.addItem(label, key)
        self.mode.blockSignals(False)
        self._mode_changed()

    def _mode_changed(self, *_):
        from uebench.domain.gb16780 import MODE_INPUT_KEYS, DEDUCTION_KEYS
        while self.form.rowCount():
            self.form.removeRow(0)
        self.fields.clear()
        self.field_rows.clear()
        self.fuels.setRowCount(0)
        for allocation in self.allocations[:]:
            self.remove_allocation(allocation)
        if self.standard is None:
            return
        product = self.standard.products[0]
        definitions = {field.key: field for field in product.input_definitions}
        for indicator in product.indicators:
            definitions.update({field.key: field for field in indicator.input_definitions})
        mode = self.mode.currentData()
        for key in MODE_INPUT_KEYS[mode]:
            if key in {"production_mode", "evaluation_period", "production_line_id"} or key not in definitions:
                continue
            definition = definitions[key]
            field = QLineEdit()
            field.setObjectName("cement_" + key)
            field.setPlaceholderText("若已扣除，则不填" if key in DEDUCTION_KEYS else "")
            label = definition.label + (f"（{definition.unit}）" if definition.unit else "")
            self.form.addRow(label, field)
            self.fields[key] = field
            field.textChanged.connect(self._invalidate)
        clinker = mode != "grinding_station"
        for widget in (self.fuel_heading, self.fuels, self.fuel_actions):
            widget.setVisible(clinker)
        if clinker:
            self.add_fuel()
        if "altitude_m" in self.fields:
            self.fields["altitude_m"].textChanged.connect(self._pressure_visibility)
        self._pressure_visibility()
        self._invalidate()

    def _pressure_visibility(self, *_):
        pressure = self.fields.get("pressure_pa")
        if pressure is None:
            return
        try:
            visible = Decimal(self.fields["altitude_m"].text()) > 1500
        except (InvalidOperation, KeyError):
            visible = False
        pressure.setVisible(visible)
        label = self.form.labelForField(pressure)
        if label:
            label.setVisible(visible)
        if not visible:
            pressure.clear()

    def _invalidate(self, *_):
        self.record_id = None
        self.export_button.setEnabled(False)
        self.results.setRowCount(0)
        self.details.clear()
        self.disclosures.clear()
        self.message.setText("数据已修改，请计算。")

    def add_fuel(self, *_):
        row = self.fuels.rowCount()
        self.fuels.insertRow(row)
        for column in range(4):
            self.fuels.setItem(row, column, QTableWidgetItem(""))
        self._invalidate()

    def remove_fuel(self, *_):
        if self.fuels.currentRow() >= 0:
            self.fuels.removeRow(self.fuels.currentRow())
            self._invalidate()

    def add_allocation(self, *_):
        from uebench.domain.gb16780 import ALLOCATION_TARGETS, MODE_INPUT_KEYS
        mode = self.mode.currentData()
        definitions = {d.key: d for d in self.standard.products[0].input_definitions}
        targets = {product: keys & set(MODE_INPUT_KEYS[mode]) for product, keys in ALLOCATION_TARGETS.items()}
        editor = SharedAllocationEditor(definitions, targets)
        editor.changed.connect(self._invalidate)
        editor.removed.connect(self.remove_allocation)
        self.allocations.append(editor)
        self.allocation_layout.addWidget(editor)
        self._invalidate()

    def remove_allocation(self, editor):
        self.allocations.remove(editor)
        self.allocation_layout.removeWidget(editor)
        editor.deleteLater()
        self._invalidate()

    def collect_request(self):
        from uebench.domain.gb16780 import STANDARD_ID, PRODUCT_ID
        from uebench.domain.models import CementDetails, CementFuelLine
        if not self.line.text().strip():
            self.line.setFocus()
            raise ValueError("请填写生产线。")
        if not self.period.text().strip():
            self.period.setFocus()
            raise ValueError("请填写统计期。")
        inputs = {"production_mode": InputValue(value=self.mode.currentData()),
                  "evaluation_period": InputValue(value=self.period.text().strip()),
                  "production_line_id": InputValue(value=self.line.text().strip())}
        definitions = {d.key: d for d in self.standard.products[0].input_definitions}
        for key, field in self.fields.items():
            # 仅当前模式、当前可见字段进入新请求；切换模式时旧控件和值已删除。
            if field.isHidden():
                continue
            text = field.text().strip()
            if text:
                inputs[key] = InputValue(value=text, unit=definitions[key].unit)
        fuels = []
        if self.mode.currentData() != "grinding_station":
            for row in range(self.fuels.rowCount()):
                values = [self.fuels.item(row, col).text().strip() if self.fuels.item(row, col) else "" for col in range(4)]
                if not any(values):
                    continue
                fuels.append(CementFuelLine(line_id=str(uuid4()), name=values[0] or f"燃料{row+1}",
                    amount_kg=values[1] or None, low_heat_kj_per_kg=values[2] or None, source_note=values[3] or None))
        return EvaluationRequest(evaluation_date=date.today(), standard_id=STANDARD_ID,
            product_id=PRODUCT_ID, input_mode=InputMode.DETAIL, inputs=inputs,
            organization_name=self.organization.text().strip() or None,
            project_name=self.line.text().strip(), notes=encode_period_notes("自定义", self.period.text().strip(), ""),
            cement_details=CementDetails(fuel_lines=fuels,
                shared_allocations=[editor.collect(self.line.text().strip()) for editor in self.allocations]))

    def calculate_and_save(self):
        now = monotonic()
        if self._busy or now - self._last_started < 0.7:
            return
        self._last_started = now
        self._busy = True
        self.record_id = None
        self.export_button.setEnabled(False)
        try:
            request = self.collect_request()
            result, saved = self.application.evaluate_or_preview(request)
            view = build_cement_report_view(request, result, self.standard, formal=False)
            self.results.setRowCount(len(view.indicators))
            for row, indicator in enumerate(view.indicators):
                limits = {field.key: field.value for field in indicator.thresholds}
                values = (indicator.label + f"（{indicator.unit}）", indicator.actual, indicator.grade,
                          *(limits.get(key, "—") for key in ("LEVEL_1", "LEVEL_2", "LEVEL_3")))
                for column, value in enumerate(values):
                    self.results.setItem(row, column, QTableWidgetItem(value))
            self.results.resizeRowsToContents()
            self.disclosures.setText("\n".join(view.disclosures))
            self.details.setPlainText("\n".join([*(f"{f.label}：{f.value} {f.unit}" for f in view.calculations), *view.basis]))
            self.record_id = result.evaluation_id if saved else None
            self.message.setText("已保存对标记录。再次计算将生成新记录。" if saved else "部分计算预览，适用指标尚未完整，未保存。")
            self.export_button.setEnabled(saved)
            if saved:
                self.saved.emit(result.evaluation_id)
        except (ValueError, TypeError, LookupError) as exc:
            self.message.setText(str(exc))
        finally:
            self._busy = False
