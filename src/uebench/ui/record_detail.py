"""独立历史只读页：仅消费保存的三件快照及报告视图。"""
import html
import re
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget, QTextEdit
from uebench.application.gb29446 import decode_period_notes, GB29446_STANDARD_ID
from uebench.application.reporting import gb29446_business_labels, render_gb29446_warning
from uebench.application.official_sources import official_source_url, NO_OFFICIAL_SOURCE_LABEL
from uebench.domain.models import GRADE_LABELS, Grade
from .presentation import format_local_date, format_local_datetime


def rich_lines(lines):
    return re.sub(r"([Ee])_d", r"\1<sub>d</sub>", html.escape("\n".join(lines))).replace("\n", "<br>")


def section(title, lines):
    return f'<h3 style="color:#18364F; font-size:16px; margin-top:22px;">{title}</h3><p style="line-height:160%;">{rich_lines(lines)}</p>'


class RecordDetailPage(QWidget):
    back_requested = Signal()
    export_requested = Signal(str)
    source_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.record_id = None
        self.standard_id = None
        body = QVBoxLayout(self)
        body.setContentsMargins(24, 20, 24, 20)
        back = QPushButton("返回对标记录")
        back.clicked.connect(self.back_requested)
        body.addWidget(back, 0, Qt.AlignLeft)
        self.title = QLabel("对标记录详情")
        self.title.setWordWrap(True)
        self.title.setProperty("class", "pageTitle")
        body.addWidget(self.title)
        actions = QHBoxLayout()
        actions.addStretch()
        self.source_button = QPushButton("查看标准原文")
        self.source_button.setObjectName("recordOfficialSourceButton")
        self.source_button.clicked.connect(lambda: self.source_requested.emit(self.standard_id))
        self.export_button = QPushButton("导出Word报告")
        self.export_button.setObjectName("recordExportWordButton")
        self.export_button.setProperty("role", "primary")
        self.export_button.clicked.connect(lambda: self.export_requested.emit(self.record_id))
        actions.addWidget(self.source_button)
        actions.addWidget(self.export_button)
        body.addLayout(actions)
        self.notice = QLabel("")
        self.notice.setWordWrap(True)
        body.addWidget(self.notice)
        self.tabs = QTabWidget()
        self.result_content = QTextEdit()
        self.result_content.setObjectName("record_detail_content")
        self.input_content = QTextEdit()
        self.input_content.setObjectName("record_detail_inputs")
        for text in (self.result_content, self.input_content):
            text.setReadOnly(True)
            text.document().setDocumentMargin(20)
        self.tabs.addTab(self.result_content, "基本信息与结果")
        self.tabs.addTab(self.input_content, "输入数据与计算依据")
        body.addWidget(self.tabs, 1)

    def show_error(self, record_id, message):
        self.record_id = record_id
        self.standard_id = None
        self.title.setText("对标记录详情")
        self.notice.setText(message)
        self.export_button.setEnabled(False)
        self.source_button.setEnabled(False)
        self.result_content.setPlainText(message)
        self.input_content.setPlainText("保存数据不可读取，未使用当前规则补造信息。")
        self.tabs.setCurrentIndex(0)

    def show_record(self, loaded, view, export_reason):
        request, result, snapshot = loaded
        self.record_id = result.evaluation_id
        self.standard_id = result.standard_id
        self.title.setText(request.organization_name or "对标记录详情")
        self.notice.setText("这是保存时结果。" + (" Word 不可用：" + export_reason if export_reason else ""))
        self.export_button.setEnabled(view is not None)
        self.export_button.setToolTip(export_reason or "使用该记录保存时的数据生成报告")
        source = official_source_url(result.standard_id)
        self.source_button.setEnabled(bool(source))
        self.source_button.setToolTip(source or NO_OFFICIAL_SOURCE_LABEL)
        if not source:
            self.notice.setText(self.notice.text() + " " + NO_OFFICIAL_SOURCE_LABEL + "。")
        period = "未记录"
        if (request.notes or "").startswith("核算周期："):
            code, custom, _ = decode_period_notes(request.notes)
            period = custom if code == "自定义" else code
        basic = [f"标准：{result.standard_number} {result.standard_title}",
                 f"企业名称：{request.organization_name or '未填写企业名称'}", f"统计期：{period}",
                 f"评价时间：{format_local_datetime(result.evaluated_at)}", f"评价日期：{format_local_date(request.evaluation_date)}"]
        product = next((p for p in snapshot.products if p.id == request.product_id), None)
        inputs = []
        if product:
            labels = gb29446_business_labels(snapshot, product) if result.standard_id == GB29446_STANDARD_ID else {}
            definitions = list(product.input_definitions) + [d for i in product.indicators for d in i.input_definitions]
            labels.update({d.key: labels.get(d.key, d.label) for d in definitions})
            for key, value in request.inputs.items():
                if result.standard_id == GB29446_STANDARD_ID and key not in {"washing_process", "electricity_consumption", "raw_coal_input"}:
                    continue
                inputs.append(f"{labels.get(key, '保存的输入项')}：{value.value} {value.unit or ''}".strip())
        else:
            inputs.append("保存的规则快照缺少对应产品定义，未从当前规则补充字段名称。")
        if view is not None:
            basic += [f"{view.actual.label}：{view.actual.value} {view.actual.unit}", f"评价结果：{view.grade.value}",
                      *(f"{f.label}：{f.value} {f.unit}" for f in view.thresholds), *view.explanation, *view.warnings]
            fields = (view.enterprise_type, view.process_type, view.electricity, view.raw_coal, view.factor)
            inputs = [f"{f.label}：{f.value} {f.unit}" for f in fields if f is not None]
            inputs += [*view.explanation, *view.basis, f"{view.scope.label}：{view.scope.value}", *view.warnings]
            if "原结果未重新计算" in view.mapping_adoption:
                inputs.append(view.mapping_adoption)
        else:
            for item in result.results:
                label = "未达3级" if result.standard_id == GB29446_STANDARD_ID and item.grade is Grade.NOT_QUALIFIED else GRADE_LABELS[item.grade]
                basic += [f"指标：{item.indicator_name}", f"实际值：{item.actual_value if item.actual_value is not None else '未记录'} {item.unit}", f"等级：{label}"]
                if item.grade is Grade.INCOMPLETE:
                    basic.append("数据不完整，未形成正常等级或符合性结论。")
                basic += [f"{GRADE_LABELS[Grade(key)]}上限：{value} {item.unit}" for key, value in item.corrected_thresholds.items()]
                inputs += [f"标准依据：{ref.standard_number} 第{ref.page}页 {ref.clause or ''} {ref.table or ''}" for ref in item.source_references]
                if product:
                    inputs += [render_gb29446_warning(w, snapshot, product) if result.standard_id == GB29446_STANDARD_ID else w for w in item.warnings]
            for energy in request.energy_lines:
                inputs.append(f"能源明细：{energy.energy_name}，{'输入' if energy.direction == 'input' else '输出'} {energy.amount} {energy.unit}；折标系数 {energy.standard_coal_coefficient} {energy.coefficient_unit}；分摊比例 {energy.allocation_ratio}")
            for line in request.production_lines:
                inputs.append(f"产量明细：{line.product_name}，{line.quantity} {line.unit}；折算系数 {line.conversion_factor}；{'合格' if line.qualified else '不合格'}")
        if view is not None:
            lead = '<table width="100%" cellpadding="8"><tr><td>选煤电力单耗</td><td>评价结果</td></tr><tr>'
            lead += f'<td style="font-size:26px; color:#18364F;">{html.escape(view.actual.value)} {html.escape(view.actual.unit)}</td><td style="font-size:26px; color:#18364F;">{html.escape(view.grade.value)}</td></tr></table>'
            self.result_content.setHtml(lead + section("基本信息", basic[:5]) + section("等级上限与判级依据", basic[7:]))
            field_count = sum(f is not None for f in fields)
            self.input_content.setHtml(section("输入数据", inputs[:field_count]) + section("计算与依据", inputs[field_count:]))
        else:
            self.result_content.setHtml(section("保存时信息与结果", basic))
            self.input_content.setHtml(section("保存的输入与依据", inputs))
        self.tabs.setCurrentIndex(0)
        for text in (self.result_content, self.input_content):
            text.verticalScrollBar().setValue(0)
