from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from uebench.bootstrap import AppContext
from uebench.domain.models import (
    EnergyLine,
    EvaluationRequest,
    DataType,
    GRADE_LABELS,
    Grade,
    LifecycleStatus,
    InputMode,
    InputValue,
    StandardSelectionMode,
    ProductionLine,
    StandardDefinition,
)


APP_STYLE = """
QMainWindow, QWidget { background: #f4f7fb; color: #1f2937; font-size: 10pt; }
QListWidget#navigation { background: #17365d; color: white; border: none; padding: 12px 6px; }
QListWidget#navigation::item { padding: 12px 14px; margin: 2px 0; border-radius: 5px; }
QListWidget#navigation::item:selected { background: #2f75b5; }
QFrame.card { background: white; border: 1px solid #d9e2f3; border-radius: 8px; padding: 12px; }
QPushButton { background: #2f75b5; color: white; border: none; border-radius: 5px; padding: 7px 14px; }
QPushButton:hover { background: #245f94; }
QPushButton:disabled { background: #aebdca; }
QLineEdit, QComboBox, QDateEdit, QTextEdit, QTableWidget { background: white; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px; }
QHeaderView::section { background: #d9eaf7; color: #17365d; padding: 7px; border: none; border-bottom: 1px solid #9fbad0; font-weight: bold; }
QLabel[class="pageTitle"] { font-size: 18pt; font-weight: bold; color: #17365d; }
QLabel[class="metric"] { font-size: 24pt; font-weight: bold; color: #2f75b5; }
"""


def _item(value, *, align_right: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem("" if value is None else str(value))
    if align_right:
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.current_standard: StandardDefinition | None = None
        self.last_result_id: str | None = None
        self.pending_import_id: str | None = None
        self.setWindowTitle("单位产品能耗对标软件")
        self.resize(1280, 820)
        self.setMinimumSize(1080, 700)
        self.setStyleSheet(APP_STYLE)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setFixedWidth(190)
        self.pages = QStackedWidget()
        layout.addWidget(self.navigation)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(central)

        page_builders = [
            ("首页", self._build_home),
            ("标准库", self._build_standards),
            ("新建评价", self._build_evaluation),
            ("评价记录", self._build_records),
            ("Excel导入", self._build_import),
            ("系统维护", self._build_maintenance),
        ]
        for title, builder in page_builders:
            self.navigation.addItem(QListWidgetItem(title))
            self.pages.addWidget(builder())
        self.navigation.currentRowChanged.connect(self._page_changed)
        self.navigation.setCurrentRow(0)
        self.refresh_all()

    def _page(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        label = QLabel(title)
        label.setProperty("class", "pageTitle")
        layout.addWidget(label)
        return page, layout

    @staticmethod
    def _card() -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setProperty("class", "card")
        layout = QVBoxLayout(frame)
        return frame, layout

    def _build_home(self) -> QWidget:
        page, layout = self._page("首页")
        metrics = QHBoxLayout()
        self.home_standard_count = QLabel("0")
        self.home_evaluation_count = QLabel("0")
        self.home_package_version = QLabel("未安装")
        for title, widget in (
            ("已发布标准", self.home_standard_count),
            ("评价记录", self.home_evaluation_count),
            ("标准包", self.home_package_version),
        ):
            card, card_layout = self._card()
            card_layout.addWidget(QLabel(title))
            widget.setProperty("class", "metric")
            card_layout.addWidget(widget)
            metrics.addWidget(card)
        layout.addLayout(metrics)
        card, card_layout = self._card()
        card_layout.addWidget(QLabel("最近评价"))
        self.home_recent = QTableWidget(0, 4)
        self.home_recent.setHorizontalHeaderLabels(["时间", "标准", "单位/项目", "评价ID"])
        self._configure_table(self.home_recent)
        card_layout.addWidget(self.home_recent)
        layout.addWidget(card, 1)
        return page

    def _build_standards(self) -> QWidget:
        page, layout = self._page("标准库")
        controls = QHBoxLayout()
        self.standard_search = QLineEdit()
        self.standard_search.setPlaceholderText("按标准编号、名称或产品搜索")
        self.standard_search.textChanged.connect(self.refresh_standards)
        open_button = QPushButton("打开标准原文")
        open_button.clicked.connect(self.open_selected_standard)
        controls.addWidget(self.standard_search, 1)
        controls.addWidget(open_button)
        layout.addLayout(controls)
        self.standard_table = QTableWidget(0, 7)
        self.standard_table.setHorizontalHeaderLabels(["标准编号", "标准名称", "状态", "版本", "实施日期", "产品/工序数", "原文SHA-256"])
        self._configure_table(self.standard_table)
        self.standard_table.itemSelectionChanged.connect(self.refresh_standard_detail)
        layout.addWidget(self.standard_table, 1)
        self.standard_detail_label = QLabel("选择标准后查看指标、限额和原文依据")
        layout.addWidget(self.standard_detail_label)
        self.standard_indicator_table = QTableWidget(0, 9)
        self.standard_indicator_table.setHorizontalHeaderLabels(
            ["产品/工序", "指标", "单位", "1级限额", "2级限额", "3级限额", "适用条件/说明", "页码", "条款/表号"]
        )
        self._configure_table(self.standard_indicator_table)
        layout.addWidget(self.standard_indicator_table, 2)
        return page

    def _build_evaluation(self) -> QWidget:
        page, layout = self._page("新建评价")
        form_card, form_layout = self._card()
        form = QFormLayout()
        self.eval_selection_mode = QComboBox()
        self.eval_selection_mode.addItem("当前有效标准（自动）", StandardSelectionMode.CURRENT.value)
        self.eval_selection_mode.addItem("历史标准（需提示确认）", StandardSelectionMode.HISTORICAL.value)
        self.eval_selection_mode.addItem("尚未实施标准（仅预览）", StandardSelectionMode.FUTURE.value)
        self.eval_selection_mode.currentIndexChanged.connect(self.refresh_standard_combo)
        self.eval_standard = QComboBox()
        self.eval_standard.currentIndexChanged.connect(self._standard_changed)
        self.eval_standard_status = QLabel("评价日期自动读取今天")
        self.eval_product = QComboBox()
        self.eval_product.currentIndexChanged.connect(self._product_changed)
        self.eval_mode = QComboBox()
        self.eval_mode.addItem("直接录入实际值", InputMode.DIRECT.value)
        self.eval_mode.addItem("能源与产量明细计算", InputMode.DETAIL.value)
        self.eval_mode.currentIndexChanged.connect(self._refresh_input_table)
        self.eval_date = QDateEdit(QDate.currentDate())
        self.eval_date.setCalendarPopup(False)
        self.eval_date.setReadOnly(True)
        self.eval_date.setEnabled(False)
        self.eval_organization = QLineEdit()
        self.eval_project = QLineEdit()
        self.eval_notes = QLineEdit()
        form.addRow("标准选择方式", self.eval_selection_mode)
        form.addRow("标准", self.eval_standard)
        form.addRow("标准状态提示", self.eval_standard_status)
        form.addRow("产品/工序", self.eval_product)
        form.addRow("评价日期", self.eval_date)
        form.addRow("录入模式", self.eval_mode)
        form.addRow("单位名称", self.eval_organization)
        form.addRow("项目名称", self.eval_project)
        form.addRow("评价备注", self.eval_notes)
        form_layout.addLayout(form)
        layout.addWidget(form_card)

        self.input_tabs = QTabWidget()
        self.eval_inputs = QTableWidget(0, 5)
        self.eval_inputs.setHorizontalHeaderLabels(["键", "名称", "值", "单位", "说明"])
        self._configure_table(self.eval_inputs, editable=True)
        self.energy_table = QTableWidget(0, 10)
        self.energy_table.setHorizontalHeaderLabels(["行ID", "能源名称", "分类键", "方向", "实物量", "单位", "折标系数", "系数单位", "分摊比例", "备注"])
        self._configure_table(self.energy_table, editable=True)
        self.production_table = QTableWidget(0, 8)
        self.production_table.setHorizontalHeaderLabels(["行ID", "产品名称", "分类键", "产量", "单位", "折算系数", "合格", "备注"])
        self._configure_table(self.production_table, editable=True)
        self.input_tabs.addTab(self.eval_inputs, "标准输入")
        self.input_tabs.addTab(self.energy_table, "能源明细")
        self.input_tabs.addTab(self.production_table, "产量与分摊")
        layout.addWidget(self.input_tabs, 1)

        buttons = QHBoxLayout()
        add_energy = QPushButton("新增能源行")
        add_energy.clicked.connect(lambda: self._append_blank_row(self.energy_table, [str(uuid4())[:8], "", "", "input", "", "", "", "", "1", ""]))
        add_product = QPushButton("新增产量行")
        add_product.clicked.connect(lambda: self._append_blank_row(self.production_table, [str(uuid4())[:8], "", "", "", "t", "1", "是", ""]))
        calculate = QPushButton("计算并判级")
        calculate.clicked.connect(self.calculate_evaluation)
        buttons.addWidget(add_energy)
        buttons.addWidget(add_product)
        buttons.addStretch()
        buttons.addWidget(calculate)
        layout.addLayout(buttons)

        self.eval_results = QTableWidget(0, 14)
        self.eval_results.setHorizontalHeaderLabels(
            ["指标", "实际值", "单位", "1级基础", "2级基础", "3级基础", "1级修正", "2级修正", "3级修正", "判定", "警告", "依据页码", "条款/表号", "来源"]
        )
        self._configure_table(self.eval_results)
        self.eval_summary = QLabel("等级汇总：尚未计算")
        layout.addWidget(self.eval_summary)
        layout.addWidget(self.eval_results, 1)
        return page

    def _build_records(self) -> QWidget:
        page, layout = self._page("评价记录")
        controls = QHBoxLayout()
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self.refresh_records)
        copy_record = QPushButton("复制到新评价")
        copy_record.clicked.connect(self.copy_selected_record)
        recalculate = QPushButton("重新计算")
        recalculate.clicked.connect(self.recalculate_selected_record)
        export = QPushButton("导出Excel")
        export.clicked.connect(self.export_selected_record)
        delete = QPushButton("删除记录")
        delete.clicked.connect(self.delete_selected_record)
        controls.addWidget(refresh)
        controls.addWidget(copy_record)
        controls.addWidget(recalculate)
        controls.addStretch()
        controls.addWidget(export)
        controls.addWidget(delete)
        layout.addLayout(controls)
        self.record_table = QTableWidget(0, 7)
        self.record_table.setHorizontalHeaderLabels(["计算时间", "评价日期", "标准", "单位", "项目", "产品ID", "评价ID"])
        self._configure_table(self.record_table)
        layout.addWidget(self.record_table, 1)
        return page

    def _build_import(self) -> QWidget:
        page, layout = self._page("Excel导入")
        controls = QHBoxLayout()
        template = QPushButton("保存导入模板")
        template.clicked.connect(self.save_import_template)
        validate = QPushButton("选择并校验Excel")
        validate.clicked.connect(self.validate_import_workbook)
        self.import_commit_button = QPushButton("提交并计算")
        self.import_commit_button.setEnabled(False)
        self.import_commit_button.clicked.connect(self.commit_import)
        controls.addWidget(template)
        controls.addWidget(validate)
        controls.addStretch()
        controls.addWidget(self.import_commit_button)
        layout.addLayout(controls)
        self.import_status = QLabel("尚未选择文件")
        layout.addWidget(self.import_status)
        self.import_issues = QTableWidget(0, 4)
        self.import_issues.setHorizontalHeaderLabels(["级别", "工作表", "单元格", "问题"])
        self._configure_table(self.import_issues)
        layout.addWidget(self.import_issues, 1)
        return page

    def _build_maintenance(self) -> QWidget:
        page, layout = self._page("系统维护")
        controls = QHBoxLayout()
        package = QPushButton("安装标准包")
        package.clicked.connect(self.install_standard_package)
        package.setEnabled(self.context.application.has_package_service())
        scan_packages = QPushButton("扫描标准包目录")
        scan_packages.clicked.connect(self.discover_standard_packages)
        scan_packages.setEnabled(self.context.application.has_package_service())
        backup = QPushButton("创建备份")
        backup.clicked.connect(self.create_backup)
        restore = QPushButton("恢复备份")
        restore.clicked.connect(self.restore_backup)
        open_data = QPushButton("打开数据目录")
        open_data.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.context.paths.root))))
        controls.addWidget(package)
        controls.addWidget(scan_packages)
        controls.addWidget(backup)
        controls.addWidget(restore)
        controls.addStretch()
        controls.addWidget(open_data)
        layout.addLayout(controls)
        if not self.context.application.has_package_service():
            layout.addWidget(QLabel("未配置标准包公钥，安装标准包功能已禁用。"))
        self.audit_table = QTableWidget(0, 5)
        self.audit_table.setHorizontalHeaderLabels(["时间", "操作", "对象类型", "对象ID", "详情"])
        self._configure_table(self.audit_table)
        layout.addWidget(self.audit_table, 1)
        return page

    @staticmethod
    def _configure_table(table: QTableWidget, *, editable: bool = False) -> None:
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        if not editable:
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    @staticmethod
    def _append_blank_row(table: QTableWidget, values: list[str]) -> None:
        row = table.rowCount()
        table.insertRow(row)
        for column, value in enumerate(values):
            table.setItem(row, column, _item(value))

    def _page_changed(self, index: int) -> None:
        if index < 0:
            return
        self.pages.setCurrentIndex(index)
        if index == 0:
            self.refresh_home()
        elif index == 1:
            self.refresh_standards()
        elif index == 3:
            self.refresh_records()
        elif index == 5:
            self.refresh_audit()

    def refresh_all(self) -> None:
        self.refresh_home()
        self.refresh_standards()
        self.refresh_standard_combo()
        self.refresh_records()
        self.refresh_audit()

    def refresh_home(self) -> None:
        today = date.today()
        standards = self.context.application.list_current_standards(today)
        all_standards = self.context.application.list_all_standards()
        records = self.context.application.list_recent_evaluations(10)
        scoped_standards = [item for item in all_standards if item.lifecycle_status is not LifecycleStatus.OBSOLETE]
        self.home_standard_count.setText(f"{len(standards)}/{len(scoped_standards)}")
        self.home_evaluation_count.setText(str(len(records)))
        package_manifest = self.context.application.latest_package_manifest()
        self.home_package_version.setText(
            package_manifest.get("data_version", "未知") if package_manifest else "未安装"
        )
        self.home_recent.setRowCount(0)
        for record in records:
            row = self.home_recent.rowCount()
            self.home_recent.insertRow(row)
            values = [record.created_at, record.standard_number, record.organization_name or record.project_name or "", record.evaluation_id]
            for column, value in enumerate(values):
                self.home_recent.setItem(row, column, _item(value))

    def refresh_standards(self) -> None:
        query = self.standard_search.text().strip().lower() if hasattr(self, "standard_search") else ""
        standards = self.context.application.list_current_standards(date.today())
        self.standard_table.setRowCount(0)
        for standard in standards:
            haystack = f"{standard.number} {standard.title} {' '.join(p.name for p in standard.products)}".lower()
            if query and query not in haystack:
                continue
            row = self.standard_table.rowCount()
            self.standard_table.insertRow(row)
            values = [
                standard.number,
                standard.title,
                ("当前有效" if standard.is_effective_on(date.today()) else ("尚未实施" if standard.effective_date > date.today() else "历史/已替代")),
                standard.version,
                standard.effective_date,
                len(standard.products),
                standard.source_sha256,
            ]
            for column, value in enumerate(values):
                item = _item(value)
                item.setData(Qt.ItemDataRole.UserRole, standard.id)
                self.standard_table.setItem(row, column, item)
        self.refresh_standard_detail()

    def refresh_standard_detail(self) -> None:
        """Show the selected standard's products, limits and source citations."""
        if not hasattr(self, "standard_indicator_table"):
            return
        self.standard_indicator_table.setRowCount(0)
        row = self.standard_table.currentRow()
        selected_item = self.standard_table.item(row, 0) if row >= 0 else None
        standard_id = selected_item.data(Qt.ItemDataRole.UserRole) if selected_item else None
        standard = next(
            (item for item in self.context.application.list_current_standards(date.today()) if item.id == standard_id),
            None,
        )
        if standard is None:
            self.standard_detail_label.setText("选择标准后查看指标、限额和原文依据")
            return
        indicator_count = sum(len(product.indicators) for product in standard.products)
        self.standard_detail_label.setText(f"{standard.number}：{indicator_count} 个指标")

        def limit_value(expression):
            if expression is None:
                return "—"
            return expression.value if expression.op == "constant" else "公式/条件"

        for product in standard.products:
            for indicator in product.indicators:
                base = indicator.base_thresholds or indicator.thresholds
                references = indicator.source_references
                pages = ", ".join(str(reference.page) for reference in references)
                clauses = "; ".join(
                    filter(None, {reference.clause for reference in references} | {reference.table for reference in references})
                )
                notes = "；".join(indicator.notes)
                if indicator.applicability.op != "always":
                    notes = (notes + "；" if notes else "") + "存在适用条件"
                values = [
                    product.name,
                    indicator.name,
                    indicator.unit,
                    limit_value(base.level_1),
                    limit_value(base.level_2),
                    limit_value(base.level_3),
                    notes,
                    pages,
                    clauses,
                ]
                detail_row = self.standard_indicator_table.rowCount()
                self.standard_indicator_table.insertRow(detail_row)
                for column, value in enumerate(values):
                    self.standard_indicator_table.setItem(detail_row, column, _item(value))

    def _selection_mode(self) -> StandardSelectionMode:
        value = self.eval_selection_mode.currentData() if hasattr(self, "eval_selection_mode") else StandardSelectionMode.CURRENT.value
        return StandardSelectionMode(value or StandardSelectionMode.CURRENT.value)

    def _standards_for_selection(self) -> list[StandardDefinition]:
        return self.context.application.list_standards_for_selection(date.today(), self._selection_mode())

    def refresh_standard_combo(self) -> None:
        selected = self.eval_standard.currentData() if self.eval_standard.count() else None
        self.eval_standard.blockSignals(True)
        self.eval_standard.clear()
        for standard in self._standards_for_selection():
            self.eval_standard.addItem(f"{standard.number} {standard.title}", standard.id)
        if selected:
            index = self.eval_standard.findData(selected)
            if index >= 0:
                self.eval_standard.setCurrentIndex(index)
        self.eval_standard.blockSignals(False)
        self._standard_changed()

    def _standard_changed(self) -> None:
        standard_id = self.eval_standard.currentData()
        mode = self._selection_mode()
        self.current_standard = (
            self.context.application.get_standard_for_evaluation(standard_id, date.today(), mode)
            if standard_id else None
        )
        self.eval_product.blockSignals(True)
        self.eval_product.clear()
        if self.current_standard:
            product_name_counts = Counter(product.name for product in self.current_standard.products)
            for product in self.current_standard.products:
                display_name = product.name
                if product_name_counts[product.name] > 1:
                    indicator_names = "、".join(indicator.name for indicator in product.indicators)
                    display_name = f"{product.name}（指标：{indicator_names}）"
                self.eval_product.addItem(display_name, product.id)
            self.eval_date.setDate(QDate.currentDate())
            warning = self.current_standard.selection_warning(date.today())
            if warning:
                self.eval_standard_status.setText(f"{self.current_standard.number} {self.current_standard.title}；{warning}")
            else:
                self.eval_standard_status.setText(f"{self.current_standard.number} {self.current_standard.title}；当前有效")
        else:
            self.eval_standard_status.setText("当前选择方式下没有可用标准")
        self.eval_product.blockSignals(False)
        self._product_changed()

    def _product_changed(self) -> None:
        self._refresh_input_table()

    def _selected_product(self):
        if self.current_standard is None:
            return None
        product_id = self.eval_product.currentData()
        return next((product for product in self.current_standard.products if product.id == product_id), None)

    def _refresh_input_table(self) -> None:
        if not hasattr(self, "eval_inputs"):
            return
        product = self._selected_product()
        mode = InputMode(self.eval_mode.currentData())
        self.eval_inputs.setRowCount(0)
        if product is None:
            return
        definitions = {definition.key: definition for definition in product.input_definitions if mode in definition.modes}
        for indicator in product.indicators:
            definitions.update(
                {definition.key: definition for definition in indicator.input_definitions if mode in definition.modes}
            )
        for definition in definitions.values():
            row = self.eval_inputs.rowCount()
            self.eval_inputs.insertRow(row)
            values = [definition.key, definition.label, "", definition.unit or "", definition.description or ""]
            for column, value in enumerate(values):
                item = _item(value)
                if column != 2:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.eval_inputs.setItem(row, column, item)
        self.energy_table.setEnabled(mode is InputMode.DETAIL)
        self.production_table.setEnabled(mode is InputMode.DETAIL)

    def _collect_request(self) -> EvaluationRequest:
        if self.current_standard is None:
            raise ValueError("没有可用标准")
        product = self._selected_product()
        definitions = {}
        if product is not None:
            definitions.update({definition.key: definition for definition in product.input_definitions})
            for indicator in product.indicators:
                definitions.update({definition.key: definition for definition in indicator.input_definitions})
        inputs = {}
        for row in range(self.eval_inputs.rowCount()):
            key = self.eval_inputs.item(row, 0).text()
            value = self.eval_inputs.item(row, 2).text().strip()
            unit = self.eval_inputs.item(row, 3).text().strip() or None
            if value:
                definition = definitions.get(key)
                if definition and definition.data_type is DataType.BOOLEAN:
                    normalized = value.lower()
                    if normalized in {"是", "true", "1", "yes", "y"}:
                        parsed_value = True
                    elif normalized in {"否", "false", "0", "no", "n"}:
                        parsed_value = False
                    else:
                        raise ValueError(f"{definition.label} 必须填写“是”或“否”")
                else:
                    parsed_value = value
                inputs[key] = InputValue(value=parsed_value, unit=unit)
        energy_lines = []
        for row in range(self.energy_table.rowCount()):
            values = [self.energy_table.item(row, column).text().strip() if self.energy_table.item(row, column) else "" for column in range(10)]
            if not values[0]:
                continue
            energy_lines.append(
                EnergyLine(
                    line_id=values[0],
                    energy_name=values[1],
                    category_key=values[2] or None,
                    direction=values[3] or "input",
                    amount=values[4],
                    unit=values[5],
                    standard_coal_coefficient=values[6],
                    coefficient_unit=values[7],
                    allocation_ratio=values[8] or "1",
                    source_note=values[9] or None,
                )
            )
        production_lines = []
        for row in range(self.production_table.rowCount()):
            values = [self.production_table.item(row, column).text().strip() if self.production_table.item(row, column) else "" for column in range(8)]
            if not values[0]:
                continue
            production_lines.append(
                ProductionLine(
                    line_id=values[0],
                    product_name=values[1],
                    category_key=values[2] or None,
                    quantity=values[3],
                    unit=values[4],
                    conversion_factor=values[5] or "1",
                    qualified=(values[6] or "是") == "是",
                    source_note=values[7] or None,
                )
            )
        return EvaluationRequest(
            evaluation_date=date.today(),
            standard_id=self.current_standard.id,
            product_id=self.eval_product.currentData(),
            selection_mode=self._selection_mode(),
            input_mode=InputMode(self.eval_mode.currentData()),
            inputs=inputs,
            energy_lines=energy_lines,
            production_lines=production_lines,
            organization_name=self.eval_organization.text().strip() or None,
            project_name=self.eval_project.text().strip() or None,
            notes=self.eval_notes.text().strip() or None,
        )

    def calculate_evaluation(self, request: EvaluationRequest | None = None) -> None:
        try:
            request = request or self._collect_request()
            is_preview = request.selection_mode is StandardSelectionMode.FUTURE
            result = self.context.application.preview_evaluation(request) if is_preview else self.context.application.evaluate(request)
        except Exception as exc:
            QMessageBox.critical(self, "无法计算", str(exc))
            return
        self.last_result_id = None if is_preview else result.evaluation_id
        self.eval_results.setRowCount(0)
        counts = Counter(item.grade for item in result.results)
        summary = "；".join(
            f"{GRADE_LABELS[grade]} {counts.get(grade, 0)} 项"
            for grade in (
                Grade.LEVEL_1,
                Grade.LEVEL_2,
                Grade.LEVEL_3,
                Grade.NOT_QUALIFIED,
                Grade.INCOMPLETE,
                Grade.NOT_APPLICABLE,
            )
            if counts.get(grade, 0)
        ) or "无指标结果"
        self.eval_summary.setText(f"等级汇总：{summary}（仅统计，不生成总体等级）")
        for item in result.results:
            row = self.eval_results.rowCount()
            self.eval_results.insertRow(row)
            base = item.base_thresholds
            thresholds = item.corrected_thresholds
            references = "; ".join(
                f"p.{ref.page}" + (f" {ref.clause}" if ref.clause else "") + (f" {ref.table}" if ref.table else "")
                for ref in item.source_references
            )
            values = [
                item.indicator_name,
                item.actual_value,
                item.unit,
                base.get("LEVEL_1"),
                base.get("LEVEL_2"),
                base.get("LEVEL_3"),
                thresholds.get("LEVEL_1"),
                thresholds.get("LEVEL_2"),
                thresholds.get("LEVEL_3"),
                GRADE_LABELS[item.grade],
                "；".join(item.warnings),
                ", ".join(str(ref.page) for ref in item.source_references),
                "; ".join(filter(None, {ref.clause for ref in item.source_references} | {ref.table for ref in item.source_references})),
                references,
            ]
            for column, value in enumerate(values):
                cell = _item(value, align_right=column in {1, 3, 4, 5, 6, 7, 8})
                if item.grade is Grade.NOT_QUALIFIED:
                    cell.setBackground(Qt.GlobalColor.red)
                self.eval_results.setItem(row, column, cell)
        self.refresh_home()
        if not is_preview:
            self.refresh_records()
        message = "预览完成：尚未实施标准仅供参考，未保存正式评价记录。" if is_preview else "单项判级已完成并保存。"
        QMessageBox.information(self, "预览完成" if is_preview else "计算完成", message)

    def refresh_records(self) -> None:
        self.record_table.setRowCount(0)
        for record in self.context.application.list_recent_evaluations(200):
            row = self.record_table.rowCount()
            self.record_table.insertRow(row)
            values = [
                record.created_at,
                record.evaluation_date,
                record.standard_number,
                record.organization_name,
                record.project_name,
                record.product_id,
                record.evaluation_id,
            ]
            for column, value in enumerate(values):
                self.record_table.setItem(row, column, _item(value))

    def _selected_record_id(self) -> str | None:
        row = self.record_table.currentRow()
        return self.record_table.item(row, 6).text() if row >= 0 and self.record_table.item(row, 6) else None

    def _load_request_into_form(self, request: EvaluationRequest) -> bool:
        """Populate the wizard from a saved request without changing its data."""
        requested_mode = request.selection_mode
        mode_index = self.eval_selection_mode.findData(requested_mode.value)
        if mode_index < 0:
            mode_index = self.eval_selection_mode.findData(StandardSelectionMode.HISTORICAL.value)
        if mode_index >= 0:
            self.eval_selection_mode.setCurrentIndex(mode_index)
        standard_index = self.eval_standard.findData(request.standard_id)
        if standard_index < 0:
            QMessageBox.warning(self, "标准不可用", "该评价使用的标准未安装，无法复制或重新计算。")
            return False
        self.eval_standard.setCurrentIndex(standard_index)
        product_index = self.eval_product.findData(request.product_id)
        if product_index < 0:
            QMessageBox.warning(self, "产品不可用", "该评价使用的产品/工序当前不在标准规则中。")
            return False
        self.eval_product.setCurrentIndex(product_index)
        mode_index = self.eval_mode.findData(request.input_mode.value)
        if mode_index >= 0:
            self.eval_mode.setCurrentIndex(mode_index)
        self.eval_date.setDate(QDate(request.evaluation_date.year, request.evaluation_date.month, request.evaluation_date.day))
        self.eval_organization.setText(request.organization_name or "")
        self.eval_project.setText(request.project_name or "")
        self.eval_notes.setText(request.notes or "")
        self._refresh_input_table()
        input_rows = {self.eval_inputs.item(row, 0).text(): row for row in range(self.eval_inputs.rowCount())}
        for key, value in request.inputs.items():
            row = input_rows.get(key)
            if row is not None:
                self.eval_inputs.item(row, 2).setText(str(value.value))
                self.eval_inputs.item(row, 3).setText(value.unit or "")
        self.energy_table.setRowCount(0)
        for line in request.energy_lines:
            self._append_blank_row(
                self.energy_table,
                [
                    line.line_id, line.energy_name, line.category_key or "", line.direction,
                    str(line.amount), line.unit, str(line.standard_coal_coefficient),
                    line.coefficient_unit, str(line.allocation_ratio), line.source_note or "",
                ],
            )
        self.production_table.setRowCount(0)
        for line in request.production_lines:
            self._append_blank_row(
                self.production_table,
                [
                    line.line_id, line.product_name, line.category_key or "", str(line.quantity),
                    line.unit, str(line.conversion_factor), "是" if line.qualified else "否", line.source_note or "",
                ],
            )
        return True

    def copy_selected_record(self) -> None:
        evaluation_id = self._selected_record_id()
        if not evaluation_id:
            QMessageBox.warning(self, "未选择", "请选择一条评价记录。")
            return
        loaded = self.context.application.get_evaluation(evaluation_id)
        if loaded is None:
            QMessageBox.warning(self, "记录不存在", "该评价记录已被删除或不存在。")
            return
        request, _result, _snapshot = loaded
        if self._load_request_into_form(request):
            self.navigation.setCurrentRow(2)

    def recalculate_selected_record(self) -> None:
        evaluation_id = self._selected_record_id()
        if not evaluation_id:
            QMessageBox.warning(self, "未选择", "请选择一条评价记录。")
            return
        loaded = self.context.application.get_evaluation(evaluation_id)
        if loaded is None:
            QMessageBox.warning(self, "记录不存在", "该评价记录已被删除或不存在。")
            return
        request, _result, _snapshot = loaded
        self.calculate_evaluation(request)

    def export_selected_record(self) -> None:
        evaluation_id = self._selected_record_id()
        if not evaluation_id:
            QMessageBox.warning(self, "未选择", "请选择一条评价记录。")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出Excel", f"能耗对标-{evaluation_id[:8]}.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        try:
            self.context.application.export_evaluation(evaluation_id, Path(path))
            QMessageBox.information(self, "导出成功", path)
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))

    def delete_selected_record(self) -> None:
        evaluation_id = self._selected_record_id()
        if not evaluation_id:
            return
        if QMessageBox.question(self, "确认删除", "记录将被软删除并保留审计日志，是否继续？") != QMessageBox.StandardButton.Yes:
            return
        self.context.application.delete_evaluation(evaluation_id)
        self.refresh_all()

    def save_import_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "保存导入模板", "单位产品能耗对标导入模板.xlsx", "Excel (*.xlsx)")
        if path:
            self.context.application.create_template(Path(path))
            QMessageBox.information(self, "模板已保存", path)

    def validate_import_workbook(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择Excel", "", "Excel (*.xlsx)")
        if not path:
            return
        report = self.context.application.validate_workbook(Path(path))
        self.pending_import_id = report.import_id if report.valid else None
        self.import_commit_button.setEnabled(report.valid)
        self.import_status.setText("校验通过，可提交计算。" if report.valid else "校验失败，请修正后重新导入。")
        self.import_issues.setRowCount(0)
        for issue in report.issues:
            row = self.import_issues.rowCount()
            self.import_issues.insertRow(row)
            for column, value in enumerate((issue.severity, issue.sheet, issue.cell, issue.message)):
                self.import_issues.setItem(row, column, _item(value))

    def commit_import(self) -> None:
        if not self.pending_import_id:
            return
        try:
            draft = self.context.application.commit_workbook(self.pending_import_id)
            self.calculate_evaluation(draft.request)
            self.pending_import_id = None
            self.import_commit_button.setEnabled(False)
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", str(exc))

    def refresh_audit(self) -> None:
        self.audit_table.setRowCount(0)
        for entry in self.context.application.list_audit(500):
            row = self.audit_table.rowCount()
            self.audit_table.insertRow(row)
            for column, value in enumerate((entry.created_at, entry.action, entry.entity_type, entry.entity_id, entry.details_json)):
                self.audit_table.setItem(row, column, _item(value))

    def discover_standard_packages(self) -> None:
        """Scan a selected local/NAS directory without installing anything."""
        if not self.context.application.has_package_service():
            return
        directory = QFileDialog.getExistingDirectory(self, "选择标准包目录")
        if not directory:
            return
        try:
            paths = self.context.application.discover_package_paths(Path(directory), recursive=True)
        except Exception as exc:
            QMessageBox.critical(self, "扫描失败", str(exc))
            return
        if not paths:
            QMessageBox.information(self, "扫描结果", "目录中没有找到 .uebench 标准包。")
            return
        lines = [f"扫描到 {len(paths)} 个候选包（仅扫描，未安装）："]
        for path in paths:
            try:
                report = self.context.application.preview_package(path)
            except Exception as exc:
                lines.append(f"{path.name}：无法读取（{exc}）")
                continue
            if report.valid and report.manifest is not None:
                manifest = report.manifest
                lines.append(f"{path.name}：可安装；数据版本 {manifest.data_version}；{manifest.package_mode}；{manifest.standard_count} 项标准")
                if report.warnings:
                    lines.append("  提示：" + "；".join(report.warnings))
            else:
                lines.append(f"{path.name}：拒绝；" + "；".join(report.errors))
        QMessageBox.information(self, "标准包扫描结果", "\n".join(lines))

    def install_standard_package(self) -> None:
        if not self.context.application.has_package_service():
            return
        path, _ = QFileDialog.getOpenFileName(self, "选择标准包", "", "UEBench标准包 (*.uebench)")
        if not path:
            return
        report = self.context.application.preview_package(Path(path))
        if not report.valid:
            QMessageBox.critical(self, "标准包无效", "\n".join(report.errors))
            return
        if QMessageBox.question(self, "确认安装", f"将安装 {len(report.definitions)} 项标准，是否继续？") != QMessageBox.StandardButton.Yes:
            return
        try:
            result = self.context.application.install_package(Path(path))
            self.refresh_all()
            QMessageBox.information(self, "安装完成", f"已安装 {result.standards_installed} 项标准。")
        except Exception as exc:
            QMessageBox.critical(self, "安装失败", str(exc))

    def create_backup(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "创建备份", f"uebench-{date.today():%Y%m%d}.uebackup", "UEBench备份 (*.uebackup)")
        if path:
            self.context.application.create_backup(Path(path))
            QMessageBox.information(self, "备份完成", path)

    def restore_backup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "恢复备份", "", "UEBench备份 (*.uebackup)")
        if not path:
            return
        if QMessageBox.question(self, "确认恢复", "恢复将替换当前数据，并先自动创建恢复前备份。是否继续？") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.context.application.restore_backup(Path(path))
            self.refresh_all()
            QMessageBox.information(self, "恢复完成", "数据已恢复。")
        except Exception as exc:
            QMessageBox.critical(self, "恢复失败", str(exc))

    def open_selected_standard(self) -> None:
        row = self.standard_table.currentRow()
        if row < 0:
            return
        standard_id = self.standard_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        standard = self.context.application.get_published_standard(standard_id)
        if standard is None:
            return
        source = self.context.application.find_standard_source(standard_id)
        if source is None:
            QMessageBox.warning(self, "原文缺失", "本机标准库中未找到该PDF。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(source)))


def create_main_window(context: AppContext) -> MainWindow:
    return MainWindow(context)
