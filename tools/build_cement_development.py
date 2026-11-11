"""水泥隔离开发EXE构建；不发布、不签名、不运行安装器。"""
from __future__ import annotations
import argparse
import json
import hashlib
from datetime import datetime, timezone
import tomllib
import os
from pathlib import Path
import subprocess
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="独立水泥开发验收EXE构建，不能正式发布")
    parser.add_argument("--development-only", action="store_true", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if head != arguments.source_commit:
        parser.error("构建提交与实际HEAD不一致")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
        parser.error("独立开发候选要求干净已提交源码")
    output = arguments.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("构建输出必须不存在或为空，不覆盖旧产物")
    output.mkdir(parents=True, exist_ok=True)
    pin = json.loads((root / "release/standard-packages/PIN.json").read_text(encoding="utf-8"))
    product = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    evidence = output / "build-identity.json"
    evidence.write_text(json.dumps({"schema": "ecq.build-identity.v1", "source_commit": head,
        "candidate_id": "cement-development-r3-" + head[:8], "formal_release": False,
        "product_version": product, "source_dirty": False, "standard_package_id": pin["package_id"],
        "standard_data_version": pin["data_version"], "standard_package_sha256": pin["sha256"],
        "build_time_utc": datetime.now(timezone.utc).isoformat(),
        "development_candidate": {"revision": 3, "purpose": "仅开发隔离验收",
          "raw_sha256": hashlib.sha256((root / "standards/development/GB16780-2021/gb-16780-2021-r3-candidate.json").read_bytes()).hexdigest()}}, ensure_ascii=False), encoding="utf-8")
    environment = os.environ.copy()
    environment["ECQ_CEMENT_DEVELOPMENT_BUILD_INFO"] = str(evidence)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", str(output / "portable"),
                    "--workpath", str(output / "build"), str(root / "uebench-stage-d.spec")], cwd=root, env=environment, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
