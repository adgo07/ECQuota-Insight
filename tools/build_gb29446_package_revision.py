"""Produce a new SIGNED full standard package from a signed parent baseline.

ECQ-RS05, approved option B.

The parent baseline is the published, Ed25519-signed
``2026.09-published.2`` package.  Its GB 29446—2019 definition is a pre-RS01
revision (``rule_revision=1``, no ``coal_type`` selection schema), which is why
the RS04 Product Golden cannot be replayed against an installed Candidate.

This tool rewrites **exactly one** member of that package — the GB 29446
definition, replaced by the current repository definition (``rule_revision=2``)
— re-signs the manifest, and leaves **every other member byte-identical**.

It deliberately does NOT go through ``StandardPackageBuilder.build()``: that
method re-serialises every definition through the current pydantic model, which
could silently change the bytes of the other 46 standards.  Here the untouched
members are copied verbatim from the parent archive, and
:func:`verify_revision_package` re-reads both archives and refuses to accept the
result unless every non-GB29446 member matches byte-for-byte.

It also never consults ``统一标准规则确认表.xlsx`` (LEGACY_REFERENCE_ONLY): no
rule content is regenerated from it.

Note on lineage: ``PackageManifest.validate_lineage`` forbids
``parent_package_id`` when ``package_mode == "full"``, so the parent relationship
cannot be recorded inside a full package's manifest.  It is recorded in
``release/standard-packages/PIN.json`` instead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# Importable both as ``python tools/<name>.py`` and as ``tools.<name>``.
try:
    from release_version import ensure_utf8_console
except ModuleNotFoundError:  # pragma: no cover - package-import style
    from tools.release_version import ensure_utf8_console

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from uebench.domain.models import StandardDefinition  # noqa: E402
from uebench.infrastructure.packages import (  # noqa: E402
    PackageFile,
    PackageManifest,
    _canonical_json,  # noqa: PLC2701 - exact byte-compatibility is the point
    _sha256_bytes,  # noqa: PLC2701
)

TARGET_STANDARD_ID = "gb-29446-2019"
GHOST_MEMBER = "signature.ed25519"


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_package(path: Path) -> tuple[bytes, dict[str, bytes]]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise SystemExit(f"标准包包含重复成员：{path}")
        manifest_bytes = archive.read("manifest.json")
        members = {name: archive.read(name) for name in names}
    return manifest_bytes, members


def _definition_kind(path: str, manifest: PackageManifest) -> bool:
    return any(entry.kind == "definition" and entry.path == path for entry in manifest.files)


def canonical_definition_payload(definition: StandardDefinition) -> bytes:
    """Canonical payload the application will compare against.

    Matches ``_definition_matches`` in ``uebench.infrastructure.packages`` so a
    freshly installed revision is recognised as identical on re-install.
    """
    return _canonical_json(definition.model_dump(mode="json"))


def build_revision_package(
    parent: Path,
    definition_path: Path,
    private_key_path: Path,
    output: Path,
    *,
    data_version: str,
    minimum_app_version: str,
    package_id: str | None = None,
    issued_at: datetime | None = None,
) -> dict:
    parent = parent.resolve()
    output = output.resolve()
    if parent == output:
        raise SystemExit("输出路径不能覆盖父基线标准包")

    manifest_bytes, members = _read_package(parent)
    parent_manifest = PackageManifest.model_validate_json(manifest_bytes)
    if parent_manifest.package_mode != "full":
        raise SystemExit(f"父基线必须是完整包，实际为 {parent_manifest.package_mode}")

    definition = StandardDefinition.model_validate_json(
        Path(definition_path).read_text(encoding="utf-8")
    )
    if definition.id != TARGET_STANDARD_ID:
        raise SystemExit(f"待替换定义不是 {TARGET_STANDARD_ID}：{definition.id}")

    # Locate the parent's member for this standard by parsing, never by name guess.
    removed: list[str] = []
    kept: dict[str, bytes] = {}
    for entry in parent_manifest.files:
        if entry.kind != "definition":
            continue
        candidate = StandardDefinition.model_validate_json(members[entry.path])
        if candidate.id == TARGET_STANDARD_ID:
            removed.append(entry.path)
    if len(removed) != 1:
        raise SystemExit(
            f"父基线中 {TARGET_STANDARD_ID} 的定义成员数应为 1，实际 {len(removed)}：{removed}"
        )

    suffix = "" if definition.rule_revision == 1 else f"-r{definition.rule_revision}"
    new_definition_member = f"definitions/{definition.id}-{definition.version}{suffix}.json"

    for name, data in members.items():
        if name in {GHOST_MEMBER, "manifest.json"}:
            continue
        if name in removed:
            continue
        kept[name] = data
    if new_definition_member in kept:
        raise SystemExit(f"新定义成员已存在于父基线：{new_definition_member}")
    kept[new_definition_member] = canonical_definition_payload(definition)

    # The definition's source PDF must already be in the parent, unmodified.
    source_member = f"sources/{definition.source_file}"
    if source_member not in kept:
        raise SystemExit(f"父基线缺少该标准的原文：{source_member}")
    if _sha256_bytes(kept[source_member]) != definition.source_sha256.lower():
        raise SystemExit("父基线中该标准原文的哈希与当前定义不一致")

    rule_count = 0
    definition_count = 0
    package_files: list[PackageFile] = []
    for name, data in sorted(kept.items()):
        if name.startswith("definitions/"):
            kind = "definition"
            parsed = StandardDefinition.model_validate_json(data)
            rule_count += sum(len(product.indicators) for product in parsed.products)
            definition_count += 1
        elif name.startswith("sources/"):
            kind = "source"
        else:
            kind = "correction"
        package_files.append(
            PackageFile(path=name, sha256=_sha256_bytes(data), size=len(data), kind=kind)
        )

    new_manifest = PackageManifest(
        package_id=package_id or f"gb29446-r2-from-{parent_manifest.data_version}",
        data_version=data_version,
        issued_at=issued_at or datetime.now(timezone.utc),
        minimum_app_version=minimum_app_version,
        package_mode="full",
        rule_engine_version=parent_manifest.rule_engine_version,
        # Forbidden for a full package by validate_lineage; see module docstring.
        parent_package_id=None,
        standard_count=definition_count,
        rule_count=rule_count,
        files=package_files,
    )
    new_manifest_bytes = _canonical_json(new_manifest.model_dump(mode="json"))

    private_key = serialization.load_pem_private_key(
        Path(private_key_path).read_bytes(), password=None
    )
    if not isinstance(private_key, Ed25519PrivateKey):
        raise SystemExit("签名私钥不是 Ed25519 私钥")
    signature = private_key.sign(new_manifest_bytes)

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", new_manifest_bytes)
        archive.writestr(GHOST_MEMBER, signature)
        for name, data in kept.items():
            archive.writestr(name, data)

    return {
        "parent": str(parent),
        "parent_package_id": parent_manifest.package_id,
        "parent_data_version": parent_manifest.data_version,
        "parent_sha256": _sha256_path(parent),
        "output": str(output),
        "output_sha256": _sha256_path(output),
        "data_version": data_version,
        "package_id": new_manifest.package_id,
        "minimum_app_version": minimum_app_version,
        "standard_count": definition_count,
        "rule_count": rule_count,
        "replaced_definition_member": removed,
        "added_definition_member": new_definition_member,
        "gb29446_rule_revision": definition.rule_revision,
        "unchanged_member_count": len(kept) - 1,  # exclude the new definition
    }


def verify_revision_package(parent: Path, candidate: Path) -> dict:
    """Assert the candidate differs from the parent ONLY for GB 29446."""
    parent_manifest_bytes, parent_members = _read_package(parent)
    parent_manifest = PackageManifest.model_validate_json(parent_manifest_bytes)
    candidate_manifest_bytes, candidate_members = _read_package(candidate)
    candidate_manifest = PackageManifest.model_validate_json(candidate_manifest_bytes)

    problems: list[str] = []
    changed: list[str] = []
    added: list[str] = []
    removed: list[str] = []

    parent_names = set(parent_members) - {"manifest.json", GHOST_MEMBER}
    candidate_names = set(candidate_members) - {"manifest.json", GHOST_MEMBER}

    for name in sorted(parent_names - candidate_names):
        removed.append(name)
    for name in sorted(candidate_names - parent_names):
        added.append(name)
    for name in sorted(parent_names & candidate_names):
        if parent_members[name] != candidate_members[name]:
            changed.append(name)

    def is_gb29446_definition(name: str) -> bool:
        if not name.startswith("definitions/"):
            return False
        try:
            return StandardDefinition.model_validate_json(
                candidate_members.get(name) or parent_members[name]
            ).id == TARGET_STANDARD_ID
        except Exception:
            return False

    # Every removed member must be the old GB29446 definition; every added member
    # must be the new one; nothing else may differ.
    for name in removed:
        if not is_gb29446_definition(name):
            problems.append(f"非目标成员被删除：{name}")
    for name in added:
        if not is_gb29446_definition(name):
            problems.append(f"非目标成员被新增：{name}")
    for name in changed:
        if not is_gb29446_definition(name):
            problems.append(f"非目标成员内容被改变：{name}")

    gb_new = None
    for name in added:
        parsed = StandardDefinition.model_validate_json(candidate_members[name])
        if parsed.id == TARGET_STANDARD_ID:
            gb_new = parsed
    if gb_new is None:
        problems.append("候选包中没有新的 GB29446 定义成员")
    elif gb_new.rule_revision != 2:
        problems.append(f"新 GB29446 规则修订应为 2，实际 {gb_new.rule_revision}")

    if candidate_manifest.standard_count != parent_manifest.standard_count:
        problems.append(
            "标准数量发生变化："
            f"{parent_manifest.standard_count} -> {candidate_manifest.standard_count}"
        )
    if candidate_manifest.data_version == parent_manifest.data_version:
        problems.append("data_version 未变更")
    if candidate_manifest.package_id == parent_manifest.package_id:
        problems.append("package_id 未变更")

    return {
        "valid": not problems,
        "problems": problems,
        "removed": removed,
        "added": added,
        "changed": changed,
        "parent_data_version": parent_manifest.data_version,
        "candidate_data_version": candidate_manifest.data_version,
        "parent_standard_count": parent_manifest.standard_count,
        "candidate_standard_count": candidate_manifest.standard_count,
        "parent_rule_count": parent_manifest.rule_count,
        "candidate_rule_count": candidate_manifest.rule_count,
        "gb29446_rule_revision": None if gb_new is None else gb_new.rule_revision,
    }


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_console()
    parser = argparse.ArgumentParser(
        description="从已签名父基线生成只替换 GB29446 定义的新完整签名标准包"
    )
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--definition", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-version", required=True)
    parser.add_argument("--minimum-app-version", default="0.2.0")
    parser.add_argument("--package-id", default=None)
    parser.add_argument("--issued-at", default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)

    if args.verify_only:
        report = verify_revision_package(args.parent, args.output)
    else:
        issued_at = (
            datetime.fromisoformat(args.issued_at).astimezone(timezone.utc)
            if args.issued_at
            else None
        )
        build = build_revision_package(
            args.parent,
            args.definition,
            args.private_key,
            args.output,
            data_version=args.data_version,
            minimum_app_version=args.minimum_app_version,
            package_id=args.package_id,
            issued_at=issued_at,
        )
        report = {**build, **{"verification": verify_revision_package(args.parent, args.output)}}
        if not report["verification"]["valid"]:
            raise SystemExit(
                "生成结果未通过同源校验：\n  " + "\n  ".join(report["verification"]["problems"])
            )

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    return 0 if report.get("valid", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
