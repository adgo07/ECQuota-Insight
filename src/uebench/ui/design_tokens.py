"""青舟本地展示参数；不承载业务规则或跨仓运行时依赖。"""

APP_STYLE = """
QMainWindow, QWidget { background: #F5F8FC; color: #213A4F; font-family: 'Microsoft YaHei UI', 'Microsoft YaHei'; font-size: 14px; }
QLabel { background: transparent; }
QFrame[class="card"] { background: white; border: 1px solid #DAE7F1; border-radius: 10px; }
QWidget#sidebar { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #E6F2FC,stop:0.5 #EDF6FD,stop:1 #E6F2FB); }
QListWidget#navigation { background: transparent; border: none; padding: 8px; }
QListWidget#navigation::item { height: 36px; padding-left: 12px; margin: 3px 0; border: 2px solid transparent; border-radius: 9px; font-size: 13px; font-weight: 600; }
QListWidget#navigation::item:hover { background: #EDF6FD; }
QListWidget#navigation::item:selected { background: #D6EBF9; color: #116FAE; border-left: 3px solid #298CCB; }
QListWidget#navigation::item:focus { border: 2px solid #197CC2; }
QListWidget#navigation::item:disabled { color: #698198; }
QPushButton#sidebarSettings { min-height: 26px; max-height: 26px; font-size: 13px; font-weight: 600; background: transparent; border-color: transparent; text-align: left; padding-left: 20px; border-radius: 9px; }
QPushButton#sidebarSettings:hover { background: #EDF6FD; }
QPushButton#sidebarSettings:pressed { background: #D6EBF9; }
QPushButton#sidebarSettings:focus { border-color: #197CC2; }
QPushButton, QToolButton { background: white; color: #116FAE; border: 2px solid #DAE7F1; border-radius: 6px; padding: 8px 14px; min-height: 20px; max-height: 20px; }
QPushButton:hover, QToolButton:hover { background: #EDF6FD; border-color: #197CC2; }
QPushButton:pressed, QToolButton:pressed, QToolButton:checked { background: #D6EBF9; }
QPushButton:focus, QToolButton:focus { border-color: #197CC2; }
QPushButton[role="secondary"] { background: white; color: #116FAE; border-color: #116FAE; }
QPushButton[role="secondary"]:hover { background: #EDF6FD; }
QPushButton[role="secondary"]:pressed { background: #D6EBF9; }
QPushButton[role="light"] { background: transparent; border-color: transparent; }
QPushButton[role="light"]:hover { background: #EDF6FD; }
QPushButton[role="light"]:pressed { background: #D6EBF9; }
QPushButton[role="danger"] { color: #B9484A; border-color: #B9484A; }
QPushButton[role="danger"]:hover { background: #FFF1F1; }
QPushButton[role="danger"]:pressed { background: #F6DDDE; }
QPushButton[role="primary"] { background: #116FAE; color: white; border-color: #116FAE; }
QPushButton[role="primary"]:hover { background: #0D6097; border-color: #0D6097; }
QPushButton[role="primary"]:pressed { background: #0A507F; border-color: #0A507F; }
QPushButton[role="primary"]:focus { border-color: #18364F; }
QPushButton[role="secondary"]:focus, QPushButton[role="light"]:focus, QPushButton[role="danger"]:focus { border-color: #197CC2; }
QPushButton:disabled, QToolButton:disabled, QPushButton[role="primary"]:disabled, QPushButton[role="secondary"]:disabled, QPushButton[role="light"]:disabled, QPushButton[role="danger"]:disabled { color: #698198; background: #F0F4F8; border-color: #DAE7F1; }
QPushButton[role="task"] { padding: 0; min-height: 172px; max-height: 9999px; border-radius: 14px; }
QPushButton[role="task"] QLabel[class="taskTitle"] { font-size: 18px; font-weight: 600; color: #18364F; }
QPushButton[role="task"] QLabel[class="taskDescription"] { font-size: 13px; color: #526A7D; }
QPushButton[role="task"] QLabel:disabled { color: #698198; }
QPushButton#standardTask { background: #183F64; color: white; padding: 0; border-radius: 14px; }
QPushButton#standardTask:hover { background: #214E76; }
QPushButton#standardTask:pressed { background: #123450; }
QPushButton#standardTask:focus { border-color: #197CC2; }
QPushButton#standardTask QLabel[class="taskTitle"] { color: white; }
QPushButton#standardTask QLabel[class="taskDescription"] { color: #C9E0F2; }
QLineEdit, QComboBox, QDateEdit, QSpinBox { background: white; border: 2px solid #DAE7F1; border-radius: 6px; padding: 8px 10px; min-height: 20px; max-height: 20px; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus { border-color: #197CC2; }
QLineEdit:read-only { background: #F7FAFD; }
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled, QSpinBox:disabled { background: #F0F4F8; color: #698198; }
QTextEdit, QTableWidget { background: white; border: 1px solid #DAE7F1; border-radius: 6px; gridline-color: #E8F0F6; }
QTextEdit:focus { border-color: #197CC2; }
QTableWidget::item { padding: 8px; }
QTableWidget::item:selected { background: #D6EBF9; color: #18364F; }
QHeaderView::section { background: #F7FAFD; color: #526A7D; padding: 10px; border: none; border-bottom: 1px solid #DAE7F1; font-size: 13px; font-weight: 600; }
QTabWidget::pane { border: 1px solid #DAE7F1; background: white; }
QTabBar::tab { background: transparent; color: #526A7D; font-size: 13px; font-weight: 600; min-height: 16px; max-height: 16px; padding: 8px 16px; border: 2px solid transparent; }
QTabBar::tab:selected { color: #116FAE; border-bottom-color: #197CC2; }
QTabBar::tab:hover { background: #EDF6FD; }
QTabBar::tab:focus { border-color: #197CC2; }
QScrollBar:vertical { width: 10px; background: #F7FAFD; margin: 0; }
QScrollBar:horizontal { height: 10px; background: #F7FAFD; margin: 0; }
QScrollBar::handle { background: #9AB8CD; border-radius: 5px; min-height: 24px; min-width: 24px; }
QScrollBar::handle:hover { background: #526A7D; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QLabel[class="pageTitle"] { font-size: 24px; font-weight: 600; color: #18364F; }
QLabel[class="sectionTitle"] { font-size: 16px; font-weight: 600; color: #18364F; }
QLabel[class="metric"] { font-size: 26px; font-weight: 600; color: #18364F; }
QLabel[class="muted"] { color: #526A7D; font-size: 13px; }
QScrollArea { border: none; }
"""


# 显式矢量指示器避免 Windows 主题与全局背景叠加后选中圆点消失。
from pathlib import Path
_radio_icons = (Path(__file__).resolve().parents[1] / "resources" / "icons").as_posix()
APP_STYLE += """
QComboBox { padding-right: 36px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 28px; border: none; background: transparent; }
QComboBox::down-arrow { image: url("RADIO_ROOT/chevron-down.svg"); width: 18px; height: 18px; }
QComboBox::down-arrow:disabled { image: url("RADIO_ROOT/chevron-down-disabled.svg"); }
QRadioButton { background: transparent; spacing: 8px; padding: 4px; border: 1px solid transparent; border-radius: 4px; }
QRadioButton:focus { border: 1px solid #197CC2; }
QRadioButton:disabled { color: #698198; }
QRadioButton::indicator { width: 20px; height: 20px; }
QRadioButton::indicator:unchecked { image: url("RADIO_ROOT/radio-off.svg"); }
QRadioButton::indicator:checked { image: url("RADIO_ROOT/radio-on.svg"); }
QRadioButton::indicator:unchecked:disabled { image: url("RADIO_ROOT/radio-off-disabled.svg"); }
QRadioButton::indicator:checked:disabled { image: url("RADIO_ROOT/radio-on-disabled.svg"); }
""".replace("RADIO_ROOT", _radio_icons)
