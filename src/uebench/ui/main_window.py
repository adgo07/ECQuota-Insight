from __future__ import annotations

import logging
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

_LOGGER = logging.getLogger(__name__)

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
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
    QScrollArea,
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

from uebench import __version__
from uebench.application.build_identity import (
    DiagnosticsFacts,
    load_build_identity,
    reconciliation_facts,
    render_diagnostics,
)
from uebench.application.evaluation_support import (
    FORMAL_EVALUATION_UNSUPPORTED_LABEL,
    evaluation_support_label,
    filter_formally_evaluable,
    supports_formal_evaluation,
)
from uebench.application.gb29446 import (
    GB29446_PERIOD_OPTIONS,
    GB29446_STANDARD_ID,
    PERIOD_CUSTOM,
    decode_period_notes,
    encode_period_notes,
)
from uebench.application.official_sources import (
    NO_OFFICIAL_SOURCE_LABEL,
    OFFICIAL_SOURCE_PLATFORM_HOME,
    OFFICIAL_SOURCE_PLATFORM_NAME,
    VIEW_OFFICIAL_SOURCE_BUTTON_TEXT,
    official_source_url,
)
from uebench.domain.models import (
    EnergyLine,
    EvaluationRequest,
    EvaluationResult,
    IndicatorResult,
    DataType,
    GRADE_LABELS,
    Grade,
    LifecycleStatus,
    InputMode,
    InputValue,
    PublicationStatus,
    RECORD_CORRUPTED_LABEL,
    SelectionLevel,
    StandardSelectionMode,
    ProductionLine,
    StandardDefinition,
    StorageCorruptionError,
)
from uebench.ui.presentation import format_local_date, format_local_datetime


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


# ---------------------------------------------------------------------------
# GB 29446 规则兼容性（FAIL-FAST）
# ---------------------------------------------------------------------------
#
# 正式 r2 规则要求标准定义自身携带“煤种”选择层级、每个煤种的非空
# ``selection_values.coal_type``，以及选煤电力单耗指标中按选煤工艺查表的
# ``process_factor`` 行。旧版/不完整定义缺少这些结构时，界面过去会：
#
# * 用 ``product.name`` 冒充“煤种”；
# * 把“选煤工艺”下拉框渲染成一个看起来正常、实际没有可选项的空控件；
# * 仍然允许发起正式评价。
#
# 上述行为都是“假装可用”。现有做法是**如实拒绝**：显示明确的中文提示、
# 不渲染假可用的选择器、阻止正式计算。这里不引入第二套业务算法，也不改变
# 正常 r2 路径的任何取值。

#: 当前 GB 29446 正式规则使用的煤种选择层级 key。
GB29446_COAL_TYPE_KEY = "coal_type"

#: 选煤电力单耗指标中按选煤工艺查附录A的展示计算 key。
GB29446_PROCESS_FACTOR_KEY = "process_factor"

#: 规则数据不完整/版本不兼容时的中文提示（必须说明“更新标准数据”）。
GB29446_RULE_INCOMPATIBLE_MESSAGE = "标准规则数据不完整或版本不兼容，请更新标准数据后再评价。"

#: 启动标准包对账未达到期望状态时的非阻断中文提示前缀（ECQ-RS05 §三 E/F）。
PACKAGE_RECONCILIATION_NOTICE_PREFIX = "标准数据未更新或标准数据状态异常"


def _gb29446_product_has_process_factor_rows(product) -> bool:
    """该煤种是否存在可用的“选煤工艺 → 折算系数 k”查表行。

    判定条件与选择器读取系数时的条件完全一致：``process_factor`` 的 lookup
    公式中至少有一行按 ``washing_process`` 相等匹配到常量系数。只要一行都取
    不到，工艺下拉框就是空的，规则即视为不完整。
    """

    for indicator in product.indicators:
        for display in indicator.display_calculations:
            if display.key != GB29446_PROCESS_FACTOR_KEY or display.formula.op != "lookup":
                continue
            for row in display.formula.rows:
                condition = row.condition
                expression = row.expression
                if (
                    condition.op == "eq"
                    and condition.field == "washing_process"
                    and expression.op == "constant"
                    and condition.value is not None
                    and expression.value is not None
                ):
                    return True
    return False


def gb29446_rule_is_compatible(definition) -> bool:
    """判断已加载的 GB 29446 定义是否具备正式 r2 规则所需的结构。

    返回 ``True`` 仅当**全部**满足：

    1. ``selection_schema`` 中含 ``coal_type`` 层级；
    2. 每个煤种都有非空的 ``selection_values["coal_type"]``；
    3. 每个煤种的选煤电力单耗指标都有可用的 ``process_factor`` 查表行。

    ``None`` 或空定义返回 ``False``。本函数是纯判定，不做任何业务计算。
    """

    if definition is None:
        return False
    if not any(level.key == GB29446_COAL_TYPE_KEY for level in definition.selection_schema):
        return False
    if not definition.products:
        return False
    for product in definition.products:
        coal_type = product.selection_values.get(GB29446_COAL_TYPE_KEY)
        if coal_type is None or not str(coal_type).strip():
            return False
        if not _gb29446_product_has_process_factor_rows(product):
            return False
    return True


# ---------------------------------------------------------------------------
# 标准库「评价范围」（ECQ-RS05 §六）
# ---------------------------------------------------------------------------
#
# 「评价范围」只能来自**已确认的既有标准元数据**，UI 不得自行编写范围文字：
#
# * GB 29446—2019 已经完成梳理，因此可以如实展示范围：覆盖煤种取自定义自身的
#   ``selection_schema`` / ``selection_values["coal_type"]``；统计边界取自定义中
#   ``electricity_consumption`` 输入的说明（“统计边界按标准第5.1条”）；单次评价
#   只支持单一煤种、单一工艺取自定义中 ``single_coal_single_process`` 输入的说明。
# * 其余标准尚未重新梳理，没有可靠范围，只能如实显示
#   :data:`EVALUATION_SCOPE_PENDING_LABEL`，不得由 UI 或实现者代写范围。
EVALUATION_SCOPE_PENDING_LABEL = "评价范围尚待梳理"

#: GB 29446 统计范围已确认文本（标准第5.1条）。此前只内联在「新建评价」的
#: 「统计范围说明」里；现在「统计范围说明」与标准库「评价范围」共用同一份已确认
#: 内容，避免两处各自漂移。
GB29446_STATISTICS_SCOPE_LINES = (
    "原煤输送至选煤厂 → 选煤产品运输出选煤厂",
    "统计内容包括：选煤机械、照明、化验室、相关线路电损失、相关变压器电损失。",
)

#: 标准库表格用的边界短文本；与定义中 ``electricity_consumption`` 的说明一致。
GB29446_STATISTICS_BOUNDARY_REFERENCE = "统计边界按标准第5.1条"


def _gb29446_statistics_scope_text() -> str:
    """「统计范围说明」按钮展开后的确认文本（保持既有换行展示）。"""

    return "\n".join(GB29446_STATISTICS_SCOPE_LINES)


def _gb29446_scope_metadata(definition) -> tuple[list[str], str, bool]:
    """从已安装的 GB 29446 定义中读出已确认的范围元数据。

    返回 ``(覆盖煤种, 统计边界依据, 是否限制单一煤种单一工艺)``。读不到的部分留空，
    由调用方如实省略，不在这里补写任何业务文字。
    """

    coal_types: list[str] = []
    boundary = ""
    single_coal_single_process = False
    for product in definition.products:
        value = str(product.selection_values.get(GB29446_COAL_TYPE_KEY) or "").strip()
        if value and value not in coal_types:
            coal_types.append(value)
        for item in product.input_definitions:
            if item.key == "single_coal_single_process":
                single_coal_single_process = True
        for indicator in product.indicators:
            for item in indicator.input_definitions:
                if item.key == "electricity_consumption" and item.description and not boundary:
                    boundary = item.description.split("；", 1)[0].strip()
    return coal_types, boundary, single_coal_single_process


def evaluation_scope_summary(definition) -> str:
    """标准库表格用的「评价范围」短文本；没有可靠范围时返回如实状态。"""

    if definition is None or definition.id != GB29446_STANDARD_ID:
        return EVALUATION_SCOPE_PENDING_LABEL
    coal_types, boundary, _single = _gb29446_scope_metadata(definition)
    parts: list[str] = []
    if coal_types:
        parts.append("覆盖煤种：" + "、".join(coal_types))
    parts.append(boundary or GB29446_STATISTICS_BOUNDARY_REFERENCE)
    return "；".join(parts)


def evaluation_scope_text(definition) -> str:
    """标准库详情用的完整「评价范围」；内容全部来自已确认的标准元数据。"""

    if definition is None or definition.id != GB29446_STANDARD_ID:
        return EVALUATION_SCOPE_PENDING_LABEL
    coal_types, boundary, single_coal_single_process = _gb29446_scope_metadata(definition)
    parts: list[str] = []
    if coal_types:
        parts.append("覆盖煤种：" + "、".join(coal_types))
    boundary_text = "；".join(line.rstrip("。") for line in GB29446_STATISTICS_SCOPE_LINES)
    parts.append(f"{boundary}：{boundary_text}" if boundary else boundary_text)
    if single_coal_single_process:
        parts.append("单次评价仅支持单一煤种、单一工艺")
    return "；".join(parts)


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.current_standard: StandardDefinition | None = None
        self.last_result_id: str | None = None
        self.pending_import_id: str | None = None
        self.pending_import_standard_id: str | None = None
        #: 当前加载的 GB 29446 规则是否满足正式 r2 结构；非 GB29446 标准恒为 True。
        self.gb29446_rule_compatible = True
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
        self._build_help_menu()
        self.refresh_all()

    def _build_help_menu(self) -> None:
        """Add the read-only 关于 / 诊断信息 entry without touching the page layout."""
        help_menu = self.menuBar().addMenu("帮助")
        diagnostics = QAction("关于 / 诊断信息…", self)
        diagnostics.setObjectName("diagnostics_action")
        diagnostics.triggered.connect(self.show_diagnostics)
        help_menu.addAction(diagnostics)
        # 保留 Python 引用：菜单属于窗口的辅助入口，不应依赖临时包装对象。
        self.help_menu = help_menu
        self.diagnostics_action = diagnostics

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
        self.home_formal_scope_count = QLabel("0 项")
        self.home_evaluation_count = QLabel("0")
        self.home_package_version = QLabel("未安装")
        self.home_standard_count.setToolTip(
            "已发布且当前有效的标准数量（标准文档状态）；不等于可正式评价的标准数量，"
            "正式评价范围见「正式评价范围」。"
        )
        self.home_formal_scope_count.setToolTip("本机标准库中已纳入正式评价范围、可给出正式评价结论的标准数量。")
        for title, widget in (
            ("已发布标准", self.home_standard_count),
            ("正式评价范围", self.home_formal_scope_count),
            ("评价记录", self.home_evaluation_count),
            ("标准包", self.home_package_version),
        ):
            card, card_layout = self._card()
            card_layout.addWidget(QLabel(title))
            widget.setProperty("class", "metric")
            card_layout.addWidget(widget)
            metrics.addWidget(card)
        layout.addLayout(metrics)
        scope_row = QHBoxLayout()
        self.home_scope_label = QLabel("")
        self.home_scope_label.setWordWrap(True)
        self.home_start_evaluation = QPushButton("开始正式评价")
        self.home_start_evaluation.setObjectName("homeStartFormalEvaluation")
        self.home_start_evaluation.clicked.connect(self.start_formal_evaluation)
        scope_row.addWidget(self.home_scope_label, 1)
        scope_row.addWidget(self.home_start_evaluation)
        layout.addLayout(scope_row)
        card, card_layout = self._card()
        card_layout.addWidget(QLabel("最近评价"))
        self.home_recent = QTableWidget(0, 3)
        self.home_recent.setHorizontalHeaderLabels(["时间", "标准", "单位/项目"])
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
        self.standard_evaluate_button = QPushButton("用该标准新建评价")
        self.standard_evaluate_button.setObjectName("standardLibraryEvaluateButton")
        self.standard_evaluate_button.setToolTip("仅正式评价范围内的标准可以发起正式评价。")
        self.standard_evaluate_button.clicked.connect(self.start_evaluation_for_selected_standard)
        self.standard_official_button = QPushButton(VIEW_OFFICIAL_SOURCE_BUTTON_TEXT)
        self.standard_official_button.setObjectName("standardLibraryOfficialSourceButton")
        self.standard_official_button.clicked.connect(self.open_selected_standard)
        self.standard_official_status = QLabel(NO_OFFICIAL_SOURCE_LABEL)
        self.standard_official_status.setObjectName("standardLibraryOfficialSourceStatus")
        controls.addWidget(self.standard_search, 1)
        controls.addWidget(self.standard_evaluate_button)
        controls.addWidget(self.standard_official_button)
        controls.addWidget(self.standard_official_status)
        layout.addLayout(controls)
        # 普通页面只保留业务信息：标准编号/名称/状态/版本/实施日期，以及软件评价支持
        # 状态、评价范围和官方来源。原文 SHA-256、页码、条款/表号、产品/工序数属于
        # 内部可追溯信息，不再占用普通页面。
        self.standard_table = QTableWidget(0, 8)
        self.standard_table.setHorizontalHeaderLabels(
            [
                "标准编号",
                "标准名称",
                "标准状态",
                "版本",
                "实施日期",
                "软件评价支持状态",
                "评价范围",
                "官方来源",
            ]
        )
        self._configure_table(self.standard_table)
        self.standard_table.itemSelectionChanged.connect(self.refresh_standard_detail)
        self.standard_table.itemDoubleClicked.connect(lambda *_: self.open_selected_standard())
        self.standard_table.setToolTip(
            f"双击标准行打开{OFFICIAL_SOURCE_PLATFORM_NAME}上已登记的官方来源；未登记地址的标准不可用。"
        )
        layout.addWidget(self.standard_table, 1)
        self.standard_detail_label = QLabel("选择标准后查看指标、限额和评价范围")
        self.standard_detail_label.setWordWrap(True)
        layout.addWidget(self.standard_detail_label)
        self.standard_indicator_table = QTableWidget(0, 7)
        self.standard_indicator_table.setHorizontalHeaderLabels(
            ["产品/工序", "指标", "单位", "1级限额", "2级限额", "3级限额", "适用条件/说明"]
        )
        self._configure_table(self.standard_indicator_table)
        layout.addWidget(self.standard_indicator_table, 2)
        return page

    def _build_evaluation(self) -> QWidget:
        page, page_layout = self._page("新建评价")
        # 页面右上角：当前标准的软件评价支持状态 + 官方来源入口。两个入口都只使用
        # 已登记的官方来源服务，不在页面里硬编码任何地址。
        header = QHBoxLayout()
        self.eval_support_label = QLabel(FORMAL_EVALUATION_UNSUPPORTED_LABEL)
        self.eval_support_label.setObjectName("evaluationSupportStatus")
        self.eval_official_status = QLabel(NO_OFFICIAL_SOURCE_LABEL)
        self.eval_official_status.setObjectName("evaluationOfficialSourceStatus")
        self.eval_standard_open = QPushButton(VIEW_OFFICIAL_SOURCE_BUTTON_TEXT)
        self.eval_standard_open.setObjectName("evaluationOfficialSourceButton")
        self.eval_standard_open.clicked.connect(self.open_selected_standard_for_evaluation)
        header.addWidget(self.eval_support_label)
        header.addStretch()
        header.addWidget(self.eval_official_status)
        header.addWidget(self.eval_standard_open)
        page_layout.addLayout(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(14)
        scroll.setWidget(content)
        page_layout.addWidget(scroll, 1)

        form_card, form_layout = self._card()
        form_layout.addWidget(QLabel("一、评价信息与数据填写"))
        form = QFormLayout()
        self.eval_selection_mode = QComboBox()
        self.eval_selection_mode.addItem("当前有效标准（自动）", StandardSelectionMode.CURRENT.value)
        self.eval_selection_mode.addItem("历史标准（需提示确认）", StandardSelectionMode.HISTORICAL.value)
        self.eval_selection_mode.addItem("尚未实施标准（仅预览）", StandardSelectionMode.FUTURE.value)
        self.eval_selection_mode.currentIndexChanged.connect(self.refresh_standard_combo)
        self.eval_standard = QComboBox()
        self.eval_standard.setEditable(True)
        self.eval_standard.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.eval_standard.setPlaceholderText("输入标准编号或名称后选择")
        # 下拉框必须能完整显示“标准编号 + 标准名称”，否则用户无法确认自己选的是哪一项。
        self.eval_standard.setMinimumWidth(420)
        self.eval_standard.setMinimumContentsLength(34)
        self.eval_standard.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        completer = self.eval_standard.completer()
        if completer is not None:
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.eval_standard.currentIndexChanged.connect(self._standard_changed)
        self.eval_standard_status = QLabel("评价日期自动读取今天")
        self.eval_standard_status.setWordWrap(True)
        self.eval_standard_status.setMinimumWidth(250)
        self.eval_product = QComboBox()
        self.eval_product.currentIndexChanged.connect(self._product_changed)
        self.eval_product.setVisible(False)
        self.selection_container = QWidget()
        self.selection_form = QFormLayout(self.selection_container)
        self.selection_form.setContentsMargins(0, 0, 0, 0)
        self.selection_form.setSpacing(6)
        self.selection_widgets: list[tuple[SelectionLevel, QComboBox]] = []
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
        self.generic_form_container = QWidget()
        generic_form = QFormLayout(self.generic_form_container)
        generic_form.setContentsMargins(0, 0, 0, 0)
        generic_form.addRow("产品/工序", self.selection_container)
        generic_form.addRow("单位名称", self.eval_organization)
        generic_form.addRow("评价备注", self.eval_notes)

        self.gb29446_form_container = QWidget()
        gb_form = QFormLayout(self.gb29446_form_container)
        gb_form.setContentsMargins(0, 0, 0, 0)
        #: 兼容性降级时需要按“行”隐藏煤种/选煤工艺/折算系数输入项。
        self.gb29446_form_layout = gb_form
        self.gb29446_organization = QLineEdit()
        self.gb29446_organization.setPlaceholderText("可选填写")
        self.gb29446_organization.textChanged.connect(self._gb29446_inputs_changed)
        self.gb29446_period = QComboBox()
        for period in GB29446_PERIOD_OPTIONS:
            self.gb29446_period.addItem(period, period)
        self.gb29446_period.currentIndexChanged.connect(self._gb29446_period_changed)
        self.gb29446_period.currentIndexChanged.connect(self._gb29446_inputs_changed)
        self.gb29446_custom_period = QLineEdit()
        self.gb29446_custom_period.setPlaceholderText("填写核算周期，例如：2026年第一季度")
        self.gb29446_custom_period.setVisible(False)
        self.gb29446_custom_period.textChanged.connect(self._gb29446_inputs_changed)
        self.gb29446_coal_type = QComboBox()
        self.gb29446_coal_type.currentIndexChanged.connect(self._gb29446_coal_changed)
        self.gb29446_coal_type.currentIndexChanged.connect(self._gb29446_inputs_changed)
        self.gb29446_process = QComboBox()
        self.gb29446_process.currentIndexChanged.connect(self._gb29446_process_changed)
        self.gb29446_process.currentIndexChanged.connect(self._gb29446_inputs_changed)
        self.gb29446_electricity = QLineEdit()
        self.gb29446_electricity.setPlaceholderText("输入统计期选煤电力消耗量")
        self.gb29446_electricity.textChanged.connect(self._gb29446_inputs_changed)
        self.gb29446_raw_coal = QLineEdit()
        self.gb29446_raw_coal.setPlaceholderText("输入统计期入选原煤量")
        self.gb29446_raw_coal.textChanged.connect(self._gb29446_inputs_changed)
        self.gb29446_factor = QLineEdit()
        self.gb29446_factor.setReadOnly(True)
        self.gb29446_factor.setPlaceholderText("根据煤种和工艺自动匹配")
        self.gb29446_notes = QLineEdit()
        self.gb29446_notes.setPlaceholderText("可选")
        self.gb29446_notes.textChanged.connect(self._gb29446_inputs_changed)
        period_row = QWidget()
        period_layout = QVBoxLayout(period_row)
        period_layout.setContentsMargins(0, 0, 0, 0)
        period_layout.setSpacing(4)
        period_layout.addWidget(self.gb29446_period)
        period_layout.addWidget(self.gb29446_custom_period)
        gb_form.addRow("企业名称（可选）", self.gb29446_organization)
        gb_form.addRow("核算周期", period_row)
        gb_form.addRow("煤种", self.gb29446_coal_type)
        gb_form.addRow("选煤工艺", self.gb29446_process)
        gb_form.addRow("统计期选煤电力消耗量 E_d（kW·h）", self.gb29446_electricity)
        gb_form.addRow("统计期入选原煤量 m（t）", self.gb29446_raw_coal)
        gb_form.addRow("折算系数 k（自动匹配，只读）", self.gb29446_factor)
        gb_form.addRow("备注", self.gb29446_notes)

        standard_row = QHBoxLayout()
        standard_row.addWidget(QLabel("标准"))
        standard_row.addWidget(self.eval_standard, 3)
        standard_row.addWidget(QLabel("版本"))
        standard_row.addWidget(self.eval_selection_mode, 2)
        standard_row.addWidget(self.eval_standard_status, 3)
        form.addRow(standard_row)
        form_layout.addLayout(form)
        form_layout.addWidget(self.generic_form_container)
        form_layout.addWidget(self.gb29446_form_container)
        # 规则数据不完整/版本不兼容时的显式中文提示；正常 r2 规则下始终隐藏。
        self.gb29446_incompatibility_message = QLabel(GB29446_RULE_INCOMPATIBLE_MESSAGE)
        self.gb29446_incompatibility_message.setObjectName("gb29446RuleIncompatibleMessage")
        self.gb29446_incompatibility_message.setWordWrap(True)
        self.gb29446_incompatibility_message.setStyleSheet("color: #b42318; font-weight: bold;")
        self.gb29446_incompatibility_message.setVisible(False)
        form_layout.addWidget(self.gb29446_incompatibility_message)
        layout.addWidget(form_card)

        self.input_controls_container = QWidget()
        input_controls_layout = QVBoxLayout(self.input_controls_container)
        input_controls_layout.setContentsMargins(0, 0, 0, 0)
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
        self.input_tabs.addTab(self.eval_inputs, "适用条件/修正参数")
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
        self.input_hint = input_hint
        input_hint.setWordWrap(True)
        input_controls_layout.addWidget(input_hint)
        input_controls_layout.addWidget(self.input_tabs, 1)

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
        self.calculate_button = calculate
        # clicked 会传 checked(bool)；用无参 lambda 接线，避免它落进 request 参数。
        calculate.clicked.connect(lambda: self.calculate_evaluation())
        buttons.addWidget(add_energy)
        buttons.addWidget(add_product)
        input_controls_layout.addLayout(buttons)
        layout.addWidget(self.input_controls_container)
        action_row = QHBoxLayout()
        action_row.addStretch()
        action_row.addWidget(calculate)
        layout.addLayout(action_row)

        self.generic_result_section, generic_result_layout = self._card()
        generic_result_layout.addWidget(QLabel("评价结果"))
        self.eval_results = QTableWidget(0, 14)
        self.eval_results.setHorizontalHeaderLabels(
            ["指标", "实际值", "单位", "1级基础", "2级基础", "3级基础", "1级修正", "2级修正", "3级修正", "判定", "警告", "依据页码", "条款/表号", "来源"]
        )
        self._configure_table(self.eval_results)
        self.eval_results.setMinimumHeight(220)
        self.eval_summary = QLabel("等级汇总：尚未计算")
        generic_result_layout.addWidget(self.eval_summary)
        generic_result_layout.addWidget(self.eval_results, 1)
        layout.addWidget(self.generic_result_section, 1)

        self.gb29446_result_section, gb_result_section_layout = self._card()
        gb_result_section_layout.addWidget(QLabel("二、评价结果"))
        self.gb29446_result_card = QFrame()
        self.gb29446_result_card.setObjectName("card")
        gb29446_layout = QVBoxLayout(self.gb29446_result_card)
        gb_result_heading = QLabel("计算完成后显示本次评价结果")
        gb_result_heading.setWordWrap(True)
        gb29446_layout.addWidget(gb_result_heading)
        metrics = QHBoxLayout()
        ed_card, ed_layout = self._card()
        ed_layout.addWidget(QLabel("选煤电力单耗 e_d"))
        self.gb29446_result_ed = QLabel("— kW·h/t")
        self.gb29446_result_ed.setProperty("class", "metric")
        ed_layout.addWidget(self.gb29446_result_ed)
        grade_card, grade_layout = self._card()
        grade_layout.addWidget(QLabel("电耗等级"))
        self.gb29446_result_grade = QLabel("—")
        self.gb29446_result_grade.setProperty("class", "metric")
        grade_layout.addWidget(self.gb29446_result_grade)
        metrics.addWidget(ed_card)
        metrics.addWidget(grade_card)
        gb29446_layout.addLayout(metrics)
        self.gb29446_result_message = QLabel("尚未计算")
        self.gb29446_result_message.setWordWrap(True)
        gb29446_layout.addWidget(self.gb29446_result_message)
        gb_result_section_layout.addWidget(self.gb29446_result_card)
        layout.addWidget(self.gb29446_result_section)

        self.gb29446_explanation_section, explanation_layout = self._card()
        explanation_layout.addWidget(QLabel("三、计算与判定说明"))
        self.gb29446_explanation = QLabel("完成计算后显示本次代入计算和判定阈值。")
        self.gb29446_explanation.setWordWrap(True)
        self.gb29446_explanation.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        explanation_layout.addWidget(self.gb29446_explanation)
        layout.addWidget(self.gb29446_explanation_section)

        self.gb29446_basis_section, basis_layout = self._card()
        basis_layout.addWidget(QLabel("四、标准依据"))
        self.gb29446_basis = QLabel("完成计算后显示本次评价的标准依据。")
        self.gb29446_basis.setWordWrap(True)
        basis_layout.addWidget(self.gb29446_basis)
        self.gb29446_basis_open = QPushButton("查看标准原文")
        self.gb29446_basis_open.clicked.connect(self.open_selected_standard_for_evaluation)
        basis_layout.addWidget(self.gb29446_basis_open, 0, Qt.AlignmentFlag.AlignLeft)
        self.gb29446_scope_toggle = QPushButton("统计范围说明 ▸")
        self.gb29446_scope_toggle.setCheckable(True)
        self.gb29446_scope_details = QLabel(_gb29446_statistics_scope_text())
        self.gb29446_scope_details.setWordWrap(True)
        self.gb29446_scope_details.setVisible(False)
        self.gb29446_scope_toggle.toggled.connect(
            lambda expanded: (
                self.gb29446_scope_details.setVisible(expanded),
                self.gb29446_scope_toggle.setText("统计范围说明 ▾" if expanded else "统计范围说明 ▸"),
            )
        )
        basis_layout.addWidget(self.gb29446_scope_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        basis_layout.addWidget(self.gb29446_scope_details)

        layout.addWidget(self.gb29446_basis_section)
        self._sync_mode_buttons()
        return page

    def _build_records(self) -> QWidget:
        page, layout = self._page("评价记录")
        controls = QHBoxLayout()
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self.refresh_records)
        view = QPushButton("查看原记录")
        view.clicked.connect(self.view_selected_record)
        recalculate = QPushButton("基于此记录重新评价")
        recalculate.clicked.connect(self.recalculate_selected_record)
        export = QPushButton("导出Excel")
        export.clicked.connect(self.export_selected_record)
        delete = QPushButton("删除记录")
        delete.clicked.connect(self.delete_selected_record)
        controls.addWidget(refresh)
        controls.addWidget(view)
        controls.addWidget(recalculate)
        controls.addStretch()
        controls.addWidget(export)
        controls.addWidget(delete)
        layout.addLayout(controls)
        self.record_table = QTableWidget(0, 6)
        self.record_table.setHorizontalHeaderLabels(["评价时间", "评价日期", "标准", "企业/单位", "项目", "产品/煤种"])
        self._configure_table(self.record_table)
        layout.addWidget(self.record_table, 1)
        return page

    def _build_import(self) -> QWidget:
        page, layout = self._page("Excel导入")
        explanation = QLabel(
            "Excel只作为录入适配器：软件按模板逐单元格校验，转换成与手工录入相同的评价请求，"
            "再交给同一套计算引擎。Excel自身不计算折算系数、单位产品能耗或等级。"
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        controls = QHBoxLayout()
        template = QPushButton("保存导入模板")
        template.clicked.connect(self.save_import_template)
        template_gb = QPushButton("保存 GB29446 专用模板")
        template_gb.clicked.connect(self.save_gb29446_template)
        validate = QPushButton("选择并校验Excel")
        validate.clicked.connect(self.validate_import_workbook)
        self.import_commit_button = QPushButton("确认导入并评价")
        self.import_commit_button.setEnabled(False)
        self.import_commit_button.clicked.connect(self.evaluate_import)
        controls.addWidget(template)
        controls.addWidget(template_gb)
        controls.addWidget(validate)
        controls.addStretch()
        controls.addWidget(self.import_commit_button)
        layout.addLayout(controls)
        self.import_status = QLabel("尚未选择文件")
        self.import_status.setWordWrap(True)
        layout.addWidget(self.import_status)
        self.import_summary = QLabel("")
        self.import_summary.setWordWrap(True)
        self.import_summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.import_summary.setVisible(False)
        layout.addWidget(self.import_summary)
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
        # 启动/刷新后如实暴露标准包对账状态（非阻断，不弹模态框）。
        self._show_package_reconciliation_notice()

    def refresh_home(self) -> None:
        today = date.today()
        standards = self.context.application.list_current_standards(today)
        all_standards = self.context.application.list_all_standards()
        records = self.context.application.list_recent_evaluations(10)
        scoped_standards = [item for item in all_standards if item.lifecycle_status is not LifecycleStatus.OBSOLETE]
        self.home_standard_count.setText(f"{len(standards)}/{len(scoped_standards)}")
        # 「可正式评价」只由正式评价范围注册表决定，与标准文档是否已发布无关。
        evaluable = filter_formally_evaluable(self.context.application.list_library_standards())
        self.home_formal_scope_count.setText(f"{len(evaluable)} 项")
        if evaluable:
            scope_names = "、".join(f"{item.number} {item.title}" for item in evaluable)
            self.home_scope_label.setText(
                f"正式评价范围：{scope_names}。软件只对已纳入正式评价范围的标准给出正式评价结论。"
            )
            self.home_start_evaluation.setEnabled(True)
        else:
            self.home_scope_label.setText("本机标准库中没有已纳入正式评价范围的标准，请先更新标准数据。")
            self.home_start_evaluation.setEnabled(False)
        self.home_evaluation_count.setText(str(self.context.application.count_evaluations()))
        package_manifest = self.context.application.latest_package_manifest()
        self.home_package_version.setText(
            package_manifest.get("data_version", "未知") if package_manifest else "未安装"
        )
        self.home_recent.setRowCount(0)
        for record in records:
            row = self.home_recent.rowCount()
            self.home_recent.insertRow(row)
            # 存储为 UTC；普通页面按本机时区显示到秒，不显示微秒。
            values = [
                format_local_datetime(record.created_at),
                record.standard_number,
                record.organization_name or record.project_name or "",
            ]
            for column, value in enumerate(values):
                cell = _item(value)
                cell.setData(Qt.ItemDataRole.UserRole, record.evaluation_id)
                self.home_recent.setItem(row, column, cell)

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
            # 「标准状态」只描述标准文档本身的效力，不再用它表达软件能否正式评价；
            # 软件评价支持状态是独立的一列，来源是正式评价范围注册表。
            if standard.publication_status is not PublicationStatus.PUBLISHED:
                status = "待确认"
            elif standard.effective_date > date.today():
                status = "尚未实施（仅预览）"
            elif standard.is_effective_on(date.today()):
                status = "当前有效"
            else:
                status = "历史/已替代"
            official_url = official_source_url(standard.id)
            values = [
                standard.number,
                standard.title,
                status,
                standard.version,
                format_local_date(standard.effective_date),
                evaluation_support_label(standard),
                evaluation_scope_summary(standard),
                OFFICIAL_SOURCE_PLATFORM_NAME if official_url else NO_OFFICIAL_SOURCE_LABEL,
            ]
            for column, value in enumerate(values):
                item = _item(value)
                item.setData(Qt.ItemDataRole.UserRole, standard.id)
                if column == 6:
                    item.setToolTip(evaluation_scope_text(standard))
                elif column == 7:
                    item.setToolTip(official_url or NO_OFFICIAL_SOURCE_LABEL)
                self.standard_table.setItem(row, column, item)
        self.refresh_standard_detail()

    def _selected_library_standard_id(self) -> str | None:
        """当前标准库选中的标准 id；未选择时返回 ``None``。"""

        row = self.standard_table.currentRow()
        cell = self.standard_table.item(row, 0) if row >= 0 else None
        return cell.data(Qt.ItemDataRole.UserRole) if cell is not None else None

    def _library_standard(self, standard_id: str | None) -> StandardDefinition | None:
        if not standard_id:
            return None
        return next(
            (item for item in self.context.application.list_library_standards() if item.id == standard_id),
            None,
        )

    def refresh_standard_detail(self) -> None:
        """Show the selected standard's products, limits, scope and official source."""
        if not hasattr(self, "standard_indicator_table"):
            return
        self.standard_indicator_table.setRowCount(0)
        standard_id = self._selected_library_standard_id()
        standard = self._library_standard(standard_id)
        if standard is None:
            self.standard_detail_label.setText("选择标准后查看指标、限额和评价范围")
            self.standard_evaluate_button.setEnabled(False)
            self.standard_official_button.setEnabled(False)
            self.standard_official_status.setText("请先选择标准")
            return
        # 「软件评价支持状态」只来自正式评价范围注册表；「标准状态」只描述文档效力。
        status = "已发布" if standard.publication_status is PublicationStatus.PUBLISHED else "待确认"
        self.standard_detail_label.setText(
            f"{standard.number} {standard.title}；标准状态：{status}；"
            f"软件评价支持状态：{evaluation_support_label(standard)}；"
            f"评价范围：{evaluation_scope_text(standard)}"
        )
        official_url = official_source_url(standard.id)
        self.standard_official_button.setEnabled(official_url is not None)
        self.standard_official_button.setToolTip(official_url or NO_OFFICIAL_SOURCE_LABEL)
        self.standard_official_status.setText(
            OFFICIAL_SOURCE_PLATFORM_NAME if official_url else NO_OFFICIAL_SOURCE_LABEL
        )
        # 未纳入正式评价范围的标准不提供可执行的评价入口。
        supported = supports_formal_evaluation(standard.id)
        self.standard_evaluate_button.setEnabled(supported)
        self.standard_evaluate_button.setToolTip(
            "用该标准发起正式评价。"
            if supported
            else f"该标准{FORMAL_EVALUATION_UNSUPPORTED_LABEL}，不能发起正式评价。"
        )

        def limit_value(expression):
            if expression is None:
                return "—"
            return expression.value if expression.op == "constant" else "公式/条件"

        for product in standard.products:
            for indicator in product.indicators:
                base = indicator.base_thresholds or indicator.thresholds
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

    def _formally_evaluable_standards(self) -> list[StandardDefinition]:
        """当前选择方式下**可以正式评价**的标准（正式评价范围注册表决定）。"""

        return filter_formally_evaluable(self._standards_for_selection())

    def _formal_scope_hint(self) -> str:
        """用于说明“为什么只有这些标准可选”的中文提示（来自注册表，不写死编号）。"""

        evaluable = filter_formally_evaluable(self.context.application.list_library_standards())
        if not evaluable:
            return "本机标准库中没有已纳入正式评价范围的标准，请先更新标准数据。"
        names = "、".join(f"{item.number} {item.title}" for item in evaluable)
        return f"本版本正式评价范围：{names}。"

    def refresh_standard_combo(self) -> None:
        selected = self.eval_standard.currentData() if self.eval_standard.count() else None
        self.eval_standard.blockSignals(True)
        self.eval_standard.clear()
        # 库里“有”这个标准 ≠ 软件“正式支持评价”这个标准。下拉框只提供正式评价
        # 范围内的标准，其余标准仍留在标准库中作为目录/参考资料。
        for standard in self._formally_evaluable_standards():
            self.eval_standard.addItem(f"{standard.number} {standard.title}", standard.id)
        restored = False
        if selected:
            index = self.eval_standard.findData(selected)
            if index >= 0:
                self.eval_standard.setCurrentIndex(index)
                restored = True
        if not restored and self.eval_standard.count():
            # Editable combo boxes keep an empty edit line after clear(); set
            # the first valid standard explicitly so the default really is
            # the first standard in the newly selected version scope.
            self.eval_standard.setCurrentIndex(0)
        self.eval_standard.blockSignals(False)
        self.eval_standard.setToolTip(self._formal_scope_hint())
        self._standard_changed()

    @staticmethod
    def _display_product_name(product, product_name_counts: Counter[str]) -> str:
        display_name = product.name
        if product_name_counts[product.name] > 1:
            indicator_names = "、".join(indicator.name for indicator in product.indicators)
            display_name = f"{product.name}（指标：{indicator_names}）"
        return display_name

    def _selection_levels_for_standard(self) -> list[SelectionLevel]:
        if self.current_standard and self.current_standard.selection_schema:
            return list(self.current_standard.selection_schema)
        # Legacy definitions have one flat product/process list.  Treat it as
        # a one-level schema so all old packages use the same selector code.
        return [SelectionLevel(key="product", label="产品/工序", required=True)]

    def _clear_selection_form(self) -> None:
        while self.selection_form.count():
            item = self.selection_form.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.selection_widgets = []

    def _product_selection_value(self, product, level: SelectionLevel) -> str:
        value = product.selection_values.get(level.key)
        if value is not None and str(value).strip():
            return str(value).strip()
        if level.key == GB29446_COAL_TYPE_KEY:
            # “煤种”只能来自规则自身的选择元数据。旧定义缺少该字段时，回落到
            # ``product.name`` 会凭空造出一个不存在的煤种，因此这里如实返回空值，
            # 由兼容性判定拒绝正式评价。
            return ""
        # Fallback for legacy rules without selection metadata.
        return product.name

    def _selection_raw_value(self, level_index: int) -> str | None:
        if level_index < 0 or level_index >= len(self.selection_widgets):
            return None
        _level, combo = self.selection_widgets[level_index]
        data = combo.currentData()
        if not data:
            return None
        text = str(data)
        if text.startswith("__product__:"):
            product_id = text.split(":", 1)[1]
            product = next(
                (item for item in (self.current_standard.products if self.current_standard else []) if item.id == product_id),
                None,
            )
            return self._product_selection_value(product, self.selection_widgets[level_index][0]) if product else None
        if text.startswith("__value__:"):
            return text.split(":", 1)[1]
        return text

    def _products_matching_selection(self, before_level: int | None = None) -> list:
        if self.current_standard is None:
            return []
        products = list(self.current_standard.products)
        limit = len(self.selection_widgets) if before_level is None else before_level
        for index in range(limit):
            selected = self._selection_raw_value(index)
            if selected is None:
                continue
            level = self.selection_widgets[index][0]
            products = [
                product for product in products
                if self._product_selection_value(product, level) == selected
            ]
        return products

    def _populate_selection_levels(self, start_index: int = 0) -> None:
        if self.current_standard is None:
            return
        levels = self._selection_levels_for_standard()
        product_name_counts = Counter(product.name for product in self.current_standard.products)
        for index in range(start_index, len(self.selection_widgets)):
            level, combo = self.selection_widgets[index]
            old_data = combo.currentData()
            candidates = self._products_matching_selection(index)
            grouped: dict[str, list] = {}
            for product in candidates:
                grouped.setdefault(self._product_selection_value(product, level), []).append(product)
            combo.blockSignals(True)
            combo.clear()
            if not grouped:
                combo.addItem("暂无可选项", None)
            else:
                for value, group in grouped.items():
                    # At the final level retain the old duplicate-product
                    # behaviour by showing indicator names and binding the
                    # item directly to one product ID.
                    if index == len(levels) - 1 and len(group) > 1:
                        for product in group:
                            combo.addItem(self._display_product_name(product, product_name_counts), f"__product__:{product.id}")
                    else:
                        combo.addItem(value, f"__value__:{value}")
            if old_data is not None:
                restored = combo.findData(old_data)
                if restored >= 0:
                    combo.setCurrentIndex(restored)
            if combo.currentIndex() < 0 and combo.count() and combo.itemData(0) is not None:
                combo.setCurrentIndex(0)
            combo.blockSignals(False)

    def _sync_hidden_product(self) -> None:
        if self.current_standard is None:
            self.eval_product.setCurrentIndex(-1)
            return
        product_id: str | None = None
        if self.selection_widgets:
            last_data = self.selection_widgets[-1][1].currentData()
            if isinstance(last_data, str) and last_data.startswith("__product__:"):
                product_id = last_data.split(":", 1)[1]
            else:
                products = self._products_matching_selection()
                if len(products) == 1:
                    product_id = products[0].id
        index = self.eval_product.findData(product_id) if product_id else -1
        self.eval_product.blockSignals(True)
        self.eval_product.setCurrentIndex(index)
        self.eval_product.blockSignals(False)

    def _rebuild_selection_widgets(self) -> None:
        self._clear_selection_form()
        if self.current_standard is None:
            return
        for index, level in enumerate(self._selection_levels_for_standard()):
            combo = QComboBox()
            combo.setMinimumWidth(280)
            combo.setPlaceholderText(f"请选择{level.label}")
            combo.currentIndexChanged.connect(
                lambda _value=0, level_index=index: self._selection_level_changed(level_index)
            )
            self.selection_form.addRow(level.label, combo)
            self.selection_widgets.append((level, combo))
        self._populate_selection_levels(0)
        self._sync_hidden_product()

    def _selection_level_changed(self, level_index: int) -> None:
        self._populate_selection_levels(level_index + 1)
        self._sync_hidden_product()
        self._refresh_input_table()

    def _is_gb29446(self) -> bool:
        return self.current_standard is not None and self.current_standard.id == GB29446_STANDARD_ID

    def _gb29446_definition(self, standard_id: str) -> StandardDefinition | None:
        """解析用于正式评价的 GB 29446 定义（当前加载的优先，其次已发布/标准库）。"""

        if self.current_standard is not None and self.current_standard.id == standard_id:
            return self.current_standard
        definition = self.context.application.get_published_standard(standard_id)
        if definition is None:
            definition = self.context.application.get_standard(standard_id)
        return definition

    def _gb29446_rule_incompatibility(self, standard_id: str | None = None) -> str | None:
        """GB 29446 规则不可用于正式评价时返回中文原因，否则返回 ``None``。

        未安装该标准时返回 ``None``：那属于既有的“标准不可用”路径，不应改写成
        规则不兼容。
        """

        target = standard_id
        if target is None and self.current_standard is not None:
            target = self.current_standard.id
        if target != GB29446_STANDARD_ID:
            return None
        try:
            definition = self._gb29446_definition(target)
        except Exception:
            # 兼容性探测本身失败时不改变既有错误路径（不得让界面崩溃）。
            return None
        if definition is None:
            return None
        if gb29446_rule_is_compatible(definition):
            return None
        return GB29446_RULE_INCOMPATIBLE_MESSAGE

    def _apply_gb29446_rule_compatibility(self) -> None:
        """按当前 GB 29446 规则是否兼容，显示/隐藏选择器与提示。

        不兼容时：显示中文提示、隐藏煤种与选煤工艺选择器（以及自动匹配的折算系数）、
        清空选择并禁用正式计算按钮；兼容时恢复原样。正常 r2 路径行为不变。
        """

        incompatible = self._is_gb29446() and not gb29446_rule_is_compatible(self.current_standard)
        self.gb29446_rule_compatible = not incompatible
        message = getattr(self, "gb29446_incompatibility_message", None)
        if message is not None:
            message.setVisible(incompatible)
        form = getattr(self, "gb29446_form_layout", None)
        if form is not None:
            for widget in (self.gb29446_coal_type, self.gb29446_process, self.gb29446_factor):
                form.setRowVisible(widget, not incompatible)
        for widget in (self.gb29446_coal_type, self.gb29446_process, self.gb29446_factor):
            widget.setEnabled(not incompatible)
        if incompatible:
            for combo in (self.gb29446_coal_type, self.gb29446_process):
                combo.blockSignals(True)
                combo.clear()
                combo.blockSignals(False)
            self.gb29446_factor.setText("")
            self.gb29446_result_message.setText(GB29446_RULE_INCOMPATIBLE_MESSAGE)
        if hasattr(self, "calculate_button"):
            self.calculate_button.setEnabled(not incompatible)

    def _set_evaluation_view(self) -> None:
        is_gb29446 = self._is_gb29446()
        self.generic_form_container.setVisible(not is_gb29446)
        self.gb29446_form_container.setVisible(is_gb29446)
        self.input_controls_container.setVisible(not is_gb29446)
        self.generic_result_section.setVisible(not is_gb29446)
        self.gb29446_result_section.setVisible(is_gb29446)
        self.gb29446_explanation_section.setVisible(is_gb29446)
        self.gb29446_basis_section.setVisible(is_gb29446)

    def _refresh_official_source_controls(self) -> None:
        """「查看标准原文」只使用已登记的官方来源；未登记时禁用并如实说明。"""

        standard_id = self.eval_standard.currentData() if hasattr(self, "eval_standard") else None
        url = official_source_url(standard_id) if standard_id else None
        button = getattr(self, "eval_standard_open", None)
        if button is not None:
            button.setEnabled(url is not None)
            button.setToolTip(url or NO_OFFICIAL_SOURCE_LABEL)
        status = getattr(self, "eval_official_status", None)
        if status is not None:
            status.setText(OFFICIAL_SOURCE_PLATFORM_NAME if url else NO_OFFICIAL_SOURCE_LABEL)
        support = getattr(self, "eval_support_label", None)
        if support is not None:
            support.setText(evaluation_support_label(standard_id) if standard_id else "—")

    @staticmethod
    def _gb29446_factor_map(product) -> dict[str, Decimal]:
        """Read the Appendix A lookup from the rule definition for the selector."""
        factors: dict[str, Decimal] = {}
        for indicator in product.indicators:
            for display in indicator.display_calculations:
                if display.key != "process_factor" or display.formula.op != "lookup":
                    continue
                for row in display.formula.rows:
                    condition = row.condition
                    expression = row.expression
                    if (
                        condition.op == "eq"
                        and condition.field == "washing_process"
                        and expression.op == "constant"
                        and condition.value is not None
                        and expression.value is not None
                    ):
                        factors[str(condition.value)] = Decimal(str(expression.value))
        return factors

    def _populate_gb29446_coal_types(self) -> None:
        combo = self.gb29446_coal_type
        previous = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        if self.current_standard is not None:
            seen: set[str] = set()
            for product in self.current_standard.products:
                # 只使用规则声明的煤种；绝不使用 product.name 冒充煤种。
                coal_type = str(product.selection_values.get(GB29446_COAL_TYPE_KEY) or "").strip()
                if coal_type and coal_type not in seen:
                    combo.addItem(coal_type, product.id)
                    seen.add(coal_type)
        restored = combo.findText(previous) if previous else -1
        if restored >= 0:
            combo.setCurrentIndex(restored)
        elif combo.count():
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _refresh_gb29446_processes(self, product=None) -> None:
        combo = self.gb29446_process
        previous = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        factors = self._gb29446_factor_map(product) if product is not None else {}
        process_definition = next(
            (item for item in product.input_definitions if item.key == "washing_process"),
            None,
        ) if product is not None else None
        choices = (
            [choice for choice in process_definition.choices if choice in factors]
            if process_definition is not None and process_definition.choices
            else list(factors)
        )
        combo.addItem("请选择选煤工艺", None)
        for choice in choices:
            combo.addItem(choice, choice)
        restored = combo.findData(previous) if previous else -1
        if restored >= 0:
            combo.setCurrentIndex(restored)
        combo.blockSignals(False)
        self._update_gb29446_factor(factors)

    def _update_gb29446_factor(self, factors: dict[str, Decimal] | None = None) -> None:
        product = self._selected_product()
        factors = factors if factors is not None else self._gb29446_factor_map(product) if product else {}
        process = self.gb29446_process.currentData()
        factor = factors.get(str(process)) if process else None
        self.gb29446_factor.setText(format(factor, "f") if factor is not None else "")

    def _gb29446_coal_changed(self, _index: int = 0) -> None:
        product_id = self.gb29446_coal_type.currentData()
        if product_id and self.eval_product.currentData() != product_id:
            self._select_product_by_id(str(product_id))
        else:
            self._refresh_gb29446_processes(self._selected_product())

    def _gb29446_process_changed(self, _index: int = 0) -> None:
        self._update_gb29446_factor()

    def _gb29446_period_changed(self, _index: int = 0) -> None:
        is_custom = self.gb29446_period.currentData() == "自定义"
        self.gb29446_custom_period.setVisible(is_custom)

    def _clear_gb29446_result(self) -> None:
        self.last_result_id = None
        self.gb29446_result_ed.setText("— kW·h/t")
        self.gb29446_result_grade.setText("—")
        self.gb29446_result_message.setText("尚未计算")
        self.gb29446_explanation.setText("完成计算后显示本次代入计算和判定阈值。")
        self.gb29446_basis.setText("完成计算后显示本次评价的标准依据。")

    def _gb29446_inputs_changed(self, *_args) -> None:
        if self._is_gb29446():
            self._clear_gb29446_result()

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
                display_name = self._display_product_name(product, product_name_counts)
                self.eval_product.addItem(display_name, product.id)
            self.eval_date.setDate(QDate.currentDate())
            warning = self.current_standard.selection_warning(date.today())
            # 标准编号与名称已经在下拉框里显示，这里只显示状态，避免同一句话重复两遍。
            self.eval_standard_status.setText(warning if warning else "当前有效")
        else:
            self.eval_standard_status.setText("当前选择方式下没有可正式评价的标准")
        self.eval_product.blockSignals(False)
        self._refresh_official_source_controls()
        self._rebuild_selection_widgets()
        self._set_evaluation_view()
        self._apply_gb29446_rule_compatibility()
        if self._is_gb29446():
            if self.gb29446_rule_compatible:
                self._populate_gb29446_coal_types()
                product_id = self.gb29446_coal_type.currentData()
                if product_id:
                    self._select_product_by_id(str(product_id))
                else:
                    self._refresh_input_table()
            else:
                # 规则不完整：不填充假“煤种”，也不渲染空的工艺下拉框。
                self._refresh_gb29446_processes(None)
            self._clear_gb29446_result()
            if not self.gb29446_rule_compatible:
                self.gb29446_result_message.setText(GB29446_RULE_INCOMPATIBLE_MESSAGE)
        else:
            self._refresh_input_table()

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

    def _select_product_by_id(self, product_id: str) -> bool:
        product = next(
            (item for item in (self.current_standard.products if self.current_standard else []) if item.id == product_id),
            None,
        )
        if product is None:
            return False
        hidden_index = self.eval_product.findData(product_id)
        if hidden_index < 0:
            return False
        self.eval_product.blockSignals(True)
        self.eval_product.setCurrentIndex(hidden_index)
        self.eval_product.blockSignals(False)
        if not self.selection_widgets:
            self._refresh_input_table()
            return True
        levels = self._selection_levels_for_standard()
        for index, (level, combo) in enumerate(self.selection_widgets):
            value = self._product_selection_value(product, level)
            item_index = combo.findData(f"__value__:{value}")
            if index == len(levels) - 1:
                duplicate_index = combo.findData(f"__product__:{product.id}")
                if duplicate_index >= 0:
                    item_index = duplicate_index
            if item_index < 0:
                return False
            combo.blockSignals(True)
            combo.setCurrentIndex(item_index)
            combo.blockSignals(False)
            if index < len(levels) - 1:
                self._populate_selection_levels(index + 1)
        self._sync_hidden_product()
        self._refresh_input_table()
        return self.eval_product.currentData() == product_id

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
            if self._is_gb29446():
                self._refresh_gb29446_processes(None)
            return
        if self._is_gb29446():
            self._refresh_gb29446_processes(product)
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
            if definition.choices:
                selector = QComboBox()
                selector.addItem("请选择", "")
                for choice in definition.choices:
                    selector.addItem(choice, choice)
                self.eval_inputs.setCellWidget(row, 2, selector)
        self.energy_table.setEnabled(mode is InputMode.DETAIL)
        self.production_table.setEnabled(mode is InputMode.DETAIL)

    def _collect_request(self) -> EvaluationRequest:
        if self.current_standard is None:
            raise ValueError("没有可用标准")
        if self._is_gb29446():
            return self._collect_gb29446_request()
        product = self._selected_product()
        definitions = {}
        if product is not None:
            definitions.update({definition.key: definition for definition in product.input_definitions})
            for indicator in product.indicators:
                definitions.update({definition.key: definition for definition in indicator.input_definitions})
        inputs = {}
        for row in range(self.eval_inputs.rowCount()):
            key = self.eval_inputs.item(row, 0).text()
            selector = self.eval_inputs.cellWidget(row, 2)
            if isinstance(selector, QComboBox):
                selected = selector.currentData()
                value = str(selected).strip() if selected not in (None, "") else ""
            else:
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

    @staticmethod
    def _encode_gb29446_notes(period: str, custom_period: str, note: str) -> str:
        # Shared with the Excel adapter so both paths persist identical notes.
        return encode_period_notes(period, custom_period, note)

    @staticmethod
    def _decode_gb29446_notes(notes: str | None) -> tuple[str, str, str]:
        # Shared with the Excel adapter; historical decoding compatibility lives
        # in the application-layer codec.
        return decode_period_notes(notes)

    def _collect_gb29446_request(self) -> EvaluationRequest:
        assert self.current_standard is not None
        period = str(self.gb29446_period.currentData() or "全年")
        custom_period = self.gb29446_custom_period.text().strip()
        if period == "自定义" and not custom_period:
            raise ValueError("请填写自定义核算周期。")
        product_id = self.gb29446_coal_type.currentData()
        if not product_id:
            raise ValueError("请选择煤种。")
        product = next(
            (item for item in self.current_standard.products if item.id == product_id),
            None,
        )
        if product is None:
            raise ValueError("所选煤种没有对应的标准评价规则。")
        process = self.gb29446_process.currentData()
        if not process:
            raise ValueError("请选择选煤工艺。")
        inputs = {"washing_process": InputValue(value=str(process))}
        electricity = self.gb29446_electricity.text().strip()
        raw_coal = self.gb29446_raw_coal.text().strip()
        if electricity:
            inputs["electricity_consumption"] = InputValue(value=electricity, unit="kW·h")
        if raw_coal:
            inputs["raw_coal_input"] = InputValue(value=raw_coal, unit="t")
        notes = self._encode_gb29446_notes(period, custom_period, self.gb29446_notes.text())
        return EvaluationRequest(
            evaluation_date=date.today(),
            standard_id=self.current_standard.id,
            product_id=product.id,
            selection_mode=self._selection_mode(),
            input_mode=InputMode.DETAIL,
            inputs=inputs,
            organization_name=self.gb29446_organization.text().strip() or None,
            notes=notes,
        )

    def calculate_evaluation(
        self, request: EvaluationRequest | None = None, checked: bool = False
    ) -> None:
        """计算并判级（GB 29446 专用页与通用页共用）。

        ``QPushButton.clicked`` 会附带 ``checked: bool`` 作为第一个位置参数。本方法
        的首个参数是**可选**的 ``EvaluationRequest``，所以 Qt 会把 ``False`` 当作
        request 传进来；若不识别，就会在 ``request.standard_id`` 上抛
        ``AttributeError``。该异常发生在下面的 ``try`` 之前，又会被 PySide6 吞掉，
        于是用户只看到"点了没反应"——既没有结果也没有记录。这里显式把 Bool 当作
        "没有请求"，并加一层兜底，保证槽函数永远不会静默失败。
        """
        if isinstance(request, bool):
            # QPushButton.clicked(bool) 传来的勾选状态，不是评价请求。
            request = None
        try:
            self._calculate_evaluation(request)
        except Exception as exc:  # noqa: BLE001 - 兜底，绝不静默
            _LOGGER.exception("计算评价时发生未预期错误")
            QMessageBox.critical(
                self,
                "计算失败",
                f"计算未完成（{type(exc).__name__}）。详细信息已写入日志，请重试。",
            )

    def _calculate_evaluation(self, request: EvaluationRequest | None) -> None:
        is_gb29446 = self._is_gb29446() if request is None else request.standard_id == GB29446_STANDARD_ID
        if is_gb29446:
            self._clear_gb29446_result()
            # FAIL-FAST：规则数据不完整/版本不兼容时，正式计算（含保存记录）必须
            # 在这里被明确拒绝，而不是给出笼统的“计算失败”，更不能生成假结论。
            reason = self._gb29446_rule_incompatibility(
                request.standard_id if request is not None else None
            )
            if reason is not None:
                self.gb29446_result_message.setText(reason)
                self.gb29446_explanation.setText(
                    "当前标准规则不能用于正式评价，因此未执行计算，也未生成评价记录。"
                )
                QMessageBox.warning(self, "标准规则不兼容", reason)
                return
        try:
            if request is None and self._is_gb29446():
                try:
                    request = self._collect_request()
                except ValueError as exc:
                    message = str(exc) if type(exc) is ValueError else "评价信息未通过校验，请检查核算周期、煤种、选煤工艺及输入数据。"
                    self.gb29446_result_message.setText(message)
                    QMessageBox.warning(self, "信息未填写", message)
                    return
            request = request or self._collect_request()
            is_preview = request.selection_mode is StandardSelectionMode.FUTURE
            result = self.context.application.preview_evaluation(request) if is_preview else self.context.application.evaluate(request)
        except Exception as exc:
            if is_gb29446:
                if type(exc) is ValueError:
                    self.gb29446_result_message.setText(f"无法计算：{exc}")
                    self.gb29446_explanation.setText("请根据提示修正评价数据后重新计算。")
                    QMessageBox.warning(self, "无法计算", str(exc))
                else:
                    message = "计算未完成，请检查输入数据、单位和选煤工艺后重试。"
                    self.gb29446_result_message.setText(message)
                    QMessageBox.critical(self, "无法计算", message)
            else:
                QMessageBox.critical(self, "无法计算", _friendly_error(exc, "计算和判级"))
            return
        self.last_result_id = None if is_preview else result.evaluation_id
        self._show_gb29446_result(request, result)
        if result.standard_id == "gb-29446-2019":
            self.eval_results.setRowCount(0)
            self.eval_summary.setText("")
            self.refresh_home()
            if not is_preview:
                self.refresh_records()
            if any(item.grade is Grade.INCOMPLETE for item in result.results):
                QMessageBox.warning(
                    self,
                    "无法计算",
                    "输入数据未通过校验，未生成电耗等级。请查看评价结果中的提示并修正。",
                )
                return
            message = "预览完成：尚未实施标准仅供参考，未保存正式评价记录。" if is_preview else "评价完成，已生成评价记录。"
            QMessageBox.information(self, "预览完成" if is_preview else "计算完成", message)
            return
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

    @staticmethod
    def _format_result_number(value: Decimal | None, places: int = 2) -> str:
        return "—" if value is None else f"{value:.{places}f}"

    @staticmethod
    def _format_explanation_number(value: Decimal | None) -> str:
        if value is None:
            return "—"
        rendered = format(value, "f")
        return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered

    @staticmethod
    def _gb29446_grade_label(grade: Grade) -> str:
        if grade is Grade.NOT_QUALIFIED:
            return "超出3级"
        return GRADE_LABELS[grade]

    def _gb29446_warning_for_display(
        self, request: EvaluationRequest, warning: str, snapshot: StandardDefinition | None = None,
    ) -> str:
        standard = snapshot if snapshot is not None else self.current_standard
        product = next(
            (
                item
                for item in (standard.products if standard else [])
                if item.id == request.product_id
            ),
            None,
        )
        labels = {
            "washing_process": "选煤工艺",
            "electricity_consumption": "统计期选煤电力消耗量 E_d",
            "raw_coal_input": "统计期入选原煤量 m",
            "actual.coking-coal": "选煤电力单耗 e_d",
            "actual.power-coal": "选煤电力单耗 e_d",
            "single_coal_single_process": "本次统计范围",
            "enterprise_status": "企业属性",
        }
        if product is not None:
            definitions = list(product.input_definitions)
            for indicator in product.indicators:
                definitions.extend(indicator.input_definitions)
            labels.update({definition.key: definition.label for definition in definitions})
        for key, label in sorted(labels.items(), key=lambda item: len(item[0]), reverse=True):
            warning = warning.replace(key, label)
        return warning

    @staticmethod
    def _gb29446_basis_for_display(item: IndicatorResult) -> str:
        lines = []
        for reference in item.source_references:
            clause = (reference.clause or "").split(" ", 1)[0]
            if clause in {"3.1", "3.2"} and reference.table:
                lines.append(f"等级依据：第{clause}条，{reference.table}")
            elif clause == "5.2" and reference.table:
                lines.append(f"计算依据：第{clause}条，{reference.table}")
            elif clause == "附录A" and reference.table:
                lines.append(f"折算系数依据：{clause}{reference.table}")
        return "\n".join(lines)

    def _show_gb29446_result(self, request: EvaluationRequest, result: EvaluationResult) -> None:
        if result.standard_id != "gb-29446-2019":
            return
        item = next(
            (
                row
                for row in result.results
                if row.indicator_id in {"GB_29446-2019.coking-coal", "GB_29446-2019.power-coal"}
            ),
            result.results[0] if result.results else None,
        )
        if item is None:
            self._clear_gb29446_result()
            return

        self.gb29446_basis.setText(self._gb29446_basis_for_display(item))
        if item.actual_value is None:
            self.gb29446_result_ed.setText("— kW·h/t")
            self.gb29446_result_grade.setText("—")
            self.gb29446_result_message.setText(
                "无法计算："
                + "；".join(self._gb29446_warning_for_display(request, warning) for warning in item.warnings)
            )
            self.gb29446_explanation.setText("请根据提示补全或修正评价数据后重新计算。")
            return

        actual = item.actual_value
        grade_label = self._gb29446_grade_label(item.grade)
        self.gb29446_result_ed.setText(f"{self._format_result_number(actual)} kW·h/t")
        self.gb29446_result_grade.setText(grade_label)
        self.gb29446_result_message.setText("")

        self.gb29446_explanation.setText(self._gb29446_saved_explanation(request, result, item))

    @staticmethod
    def _gb29446_saved_explanation(
        request: EvaluationRequest, result: EvaluationResult, item: IndicatorResult,
    ) -> str:
        """用普通用户语言说明本次代入的数据、公式、阈值和判定结果。

        只展示保存下来的输入与结果：不重新执行公式，也不重新判级。计算依据（E_d、m、
        选煤工艺与 k、``e_d = E_d × k / m``、分级阈值、判定结果、标准条款）全部保留，
        但不再堆叠内部追踪术语（rule_id / numeric_behavior 之类不出现在这里）。
        """
        actual = item.actual_value
        grade_label = MainWindow._gb29446_grade_label(item.grade)
        supplied_electricity = request.inputs.get("electricity_consumption")
        supplied_raw_coal = request.inputs.get("raw_coal_input")
        electricity = (
            Decimal(str(supplied_electricity.value))
            if supplied_electricity is not None
            else None
        )
        raw_coal = (
            Decimal(str(supplied_raw_coal.value))
            if supplied_raw_coal is not None
            else None
        )
        e0 = item.display_values.get("unadjusted_power_consumption")
        factor = item.display_values.get("process_factor")
        process = request.inputs.get("washing_process")
        process_name = str(process.value) if process is not None else "—"
        coal_type = "炼焦煤" if "coking" in item.indicator_id else "动力煤"

        lines: list[str] = []
        if request.input_mode is InputMode.DETAIL:
            electricity_text = (
                f"{MainWindow._format_explanation_number(electricity)} kW·h"
                if electricity is not None
                else "未填写"
            )
            raw_coal_text = (
                f"{MainWindow._format_explanation_number(raw_coal)} t"
                if raw_coal is not None
                else "未填写"
            )
            lines.append(
                f"本次评价输入：煤种 {coal_type}；选煤工艺 {process_name}；"
                f"统计期选煤电力消耗量 E_d = {electricity_text}；"
                f"统计期入选原煤量 m = {raw_coal_text}。"
            )
            if e0 is not None:
                lines.append(
                    f"未折算单位电耗 E_d/m：{MainWindow._format_result_number(e0)} kW·h/t"
                )
        else:
            # 直接录入口径：没有 E_d / m 明细，但公式依据照样说明。
            lines.append("本次评价输入：直接录入选煤电力单耗 e_d（已按 e_d = E_d × k / m 折算）。")
        lines.append(
            f"折算系数 k：{MainWindow._format_result_number(factor)}"
            f"（煤种 {coal_type}，选煤工艺 {process_name}；按标准附录A表A.1自动匹配）"
        )
        if electricity is not None and raw_coal is not None and factor is not None:
            lines.append(
                f"本次代入：e_d = {MainWindow._format_explanation_number(electricity)} × "
                f"{MainWindow._format_explanation_number(factor)} / "
                f"{MainWindow._format_explanation_number(raw_coal)} = "
                f"{MainWindow._format_explanation_number(actual)} kW·h/t"
            )
        else:
            lines.append("计算公式：e_d = E_d × k / m")
        lines.append(
            f"本次电耗 e_d = {MainWindow._format_result_number(actual)} kW·h/t；判级结果：{grade_label}。"
        )

        thresholds = item.corrected_thresholds
        threshold_names = (("LEVEL_1", "1级"), ("LEVEL_2", "2级"), ("LEVEL_3", "3级"))
        threshold_text = "；".join(
            f"{name} ≤ {MainWindow._format_result_number(thresholds.get(key))} kW·h/t"
            for key, name in threshold_names
            if thresholds.get(key) is not None
        )
        level3 = thresholds.get("LEVEL_3")
        if level3 is not None:
            threshold_text += f"；超出3级：> {MainWindow._format_result_number(level3)} kW·h/t"
        raw_value_line = f"原始计算值（未修约）：{MainWindow._format_explanation_number(actual)} kW·h/t"
        threshold_key = "LEVEL_3" if item.grade is Grade.NOT_QUALIFIED else item.grade.value
        threshold = thresholds.get(threshold_key)
        if threshold is not None:
            operator = ">" if item.grade is Grade.NOT_QUALIFIED else "≤"
            comparison_line = (
                f"判级比较：{MainWindow._format_explanation_number(actual)} {operator} "
                f"{MainWindow._format_explanation_number(threshold)}；结果：{grade_label}"
            )
        else:
            comparison_line = f"正式结果：{grade_label}"
        current_grade_line = (
            f"{raw_value_line}\n{comparison_line}\n"
            "判级采用原始计算值与等级限值直接比较；页面显示的小数位仅用于展示，不影响判级。"
        )
        if result.numeric_profile_id != "ECQUOTA_DECIMAL_FULL_VALUE_V1":
            # 未声明当前 Profile 的旧记录只展示当时结论，不替它补写当前比较语义。
            current_grade_line = (
                f"{raw_value_line}\n当时保存的结果：{grade_label}。"
                "正式比较语义见原记录技术详情。"
            )
        lines.extend((f"{coal_type}分级阈值：{threshold_text}", current_grade_line))
        # 标准依据属于本次说明的一部分，必须保留；与「四、标准依据」卡片同源。
        basis = MainWindow._gb29446_basis_for_display(item)
        if basis:
            lines.append("标准依据：" + "；".join(basis.splitlines()))
        return "\n".join(lines)

    def refresh_records(self) -> None:
        self.record_table.setRowCount(0)
        for record in self.context.application.list_recent_evaluations(200):
            row = self.record_table.rowCount()
            self.record_table.insertRow(row)
            values = [
                format_local_datetime(record.created_at),
                format_local_date(record.evaluation_date),
                f"{record.standard_number} {record.standard_title}".strip(),
                record.organization_name,
                record.project_name,
                record.product_name or "",
            ]
            for column, value in enumerate(values):
                cell = _item(value)
                cell.setData(Qt.ItemDataRole.UserRole, record.evaluation_id)
                if record.is_corrupted and column == 5:
                    # Explicit degradation: the row stays visible and states why
                    # its stored conclusion cannot be shown, instead of looking
                    # like a normal record.
                    cell.setText(f"{RECORD_CORRUPTED_LABEL}（{record.corruption_reason}）")
                    cell.setToolTip(record.corruption_reason)
                self.record_table.setItem(row, column, cell)

    def _selected_record_id(self) -> str | None:
        row = self.record_table.currentRow()
        cell = self.record_table.item(row, 0) if row >= 0 else None
        return cell.data(Qt.ItemDataRole.UserRole) if cell is not None else None

    def view_selected_record(self) -> None:
        evaluation_id = self._selected_record_id()
        if not evaluation_id:
            QMessageBox.warning(self, "未选择", "请选择一条评价记录。")
            return
        try:
            loaded = self.context.application.get_evaluation(evaluation_id)
        except StorageCorruptionError as exc:
            # Corrupted storage is not a deletion: never reuse the "不存在" wording
            # and never blame the user's input data.
            QMessageBox.warning(self, RECORD_CORRUPTED_LABEL, str(exc))
            return
        if loaded is None:
            QMessageBox.warning(self, "记录不存在", "该评价记录已被删除或不存在。")
            return
        request, result, snapshot = loaded
        dialog = QDialog(self)
        dialog.setWindowTitle("查看原记录")
        dialog.resize(820, 700)
        layout = QVBoxLayout(dialog)
        content = QTextEdit()
        content.setObjectName("record_detail_content")
        content.setReadOnly(True)
        lines = [
            f"{result.standard_number} {result.standard_title}",
            f"评价时间：{format_local_datetime(result.evaluated_at)}",
            f"评价日期：{format_local_date(request.evaluation_date)}",
            f"企业名称：{request.organization_name or '—'}",
            f"产品/煤种：{result.product_name}",
        ]
        if result.standard_id == "gb-29446-2019":
            period, custom, note = self._decode_gb29446_notes(request.notes)
            lines.extend([f"核算周期：{custom if period == '自定义' else period}", f"备注：{note or '—'}"])
            for key, label in [("washing_process", "选煤工艺"), ("electricity_consumption", "E_d"), ("raw_coal_input", "m")]:
                supplied = request.inputs.get(key)
                lines.append(f"{label}：{supplied.value if supplied is not None else '—'} {supplied.unit or '' if supplied is not None else ''}")
        else:
            product = next((p for p in snapshot.products if p.id == request.product_id), None)
            definitions = list(product.input_definitions) if product else []
            if product:
                definitions.extend(d for i in product.indicators for d in i.input_definitions)
            labels = {d.key: d.label for d in definitions}
            lines.append(f"备注：{request.notes or '—'}")
            lines.extend(f"{labels.get(key, '输入项')}：{value.value} {value.unit or ''}" for key, value in request.inputs.items())
        for item in result.results:
            grade = self._gb29446_grade_label(item.grade) if result.standard_id == "gb-29446-2019" else GRADE_LABELS[item.grade]
            lines.extend([f"指标：{item.indicator_name}", f"等级：{grade}"])
            if item.grade is Grade.INCOMPLETE:
                lines.append("数据不完整，未形成正常等级或符合性结论。")
            if item.actual_value is not None:
                lines.append(f"实际值：{self._format_explanation_number(item.actual_value)} {item.unit}")
                if result.standard_id == "gb-29446-2019":
                    lines.append(self._gb29446_saved_explanation(request, result, item))
                else:
                    lines.extend(f"{GRADE_LABELS[Grade(key)]}限值：{value} {item.unit}" for key, value in item.corrected_thresholds.items())
            if result.standard_id == "gb-29446-2019":
                lines.append(self._gb29446_basis_for_display(item))
                lines.extend(self._gb29446_warning_for_display(request, warning, snapshot) for warning in item.warnings)
            # 所有依据均来自保存的 Result；包括普通结果页未展开的条款。
            lines.append("标准依据：")
            lines.extend(
                f"{ref.standard_number}，第{ref.page}页，{ref.clause or ''} {ref.table or ''} {ref.note or ''}"
                for ref in item.source_references
            )
        content.setPlainText("\n".join(lines))
        layout.addWidget(content, 1)
        toggle = QPushButton("技术详情")
        toggle.setCheckable(True)
        technical = QTextEdit()
        technical.setObjectName("record_detail_technical")
        technical.setReadOnly(True)
        technical.setPlainText("\n".join([
            f"evaluation_id: {result.evaluation_id}",
            f"standard version: {snapshot.version}",
            f"rule_revision: {snapshot.rule_revision}",
            f"numeric_contract_version: {result.numeric_contract_version}",
            f"numeric_profile_id: {result.numeric_profile_id}",
            f"calculator_version: {result.calculator_version}",
            f"numeric_behavior_version: {result.numeric_behavior_version}",
            f"rule_snapshot_sha256: {result.rule_snapshot_sha256}",
            f"source_sha256: {snapshot.source_sha256}",
            "原 Request：" + request.model_dump_json(),
            "原 Result：" + result.model_dump_json(),
            "原 Rule Snapshot：" + snapshot.model_dump_json(),
        ]))
        technical.setVisible(False)
        toggle.toggled.connect(technical.setVisible)
        layout.addWidget(toggle)
        layout.addWidget(technical)
        buttons = QHBoxLayout()
        # 普通界面不再打开本机 PDF，只打开已登记的官方来源页面。
        official = official_source_url(result.standard_id)
        source = QPushButton(VIEW_OFFICIAL_SOURCE_BUTTON_TEXT)
        source.setObjectName("recordOfficialSourceButton")
        source.setEnabled(official is not None)
        source.setToolTip(official or NO_OFFICIAL_SOURCE_LABEL)
        source.clicked.connect(lambda: self.open_evaluation_standard_source(evaluation_id))
        close = QPushButton("关闭")
        close.clicked.connect(dialog.accept)
        buttons.addWidget(source)
        if official is None:
            buttons.addWidget(QLabel(NO_OFFICIAL_SOURCE_LABEL))
        buttons.addStretch()
        buttons.addWidget(close)
        layout.addLayout(buttons)
        previous = getattr(self, "record_detail_dialog", None)
        if previous is not None:
            previous.close()
            previous.deleteLater()
        self.record_detail_dialog = dialog
        dialog.open()

    def open_evaluation_standard_source(self, evaluation_id: str) -> None:
        """打开该评价所依据标准的**官方来源页面**（普通界面不再打开本机 PDF）。"""

        try:
            loaded = self.context.application.get_evaluation(evaluation_id)
        except StorageCorruptionError as exc:
            QMessageBox.warning(self, RECORD_CORRUPTED_LABEL, str(exc))
            return
        if loaded is None:
            QMessageBox.warning(self, "记录不存在", "该评价记录已被删除或不存在。")
            return
        _request, result, _snapshot = loaded
        self.open_official_source(result.standard_id)

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
            # “库里没有”“软件不正式支持”“当前选择方式取不到”是三件事，提示必须区分。
            # 后两种情况的调用方（基于此记录重新评价）在调用本方法之前已经给出模态提示，
            # 因此这里只更新页面上的状态文字：同一件事不说两遍，也不从加载函数里弹框。
            if self._library_standard(request.standard_id) is None:
                QMessageBox.warning(self, "标准不可用", "该评价使用的标准未安装，无法基于此记录重新评价。")
            elif not supports_formal_evaluation(request.standard_id):
                self.eval_standard_status.setText(
                    f"该标准{FORMAL_EVALUATION_UNSUPPORTED_LABEL}，不能重新发起正式评价；原记录仍可查看。"
                )
            else:
                self.eval_standard_status.setText(
                    "该标准在当前的“版本”选择方式下不可正式评价，请切换选择方式后重试。"
                )
            return False
        self.eval_standard.setCurrentIndex(standard_index)
        if not self._select_product_by_id(request.product_id):
            QMessageBox.warning(self, "产品不可用", "该评价使用的产品/工序当前不在标准规则中。")
            return False
        mode_index = self.eval_mode.findData(request.input_mode.value)
        if mode_index >= 0:
            self.eval_mode.setCurrentIndex(mode_index)
        self._sync_mode_buttons()
        self.eval_date.setDate(QDate(request.evaluation_date.year, request.evaluation_date.month, request.evaluation_date.day))
        self.eval_organization.setText(request.organization_name or "")
        self.eval_project.setText(request.project_name or "")
        self.eval_notes.setText(request.notes or "")
        if request.standard_id == "gb-29446-2019":
            coal_index = self.gb29446_coal_type.findData(request.product_id)
            if coal_index >= 0:
                self.gb29446_coal_type.setCurrentIndex(coal_index)
            self.gb29446_organization.setText(request.organization_name or "")
            period, custom_period, note = self._decode_gb29446_notes(request.notes)
            period_index = self.gb29446_period.findData(period)
            if period_index >= 0:
                self.gb29446_period.setCurrentIndex(period_index)
            self.gb29446_custom_period.setText(custom_period)
            self.gb29446_custom_period.setVisible(period == "自定义")
            self.gb29446_notes.setText(note)
            supplied_process = request.inputs.get("washing_process")
            if supplied_process is not None:
                process_index = self.gb29446_process.findData(str(supplied_process.value))
                if process_index >= 0:
                    self.gb29446_process.setCurrentIndex(process_index)
            supplied_electricity = request.inputs.get("electricity_consumption")
            self.gb29446_electricity.setText(
                str(supplied_electricity.value) if supplied_electricity is not None else ""
            )
            supplied_raw_coal = request.inputs.get("raw_coal_input")
            self.gb29446_raw_coal.setText(
                str(supplied_raw_coal.value) if supplied_raw_coal is not None else ""
            )
        self._refresh_input_table()
        input_rows = {self.eval_inputs.item(row, 0).text(): row for row in range(self.eval_inputs.rowCount())}
        for key, value in request.inputs.items():
            row = input_rows.get(key)
            if row is not None:
                selector = self.eval_inputs.cellWidget(row, 2)
                if isinstance(selector, QComboBox):
                    text_value = (
                        "是" if value.value is True else "否" if value.value is False
                        else str(value.value)
                    )
                    index = selector.findData(text_value)
                    if index >= 0:
                        selector.setCurrentIndex(index)
                else:
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
        # 保留已有调用入口，统一为基于原记录开始新评价。
        self.recalculate_selected_record()

    def recalculate_selected_record(self) -> None:
        evaluation_id = self._selected_record_id()
        if not evaluation_id:
            QMessageBox.warning(self, "未选择", "请选择一条评价记录。")
            return
        try:
            loaded = self.context.application.get_evaluation(evaluation_id)
        except StorageCorruptionError as exc:
            QMessageBox.warning(self, RECORD_CORRUPTED_LABEL, str(exc))
            return
        if loaded is None:
            QMessageBox.warning(self, "记录不存在", "该评价记录已被删除或不存在。")
            return
        request, _result, snapshot = loaded
        # 未纳入正式评价范围的标准不能通过“基于此记录重新评价”绕开正式评价范围。
        if not supports_formal_evaluation(request.standard_id):
            QMessageBox.warning(
                self,
                FORMAL_EVALUATION_UNSUPPORTED_LABEL,
                f"该标准{FORMAL_EVALUATION_UNSUPPORTED_LABEL}，不能重新发起正式评价；原记录仍可查看。",
            )
            return
        current = self.context.application.get_standard_for_evaluation(request.standard_id, date.today())
        if current is None:
            QMessageBox.warning(self, "标准不可用", "当前没有可正式评价的适用标准，原记录仍可查看。")
            return
        if (current.version, current.rule_revision) != (snapshot.version, snapshot.rule_revision):
            QMessageBox.information(
                self, "规则版本变化",
                f"原记录使用标准版本 {snapshot.version}、规则修订 {snapshot.rule_revision}；"
                f"本次重新评价将按当前适用的标准版本 {current.version}、规则修订 {current.rule_revision} 进行。"
                "原记录不会被修改。",
            )
        self.refresh_standard_combo()
        new_request = request.model_copy(update={"selection_mode": StandardSelectionMode.CURRENT})
        if self._load_request_into_form(new_request):
            self.last_result_id = None
            self.eval_results.setRowCount(0)
            self.eval_summary.setText("")
            self._clear_gb29446_result()
            self.navigation.setCurrentRow(2)

    def export_selected_record(self) -> None:
        evaluation_id = self._selected_record_id()
        if not evaluation_id:
            QMessageBox.warning(self, "未选择", "请选择一条评价记录。")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出Excel", "能耗对标报告.xlsx", "Excel (*.xlsx)")
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

    def save_gb29446_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 GB29446 专用模板", "GB29446-选煤电力消耗限额-评价数据.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            self.context.application.create_template(Path(path), GB29446_STANDARD_ID)
        except Exception as exc:
            QMessageBox.critical(self, "模板保存失败", _friendly_error(exc, "保存GB29446模板"))
            return
        QMessageBox.information(self, "模板已保存", path)

    def validate_import_workbook(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择Excel", "", "Excel (*.xlsx)")
        if not path:
            return
        report = self.context.application.validate_workbook(Path(path))
        self.pending_import_id = report.import_id if report.valid else None
        self.pending_import_standard_id = getattr(getattr(report, "request", None), "standard_id", None)
        self.import_commit_button.setEnabled(report.valid)
        self.import_status.setText("校验通过，请确认下方识别摘要后点击“确认导入并评价”。" if report.valid else "校验失败，请修正后重新导入。")
        self._show_import_summary(report)
        self.import_issues.setRowCount(0)
        for issue in report.issues:
            row = self.import_issues.rowCount()
            self.import_issues.insertRow(row)
            for column, value in enumerate((issue.severity, issue.sheet, issue.cell, issue.message)):
                self.import_issues.setItem(row, column, _item(value))
        # FAIL-FAST（§三）：Excel 是正式评价入口之一，唯一能评价的范围同样由正式评价
        # 范围注册表决定。未纳入范围的标准即使工作簿本身合法，也不能被当成正式评价。
        if self.pending_import_id is not None and not supports_formal_evaluation(self.pending_import_standard_id):
            self.pending_import_id = None
            self.import_commit_button.setEnabled(False)
            self.import_status.setText(self._excel_scope_rejection())
            self.import_summary.setVisible(False)
            self.import_summary.setText("")
            QMessageBox.warning(self, FORMAL_EVALUATION_UNSUPPORTED_LABEL, self._excel_scope_rejection())
            return
        # FAIL-FAST：即使工作簿本身校验通过，只要当前 GB 29446 规则不完整/不兼容，
        # 也不能通过 Excel 路径生成正式评价记录。
        if self.pending_import_standard_id is not None:
            reason = self._gb29446_rule_incompatibility(self.pending_import_standard_id)
            if reason is not None:
                self.pending_import_id = None
                self.import_commit_button.setEnabled(False)
                self.import_status.setText(reason)
                self.import_summary.setVisible(False)
                self.import_summary.setText("")
                QMessageBox.warning(self, "标准规则不兼容", reason)

    @staticmethod
    def _excel_scope_rejection() -> str:
        return (
            f"该标准{FORMAL_EVALUATION_UNSUPPORTED_LABEL}，Excel 导入不能作为它的正式评价入口；"
            "请在标准库中确认软件评价支持状态。"
        )

    def _show_import_summary(self, report) -> None:
        """Show the recognisable business summary of a validated workbook.

        Only user-facing fields are shown; internal keys, the numeric profile
        and calculator identifiers stay in the technical detail layer.
        """
        request = getattr(report, "request", None)
        if not report.valid or request is None:
            self.import_summary.setVisible(False)
            self.import_summary.setText("")
            return
        lines = []
        support_line = f"软件评价支持状态：{evaluation_support_label(request.standard_id)}"
        if request.standard_id == GB29446_STANDARD_ID:
            period, custom_period, _note = self._decode_gb29446_notes(request.notes)
            standard = self.context.application.get_standard(request.standard_id)
            product = None
            if standard is not None:
                product = next((item for item in standard.products if item.id == request.product_id), None)
            coal = ""
            if product is not None:
                # 只显示规则声明的煤种；缺少时留空，不用产品名冒充煤种。
                coal = str(product.selection_values.get(GB29446_COAL_TYPE_KEY) or "").strip()
            electricity = request.inputs.get("electricity_consumption")
            raw_coal = request.inputs.get("raw_coal_input")
            process = request.inputs.get("washing_process")
            lines = [
                f"标准：{standard.number if standard else 'GB 29446—2019'}",
                support_line,
                f"企业：{request.organization_name or '—'}",
                f"评价日期：{format_local_date(request.evaluation_date)}",
                f"核算周期：{custom_period if period == PERIOD_CUSTOM else period}",
                f"煤种：{coal or '—'}",
                f"选煤工艺：{process.value if process else '—'}",
                f"统计期选煤电力消耗量 E_d：{electricity.value if electricity else '—'} kW·h",
                f"统计期入选原煤量 m：{raw_coal.value if raw_coal else '—'} t",
            ]
        else:
            standard = self.context.application.get_standard(request.standard_id)
            lines = [
                f"标准：{standard.number if standard else request.standard_id}",
                support_line,
                f"企业：{request.organization_name or '—'}",
                f"评价日期：{format_local_date(request.evaluation_date)}",
                f"产品/工序：{request.product_id}",
            ]
        self.import_summary.setText("\n".join(lines))
        self.import_summary.setVisible(True)

    def evaluate_import(self) -> None:
        """Formal Excel evaluation: same application use case as the GUI path."""
        if not self.pending_import_id:
            return
        if not supports_formal_evaluation(self.pending_import_standard_id):
            self.pending_import_id = None
            self.import_commit_button.setEnabled(False)
            self.import_status.setText(self._excel_scope_rejection())
            QMessageBox.warning(self, FORMAL_EVALUATION_UNSUPPORTED_LABEL, self._excel_scope_rejection())
            return
        if self.pending_import_standard_id is not None:
            reason = self._gb29446_rule_incompatibility(self.pending_import_standard_id)
            if reason is not None:
                self.pending_import_id = None
                self.import_commit_button.setEnabled(False)
                self.import_status.setText(reason)
                QMessageBox.warning(self, "标准规则不兼容", reason)
                return
        try:
            result = self.context.application.evaluate_workbook(self.pending_import_id)
        except Exception as exc:
            QMessageBox.critical(self, "导入评价失败", _friendly_error(exc, "导入Excel"))
            return
        self.pending_import_id = None
        self.import_commit_button.setEnabled(False)
        self.import_summary.setVisible(False)
        self.import_summary.setText("")
        self.import_status.setText("评价已完成并保存记录。")
        self.refresh_all()
        if result.standard_id == GB29446_STANDARD_ID:
            try:
                request = self.context.application.get_evaluation(result.evaluation_id)
            except StorageCorruptionError:
                # A record saved by this very process is corrupt on disk; the
                # calculation result stays on screen and no detail is fabricated.
                request = None
            if request is not None:
                self._show_gb29446_result(request[0], result)

    def commit_import(self) -> None:
        """Legacy generic submission path kept for the other standards."""
        if not self.pending_import_id:
            return
        try:
            draft = self.context.application.commit_workbook(self.pending_import_id)
            # 与「确认导入并评价」同一门禁：正式评价范围之外的不得经 Excel 生成正式记录。
            if not supports_formal_evaluation(getattr(draft.request, "standard_id", None)):
                self.pending_import_id = None
                self.import_commit_button.setEnabled(False)
                self.import_status.setText(self._excel_scope_rejection())
                QMessageBox.warning(self, FORMAL_EVALUATION_UNSUPPORTED_LABEL, self._excel_scope_rejection())
                return
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
                format_local_datetime(entry.installed_at),
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
            for column, value in enumerate(
                (
                    format_local_datetime(entry.created_at),
                    entry.action,
                    entry.entity_type,
                    entry.entity_id,
                    entry.details_json,
                )
            ):
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

    # ------------------------------------------------------------------
    # 关于 / 诊断信息（只读）
    # ------------------------------------------------------------------

    def build_identity(self):
        """返回当前构建身份；未嵌入时返回占位身份（不抛异常）。"""
        return load_build_identity()

    def _gb29446_rule_revision_text(self) -> str:
        try:
            standard = self.context.application.get_standard(GB29446_STANDARD_ID)
        except Exception:
            return "未知（无法读取标准库）"
        if standard is None:
            return f"未安装 {GB29446_STANDARD_ID}"
        return str(standard.rule_revision)

    def _installed_package_text(self) -> tuple[str, str, str]:
        """最近一次成功安装的标准包 (package_id, data_version, sha256)。"""
        try:
            history = list(self.context.application.list_package_history(1))
        except Exception:
            history = []
        if history:
            latest = history[0]
            return (str(latest.package_id), str(latest.data_version), str(latest.package_sha256))
        try:
            has_service = bool(self.context.application.has_package_service())
        except Exception:
            has_service = False
        placeholder = "未安装标准包" if has_service else "未配置标准包服务"
        return (placeholder, placeholder, placeholder)

    def _diagnostics_facts(self) -> DiagnosticsFacts:
        """Collect the read-only diagnostic facts from the application context."""
        identity = load_build_identity()
        installed_id, installed_version, installed_sha256 = self._installed_package_text()
        try:
            revision = self.context.database.current_revision()
        except Exception:
            revision = None
        return DiagnosticsFacts(
            product_version=__version__,
            data_directory=str(self.context.paths.root),
            db_schema_revision=(
                str(revision) if revision else "未知（数据库未写入 Alembic 版本标记）"
            ),
            gb29446_rule_revision=self._gb29446_rule_revision_text(),
            bundled_package_id=identity.standard_package_id,
            bundled_package_data_version=identity.standard_data_version,
            installed_package_id=installed_id,
            installed_package_data_version=installed_version,
            installed_package_sha256=installed_sha256,
        )

    def diagnostics_report(self) -> str:
        """可复制的纯文本诊断信息（不含私钥或任何凭据内容）。"""
        return render_diagnostics(
            load_build_identity(),
            self._diagnostics_facts(),
            reconciliation_facts(self._package_reconciliation_outcome()),
        )

    # -- 最近一次标准包对账（只读展示 + 非阻断提示） -----------------------

    def _package_reconciliation_outcome(self):
        """最近一次启动标准包对账结果；组合根未记录或旧版门面不支持时返回 ``None``。"""

        getter = getattr(self.context.application, "last_package_reconciliation", None)
        if getter is None:
            return None
        try:
            return getter()
        except Exception:
            return None

    def package_reconciliation_notice(self) -> str | None:
        """对账未达到期望状态时的中文非阻断提示；正常或未对账时返回 ``None``。

        只有 ``succeeded``（install / noop / upgrade）才视为“标准数据可信”，
        conflict / invalid / no-downgrade / missing / unavailable 都必须让用户看到
        标准数据尚未更新的提示，而不是让他误以为已经是最新。
        """

        outcome = self._package_reconciliation_outcome()
        if outcome is None:
            return None
        if bool(getattr(outcome, "succeeded", False)):
            return None
        message = str(getattr(outcome, "message", "") or "").strip()
        notice = PACKAGE_RECONCILIATION_NOTICE_PREFIX
        if message:
            notice = f"{notice}：{message}"
        return f"{notice}（详见“帮助 → 关于 / 诊断信息”）"

    def _clear_package_reconciliation_notice(self) -> None:
        for attribute in ("package_reconciliation_notice_label", "package_reconciliation_notice_dismiss"):
            widget = getattr(self, attribute, None)
            if widget is None:
                continue
            widget.setParent(None)
            widget.deleteLater()
            setattr(self, attribute, None)

    def _show_package_reconciliation_notice(self) -> None:
        """在状态栏显示可关闭的非阻断中文提示（不弹模态框、不改页面布局）。"""

        self._clear_package_reconciliation_notice()
        notice = self.package_reconciliation_notice()
        if notice is None:
            return
        status = self.statusBar()
        label = QLabel(notice)
        label.setObjectName("packageReconciliationNotice")
        label.setStyleSheet("color: #b42318; font-weight: bold;")
        dismiss = QPushButton("关闭提示")
        dismiss.setObjectName("packageReconciliationNoticeDismiss")
        dismiss.clicked.connect(lambda: self._clear_package_reconciliation_notice())
        status.addWidget(label, 1)
        status.addPermanentWidget(dismiss)
        self.package_reconciliation_notice_label = label
        self.package_reconciliation_notice_dismiss = dismiss

    def _copy_diagnostics(self, text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    def show_diagnostics(self) -> None:
        """Open the read-only 关于 / 诊断信息 dialog."""
        text = self.diagnostics_report()
        dialog = QDialog(self)
        dialog.setWindowTitle("关于 / 诊断信息")
        dialog.resize(760, 560)
        layout = QVBoxLayout(dialog)
        content = QTextEdit()
        content.setObjectName("diagnostics_content")
        content.setReadOnly(True)
        content.setPlainText(text)
        content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(content, 1)
        buttons = QHBoxLayout()
        copy = QPushButton("复制到剪贴板")
        copy.clicked.connect(lambda: self._copy_diagnostics(text))
        close = QPushButton("关闭")
        close.clicked.connect(dialog.accept)
        buttons.addWidget(copy)
        buttons.addStretch()
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.diagnostics_dialog = dialog
        self.diagnostics_content = content
        dialog.open()

    # ------------------------------------------------------------------
    # 官方来源（ECQ-RS05 §四）：普通界面只打开已登记的官方页面
    # ------------------------------------------------------------------

    def open_official_source(self, standard_id: str | None) -> bool:
        """打开 ``standard_id`` 已登记的官方标准来源页面。

        这是普通界面唯一的“查看标准原文”实现：地址只来自
        :func:`uebench.application.official_sources.official_source_url`，不做任何
        运行时检索、拼接或猜测，也**不打开本机 PDF**。未登记地址时如实拒绝并提示
        :data:`NO_OFFICIAL_SOURCE_LABEL`。
        """

        url = official_source_url(standard_id) if standard_id else None
        if url is None:
            QMessageBox.information(
                self,
                "官方来源",
                f"{NO_OFFICIAL_SOURCE_LABEL}。可在{OFFICIAL_SOURCE_PLATFORM_NAME}"
                f"（{OFFICIAL_SOURCE_PLATFORM_HOME}）自行检索该标准。",
            )
            return False
        QDesktopServices.openUrl(QUrl(url))
        return True

    def open_selected_standard(self) -> None:
        """标准库：打开所选标准的官方来源页面（不再打开本机 PDF）。"""

        standard_id = self._selected_library_standard_id()
        if standard_id is None:
            QMessageBox.warning(self, "未选择", "请先在标准库中选择一个标准。")
            return
        self.open_official_source(standard_id)

    def open_selected_standard_for_evaluation(self) -> None:
        """新建评价页 / 标准依据：打开当前所选标准的官方来源页面。"""

        standard_id = self.eval_standard.currentData()
        if not standard_id:
            QMessageBox.warning(self, "未选择标准", "请先选择标准后再查看标准原文。")
            return
        self.open_official_source(standard_id)

    # ------------------------------------------------------------------
    # 从标准库进入「新建评价」（ECQ-RS05 §六/§七）
    # ------------------------------------------------------------------

    def start_formal_evaluation(self) -> None:
        """首页「开始正式评价」：进入新建评价并选中正式评价范围内的标准。"""

        evaluable = filter_formally_evaluable(self.context.application.list_library_standards())
        if not evaluable:
            QMessageBox.information(
                self, "暂无可正式评价的标准", "本机标准库中没有已纳入正式评价范围的标准，请先更新标准数据。"
            )
            return
        self.open_evaluation_for_standard(evaluable[0].id)

    def start_evaluation_for_selected_standard(self) -> None:
        """标准库「用该标准新建评价」：只有正式评价范围内的标准可用。"""

        standard_id = self._selected_library_standard_id()
        if standard_id is None:
            QMessageBox.warning(self, "未选择", "请先在标准库中选择一个标准。")
            return
        self.open_evaluation_for_standard(standard_id)

    def open_evaluation_for_standard(self, standard_id: str | None) -> bool:
        """在「新建评价」中选中 ``standard_id``；范围之外的标准不提供评价入口。

        返回 ``True`` 表示已经带着该标准进入「新建评价」页面。
        """

        if not supports_formal_evaluation(standard_id):
            QMessageBox.information(
                self,
                FORMAL_EVALUATION_UNSUPPORTED_LABEL,
                f"该标准{FORMAL_EVALUATION_UNSUPPORTED_LABEL}，本版本不能发起正式评价；"
                "标准原文仍可在标准库中查看。",
            )
            return False
        current_mode = self.eval_selection_mode.findData(StandardSelectionMode.CURRENT.value)
        if current_mode >= 0 and self.eval_selection_mode.currentIndex() != current_mode:
            self.eval_selection_mode.setCurrentIndex(current_mode)
        self.refresh_standard_combo()
        combo_index = self.eval_standard.findData(standard_id)
        if combo_index < 0:
            QMessageBox.warning(
                self,
                "标准不可用",
                "该标准当前不在可正式评价的标准列表中，请先更新标准数据后重试。",
            )
            return False
        self.eval_standard.setCurrentIndex(combo_index)
        self._standard_changed()
        self.navigation.setCurrentRow(2)
        return True


def create_main_window(context: AppContext) -> MainWindow:
    return MainWindow(context)
