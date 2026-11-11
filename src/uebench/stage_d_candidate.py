"""独立开发验收入口；不修改正式标准集合，不冒认签名水泥包。"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

MARKER = ".uebench-cement-development-r3.json"


def prepare_isolated_root(root: Path, *, read_only=False) -> Path:
    root = root.absolute()
    if root.is_symlink() or (root.exists() and root.resolve() != root):
        raise ValueError("验收目录不能使用链接或重解析路径")
    for ancestor in [root, *root.parents]:
        if ancestor.exists() and (ancestor.is_symlink() or getattr(ancestor.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400):
            raise ValueError("验收目录祖先包含链接或重解析点")
    temporary = Path(tempfile.gettempdir()).resolve()
    if not root.resolve().is_relative_to(temporary):
        raise ValueError("开发验收数据必须位于本进程TEMP目录内")
    protected = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "UEBench"
    protected_paths = [protected]
    if os.environ.get("UEBENCH_DATA_DIR"):
        protected_paths.append(Path(os.environ["UEBENCH_DATA_DIR"]))
    if any(root.resolve().is_relative_to(path.resolve()) or path.resolve().is_relative_to(root.resolve()) for path in protected_paths):
        raise ValueError("验收目录不能访问正式用户数据")
    expected = {"schema": "ecq.cement-development-r3.v1", "purpose": "开发验收，非正式发布", "root": str(root)}
    marker = root / MARKER
    if root.exists() and any(root.iterdir()):
        if not marker.is_file() or json.loads(marker.read_text(encoding="utf-8")) != expected:
            raise ValueError("仅允许新空目录或本候选已标识目录")
        for path in root.rglob("*"):
            if path.is_symlink() or getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
                raise ValueError("验收目录包含链接或重解析点")
    if read_only:
        if not marker.is_file():
            raise ValueError("只读验收要求已标记目录")
        return root
    root.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")
    return root


def candidate_definition():
    from .domain.models import StandardDefinition
    from .domain.gb16780 import adopted
    packaged = Path(__file__).resolve().parent / "resources/gb-16780-2021-r3-candidate.json"
    source = Path(__file__).resolve().parents[2] / "standards/development/GB16780-2021/gb-16780-2021-r3-candidate.json"
    definition = StandardDefinition.model_validate_json((packaged if packaged.exists() else source).read_bytes())
    if not adopted(definition):
        raise ValueError("开发候选映射身份无效")
    return definition


def main(argv=None):
    parser = argparse.ArgumentParser(description="水泥r3开发验收专用，非正式发布；仅TEMP隔离目录")
    parser.add_argument("--data-dir", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--self-check", action="store_true")
    modes.add_argument("--readback", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        root = prepare_isolated_root(arguments.data_dir, read_only=arguments.readback)
        definition = candidate_definition()
    except (ValueError, OSError) as error:
        parser.error(str(error))
    if arguments.readback:
        print(json.dumps(_readback(root)))
        return 0
    from .application.evaluation_support import _DEVELOPMENT_EVALUATION_IDS
    token = _DEVELOPMENT_EVALUATION_IDS.set(frozenset({"gb-16780-2021"}))
    try:
        if arguments.self_check or arguments.readback:
            from .bootstrap import create_context
            from .main import reconcile_standard_package
            context = create_context(root, public_key_path=Path(__file__).resolve().parent / "resources/update_public_key.pem")
            try:
                reconcile_standard_package(context)
                context.standards.install(definition)
                if context.standards.get_published(definition.id).rule_revision != 3:
                    raise ValueError("候选规则未安装")
                identity_file = root / "smoke-record-id.txt"
                if arguments.readback:
                    record = context.application.get_evaluation(identity_file.read_text(encoding="utf-8"))
                    if record is None or record[1].rule_revision != 3:
                        raise ValueError("保存快照读回失败")
                else:
                    from .domain.models import EvaluationRequest, CementLineInput, InputMode, InputValue
                    from datetime import date
                    request = EvaluationRequest(evaluation_date=date(2026, 11, 11), standard_id=definition.id,
                        product_id="cement-assessment", input_mode=InputMode.DETAIL, inputs={}, notes="核算周期：全年",
                        cement_lines=[CementLineInput(line_id="smoke", line_name="开发验收粉磨线", production_mode="purchased_clinker_grinding",
                            inputs={"cement.production_t": InputValue(value="1000"), "cement.preparation_electricity_kwh": InputValue(value="29000")})])
                    result = context.application.evaluate(request)
                    identity_file.write_text(result.evaluation_id, encoding="utf-8")
                    record = context.application.get_evaluation(result.evaluation_id)
                _verify_smoke_result(record[1])
                import sqlite3, hashlib
                with sqlite3.connect(context.paths.database) as connection:
                    row = connection.execute("SELECT request_json,result_json,rule_snapshot_json FROM evaluations WHERE evaluation_id=?", (record[1].evaluation_id,)).fetchone()
                    evidence = {"record_id": record[1].evaluation_id,
                        "payload_sha256": [hashlib.sha256(value.encode("utf-8")).hexdigest() for value in row],
                        "record_count": connection.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0],
                        "audit_count": connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]}
                (root / "smoke-evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
                print(json.dumps({"development_only": True, "cement_revision": 3, "saved_record": record[1].evaluation_id,
                                  "readback": arguments.readback, "grades": [item.grade.value for item in record[1].results], "data_directory": str(root)}))
                return 0
            finally:
                context.database.dispose()
        from .main import _run_desktop_application
        return _run_desktop_application(root=root, candidate_definition=definition,
            candidate_title="水泥r3开发验收 · 非正式发布 · TEMP隔离数据")
    finally:
        _DEVELOPMENT_EVALUATION_IDS.reset(token)


def _verify_smoke_result(result):
    from decimal import Decimal
    applicable = [item for item in result.results if item.indicator_id == "cement-preparation.electricity"]
    if (len(result.results) != 5 or len(applicable) != 1
            or applicable[0].actual_value != Decimal(29) or applicable[0].grade.value != "LEVEL_2"
            or any(item.grade.value != "NOT_APPLICABLE" or item.actual_value is not None
                   for item in result.results if item.indicator_id != "cement-preparation.electricity")):
        raise ValueError("开发验收表3保存值/等级与独立预期不符")


def _readback(root):
    import sqlite3, hashlib
    from .domain.models import EvaluationResult
    evidence = json.loads((root / "smoke-evidence.json").read_text(encoding="utf-8"))
    with sqlite3.connect((root / "uebench.sqlite3").as_uri() + "?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT request_json,result_json,rule_snapshot_json FROM evaluations WHERE evaluation_id=?", (evidence["record_id"],)).fetchone()
        if not row or [hashlib.sha256(value.encode("utf-8")).hexdigest() for value in row] != evidence["payload_sha256"]:
            raise ValueError("读回三JSON原始哈希不一致")
        if connection.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] != evidence["record_count"] or connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] != evidence["audit_count"]:
            raise ValueError("读回记录数或审计数改变")
        _verify_smoke_result(EvaluationResult.model_validate_json(row[1]))
    return {"development_only": True, "readback": True, **evidence}


if __name__ == "__main__":
    raise SystemExit(main())
