"""焦炭隔离预览页。普通正式流程不注册此页，不写记录。"""
from decimal import localcontext
from html import escape

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QScrollArea, QTextBrowser,
)
from .wheel_safe_combo import WheelSafeComboBox
from uebench.application.gb21342 import preview_coke
from uebench.domain.coke_flows import normalize_energy, REFERENCES
from .coke_flows_form import CokeFlowsForm
from uebench.domain.models import GRADE_LABELS
from uebench.domain.gb21342 import (
    CokeAssessmentInput, CokeEnergyInput, ExternalServicesStatus, LABELS,
    _optional_number, _declared_context,
)


def result_html(result, flow_warnings=()):
    def number(value):
        return "待确定" if value is None else escape(str(value))
    energy = result.energy
    rows = "".join(
        f"<tr><td>{escape(GRADE_LABELS[level.grade])}</td><td>{number(level.threshold)}</td>"
        f"<td>{'待确定' if level.matched is None else '满足' if level.matched else '不满足'}</td>"
        f"<td>{escape('；'.join(level.undetermined_reasons))}</td></tr>"
        for level in result.levels
    )
    warnings = "<br>".join(escape(w) for w in (*result.warnings, *flow_warnings))
    return (
        f"<h2>{escape(GRADE_LABELS[result.grade])}</h2>"
        f"<p>实际能耗：{number(energy.actual_energy_kgce_per_t)} kgce/t<br>"
        f"外属调整：{number(energy.adjustment_kgce_per_t)} kgce/t<br>"
        f"评价能耗：{number(energy.evaluation_energy_kgce_per_t)} kgce/t</p>"
        f"<table cellspacing='10'><tr><th>等级</th><th>修正限额（kgce/t）</th>"
        f"<th>比较结果</th><th>待确定原因</th></tr>{rows}</table><p>{warnings}</p>"
    )


class CokePreviewPage(QWidget):
    def __init__(self, preview=preview_coke):
        super().__init__()
        self.preview = preview
        self.result = None
        self.fields, self.choices = {}, {}
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(28, 24, 28, 24)
        body.setSpacing(16)
        title = QLabel("焦炭能耗计算预览")
        title.setProperty("class", "pageTitle")
        body.addWidget(title)
        body.addWidget(QLabel("GB 21342—2025 · 隔离预览，不生成记录"))

        def section(title):
            group = QGroupBox(title)
            form = QFormLayout(group)
            form.setSpacing(12)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            body.addWidget(group)
            return form

        def field(form, key, label):
            edit = QLineEdit()
            edit.setObjectName("coke_" + key)
            edit.setAccessibleName(label.text() if isinstance(label, QLabel) else label)
            if isinstance(label, QLabel):
                label.setBuddy(edit)
            edit.textChanged.connect(self.invalidate)
            self.fields[key] = edit
            form.addRow(label, edit)
            return edit

        def choice(form, key, label, options):
            combo = WheelSafeComboBox()
            combo.setAccessibleName(label)
            for text, value in options:
                combo.addItem(text, value)
            combo.currentIndexChanged.connect(self.invalidate)
            self.choices[key] = combo
            form.addRow(label, combo)
            return combo

        form = section("评价对象")
        field(form, "object_name", "对象名称")
        field(form, "period", "统计期")
        choice(form, "oven_type", "焦炉类型", [("请选择", None), ("顶装焦炉", "top_charging"), ("捣固焦炉", "stamp_charging")])
        choice(form, "conventional_oven", "是否常规焦炉", [("待确定", None), ("是", True), ("否", False)])
        form = section("能量与产量")
        self.energy_mode = choice(form, "energy_mode", "录入方式", [("已折标五分量总量", "totals"), ("原始能流明细", "flows")])
        self.energy_mode.currentIndexChanged.connect(self.update_energy_mode)
        self.energy_labels = {}
        for key, label in LABELS.items():
            self.energy_labels[key] = QLabel(label + ("（t）" if key == "dry_coke_output_t" else "（kgce）"))
            field(form, key, self.energy_labels[key])
        self.flows_form = CokeFlowsForm()
        self.flows_form.changed.connect(self.invalidate)
        form.addRow(self.flows_form)
        form = section("生产条件")
        fuel = choice(form, "heating_fuel", "加热燃料", [("请选择", None), ("焦炉煤气", "coke_oven_gas"), ("混合煤气", "mixed_gas"), ("其他", "other"), ("待确定", "unknown")])
        self.ratio_label = QLabel("混合煤气使用时间占比（%）")
        self.ratio = field(form, "mixed_gas_percent", self.ratio_label)
        fuel.currentIndexChanged.connect(self.update_conditions)
        field(form, "dry_volatile_pct", "干基挥发分（%）")
        field(form, "total_moisture_pct", "全水分（%）")
        field(form, "oven_age_years", "炉龄（年）")
        choice(form, "quenching_method", "熄焦方式", [("请选择", None), ("干熄焦", "dry"), ("湿熄焦", "wet"), ("干湿并存", "mixed"), ("待确定", "unknown")])
        form = section("外属情况")
        for key, label in (("purification", "煤气净化"), ("wastewater", "废水处理")):
            choice(form, key, label, [("待确定", None), ("不外属，或能耗已计入", False), ("全部外属且能耗未计入", True)])
        self.notice = QLabel("填写五项能量及干全焦产量；无发生量请明确填0。")
        self.notice.setWordWrap(True)
        self.notice.setTextInteractionFlags(self.notice.textInteractionFlags())
        body.addWidget(self.notice)
        self.calculate = QPushButton("计算预览")
        self.calculate.setProperty("role", "primary")
        self.calculate.clicked.connect(self.run_preview)
        body.addWidget(self.calculate)
        self.output = QTextBrowser()
        self.output.setMinimumHeight(310)
        body.addWidget(self.output)
        self.details_toggle = QPushButton("展开计算依据与版本")
        self.details_toggle.setCheckable(True)
        self.details = QTextBrowser()
        self.details.setMinimumHeight(240)
        self.details.hide()
        self.details_toggle.toggled.connect(self.details.setVisible)
        body.addWidget(self.details_toggle)
        body.addWidget(self.details)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.update_conditions()
        self.update_energy_mode()

    def update_energy_mode(self):
        totals = self.energy_mode.currentData() == "totals"
        for key in LABELS:
            if key != "dry_coke_output_t":
                self.fields[key].setVisible(totals)
                self.energy_labels[key].setVisible(totals)
        self.flows_form.setVisible(not totals)

    def update_conditions(self):
        visible = self.choices["heating_fuel"].currentData() == "mixed_gas"
        self.ratio.setVisible(visible)
        self.ratio_label.setVisible(visible)

    def invalidate(self, *_):
        if self.result is not None:
            self.result = None
            self.notice.setText("数据已修改，结果已过期，请重新计算。")
            self.output.clear()
            self.details.clear()

    def collect(self):
        values = {key: edit.text().strip() or None for key, edit in self.fields.items()}
        facts = [self.choices[key].currentData() for key in ("purification", "wastewater")]
        status = (ExternalServicesStatus.BOTH_EXTERNAL_EXCLUDED if all(v is True for v in facts)
                  else ExternalServicesStatus.INCLUDED_OR_NOT_EXTERNAL if all(v is False for v in facts)
                  else ExternalServicesStatus.PARTIAL_OR_UNKNOWN)
        mode = self.energy_mode.currentData()
        flows, zeros = self.flows_form.collect() if mode == "flows" else (None, ())
        energy, self.flow_result = normalize_energy(mode=mode,
            totals={key: values[key] for key in LABELS if key != "dry_coke_output_t"} if mode == "totals" else None,
            flows=flows, zero_components=zeros, dry_coke_output_t=values["dry_coke_output_t"], external_services_status=status)
        parameters = {key: combo.currentData() for key, combo in self.choices.items()
                      if key not in {"purification", "wastewater", "energy_mode"}}
        ratio = None
        if parameters["heating_fuel"] == "mixed_gas":
            percent = _optional_number(values["mixed_gas_percent"], "混合煤气使用时间占比")
            if percent is not None:
                if not 0 <= percent <= 100:
                    raise ValueError("混合煤气使用时间占比须在0至100%之间")
                with localcontext(_declared_context()):
                    ratio = percent / 100
        return CokeAssessmentInput(energy=energy, **parameters, mixed_gas_ratio=ratio,
            **{key: values[key] for key in ("dry_volatile_pct", "total_moisture_pct", "oven_age_years")})

    def run_preview(self):
        self.calculate.setEnabled(False)
        self.result = None
        self.output.clear()
        self.details.clear()
        try:
            self.result = self.preview(self.collect())
            flow_warnings = self.flow_result.warnings if self.flow_result else ()
            self.output.setHtml(result_html(self.result, flow_warnings))
            r = self.result
            flow_details = []
            if self.flow_result:
                for row in self.flow_result.rows:
                    flow = row.flow
                    label = REFERENCES.get(flow.energy_id, ({"saturated_steam":"饱和蒸汽",
                        "superheated_steam":"过热蒸汽", "standard_coal":"已折标能流"}.get(flow.energy_id,"其他能源或工质"),))[0]
                    flow_details.append(f"{LABELS[flow.component]} · {label}：{flow.quantity} {flow.unit} × "
                        f"{row.coefficient} {row.coefficient_unit} = {row.energy_kgce} kgce；{row.coefficient_source}")
            self.details.setPlainText("\n".join([
                r.source_location, f"数值配置：{r.numeric_profile_id}",
                f"计算器版本：{r.calculator_version}", f"规则版本：{r.rule_revision}",
                *[("最终级别：" + GRADE_LABELS[r.grade]) if s.label == "最终级别"
                  else f"{s.label}：{s.expression} = {s.value} {s.unit or ''}" for s in r.calculation_trace],
                *flow_details,
            ]))
            self.notice.setText("预览完成，不生成记录。")
        except ValueError as exc:
            self.notice.setText("请检查输入：" + str(exc))
        finally:
            self.calculate.setEnabled(True)
