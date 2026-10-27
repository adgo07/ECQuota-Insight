"""用有界 Python 子进程运行冻结 EXE，保留自检报告和进程日志。"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Sequence


class SelfCheckError(RuntimeError):
    """进程失败或报告不满足候选门禁。证据保留在异常所指目录。"""


def run_self_check(
    command: Sequence[str], project_root: Path, *, timeout_seconds: float = 120
) -> Path:
    """command 是参数数组，生产调用只传指定 EXE；测试可传 Python 探针。"""
    if not command or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("自检命令不能为空，超时须为有限正数")
    root = project_root.resolve(strict=True)
    work = root / "work"
    work.mkdir(exist_ok=True)
    if work.is_symlink() or work.resolve().parent != root:
        raise ValueError("自检 work 目录必须实际位于项目目录内")
    run_dir = Path(tempfile.mkdtemp(prefix="candidate-self-check-", dir=work)).resolve()
    scratch = run_dir / "scratch"
    data = scratch / "data"
    temporary = scratch / "temp"
    data.mkdir(parents=True)
    temporary.mkdir()
    report = run_dir / "report.json"
    args = [*command, "--self-check", "--data-dir", str(data), "--output", str(report)]
    environment = os.environ.copy()
    environment.update(UEBENCH_DATA_DIR=str(data), TEMP=str(temporary), TMP=str(temporary))
    outcome: dict = {
        "command": args,
        "cwd": str(root),
        "timeout_seconds": timeout_seconds,
        "isolated_environment": {key: environment[key] for key in ("UEBENCH_DATA_DIR", "TEMP", "TMP")},
        "status": "failed",
        "report": str(report),
    }
    try:
        with (run_dir / "stdout.log").open("wb") as stdout, (run_dir / "stderr.log").open("wb") as stderr:
            # shell=False 保证中文、空格和 shell 元字符原样传递；不等待整个 Windows job。
            process = subprocess.Popen(
                args, cwd=root, env=environment, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                shell=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            outcome["pid"] = process.pid
            try:
                outcome["returncode"] = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                # 只结束本次 Popen 拥有的进程，不按名称或全局进程树终止其他程序。
                outcome["timed_out"] = True
                process.kill()
                outcome["returncode"] = process.wait(timeout=10)
                raise SelfCheckError(f"冻结 EXE 自检超时：{timeout_seconds} 秒") from exc
        if outcome["returncode"] != 0:
            raise SelfCheckError(f"冻结 EXE 自检退出码：{outcome['returncode']}")
        try:
            payload = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SelfCheckError("冻结 EXE 自检报告缺失或损坏") from exc
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != "uebench.self-check-report"
            or payload.get("overall_status") != "passed"
            or payload.get("frozen") is not True
            or payload.get("failed_checks") != []
        ):
            raise SelfCheckError("冻结 EXE 自检报告未通过候选门禁")
        # 只清理成功运行的自有 scratch；报告、stdout/stderr 与 runner 记录留存。
        if scratch.is_symlink() or scratch.resolve().parent != run_dir or run_dir.parent != work.resolve():
            raise SelfCheckError("拒绝清理超出本次自检边界的临时数据")
        shutil.rmtree(scratch)
        outcome["status"] = "passed"
        return report
    except Exception as exc:
        outcome["error"] = str(exc)
        raise SelfCheckError(f"{exc}；自检证据：{run_dir}") from exc
    finally:
        (run_dir / "runner.json").write_text(
            json.dumps(outcome, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=120)
    options = parser.parse_args()
    try:
        executable = options.exe.resolve(strict=True)
        if not executable.is_file():
            raise ValueError(f"冻结 EXE 不存在：{executable}")
        report = run_self_check(
            [str(executable)], options.project_root, timeout_seconds=options.timeout_seconds
        )
    except (SelfCheckError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    # stdout 是给 PowerShell 的机器接口：仅发 ASCII，避免双方代码页不同损坏中文路径。
    print(json.dumps({"report_path": str(report)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
