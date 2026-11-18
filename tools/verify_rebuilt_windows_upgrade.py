"""Exercise both Inno installers in a disposable GitHub-hosted Windows profile."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from ctypes import wintypes
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_COMMIT = "a83a838a01ca48dd8e8afdf061a7402aef1e7a0c"
LEGACY_PACKAGE_COMMIT = "6f570f71ae68220176ce79166d5654461ee44bc0"
LEGACY_PACKAGE_SHA256 = "4f025b8a45f03fc5539b2d5eb76bdf6c3d127b863e7485b46fbb100b6f221727"
HISTORICAL_INSTALLER_SHA256 = "234bb4b00c3ca3ea3d992b5ed3f5e3ee2ef9f01343680ee96819a98ae248a911"
PACKAGE_FILE = "initial-standard-package-published.uebench"
APP_ID = "{6C4394C8-8A07-4AB3-A9D5-67B18623C3B0}"
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}_is1"
MAIN_WINDOW_TITLES = {"单位产品能耗对标软件", "单位产品能耗限额评价软件"}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def seed_legacy_record(legacy: Path, data: Path) -> None:
    from datetime import date
    from decimal import Decimal

    sys.path.insert(0, str(legacy / "src"))
    from uebench.bootstrap import create_context
    from uebench.domain.models import EvaluationRequest, InputMode, InputValue
    from uebench.infrastructure.logging import close_logging

    context = create_context(root=data)
    try:
        result = context.evaluation_service.evaluate(EvaluationRequest(
            evaluation_date=date(2026, 9, 9),
            standard_id="gb-29446-2019",
            product_id="gb_29446-2019-coking-coal",
            input_mode=InputMode.DIRECT,
            inputs={"actual.coking-coal": InputValue(value=Decimal("7.0"), unit="kW·h/t")},
            organization_name="隔离升级验收企业",
            project_name="0.1.0 旧版业务链生成",
        ))
        require(result.rule_revision == 1, "The legacy evaluator did not use revision 1")
    finally:
        context.database.dispose()
        close_logging()


def build_legacy(root: Path, evidence: Path) -> tuple[Path, Path]:
    legacy = root / "legacy"
    package = legacy / "dist" / "standard-packages" / PACKAGE_FILE
    package_ref = f"{LEGACY_PACKAGE_COMMIT}:release/standard-packages/{PACKAGE_FILE}"
    subprocess.run(["git", "worktree", "add", "--detach", legacy, LEGACY_COMMIT], cwd=ROOT, check=True)
    package.parent.mkdir(parents=True)
    package.write_bytes(subprocess.check_output(["git", "show", package_ref], cwd=ROOT))
    require(sha256(package) == LEGACY_PACKAGE_SHA256, "Historical signed package hash mismatch")

    # The old installer requires two companion XLSX documents. Their original
    # files were never tracked. These placeholders reproduce the layout only.
    from openpyxl import Workbook

    release = legacy / "dist" / "release"
    release.mkdir()
    for name in ("单位产品能耗对标导入模板.xlsx", "统一标准规则确认表.xlsx"):
        workbook = Workbook()
        workbook.active.append(["隔离安装升级验收占位"])
        workbook.save(release / name)

    python = legacy / ".venv" / "Scripts" / "python.exe"
    with (evidence / "legacy-build.log").open("wb") as log:
        commands = (
            [sys.executable, "-m", "venv", legacy / ".venv"],
            [python, "-m", "pip", "install", "-r", "requirements.lock"],
            ["pwsh", "-NoProfile", "-File", "scripts/build_release.ps1", "-SkipTests"],
        )
        for command in commands:
            subprocess.run(command, cwd=legacy, stdout=log, stderr=subprocess.STDOUT, check=True)
    return legacy, python


def registration(hive: int) -> dict[str, str] | None:
    import winreg

    try:
        with winreg.OpenKey(hive, UNINSTALL_KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            return {name: winreg.QueryValueEx(key, name)[0] for name in (
                "InstallLocation", "DisplayVersion", "UninstallString",
            )}
    except FileNotFoundError:
        return None


def launch_and_close(executable: Path) -> None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    with subprocess.Popen([executable], cwd=executable.parent) as app:
        handle = None
        visible_titles = set()

        @callback_type
        def find_window(window, _):
            nonlocal handle
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
            if pid.value != app.pid or not user32.IsWindowVisible(window):
                return True
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(window, title, len(title))
            if title.value:
                visible_titles.add(title.value)
            if title.value not in MAIN_WINDOW_TITLES:
                return True
            handle = window
            return False

        try:
            deadline = time.monotonic() + 75
            while handle is None and time.monotonic() < deadline:
                require(app.poll() is None, f"Installed app exited at startup: {app.returncode}")
                user32.EnumWindows(find_window, 0)
                if handle is None:
                    time.sleep(0.5)
            require(handle is not None, f"No installed main window: {executable}; windows: {sorted(visible_titles)}")
            # Qt may recreate the handle while restoring the window geometry.
            # Resolve the current main window on each bounded close attempt.
            close_sent = False
            deadline = time.monotonic() + 20
            while app.poll() is None and time.monotonic() < deadline:
                time.sleep(0.5)
                handle = None
                user32.EnumWindows(find_window, 0)
                if handle is not None and user32.PostMessageW(handle, 0x0010, 0, 0):
                    close_sent = True
            require(close_sent and app.poll() == 0,
                    f"Installed app did not close normally; windows: {sorted(visible_titles)}")
        finally:
            if app.poll() is None:
                app.terminate()


def snapshot(database: Path) -> dict:
    require(database.is_file(), "Expected user database does not exist")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        revision, = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        evaluation_id, request, result, rule, deleted = connection.execute(
            "SELECT evaluation_id, request_json, result_json, rule_snapshot_json, deleted_at "
            "FROM evaluations WHERE project_name = '0.1.0 旧版业务链生成'"
        ).fetchone()
        packages = dict(connection.execute("SELECT package_id, package_sha256 FROM standard_packages"))
        coke_rules = list(connection.execute(
            "SELECT rule_revision, package_id FROM standards "
            "WHERE standard_id = 'gb-21342-2025' ORDER BY rule_revision"
        ))
    return {
        "database_revision": revision,
        "evaluation_id": evaluation_id,
        "legacy_record": {
            "request_sha256": hashlib.sha256(request.encode()).hexdigest(),
            "result_sha256": hashlib.sha256(result.encode()).hexdigest(),
            "rule_snapshot_sha256": hashlib.sha256(rule.encode()).hexdigest(),
            "deleted_at": deleted,
        },
        "installed_packages": packages,
        "coke_rules": coke_rules,
    }


def verify_upgrade(candidate: Path, evidence: Path) -> None:
    import winreg

    require(os.environ.get("GITHUB_ACTIONS") == "true" and
            os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "This installer check requires a disposable GitHub-hosted runner")
    require(registration(winreg.HKEY_CURRENT_USER) is None and
            registration(winreg.HKEY_LOCAL_MACHINE) is None,
            "The UEBench AppId is already registered")
    require("UEBENCH_DATA_DIR" not in os.environ, "The runner already overrides its user data root")

    data = Path(os.environ["LOCALAPPDATA"]) / "UEBench"
    require(not data.exists(), "The runner already has UEBench data")
    evidence.mkdir(parents=True)
    root = Path(tempfile.mkdtemp(prefix="uebench-upgrade-", dir=os.environ["RUNNER_TEMP"]))
    install_dir = root / "installed"
    executable = install_dir / "UEBench.exe"
    info = json.loads((candidate.parent / "release-build-info.json").read_text(encoding="utf-8"))
    expected_exe_hash = sha256(ROOT / "dist" / "UEBench" / "UEBench.exe")
    expected_package_hash = info["standard_package_sha256"]
    package_id = info["standard_package_id"]
    database = data / "uebench.sqlite3"
    report = {
        "baseline_kind": "rebuilt-0.1.0",
        "windows": platform.platform(),
        "legacy_source_commit": LEGACY_COMMIT,
        "historical_installer_sha256_reference_only": HISTORICAL_INSTALLER_SHA256,
        "legacy_package_sha256": LEGACY_PACKAGE_SHA256,
        "legacy_companion_workbooks": "layout placeholders",
        "candidate_source_commit": info["source_commit"],
        "candidate_id": info["candidate_id"],
        "candidate_installer_sha256": sha256(candidate),
        "candidate_exe_sha256": expected_exe_hash,
        "candidate_package_sha256": expected_package_hash,
        "checkpoints": {},
    }
    log_options = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]

    def run_installer(installer: Path, stage: str, *options: str) -> None:
        subprocess.run(
            [installer, *log_options, f"/LOG={evidence / (stage + '.log')}", *options],
            check=True, timeout=300,
        )

    def installed_version(expected: str) -> dict:
        installed = registration(winreg.HKEY_CURRENT_USER)
        require(installed is not None, "The installer did not register the common AppId")
        require(Path(installed["InstallLocation"]).resolve() == install_dir,
                "Inno did not use the same installation directory")
        require(installed["DisplayVersion"] == expected, "Wrong version registered for the common AppId")
        return installed

    def verify_retained(stage: str) -> None:
        latest = snapshot(database)
        report["checkpoints"][stage] = latest
        require(latest["evaluation_id"] == old_snapshot["evaluation_id"] and
                latest["legacy_record"] == old_snapshot["legacy_record"], "Legacy record changed")
        require(latest["installed_packages"].get(package_id) == expected_package_hash,
                "Installed package history does not contain the signed candidate package")
        require([2, package_id] in [list(item) for item in latest["coke_rules"]],
                "Signed candidate coke r2 is missing in the upgraded database")

    try:
        legacy, legacy_python = build_legacy(root, evidence)
        old_installer = legacy / "dist" / "installer" / "UEBench-Setup-0.1.0-x64.exe"
        report["rebuilt_installer_sha256"] = sha256(old_installer)
        run_installer(old_installer, "old-install", f"/DIR={install_dir}")
        installed_version("0.1.0")
        report["rebuilt_exe_sha256"] = sha256(executable)
        require(report["rebuilt_exe_sha256"] == sha256(legacy / "dist" / "UEBench" / "UEBench.exe"),
                "Installed 0.1.0 executable differs from the newly built legacy payload")
        launch_and_close(executable)
        subprocess.run([legacy_python, __file__, "--seed-legacy", legacy, data], cwd=legacy, check=True)
        old_snapshot = snapshot(database)
        require(LEGACY_PACKAGE_SHA256 in old_snapshot["installed_packages"].values(),
                "Rebuilt 0.1.0 did not install the historical signed standard package")
        report["checkpoints"]["old_saved"] = old_snapshot

        stale = install_dir / "_internal" / "legacy-payload.marker"
        stale.touch()
        run_installer(candidate, "candidate-upgrade")
        installed_version(info["product_version"])
        require(not stale.exists(), "Upgrade left obsolete content from the old runtime payload")
        require(sha256(executable) == expected_exe_hash, "Upgraded executable hash differs from candidate")
        require(sha256(install_dir / "_internal" / "uebench" / "resources" / PACKAGE_FILE)
                == expected_package_hash, "Upgraded installation contains the wrong standard package")
        launch_and_close(executable)
        verify_retained("upgraded_and_opened")
        launch_and_close(executable)
        verify_retained("reopened")

        run_installer(candidate, "candidate-reinstall")
        entry = installed_version(info["product_version"])
        launch_and_close(executable)
        verify_retained("same_version_reinstalled")

        uninstaller = Path(entry["UninstallString"].strip('"')).resolve()
        require(uninstaller.is_relative_to(install_dir), "Uninstaller path is outside the test installation")
        run_installer(uninstaller, "candidate-uninstall")
        require(not executable.exists() and registration(winreg.HKEY_CURRENT_USER) is None,
                "App executable or registration remained after uninstall")
        verify_retained("uninstalled_data_retained")
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        (evidence / "upgrade-result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--seed-legacy", type=Path, nargs=2, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.seed_legacy:
        seed_legacy_record(*args.seed_legacy)
    elif args.candidate and args.evidence:
        verify_upgrade(args.candidate.resolve(), args.evidence.resolve())
    else:
        parser.error("--candidate and --evidence are required")


if __name__ == "__main__":
    main()
