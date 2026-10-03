from __future__ import annotations

import argparse
from pathlib import Path
import zipfile

# Importable both as `python tools/<name>.py` (tools/ is sys.path[0]) and as
# `tools.<name>` from a test module.
try:
    from release_version import artifact_names, project_version
except ModuleNotFoundError:  # pragma: no cover - package-import style
    from tools.release_version import artifact_names, project_version


INCLUDE_ROOTS = ["src", "tests", "tools", "scripts", "packaging", "migrations", "data", "docs", "standards/development"]

#: Root-level files shipped in the source package.  ECQ-RS05 additionally
#: requires the governance/state documents so a source recipient can reproduce
#: the exact released state without consulting another repository.
ROOT_FILES = [
    "README.md",
    "pyproject.toml",
    "requirements.txt",
    "requirements.lock",
    "run_uebench.py",
    "uebench.spec",
    "alembic.ini",
    ".gitignore",
    # Governance / state documents (ECQ-RS05 §18).
    "AGENTS.md",
    "platform-lock.json",
    "PLATFORM_BASELINE.md",
    "TASK_STATE.md",
    "HANDOFF.md",
    "STANDARD_ISSUES_REGISTER.md",
    "参考标准开发路线.md",
]

#: Subset of ROOT_FILES whose absence must fail the build rather than be
#: silently skipped (these are the ECQ-RS05 §18 governance documents).
MANDATORY_ROOT_FILES = frozenset(
    {
        "AGENTS.md",
        "platform-lock.json",
        "PLATFORM_BASELINE.md",
        "TASK_STATE.md",
        "HANDOFF.md",
        "STANDARD_ISSUES_REGISTER.md",
        "参考标准开发路线.md",
    }
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_from_root(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def build_source_zip(output: Path) -> Path:
    root = project_root()
    output = resolve_from_root(root, output).resolve()
    files: list[Path] = []
    for name in INCLUDE_ROOTS:
        base = root / name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and "node_modules" not in path.parts
                and path.suffix not in {".pyc", ".pyo"}
            ):
                files.append(path)
    missing_required: list[str] = []
    for name in ROOT_FILES:
        path = root / name
        if path.exists():
            files.append(path)
        elif name in MANDATORY_ROOT_FILES:
            missing_required.append(name)
    if missing_required:
        raise SystemExit(f"源码包缺少必需文件：{missing_required}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(set(files)):
            archive.write(path, path.relative_to(root).as_posix())
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="生成不依赖固定盘符的UEBench源码压缩包")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/release") / artifact_names(project_version())["source"],
    )
    args = parser.parse_args()
    output = build_source_zip(args.output)
    with zipfile.ZipFile(output) as archive:
        file_count = len(archive.namelist())
    print(f"wrote {output} files={file_count} bytes={output.stat().st_size}")


if __name__ == "__main__":
    main()
