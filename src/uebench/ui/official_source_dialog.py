from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QApplication


class OfficialSourceDialog(QDialog):
    """区分系统打开请求与网页实际呈现，始终保留官方地址备用。"""
    def __init__(self, url, requested, parent):
        super().__init__(parent)
        self.setWindowTitle("官方标准页面")
        self.resize(620, 230)
        layout = QVBoxLayout(self)
        self.notice = QLabel("已向系统请求打开官方页面，软件无法确认浏览器是否已显示网页。若没有出现页面，请复制官方地址在浏览器中打开。" if requested else "未能向系统提交打开请求，请检查系统默认浏览器，或复制官方地址手动打开。")
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.address = QLineEdit(url)
        self.address.setReadOnly(True)
        layout.addWidget(self.address)
        self.copy_button = QPushButton("复制官方地址")
        self.copy_button.clicked.connect(lambda: QApplication.clipboard().setText(url))
        layout.addWidget(self.copy_button)
        close = QPushButton("关闭")
        close.clicked.connect(self.close)
        layout.addWidget(close)
