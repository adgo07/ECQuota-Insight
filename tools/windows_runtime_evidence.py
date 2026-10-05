# -*- coding: utf-8 -*-
"""ECQ-RS05 §十 — local Windows runtime evidence for the frozen Candidate.

Part A: clean data directory  -> frozen EXE -> bundled package installed -> a real
        GB29446 evaluation succeeds under rule_revision 2.
Part B: deterministic LEGACY data directory (published package with GB29446 r1,
        plus one saved evaluation) -> frozen EXE -> automatic reconciliation
        upgrades to the bundled r2 package -> GB29446 becomes evaluable at r2 and
        the saved evaluation keeps its original rule snapshot.

Never touches the real %LOCALAPPDATA%\\UEBench.

Path policy (AGENTS.md §1.1)
---------------------------
Nothing here hardcodes one machine's absolute path.  The repository root defaults
to this script's own parent directory and can be overridden with
``--root`` / ``UEBENCH_EVIDENCE_ROOT``, so the tool runs from any checkout.  The
few inputs that genuinely live outside the checkout (the frozen payload, the
superseded archive) are environment-overridable too.

Lazy archive access
-------------------
Part A is self-contained: it only needs the repository and the frozen EXE.  The
read-only archive is therefore touched **only** when Part B actually runs, so
``--part a`` succeeds on a machine that has no ``G:\\ECQuota-Archive`` at all.
``ECQ_LEGACY_ARCHIVE`` overrides the committed archive pointer root.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

#: Repository root: ``--root`` / ``UEBENCH_EVIDENCE_ROOT`` first, otherwise this
#: file's own parent directory.  Resolved before ``uebench`` is imported so that
#: ``sys.path`` points at the selected checkout's ``src``.
def _preliminary_root() -> Path:
    argv = sys.argv[1:]
    for index, token in enumerate(argv):
        if token == "--root" and index + 1 < len(argv):
            return Path(argv[index + 1])
        if token.startswith("--root="):
            return Path(token.split("=", 1)[1])
    return Path(os.environ.get("UEBENCH_EVIDENCE_ROOT") or Path(__file__).resolve().parents[1])


ROOT = _preliminary_root().resolve()
EXE = Path(os.environ.get("UEBENCH_EVIDENCE_EXE") or (ROOT / "dist" / "UEBench" / "UEBench.exe"))
POINTER = ROOT / "release" / "standard-packages" / "LEGACY-REFERENCE.json"
BUNDLED_PACKAGE = Path(
    os.environ.get("UEBENCH_EVIDENCE_PACKAGE")
    or (ROOT / "release" / "standard-packages" / "initial-standard-package-published.uebench")
)
PUBLIC_KEY = ROOT / "src" / "uebench" / "resources" / "update_public_key.pem"
WORK = Path(
    os.environ.get("UEBENCH_EVIDENCE_WORK")
    or (Path(tempfile.gettempdir()) / "rs05-runtime-evidence")
)


def archive_root() -> Path:
    """Archive root: ``ECQ_LEGACY_ARCHIVE`` overrides the committed pointer.

    Read lazily (never at import time) so Part A does not depend on the archive.
    """
    overridden = os.environ.get("ECQ_LEGACY_ARCHIVE")
    if overridden:
        return Path(overridden)
    return Path(json.loads(POINTER.read_text(encoding="utf-8"))["archive_root"])


def legacy_package_copy() -> Path:
    """COPY the archived parent-baseline package out of the read-only archive.

    归档原件禁止直接使用，必须复制到独立临时目录后再用（操作者决定）。
    只有 Part B 会调用本函数，因此归档缺失不会影响 Part A。
    """
    entry = json.loads(POINTER.read_text(encoding="utf-8"))["parent_baseline"]
    source = archive_root() / entry["relative_path"]
    if not source.is_file():
        raise SystemExit(
            f"旧标准包归档不可用：{source}\n"
            "（Part B 需要该归档；Part A 可在无归档机器上单独运行："
            "python tools/windows_runtime_evidence.py --part a）"
        )
    target = WORK / entry["file_name"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    target.chmod(0o644)
    return target


sys.path.insert(0, str(ROOT / "src"))

from uebench.bootstrap import create_context  # noqa: E402
from uebench.domain.models import (  # noqa: E402
    EvaluationRequest,
    InputMode,
    InputValue,
    StandardSelectionMode,
)
from uebench.infrastructure.logging import close_logging  # noqa: E402

RESULTS: dict[str, object] = {}


def db_state(root: Path) -> dict:
    db = root / "uebench.sqlite3"
    if not db.exists():
        return {"exists": False}
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        out = {"exists": True, "size": db.stat().st_size}
        out["alembic"] = [r[0] for r in cur.execute("SELECT version_num FROM alembic_version")]
        out["standards"] = cur.execute("SELECT COUNT(*) FROM standards").fetchone()[0]
        out["packages"] = [r[0] for r in cur.execute(
            "SELECT package_id FROM standard_packages ORDER BY installed_at")]
        out["gb29446_revision"] = [r[0] for r in cur.execute(
            "SELECT rule_revision FROM standards WHERE standard_id='gb-29446-2019'")]
        out["evaluations"] = cur.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
        # The immutable per-evaluation rule snapshot lives in rule_snapshot_json;
        # it must keep its original rule_revision across a package upgrade.
        out["evaluation_snapshots"] = [
            {"id": r[0], "rule_revision": r[1], "standard_id": r[2]}
            for r in cur.execute(
                "SELECT evaluation_id, "
                "json_extract(rule_snapshot_json,'$.rule_revision'), "
                "json_extract(rule_snapshot_json,'$.id') "
                "FROM evaluations ORDER BY created_at"
            )
        ] if out["evaluations"] else []
        return out
    except sqlite3.Error as exc:
        return {"exists": True, "error": str(exc)}
    finally:
        con.close()


def launch_frozen(data_dir: Path, seconds: int = 30) -> dict:
    """Start the packaged GUI against data_dir, wait for first-run work, close it."""
    env = dict(os.environ)
    env["UEBENCH_DATA_DIR"] = str(data_dir)
    proc = subprocess.Popen([str(EXE)], env=env, cwd=str(EXE.parent))
    info = {"pid": proc.pid, "exited_early": None}
    deadline = time.time() + seconds
    try:
        while time.time() < deadline:
            time.sleep(2)
            if proc.poll() is not None:
                info["exited_early"] = proc.returncode
                break
            db = data_dir / "uebench.sqlite3"
            if db.exists() and db.stat().st_size > 0:
                time.sleep(4)
                break
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
        else:
            proc.wait(timeout=5)
    info["closed"] = True
    return info


def bundled_identity() -> dict:
    import zipfile
    with zipfile.ZipFile(BUNDLED_PACKAGE) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    return {"package_id": manifest["package_id"], "data_version": manifest["data_version"]}


def _build_request(standard, organization: str, notes: str) -> EvaluationRequest:
    """Build a valid GB29446 request for whichever rule revision is installed.

    r1 and r2 are genuinely different definitions and we must NOT paper over
    that: the legacy revision predates the coal-type selection schema and uses
    ``energy.total_standard_coal`` / ``production.total_equivalent``, whereas r2
    selects a product by 煤种 and takes the r2 input keys.  Using each revision's
    own declared inputs is what "preserve the original saved semantics" means.
    """
    legacy = standard.rule_revision < 2
    if legacy:
        product = standard.products[0]
        indicator = product.indicators[0]
        # Legacy revisions declare a single direct input (e.g.
        # ``actual.coking-coal``) and no r2-style input schema, so use DIRECT
        # mode with that key.  6.0 kW·h/t falls in the 5.0 < x <= 7.0 band.
        direct_key = indicator.direct_input_key or "actual.coking-coal"
        supplied = {direct_key: InputValue(value="6.0", unit="kW·h/t")}
        mode = InputMode.DIRECT
    else:
        product = next(
            p for p in standard.products
            if (p.selection_values or {}).get("coal_type") == "炼焦煤"
        )
        supplied = {
            "washing_process": InputValue(value="跳汰"),
            "single_coal_single_process": InputValue(value="是"),
            "enterprise_status": InputValue(value="现有企业"),
            "electricity_consumption": InputValue(value="350", unit="kW·h"),
            "raw_coal_input": InputValue(value="100", unit="t"),
        }
        mode = InputMode.DETAIL
    return EvaluationRequest(
        evaluation_date=date(2026, 6, 1),
        standard_id=standard.id,
        product_id=product.id,
        selection_mode=StandardSelectionMode.CURRENT,
        input_mode=mode,
        inputs=supplied,
        organization_name=organization,
        notes=notes,
    )


def save_real_evaluation(data_dir: Path) -> dict:
    """Save one genuine GB29446 evaluation so we have real history to preserve."""
    ctx = create_context(data_dir, public_key_path=PUBLIC_KEY)
    try:
        app = ctx.application
        standard = app.get_published_standard("gb-29446-2019")
        result = app.evaluate(_build_request(
            standard, "RS05 升级取证企业", "核算周期：全年\n备注：ECQ-RS05 legacy 升级取证"))
        item = result.results[0]
        return {
            "rule_revision_at_save": standard.rule_revision,
            "grade": str(item.grade),
            "actual_value": str(item.actual_value),
            "evaluation_id": getattr(result, "evaluation_id", None),
        }
    finally:
        ctx.database.dispose()
        close_logging()


def evaluate_under_installed(data_dir: Path) -> dict:
    """Run a real GB29446 evaluation against whatever is installed right now."""
    ctx = create_context(data_dir, public_key_path=PUBLIC_KEY)
    try:
        app = ctx.application
        standard = app.get_published_standard("gb-29446-2019")
        if standard.rule_revision >= 2:
            coal = next((p for p in standard.products
                         if (p.selection_values or {}).get("coal_type") == "炼焦煤"), None)
            if coal is None:
                return {"rule_revision": standard.rule_revision, "evaluable": False,
                        "reason": "r2 定义缺少 coal_type 选择结构"}
        result = app.evaluate(_build_request(
            standard, "RS05 运行期取证企业", "核算周期：全年\n备注：ECQ-RS05 runtime evidence"))
        item = result.results[0]
        return {"rule_revision": standard.rule_revision, "evaluable": True,
                "grade": str(item.grade), "actual_value": str(item.actual_value)}
    finally:
        ctx.database.dispose()
        close_logging()


def run_part_a() -> None:
    """Clean data directory -> frozen EXE -> bundled package installed and r2 evaluable."""
    print("\n=== A. clean data directory -> frozen EXE ===")
    clean = WORK / "clean"
    clean.mkdir(parents=True, exist_ok=True)
    RESULTS["A_launch"] = launch_frozen(clean)
    RESULTS["A_state"] = db_state(clean)
    RESULTS["A_evaluate"] = evaluate_under_installed(clean)
    print("  state:", json.dumps(RESULTS["A_state"], ensure_ascii=False))
    print("  evaluate:", json.dumps(RESULTS["A_evaluate"], ensure_ascii=False))


def run_part_b() -> None:
    """Deterministic legacy r1 directory -> frozen EXE -> reconciliation to r2.

    The archived parent-baseline package is required here and copied lazily, so
    importing this module and running Part A never touch the archive.
    """
    print("\n=== B. legacy published r1 directory -> frozen EXE ===")
    legacy_package = legacy_package_copy()
    legacy = WORK / "legacy"
    legacy.mkdir(parents=True, exist_ok=True)
    ctx = create_context(legacy, public_key_path=PUBLIC_KEY)
    try:
        installed = ctx.application.install_package(legacy_package)
        print("  installed legacy package:", installed.package_id, installed.data_version)
    finally:
        ctx.database.dispose()
        close_logging()
    RESULTS["B_pre_state"] = db_state(legacy)
    RESULTS["B_pre_evaluate"] = evaluate_under_installed(legacy)
    RESULTS["B_saved_evaluation"] = save_real_evaluation(legacy)
    print("  pre-reconcile state:", json.dumps(RESULTS["B_pre_state"], ensure_ascii=False))
    print("  pre-reconcile evaluate:", json.dumps(RESULTS["B_pre_evaluate"], ensure_ascii=False))
    print("  saved evaluation:", json.dumps(RESULTS["B_saved_evaluation"], ensure_ascii=False))

    backups_before = sorted(p.name for p in (legacy / "backups").glob("pre-package-*.uebackup"))
    RESULTS["B_launch"] = launch_frozen(legacy)
    backups_after = sorted(p.name for p in (legacy / "backups").glob("pre-package-*.uebackup"))
    RESULTS["B_backups_before"] = backups_before
    RESULTS["B_backups_after"] = backups_after
    RESULTS["B_post_state"] = db_state(legacy)
    RESULTS["B_post_evaluate"] = evaluate_under_installed(legacy)
    print("  post-reconcile state:", json.dumps(RESULTS["B_post_state"], ensure_ascii=False))
    print("  post-reconcile evaluate:", json.dumps(RESULTS["B_post_evaluate"], ensure_ascii=False))
    print("  new pre-package backups:", [b for b in backups_after if b not in backups_before])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ECQ-RS05 Windows 实机运行期取证（不触碰真实用户数据目录）"
    )
    parser.add_argument(
        "--part",
        choices=("a", "b", "both"),
        default="both",
        help="a=干净目录取证（不需要外部归档）；b=旧版升级取证（需要外部归档）；both=全部",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help=f"仓库根目录（默认按脚本位置推导：{ROOT}；也可用 UEBENCH_EVIDENCE_ROOT）",
    )
    parser.add_argument(
        "--exe",
        type=Path,
        default=EXE,
        help=f"冻结 EXE 路径（默认 {EXE}；也可用 UEBENCH_EVIDENCE_EXE）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    global EXE  # noqa: PLW0603 - explicit CLI override of the frozen EXE location
    args = parse_args(argv)
    EXE = Path(args.exe).resolve()

    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)
    print("root:", ROOT)
    print("work dir:", WORK)
    print("frozen exe:", EXE, "exists:", EXE.is_file())
    if BUNDLED_PACKAGE.is_file():
        print("bundled:", bundled_identity())
        RESULTS["bundled_identity"] = bundled_identity()
    else:
        print("bundled: 缺失 ->", BUNDLED_PACKAGE)
    RESULTS["frozen_exe"] = {"path": str(EXE), "exists": EXE.is_file()}

    if args.part in ("a", "both"):
        run_part_a()
    if args.part in ("b", "both"):
        run_part_b()

    out = WORK / "runtime-evidence.json"
    out.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nwrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
