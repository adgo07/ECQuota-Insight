"""ECQ-RS05 §14 — 无头候选自检门禁（Candidate self-check gate）。

这些测试证明：

1. 全新隔离 ``--data-dir`` 下自检退出码为 ``0``，报告包含全部必需检查项；
2. 报告版本与 ``uebench.__version__``、``pyproject.toml`` 一致；
3. 内嵌 RS04 Golden 子集的三个案例等级正确（含 ``5.0000004`` full-value trap）；
4. 损坏的数据目录或缺失的标准包会以退出码 ``1`` 失败，并在报告中记录原因；
5. 自检子进程不导入 PySide6（也不需要 ``QT_QPA_PLATFORM=offscreen``）；
6. 自检只写隔离 ``--data-dir``，不触碰真实 ``%LOCALAPPDATA%\\UEBench``。

子进程统一通过 ``python -c`` 调用 ``uebench.main.main(argv)``，因此测试的是
真实 CLI 入口而不是测试内的近似实现。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from decimal import Decimal
from pathlib import Path

import pytest

import uebench
from uebench.application import self_check as self_check_module

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PUBLIC_KEY = SRC / "uebench" / "resources" / "update_public_key.pem"

#: 报告必须包含的检查项（顺序即执行顺序）。
REQUIRED_CHECKS = (
    "build_info",
    "standard_package",
    "database",
    "golden_replay",
    "record_roundtrip",
    "excel_import_chain",
)

#: 自检在子进程内必须完全没有导入过 Qt。
QT_MODULE_PREFIX = "PySide6"

_SUMMARY_PREFIX = "UEBench 自检："

_CHILD_SCRIPT = """\
import json, os, sys
sys.path.insert(0, __SRC__)
from uebench.main import main
try:
    code = main(__ARGV__)
except SystemExit as exc:
    code = exc.code if isinstance(exc.code, int) else 1
result = {
    "exit_code": code,
    "py_side6_loaded": any(n == "PySide6" or n.startswith("PySide6.") for n in sys.modules),
    "qt_widgets_loaded": "PySide6.QtWidgets" in sys.modules,
    "qt_qpa_platform": os.environ.get("QT_QPA_PLATFORM"),
    "uebench_data_dir_env": os.environ.get("UEBENCH_DATA_DIR"),
}
print("CHILD_RESULT " + json.dumps(result, ensure_ascii=False), flush=True)
sys.exit(code)
"""


def _child_script(argv: list[str]) -> str:
    return _CHILD_SCRIPT.replace("__SRC__", repr(str(SRC))).replace(
        "__ARGV__", repr([str(item) for item in argv])
    )


def run_cli(
    argv: list[str],
    *,
    local_app_data: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict | None]:
    """在子进程中执行真实 CLI；返回 (进程结果, 子进程自报状态)。

    ``QT_QPA_PLATFORM`` 与 ``UEBENCH_DATA_DIR`` 会被显式移除，以证明自检既不
    需要 offscreen 平台，也不会被环境变量重定向数据目录。
    """
    env = dict(os.environ)
    env.pop("QT_QPA_PLATFORM", None)
    env.pop("UEBENCH_DATA_DIR", None)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(SRC), str(ROOT), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    env["PYTHONIOENCODING"] = "utf-8"
    if local_app_data is not None:
        env["LOCALAPPDATA"] = str(local_app_data)
    completed = subprocess.run(
        [sys.executable, "-B", "-c", _child_script(argv)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        env=env,
        timeout=900,
    )
    payload = None
    for line in completed.stdout.splitlines():
        if line.startswith("CHILD_RESULT "):
            payload = json.loads(line[len("CHILD_RESULT ") :])
    return completed, payload


def sections(report: dict) -> dict[str, dict]:
    return {check["id"]: check for check in report["checks"]}


@pytest.fixture(scope="module")
def cli_run(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """执行一次完整自检并复用其结果（安装 48 条标准，代价较高）。"""
    base = tmp_path_factory.mktemp("self-check")
    data_dir = base / "isolated-data"
    output = base / "self-check-report.json"
    local_app_data = base / "localappdata"
    local_app_data.mkdir()
    completed, payload = run_cli(
        ["--self-check", "--data-dir", str(data_dir), "--output", str(output)],
        local_app_data=local_app_data,
    )
    report = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    return {
        "completed": completed,
        "payload": payload,
        "report": report,
        "data_dir": data_dir,
        "output": output,
        "local_app_data": local_app_data,
    }


# ---------------------------------------------------------------------------
# 1. 全新隔离数据目录必须通过，并且报告包含全部必需检查项
# ---------------------------------------------------------------------------


def test_fresh_isolated_data_dir_passes_with_every_required_section(cli_run: dict) -> None:
    completed = cli_run["completed"]
    assert completed.returncode == 0, f"{completed.stdout}\n{completed.stderr}"
    assert cli_run["payload"] is not None, f"子进程未回报状态：{completed.stdout}"
    assert cli_run["payload"]["exit_code"] == 0
    assert _SUMMARY_PREFIX in completed.stdout

    report = cli_run["report"]
    assert report is not None, "自检未写出 JSON 报告"
    assert report["schema"] == self_check_module.REPORT_SCHEMA
    assert report["schema_version"] == self_check_module.REPORT_SCHEMA_VERSION
    assert report["overall_status"] == "passed"
    assert report["exit_code"] == 0
    assert report["failed_checks"] == []

    found = sections(report)
    assert tuple(found) == REQUIRED_CHECKS, f"检查项缺失或顺序变化：{tuple(found)}"
    for check_id, section in found.items():
        assert section["status"] == "passed", f"{check_id}: {section['errors']}"
        assert section["errors"] == [], check_id
        assert isinstance(section["details"], dict) and section["details"], check_id


def test_fresh_report_is_json_serialisable(cli_run: dict) -> None:
    report = cli_run["report"]
    assert json.loads(json.dumps(report, ensure_ascii=False)) == report


def test_exit_code_constants_match_the_documented_contract() -> None:
    assert self_check_module.EXIT_OK == 0
    assert self_check_module.EXIT_CHECKS_FAILED == 1
    assert self_check_module.EXIT_USAGE == 2


def test_frozen_layout_locates_packaged_standard_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """打包布局（``sys._MEIPASS`` / ``_MEIPASS/_internal``）必须能找到标准包与公钥。

    这里只验证路径解析，不伪造签名或安装，因此不需要 21MB 的真实标准包。
    """
    layouts = (
        ("meipass-root", Path()),
        ("meipass-internal", Path("_internal")),
    )
    for base_name, relative in layouts:
        meipass = tmp_path / base_name
        resources = meipass / relative / "uebench" / "resources"
        resources.mkdir(parents=True)
        package = resources / self_check_module.PREFERRED_PACKAGE_FILENAME
        package.write_bytes(b"stub-package")
        public_key = resources / self_check_module.PUBLIC_KEY_FILENAME
        public_key.write_bytes(b"stub-key")

        monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        assert self_check_module.source_root() is None
        assert self_check_module.locate_standard_package() == package, base_name
        assert self_check_module.locate_public_key() == public_key, base_name


# ---------------------------------------------------------------------------
# 2. 版本一致
# ---------------------------------------------------------------------------


def test_report_version_matches_package_and_pyproject(cli_run: dict) -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    authorative = pyproject["project"]["version"]

    report = cli_run["report"]
    build_info = sections(report)["build_info"]["details"]
    assert report["product_version"] == authorative
    assert build_info["product_version"] == authorative
    assert uebench.__version__ == authorative
    assert build_info["rule_engine_version"] == uebench.RULE_ENGINE_VERSION
    assert build_info["frozen"] is False
    assert build_info["source_root"] == str(ROOT)
    assert build_info["python_version"].startswith("3.13")


# ---------------------------------------------------------------------------
# 3. 内嵌 Golden 子集的等级
# ---------------------------------------------------------------------------


def test_golden_replay_reports_the_three_embedded_cases(cli_run: dict) -> None:
    golden = sections(cli_run["report"])["golden_replay"]["details"]
    assert golden["golden_id"] == self_check_module.GOLDEN_ID
    assert golden["golden_version"] == self_check_module.GOLDEN_VERSION
    assert golden["standard_id"] == self_check_module.GOLDEN_STANDARD_ID
    assert golden["rule_revision"] == self_check_module.GOLDEN_RULE_REVISION
    assert golden["passed_case_count"] == 3
    assert golden["failed_case_count"] == 0

    cases = {case["case_id"]: case for case in golden["cases"]}
    assert set(cases) == {case["case_id"] for case in self_check_module.GOLDEN_CASES}

    expected_grades = {
        "gb29446-coking-grade1-exact-l1": "LEVEL_1",
        "gb29446-coking-not-qualified-above-l3": "NOT_QUALIFIED",
        "gb29446-coking-full-value-trap": "LEVEL_2",
    }
    expected_values = {
        "gb29446-coking-grade1-exact-l1": "5.0",
        "gb29446-coking-not-qualified-above-l3": "9.13",
        "gb29446-coking-full-value-trap": "5.0000004",
    }
    for case_id, grade in expected_grades.items():
        case = cases[case_id]
        assert case["passed"] is True, f"{case_id}: {case['errors']}"
        assert case["expected_grade"] == grade
        assert case["actual_grade"] == grade, case_id
        assert case["expected_actual_value"] == format(
            Decimal(expected_values[case_id]).normalize(), "f"
        ), case_id
        assert case["actual_value"] == case["expected_actual_value"], case_id
        assert case["evaluation_id"], case_id

    # full-value trap：比较前不得做隐式修约，5.0000004 必须不是 1 级。
    trap = cases["gb29446-coking-full-value-trap"]
    assert trap["expected_actual_value"] == "5.0000004"
    assert trap["actual_value"] == "5.0000004"
    assert trap["actual_grade"] != "LEVEL_1"


def test_golden_replay_records_which_rule_was_evaluated(cli_run: dict) -> None:
    """规则来源必须显式记录，且落后于 Golden 的 payload 必须产生警告。"""
    golden = sections(cli_run["report"])["golden_replay"]["details"]
    assert golden["rule_source"] in {"standard-package", "repository-definition"}
    assert golden["installed_rule_revision"] == self_check_module.GOLDEN_RULE_REVISION
    if golden["rule_source"] == "repository-definition":
        assert golden["rule_source_path"] == str(
            ROOT / "data" / "definitions" / f"{self_check_module.GOLDEN_STANDARD_ID}.json"
        )
        assert any("known_gap" in warning for warning in cli_run["report"]["warnings"])


# ---------------------------------------------------------------------------
# 4. 损坏的数据目录 / 缺失的标准包必须以 1 失败并记录
# ---------------------------------------------------------------------------


def test_missing_standard_package_is_recorded_as_failure(tmp_path: Path) -> None:
    """把解析到的标准包指向不存在的文件，检查项必须失败并写明原因。"""
    from uebench.bootstrap import create_context
    from uebench.infrastructure.logging import close_logging
    from uebench.main import write_workbook_rows

    data_dir = tmp_path / "isolated-data"
    missing_package = tmp_path / "initial-standard-package-published.uebench"

    def context_factory(target: Path):
        return create_context(target, public_key_path=PUBLIC_KEY)

    try:
        report = self_check_module.run_self_check(
            data_dir=data_dir,
            context_factory=context_factory,
            workbook_writer=write_workbook_rows,
            package_path=missing_package,
        )
    finally:
        close_logging()

    assert report["exit_code"] == 1
    assert report["overall_status"] == "failed"
    assert report["failed_checks"] == ["standard_package"]
    section = sections(report)["standard_package"]
    assert section["status"] == "failed"
    assert any("标准包" in error for error in section["errors"]), section["errors"]
    assert section["details"]["package_path"] == str(missing_package)
    # 报告仍必须完整且可序列化。
    assert tuple(sections(report)) == REQUIRED_CHECKS
    json.dumps(report, ensure_ascii=False)


def test_corrupted_data_dir_fails_the_command_and_writes_the_report(tmp_path: Path) -> None:
    """``--data-dir`` 指向一个已存在的文件时，数据库无法初始化。"""
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("occupied", encoding="utf-8")
    output = tmp_path / "corrupted.json"

    completed, payload = run_cli(
        ["--self-check", "--data-dir", str(blocked), "--output", str(output)]
    )

    assert completed.returncode == 1, f"{completed.stdout}\n{completed.stderr}"
    assert payload is not None and payload["exit_code"] == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["overall_status"] == "failed"
    assert "database" in report["failed_checks"]
    database_section = sections(report)["database"]
    assert database_section["status"] == "failed"
    assert any("数据目录初始化失败" in error for error in database_section["errors"])


def test_usage_errors_exit_with_code_two(tmp_path: Path) -> None:
    """缺少 --data-dir 或 --output 不可写属于用法错误。"""
    completed, payload = run_cli(["--self-check"])
    assert completed.returncode == 2
    assert payload is not None and payload["exit_code"] == 2

    unwritable_output = tmp_path / "output-is-a-directory"
    unwritable_output.mkdir()
    completed, payload = run_cli(
        [
            "--self-check",
            "--data-dir",
            str(tmp_path / "never-created"),
            "--output",
            str(unwritable_output),
        ]
    )
    assert completed.returncode == 2, f"{completed.stdout}\n{completed.stderr}"
    assert payload is not None and payload["exit_code"] == 2
    assert not (tmp_path / "never-created").exists()

    completed, payload = run_cli(["--data-dir", str(tmp_path / "gui-mode")])
    assert completed.returncode == 2
    assert payload is not None and payload["exit_code"] == 2


# ---------------------------------------------------------------------------
# 5. 自检不导入 Qt
# ---------------------------------------------------------------------------


def test_self_check_subprocess_never_imports_qt(cli_run: dict) -> None:
    payload = cli_run["payload"]
    assert payload is not None
    assert payload["py_side6_loaded"] is False, "自检子进程导入了 PySide6"
    assert payload["qt_widgets_loaded"] is False, "自检子进程导入了 QApplication 所在的 QtWidgets"
    # 自检必须在 QT_QPA_PLATFORM 未设置（即真正无 Qt）的情况下通过。
    assert payload["qt_qpa_platform"] is None
    assert payload["uebench_data_dir_env"] is None

    build_info = sections(cli_run["report"])["build_info"]["details"]
    assert build_info["qt_imported"] is False
    assert build_info["qt_imported_by_self_check"] is False


def test_self_check_module_does_not_import_pyside6_at_all() -> None:
    """application 层自检模块不得出现任何 PySide6 导入（含函数级延迟导入）。

    模块文档里出现 “PySide6” 字样是允许的（它说明约束），所以这里走 AST，
    与 ``tests/test_architecture_boundaries.py`` 使用同一判定口径。
    """
    import ast

    path = SRC / "uebench" / "application" / "self_check.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not [
        name
        for name in imported
        if name == QT_MODULE_PREFIX or name.startswith(f"{QT_MODULE_PREFIX}.")
    ], imported


# ---------------------------------------------------------------------------
# 6. 隔离数据目录
# ---------------------------------------------------------------------------


def test_isolated_data_dir_holds_the_database_and_localappdata_is_untouched(
    cli_run: dict,
) -> None:
    data_dir = cli_run["data_dir"]
    report = cli_run["report"]

    assert (data_dir / "uebench.sqlite3").is_file(), "SQLite 数据库未出现在隔离 --data-dir 中"
    assert report["data_dir"] == str(data_dir.resolve())
    database_section = sections(report)["database"]["details"]
    assert Path(database_section["database_path"]).parent == data_dir.resolve()

    # 真实用户数据目录绝不出现：子进程的 LOCALAPPDATA 指向隔离目录。
    assert not (cli_run["local_app_data"] / "UEBench").exists()
    assert report["data_dir"] != str(
        (cli_run["local_app_data"] / "UEBench").resolve()
    )

    # 模板等工作簿同样只写在隔离目录内。
    template_path = Path(sections(report)["excel_import_chain"]["details"]["template_path"])
    assert data_dir.resolve() in template_path.resolve().parents
