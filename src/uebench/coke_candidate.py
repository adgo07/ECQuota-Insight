"""焦炭完整主应用开发入口：真实readiness、内存候选、可重开的TEMP隔离库。"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile

MARKER = ".uebench-coke-development.json"
STANDARD_ID = "gb-21342-2025"


def prepare_isolated_root(root):
    root = Path(root).absolute()
    for path in [root, *root.parents]:
        if path.exists() and (path.is_symlink() or getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400):
            raise ValueError("开发目录不能包含链接或重解析点")
    resolved = root.resolve()
    temporary = Path(tempfile.gettempdir()).resolve()
    if resolved == temporary or not resolved.is_relative_to(temporary):
        raise ValueError("焦炭开发数据必须位于TEMP内的独立子目录")
    protected = [Path(os.environ.get("LOCALAPPDATA", Path.home()/"AppData/Local"))/"UEBench"]
    if os.environ.get("UEBENCH_DATA_DIR"):
        protected.append(Path(os.environ["UEBENCH_DATA_DIR"]))
    if any(resolved.is_relative_to(p.resolve()) or p.resolve().is_relative_to(resolved) for p in protected):
        raise ValueError("开发目录不能访问正式用户数据")
    expected = {"schema":"ecq.coke-development.v1", "purpose":"开发验收，非正式发布", "root":str(resolved)}
    marker = root/MARKER
    if root.exists() and any(root.iterdir()):
        if not marker.is_file() or json.loads(marker.read_text(encoding="utf-8")) != expected:
            raise ValueError("仅允许新空目录或本焦炭开发入口已标记目录")
        for path in root.rglob("*"):
            if path.is_symlink() or getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
                raise ValueError("开发目录包含链接或重解析点")
    root.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(expected,ensure_ascii=False),encoding="utf-8")
    return root


@contextmanager
def isolated_coke_context(root):
    from .application.evaluation_support import development_evaluation_scope
    from .application.coke_records import candidate_snapshot, is_adopted_snapshot
    from .bootstrap import create_context
    from .main import reconcile_standard_package
    from .infrastructure.logging import close_logging
    root = prepare_isolated_root(root)
    key = Path(__file__).resolve().parent/"resources/update_public_key.pem"
    with development_evaluation_scope({STANDARD_ID}):
        context = create_context(root, public_key_path=key, enforce_standard_library_readiness=True)
        try:
            reconcile_standard_package(context)
            context.package_reconciliation.require_formal_evaluation_ready()
            base = next((item for item in context.standards.list_by_id(STANDARD_ID) if item.rule_revision == 1), None)
            if base is None:
                raise ValueError("配套标准包缺少焦炭定义")
            snapshot = candidate_snapshot(base)
            if not is_adopted_snapshot(snapshot):
                raise ValueError("焦炭内存候选身份无效")
            if context.standards.get_published(STANDARD_ID) != snapshot:
                context.standards.install(snapshot)
            loaded = context.standards.get_published(STANDARD_ID)
            if loaded != snapshot:
                raise ValueError("焦炭内存候选安装身份不一致")
            context.package_reconciliation.require_formal_evaluation_ready()
            yield context
        finally:
            context.database.dispose()
            close_logging()


def _record_hashes(context, record_id):
    from .infrastructure.database import EvaluationRow
    with context.database.session() as session:
        row = session.get(EvaluationRow, record_id)
        return [hashlib.sha256(s.encode()).hexdigest() for s in (row.request_json,row.result_json,row.rule_snapshot_json)]


def _saved_counts(context):
    from sqlalchemy import func, select
    from .infrastructure.database import AuditRow
    with context.database.session() as session:
        audit_count = session.scalar(select(func.count()).select_from(AuditRow))
    return {"records":context.evaluations.count(), "audit_rows":audit_count}


def _smoke(root):
    from PySide6.QtWidgets import QApplication
    from .ui.main_window import MainWindow
    app = QApplication.instance() or QApplication(["coke-self-check", "-platform", "offscreen"])
    with isolated_coke_context(root) as context:
        window = MainWindow(context)
        try:
            if not window.open_evaluation_for_standard(STANDARD_ID):
                raise ValueError("主应用焦炭入口不可用")
            form = window.coke_form
            for key, value in {"object_name":"合成焦炭开发验收对象", "period":"2026年10月 合成数据", "raw_coal_energy_kgce":"111",
                "processing_energy_kgce":"0", "coke_energy_kgce":"0", "chemical_products_energy_kgce":"0",
                "recovered_heat_energy_kgce":"0", "dry_coke_output_t":"1", "dry_volatile_pct":"23", "total_moisture_pct":"10", "oven_age_years":"20"}.items():
                form.fields[key].setText(value)
            for key,value in {"oven_type":"top_charging", "heating_fuel":"coke_oven_gas", "conventional_oven":True,
                "quenching_method":"mixed", "purification":False, "wastewater":False}.items():
                form.choices[key].setCurrentIndex(form.choices[key].findData(value))
            before = context.evaluations.count()
            window.calculate_button.click()
            record_id = window.last_result_id
            if not record_id or context.evaluations.count() != before+1:
                raise ValueError("主应用没有生成唯一记录："+form.notice.text())
            window.calculate_evaluation()
            if context.evaluations.count() != before+1:
                raise ValueError("重复计算生成多条记录")
            window.view_record(record_id)
            if not window.record_detail_page.export_button.isEnabled():
                raise ValueError("主应用历史报告不可用")
            context.application.export_word_report(record_id, root/"coke-smoke.docx")
            result = context.application.get_evaluation(record_id)[1]
            if result.results[0].grade.value != "LEVEL_1":
                raise ValueError("主应用结果与独立预期不一致")
            evidence = {"kind":"UNPUBLISHED_COKE_FULL_APPLICATION", "record_id":record_id,
                "grade":"LEVEL_1", "record_hashes":_record_hashes(context,record_id),
                "saved_counts":_saved_counts(context),
                "records_written":1, "readiness_enforced":True, "main_window_dispatch":True,
                "word_generated":True, "native_gui":"OPEN", "word_layout":"OPEN"}
            (root/"smoke-evidence.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8")
            return evidence
        finally:
            window.close()
            app.processEvents()


def _readback(root):
    evidence = json.loads((root/"smoke-evidence.json").read_text(encoding="utf-8"))
    with isolated_coke_context(root) as context:
        if _record_hashes(context,evidence["record_id"]) != evidence["record_hashes"]:
            raise ValueError("重开后保存快照改变")
        if _saved_counts(context) != evidence["saved_counts"]:
            raise ValueError("重开后记录或审计数量改变")
        view = context.application.get_report_view(evidence["record_id"])
        if view.lines[0].metrics[0].grade != "1级":
            raise ValueError("保存报告读回不一致")
    return {"readback":True, "snapshots_unchanged":True, "new_records_written":0, **evidence}


def main(argv=None):
    parser = argparse.ArgumentParser(description="焦炭完整主应用开发验收；仅TEMP隔离目录，非正式发布")
    parser.add_argument("--data-dir", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--self-check", action="store_true")
    modes.add_argument("--readback", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = prepare_isolated_root(args.data_dir)
        if args.self_check:
            print(json.dumps(_smoke(root),ensure_ascii=False))
            return 0
        if args.readback:
            print(json.dumps(_readback(root),ensure_ascii=False))
            return 0
        from PySide6.QtWidgets import QApplication
        from .main import configure_application_font
        from .ui.main_window import MainWindow
        app = QApplication.instance() or QApplication([])
        configure_application_font(app)
        with isolated_coke_context(root) as context:
            window = MainWindow(context)
            window.setWindowTitle("焦炭完整功能开发验收 · 非正式发布 · TEMP隔离数据")
            window.show()
            try:
                return app.exec()
            finally:
                window.close()
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
