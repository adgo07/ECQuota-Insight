"""Write ``release-build-info.json``, the embedded ``build-identity.json`` and
the ``ACTIVE-CANDIDATE.json`` marker.

ECQ-RS05 needs three different documents, and the differences are deliberate.

1. **The release-directory provenance document** (``release-build-info.json``,
   next to the shipped artifacts).  It carries the full provenance record --
   ``product_version``, ``candidate_id``, ``source_commit``/``source_dirty``,
   the standard-package identity, ``payload_tree_sha256`` and
   ``build_time_utc`` -- on top of the earlier unsigned-release declaration.
   ``tools/audit_release.py`` and the CI Artifact Gate verify it.

2. **The embedded build identity** (``build-identity.json``, written *inside*
   the built payload at ``<payload>/_internal/uebench/resources/``).  The
   in-app 诊断信息 view reads it, so a user can tell exactly which commit a
   running copy came from.

The embedded document must **not** contain ``payload_tree_sha256``: that digest
describes the payload tree, and a file cannot describe the tree it is part of
without the value depending on itself.  It is written *before*
``tools/build_payload_manifest.py`` runs, so the payload manifest covers and
hashes it like any other payload file.

3. **The ACTIVE Candidate marker** (``ACTIVE-CANDIDATE.json`` in the assembled
   release directory).  Several Candidates may be built over time; this file
   states which one a directory currently holds, so a tester cannot mistake a
   stale payload for the current one.  It is written only after the files are
   assembled -- ``scripts/build_candidate.ps1`` writes it and then lets its
   Artifact Gate validate it (removing it again if the gate fails), while
   ``scripts/sync_release.ps1`` writes it after its audit -- and it is
   deliberately not part of ``SHA256SUMS.txt``: a document naming the assembly
   cannot be one of the files it pins.

The 0.2.0 Candidate is shipped **unsigned**: there is no code-signing
certificate available.  That fact is a property of the artifact, so it is
recorded in machine-readable form rather than left implicit:

* ``authenticode_signed``  = ``false``
* ``unsigned_reason``      = ``no_signing_certificate``

This is deliberately distinct from the ``.uebench`` standard package's own
Ed25519 signature (see ``src/uebench/infrastructure/packages.py``): that
signature authenticates standard-package content and is verified at install
time, whereas Authenticode would authenticate the Windows PE binaries.  Do not
conflate the two.

Environment values below are **diagnostic only**.  A change in Python version,
dependency lock hash or calculator version must never by itself invalidate the
RS04 Product Golden; the Golden exists precisely to prove that a new build
environment preserves the same business semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Importable both as `python tools/<name>.py` (tools/ is sys.path[0]) and as
# `tools.<name>` from a test module.
try:
    from release_version import (
        ensure_utf8_console,
        project_version,
        resolve_candidate_id,
    )
except ModuleNotFoundError:  # pragma: no cover - package-import style
    from tools.release_version import (
        ensure_utf8_console,
        project_version,
        resolve_candidate_id,
    )

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ecq.release-build-info.v1"
IDENTITY_SCHEMA = "ecq.build-identity.v1"
ACTIVE_SCHEMA = "ecq.active-candidate.v1"
UNSIGNED_REASON = "no_signing_certificate"
SMART_SCREEN_NOTE = (
    "本发布物未进行 Authenticode 代码签名（无可用签名证书）。Windows 可能显示"
    "“未知发布者”或 SmartScreen 提示；在企业环境中，应用控制/白名单策略可能"
    "阻止未签名程序运行。安装前请用 SHA256SUMS.txt 核对文件哈希。"
)

#: Contract path of the embedded identity, relative to the PyInstaller payload
#: root (``dist/UEBench``).  A UI workstream reads this exact file; do not move
#: it and do not rename its keys.
EMBEDDED_IDENTITY_RELATIVE_PATH = Path("_internal/uebench/resources/build-identity.json")

#: Keys the release-directory build info must always carry.  The audit and the
#: CI provenance check both rely on them.
REQUIRED_BUILD_INFO_KEYS: tuple[str, ...] = (
    "product_version",
    "candidate_id",
    "source_commit",
    "source_dirty",
    "standard_package_id",
    "standard_data_version",
    "standard_package_sha256",
    "payload_tree_sha256",
    "build_time_utc",
)

#: The embedded identity: the same provenance minus ``payload_tree_sha256``.
IDENTITY_KEYS: tuple[str, ...] = (
    "product_version",
    "candidate_id",
    "source_commit",
    "source_dirty",
    "standard_package_id",
    "standard_data_version",
    "standard_package_sha256",
    "build_time_utc",
)

#: Name of the marker that declares **which** Candidate a directory holds.
#: ``ACTIVE-CANDIDATE.json`` is release-directory metadata, never payload
#: content: it is written after the assembly (and after its audit) and is
#: deliberately not listed in ``SHA256SUMS.txt``, because a document that names
#: the assembly cannot be part of what it describes.
ACTIVE_MARKER_NAME = "ACTIVE-CANDIDATE.json"

SOURCE_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_of(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------
# git provenance
# --------------------------------------------------------------------------


def _run_git(root: Path | None, *args: str) -> str | None:
    """Run git in ``root``; return stdout, or ``None`` when git cannot answer."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(root or ROOT), *args],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except Exception:  # pragma: no cover - git missing / not a repository
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def source_commit(root: Path | None = None) -> str | None:
    """Full 40-hex SHA of the checked-out commit, or ``None`` if unknowable."""
    output = _run_git(root, "rev-parse", "HEAD")
    if output is None:
        return None
    candidate = output.strip().splitlines()[0].strip() if output.strip() else ""
    return candidate if SOURCE_COMMIT_RE.match(candidate) else None


def source_dirty(root: Path | None = None) -> bool:
    """``True`` when the working tree differs from the commit.

    ``git status --porcelain`` already applies ``.gitignore``, so build outputs
    the project ignores do not make a tree dirty.  Anything it reports --
    including an untracked file -- does.  When git cannot answer at all the tree
    is treated as dirty: a build that cannot prove its own provenance must not
    be able to claim a clean one.
    """
    output = _run_git(root, "status", "--porcelain")
    if output is None:
        return True
    return bool(output.strip())


def git_provenance(root: Path | None = None) -> tuple[str | None, bool]:
    base = root or ROOT
    return source_commit(base), source_dirty(base)


# --------------------------------------------------------------------------
# diagnostic blocks
# --------------------------------------------------------------------------


def _os_details() -> dict[str, str]:
    details = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "release": platform.release(),
        "version": platform.version(),
    }
    if sys.platform == "win32":
        try:
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_OperatingSystem).Caption + '|' + "
                    "(Get-CimInstance Win32_OperatingSystem).BuildNumber",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            caption, _, build = completed.stdout.strip().partition("|")
            details["caption"] = caption.strip()
            details["build"] = build.strip()
        except Exception:
            pass
    return details


def _lock_hash() -> str | None:
    return sha256_of(ROOT / "requirements.lock")


def _standard_package_info(names: dict[str, str]) -> dict[str, Any]:
    pinned = ROOT / "release" / "standard-packages" / names["standard_package"]
    info: dict[str, Any] = {
        "path": str(pinned.relative_to(ROOT)) if pinned.exists() else None,
        "sha256": sha256_of(pinned),
        "size": pinned.stat().st_size if pinned.exists() else None,
    }
    if pinned.is_file():
        try:
            import zipfile

            with zipfile.ZipFile(pinned) as archive:
                manifest = json.loads(archive.read("manifest.json"))
            info["data_version"] = manifest.get("data_version")
            info["package_id"] = manifest.get("package_id")
            info["standard_count"] = manifest.get("standard_count")
            info["rule_count"] = manifest.get("rule_count")
            info["signature_algorithm"] = "ed25519"
        except Exception as exc:  # pragma: no cover - defensive
            info["error"] = str(exc)
    return info


def _golden_info() -> dict[str, Any]:
    """Record the RS04 Golden identity this Candidate was verified against."""
    path = ROOT / "tests" / "golden" / "gb29446_product_golden_v1.json"
    if not path.is_file():
        return {}
    golden = json.loads(path.read_text(encoding="utf-8"))
    return {
        "golden_id": golden.get("golden_id"),
        "golden_version": golden.get("golden_version"),
        "standard_id": golden.get("standard_id"),
        "rule_revision": golden.get("rule_revision"),
        "standard_source_sha256": golden.get("standard_source_sha256"),
    }


def payload_manifest_tree_sha256(path: Path) -> str | None:
    """Read ``payload_tree_sha256`` out of a payload manifest (``None`` if absent)."""
    if not path.is_file():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    value = manifest.get("payload_tree_sha256")
    return value if isinstance(value, str) else None


# --------------------------------------------------------------------------
# documents
# --------------------------------------------------------------------------


def build_info(
    names: dict[str, str],
    *,
    built_at: str | None = None,
    candidate_id: str | None = None,
    commit: str | None = None,
    dirty: bool | None = None,
    payload_tree_sha256: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """The release-directory provenance document.

    ``commit``/``dirty`` are the values the build script already resolved; when
    they are omitted git is asked directly.  ``payload_tree_sha256`` comes from
    the payload manifest that describes the shipped payload tree.
    """
    base = root or ROOT
    version = project_version(base / "pyproject.toml")
    if commit is None or dirty is None:
        git_commit, git_dirty = git_provenance(base)
        commit = git_commit if commit is None else commit
        dirty = git_dirty if dirty is None else dirty
    timestamp = built_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    package = _standard_package_info(names)

    info: dict[str, Any] = {
        "schema": SCHEMA,
        "version": version,
        "built_at": timestamp,
        # --- Candidate provenance (ECQ-RS05) -------------------------------
        "product_version": version,
        "candidate_id": candidate_id,
        "source_commit": commit,
        "source_dirty": bool(dirty),
        "standard_package_id": package.get("package_id"),
        "standard_data_version": package.get("data_version"),
        "standard_package_sha256": package.get("sha256"),
        "payload_tree_sha256": payload_tree_sha256,
        "build_time_utc": timestamp,
        # --- Unsigned-release declaration (ECQ-RS05 §16) --------------------
        "authenticode_signed": False,
        "unsigned_reason": UNSIGNED_REASON,
        "smart_screen_note": SMART_SCREEN_NOTE,
        # --- Diagnostics only - never a Golden skip condition ---------------
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "requirements_lock_sha256": _lock_hash(),
        "os": _os_details(),
        "standard_package": package,
        "golden": _golden_info(),
        "standard_package_signature_note": (
            ".uebench 标准包使用 Ed25519 内容签名，安装时校验；这与 Windows "
            "Authenticode 代码签名是两件事，不要混淆。"
        ),
    }
    return info


def build_identity(info: dict[str, Any]) -> dict[str, Any]:
    """Project the full build info onto the embedded identity document.

    ``payload_tree_sha256`` is excluded on purpose: it describes the payload
    tree that will contain this very file.
    """
    identity: dict[str, Any] = {"schema": IDENTITY_SCHEMA}
    for key in IDENTITY_KEYS:
        identity[key] = info.get(key)
    return identity


def identity_path_for_payload(payload_dir: Path) -> Path:
    """The contract location of the embedded identity inside a built payload."""
    return payload_dir / EMBEDDED_IDENTITY_RELATIVE_PATH


def active_candidate_document(info: dict[str, Any]) -> dict[str, Any]:
    """The ``ACTIVE-CANDIDATE.json`` document for an assembled Candidate.

    Its ``payload_tree_sha256`` is the manifest's own value (both are read from
    the same ``build_info`` mapping), so the marker can never disagree with
    ``payload-manifest.json`` about which payload tree is ACTIVE.
    """
    return {
        "schema": ACTIVE_SCHEMA,
        "status": "ACTIVE",
        "candidate_id": info.get("candidate_id"),
        "product_version": info.get("product_version"),
        "source_commit": info.get("source_commit"),
        "source_dirty": info.get("source_dirty"),
        "standard_package_id": info.get("standard_package_id"),
        "standard_data_version": info.get("standard_data_version"),
        "standard_package_sha256": info.get("standard_package_sha256"),
        "payload_tree_sha256": info.get("payload_tree_sha256"),
        "assembled_at_utc": info.get("build_time_utc"),
    }


def _active_marker_problems(marker: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if not SOURCE_COMMIT_RE.match(str(marker.get("source_commit") or "")):
        problems.append("source_commit 不是 40 位小写十六进制")
    if not SHA256_RE.match(str(marker.get("standard_package_sha256") or "")):
        problems.append("standard_package_sha256 不是 64 位小写十六进制")
    if not SHA256_RE.match(str(marker.get("payload_tree_sha256") or "")):
        problems.append(
            "payload_tree_sha256 不是 64 位小写十六进制（必须来自本次 payload-manifest.json）"
        )
    if marker.get("source_dirty") is not False:
        problems.append("source_dirty 必须为 false，正式候选只能声明干净构建")
    return problems


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def _identity_is_traceable(identity: dict[str, Any]) -> list[str]:
    """Problems that make an embedded identity useless for traceability."""
    problems: list[str] = []
    if not identity.get("product_version"):
        problems.append("product_version 为空")
    if not identity.get("candidate_id"):
        problems.append("candidate_id 为空（必须由 --source-commit/--candidate-id 提供）")
    if not SOURCE_COMMIT_RE.match(str(identity.get("source_commit") or "")):
        problems.append("source_commit 不是 40 位小写十六进制")
    if not SHA256_RE.match(str(identity.get("standard_package_sha256") or "")):
        problems.append("standard_package_sha256 不是 64 位小写十六进制")
    return problems


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_console()
    parser = argparse.ArgumentParser(
        description="生成 Candidate 构建信息（完整溯源 + 内嵌 build-identity.json）"
    )
    parser.add_argument(
        "--names", required=True, help="tools/release_version.py --names 的 JSON"
    )
    parser.add_argument("--output", type=Path, default=None, help="release-build-info.json 路径")
    parser.add_argument(
        "--payload-dir",
        type=Path,
        default=None,
        help="PyInstaller 载荷目录（dist/UEBench）；据此写入内嵌 build-identity.json",
    )
    parser.add_argument(
        "--identity-output",
        type=Path,
        default=None,
        help="内嵌 build-identity.json 的显式路径（默认由 --payload-dir 决定）",
    )
    parser.add_argument(
        "--active-marker",
        type=Path,
        default=None,
        help=f"ACTIVE-CANDIDATE.json（{ACTIVE_MARKER_NAME}）写入路径；仅用于已装配完成的候选目录",
    )
    parser.add_argument(
        "--payload-manifest",
        type=Path,
        default=None,
        help="payload-manifest.json 路径；用于记录 payload_tree_sha256",
    )
    parser.add_argument("--candidate-id", default=None, help="候选标识 rc-<7位提交前缀>")
    parser.add_argument("--source-commit", default=None, help="源提交 SHA（40 位十六进制）")
    parser.add_argument("--built-at", default=None, help="构建时间（UTC，默认当前时间）")
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="工作区有未提交改动时拒绝生成（正式候选构建必须使用）",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="仅用于本地实验：允许脏工作区，并如实记录 source_dirty = true",
    )
    args = parser.parse_args(argv)

    if (
        args.output is None
        and args.identity_output is None
        and args.payload_dir is None
        and args.active_marker is None
    ):
        print(
            "必须至少指定 --output、--payload-dir/--identity-output 或 --active-marker。",
            file=sys.stderr,
        )
        return 2

    names = json.loads(args.names)
    for key in ("standard_package", "payload_manifest", "build_info"):
        if key not in names:
            print(f"产物文件名清单缺少 {key}。", file=sys.stderr)
            return 2

    try:
        candidate = resolve_candidate_id(args.candidate_id, args.source_commit)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    commit = args.source_commit or source_commit()
    if commit is not None:
        commit = commit.strip().lower()
    dirty = source_dirty()

    if dirty and args.require_clean and not args.allow_dirty:
        print(
            "工作区存在未提交改动（source_dirty = true）。正式候选构建必须来自干净检出；"
            "请提交或清理改动，或在本地实验时显式使用 --allow-dirty。",
            file=sys.stderr,
        )
        return 1

    manifest_path = args.payload_manifest
    if manifest_path is None and args.output is not None:
        default_manifest = args.output.parent / names["payload_manifest"]
        if default_manifest.is_file():
            manifest_path = default_manifest
    tree_sha256 = (
        payload_manifest_tree_sha256(manifest_path) if manifest_path is not None else None
    )

    timestamp = args.built_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    info = build_info(
        names,
        built_at=timestamp,
        candidate_id=candidate,
        commit=commit,
        dirty=dirty,
        payload_tree_sha256=tree_sha256,
    )

    if args.output is not None and tree_sha256 is None:
        # The Artifact Gate requires payload_tree_sha256 to equal the payload
        # manifest's value, so a document written without it is unauditable.
        # The build scripts always pass --payload-manifest; this is a loud
        # warning for ad-hoc/diagnostic runs (which the console gate also
        # exercises) rather than a failure, because audit_release is the gate
        # that decides whether such a directory may ship.
        print(
            "警告：未取得 payload_tree_sha256。请用 --payload-manifest 指向本次构建的 "
            "payload-manifest.json（它必须先于 release-build-info.json 生成）；"
            "否则该目录无法通过 audit_release。",
            file=sys.stderr,
        )

    if args.output is not None:
        write_json(args.output, info)
        print(f"wrote {args.output}")

    identity_target = args.identity_output
    if identity_target is None and args.payload_dir is not None:
        identity_target = identity_path_for_payload(args.payload_dir)
    if identity_target is not None:
        identity = build_identity(info)
        # A payload that cannot be traced back to an exact commit is worse than
        # a failed build: refuse instead of embedding a hollow identity.
        problems = _identity_is_traceable(identity)
        if problems:
            print(
                "内嵌构建标识不完整，拒绝写入："
                + "；".join(problems)
                + "。请提供 --source-commit 与 --candidate-id。",
                file=sys.stderr,
            )
            return 1
        write_json(identity_target, identity)
        print(f"wrote {identity_target}")

    if args.active_marker is not None:
        marker = active_candidate_document(info)
        # Claiming ACTIVE means "this is the one Candidate directory that is
        # current".  It must not be possible to claim that from a dirty tree or
        # without the payload digest the marker is supposed to pin.
        problems = _active_marker_problems(marker)
        if problems:
            print(
                f"拒绝写入 {ACTIVE_MARKER_NAME}（ACTIVE 候选声明不完整）："
                + "；".join(problems),
                file=sys.stderr,
            )
            return 1
        write_json(args.active_marker, marker)
        print(f"wrote {args.active_marker}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
