"""Explicit isolated acceptance entry; the normal application scope stays fixed."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import stat

from .application.evaluation_support import SUPPORTED_EVALUATION_STANDARD_IDS

CANDIDATE_STANDARD_IDS = SUPPORTED_EVALUATION_STANDARD_IDS | {"gb-16780-2021"}
MARKER = ".uebench-stage-d-cement.json"
MARKER_SCHEMA = "ecq.stage-d-cement-isolation.v1"


def _normalized(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def _reject_links(root: Path) -> None:
    """Inspect without following any reparse point, including file links."""
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    raise ValueError("验收目录包含链接或重解析点；拒绝访问外部数据。")
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))


def prepare_isolated_root(root: Path) -> Path:
    """Resolve junctions, reject user-data overlap, then require an empty/marked root."""
    root = root.resolve()
    # Protect both the real Windows default and an existing configured override.
    protected = [Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "UEBench"]
    if os.environ.get("UEBENCH_DATA_DIR"):
        configured = Path(os.environ["UEBENCH_DATA_DIR"])
        # The existing self-check runner sets its own empty scratch as override.
        # Any populated override remains protected regardless of marker contents.
        if configured.exists() and (not configured.is_dir() or any(configured.iterdir())):
            protected.append(configured)
    candidate = _normalized(root)
    for path in protected:
        target = _normalized(path)
        try:
            common = os.path.commonpath([candidate, target])
        except ValueError:  # different drives
            continue
        if common in (candidate, target):
            raise ValueError("验收数据目录不得与现有用户数据目录重叠。")
    expected = {"schema": MARKER_SCHEMA, "resolved_root": candidate}
    marker = root / MARKER
    if root.exists():
        if not root.is_dir():
            raise ValueError("验收数据目录必须是文件夹。")
        _reject_links(root)
        if marker.exists():
            if json.loads(marker.read_text(encoding="utf-8")) != expected:
                raise ValueError("验收目录标记无效；请指定新的空文件夹。")
        elif any(root.iterdir()):
            raise ValueError("验收目录已有未标识数据；请指定新的空文件夹。")
    root.mkdir(parents=True, exist_ok=True)
    if not marker.exists():
        marker.write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="水泥Stage D隔离验收候选，尚未正式支持；禁止覆盖已安装产品。")
    parser.add_argument("--data-dir", type=Path, required=True, help="必填：新的空验收目录，或本候选已标识目录")
    parser.add_argument("--self-check", action="store_true", help="运行既有无头自检")
    parser.add_argument("--acceptance-smoke", action="store_true", help="水泥实包验收：新隔离子目录及独立进程读回")
    parser.add_argument("--acceptance-readback", action="store_true", help="验收子进程：只读快照，不重新计算")
    parser.add_argument("--output", type=Path, help="无头自检JSON输出")
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if sum((arguments.self_check, arguments.acceptance_smoke, arguments.acceptance_readback)) > 1:
        parser.error("三种自检/验收模式不能同时选择")
    if arguments.output and not arguments.self_check:
        parser.error("--output仅用于--self-check")
    try:
        root = prepare_isolated_root(arguments.data_dir)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    from .application.build_identity import load_build_identity
    identity = load_build_identity()
    evidence = {"purpose": "水泥Stage D验收候选，尚未正式支持", "source_commit": identity.source_commit,
                "candidate_id": identity.candidate_id, "standard_package_id": identity.standard_package_id,
                "standard_data_version": identity.standard_data_version, "data_directory": str(root),
                "evaluation_standard_ids": sorted(CANDIDATE_STANDARD_IDS)}
    (root / "candidate-runtime.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    if arguments.acceptance_smoke or arguments.acceptance_readback:
        from .stage_d_smoke import run_smoke, readback
        return run_smoke(root) if arguments.acceptance_smoke else readback(root)
    from uebench import main as application_main
    if arguments.self_check:
        args = ["--self-check", "--data-dir", str(root)]
        if arguments.output:
            args += ["--output", str(arguments.output)]
        return application_main.main(args)
    return application_main._run_desktop_application(
        root=root, evaluation_standard_ids=CANDIDATE_STANDARD_IDS,
        candidate_title=f"单位产品能耗限额评价软件 · 水泥Stage D验收候选 · {identity.candidate_id}")
