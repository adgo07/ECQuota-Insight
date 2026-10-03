"""Build the same-origin payload manifest for the PyInstaller output (ECQ-RS05).

The portable ZIP and the installer must both be produced from **one** audited
``dist/UEBench`` tree.  This tool records, for every file in that tree:

* ``path``   - POSIX relative path below the payload root
* ``size``   - byte length
* ``sha256`` - content digest

and a single ``payload_tree_sha256`` over the sorted
``"{sha256}  {size}  {path}\\n"`` lines.

``tools/audit_release.py`` re-derives the same values from the shipped portable
ZIP, so a mismatch between the audited tree and the shipped archive fails the
Artifact Gate.  The digest algorithm must stay byte-identical in both files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

# Importable both as `python tools/<name>.py` (tools/ is sys.path[0]) and as
# `tools.<name>` from a test module.
try:
    from release_version import project_version
except ModuleNotFoundError:  # pragma: no cover - package-import style
    from tools.release_version import project_version

SCHEMA = "ecq.payload-manifest.v1"
DEFAULT_ROOT_NAME = "UEBench"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def payload_tree_sha256(entries: list[dict[str, Any]]) -> str:
    """Deterministic digest over (path, size, sha256) triples.

    Must stay byte-identical to ``tools/audit_release.py``.
    """
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item["path"]):
        digest.update(
            f"{entry['sha256']}  {entry['size']}  {entry['path']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def collect_entries(payload_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(payload_dir.rglob("*")):
        if not path.is_file():
            continue
        entries.append(
            {
                "path": path.relative_to(payload_dir).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_of(path),
            }
        )
    return entries


def build_manifest(
    payload_dir: Path,
    root_name: str = DEFAULT_ROOT_NAME,
    version: str | None = None,
) -> dict[str, Any]:
    if not payload_dir.is_dir():
        raise SystemExit(f"payload 目录不存在：{payload_dir}")
    entries = collect_entries(payload_dir)
    if not entries:
        raise SystemExit(f"payload 目录为空：{payload_dir}")
    return {
        "schema": SCHEMA,
        "version": version or project_version(),
        "root": root_name,
        "file_count": len(entries),
        "total_bytes": sum(entry["size"] for entry in entries),
        "payload_tree_sha256": payload_tree_sha256(entries),
        "files": entries,
    }


def write_manifest(manifest: dict[str, Any], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 UEBench payload 同源清单")
    parser.add_argument("--payload-dir", type=Path, default=Path("dist/UEBench"))
    parser.add_argument("--output", type=Path, default=Path("dist/release/payload-manifest.json"))
    parser.add_argument("--root-name", default=DEFAULT_ROOT_NAME)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    manifest = build_manifest(args.payload_dir, args.root_name)
    write_manifest(manifest, args.output)
    if not args.quiet:
        print(
            f"wrote {args.output} files={manifest['file_count']} "
            f"bytes={manifest['total_bytes']} tree={manifest['payload_tree_sha256']}"
        )


if __name__ == "__main__":
    main()
