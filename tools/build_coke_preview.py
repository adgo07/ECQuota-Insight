"""构建可追溯的焦炭隔离预览EXE，不构建正式安装包或签名规则包。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    head = subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
    if args.source_commit != head or subprocess.check_output(["git","status","--porcelain"],cwd=root,text=True).strip():
        parser.error("需要精确HEAD和干净已提交源码")
    output = args.output.resolve()
    if output.exists():
        parser.error("输出须为不存在的新目录")
    output.mkdir(parents=True)
    identity = {"source_commit":head,"source_dirty":False,"kind":"UNPUBLISHED_PREVIEW_ONLY",
                "formal_release":False,"production_scope_changed":False,"build_time_utc":datetime.now(timezone.utc).isoformat()}
    identity_path = output / "build-identity.json"
    identity_path.write_text(json.dumps(identity,ensure_ascii=False,indent=2),encoding="utf-8")
    subprocess.run([sys.executable,"-m","PyInstaller","--noconfirm","--onedir","--console",
        "--name","UEBench-Coke-Preview","--paths",str(root/"src"),
        "--distpath",str(output/"portable"),"--workpath",str(output/"build"),"--specpath",str(output),
        "--add-data",str(root/"migrations")+";migrations",
        "--add-data",str(root/"src/uebench/resources")+";uebench/resources",
        "--add-data",str(identity_path)+";uebench/resources",
        "--runtime-hook",str(root/"packaging/pyi_rth_uebench.py"),
        "--hidden-import","alembic.runtime.migration","--hidden-import","alembic.ddl.sqlite",
        "--exclude-module","pytest","--exclude-module","hypothesis",
        str(root/"tools/coke_preview.py")],cwd=root,check=True)
    executable = output/"portable/UEBench-Coke-Preview/UEBench-Coke-Preview.exe"
    completed = subprocess.run([str(executable),"--self-check"],cwd=output,text=True,capture_output=True)
    identity.update(exe_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
                    self_check_exit_code=completed.returncode,self_check_stdout=completed.stdout,self_check_stderr=completed.stderr)
    (output/"build-result.json").write_text(json.dumps(identity,ensure_ascii=False,indent=2),encoding="utf-8")
    if completed.returncode:
        raise RuntimeError("隔离预览EXE自检失败，见build-result.json")
    print(str(output/"build-result.json"))


if __name__ == "__main__":
    main()
