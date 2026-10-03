"""Audit the user-facing release directory without modifying any project data.

ECQ-RS05 changed three things here:

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
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

# Importable both as `python tools/<name>.py` (tools/ is sys.path[0]) and as
# `tools.<name>` from a test module.
try:
    from release_version import ensure_utf8_console, artifact_names, project_version
except ModuleNotFoundError:  # pragma: no cover - package-import style
    from tools.release_version import ensure_utf8_console, artifact_names, project_version

#: Present in older delivery folders; deliberately not a correctness input.
LEGACY_FILES = ("统一标准规则确认表.xlsx",)

#: The unsigned-release declaration every Candidate build must carry.
REQUIRED_UNSIGNED_REASON = "no_signing_certificate"


def required_files(version: str | None = None) -> tuple[str, ...]:
    names = artifact_names(version or project_version())
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


def _audit_build_info(root: Path, build_info_name: str) -> dict[str, Any]:
    path = root / build_info_name
    if not path.exists():
        return {}
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"errors": [f"{build_info_name} 无法解析：{exc}"]}

    errors: list[str] = []
    if info.get("version") != project_version():
        errors.append(f"{build_info_name} 的版本与 pyproject.toml 不一致")
    if info.get("authenticode_signed") is not False:
        errors.append(f"{build_info_name} 必须声明 authenticode_signed = false")
    if info.get("unsigned_reason") != REQUIRED_UNSIGNED_REASON:
        errors.append(
            f"{build_info_name} 必须声明 unsigned_reason = {REQUIRED_UNSIGNED_REASON}"
        )
    return {
        "version": info.get("version"),
        "authenticode_signed": info.get("authenticode_signed"),
        "unsigned_reason": info.get("unsigned_reason"),
        "built_at": info.get("built_at"),
        "errors": errors,
    }


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


def audit_release(root: Path, version: str | None = None) -> dict[str, Any]:
    resolved = version or project_version()
    names = artifact_names(resolved)
    errors: list[str] = []

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
    for name in required_files(resolved):
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

    build_info_report = _audit_build_info(root, names["build_info"])
    errors.extend(build_info_report.get("errors", []))

    package_report, package_errors = _audit_standard_package(root / names["standard_package"])
    errors.extend(package_errors)

    # Legacy reference material: reported, never a PASS condition.
    legacy_present = [name for name in LEGACY_FILES if (root / name).exists()]

    return {
        "valid": not errors,
        "version": resolved,
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
