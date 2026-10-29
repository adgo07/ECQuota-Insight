"""仅翻译 Qt 标准按钮文字，保留 QMessageBox 的角色、默认键和返回值。"""
from __future__ import annotations

from PySide6.QtCore import QTranslator
from PySide6.QtWidgets import QApplication


class _ChineseButtonTranslator(QTranslator):
    def translate(self, context, source_text, disambiguation=None, n=-1):
        labels = {
            "OK": "确定", "&OK": "确定(&O)",
            "&Yes": "确认(&Y)", "Yes": "确认",
            "&No": "取消(&N)", "No": "取消",
            "Cancel": "取消", "&Cancel": "取消(&C)",
        }
        if context in {"QPlatformTheme", "QMessageBox"} and source_text in labels:
            return labels[source_text]
        return super().translate(context, source_text, disambiguation, n)


def install_chinese_message_box_buttons() -> None:
    application = QApplication.instance()
    if application is not None and not hasattr(application, "_uebench_button_translator"):
        translator = _ChineseButtonTranslator(application)
        application.installTranslator(translator)
        # 译器与 QApplication 同寿命，不因窗口关闭而丢失。
        application._uebench_button_translator = translator
