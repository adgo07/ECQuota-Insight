from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING
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

if TYPE_CHECKING:
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
    PublicationStatus,
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
QPushButton:checked { background: #17365d; border: 2px solid #f5a623; }
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


# Rule JSON keeps stable machine-readable note codes.  The desktop UI must
# never expose those implementation codes to Chinese users, so translate the
# common codes at the presentation boundary and keep a Chinese fallback for
# newly added rules.
_NOTE_TRANSLATIONS = {
    "requires_independent_review": "需独立复核后使用",
    "original_pdf_transcribed": "已从标准原文转录",
    "candidate_from_original_pdf": "由标准原文提取的候选规则",
    "not_for_formal_evaluation": "尚未发布，不能用于正式评价",
    "product_specification_factor_from_table_footnotes": "产品规格修正系数取自表格脚注",
    "statistics_scope_and_80_percent_rule_in_clause_6": "统计范围及80%规则见第6章",
    "winter_heating_scope_note_in_table": "采暖范围按表中说明执行",
    "statistics_and_yield_conversion_in_clause_6": "统计范围和产量折算见第6章",
    "thickness_column_from_table_3": "厚度修正取表3",
    "paper_process_modifier_from_table_2_notes": "纸种和工艺修正取表2注",
    "detail_formula_blocked_until_factor_model_review": "修正因子模型复核完成前，明细模式返回不完整",
    "non_monotonic_source_values_preserved": "保留标准原文中的非单调限额值",
    "table_rows_transcribed_from_current_mandatory_text": "已从现行强制性标准原文表格转录",
    "special_process_boundary_or_product_conversion_requires_clause_review": "特殊工艺边界或产品折算需按条款复核",
    "product_indicator_split_confirmed": "产品和指标已按规则拆分",
    "missing_grade_preserved": "标准原文缺少该等级，按缺级保留",
    "detail_energy_lines_are_scoped_to_the_selected_product": "能源明细仅计入所选产品或工序范围",
    "standard_scope_excludes_special_glass_fibers": "标准范围不包括特殊玻璃纤维",
    "qualified_product_must_meet_GB_T_32469_for_TDI_or_GB_T_13941_for_MDI": "合格产品应满足标准引用的产品质量要求",
}


def _translate_note(note: str) -> str:
    text = str(note).strip()
    if not text:
        return ""
    if text in _NOTE_TRANSLATIONS:
        return _NOTE_TRANSLATIONS[text]
    if text.startswith("visual_reviewed_"):
        return "已对照标准原文复核"
    if text.startswith("detail_input_category:"):
        return "明细录入分类按标准规则设置"
    if text.startswith("detail_energy_category_keys:"):
        return "明细能源分类按标准规则设置"
    if text.startswith("detail_") and text.endswith("_review"):
        return "明细计算口径需按标准条款复核"
    if text.startswith("formula_") or text.endswith("_formula") or "_formula_" in text:
        return "修正公式已结构化，计算时按标准条款执行"
    if text.startswith("capacity_") or text.startswith("fuel_") or text.startswith("heating_"):
        return "修正参数按标准表格和条款执行"
    # Do not leak a new English rule code before its translation is added.
    if any("a" <= char.lower() <= "z" for char in text):
        return "规则说明已登记，具体以标准原文依据为准"
    return text


def _condition_description(condition) -> str:
    """Render a concise Chinese applicability description for the library."""
    op = getattr(condition, "op", "always")
    if op == "always":
        return ""
    operators = {
        "eq": "等于",
        "ne": "不等于",
        "lt": "小于",
        "lte": "小于或等于",
        "gt": "大于",
        "gte": "大于或等于",
        "in": "属于规定选项",
    }
    if op in {"all", "any"}:
        parts = [_condition_description(item) for item in getattr(condition, "args", [])]
        parts = [item for item in parts if item]
        connector = "且" if op == "all" else "或"
        return connector.join(parts) if parts else "按标准规定确认"
    if op == "not":
        parts = [_condition_description(item) for item in getattr(condition, "args", [])]
        return "不满足（" + "且".join(item for item in parts if item) + "）"
    if op == "range":
        minimum = getattr(condition, "minimum", None)
        maximum = getattr(condition, "maximum", None)
        left = "不小于" if getattr(condition, "include_minimum", True) else "大于"
        right = "不大于" if getattr(condition, "include_maximum", True) else "小于"
        return f"相关参数{left}{minimum}且{right}{maximum}"
    if op == "in":
        values = "、".join(str(item) for item in getattr(condition, "values", []))
        return f"相关参数属于{values or '标准规定选项'}"
    value = getattr(condition, "value", None)
    return f"相关参数{operators.get(op, '满足')} {value if value is not None else '标准规定值'}"


def _friendly_error(exc: Exception, operation: str) -> str:
    """Keep error dialogs understandable and Chinese even for library errors."""
    detail = str(exc).strip()
    if detail and any("\u4e00" <= char <= "\u9fff" for char in detail):
        return f"{operation}：{detail}"
    return f"{operation}失败，请检查输入数据、单位和适用条件后重试。"


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.current_standard: StandardDefinition | None = None
        self.last_result_id: str | None = None
        self.pending_import_id: str | None = None
        self.setWindowTitle("单位产品能耗对标软件")
        # Leave room for the ten-column energy table on ordinary 1366x768 and
        # 1920x1080 screens.  Users can still resize the window smaller.
        self.resize(1440, 900)
        self.setMinimumSize(1180, 760)
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
        self.standard_table.itemDoubleClicked.connect(lambda *_: self.open_selected_standard())
        self.standard_table.setToolTip("双击标准行直接打开已安装且校验通过的标准原文")
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
        # Kept as a hidden compatibility model field; the visible choice is
        # presented as two large checkable buttons beside the action buttons.
        self.eval_mode.setVisible(False)
        self.eval_date = QDateEdit(QDate.currentDate())
        self.eval_date.setCalendarPopup(False)
        self.eval_date.setReadOnly(True)
        self.eval_date.setEnabled(False)
        self.eval_date.setVisible(False)
        self.eval_organization = QLineEdit()
        self.eval_project = QLineEdit()
        self.eval_project.setVisible(False)
        self.eval_notes = QLineEdit()
        form.addRow("标准选择方式", self.eval_selection_mode)
        form.addRow("标准", self.eval_standard)
        form.addRow("标准状态提示", self.eval_standard_status)
        form.addRow("产品/工序", self.eval_product)
        form.addRow("单位名称", self.eval_organization)
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
        self.input_tabs.setMinimumHeight(360)
        for table in (self.eval_inputs, self.energy_table, self.production_table):
            table.setMinimumHeight(300)
            table.verticalHeader().setDefaultSectionSize(28)
        input_hint = QLabel(
            "下方参数由所选标准和产品/工序自动生成。可直接点击“值”列输入；选择明细方式时，"
            "再填写能源明细和产量与分摊。"
        )
        input_hint.setWordWrap(True)
        layout.addWidget(input_hint)
        layout.addWidget(self.input_tabs, 1)

        buttons = QHBoxLayout()
        mode_label = QLabel("输入方式")
        self.direct_mode_button = QPushButton("直接录入实际值")
        self.detail_mode_button = QPushButton("按能源/产量明细计算")
        for button in (self.direct_mode_button, self.detail_mode_button):
            button.setCheckable(True)
            button.setAutoExclusive(True)
        self.direct_mode_button.clicked.connect(lambda: self._set_input_mode(InputMode.DIRECT))
        self.detail_mode_button.clicked.connect(lambda: self._set_input_mode(InputMode.DETAIL))
        buttons.addWidget(mode_label)
        buttons.addWidget(self.direct_mode_button)
        buttons.addWidget(self.detail_mode_button)
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
        self.eval_results.setMinimumHeight(220)
        self.eval_summary = QLabel("等级汇总：尚未计算")
        layout.addWidget(self.eval_summary)
        layout.addWidget(self.eval_results, 1)
        self._sync_mode_buttons()
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
        explanation = QLabel(
            "Excel导入用于批量填写评价信息、适用条件、实际值、能源明细和产量分摊。"
            "软件会先按固定模板逐单元格校验，校验通过后再提交计算；Excel本身不单独判级。"
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
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
        layout.addWidget(QLabel("已安装标准包历史"))
        self.package_history_table = QTableWidget(0, 8)
        self.package_history_table.setHorizontalHeaderLabels(
            ["安装时间", "数据版本", "包类型", "父包", "标准数", "规则数", "包ID", "SHA-256"]
        )
        self._configure_table(self.package_history_table)
        layout.addWidget(self.package_history_table, 1)
        layout.addWidget(QLabel("审计日志"))
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
            self.refresh_package_history()
            self.refresh_audit()

    def refresh_all(self) -> None:
        self.refresh_home()
        self.refresh_standards()
        self.refresh_standard_combo()
        self.refresh_records()
        self.refresh_package_history()
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
        # The library is a catalogue of the 63 in-scope standards, not only
        # today's executable subset.  Draft/future entries remain visible so
        # users can find them and see why formal evaluation is unavailable.
        standards = [
            item
            for item in self.context.application.list_library_standards()
            if item.lifecycle_status is not LifecycleStatus.OBSOLETE
        ]
        self.standard_table.setRowCount(0)
        for standard in standards:
            haystack = f"{standard.number} {standard.title} {' '.join(p.name for p in standard.products)}".lower()
            if query and query not in haystack:
                continue
            row = self.standard_table.rowCount()
            self.standard_table.insertRow(row)
            if standard.publication_status is not PublicationStatus.PUBLISHED:
                status = "待确认（不可正式评价）"
            elif standard.effective_date > date.today():
                status = "尚未实施（仅预览）"
            elif standard.is_effective_on(date.today()):
                status = "当前有效"
            else:
                status = "历史/已替代"
            values = [
                standard.number,
                standard.title,
                status,
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
            (item for item in self.context.application.list_library_standards() if item.id == standard_id),
            None,
        )
        if standard is None:
            self.standard_detail_label.setText("选择标准后查看指标、限额和原文依据")
            return
        indicator_count = sum(len(product.indicators) for product in standard.products)
        status = "已发布" if standard.publication_status is PublicationStatus.PUBLISHED else "待确认，不能正式评价"
        self.standard_detail_label.setText(f"{standard.number}：{indicator_count} 个指标；{status}")

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
                notes = "；".join(
                    translated
                    for translated in (_translate_note(note) for note in indicator.notes)
                    if translated
                )
                if indicator.applicability.op != "always":
                    condition_text = _condition_description(indicator.applicability)
                    notes = (notes + "；" if notes else "") + (
                        f"适用条件：{condition_text}" if condition_text else "适用条件：按标准规定确认"
                    )
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

    def _set_input_mode(self, mode: InputMode) -> None:
        """Update the hidden request field from the visible mode buttons."""
        index = self.eval_mode.findData(mode.value)
        if index < 0:
            return
        self.eval_mode.blockSignals(True)
        self.eval_mode.setCurrentIndex(index)
        self.eval_mode.blockSignals(False)
        self._sync_mode_buttons()
        self._refresh_input_table()

    def _sync_mode_buttons(self) -> None:
        if not hasattr(self, "direct_mode_button"):
            return
        mode = self.eval_mode.currentData()
        self.direct_mode_button.setChecked(mode == InputMode.DIRECT.value)
        self.detail_mode_button.setChecked(mode == InputMode.DETAIL.value)

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
            QMessageBox.critical(self, "无法计算", _friendly_error(exc, "计算和判级"))
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
        self._sync_mode_buttons()
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
            QMessageBox.critical(self, "导出失败", _friendly_error(exc, "导出Excel"))

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
            QMessageBox.critical(self, "导入失败", _friendly_error(exc, "导入Excel"))

    def refresh_package_history(self) -> None:
        self.package_history_table.setRowCount(0)
        mode_labels = {"full": "完整包", "incremental": "增量包"}
        for entry in self.context.application.list_package_history(100):
            row = self.package_history_table.rowCount()
            self.package_history_table.insertRow(row)
            values = (
                entry.installed_at.strftime("%Y-%m-%d %H:%M:%S"),
                entry.data_version,
                mode_labels.get(entry.package_mode, entry.package_mode),
                entry.parent_package_id or "—",
                entry.standard_count,
                entry.rule_count,
                entry.package_id,
                entry.package_sha256,
            )
            for column, value in enumerate(values):
                item = _item(value)
                if column == 7:
                    item.setToolTip(entry.package_sha256)
                self.package_history_table.setItem(row, column, item)
    def refresh_audit(self) -> None:
        self.audit_table.setRowCount(0)
        for entry in self.context.application.list_audit(500):
            row = self.audit_table.rowCount()
            self.audit_table.insertRow(row)
            for column, value in enumerate((entry.created_at, entry.action, entry.entity_type, entry.entity_id, entry.details_json)):
                self.audit_table.setItem(row, column, _item(value))

    def discover_standard_packages(self) -> None:
        """Scan a selected local/NAS directory through the application use case."""
        if not self.context.application.has_package_service():
            return
        directory = QFileDialog.getExistingDirectory(self, "选择标准包目录")
        if not directory:
            return
        try:
            items = self.context.application.scan_package_directory(Path(directory), recursive=True)
        except Exception as exc:
            QMessageBox.critical(self, "扫描失败", _friendly_error(exc, "扫描标准包目录"))
            return
        if not items:
            QMessageBox.information(self, "扫描结果", "目录中没有找到 .uebench 标准包。")
            return
        lines = [f"扫描到 {len(items)} 个候选包（仅扫描，未安装）："]
        for item in items:
            filename = Path(item.path).name
            if item.valid:
                detail = f"可安装；数据版本 {item.data_version}；{item.package_mode}；{item.standard_count} 项标准"
                lines.append(f"{filename}：{detail}")
                if item.warnings:
                    lines.append("  提示：" + "；".join(item.warnings))
            else:
                lines.append(f"{filename}：拒绝；" + "；".join(item.errors))
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
            QMessageBox.critical(self, "安装失败", _friendly_error(exc, "安装标准包"))

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
            QMessageBox.critical(self, "恢复失败", _friendly_error(exc, "恢复备份"))

    def open_selected_standard(self) -> None:
        row = self.standard_table.currentRow()
        if row < 0:
            return
        standard_id = self.standard_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        standard = next(
            (item for item in self.context.application.list_library_standards() if item.id == standard_id),
            None,
        )
        if standard is None:
            return
        source = self.context.application.find_standard_source(standard_id)
        if source is None:
            QMessageBox.warning(
                self,
                "原文缺失或不匹配",
                "本机标准库中未找到与该标准版本 SHA-256 一致的PDF；请先安装包含该原文的标准包。",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(source)))


def create_main_window(context: AppContext) -> MainWindow:
    return MainWindow(context)
