"""构建焦炭完整主应用开发EXE；干净源码、真实签包readiness、TEMP持久隔离。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    head = subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    if args.source_commit != head or subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip():
        parser.error("需要精确HEAD和干净已提交源码")
    output = args.output.resolve()
    if output.exists():
        parser.error("构建输出必须是不存在的新目录")
    output.mkdir(parents=True)
    identity = {"source_commit":head,"source_dirty":False,"kind":"UNPUBLISHED_COKE_FULL_APPLICATION",
                "formal_release":False,"production_scope_changed":False,"build_time_utc":datetime.now(timezone.utc).isoformat()}
    identity_path = output/"build-identity.json"
    identity_path.write_text(json.dumps(identity,ensure_ascii=False,indent=2),encoding="utf-8")
    package = ROOT/"release/standard-packages/initial-standard-package-published.uebench"
    subprocess.run([sys.executable,"-m","PyInstaller","--noconfirm","--onedir","--console",
        "--name","UEBench-Coke-Application","--paths",str(ROOT/"src"),
        "--distpath",str(output/"portable"),"--workpath",str(output/"build"),"--specpath",str(output),
        "--add-data",str(ROOT/"migrations")+";migrations",
        "--add-data",str(ROOT/"src/uebench/resources")+";uebench/resources",
        "--add-data",str(package)+";uebench/resources",
        "--add-data",str(identity_path)+";uebench/resources",
        "--runtime-hook",str(ROOT/"packaging/pyi_rth_uebench.py"),
        "--hidden-import","alembic.runtime.migration","--hidden-import","alembic.ddl.sqlite",
        "--exclude-module","pytest","--exclude-module","hypothesis",
        str(ROOT/"tools/coke_application.py")],cwd=ROOT,check=True)
    portable = output/"portable/UEBench-Coke-Application"
    internal = portable/"_internal"
    removed = []
    for name in ("icuuc.dll","icudt78.dll"):
        target = internal/name
        if target.exists():
            if not target.resolve().is_relative_to(output):
                raise ValueError("构建清理目标超出本次新输出目录")
            target.unlink()
            removed.append(name)
    executable = portable/"UEBench-Coke-Application.exe"
    checks = {}
    # 同一个新TEMP子目录跨进程保存/关闭/重开；不接用户数据或正式包写入口。
    with tempfile.TemporaryDirectory(prefix="ecq-coke-build-check-") as directory:
        data = Path(directory)/"isolated"
        for mode in ("--self-check","--readback"):
            completed = subprocess.run([str(executable),"--data-dir",str(data),mode],cwd=output,
                                       text=True,capture_output=True)
            checks[mode] = {"exit_code":completed.returncode,"stdout":completed.stdout,"stderr":completed.stderr}
            if completed.returncode:
                identity.update(checks=checks)
                (output/"build-result.json").write_text(json.dumps(identity,ensure_ascii=False,indent=2),encoding="utf-8")
                raise RuntimeError("完整主应用开发EXE自检/重开失败，见build-result.json")
    launcher = portable/"启动焦炭开发验收.cmd"
    launcher.write_text('@echo off\n"%~dp0UEBench-Coke-Application.exe" --data-dir "%TEMP%\\UEBench-Coke-Application-'+head[:7]+'"\n',encoding="utf-8")
    manifest = {str(p.relative_to(portable)).replace("\\","/"):{"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in sorted(portable.rglob("*")) if p.is_file()}
    (output/"payload-sha256.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    archive = output/("UEBench-Coke-Application-"+head[:7]+".zip")
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as stream:
        for name in manifest:
            stream.write(portable/name,"UEBench-Coke-Application/"+name)
    with zipfile.ZipFile(archive) as stream:
        if stream.testzip() is not None:
            raise RuntimeError("完整主应用ZIP CRC失败")
    identity.update(excluded_incompatible_icu=removed,exe_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
        checks=checks,zip=archive.name,zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),zip_bytes=archive.stat().st_size,
        payload_files=len(manifest),zip_crc="PASS",native_gui="OPEN",word_layout="OPEN",formal_install_upgrade="OPEN")
    (output/"build-result.json").write_text(json.dumps(identity,ensure_ascii=False,indent=2),encoding="utf-8")
    print(str(output/"build-result.json"))


if __name__ == "__main__":
    main()
