from __future__ import annotations

import html
import logging
import re
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4
from zipfile import BadZipFile

_LOGGER = logging.getLogger(__name__)

from PySide6.QtCore import QDate, Qt, QUrl, QSize, QTimer
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from .record_table import RecordTable, StandardTable
from .wheel_safe_combo import WheelSafeComboBox
from .official_source_dialog import OfficialSourceDialog
from .external_browser import external_browser_environment
from .message_box_text import install_chinese_message_box_buttons
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
    QLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QButtonGroup,
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
from uebench.application.backup_errors import BackupValidationError, RestoreSafetyError
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
    standard_confirmation_message,
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
    parse_decimal,
)
from uebench.application.reporting import PERIOD_LABEL, STATISTICS_SCOPE, build_report_view, gb29446_business_labels, render_gb29446_warning
from uebench.ui.presentation import format_local_date, format_local_datetime
from uebench.ui.settings_page import SettingsPage
from uebench.ui.design_tokens import APP_STYLE
from uebench.ui.responsive_fields import ResponsiveFields
from uebench.ui.task_card import TaskCard, TaskCardGrid
from uebench.ui.record_detail import RecordDetailPage


def _item(value, *, align_right: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem("" if value is None else str(value))
    if align_right:
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item


#: 普通界面里的 ``E_d`` / ``e_d`` 必须以**真下标**呈现。内部变量键、JSON 与领域字段名
#: 保持不变，只在展示层把它们渲染成 Qt 富文本；绝不能把字面量 “<sub>” 直接塞进纯文本。
_SUBSCRIPT_D = re.compile(r"([Ee])_d")


def _rich_text(value) -> str:
    """把普通文本转成 Qt 富文本：先转义，再把 ``E_d`` / ``e_d`` 变成真下标。"""

    escaped = html.escape("" if value is None else str(value), quote=False)
    return _SUBSCRIPT_D.sub(r"\1<sub>d</sub>", escaped).replace("\n", "<br>")


def _rich_label(value) -> QLabel:
    """构造一个真正按富文本渲染的标签：只有显式声明富文本，``<sub>`` 才会显示为下标。"""

    label = QLabel(_rich_text(value))
    label.setTextFormat(Qt.TextFormat.RichText)
    return label


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


def _backup_failure_message(exc: Exception) -> str:
    """创建备份失败时给用户的中文提示（H03）。

    ``_friendly_error`` 的兜底文案是面向**评价**的（“输入数据、单位”），对备份
    场景不适用；而 ``PermissionError`` 之类的 ``str(exc)`` 在英文系统上是纯英文，
    中文系统上又带着路径。因此备份走专用文案：技术细节（异常类型、errno、路径）
    一律只进日志，用户看到的是稳定、明确的中文失败原因。
    """
    detail = str(exc).strip()
    if not isinstance(exc, OSError) and detail and any("\u4e00" <= char <= "\u9fff" for char in detail):
        return f"创建备份失败：{detail}"
    return "创建备份失败：无法写入所选位置，请检查磁盘空间与文件权限，或更换保存位置后重试。"


def _restore_failure_message(exc: Exception) -> str:
    """恢复专用提示；不把未知后置错误说成原数据未变，技术详情只记日志。"""
    if isinstance(exc, RestoreSafetyError):
        # 既有后端消息区分未切换、已回滚与回滚失败，保留实际保护状态和处理建议。
        return str(exc)
    if isinstance(exc, (BackupValidationError, BadZipFile)):
        return "所选备份无效、已损坏或与当前版本不兼容。请选择有效的 UEBench 备份（.uebackup），或重新复制备份文件后重试。"
    if isinstance(exc, PermissionError):
        return "恢复备份失败：无法访问备份文件或数据目录。请检查读取和写入权限、关闭占用文件的程序，或将备份复制到可访问的位置后重试。"
    if isinstance(exc, (FileNotFoundError, IsADirectoryError, NotADirectoryError)):
        return "恢复备份失败：文件或目录路径不可用。请确认备份文件仍然存在，重新选择有效文件，并检查数据目录后重试。"
    if isinstance(exc, OSError):
        return "恢复备份失败：无法读写备份文件或数据目录。请检查文件路径、磁盘空间和访问权限后重试。"
    return "恢复未完成。请先核对当前记录状态，并保留恢复前的自动备份；如仍无法正常使用，请联系支持人员。"


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
GB29446_RULE_INCOMPATIBLE_MESSAGE = "标准规则数据不完整或版本不兼容，请安装完整的新版本后再评价。"

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
# 标准「适用范围」（ECQ-RS05 §六 收尾）
# ---------------------------------------------------------------------------
#
# 所有标准共用同一个「适用范围」字段与同一个位置。文字只能来自**已确认的标准元数据**：
#
# * GB 29446—2019 的适用范围已由 Owner 逐字确认，登记在
#   :data:`STANDARD_SCOPE_TEXTS`，界面只做展示，不改一个字；
# * 其余标准尚未重新梳理，没有可靠范围，只能如实显示
#   :data:`STANDARD_SCOPE_PENDING_LABEL`。不得由界面或实现者根据旧规则、旧 Excel 或
#   推测代写范围文字。
STANDARD_SCOPE_PENDING_LABEL = "适用范围尚待整理"

#: Owner 已确认的「适用范围」原文（逐字登记，未登记的标准一律显示待整理）。
STANDARD_SCOPE_TEXTS: dict[str, str] = {
    GB29446_STANDARD_ID: (
        "适用于煤炭行业煤炭洗选过程选煤电力单耗的计算、考核，以及新建和改扩建企业的电力单耗控制。"
    ),
}

#: GB 29446 统计范围已确认文本（标准第5.1条），只用于「新建评价」的「统计范围说明」。
GB29446_STATISTICS_SCOPE_LINES = (STATISTICS_SCOPE,)


def _gb29446_statistics_scope_text() -> str:
    """「统计范围说明」按钮展开后的确认文本（保持既有换行展示）。"""

    return "\n".join(GB29446_STATISTICS_SCOPE_LINES)


def standard_scope_text(standard_id: str | None) -> str:
    """标准「适用范围」：只有已确认登记的标准才有文字，其余如实显示待整理。"""

    if not standard_id:
        return STANDARD_SCOPE_PENDING_LABEL
    return STANDARD_SCOPE_TEXTS.get(standard_id, STANDARD_SCOPE_PENDING_LABEL)


def standard_scope_line(standard_id: str | None) -> str:
    """标准库详情里唯一的一行「适用范围」。

    已确认的标准显示 ``适用范围：<scope>``；未确认的标准只显示
    :data:`STANDARD_SCOPE_PENDING_LABEL`（该文字本身已经点名「适用范围」，不再重复字段名）。
    """

    text = standard_scope_text(standard_id)
    return text if text == STANDARD_SCOPE_PENDING_LABEL else f"适用范围：{text}"



class MainWindow(QMainWindow):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        install_chinese_message_box_buttons()
        self.context = context
        self.current_standard: StandardDefinition | None = None
        self.last_result_id: str | None = None
        #: 当前加载的 GB 29446 规则是否满足正式 r2 结构；非 GB29446 标准恒为 True。
        self.gb29446_rule_compatible = True
        #: ECQ-RS05 M3：「评价记录」只在首次进入时加载（或在被标记为待刷新后重进时
        #: 加载）。全局刷新只把它标记为脏，绝不为用户从未打开过的页面读取 200 条记录。
        self._records_loaded = False
        self._records_dirty = True
        self.setWindowTitle("单位产品能耗限额评价软件")
        # Leave room for the ten-column energy table on ordinary 1366x768 and
        # 1920x1080 screens.  Users can still resize the window smaller.
        self.resize(1440, 900)
        self.setMinimumSize(900, 600)
        if QApplication.platformName() != "offscreen" and self.screen() is not None:
            available = self.screen().availableGeometry()
            self.setMinimumSize(min(900, max(640, available.width() - 32)), min(600, max(420, available.height() - 64)))
            self.resize(min(1440, available.width() - 24), min(900, available.height() - 48))
        self.setStyleSheet(APP_STYLE)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(242)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(8, 24, 8, 18)
        side_layout.addWidget(self._brand(194))
        brand_caption = QLabel("单位产品能耗限额\n评价软件")
        brand_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_layout.addWidget(brand_caption)
        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setIconSize(QSize(18, 18))
        self.pages = QStackedWidget()
        side_layout.addWidget(self.navigation, 1)
        settings = QPushButton("设置")
        settings.setIcon(self._icon("settings"))
        settings.clicked.connect(lambda: self.navigate("settings"))
        side_layout.addWidget(settings)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(central)

        page_builders = [
            ("home", self._build_home),
            ("standards", self._build_standards),
            ("evaluation", self._build_evaluation),
            ("records", self._build_records),
            ("settings", self._build_settings),
        ]
        self.page_widgets = {}
        for key, builder in page_builders:
            self.page_widgets[key] = builder()
            self.pages.addWidget(self.page_widgets[key])
        self.page_widgets["standard_detail"] = self._build_standard_detail()
        self.pages.addWidget(self.page_widgets["standard_detail"])
        self.record_detail_page = RecordDetailPage()
        self.record_detail_page.back_requested.connect(lambda: self.navigate("records"))
        self.record_detail_page.export_requested.connect(self.export_word_record)
        self.record_detail_page.source_requested.connect(self.open_official_source)
        self.page_widgets["record_detail"] = self.record_detail_page
        self.pages.addWidget(self.record_detail_page)
        for key, title, icon_name, enabled in (
            ("home", "首页", "home", True),
            ("standards", "标准库", "standards", True),
            ("evaluation", "新建对标", "new", True),
            ("import", "表格导入 · 暂未开放", "excel", False),
            ("records", "对标记录", "records", True),
            ("factors", "折标系数库 · 暂未开放", "factors", False),
        ):
            item = QListWidgetItem(self._icon(icon_name), title)
            item.setData(Qt.ItemDataRole.UserRole, key)
            if not enabled:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled & ~Qt.ItemFlag.ItemIsSelectable)
            self.navigation.addItem(item)
        # 先把首页设为当前项再连信号：否则 setCurrentRow(0) 会立刻触发一次
        # `_page_changed(0)`，紧接着的 `refresh_all()` 又把首页刷新一遍——同一份
        # 标准定义在一次构造里被完整解析两遍。最终状态与从前一致（页面栈默认就是
        # 第 0 页，首页刷新与就绪检查都由 refresh_all 完成）。
        self.navigation.setCurrentRow(0)
        self.navigation.currentRowChanged.connect(self._page_changed)
        self.navigation.itemClicked.connect(self._navigation_clicked)
        self.sidebar.hide()
        self.refresh_all()

    @staticmethod
    def _icon(name: str, color: str = "#197CC2") -> QIcon:
        source = Path(__file__).resolve().parents[1] / "resources" / "icons" / f"{name}.svg"
        renderer = QSvgRenderer(source.read_bytes().replace(b"#FFFFFF", color.encode("ascii")))
        pixmap = QPixmap(36, 36)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def _brand(width: int) -> QLabel:
        label = QLabel()
        pixmap = QPixmap(str(Path(__file__).resolve().parents[1] / "resources" / "branding" / "qingzhou_logo.png"))
        label.setPixmap(pixmap.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def navigate(self, key: str) -> None:
        if key not in self.page_widgets:
            return
        self.pages.setCurrentWidget(self.page_widgets[key])
        self.sidebar.setVisible(key != "home")
        context_key = "standards" if key == "standard_detail" else "records" if key == "record_detail" else key
        self.navigation.blockSignals(True)
        self.navigation.setCurrentRow(-1)
        for row in range(self.navigation.count()):
            if self.navigation.item(row).data(Qt.ItemDataRole.UserRole) == context_key:
                self.navigation.setCurrentRow(row)
                break
        self.navigation.blockSignals(False)
        if key == "home":
            self.refresh_home()
        elif key == "records" and (self._records_dirty or not self._records_loaded):
            self.refresh_records()
        elif key == "settings":
            self.refresh_settings()
        self.refresh_formal_evaluation_readiness()

    def _page(self, title: str, label: QLabel | None = None) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        label = label if label is not None else QLabel(title)
        label.setWordWrap(True)
        label.setProperty("class", "pageTitle")
        layout.addWidget(label)
        return page, layout

    @staticmethod
    def _card() -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setProperty("class", "card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        return frame, layout

    def _build_home(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        layout.setContentsMargins(36, 30, 36, 28)
        layout.setSpacing(26)
        header = QHBoxLayout()
        header.addWidget(self._brand(220))
        title = QLabel("单位产品能耗限额评价软件")
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 30px; font-weight: 800; color: #18364F;")
        header.addWidget(title, 1)
        settings = QPushButton("设置")
        settings.setIcon(self._icon("settings"))
        settings.clicked.connect(lambda: self.navigate("settings"))
        header.addWidget(settings)
        layout.addLayout(header)
        # 兼容现有就绪状态投影；统计与包身份不进入首页可见布局。
        self.home_standard_count = QLabel(page)
        self.home_formal_scope_count = QLabel(page)
        self.home_evaluation_count = QLabel(page)
        self.home_standard_library_version = QLabel(page)
        self.home_scope_label = QLabel(page)
        for widget in (self.home_standard_count, self.home_formal_scope_count,
                       self.home_evaluation_count, self.home_standard_library_version, self.home_scope_label):
            widget.hide()
        tasks = TaskCardGrid()
        self.home_task_buttons = {}
        for key, title, description, icon_name, enabled in (
            ("standards", "标准库", "查阅标准与要求", "standards", True),
            ("evaluation", "新建对标", "填写数据，计算判级", "new", True),
            ("import", "表格导入", "暂未开放", "excel", False),
            ("records", "对标记录", "查看保存时结果", "records", True),
            ("factors", "折标系数库", "暂未开放", "factors", False),
        ):
            button = TaskCard(title, description, self._icon(icon_name, "#FFFFFF" if key == "standards" else "#197CC2"), emphasized=key == "standards")
            button.setEnabled(enabled)
            if key == "standards":
                button.setObjectName("standardTask")
            if key == "evaluation":
                self.home_start_evaluation = button
                button.clicked.connect(self.start_formal_evaluation)
            elif enabled:
                button.clicked.connect(lambda _=False, target=key: self.navigate(target))
            self.home_task_buttons[key] = button
            tasks.add_card(button)
        layout.addWidget(tasks)
        self.home_compatibility_notice = QLabel("")
        self.home_compatibility_notice.setWordWrap(True)
        self.home_compatibility_notice.setStyleSheet("color: #B9484A;")
        self.home_compatibility_notice.hide()
        layout.addWidget(self.home_compatibility_notice)
        card, card_layout = self._card()
        self.home_recent_card = card
        row = QHBoxLayout()
        heading = QLabel("最近对标")
        heading.setProperty("class", "sectionTitle")
        row.addWidget(heading, 1)
        all_records = QPushButton("查看全部")
        all_records.clicked.connect(lambda: self.navigate("records"))
        row.addWidget(all_records)
        self.home_retry = QPushButton("重试")
        self.home_retry.clicked.connect(self.refresh_home)
        self.home_retry.hide()
        row.addWidget(self.home_retry)
        card_layout.addLayout(row)
        self.home_recent = QTableWidget(0, 6)
        self.home_recent.setHorizontalHeaderLabels(["企业名称", "统计期", "标准", "核心结果", "评价时间", "操作"])
        self._configure_table(self.home_recent)
        self.home_recent.horizontalHeader().setStretchLastSection(False)
        self.home_recent.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.home_recent.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.home_recent.setColumnWidth(5, 92)
        self.home_recent.verticalHeader().setDefaultSectionSize(52)
        self.home_recent.itemDoubleClicked.connect(lambda *_: self._open_home_record())
        card_layout.addWidget(self.home_recent)
        self.home_recent_notice = QLabel("暂无对标记录")
        self.home_recent_notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.home_recent_notice.setMinimumHeight(64)
        card_layout.addWidget(self.home_recent_notice)
        self.home_empty_start = QPushButton("新建对标")
        self.home_empty_start.setProperty("role", "primary")
        self.home_empty_start.clicked.connect(self.start_formal_evaluation)
        card_layout.addWidget(self.home_empty_start, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _open_home_record(self, record_id: str | None = None) -> None:
        if record_id is None:
            item = self.home_recent.item(self.home_recent.currentRow(), 0)
            record_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not record_id:
            return
        self.view_record(record_id)

    def _build_standards(self) -> QWidget:
        page, layout = self._page("标准库")
        controls = QHBoxLayout()
        self.standard_search = QLineEdit()
        self.standard_search.setPlaceholderText("搜索标准编号、名称或适用对象")
        self.standard_search.setClearButtonEnabled(True)
        self.standard_search.textChanged.connect(self.refresh_standards)
        self.standard_status_filter = QComboBox()
        self.standard_status_filter.addItems(["全部标准状态", "当前有效", "尚未实施", "历史/已替代", "待确认"])
        self.standard_status_filter.currentIndexChanged.connect(self.refresh_standards)
        controls.addWidget(self.standard_search, 1)
        controls.addWidget(self.standard_status_filter)
        self.standard_retry = QPushButton("重试")
        self.standard_retry.clicked.connect(self.refresh_standards)
        self.standard_retry.hide()
        controls.addWidget(self.standard_retry)
        layout.addLayout(controls)
        self.standard_table = StandardTable(0, 5)
        self.standard_table.setHorizontalHeaderLabels(["标准编号", "标准名称", "标准状态", "实施日期", "软件支持"])
        self._configure_table(self.standard_table)
        self.standard_table.itemSelectionChanged.connect(self.refresh_standard_detail)
        self.standard_table.cellClicked.connect(lambda row, column: self.show_standard_detail() if column in (0, 1) else None)
        self.standard_table.itemActivated.connect(lambda *_: self.show_standard_detail())
        self.standard_table.itemDoubleClicked.connect(lambda *_: self.show_standard_detail())
        self.standard_table.setWordWrap(True)
        self.standard_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.standard_table.horizontalHeader().setStretchLastSection(False)
        self.standard_table.verticalHeader().setDefaultSectionSize(58)
        layout.addWidget(self.standard_table, 1)
        self.standard_count_label = QLabel("")
        layout.addWidget(self.standard_count_label)
        return page

    def _build_standard_detail(self) -> QWidget:
        self.standard_detail_title = QLabel("标准详情")
        page, layout = self._page("标准详情", self.standard_detail_title)
        back = QPushButton("返回标准库")
        back.clicked.connect(lambda: self.navigate("standards"))
        layout.insertWidget(0, back, 0, Qt.AlignmentFlag.AlignLeft)
        actions = QHBoxLayout()
        actions.addStretch()
        self.standard_official_status = QLabel(NO_OFFICIAL_SOURCE_LABEL)
        self.standard_official_button = QPushButton(VIEW_OFFICIAL_SOURCE_BUTTON_TEXT)
        self.standard_official_button.clicked.connect(self.open_selected_standard)
        self.standard_evaluate_button = QPushButton("按此标准对标")
        self.standard_evaluate_button.setProperty("role", "primary")
        self.standard_evaluate_button.clicked.connect(self.start_evaluation_for_selected_standard)
        actions.addWidget(self.standard_official_status)
        actions.addWidget(self.standard_official_button)
        actions.addWidget(self.standard_evaluate_button)
        layout.addLayout(actions)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.standard_detail_scroll = scroll
        content = QWidget()
        blocks = QVBoxLayout(content)
        blocks.setContentsMargins(0, 0, 8, 0)
        blocks.setSpacing(20)
        self.standard_confirmation_label = QLabel("")
        self.standard_detail_label = QLabel("")
        self.standard_requirements_notice = QLabel("")
        self.standard_indicator_table = QTableWidget(0, 6)
        self.standard_indicator_table.setHorizontalHeaderLabels(["选煤企业类型", "指标", "单位", "1级上限", "2级上限", "3级上限"])
        self._configure_table(self.standard_indicator_table)
        self.standard_indicator_table.horizontalHeader().setStretchLastSection(False)
        self.standard_indicator_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.standard_indicator_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.standard_requirements_basis = QLabel("")
        self.standard_metadata = QLabel("")
        for title, widgets in (
            ("基本信息", [self.standard_metadata, self.standard_confirmation_label]),
            ("适用范围", [self.standard_detail_label]),
            ("标准要求", [self.standard_requirements_notice, self.standard_indicator_table, self.standard_requirements_basis]),
        ):
            card, body = self._card()
            heading = QLabel(title)
            heading.setProperty("class", "sectionTitle")
            body.addWidget(heading)
            for widget in widgets:
                if isinstance(widget, QLabel):
                    widget.setWordWrap(True)
                    widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                body.addWidget(widget)
            blocks.addWidget(card)
        blocks.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def show_standard_detail(self) -> None:
        if self._selected_library_standard_id() is None:
            return
        self.refresh_standard_detail()
        self.standard_detail_scroll.verticalScrollBar().setValue(0)
        self.navigate("standard_detail")

    def _build_evaluation(self) -> QWidget:
        page, page_layout = self._page("新建对标")
        self.eval_standard_summary = QLabel("")
        self.eval_standard_summary.setWordWrap(True)
        self.eval_standard_summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        page_layout.addWidget(self.eval_standard_summary)
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
        self.evaluation_readiness_notice = QLabel("")
        self.evaluation_readiness_notice.setObjectName("evaluationReadinessNotice")
        self.evaluation_readiness_notice.setWordWrap(True)
        self.evaluation_readiness_notice.setStyleSheet("color: #b42318; font-weight: bold;")
        self.evaluation_readiness_notice.setVisible(False)
        page_layout.addWidget(self.evaluation_readiness_notice)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(14)
        scroll.setWidget(content)
        page_layout.addWidget(scroll, 1)

        form_card, form_layout = self._card()
        # ECQ-RS05 M2 §四：普通用户不再选择“当前 / 历史 / 未来”版本范围。
        # 0.2.0 只有正式支持的当前标准，新建评价只列出正式可评价的标准；
        # “评价记录”里的历史记录查看不受影响（它读的是已保存的请求与结果快照）。
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
        page_layout.insertWidget(3, self.eval_standard_status)
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
        # 「备注」不再出现在普通界面上；控件保留为**不进入任何布局**的内部承载，
        # 历史记录的 notes 才能继续原样载入与保存（见 _load_request_into_form）。
        self.eval_notes = QLineEdit()
        self.generic_form_container = QWidget()
        generic_form = QFormLayout(self.generic_form_container)
        generic_form.setContentsMargins(0, 0, 0, 0)
        generic_form.addRow("产品/工序", self.selection_container)
        generic_form.addRow("单位名称", self.eval_organization)

        self.gb29446_form_container = QWidget()
        gb_form = QFormLayout(self.gb29446_form_container)
        gb_form.setContentsMargins(0, 0, 0, 0)
        #: 兼容性降级时需要按“行”隐藏煤种/选煤工艺/折算系数输入项。
        self.gb29446_form_layout = gb_form
        self.gb29446_organization = QLineEdit()
        self.gb29446_organization.setPlaceholderText("可选填写")
        self.gb29446_organization.textChanged.connect(self._gb29446_inputs_changed)
        self.gb29446_period = WheelSafeComboBox()
        for period in GB29446_PERIOD_OPTIONS:
            self.gb29446_period.addItem(period, period)
        self.gb29446_period.currentIndexChanged.connect(self._gb29446_period_changed)
        self.gb29446_period.currentIndexChanged.connect(self._gb29446_inputs_changed)
        self.gb29446_custom_period = QLineEdit()
        self.gb29446_custom_period.setPlaceholderText(f"填写{PERIOD_LABEL}，例如：2026年第一季度")
        self.gb29446_custom_period.setVisible(False)
        self.gb29446_custom_period.textChanged.connect(self._gb29446_inputs_changed)
        self.gb29446_coal_type = QComboBox()
        self.gb29446_coal_type.currentIndexChanged.connect(self._gb29446_coal_changed)
        self.gb29446_coal_type.currentIndexChanged.connect(self._gb29446_inputs_changed)
        self.gb29446_coal_buttons = QWidget()
        coal_layout = QHBoxLayout(self.gb29446_coal_buttons)
        coal_layout.setContentsMargins(0, 0, 0, 0)
        self.coal_button_group = QButtonGroup(self)
        for name in ("炼焦煤", "动力煤"):
            radio = QRadioButton(name)
            self.coal_button_group.addButton(radio)
            coal_layout.addWidget(radio)
            radio.clicked.connect(lambda _=False, name=name: self.gb29446_coal_type.setCurrentIndex(self.gb29446_coal_type.findText(name)))
        coal_layout.setSpacing(28)
        coal_layout.addStretch()
        self.gb29446_coal_type.currentIndexChanged.connect(self._sync_coal_radios)
        self.gb29446_process = WheelSafeComboBox()
        self.gb29446_process.currentIndexChanged.connect(self._gb29446_process_changed)
        self.gb29446_process.currentIndexChanged.connect(self._gb29446_inputs_changed)
        self.gb29446_electricity = QLineEdit()
        self.gb29446_electricity.setPlaceholderText("输入统计期内选煤电力消耗量")
        self.gb29446_electricity.textChanged.connect(self._gb29446_inputs_changed)
        self.gb29446_raw_coal = QLineEdit()
        self.gb29446_raw_coal.setPlaceholderText("输入统计期内入选原煤量")
        self.gb29446_raw_coal.textChanged.connect(self._gb29446_inputs_changed)
        self.gb29446_factor = QLineEdit()
        self.gb29446_factor.setReadOnly(True)
        self.gb29446_factor.setPlaceholderText("待选择工艺")
        self.gb29446_factor.setFixedWidth(150)
        self.gb29446_factor.setStyleSheet("QLineEdit { border: none; background: transparent; padding: 0; font-size: 20px; font-weight: 600; }")
        self.gb29446_notes = QLineEdit()
        self.gb29446_notes.setPlaceholderText("可选")
        self.gb29446_notes.textChanged.connect(self._gb29446_inputs_changed)
        period_row = QWidget()
        period_layout = QVBoxLayout(period_row)
        period_layout.setContentsMargins(0, 0, 0, 0)
        period_layout.setSpacing(4)
        period_layout.addWidget(self.gb29446_period)
        period_layout.addWidget(self.gb29446_custom_period)
        self.gb29446_coal_type.setParent(self.gb29446_form_container)
        self.gb29446_coal_type.hide()
        basic_heading = QLabel("基本信息")
        basic_heading.setProperty("class", "sectionTitle")
        gb_form.addRow(basic_heading)
        basic_fields = ResponsiveFields([
            ("企业名称（可选）", self.gb29446_organization, False),
            (PERIOD_LABEL, period_row, False),
        ])
        gb_form.addRow(basic_fields)
        business_heading = QLabel("业务数据")
        business_heading.setProperty("class", "sectionTitle")
        gb_form.addRow(business_heading)
        self.gb29446_business_fields = ResponsiveFields([
            ("选煤企业类型", self.gb29446_coal_buttons, True),
            ("选煤工艺类型", self.gb29446_process, True),
            ("选煤工艺类型折算系数 k · 来源：附录A 表A.1", self.gb29446_factor, True),
            ("统计期内选煤电力消耗量 E<sub>d</sub>（kW·h）", self.gb29446_electricity, False),
            ("统计期内入选原煤量 m（t）", self.gb29446_raw_coal, False),
        ])
        gb_form.addRow(self.gb29446_business_fields)
        self.gb29446_field_error = QLabel("")
        self.gb29446_field_error.setWordWrap(True)
        self.gb29446_field_error.setStyleSheet("color: #B9484A;")
        gb_form.addRow(self.gb29446_field_error)
        # 「备注」不再出现在普通界面上；控件保留为不进入任何布局的内部承载，
        # 历史记录的 notes（核算周期 + 备注）才能继续原样载入与保存。
        self.eval_notes.setParent(self.generic_form_container)
        self.eval_notes.setVisible(False)
        self.gb29446_notes.setParent(self.gb29446_form_container)
        self.gb29446_notes.setVisible(False)

        self.eval_standard.setParent(page)
        self.eval_standard.hide()
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
        calculate.setProperty("role", "primary")
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
        self.gb29446_result_heading = result_heading = QLabel("对标结果")
        result_heading.setProperty("class", "sectionTitle")
        gb_result_section_layout.addWidget(result_heading)
        self.gb29446_result_card = QFrame()
        self.gb29446_result_card.setObjectName("card")
        gb29446_layout = QVBoxLayout(self.gb29446_result_card)
        gb29446_layout.setContentsMargins(0, 0, 0, 0)
        gb29446_layout.setSpacing(14)
        metrics = QHBoxLayout()
        ed_card = QWidget()
        ed_card.setObjectName("coreMetric")
        ed_layout = QVBoxLayout(ed_card)
        ed_layout.setContentsMargins(0, 0, 0, 0)
        ed_layout.addWidget(_rich_label("选煤电力单耗 e_d"))
        self.gb29446_result_ed = QLabel("— kW·h/t")
        self.gb29446_result_ed.setProperty("class", "metric")
        ed_layout.addWidget(self.gb29446_result_ed)
        grade_card = QWidget()
        grade_card.setObjectName("coreMetric")
        grade_layout = QVBoxLayout(grade_card)
        grade_layout.setContentsMargins(0, 0, 0, 0)
        grade_layout.addWidget(QLabel("电耗等级"))
        self.gb29446_result_grade = QLabel("—")
        self.gb29446_result_grade.setProperty("class", "metric")
        grade_layout.addWidget(self.gb29446_result_grade)
        metrics.addWidget(ed_card)
        metrics.addWidget(grade_card)
        self.gb29446_metrics = QWidget()
        self.gb29446_metrics.setObjectName("coreMetrics")
        self.gb29446_metrics.setMinimumHeight(90)
        metrics.setContentsMargins(0, 0, 0, 0)
        self.gb29446_metrics.setLayout(metrics)
        gb29446_layout.addWidget(self.gb29446_metrics)
        self.gb29446_metrics.hide()
        self.gb29446_view_record = QPushButton("查看对标记录")
        self.gb29446_view_record.setProperty("role", "primary")
        self.gb29446_view_record.setEnabled(False)
        self.gb29446_view_record.clicked.connect(lambda: self._open_home_record(self.last_result_id))
        gb29446_layout.addWidget(self.gb29446_view_record, 0, Qt.AlignmentFlag.AlignRight)
        self.gb29446_export_word = QPushButton("导出Word报告")
        self.gb29446_export_word.setObjectName("gb29446ExportWordButton")
        self.gb29446_export_word.setEnabled(False)
        self.gb29446_export_word.clicked.connect(self.export_latest_word_report)
        gb29446_layout.addWidget(self.gb29446_export_word, 0, Qt.AlignmentFlag.AlignRight)
        self.gb29446_result_message = QLabel("尚未计算")
        self.gb29446_result_message.setWordWrap(True)
        self.gb29446_result_message.setTextFormat(Qt.TextFormat.RichText)
        gb29446_layout.addWidget(self.gb29446_result_message)
        gb_result_section_layout.addWidget(self.gb29446_result_card)
        layout.addWidget(self.gb29446_result_section)

        self.gb29446_explanation_section, explanation_layout = self._card()
        self.gb29446_explanation = QLabel("完成计算后显示本次计算与判定说明。")
        self.gb29446_explanation.setWordWrap(True)
        # 说明里含 E_d / e_d 真下标（富文本）；只有显式声明富文本才会渲染为下标。
        self.gb29446_explanation.setTextFormat(Qt.TextFormat.RichText)
        self.gb29446_explanation.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        explanation_layout.addWidget(self.gb29446_explanation)
        layout.addWidget(self.gb29446_explanation_section)

        self.gb29446_basis_section, basis_layout = self._card()
        self.gb29446_basis = QLabel("完成计算后显示本次评价的标准依据。")
        self.gb29446_basis.setWordWrap(True)
        basis_layout.addWidget(self.gb29446_basis)
        # 页面顶部已有统一的「查看标准原文」入口；这里不再重复一个同样的按钮，
        # 只保留本页特有的「统计范围说明」。
        self.gb29446_scope_toggle = QPushButton("展开统计范围说明")
        self.gb29446_scope_toggle.setCheckable(True)
        self.gb29446_scope_details = QLabel(_gb29446_statistics_scope_text())
        self.gb29446_scope_details.setWordWrap(True)
        self.gb29446_scope_details.setVisible(False)
        self.gb29446_scope_toggle.toggled.connect(
            lambda expanded: (
                self.gb29446_scope_details.setVisible(expanded),
                self.gb29446_scope_toggle.setText("收起统计范围说明" if expanded else "展开统计范围说明"),
            )
        )
        basis_layout.addWidget(self.gb29446_scope_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        basis_layout.addWidget(self.gb29446_scope_details)

        layout.addWidget(self.gb29446_basis_section)
        # 结果、说明、依据共用同一块面板；统计范围就近放在录入末尾。
        basis_layout.removeWidget(self.gb29446_scope_toggle)
        basis_layout.removeWidget(self.gb29446_scope_details)
        gb_form.addRow(self.gb29446_scope_toggle)
        gb_form.addRow(self.gb29446_scope_details)
        explanation_layout.removeWidget(self.gb29446_explanation)
        basis_layout.removeWidget(self.gb29446_basis)
        gb29446_layout.addWidget(self.gb29446_explanation)
        gb29446_layout.addWidget(self.gb29446_basis)
        gb29446_layout.removeWidget(self.gb29446_view_record)
        gb29446_layout.removeWidget(self.gb29446_export_word)
        result_actions = QHBoxLayout()
        result_actions.addStretch()
        result_actions.addWidget(self.gb29446_view_record)
        result_actions.addWidget(self.gb29446_export_word)
        gb29446_layout.addLayout(result_actions)
        self.gb29446_explanation_section.hide()
        self.gb29446_basis_section.hide()
        self.evaluation_scroll = scroll
        self.eval_standard.setEditable(False)
        self.eval_standard.setEnabled(False)
        self.gb29446_form_container.setStyleSheet("QWidget { background: white; }")
        self.gb29446_result_card.setStyleSheet("QFrame#card, QWidget#coreMetric, QWidget#coreMetrics { background: transparent; border: none; }")
        self._sync_mode_buttons()
        return page

    def _build_records(self) -> QWidget:
        page, layout = self._page("对标记录")
        self._record_page = 1
        controls = QHBoxLayout()
        self.record_search = QLineEdit()
        self.record_search.setPlaceholderText("搜索全部记录的企业、标准或历史业务文本")
        self.record_search.setClearButtonEnabled(True)
        self.record_status_filter = QComboBox()
        self.record_status_filter.addItems(["全部结果状态", "1级", "2级", "3级", "未达3级", "不完整", "不适用", "无法判定", "分项结果", "记录损坏"])
        self.record_search_timer = QTimer(self)
        self.record_search_timer.setSingleShot(True)
        self.record_search_timer.setInterval(200)
        self.record_search_timer.timeout.connect(self._record_filters_changed)
        self.record_search.textChanged.connect(lambda *_: self.record_search_timer.start())
        self.record_status_filter.currentIndexChanged.connect(self._record_filters_changed)
        refresh = QPushButton("刷新 / 重试")
        refresh.clicked.connect(self.refresh_records)
        view = QPushButton("查看")
        view.clicked.connect(self.view_selected_record)
        delete = QPushButton("删除选中记录")
        delete.setStyleSheet("color: #B42318;")
        delete.clicked.connect(self.delete_selected_record)
        controls.addWidget(self.record_search, 1)
        controls.addWidget(self.record_status_filter)
        controls.addWidget(refresh)
        layout.addLayout(controls)
        actions = QHBoxLayout()
        actions.addWidget(view)
        actions.addStretch()
        actions.addWidget(delete)
        layout.addLayout(actions)
        self.record_table = RecordTable(0, 7)
        self.record_table.setHorizontalHeaderLabels(["企业名称", "统计期", "标准", "核心结果", "结果状态", "评价时间", "操作"])
        self._configure_table(self.record_table)
        self.record_table.setWordWrap(True)
        self.record_table.horizontalHeader().setStretchLastSection(False)
        self.record_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.record_table.verticalHeader().setDefaultSectionSize(60)
        self.record_table.itemDoubleClicked.connect(lambda *_: self.view_selected_record())
        self.record_table.itemActivated.connect(lambda *_: self.view_selected_record())
        layout.addWidget(self.record_table, 1)
        foot = QHBoxLayout()
        self.record_count_label = QLabel("")
        self.record_previous = QPushButton("上一页")
        self.record_next = QPushButton("下一页")
        self.record_previous.clicked.connect(lambda: self._change_record_page(-1))
        self.record_next.clicked.connect(lambda: self._change_record_page(1))
        foot.addWidget(self.record_count_label, 1)
        foot.addWidget(self.record_previous)
        foot.addWidget(self.record_next)
        layout.addLayout(foot)
        return page

    def _record_filters_changed(self, *_args) -> None:
        self.record_search_timer.stop()
        self._record_page = 1
        self.refresh_records()

    def _change_record_page(self, delta: int) -> None:
        self._record_page = max(1, self._record_page + delta)
        self.refresh_records()

    def _build_settings(self) -> QWidget:
        self.settings_page = SettingsPage(
            software_version=__version__,
            standard_library_version=self._standard_library_version_text(),
            data_directory=str(self.context.paths.root),
            parent=self,
        )
        self.settings_page.create_backup_requested.connect(self.create_backup)
        self.settings_page.restore_backup_requested.connect(self.restore_backup)
        self.settings_page.open_data_directory_requested.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.context.paths.root)))
        )
        self.settings_page.view_diagnostics_requested.connect(self.show_diagnostics)
        self.settings_page.copy_diagnostics_requested.connect(self.copy_diagnostics)
        return self.settings_page

    @staticmethod
    def _configure_table(table: QTableWidget, *, editable: bool = False) -> None:
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(44)
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

    def _navigation_clicked(self, item: QListWidgetItem) -> None:
        key = item.data(Qt.ItemDataRole.UserRole)
        # 行变化已通过 currentRowChanged 导航；仅补当前父入口的重复点击。
        if item.flags() & Qt.ItemFlag.ItemIsEnabled and self.pages.currentWidget() is not self.page_widgets.get(key):
            self.navigate(key)

    def _scroll_to_gb29446_result(self) -> None:
        content = self.evaluation_scroll.widget()
        content.layout().activate()
        heading_y = self.gb29446_result_heading.mapTo(content, self.gb29446_result_heading.rect().topLeft()).y()
        self.evaluation_scroll.verticalScrollBar().setValue(max(0, heading_y - 18))

    def _page_changed(self, index: int) -> None:
        if index < 0:
            return
        item = self.navigation.item(index)
        if item and item.flags() & Qt.ItemFlag.ItemIsEnabled:
            self.navigate(item.data(Qt.ItemDataRole.UserRole))

    def refresh_all(self) -> None:
        self.refresh_home()
        self.refresh_standards()
        self.refresh_standard_combo()
        # 记录页只标记待刷新：全局刷新不再为用户没打开过的页面读取 200 条记录。
        self.mark_records_dirty()
        self.refresh_settings()
        self.refresh_formal_evaluation_readiness()

    def _standard_library_version_text(self) -> str:
        try:
            version = self.context.application.standard_library_version()
        except Exception:
            version = None
        return str(version) if version else "未安装"

    def refresh_settings(self) -> None:
        page = getattr(self, "settings_page", None)
        if page is not None:
            page.set_standard_library_version(self._standard_library_version_text())

    def refresh_formal_evaluation_readiness(self) -> None:
        try:
            message = self.context.application.formal_evaluation_block_message()
        except Exception:
            message = "当前安装文件不完整或已损坏，请重新安装完整版本。历史记录和备份仍可继续使用。"
        message = str(message).strip() if message else None
        # ECQ-RS05 M2 §四：没有正式可评价标准时，新建评价必须被禁用并给出用户真正
        # 能执行的动作；不得保留“空选择但仍可点击计算”。这只是一个额外阻断条件，
        # 不改变任何判定语义，也不影响“评价记录”里的历史记录查看。
        if message is None and hasattr(self, "eval_standard") and self.eval_standard.count() == 0:
            message = self._formal_scope_hint()
        if hasattr(self, "home_compatibility_notice"):
            self.home_compatibility_notice.setText(message or "")
            self.home_compatibility_notice.setVisible(message is not None)
            has_formal_scope = self.home_formal_scope_count.text() != "0 项"
            self.home_start_evaluation.setEnabled(has_formal_scope and message is None)
            self.home_empty_start.setEnabled(has_formal_scope and message is None)
        if hasattr(self, "evaluation_readiness_notice"):
            self.evaluation_readiness_notice.setText(message or "")
            self.evaluation_readiness_notice.setVisible(message is not None)
        if hasattr(self, "standard_evaluate_button"):
            standard_id = self._selected_library_standard_id()
            self.standard_evaluate_button.setEnabled(
                message is None and supports_formal_evaluation(standard_id)
            )
        if hasattr(self, "calculate_button"):
            has_evaluable_standard = (
                self.eval_standard.count() > 0 if hasattr(self, "eval_standard") else False
            )
            self.calculate_button.setEnabled(
                self.gb29446_rule_compatible and message is None and has_evaluable_standard and not getattr(self, "_calculating", False)
            )
            self._sync_evaluation_actions()

    def _sync_evaluation_actions(self) -> None:
        """保存后的主要动作是查看；重算仍调用原正式用例，明确生成新记录。"""
        busy = getattr(self, "_calculating", False)
        saved = self.last_result_id is not None and self._is_gb29446()
        role = "secondary" if saved else "primary"
        self.calculate_button.setText("正在计算…" if busy else "重新计算并生成新记录" if saved else "计算并判级")
        if self.calculate_button.property("role") != role:
            self.calculate_button.setProperty("role", role)
            self.calculate_button.style().unpolish(self.calculate_button)
            self.calculate_button.style().polish(self.calculate_button)

    def refresh_home(self) -> None:
        try:
            self._refresh_home_data()
        except Exception:
            _LOGGER.exception("首页读取失败")
            self.home_recent.setRowCount(0)
            self.home_recent.hide()
            self.home_empty_start.hide()
            self.home_recent_notice.setText("最近对标读取失败，请重试。")
            self.home_recent_notice.show()
            self.home_retry.show()

    def _refresh_home_data(self) -> None:
        today = date.today()
        standards = self.context.application.list_current_standards(today)
        all_standards = self.context.application.list_all_standards()
        records = self.context.application.list_recent_evaluations(6)
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
            self.home_scope_label.setText("本机标准库中没有已纳入正式评价范围的标准，请安装完整的新版本。")
            self.home_start_evaluation.setEnabled(False)
        self.home_evaluation_count.setText(str(self.context.application.count_evaluations()))
        self.home_standard_library_version.setText(self._standard_library_version_text())
        self.home_recent.setRowCount(0)
        self.home_retry.hide()
        self.home_recent_notice.setText("暂无对标记录")
        self.home_recent_notice.setVisible(not records)
        self.home_recent.setVisible(bool(records))
        self.home_empty_start.setVisible(not records)
        for record in records:
            row = self.home_recent.rowCount()
            self.home_recent.insertRow(row)
            # 存储为 UTC；普通页面按本机时区显示到秒，不显示微秒。
            period, core = "未记录", "记录损坏" if record.is_corrupted else "未记录"
            if not record.is_corrupted:
                try:
                    request, result, _snapshot = self.context.application.get_evaluation(record.evaluation_id)
                    period, custom, _ = decode_period_notes(request.notes)
                    period = custom if period == PERIOD_CUSTOM else period
                    period = (period or "未记录") if (request.notes or "").startswith("核算周期：") else "未记录"
                    if result.results:
                        item = result.results[0]
                        core = f"{self._format_result_number(item.actual_value)} {item.unit} · {self._gb29446_grade_label(item.grade)}"
                except Exception:
                    core = "结果暂不可读"
            values = [
                record.organization_name or "未填写企业名称", period,
                record.standard_number, core, format_local_datetime(record.created_at), "查看",
            ]
            for column, value in enumerate(values):
                cell = _item(value)
                cell.setData(Qt.ItemDataRole.UserRole, record.evaluation_id)
                self.home_recent.setItem(row, column, cell)
            view_button = QPushButton("查看")
            view_button.clicked.connect(lambda _=False, rid=record.evaluation_id: self._open_home_record(rid))
            self.home_recent.setCellWidget(row, 5, view_button)
        self.home_recent.setFixedHeight(self.home_recent.horizontalHeader().sizeHint().height() + max(1, len(records)) * 52 + 4)

    def refresh_standards(self) -> None:
        try:
            self._refresh_standards_data()
            self.standard_retry.hide()
        except Exception:
            _LOGGER.exception("标准目录读取失败")
            self.standard_table.setRowCount(0)
            self.standard_count_label.setText("标准目录读取失败，请重试。")
            self.standard_retry.show()

    def _refresh_standards_data(self) -> None:
        query = self.standard_search.text().strip().lower() if hasattr(self, "standard_search") else ""
        # The library is a catalogue of the 63 in-scope standards, not only
        # today's executable subset.  Draft/future entries remain visible so
        # users can find them and see why formal evaluation is unavailable.
        standards = [
            item
            for item in self.context.application.list_library_standards()
        ]
        self.standard_table.setRowCount(0)
        for standard in standards:
            haystack = f"{standard.number} {standard.title} {standard_scope_line(standard.id)} {' '.join(p.name for p in standard.products)}".lower()
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
            if standard.lifecycle_status is LifecycleStatus.OBSOLETE:
                status = "历史/已替代"
            selected_status = self.standard_status_filter.currentText()
            if selected_status != "全部标准状态" and not status.startswith(selected_status):
                self.standard_table.removeRow(row)
                continue
            values = [
                standard.number,
                standard.title,
                status,
                format_local_date(standard.effective_date),
                evaluation_support_label(standard),
            ]
            for column, value in enumerate(values):
                item = _item(value)
                item.setData(Qt.ItemDataRole.UserRole, standard.id)
                self.standard_table.setItem(row, column, item)
        self.standard_table.fit_columns()
        self.standard_count_label.setText(f"共 {self.standard_table.rowCount()} 项标准" if self.standard_table.rowCount() else "没有匹配结果")
        self.refresh_standard_detail()

    def _selected_library_standard_id(self) -> str | None:
        """当前标准库选中的标准 id；未选择时返回 ``None``。"""

        row = self.standard_table.currentRow()
        cell = self.standard_table.item(row, 0) if row >= 0 else None
        return cell.data(Qt.ItemDataRole.UserRole) if cell is not None else None

    def _library_standard(self, standard_id: str | None) -> StandardDefinition | None:
        if not standard_id:
            return None
        # 只读取被选中的那一个标准：原本为了取一条而重建整个标准库。
        return self.context.application.get_standard(standard_id)

    def refresh_standard_detail(self) -> None:
        """Show the selected standard's 适用范围 line, then its limits."""
        if not hasattr(self, "standard_indicator_table"):
            return
        self.standard_indicator_table.setRowCount(0)
        self.standard_requirements_basis.clear()
        standard_id = self._selected_library_standard_id()
        standard = self._library_standard(standard_id)
        if standard is None:
            self.standard_detail_label.setText("选择标准后查看适用范围")
            self.standard_confirmation_label.setText("选择标准后查看业务映射与软件核算状态")
            self.standard_indicator_table.setVisible(False)
            self.standard_evaluate_button.setEnabled(False)
            self.standard_official_button.setEnabled(False)
            self.standard_official_status.setText("请先选择标准")
            self.refresh_formal_evaluation_readiness()
            return
        self.standard_detail_title.setText(f"{standard.number} {standard.title}")
        state = next((self.standard_table.item(row, 2).text() for row in range(self.standard_table.rowCount())
                      if self.standard_table.item(row, 0).data(Qt.ItemDataRole.UserRole) == standard.id), "")
        self.standard_metadata.setText(f"标准编号：{standard.number}\n标准名称：{standard.title}\n标准状态：{state}\n实施日期：{format_local_date(standard.effective_date)}")
        self.standard_requirements_notice.setText(
            "选煤电力单耗三级上限如下。统计范围：" + _gb29446_statistics_scope_text()
            if supports_formal_evaluation(standard.id)
            else "软件接入及验收尚未完成，暂不展示未经确认的限值明细。"
        )
        # 选中标准后只有一行：所有标准共用同一个「适用范围」字段与位置。
        self.standard_detail_label.setText(standard_scope_line(standard.id))
        self.standard_confirmation_label.setText(standard_confirmation_message(standard.id))
        official_url = official_source_url(standard.id)
        self.standard_official_button.setEnabled(official_url is not None)
        self.standard_official_button.setToolTip(official_url or NO_OFFICIAL_SOURCE_LABEL)
        self.standard_official_status.setText(
            OFFICIAL_SOURCE_PLATFORM_NAME if official_url else NO_OFFICIAL_SOURCE_LABEL
        )
        # 未纳入正式评价范围的标准不提供可执行的评价入口。
        supported = supports_formal_evaluation(standard.id)
        # 旧规则可能尚未按批准映射重新验收；清空后只为正式支持的标准重建限值。
        # 切换标准时不会把上一条标准的旧限值留在隐藏表格中。
        self.standard_indicator_table.setVisible(supported)
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

        requirement_basis = []
        if supported:
            for product in standard.products:
                for indicator in product.indicators:
                    base = indicator.base_thresholds or indicator.thresholds
                    # 「适用条件/说明」不再出现在普通标准库里：条件与内部备注代码都不再展示。
                    values = [
                        product.selection_values.get("coal_type", product.name),
                        indicator.name,
                        indicator.unit,
                        limit_value(base.level_1),
                        limit_value(base.level_2),
                        limit_value(base.level_3),
                    ]
                    detail_row = self.standard_indicator_table.rowCount()
                    self.standard_indicator_table.insertRow(detail_row)
                    for column, value in enumerate(values):
                        self.standard_indicator_table.setItem(detail_row, column, _item(value))
                    for line in self._gb29446_basis_for_display(indicator).splitlines():
                        if line.startswith("等级依据："):
                            requirement_basis.append(f"{values[0]}：{line}")
        self.standard_requirements_basis.setText("\n".join(dict.fromkeys(requirement_basis)))
        self.standard_requirements_basis.setVisible(bool(requirement_basis))
        self.standard_indicator_table.setFixedHeight(self.standard_indicator_table.horizontalHeader().sizeHint().height() + self.standard_indicator_table.rowCount() * 44 + 4)
        self.refresh_formal_evaluation_readiness()

    def _selection_mode(self) -> StandardSelectionMode:
        """新建评价固定使用**当前正式可评价**标准（ECQ-RS05 M2 §四）。

        请求模型仍带 ``selection_mode`` 字段：既有存档、历史记录与领域层
        （``StandardSelectionMode`` 的 CURRENT / HISTORICAL / FUTURE 语义）都保持不变，
        只是普通界面不再提供“历史 / 尚未实施”入口——0.2.0 没有它们的用户用途。
        """

        return StandardSelectionMode.CURRENT

    def _standards_for_selection(self) -> list[StandardDefinition]:
        return self.context.application.list_standards_for_selection(date.today(), self._selection_mode())

    def _formally_evaluable_standards(self) -> list[StandardDefinition]:
        """当前选择方式下**可以正式评价**的标准（正式评价范围注册表决定）。"""

        return filter_formally_evaluable(self._standards_for_selection())

    def _formal_scope_hint(self) -> str:
        """用于说明“为什么只有这些标准可选”的中文提示（来自注册表，不写死编号）。"""

        evaluable = filter_formally_evaluable(self.context.application.list_library_standards())
        if not evaluable:
            return "本机标准库中没有已纳入正式评价范围的标准，请安装完整的新版本。"
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
            if self._is_gb29446() and self.current_standard.products:
                product = self.current_standard.products[0]
                labels = gb29446_business_labels(self.current_standard, product)
                for widget, key, suffix in (
                    (self.gb29446_coal_type, "coal_type", ""),
                    (self.gb29446_process, "washing_process", ""),
                    (self.gb29446_electricity, "electricity_consumption", "（kW·h）"),
                    (self.gb29446_raw_coal, "raw_coal_input", "（t）"),
                    (self.gb29446_factor, "process_factor", "（自动匹配，只读）"),
                ):
                    label_widget = self.gb29446_business_fields.labels.get(widget)
                    if isinstance(label_widget, QLabel):
                        label_widget.setText(_rich_text(labels[key] + suffix + (" · 来源：附录A 表A.1" if key == "process_factor" else "")))
                self.gb29446_electricity.setPlaceholderText("输入统计期内选煤电力消耗量")
                self.gb29446_raw_coal.setPlaceholderText("输入" + labels["raw_coal_input"])
                self.gb29446_factor.setPlaceholderText("待选择工艺")
            self.gb29446_coal_buttons.setEnabled(not incompatible)
            for widget in (self.gb29446_coal_buttons, self.gb29446_process, self.gb29446_factor):
                self.gb29446_business_fields.labels[widget].parentWidget().setVisible(not incompatible)
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
        self.gb29446_explanation_section.hide()
        self.gb29446_basis_section.hide()

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
        self._sync_coal_radios()

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
        combo.addItem("请选择选煤工艺类型", None)
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

    def _sync_coal_radios(self, *_args) -> None:
        text = self.gb29446_coal_type.currentText()
        self.coal_button_group.setExclusive(False)
        for button in self.coal_button_group.buttons():
            button.setChecked(button.text() == text)
        self.coal_button_group.setExclusive(True)

    def _gb29446_process_changed(self, _index: int = 0) -> None:
        self._update_gb29446_factor()

    def _gb29446_period_changed(self, _index: int = 0) -> None:
        is_custom = self.gb29446_period.currentData() == "自定义"
        self.gb29446_custom_period.setVisible(is_custom)

    def _clear_gb29446_result(self) -> None:
        self._result_invalidated = False
        self.gb29446_field_error.clear()
        self.last_result_id = None
        self.gb29446_export_word.setEnabled(False)
        self.gb29446_view_record.setEnabled(False)
        self.gb29446_metrics.hide()
        self.gb29446_result_ed.setText("— kW·h/t")
        self.gb29446_result_grade.setText("—")
        self.gb29446_result_message.setText("填写数据后计算")
        self.gb29446_explanation.setText("完成计算后显示本次计算与判定说明。")
        self.gb29446_basis.setText("完成计算后显示本次评价的标准依据。")
        self.gb29446_explanation.hide()
        self.gb29446_basis.hide()
        self._sync_evaluation_actions()

    def _gb29446_inputs_changed(self, *_args) -> None:
        if self._is_gb29446():
            had_result = self.last_result_id is not None or getattr(self, "_result_invalidated", False)
            self._clear_gb29446_result()
            self.gb29446_field_error.clear()
            if had_result:
                self._result_invalidated = True
                self.gb29446_result_message.setText("数据已修改，请重新计算")

    def _standard_changed(self) -> None:
        standard_id = self.eval_standard.currentData()
        mode = self._selection_mode()
        self.current_standard = (
            self.context.application.get_standard_for_evaluation(standard_id, date.today(), mode)
            if standard_id else None
        )
        self.eval_standard_summary.setText(
            f"{self.current_standard.number}　{self.current_standard.title}" if self.current_standard
            else "暂无可用的正式对标标准"
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
            # 新建评价只提供“当前正式可评价”的标准，因此正常情况下这里没有需要重复的
            # 说明；只有规则数据本身带出的警告（例如尚未实施）才显示。
            self.eval_standard_status.setText(warning or "")
        else:
            self.eval_standard_status.setText("本机标准库中没有已纳入正式评价范围的标准，请安装完整的新版本。")
        self.eval_standard_status.setVisible(bool(self.eval_standard_status.text()))
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
        self.refresh_formal_evaluation_readiness()

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

    def _gb29446_quantity_input(self, product, key: str, field: QLineEdit) -> InputValue:
        """校验并包装 GB 29446 标准公式必须的一个数量输入（MUST BLOCK / WARN ONLY）。

        标签与单位都取自规则定义本身，界面不写死业务文字。必须**当场阻止**、且不生成
        任何评价记录的三类情况（对应 §五 的分类）：

        * 空值——标准公式 ``e_d = E_d × k ÷ m`` 需要该数据，``m`` 还是分母；
        * 非数字或非有限值——公式根本无法代入；
        * 小于或等于 0——``m`` 为 0 即除零；``E_d`` 的领域守卫同样要求大于 0
          （``EvaluationEngine._validate_inputs``），界面只做前置拦截，不重算任何东西。

        其余一律放行：例如 ``1e999`` 这类极大但有限的值标准并未禁止，界面不发明任何上限，
        只由结果与等级如实呈现。
        """

        definition = next((item for item in product.input_definitions if item.key == key), None)
        if definition is None:
            # 这两个数量由**指标**声明（产品只声明煤种/工艺等选择项），查找方式与引擎一致。
            definition = next(
                (
                    item
                    for indicator in product.indicators
                    for item in indicator.input_definitions
                    if item.key == key
                ),
                None,
            )
        label = definition.label if definition is not None else key
        raw = field.text().strip()
        if not raw:
            raise ValueError(f"{label} 不能为空。")
        try:
            value = parse_decimal(raw, field_name=label)
        except ValueError as exc:
            # 领域解析器的中文提示直接复用，避免界面出现第二套数值口径。
            raise ValueError(f"{exc}。") from exc
        if value <= 0:
            raise ValueError(f"{label} 必须大于 0（软件防误录校验）。")
        # 保留用户录入的原始十进制字面量：Numeric full-value 语义不得被界面改写。
        return InputValue(value=raw, unit=definition.unit if definition is not None else None)

    def _collect_gb29446_request(self) -> EvaluationRequest:
        assert self.current_standard is not None
        period = str(self.gb29446_period.currentData() or "全年")
        custom_period = self.gb29446_custom_period.text().strip()
        if period == "自定义" and not custom_period:
            raise ValueError(f"请填写自定义{PERIOD_LABEL}。")
        product_id = self.gb29446_coal_type.currentData()
        if not product_id:
            raise ValueError("请选择选煤企业类型。")
        product = next(
            (item for item in self.current_standard.products if item.id == product_id),
            None,
        )
        if product is None:
            raise ValueError("所选选煤企业类型没有对应的标准评价规则。")
        process = self.gb29446_process.currentData()
        if not process:
            raise ValueError("请选择选煤工艺类型。")
        inputs = {"washing_process": InputValue(value=str(process))}
        # 标准公式 e_d = E_d × k ÷ m 的两个必填量：空值 / 非数字 / 不大于 0 必须在这里
        # 就被拒绝（MUST BLOCK），不能先生成一条“不完整”记录再让用户去结果页里找原因。
        for key, field in (
            ("electricity_consumption", self.gb29446_electricity),
            ("raw_coal_input", self.gb29446_raw_coal),
        ):
            inputs[key] = self._gb29446_quantity_input(product, key, field)
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
        if getattr(self, "_calculating", False):
            return
        self._calculating = True
        self.calculate_button.setEnabled(False)
        self.calculate_button.setText("正在计算…")
        try:
            self._calculate_evaluation(request)
        except Exception as exc:  # noqa: BLE001 - 兜底，绝不静默
            _LOGGER.exception("计算评价时发生未预期错误")
            QMessageBox.critical(
                self,
                "计算失败",
                f"计算未完成（{type(exc).__name__}）。详细信息已写入日志，请重试。",
            )

        finally:
            self._calculating = False
            self.refresh_formal_evaluation_readiness()

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
                    message = str(exc) if type(exc) is ValueError else "评价信息未通过校验，请检查统计期、选煤企业类型、选煤工艺类型及输入数据。"
                    # 结果卡是富文本：E_d / e_d 必须按真下标呈现（提示文字本身保持纯文本）。
                    self.gb29446_result_message.setText(_rich_text(message))
                    self.gb29446_field_error.setText(message)
                    target = self.gb29446_electricity if "电力" in message else self.gb29446_raw_coal if "原煤" in message else self.gb29446_custom_period if "统计期" in message else self.gb29446_process
                    target.setFocus()
                    self.evaluation_scroll.ensureWidgetVisible(target)
                    self.gb29446_explanation.setText("请根据提示修正评价数据后重新计算。")
                    QMessageBox.warning(self, "评价信息未通过校验", message)
                    return
            request = request or self._collect_request()
            is_preview = request.selection_mode is StandardSelectionMode.FUTURE
            result = self.context.application.preview_evaluation(request) if is_preview else self.context.application.evaluate(request)
        except Exception as exc:
            if is_gb29446:
                if type(exc) is ValueError:
                    self.gb29446_result_message.setText(_rich_text(f"无法计算：{exc}"))
                    self.gb29446_explanation.setText("请根据提示修正评价数据后重新计算。")
                    QMessageBox.warning(self, "无法计算", str(exc))
                else:
                    message = "计算未完成，请检查输入数据、单位和选煤工艺类型后重试。"
                    self.gb29446_result_message.setText(message)
                    QMessageBox.critical(self, "无法计算", message)
            else:
                QMessageBox.critical(self, "无法计算", _friendly_error(exc, "计算和判级"))
            return
        self.last_result_id = None if is_preview else result.evaluation_id
        self.gb29446_view_record.setEnabled(bool(self.last_result_id) and is_gb29446)
        self.gb29446_export_word.setEnabled(bool(self.last_result_id) and is_gb29446)
        try:
            display_ok = self._show_gb29446_result(request, result)
        except Exception:
            _LOGGER.exception("记录保存后的结果展示失败")
            display_ok = False
        if is_gb29446 and not display_ok:
            self.gb29446_export_word.setEnabled(False)
            self.gb29446_result_message.setText(
                "记录已保存，结果暂未显示，请查看对标记录。" if self.last_result_id else "预览结果暂未显示。"
            )
            if not is_preview:
                self.mark_records_dirty()
            QMessageBox.warning(
                self, "结果展示未完成",
                "评价记录已保存，但结果展示未完成；请在评价记录中查看，必要时联系技术支持。"
                if not is_preview else "预览结果展示未完成，请重试。",
            )
            return
        if result.standard_id == "gb-29446-2019":
            self.eval_results.setRowCount(0)
            self.eval_summary.setText("")
            self.refresh_home()
            if not is_preview:
                # 新记录只把「评价记录」标记为待刷新：用户此时在「新建评价」页。
                self.mark_records_dirty()
            if any(item.grade is Grade.INCOMPLETE for item in result.results):
                QMessageBox.warning(
                    self,
                    "无法计算",
                    "输入数据未通过校验，未生成电耗等级。请查看评价结果中的提示并修正。",
                )
                return
            QTimer.singleShot(0, self._scroll_to_gb29446_result)
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
            # 新记录只把「评价记录」标记为待刷新，不在这一刻读取 200 条。
            self.mark_records_dirty()
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
        # 新工作树 AGENTS §2.8 和批准映射 §13.4 D01 已取代旧专用标签。
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
        return render_gb29446_warning(warning, standard, product) if standard is not None and product is not None else warning

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

    def _show_gb29446_result(self, request: EvaluationRequest, result: EvaluationResult) -> bool:
        if result.standard_id != "gb-29446-2019":
            return True
        item = next(
            (
                row
                for row in result.results
                if row.indicator_id in {"GB_29446-2019.coking-coal", "GB_29446-2019.power-coal"}
            ),
            result.results[0] if result.results else None,
        )
        if item is None:
            self.gb29446_metrics.hide()
            return False

        self.gb29446_basis.setText(self._gb29446_basis_for_display(item))
        if item.actual_value is None:
            self.gb29446_result_ed.setText("— kW·h/t")
            self.gb29446_result_grade.setText("—")
            self.gb29446_result_message.setText(
                _rich_text(
                    "无法计算："
                    + "；".join(
                        self._gb29446_warning_for_display(request, warning) for warning in item.warnings
                    )
                )
            )
            self.gb29446_explanation.setText("请根据提示补全或修正评价数据后重新计算。")
            self.gb29446_explanation.show()
            self.gb29446_export_word.setEnabled(False)
            return True

        try:
            if self.last_result_id == result.evaluation_id:
                view = self.context.application.get_report_view(result.evaluation_id)
            else:
                if self.current_standard is None:
                    raise ValueError("缺少预览所用规则。")
                view = build_report_view(request, result, self.current_standard)
        except Exception:
            _LOGGER.exception("选煤结果共享视图生成失败：%s", result.evaluation_id)
            self.gb29446_export_word.setEnabled(False)
            self.gb29446_result_message.setText("结果展示未完成；已保存的评价记录未被修改。")
            return False
        self.gb29446_result_ed.setText(f"{view.actual.value} {view.actual.unit}")
        self.gb29446_metrics.show()
        self.gb29446_result_grade.setText(view.grade.value)
        self.gb29446_result_grade.setStyleSheet("color: #956420;" if item.grade is Grade.NOT_QUALIFIED else "color: #18364F;")
        self.gb29446_result_message.setText("已生成对标记录。重新计算将生成新记录。" if self.last_result_id else "预览结果")
        self.gb29446_explanation.setText(_rich_text("\n".join((*view.explanation, *view.warnings))))
        self.gb29446_explanation.show()
        self.gb29446_basis.setText("\n".join(view.basis))
        self.gb29446_scope_details.setText(view.scope.value)
        return True

    def refresh_records(self) -> None:
        selected = self._selected_record_id()
        scroll = self.record_table.verticalScrollBar().value()
        try:
            result = self.context.application.query_evaluations(
                query=self.record_search.text(),
                status="" if self.record_status_filter.currentIndex() == 0 else self.record_status_filter.currentText(),
                page=self._record_page, page_size=20,
            )
        except Exception:
            _LOGGER.exception("对标记录查询失败")
            self.record_table.setRowCount(0)
            self.record_count_label.setText("记录读取失败，请重试；原记录未被修改。")
            self.record_previous.setEnabled(False)
            self.record_next.setEnabled(False)
            self._records_dirty = True
            self._records_loaded = False
            return
        self._record_page = result.page
        self.record_table.setRowCount(0)
        for record in result.items:
            row = self.record_table.rowCount()
            self.record_table.insertRow(row)
            values = [record.organization, record.period, record.standard, record.core_result, record.status,
                      format_local_datetime(record.created_at), "查看"]
            for column, value in enumerate(values):
                cell = _item(value, align_right=column == 3)
                cell.setToolTip(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, record.evaluation_id)
                self.record_table.setItem(row, column, cell)
            button = QPushButton("查看")
            button.clicked.connect(lambda _=False, rid=record.evaluation_id: self.view_record(rid))
            self.record_table.setCellWidget(row, 6, button)
            if record.evaluation_id == selected:
                self.record_table.selectRow(row)
        self.record_table.fit_columns()
        self.record_table.verticalScrollBar().setValue(scroll)
        pages = max(1, (result.total + result.page_size - 1) // result.page_size)
        self.record_count_label.setText(f"共 {result.total} 条 · 第 {result.page} / {pages} 页" if result.total else "没有匹配记录" if self.record_search.text() or self.record_status_filter.currentIndex() else "暂无对标记录")
        self.record_previous.setEnabled(result.page > 1)
        self.record_next.setEnabled(result.page < pages)
        self._records_loaded = True
        self._records_dirty = False

    def mark_records_dirty(self) -> None:
        """记录列表已过期，但不一定现在就去读它。

        保存、删除、恢复只把列表标记为待刷新：用户正看着「评价记录」页时立即重建，
        否则等下次进入该页时再重建。这样全局刷新不会替一个从未打开过的页面读取
        200 条记录，而页面上显示的内容又不会过期。
        """
        self._records_dirty = True
        if self.pages.currentWidget() is self.page_widgets["records"]:
            self.refresh_records()

    def _selected_record_id(self) -> str | None:
        row = self.record_table.currentRow()
        cell = self.record_table.item(row, 0) if row >= 0 else None
        return cell.data(Qt.ItemDataRole.UserRole) if cell is not None else None

    def view_selected_record(self) -> None:
        evaluation_id = self._selected_record_id()
        if not evaluation_id:
            QMessageBox.warning(self, "未选择", "请选择一条对标记录。")
            return
        self.view_record(evaluation_id)

    def view_record(self, evaluation_id: str) -> None:
        try:
            loaded = self.context.application.get_evaluation(evaluation_id)
        except StorageCorruptionError:
            _LOGGER.exception("保存记录损坏：%s", evaluation_id)
            self.record_detail_page.show_error(evaluation_id, "记录损坏：保存数据无法读取。记录已保留，请联系技术支持。")
        except Exception:
            _LOGGER.exception("保存记录读取失败：%s", evaluation_id)
            self.record_detail_page.show_error(evaluation_id, "记录读取失败，请返回列表后重试。")
        else:
            if loaded is None:
                self.record_detail_page.show_error(evaluation_id, "该对标记录已被删除或不存在。")
            else:
                view = None
                reason = "该标准尚未开放 Word 报告。"
                if loaded[1].standard_id == GB29446_STANDARD_ID:
                    try:
                        view = self.context.application.get_report_view(evaluation_id)
                        reason = ""
                    except (ValueError, LookupError) as exc:
                        reason = str(exc)
                    except Exception:
                        _LOGGER.exception("历史报告视图不可用：%s", evaluation_id)
                        reason = "保存的报告数据暂时无法读取，请重试。"
                self.record_detail_page.show_record(loaded, view, reason)
        self.navigate("record_detail")

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
        # ECQ-RS05 M2 §四：普通界面不再提供版本范围选择。请求里的 ``selection_mode``
        # 仍按原值保留（历史存档/领域层语义不变），只是不再驱动任何界面控件。
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
                    "该标准当前不在可正式评价的标准列表中，请安装完整的新版本后重试。"
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
            self.navigate("evaluation")

    def export_selected_record(self) -> None:
        """导出所选记录的 Excel 能力（保留）。

        本轮只按 Owner 要求移除了「评价记录」页上的普通界面按钮；导出本身仍由
        :meth:`ApplicationFacade.export_evaluation` 提供，程序化入口保持不变。
        """

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

    def export_latest_word_report(self) -> None:
        if self.last_result_id:
            self.export_word_record(self.last_result_id)

    def export_word_record(self, evaluation_id: str) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "导出Word报告", "选煤电力单耗等级评价报告.docx", "Word文档 (*.docx)"
        )
        if not path:
            return
        try:
            self.context.application.export_word_report(evaluation_id, Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", _friendly_error(exc, "导出Word报告"))
            return
        QMessageBox.information(self, "导出完成", path)

    def delete_selected_record(self) -> None:
        evaluation_id = self._selected_record_id()
        if not evaluation_id:
            return
        organization = self.record_table.item(self.record_table.currentRow(), 0).text()
        if QMessageBox.question(self, "确认删除", f"删除“{organization}”的这条对标记录？原始追溯数据会保留。", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self.context.application.delete_evaluation(evaluation_id)
        self.refresh_all()

    def create_backup(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "创建备份", f"uebench-{date.today():%Y%m%d}.uebackup", "UEBench备份 (*.uebackup)")
        if not path:
            return
        try:
            self.context.application.create_backup(Path(path))
        except Exception as exc:
            # 技术详情（异常类型 / errno / 路径）只进日志；用户必须看到明确的
            # 中文失败提示，且失败绝不显示“备份完成”，异常也不得传播成未处理。
            _LOGGER.exception("创建备份失败：%s", path)
            QMessageBox.critical(self, "备份失败", _backup_failure_message(exc))
            return
        QMessageBox.information(self, "备份完成", path)

    def restore_backup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "恢复备份", "", "UEBench备份 (*.uebackup)")
        if not path:
            return
        if QMessageBox.question(self, "确认恢复", "恢复将替换当前数据，并先自动创建恢复前备份。是否继续？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.context.application.restore_backup(Path(path))
            self.refresh_all()
            readiness = self.context.application.formal_evaluation_block_message()
            if readiness:
                QMessageBox.warning(self, "数据已恢复", f"数据已恢复。{readiness}")
            else:
                QMessageBox.information(self, "恢复完成", "数据已恢复。")
        except Exception as exc:
            _LOGGER.exception("恢复备份失败：%s", path)
            QMessageBox.critical(self, "恢复失败", _restore_failure_message(exc))

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
        """返回仅供诊断信息使用的完整标准库身份。"""
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
        placeholder = "未安装" if has_service else "服务不可用"
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

    # -- 最近一次启动/恢复后的标准库对账（仅供高级诊断） -------------------

    def _package_reconciliation_outcome(self):
        """最近一次启动标准包对账结果；组合根未记录或旧版门面不支持时返回 ``None``。"""

        getter = getattr(self.context.application, "last_package_reconciliation", None)
        if getter is None:
            return None
        try:
            return getter()
        except Exception:
            return None

    def _copy_diagnostics(self, text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    def copy_diagnostics(self) -> None:
        self._copy_diagnostics(self.diagnostics_report())
        QMessageBox.information(self, "诊断信息", "诊断信息已复制到剪贴板。")

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
        try:
            with external_browser_environment():
                requested = bool(QDesktopServices.openUrl(QUrl(url)))
        except Exception:
            _LOGGER.exception("官方页面打开请求失败")
            requested = False
        if getattr(self, "official_source_dialog", None):
            self.official_source_dialog.close()
        self.official_source_dialog = OfficialSourceDialog(url, requested, self)
        self.official_source_dialog.open()
        return requested

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
                self, "暂无可正式评价的标准", "本机标准库中没有已纳入正式评价范围的标准，请安装完整的新版本。"
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
        if self.eval_standard.currentData() == standard_id:
            self.navigate("evaluation")
            return True
        self.refresh_standard_combo()
        combo_index = self.eval_standard.findData(standard_id)
        if combo_index < 0:
            QMessageBox.warning(
                self,
                "标准不可用",
                "该标准当前不在可正式评价的标准列表中，请安装完整的新版本后重试。",
            )
            return False
        self.eval_standard.setCurrentIndex(combo_index)
        self._standard_changed()
        self.navigate("evaluation")
        return True


def create_main_window(context: AppContext) -> MainWindow:
    return MainWindow(context)
