"""焦炭主应用表单；沿用预览采集与展示，不承载业务算术。"""
from datetime import date
from types import SimpleNamespace
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QScrollArea
from uebench.domain.models import EvaluationRequest, InputMode
from uebench.application.coke_records import input_payload, PRODUCTS, STANDARD_ID
from .coke_preview import CokePreviewPage


def _saved_namespace(value):
    if isinstance(value, dict):
        return SimpleNamespace(**{k:_saved_namespace(v) for k,v in value.items()})
    if isinstance(value, list):
        return [_saved_namespace(v) for v in value]
    return value


class CokeForm(CokePreviewPage):
    changed = Signal()

    def __init__(self):
        super().__init__(embedded=True)
        self.title.setText("焦炭能耗对标")
        self.calculate.hide()  # 主应用固定动作区统一发起计算。
        self.scope_notice.setText("最高等级完整时自动生成一条对标记录；待确定或不适用时仅保留预览。")
        self.notice.setText("填写数据后计算；最高等级可确定时自动生成记录。")
        self.view_record = QPushButton("查看对标记录")
        self.export_word = QPushButton("导出报告（Word）")
        actions = QHBoxLayout()
        actions.addStretch()
        for button in (self.view_record, self.export_word):
            button.setEnabled(False)
            actions.addWidget(button)
        self.layout().addLayout(actions)

    def invalidate(self, *_):
        super().invalidate()
        self.changed.emit()

    def collect_request(self, selection_mode):
        name = self.fields["object_name"].text().strip()
        period = self.fields["period"].text().strip()
        if not name:
            self.fields["object_name"].setFocus()
            raise ValueError("请填写对象名称")
        if not period:
            self.fields["period"].setFocus()
            raise ValueError("请填写统计期")
        assessment = self.collect()
        product = PRODUCTS.get(assessment.oven_type)
        if product is None:
            self.choices["oven_type"].setFocus()
            raise ValueError("请选择焦炉类型")
        return EvaluationRequest(evaluation_date=date.today(), standard_id=STANDARD_ID,
            product_id=product, selection_mode=selection_mode, input_mode=InputMode.DETAIL,
            inputs={}, organization_name=name, notes=period,
            coke_payload=input_payload(assessment, flow_result=self.flow_result))

    def display_saved_result(self, result):
        saved = _saved_namespace(result.coke_payload["assessment"])
        saved.numeric_profile_id = result.numeric_profile_id
        saved.numeric_contract_version = result.numeric_contract_version
        self.show_result(saved)

    def locate_error(self, message):
        from uebench.domain.gb21342 import LABELS
        labels = {**LABELS, "dry_volatile_pct":"干基挥发分", "total_moisture_pct":"全水分",
                  "oven_age_years":"炉龄", "mixed_gas_percent":"混合煤气使用时间占比",
                  "object_name":"对象名称", "period":"统计期"}
        target = next((self.fields[key] for key,label in labels.items() if label in message), None)
        if target is not None:
            target.setFocus()
            for scroll in self.findChildren(QScrollArea):
                scroll.ensureWidgetVisible(target)
        return target
