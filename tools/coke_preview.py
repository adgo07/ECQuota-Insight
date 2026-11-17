"""以新建临时数据目录启动家族壳内的焦炭预览，不接触用户库。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main():
    if "--self-check" in sys.argv:
        import json
        from uebench.application.gb21342 import preview_coke
        from uebench.domain.gb21342 import CokeAssessmentInput, CokeEnergyInput
        from uebench.domain.coke_flows import CokeFlow, aggregate_flows
        request = CokeAssessmentInput(CokeEnergyInput("111","0","0","0","0","1","included_or_not_external"),
            oven_type="top_charging",heating_fuel="coke_oven_gas",dry_volatile_pct="23",total_moisture_pct="10",
            oven_age_years="20",quenching_method="mixed",conventional_oven=True)
        result = preview_coke(request)
        flow = aggregate_flows([CokeFlow("one","processing_energy_kgce","electricity","1000","kWh")])
        assert result.grade.value == "LEVEL_1" and result.levels[2].threshold is None
        assert str(flow.rows[0].energy_kgce) == "122.9000"
        print(json.dumps({"kind":"UNPUBLISHED_PREVIEW_ONLY","grade":result.grade.value,
                          "lower_level_unknown":True,"flow_kgce":str(flow.rows[0].energy_kgce),"records_written":0}))
        return 0
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
