"""仅开发者隔离验收：不代表默认签名包正式支持，不进入产品入口。"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def sample(scenario):
    from uebench.domain.models import EvaluationRequest, InputValue
    data = json.loads((ROOT / "tests/golden/gb16780_candidates_v1.json").read_text(encoding="utf-8"))["cases"][0]["inputs"]
    request = EvaluationRequest.model_validate(data)
    request.organization_name = "合成水泥验收企业（非真实生产数据）"
    request.notes = "核算周期：自定义\n自定义周期：2026年10月（合成）"
    if scenario == "missing-fuel":
        request.cement_lines[0].fuels[0].mass_kg = None
    elif scenario == "grinding":
        line = request.cement_lines[0]
        line.line_name = "全部外购熟料粉磨线"
        line.production_mode = "purchased_clinker_grinding"
        line.fuels = []
        line.inputs = {"cement.production_t": InputValue(value="1000", unit="t"),
                       "cement.preparation_electricity_kwh": InputValue(value="29000", unit="kWh")}
    elif scenario == "multi":
        request.cement_lines[0].line_name = "第一条生产线——合成超长中文名称用于核对分页换行与完整显示甲乙丙丁戊己庚辛壬癸"
        second = request.cement_lines[0].model_copy(deep=True, update={"line_id": "kiln-2", "line_name": "第二条生产线——合成超长中文名称用于核对分线独立等级和保存时输入完整显示"})
        second.production_mode = "integrated"
        request.cement_lines.append(second)
    return request


def isolated_context(scenario):
    from uebench.application import evaluation_support
    from uebench.bootstrap import create_context
    from uebench.domain.models import StandardDefinition
    # 明确依赖注入，仅在此独立进程；生产注册表及readiness没有新增绕过入口。
    evaluation_support.SUPPORTED_EVALUATION_STANDARD_IDS = frozenset({"gb-29446-2019", "gb-16780-2021"})
    context = create_context(ROOT / "work/cement-acceptance" / scenario,
                             enforce_standard_library_readiness=False)
    for standard_id in ("gb-29446-2019", "gb-16780-2021"):
        context.standards.install(StandardDefinition.model_validate_json(
            (ROOT / "data/definitions" / f"{standard_id}.json").read_text(encoding="utf-8")))
    return context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("complete", "missing-fuel", "grinding", "multi"), default="complete")
    parser.add_argument("--prepare-evidence", action="store_true", help="仅经实际应用/Writer生成单线及长名称多线DOCX，不启动桌面")
    args = parser.parse_args()
    if args.prepare_evidence:
        outputs = []
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
        for scenario in ("complete", "multi"):
            context = isolated_context("evidence-" + scenario)
            try:
                request = sample(scenario)
                result = context.application.evaluate(request)
                path = ROOT / "work/cement-acceptance/evidence" / f"cement-{scenario}.docx"
                context.application.export_word_report(result.evaluation_id, path)
                outputs.append({"scenario": scenario, "record_id": result.evaluation_id, "docx": str(path),
                                "source_commit": head, "source_dirty": dirty,
                                "docx_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                "rule_snapshot_sha256": result.rule_snapshot_sha256})
            finally:
                context.database.dispose()
        output = ROOT / "work/cement-acceptance/evidence/outputs.json"
        output.write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
        print(output)
        return 0
    from PySide6.QtWidgets import QApplication, QLabel
    from uebench.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    context = isolated_context(args.scenario)
    window = MainWindow(context)
    window.setWindowTitle("水泥源码隔离验收（签名包未完成，非正式支持）")
    index = window.eval_standard.findData("gb-16780-2021")
    window.eval_standard.setCurrentIndex(index)
    window.cement_form.load(sample(args.scenario))
    banner = QLabel("隔离验收夹具：仅测试尚未开放的源码路径；当前默认正式范围仍仅选煤，水泥配套签名包及候选待验。")
    banner.setWordWrap(True)
    banner.setStyleSheet("color:#956420; font-weight:bold;")
    window.page_widgets["evaluation"].layout().insertWidget(0, banner)
    window.eval_support_label.setText("源码隔离受测路径（未开放）")
    window.navigate("evaluation")
    window.show()
    try:
        return app.exec()
    finally:
        context.database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
