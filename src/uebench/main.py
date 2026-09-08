from __future__ import annotations

import sys
import logging
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from .bootstrap import create_context
from .infrastructure.logging import close_logging
from .ui.main_window import create_main_window


def configure_application_font(application: QApplication) -> None:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(candidate))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            application.setFont(QFont(families[0], 10))
            return


def install_bundled_package(context) -> None:
    if not context.application.has_package_service() or context.application.list_all_standards():
        return
    resource_directory = Path(__file__).resolve().parent / "resources"
    packages = sorted(resource_directory.glob("initial-standard-package-*.uebench"))
    if not packages:
        return
    try:
        context.application.install_package(packages[-1])
    except Exception:
        logging.getLogger(__name__).exception("内置初始标准包安装失败")


def main() -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("单位产品能耗对标软件")
    application.setOrganizationName("UEBench")
    bundled_icon = Path(__file__).resolve().parent / "resources" / "uebench.ico"
    if bundled_icon.exists():
        application.setWindowIcon(QIcon(str(bundled_icon)))
    configure_application_font(application)
    resource_key = Path(__file__).resolve().parent / "resources" / "update_public_key.pem"
    context = create_context(public_key_path=resource_key)
    try:
        install_bundled_package(context)
        window = create_main_window(context)
        window.show()
        return application.exec()
    finally:
        context.database.dispose()
        close_logging()

if __name__ == "__main__":
    raise SystemExit(main())
