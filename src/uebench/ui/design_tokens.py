"""青舟本地展示参数；不承载业务规则或跨仓运行时依赖。"""

APP_STYLE = """
QMainWindow, QWidget { background: #F5F8FC; color: #213A4F; font-family: 'Microsoft YaHei UI', 'Microsoft YaHei'; font-size: 14px; }
QLabel { background: transparent; }
QFrame[class="card"] { background: white; border: 1px solid #DAE7F1; border-radius: 10px; }
QWidget#sidebar { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #E6F2FC,stop:0.5 #EDF6FD,stop:1 #E6F2FB); }
QListWidget#navigation { background: transparent; border: none; padding: 8px; }
QListWidget#navigation::item { height: 46px; padding-left: 12px; margin: 3px 0; border-radius: 9px; }
QListWidget#navigation::item:selected { background: #D6EBF9; color: #116FAE; border-left: 3px solid #298CCB; }
QListWidget#navigation::item:disabled { color: #698198; }
QPushButton { background: white; color: #197CC2; border: 1px solid #DAE7F1; border-radius: 6px; padding: 9px 16px; min-height: 20px; }
QPushButton:hover { background: #EDF6FD; border-color: #197CC2; }
QPushButton:pressed, QPushButton:checked { background: #D6EBF9; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus { border: 2px solid #197CC2; }
QPushButton[role="primary"] { background: #197CC2; color: white; border-color: #197CC2; }
QPushButton[role="primary"]:hover { background: #116FAE; }
QPushButton:disabled { color: #698198; background: #F0F4F8; border-color: #DAE7F1; }
QPushButton[role="task"] { text-align: left; padding: 22px; font-size: 16px; border-radius: 14px; }
QPushButton#standardTask { background: #183F64; color: white; text-align: left; padding: 22px; border-radius: 14px; font-size: 18px; }
QLineEdit, QComboBox, QDateEdit, QSpinBox { background: white; border: 1px solid #DAE7F1; border-radius: 6px; padding: 8px; min-height: 22px; }
QLineEdit:read-only { background: #F7FAFD; }
QTextEdit, QTableWidget { background: white; border: 1px solid #DAE7F1; border-radius: 6px; gridline-color: #E8F0F6; }
QTableWidget::item { padding: 8px; }
QTableWidget::item:selected { background: #D6EBF9; color: #18364F; }
QHeaderView::section { background: #F7FAFD; color: #698198; padding: 10px; border: none; border-bottom: 1px solid #DAE7F1; font-size: 13px; }
QLabel[class="pageTitle"] { font-size: 24px; font-weight: 600; color: #18364F; }
QLabel[class="sectionTitle"] { font-size: 16px; font-weight: 600; color: #18364F; }
QLabel[class="metric"] { font-size: 26px; font-weight: 600; color: #18364F; }
QLabel[class="muted"] { color: #698198; font-size: 13px; }
QScrollArea { border: none; }
"""
