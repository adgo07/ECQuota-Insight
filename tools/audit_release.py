"""Audit the user-facing release directory without modifying any project data.

ECQ-RS05 changed four things here:

1. **No hard-coded version.**  Required artifact names come from
   ``tools/release_version.py``, which reads ``pyproject.toml``.
2. **The 统一标准规则确认表.xlsx is no longer a release input.**  It is
   downgraded to ``LEGACY_REFERENCE_ONLY``: it is not a correctness basis for
   the 0.2.0 product or the standard package, not a PASS condition here, not
   installer content, and its "同意发布" column must never be read as proof that
   the other 46 standards were formally verified.  If the file is present it is
   reported as legacy information only and never fails the audit.
3. **Same-origin payload verification.**  ``payload-manifest.json`` records
   ``sha256``/``size`` for every file of the PyInstaller payload plus a
   ``payload_tree_sha256``.  The audit re-derives those from the portable ZIP,
   which proves the ZIP really is a faithful copy of the audited payload tree.
4. **Candidate provenance.**  ``release-build-info.json`` must carry the
   Candidate identity, the exact 40-hex source commit, ``source_dirty=false``,
   the standard-package identity and the **same** ``payload_tree_sha256`` as the
   payload manifest.  The audited directory's Candidate identity is read from
   that document, so a Candidate release directory is audited under its own
   Candidate file names instead of being compared against formal-release names.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

# Importable both as `python tools/<name>.py` (tools/ is sys.path[0]) and as
# `tools.<name>` from a test module.
try:
    from release_version import (
        CANDIDATE_ID_RE,
        artifact_names,
        ensure_utf8_console,
        project_version,
    )
except ModuleNotFoundError:  # pragma: no cover - package-import style
    from tools.release_version import (
        CANDIDATE_ID_RE,
        artifact_names,
        ensure_utf8_console,
        project_version,
    )

#: Present in older delivery folders; deliberately not a correctness input.
LEGACY_FILES = ("统一标准规则确认表.xlsx",)

#: The unsigned-release declaration every Candidate build must carry.
REQUIRED_UNSIGNED_REASON = "no_signing_certificate"

#: Provenance fields ``release-build-info.json`` must carry (ECQ-RS05).
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

#: ``source_commit`` must be a full, lowercase, unambiguous commit id.
SOURCE_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def release_candidate_id(root: Path, build_info_name: str) -> str | None:
    """Candidate identity declared by the directory itself (``None`` = formal).

    Reading it from ``release-build-info.json`` is what lets one audit code path
    cover both a formal release cut (no identity) and a Candidate (suffixed
    names) without either hard-coding the other's file names.
    """
    path = root / build_info_name
    if not path.is_file():
        return None
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    value = info.get("candidate_id") if isinstance(info, dict) else None
    if isinstance(value, str) and CANDIDATE_ID_RE.match(value.strip().lower()):
        return value.strip().lower()
    return None


def required_files(
    version: str | None = None, candidate_id: str | None = None
) -> tuple[str, ...]:
    names = artifact_names(version or project_version(), candidate_id)
    return (
        names["portable"],
        names["installer"],
        names["source"],
        names["standard_package"],
        names["template"],
        names["sha256sums"],
        names["payload_manifest"],
        names["build_info"],
        names["helper_ps1"],
        names["helper_cmd"],
        names["release_notes"],
        names["delivery_list"],
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def payload_tree_sha256(entries: list[dict[str, Any]]) -> str:
    """Deterministic digest over the manifest's (path, size, sha256) triples.

    Must stay byte-identical to ``tools/build_payload_manifest.py``.
    """
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item["path"]):
        digest.update(
            f"{entry['sha256']}  {entry['size']}  {entry['path']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def _audit_payload_manifest(root: Path, manifest_name: str, portable_name: str) -> dict[str, Any]:
    """Verify the portable ZIP against the payload manifest (same-origin proof)."""
    manifest_path = root / manifest_name
    portable_path = root / portable_name
    if not manifest_path.exists() or not portable_path.exists():
        return {}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"errors": [f"{manifest_name} 无法解析：{exc}"]}

    errors: list[str] = []
    entries = manifest.get("files") or []
    root_prefix = (manifest.get("root") or "UEBench").rstrip("/") + "/"
    recomputed = payload_tree_sha256(entries)
    report: dict[str, Any] = {
        "schema": manifest.get("schema"),
        "version": manifest.get("version"),
        "root": manifest.get("root"),
        "file_count": manifest.get("file_count"),
        "recorded_tree_sha256": manifest.get("payload_tree_sha256"),
        "recomputed_tree_sha256": recomputed,
        "matches_zip": None,
    }
    if manifest.get("file_count") != len(entries):
        errors.append(f"{manifest_name} 的 file_count 与 files 数量不一致")
    if manifest.get("payload_tree_sha256") != recomputed:
        errors.append(f"{manifest_name} 的 payload_tree_sha256 与自身条目不一致")
    if manifest.get("version") != project_version():
        errors.append(f"{manifest_name} 的版本与 pyproject.toml 不一致")

    expected = {entry["path"]: entry for entry in entries}
    mismatched: list[str] = []
    extra: list[str] = []
    with zipfile.ZipFile(portable_path) as archive:
        present: set[str] = set()
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if not name.startswith(root_prefix):
                continue
            relative = name[len(root_prefix):]
            present.add(relative)
            entry = expected.get(relative)
            if entry is None:
                extra.append(relative)
                continue
            digest = hashlib.sha256(archive.read(name)).hexdigest()
            if digest != entry["sha256"] or info.file_size != entry["size"]:
                mismatched.append(relative)
        missing = sorted(set(expected) - present)

    report["matches_zip"] = not (mismatched or missing or extra)
    if missing:
        errors.append(f"便携包缺少 payload 清单中的文件：{missing[:5]}（共 {len(missing)}）")
    if extra:
        errors.append(f"便携包含 payload 清单之外的 UEBench 文件：{extra[:5]}（共 {len(extra)}）")
    if mismatched:
        errors.append(
            f"便携包文件与 payload 清单哈希/大小不一致：{mismatched[:5]}（共 {len(mismatched)}）"
        )
    report["errors"] = errors
    return report


def _audit_build_info(
    root: Path, build_info_name: str, names: dict[str, str]
) -> dict[str, Any]:
    """Verify the Candidate provenance document (ECQ-RS05)."""
    path = root / build_info_name
    if not path.exists():
        return {}
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"errors": [f"{build_info_name} 无法解析：{exc}"]}
    if not isinstance(info, dict):
        return {"errors": [f"{build_info_name} 顶层必须是 JSON 对象"]}

    version = project_version()
    errors: list[str] = []

    missing = [key for key in REQUIRED_BUILD_INFO_KEYS if key not in info]
    if missing:
        errors.append(
            f"{build_info_name} 缺少必备溯源字段：{missing}；"
            "候选构建必须记录产品版本、候选标识、源提交、标准包身份与 payload 树哈希"
        )

    if info.get("version") != version:
        errors.append(f"{build_info_name} 的版本与 pyproject.toml 不一致")
    if info.get("product_version") != version:
        errors.append(
            f"{build_info_name} 的 product_version 必须是 {version}（与 pyproject.toml 一致）"
        )

    candidate = info.get("candidate_id")
    if candidate is not None and (
        not isinstance(candidate, str) or not CANDIDATE_ID_RE.match(candidate)
    ):
        errors.append(
            f"{build_info_name} 的 candidate_id 非法：{candidate!r}；"
            "应为 rc-<7位十六进制提交前缀> 或 null（正式发布）"
        )

    if info.get("authenticode_signed") is not False:
        errors.append(f"{build_info_name} 必须声明 authenticode_signed = false")
    if info.get("unsigned_reason") != REQUIRED_UNSIGNED_REASON:
        errors.append(
            f"{build_info_name} 必须声明 unsigned_reason = {REQUIRED_UNSIGNED_REASON}"
        )

    # --- source identity ----------------------------------------------------
    commit = info.get("source_commit")
    if not isinstance(commit, str) or not SOURCE_COMMIT_RE.match(commit):
        errors.append(
            f"{build_info_name} 的 source_commit 必须是 40 位小写十六进制提交号，"
            f"实际：{commit!r}"
        )
    if info.get("source_dirty") is not False:
        errors.append(
            f"{build_info_name} 必须声明 source_dirty = false；"
            "正式候选构建只能来自干净检出"
        )

    # --- standard package identity -----------------------------------------
    for key in ("standard_package_id", "standard_data_version"):
        value = info.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{build_info_name} 的 {key} 必须是非空字符串，实际：{value!r}")
    package_sha256 = info.get("standard_package_sha256")
    if not isinstance(package_sha256, str) or not SHA256_RE.match(package_sha256):
        errors.append(
            f"{build_info_name} 的 standard_package_sha256 必须是 64 位小写十六进制，"
            f"实际：{package_sha256!r}"
        )
    else:
        shipped = root / names["standard_package"]
        if shipped.is_file():
            actual = sha256(shipped)
            if actual != package_sha256:
                errors.append(
                    f"{build_info_name} 的 standard_package_sha256 与交付目录中的 "
                    f"{names['standard_package']} 不一致：{package_sha256} != {actual}"
                )

    # --- payload tree digest (must agree with the payload manifest) ---------
    tree_sha256 = info.get("payload_tree_sha256")
    if not isinstance(tree_sha256, str) or not SHA256_RE.match(tree_sha256):
        errors.append(
            f"{build_info_name} 的 payload_tree_sha256 必须是 64 位小写十六进制，"
            f"实际：{tree_sha256!r}"
        )
    else:
        recorded = _manifest_tree_sha256(root / names["payload_manifest"])
        if recorded is None:
            errors.append(
                f"无法从 {names['payload_manifest']} 取得 payload_tree_sha256，"
                f"无法核对 {build_info_name}"
            )
        elif recorded != tree_sha256:
            errors.append(
                f"{build_info_name} 的 payload_tree_sha256 与 {names['payload_manifest']} "
                f"不一致：{tree_sha256} != {recorded}"
            )

    build_time = info.get("build_time_utc")
    if not isinstance(build_time, str) or not build_time.strip():
        errors.append(f"{build_info_name} 的 build_time_utc 必须是非空字符串")

    return {
        "version": info.get("version"),
        "product_version": info.get("product_version"),
        "candidate_id": candidate,
        "source_commit": commit,
        "source_dirty": info.get("source_dirty"),
        "standard_package_id": info.get("standard_package_id"),
        "standard_data_version": info.get("standard_data_version"),
        "standard_package_sha256": package_sha256,
        "payload_tree_sha256": tree_sha256,
        "build_time_utc": build_time,
        "authenticode_signed": info.get("authenticode_signed"),
        "unsigned_reason": info.get("unsigned_reason"),
        "built_at": info.get("built_at"),
        "errors": errors,
    }


def _manifest_tree_sha256(manifest_path: Path) -> str | None:
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    value = manifest.get("payload_tree_sha256") if isinstance(manifest, dict) else None
    return value if isinstance(value, str) else None


def _audit_standard_package(package: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    report: dict[str, Any] = {}
    if not package.exists():
        return report, errors
    try:
        with zipfile.ZipFile(package) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            definitions = [
                json.loads(archive.read(name))
                for name in archive.namelist()
                if name.startswith("definitions/") and name.endswith(".json")
            ]
        current = [d for d in definitions if d.get("lifecycle_status", "active") != "obsolete"]
        history = [d for d in definitions if d.get("lifecycle_status") == "obsolete"]
        expected_current_rules = sum(
            len(product.get("indicators", []))
            for definition in current
            for product in definition.get("products", [])
        )
        report = {
            "standard_count": manifest.get("standard_count"),
            "rule_count": manifest.get("rule_count"),
            "data_version": manifest.get("data_version"),
            "current_standard_count": len(current),
            "historical_standard_count": len(history),
            "current_rule_count": expected_current_rules,
        }
        if not isinstance(manifest.get("standard_count"), int) or not isinstance(
            manifest.get("rule_count"), int
        ):
            errors.append("正式标准包清单缺少有效的标准数量或规则数量")
    except Exception as exc:
        errors.append(f"标准包无法读取：{exc}")
    return report, errors


def audit_release(
    root: Path, version: str | None = None, candidate_id: str | None = None
) -> dict[str, Any]:
    resolved = version or project_version()
    formal_names = artifact_names(resolved)
    errors: list[str] = []

    if candidate_id is None:
        # The directory declares its own identity; a Candidate release
        # directory is therefore audited under its Candidate file names.
        candidate_id = release_candidate_id(root, formal_names["build_info"])
    if candidate_id is not None and not CANDIDATE_ID_RE.match(candidate_id):
        errors.append(
            f"候选标识非法：{candidate_id!r}；应为 rc-<7位十六进制提交前缀>"
        )
        candidate_id = None
    names = artifact_names(resolved, candidate_id)

    hashes_path = root / names["sha256sums"]
    expected_hashes: dict[str, str] = {}
    if not hashes_path.exists():
        errors.append(f"缺少 {names['sha256sums']}")
    else:
        for line_number, line in enumerate(
            hashes_path.read_text(encoding="utf-8-sig").splitlines(), start=1
        ):
            parts = line.split()
            if len(parts) != 2:
                errors.append(f"{names['sha256sums']} 第{line_number}行格式错误")
                continue
            expected_hashes[parts[1]] = parts[0].lower()

    file_report: dict[str, dict[str, Any]] = {}
    sums_name = names["sha256sums"]
    for name in required_files(resolved, candidate_id):
        path = root / name
        exists = path.exists()
        actual = sha256(path) if exists else None
        if name == sums_name:
            # A checksum file cannot contain its own digest, so it must exist but
            # is never expected to appear inside itself.
            file_report[name] = {"exists": exists, "sha256": actual, "matches": None}
            if not exists:
                errors.append(f"缺少交付文件：{name}")
            continue
        expected = expected_hashes.get(name)
        file_report[name] = {
            "exists": exists,
            "sha256": actual,
            "matches": bool(exists and actual == expected),
        }
        if not exists:
            errors.append(f"缺少交付文件：{name}")
        elif expected is None:
            errors.append(f"{sums_name} 未登记：{name}")
        elif actual != expected:
            errors.append(f"文件哈希不匹配：{name}")

    payload_report = _audit_payload_manifest(root, names["payload_manifest"], names["portable"])
    errors.extend(payload_report.get("errors", []))

    build_info_report = _audit_build_info(root, names["build_info"], names)
    errors.extend(build_info_report.get("errors", []))

    package_report, package_errors = _audit_standard_package(root / names["standard_package"])
    errors.extend(package_errors)

    # Legacy reference material: reported, never a PASS condition.
    legacy_present = [name for name in LEGACY_FILES if (root / name).exists()]

    return {
        "valid": not errors,
        "version": resolved,
        "candidate_id": candidate_id,
        "release_dir": str(root),
        "files": file_report,
        "payload": payload_report,
        "build_info": build_info_report,
        "published_package": package_report,
        "legacy_reference_only": {
            "files_present": legacy_present,
            "correctness_basis": False,
            "note": (
                "统一标准规则确认表.xlsx 为 LEGACY_REFERENCE_ONLY：不作为 0.2.0 发布正确性依据、"
                "不作为正式标准包正确性依据、不是本审计的 PASS 条件、不随普通用户 release 交付，"
                "其“同意发布”也不代表其余 46 个标准已正式验证。"
            ),
        },
        "errors": errors,
    }


def main() -> None:
    ensure_utf8_console()
    parser = argparse.ArgumentParser(description="审计UEBench最终交付目录，不修改任何数据")
    parser.add_argument("release_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_release(args.release_dir.resolve())
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.output.resolve().write_text(payload + "\n", encoding="utf-8")
    if not report["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
