"""第一阶段真实 Qt 样板；临时隔离数据，默认离屏，不读用户数据库。

从仓库根运行：python tools/capture_ui_phase1.py
交互检查：python tools/capture_ui_phase1.py --interactive
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import platform
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interactive", action="store_true", help="在临时数据上打开原生窗口，关闭后删除临时数据")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/ui/screenshots/phase1")
    args = parser.parse_args()
    if not args.interactive:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6 import __version__ as qt_version
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox
    from uebench.bootstrap import create_context
    from uebench.main import configure_application_font, reconcile_standard_package
    from uebench.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    configure_application_font(app)
    args.output.mkdir(parents=True, exist_ok=True)
    local_work = ROOT / "work"
    local_work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ui-phase1-", dir=local_work) as temporary:
        context = create_context(Path(temporary), public_key_path=ROOT / "src/uebench/resources/update_public_key.pem")
        reconcile_standard_package(context)
        window = MainWindow(context)
        window.show()
        if args.interactive:
            app.exec()
            window.close()
            context.database.dispose()
            logging.shutdown()
            return
        for name in ("warning", "information", "critical"):
            setattr(QMessageBox, name, lambda *a, **k: QMessageBox.Ok)
        captures = []

        def settle():
            for _ in range(3):
                app.processEvents()

        def shot(name):
            settle()
            path = (args.output / (name + ".png")).resolve()
            if not window.grab().save(str(path)):
                raise RuntimeError(f"截图写入失败：{path}")
            captures.append({"file": path.name, "width": window.width(), "height": window.height()})
            print(path)

        shot("home-1440")
        window.navigate("standards")
        shot("standards-1440")
        for sid, name in (("gb-29446-2019", "coal"), ("gb-16780-2021", "cement"), ("gb-21343-2023", "other")):
            row = next(r for r in range(window.standard_table.rowCount()) if window.standard_table.item(r, 0).data(Qt.UserRole) == sid)
            window.standard_table.selectRow(row)
            window.show_standard_detail()
            shot("detail-" + name + "-1440")
        window.start_formal_evaluation()
        shot("form-1440")
        window.gb29446_coal_type.setCurrentIndex(window.gb29446_coal_type.findText("炼焦煤"))
        window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("重介、浮选联合"))
        window.gb29446_electricity.setText("8000000")
        window.gb29446_raw_coal.setText("1000000")
        window.calculate_button.click()
        assert window.last_result_id and context.application.count_evaluations() == 1
        assert window.gb29446_result_grade.text() == "2级"
        settle()
        window.evaluation_scroll.verticalScrollBar().setValue(window.evaluation_scroll.verticalScrollBar().maximum())
        shot("result-1440")
        window.resize(1180, 760)
        settle()
        window.evaluation_scroll.verticalScrollBar().setValue(0)
        shot("form-1180")
        window.evaluation_scroll.verticalScrollBar().setValue(window.evaluation_scroll.verticalScrollBar().maximum())
        shot("result-1180")
        window.navigate("home")
        shot("home-record-1180")
        manifest = {
            "platform": app.platformName(), "python": platform.python_version(), "pyside6": qt_version,
            "isolated_data": True, "data_lifetime": "临时数据，关闭后删除",
            "native_dpi_acceptance": False, "dimensions": "Qt 窗口逻辑像素；离屏 devicePixelRatio=" + str(window.devicePixelRatio()),
            "input": {"electricity": "8000000", "raw_coal": "1000000", "process": "重介、浮选联合"},
            "captures": captures,
        }
        (args.output / "capture-environment.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        window.close()
        context.database.dispose()
        logging.shutdown()


if __name__ == "__main__":
    main()
