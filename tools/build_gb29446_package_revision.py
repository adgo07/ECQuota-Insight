"""Produce SIGNED standard packages from a signed parent baseline.

Two build modes live here.

**1. GB 29446 revision replacement** (ECQ-RS05, approved option B — default mode)

The parent baseline is the published, Ed25519-signed
``2026.09-published.2`` package.  Its GB 29446—2019 definition is a pre-RS01
revision (``rule_revision=1``, no ``coal_type`` selection schema), which is why
the RS04 Product Golden cannot be replayed against an installed Candidate.

This tool rewrites **exactly one** member of that package — the GB 29446
definition, replaced by the current repository definition (``rule_revision=2``)
— re-signs the manifest, and leaves **every other member byte-identical**.

**2. Source-free / provenance-only variant** (ECQ-RS05 §五 + package half of §九)

``--drop-sources`` builds the same catalogue as its baseline while shipping
**no** ``sources/*`` member at all.  The owner decision for 0.2.0 is that the
product must not distribute, store or open full standard PDFs: the definitions
keep their ``source_file`` / ``source_sha256`` provenance, but the原文 files are
removed from the distribution.  The manifest declares this explicitly through
``source_policy = "provenance-only"`` (absent field = legacy ``embedded``).

  * every ``definitions/*.json`` member and ``corrections.json`` must stay
    **byte-identical** to the baseline — this is asserted, and the build fails
    otherwise;
  * **only** ``sources/*`` members may disappear; nothing else may be added,
    removed or changed;
  * ``package_id`` and ``data_version`` must both change, and the new
    ``data_version`` must sort **after** the baseline under the application's
    ``YYYY.MM-channel.revision`` ordering (``_data_version_key``).

Both modes deliberately do NOT go through ``StandardPackageBuilder.build()``:
that method re-serialises every definition through the current pydantic model,
which could silently change the bytes of the other standards.  Here the
untouched members are copied verbatim from the parent archive.

Neither mode ever consults ``统一标准规则确认表.xlsx`` (LEGACY_REFERENCE_ONLY):
no rule content is regenerated from it.

Signing key: this is a **developer-side** tool.  The Ed25519 private key is never
committed and never referenced from CI; ``--private-key`` must point at an
existing file or the tool fails with a clear message before touching anything.

Lineage: ``PackageManifest.validate_lineage`` forbids ``parent_package_id`` when
``package_mode == "full"``, so the parent relationship cannot be recorded inside
a full package's manifest.  It is recorded in
``release/standard-packages/PIN.json`` (and in the build report) instead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
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
    _data_version_key,  # noqa: PLC2701
    _sha256_bytes,  # noqa: PLC2701
)

TARGET_STANDARD_ID = "gb-29446-2019"
GHOST_MEMBER = "signature.ed25519"

#: Members that must never be treated as content.
STRUCTURAL_MEMBERS = frozenset({GHOST_MEMBER, "manifest.json"})

#: The two distribution modes, mirrored in ``PackageManifest.source_policy``.
SOURCE_POLICY_EMBEDDED = "embedded"
SOURCE_POLICY_PROVENANCE_ONLY = "provenance-only"


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


def _diff_members(
    parent_members: dict[str, bytes], candidate_members: dict[str, bytes]
) -> tuple[list[str], list[str], list[str]]:
    """Return (removed, added, changed) member names, ignoring structure members."""
    parent_names = set(parent_members) - STRUCTURAL_MEMBERS
    candidate_names = set(candidate_members) - STRUCTURAL_MEMBERS
    removed = sorted(parent_names - candidate_names)
    added = sorted(candidate_names - parent_names)
    changed = sorted(
        name for name in parent_names & candidate_names if parent_members[name] != candidate_members[name]
    )
    return removed, added, changed


def canonical_definition_payload(definition: StandardDefinition) -> bytes:
    """Canonical payload the application will compare against.

    Matches ``_definition_matches`` in ``uebench.infrastructure.packages`` so a
    freshly installed revision is recognised as identical on re-install.
    """
    return _canonical_json(definition.model_dump(mode="json"))


def _definition_by_standard_id(members: dict[str, bytes], manifest: PackageManifest) -> dict[str, bytes]:
    """Map ``definition.id`` -> the exact raw member bytes carried by a package."""
    found: dict[str, bytes] = {}
    for entry in manifest.files:
        if entry.kind != "definition":
            continue
        parsed = StandardDefinition.model_validate_json(members[entry.path])
        found[parsed.id] = members[entry.path]
    return found


def _load_signing_key(private_key_path: Path) -> Ed25519PrivateKey:
    """Load the local development signing key, failing clearly when absent.

    The key lives outside version control (``work/signing/``); it is never
    committed and never referenced from CI.  A missing key must stop the build
    before any output is written.
    """
    path = Path(private_key_path)
    if not path.is_file():
        raise SystemExit(
            "缺少本地开发签名私钥："
            f"{path}\n"
            "该私钥不随仓库分发、也不得从 CI 引用；请在本地开发机放置 "
            "work/signing/development-private-key.pem 后用 --private-key 指向它。"
        )
    try:
        private_key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except Exception as exc:  # noqa: BLE001 - a clear message beats a traceback
        raise SystemExit(f"签名私钥无法加载：{path}（{type(exc).__name__}: {exc}）") from exc
    if not isinstance(private_key, Ed25519PrivateKey):
        raise SystemExit("签名私钥不是 Ed25519 私钥")
    return private_key


def _write_signed_package(
    output: Path,
    manifest: PackageManifest,
    private_key: Ed25519PrivateKey,
    members: dict[str, bytes],
) -> None:
    manifest_bytes = _canonical_json(manifest.model_dump(mode="json"))
    signature = private_key.sign(manifest_bytes)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", manifest_bytes)
        archive.writestr(GHOST_MEMBER, signature)
        for name, data in members.items():
            archive.writestr(name, data)


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
        if name in STRUCTURAL_MEMBERS:
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
        source_policy=SOURCE_POLICY_EMBEDDED,
        rule_engine_version=parent_manifest.rule_engine_version,
        # Forbidden for a full package by validate_lineage; see module docstring.
        parent_package_id=None,
        standard_count=definition_count,
        rule_count=rule_count,
        files=package_files,
    )
    private_key = _load_signing_key(private_key_path)
    _write_signed_package(output, new_manifest, private_key, kept)

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
        "source_policy": new_manifest.source_policy,
        "source_free": False,
        "standard_count": definition_count,
        "rule_count": rule_count,
        "replaced_definition_member": removed,
        "added_definition_member": new_definition_member,
        "gb29446_rule_revision": definition.rule_revision,
        "unchanged_member_count": len(kept) - 1,  # exclude the new definition
    }


def build_source_free_package(
    parent: Path,
    private_key_path: Path,
    output: Path,
    *,
    data_version: str,
    minimum_app_version: str,
    package_id: str | None = None,
    issued_at: datetime | None = None,
) -> dict:
    """Build a signed **source-free** (provenance-only) full package.

    The catalogue is copied verbatim from ``parent``: every content member keeps
    its exact bytes.  The **only** change is the removal of every ``sources/*``
    member, which the manifest declares through
    ``source_policy = "provenance-only"``.

    Raises ``SystemExit`` when the result would deviate in any other way.
    """
    parent = parent.resolve()
    output = output.resolve()
    if parent == output:
        raise SystemExit("输出路径不能覆盖父基线标准包")

    manifest_bytes, members = _read_package(parent)
    parent_manifest = PackageManifest.model_validate_json(manifest_bytes)
    if parent_manifest.package_mode != "full":
        raise SystemExit(f"父基线必须是完整包，实际为 {parent_manifest.package_mode}")

    source_members = sorted(
        name for name in members if name not in STRUCTURAL_MEMBERS and name.startswith("sources/")
    )
    if not source_members:
        raise SystemExit(f"父基线不包含 sources/*，无需生成去原文版本：{parent}")

    # --- content must be complete and self-consistent -----------------------
    definitions = _definition_by_standard_id(members, parent_manifest)
    if len(definitions) != parent_manifest.standard_count:
        raise SystemExit(
            f"父基线定义数量与清单不一致：{len(definitions)} != {parent_manifest.standard_count}"
        )
    declared_source_names = {
        entry.path for entry in parent_manifest.files if entry.kind == "source"
    }
    if declared_source_names != set(source_members):
        raise SystemExit("父基线 sources/* 成员与清单登记不一致")

    # Every definition must carry full provenance and the parent must really hold
    # the cited原文 with the cited hash -- otherwise "provenance-only" would drop a
    # reference that was never verifiable in the first place.
    for name, raw in definitions.items():
        parsed = StandardDefinition.model_validate_json(raw)
        source_path = f"sources/{parsed.source_file}"
        if source_path not in members:
            raise SystemExit(f"标准 {parsed.number} 引用的原文不在父基线中：{source_path}")
        if _sha256_bytes(members[source_path]) != parsed.source_sha256.lower():
            raise SystemExit(f"标准 {parsed.number} 的原文哈希与定义不一致：{source_path}")
        for product in parsed.products:
            for indicator in product.indicators:
                if not indicator.source_references:
                    raise SystemExit(
                        f"标准 {parsed.number}/{indicator.id} 缺少原文依据，不能生成去原文版本"
                    )

    # --- build the new member set: drop sources/* and nothing else ----------
    kept = {
        name: data
        for name, data in members.items()
        if name not in STRUCTURAL_MEMBERS and not name.startswith("sources/")
    }
    expected_kept = {
        name
        for name in members
        if name not in STRUCTURAL_MEMBERS and not name.startswith("sources/")
    }
    if set(kept) != expected_kept:  # pragma: no cover - defensive
        raise SystemExit("去原文构建时意外改动了非 sources/* 成员集合")

    definition_count = 0
    rule_count = 0
    package_files: list[PackageFile] = []
    for name, data in sorted(kept.items()):
        if name.startswith("definitions/"):
            kind = "definition"
            parsed = StandardDefinition.model_validate_json(data)
            rule_count += sum(len(product.indicators) for product in parsed.products)
            definition_count += 1
        elif name.startswith("sources/"):  # pragma: no cover - defensive
            raise SystemExit(f"去原文构建仍包含原文成员：{name}")
        else:
            kind = "correction"
        package_files.append(
            PackageFile(path=name, sha256=_sha256_bytes(data), size=len(data), kind=kind)
        )

    if definition_count != parent_manifest.standard_count:
        raise SystemExit(
            f"标准数量发生变化：{parent_manifest.standard_count} -> {definition_count}"
        )
    if rule_count != parent_manifest.rule_count:
        raise SystemExit(
            f"规则数量发生变化：{parent_manifest.rule_count} -> {rule_count}"
        )

    new_manifest = PackageManifest(
        package_id=package_id or f"provenance-only-from-{parent_manifest.data_version}",
        data_version=data_version,
        issued_at=issued_at or datetime.now(timezone.utc),
        minimum_app_version=minimum_app_version,
        package_mode="full",
        source_policy=SOURCE_POLICY_PROVENANCE_ONLY,
        rule_engine_version=parent_manifest.rule_engine_version,
        # Forbidden for a full package by validate_lineage; see module docstring.
        parent_package_id=None,
        standard_count=definition_count,
        rule_count=rule_count,
        files=package_files,
    )
    private_key = _load_signing_key(private_key_path)
    _write_signed_package(output, new_manifest, private_key, kept)

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
        "source_policy": new_manifest.source_policy,
        "source_free": True,
        "standard_count": definition_count,
        "rule_count": rule_count,
        "sources_removed": source_members,
        "sources_removed_count": len(source_members),
        "unchanged_member_count": len(kept),
    }


def verify_source_free_package(
    parent: Path, candidate: Path, *, expect_data_version: str | None = None
) -> dict:
    """Assert the candidate differs from ``parent`` ONLY by removed ``sources/*``."""
    parent_manifest_bytes, parent_members = _read_package(parent)
    parent_manifest = PackageManifest.model_validate_json(parent_manifest_bytes)
    candidate_manifest_bytes, candidate_members = _read_package(candidate)
    candidate_manifest = PackageManifest.model_validate_json(candidate_manifest_bytes)

    problems: list[str] = []
    removed, added, changed = _diff_members(parent_members, candidate_members)
    parent_sources = sorted(name for name in removed if name.startswith("sources/"))
    non_source_removed = [name for name in removed if not name.startswith("sources/")]

    # 1. only sources/* may disappear; nothing may be added or changed.
    for name in non_source_removed:
        problems.append(f"非 sources/* 成员被删除：{name}")
    for name in added:
        problems.append(f"成员被新增（去原文版本不得新增成员）：{name}")
    for name in changed:
        problems.append(f"成员内容被改变（去原文版本必须逐字节一致）：{name}")

    # 2. definitions and corrections.json must be byte-identical, explicitly.
    for name in sorted(set(parent_members) & set(candidate_members)):
        if name in STRUCTURAL_MEMBERS:
            continue
        if parent_members[name] != candidate_members[name]:  # pragma: no cover - covered above
            problems.append(f"内容成员字节不同：{name}")
    if sorted(
        name for name in parent_members if name.startswith("definitions/")
    ) != sorted(name for name in candidate_members if name.startswith("definitions/")):
        problems.append("definitions/ 成员集合发生变化")
    if parent_members.get("corrections.json") != candidate_members.get("corrections.json"):
        problems.append("corrections.json 字节不同")

    # 3. the candidate must really be source-free and must say so.
    candidate_sources = sorted(name for name in candidate_members if name.startswith("sources/"))
    if candidate_sources:
        problems.append(f"候选包仍包含原文成员：{candidate_sources[:5]}")
    if any(entry.kind == "source" for entry in candidate_manifest.files):
        problems.append("候选包清单仍登记 source 条目")
    if candidate_manifest.source_policy != SOURCE_POLICY_PROVENANCE_ONLY:
        problems.append(
            f"候选包 source_policy 应为 {SOURCE_POLICY_PROVENANCE_ONLY}，"
            f"实际 {candidate_manifest.source_policy}"
        )
    if not parent_sources:
        problems.append("父基线没有 sources/* 成员，无法证明“只移除原文”")

    # 4. identity / counts.
    if candidate_manifest.package_id == parent_manifest.package_id:
        problems.append("package_id 未变更")
    if candidate_manifest.data_version == parent_manifest.data_version:
        problems.append("data_version 未变更")
    parent_key = _data_version_key(parent_manifest.data_version)
    candidate_key = _data_version_key(candidate_manifest.data_version)
    if parent_key is not None and candidate_key is not None and candidate_key <= parent_key:
        problems.append(
            f"data_version 必须排在父基线之后：{parent_manifest.data_version} -> "
            f"{candidate_manifest.data_version}"
        )
    if expect_data_version is not None and candidate_manifest.data_version != expect_data_version:
        problems.append(
            f"data_version 与预期不符：期望 {expect_data_version}，实际 {candidate_manifest.data_version}"
        )
    if candidate_manifest.standard_count != parent_manifest.standard_count:
        problems.append(
            f"标准数量发生变化：{parent_manifest.standard_count} -> {candidate_manifest.standard_count}"
        )
    if candidate_manifest.rule_count != parent_manifest.rule_count:
        problems.append(
            f"规则数量发生变化：{parent_manifest.rule_count} -> {candidate_manifest.rule_count}"
        )
    if candidate_manifest.package_mode != "full":
        problems.append(f"候选包必须是完整包，实际 {candidate_manifest.package_mode}")
    if candidate_manifest.parent_package_id is not None:
        problems.append("完整包不得携带 parent_package_id")

    return {
        "valid": not problems,
        "problems": problems,
        "source_free": True,
        "removed": removed,
        "removed_sources": parent_sources,
        "removed_source_count": len(parent_sources),
        "added": added,
        "changed": changed,
        "unchanged_member_count": len(
            [
                name
                for name in set(parent_members) & set(candidate_members)
                if name not in STRUCTURAL_MEMBERS
            ]
        ),
        "parent_package_id": parent_manifest.package_id,
        "parent_data_version": parent_manifest.data_version,
        "candidate_package_id": candidate_manifest.package_id,
        "candidate_data_version": candidate_manifest.data_version,
        "candidate_source_policy": candidate_manifest.source_policy,
        "parent_standard_count": parent_manifest.standard_count,
        "candidate_standard_count": candidate_manifest.standard_count,
        "parent_rule_count": parent_manifest.rule_count,
        "candidate_rule_count": candidate_manifest.rule_count,
        "candidate_minimum_app_version": candidate_manifest.minimum_app_version,
        "candidate_size": candidate.stat().st_size,
        "candidate_sha256": _sha256_path(candidate),
    }


def verify_revision_package(parent: Path, candidate: Path) -> dict:
    """Assert the candidate differs from the parent ONLY for GB 29446."""
    parent_manifest_bytes, parent_members = _read_package(parent)
    parent_manifest = PackageManifest.model_validate_json(parent_manifest_bytes)
    candidate_manifest_bytes, candidate_members = _read_package(candidate)
    candidate_manifest = PackageManifest.model_validate_json(candidate_manifest_bytes)

    problems: list[str] = []
    removed, added, changed = _diff_members(parent_members, candidate_members)

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
        description=(
            "从已签名父基线生成新的签名标准包：默认只替换 GB29446 定义；"
            "加 --drop-sources 则生成不随包分发标准原文（provenance-only）的完整包"
        )
    )
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument(
        "--definition",
        type=Path,
        default=None,
        help="替换用的 GB29446 定义（--drop-sources 时不需要）",
    )
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-version", required=True)
    parser.add_argument("--minimum-app-version", default="0.2.0")
    parser.add_argument("--package-id", default=None)
    parser.add_argument("--issued-at", default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument(
        "--drop-sources",
        action="store_true",
        help="生成 source_policy=provenance-only 的完整包：只移除 sources/*，内容逐字节不变",
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)

    issued_at = (
        datetime.fromisoformat(args.issued_at).astimezone(timezone.utc)
        if args.issued_at
        else None
    )

    if args.verify_only and args.definition is not None:
        raise SystemExit(
            "--verify-only 不接受 --definition；"
            "复核去原文包请用 --drop-sources --verify-only，复核 GB29446 替换不要带 --definition"
        )
    if args.drop_sources:
        if args.definition is not None:
            raise SystemExit("--drop-sources 不接受 --definition：去原文版本不得改动任何定义")
        if args.verify_only:
            report = verify_source_free_package(
                args.parent,
                args.output,
                expect_data_version=args.data_version if args.output.is_file() else None,
            )
        else:
            build = build_source_free_package(
                args.parent,
                args.private_key,
                args.output,
                data_version=args.data_version,
                minimum_app_version=args.minimum_app_version,
                package_id=args.package_id or f"provenance-only-{args.data_version}",
                issued_at=issued_at,
            )
            verification = verify_source_free_package(
                args.parent, args.output, expect_data_version=args.data_version
            )
            report = {**build, "verification": verification}
            if not verification["valid"]:
                raise SystemExit(
                    "生成结果未通过同源校验：\n  " + "\n  ".join(verification["problems"])
                )
    elif args.verify_only:
        report = verify_revision_package(args.parent, args.output)
    else:
        if args.definition is None:
            raise SystemExit("默认模式必须提供 --definition（或用 --drop-sources）")
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
