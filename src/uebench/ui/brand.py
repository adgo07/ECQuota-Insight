"""从原始透明 PNG 按当前屏幕 DPR 绘制品牌。"""
from pathlib import Path
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel


class BrandLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._source = QPixmap(str(Path(__file__).resolve().parents[1] / "resources/branding/qingzhou_logo.png"))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAccessibleName("青舟节能")
        self.setFixedSize(180, round(180 * self._source.height() / self._source.width()) if not self._source.isNull() else 45)
        self.refresh_pixmap()

    def refresh_pixmap(self):
        if self._source.isNull():
            self.setText("青舟节能")
            return
        self.setPixmap(self.pixmap_for_dpr(self.devicePixelRatioF()))

    def pixmap_for_dpr(self, dpr):
        pixmap = self._source.scaledToWidth(round(180 * dpr), Qt.TransformationMode.SmoothTransformation)
        pixmap.setDevicePixelRatio(dpr)
        return pixmap

    def event(self, event):
        result = super().event(event)
        if event.type() in (QEvent.Type.Show, QEvent.Type.Resize, QEvent.Type.DevicePixelRatioChange):
            if hasattr(self, "_source"):
                self.refresh_pixmap()
        return result
