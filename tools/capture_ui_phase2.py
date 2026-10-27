"""第二阶段隔离预览/截图；不使用用户数据库。默认离屏，--interactive 为原生窗口。"""
import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--revision-evidence", action="store_true", help="额外采集返修结果定位及异常状态证据")
    parser.add_argument("--round2-evidence", action="store_true", help="实际默认尺寸、表格与单选标记返修证据")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/ui/screenshots/phase2")
    args = parser.parse_args()
    if not args.interactive:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6 import __version__ as qt_version
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox
    from uebench.bootstrap import create_context
    from uebench.main import configure_application_font, reconcile_standard_package
    from uebench.domain.models import EvaluationRequest, InputMode, InputValue
    from uebench.ui.main_window import MainWindow
    app = QApplication([])
    configure_application_font(app)
    args.output.mkdir(parents=True, exist_ok=True)
    (ROOT / "work").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ui-phase2-", dir=ROOT / "work") as data:
        context = create_context(Path(data), public_key_path=ROOT / "src/uebench/resources/update_public_key.pem")
        reconcile_standard_package(context)
        standard = context.application.get_published_standard("gb-29446-2019")
        product = next(p for p in standard.products if p.selection_values.get("coal_type") == "炼焦煤")
        request = EvaluationRequest(evaluation_date=datetime.now().date(), standard_id=standard.id, product_id=product.id, input_mode=InputMode.DETAIL,
            inputs={"washing_process": InputValue(value="重介、浮选联合"), "electricity_consumption": InputValue(value="8000000", unit="kW·h"), "raw_coal_input": InputValue(value="1000000", unit="t")},
            notes="核算周期：自定义\n自定义周期：历史第三季度")
        result = context.application.preview_evaluation(request)
        for index in range(225):
            req = request.model_copy(deep=True, update={"organization_name": "最早隔离测试企业" if index == 0 else f"隔离测试企业{index:03}"})
            saved = result.model_copy(deep=True, update={"evaluation_id": f"{index:036}", "evaluated_at": datetime(2026,10,1,tzinfo=timezone.utc)})
            context.evaluations.save(req, saved, standard)
        win = MainWindow(context)
        win.setWindowTitle("能耗限额 UI 第二阶段隔离检查")
        if not args.interactive:
            win.resize(1440,900)
        win.show()
        if args.round2_evidence and args.interactive:
            win.setWindowTitle("能耗限额 PR33 第二轮返修隔离检查")
            win.navigate("standards")
        captures = []
        def settle():
            for _ in range(4):
                app.processEvents()
        def shot(name):
            settle()
            win.grab().save(str(args.output / (name + ".png")))
            captures.append({"file": name + ".png", "width": win.width(), "height": win.height()})
        settle()
        screens = [{"name": s.name(), "logical_dpi": s.logicalDotsPerInch(), "device_pixel_ratio": s.devicePixelRatio(),
                    "geometry": [s.geometry().width(),s.geometry().height()], "available": [s.availableGeometry().width(),s.availableGeometry().height()]} for s in app.screens()]
        environment = {"platform": app.platformName(), "python": platform.python_version(), "pyside6": qt_version,
            "isolated_data": True, "records": 225, "screens": screens, "native_dpi_acceptance": False, "captures": captures}
        environment["source_head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        environment["source_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True).strip())
        environment["scale_overrides"] = {name: os.environ.get(name) for name in ("QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS", "QT_FONT_DPI")}
        if sys.platform == "win32" and args.interactive:
            import ctypes
            from ctypes import wintypes
            get_dpi = ctypes.windll.user32.GetDpiForWindow
            get_dpi.argtypes = [wintypes.HWND]
            get_dpi.restype = ctypes.c_uint
            environment["native_window_dpi"] = get_dpi(int(win.winId()))
            environment["window_logical_size"] = [win.width(), win.height()]
        (args.output / ("native-environment.json" if args.interactive else "capture-environment.json")).write_text(json.dumps(environment, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.interactive:
            app.exec()
        else:
            for name in ("information", "warning", "critical"):
                setattr(QMessageBox, name, lambda *a, **k: QMessageBox.Ok)
            if args.round2_evidence:
                for width, height in ((1256,624),(1180,760),(1440,900),(900,600)):
                    win.resize(width,height)
                    for key in ("standards", "records"):
                        win.navigate(key)
                        shot(f"{key}-{width}")
                long_request = request.model_copy(deep=True, update={"organization_name": "长企业名称换行检查：" + "青舟选煤示例企业" * 6})
                long_result = result.model_copy(deep=True, update={"evaluation_id": "long-name-fixture", "standard_title": "选煤电力消耗限额长名称检查：" + "保存的标准名称" * 6})
                context.evaluations.save(long_request, long_result, standard)
                win.mark_records_dirty()
                win.navigate("records")
                for width, height in ((1256,624),(1180,760)):
                    win.resize(width,height)
                    shot(f"records-long-{width}")
                environment["records"] = context.application.count_evaluations()
                win.resize(1256,624)
                win.navigate("settings")
                shot("settings-1256")
                win.settings_page.advanced_toggle.click()
                shot("settings-advanced-1256")
                win.start_formal_evaluation()
                win.evaluation_scroll.verticalScrollBar().setValue(0)
                for index, name in ((0,"coking"),(1,"thermal"),(0,"coking-return")):
                    win.coal_button_group.buttons()[index].click()
                    shot("radio-" + name + "-1256")
                environment["captures"] = captures
                (args.output / "capture-environment.json").write_text(json.dumps(environment,ensure_ascii=False,indent=2),encoding="utf-8")
                win.close()
                context.database.dispose()
                logging.shutdown()
                return
            win.navigate("records")
            shot("records-1440")
            win._record_page = 12
            win.refresh_records()
            shot("records-last-page-1440")
            win.view_record(f"{0:036}")
            shot("record-result-1440")
            win.record_detail_page.tabs.setCurrentIndex(1)
            shot("record-inputs-1440")
            win.navigate("settings")
            shot("settings-1440")
            win.settings_page.advanced_toggle.click()
            shot("settings-advanced-1440")
            win.resize(900,600)
            win.navigate("records")
            shot("records-900")
            win.view_record(f"{0:036}")
            shot("record-900")
            win.navigate("settings")
            shot("settings-900")
            win.navigate("home")
            shot("home-900")
            if args.revision_evidence:
                from uebench.domain.models import Grade
                for size in ((1440, 900), (900, 600)):
                    win.resize(*size)
                    win.start_formal_evaluation()
                    win.gb29446_coal_type.setCurrentText("炼焦煤")
                    win.gb29446_process.setCurrentIndex(win.gb29446_process.findData("重介、浮选联合"))
                    win.gb29446_electricity.setText("8000000")
                    win.gb29446_raw_coal.setText("1000000")
                    win.calculate_button.click()
                    shot(f"success-result-{size[0]}")
                for grade, name in ((Grade.INCOMPLETE, "incomplete"), (Grade.NOT_APPLICABLE, "not-applicable")):
                    saved = result.model_copy(deep=True, update={"evaluation_id": name})
                    saved.results[0].grade = grade
                    saved.results[0].actual_value = None
                    special_request = request.model_copy(deep=True, update={"organization_name": "A<b>x</b>B & 保存的企业名称"})
                    context.evaluations.save(special_request, saved, standard)
                    win.resize(1440, 900)
                    win.navigate("records")
                    win.record_status_filter.setCurrentText("不完整" if grade is Grade.INCOMPLETE else "不适用")
                    shot(name + "-list-1440")
                    win.view_record(name)
                    shot(name + "-detail-1440")
                environment["records"] = context.application.count_evaluations()
            environment["captures"] = captures
            (args.output / "capture-environment.json").write_text(json.dumps(environment,ensure_ascii=False,indent=2),encoding="utf-8")
        win.close()
        context.database.dispose()
        logging.shutdown()

if __name__ == "__main__":
    main()
