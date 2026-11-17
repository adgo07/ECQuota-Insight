"""以新建临时数据目录启动家族壳内的焦炭预览，不接触用户库。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main():
    from PySide6.QtWidgets import QApplication
    from uebench.bootstrap import create_context
    from uebench.main import configure_application_font
    from uebench.ui.main_window import MainWindow
    from uebench.ui.coke_preview import CokePreviewPage

    app = QApplication(sys.argv)
    configure_application_font(app)
    with tempfile.TemporaryDirectory(prefix="ecquota-coke-preview-") as directory:
        context = create_context(Path(directory), enforce_standard_library_readiness=False)
        window = MainWindow(context)
        page = CokePreviewPage(context.application.preview_coke)
        window.pages.addWidget(page)
        window.pages.setCurrentWidget(page)
        window.sidebar.show()
        window.setWindowTitle("焦炭隔离开发预览 · 不生成记录")
        window.show()
        code = app.exec()
        context.database.dispose()
        return code


if __name__ == "__main__":
    raise SystemExit(main())
