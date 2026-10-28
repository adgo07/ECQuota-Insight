from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QFrame,
    QSizePolicy,
)


class SettingsPage(QWidget):
    """Small user-facing settings surface; package lifecycle stays automatic."""

    create_backup_requested = Signal()
    restore_backup_requested = Signal()
    open_data_directory_requested = Signal()
    view_diagnostics_requested = Signal()
    copy_diagnostics_requested = Signal()

    def __init__(
        self,
        *,
        software_version: str,
        standard_library_version: str,
        data_directory: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title = QLabel("设置")
        title.setProperty("class", "pageTitle")
        root.addWidget(title)
        outer = root
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 8, 0)
        root.setSpacing(20)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        app_group, app_layout = self._section("应用信息")
        app_form = QFormLayout()
        app_layout.addLayout(app_form)
        self.software_version_value = QLabel(software_version)
        self.software_version_value.setObjectName("settingsSoftwareVersion")
        self.standard_library_version_value = QLabel(standard_library_version)
        self.standard_library_version_value.setObjectName("settingsStandardLibraryVersion")
        self.data_directory_value = QLabel(data_directory)
        self.data_directory_value.setObjectName("settingsDataDirectory")
        self.data_directory_value.setWordWrap(True)
        self.data_directory_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.data_directory_value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        app_form.addRow("软件版本", self.software_version_value)
        app_form.addRow("标准库版本", self.standard_library_version_value)
        app_form.addRow("数据存储位置", self.data_directory_value)
        app_form.addRow(QLabel("标准库随软件版本一起更新，无需单独安装。"))
        root.addWidget(app_group)

        backup_group, backup_layout = self._section("数据与备份")
        backup_buttons = QHBoxLayout()
        self.create_backup_button = QPushButton("创建备份")
        self.create_backup_button.setObjectName("settingsCreateBackup")
        self.create_backup_button.clicked.connect(self.create_backup_requested)
        self.restore_backup_button = QPushButton("恢复备份")
        self.restore_backup_button.setObjectName("settingsRestoreBackup")
        self.restore_backup_button.clicked.connect(self.restore_backup_requested)
        backup_buttons.addWidget(self.create_backup_button)
        backup_buttons.addWidget(self.restore_backup_button)
        backup_buttons.addStretch()
        backup_layout.addLayout(backup_buttons)
        backup_hint = QLabel("恢复会替换当前数据，软件会先创建恢复前保护。")
        backup_hint.setWordWrap(True)
        backup_layout.addWidget(backup_hint)
        root.addWidget(backup_group)

        self.advanced_toggle = QToolButton()
        self.advanced_toggle.setObjectName("settingsAdvancedToggle")
        self.advanced_toggle.setText("高级")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setChecked(False)
        self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.advanced_toggle.setArrowType(Qt.ArrowType.RightArrow)
        root.addWidget(self.advanced_toggle, 0, Qt.AlignmentFlag.AlignLeft)

        self.advanced_content, advanced_layout = self._section("诊断与数据位置")
        self.advanced_content.setObjectName("settingsAdvancedContent")
        self.advanced_content.setVisible(False)
        self.open_data_directory_button = QPushButton("打开数据目录")
        self.open_data_directory_button.setObjectName("settingsOpenDataDirectory")
        self.open_data_directory_button.clicked.connect(self.open_data_directory_requested)
        self.view_diagnostics_button = QPushButton("查看诊断信息")
        self.view_diagnostics_button.setObjectName("settingsViewDiagnostics")
        self.view_diagnostics_button.clicked.connect(self.view_diagnostics_requested)
        self.copy_diagnostics_button = QPushButton("复制诊断信息")
        self.copy_diagnostics_button.setObjectName("settingsCopyDiagnostics")
        self.copy_diagnostics_button.clicked.connect(self.copy_diagnostics_requested)
        for button in (
            self.open_data_directory_button,
            self.view_diagnostics_button,
            self.copy_diagnostics_button,
        ):
            advanced_layout.addWidget(button)
        root.addWidget(self.advanced_content)
        self.advanced_toggle.toggled.connect(self._set_advanced_visible)
        root.addStretch(1)


    @staticmethod
    def _section(title):
        card = QFrame()
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        heading = QLabel(title)
        heading.setProperty("class", "sectionTitle")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        return card, layout

    def set_standard_library_version(self, version: str) -> None:
        self.standard_library_version_value.setText(version)

    def _set_advanced_visible(self, expanded: bool) -> None:
        self.advanced_content.setVisible(expanded)
        self.advanced_toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
