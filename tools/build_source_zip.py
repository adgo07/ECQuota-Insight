from __future__ import annotations

import argparse
from pathlib import Path
import zipfile


INCLUDE_ROOTS = ["src", "tests", "tools", "scripts", "packaging", "migrations", "data", "docs"]
ROOT_FILES = [
    "README.md",
    "pyproject.toml",
    "requirements.txt",
    "requirements.lock",
    "run_uebench.py",
    "uebench.spec",
    "alembic.ini",
    ".gitignore",
]


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
    for name in ROOT_FILES:
        path = root / name
        if path.exists():
            files.append(path)
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
        default=Path("dist/release/UEBench-source-0.1.0.zip"),
    )
    args = parser.parse_args()
    output = build_source_zip(args.output)
    print(f"wrote {output} files={len(zipfile.ZipFile(output).namelist())} bytes={output.stat().st_size}")


if __name__ == "__main__":
    main()
