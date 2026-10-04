"""ECQ-RS05 §8 — Artifact Gate.

This gate runs **after** a Candidate build and it must FAIL on a missing
artifact.  It is enabled only when the built Candidate directory is explicitly
declared, so an ordinary source checkout does not turn into a false failure:

* ``UEBENCH_ARTIFACT_DIR`` unset  -> ``SKIP`` (no Candidate was declared);
* ``UEBENCH_ARTIFACT_DIR`` set but missing/empty -> ``FAIL``;
* set and populated -> every check below must be a real read of the artifact.

Nothing here is mocked.  The payload manifest is verified independently of
``tools/audit_release.py`` (which is also invoked, as the product's own
verifier), so a bug in one implementation cannot hide a mismatch from both.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]

ENV_VAR = "UEBENCH_ARTIFACT_DIR"

#: Name of the legacy confirmation workbook: LEGACY_REFERENCE_ONLY, never a
#: PASS condition and never required in a Candidate directory.
LEGACY_CONFIRMATION_WORKBOOK = "统一标准规则确认表.xlsx"

FORBIDDEN_PAYLOAD_BINARIES = ("icuuc.dll", "icudt78.dll")

#: Minimum plausible size for the Inno Setup installer (MiB).
MIN_INSTALLER_BYTES = 1 << 20

UNSIGNED_REASON = "no_signing_certificate"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _load_sibling_module(name: str, path: Path) -> ModuleType:
    """Import a ``tools/`` script that imports siblings by bare name."""
    import importlib.util

    tools_dir = ROOT / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _artifact_dir_from_env() -> Path | None:
    raw = (os.environ.get(ENV_VAR) or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dataset_sha256(entries: list[dict[str, Any]]) -> str:
    """Re-derive ``payload_tree_sha256`` from the manifest's own triples.

    Must stay byte-identical to ``tools/build_payload_manifest.py`` and
    ``tools/audit_release.py``; asserted here as an independent implementation.
    """
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item["path"]):
        digest.update(
            f"{entry['sha256']}  {entry['size']}  {entry['path']}\n".encode("utf-8")
        )
    return digest.hexdigest()


@pytest.fixture(scope="session")
def artifact_dir() -> Path:
    """The declared Candidate directory, or a SKIP when none was declared."""
    declared = _artifact_dir_from_env()
    if declared is None:
        pytest.skip(
            "SKIP: UEBENCH_ARTIFACT_DIR 未设置，未声明已构建 Candidate 产物"
        )
    if not declared.exists():
        pytest.fail(f"{ENV_VAR} 指向的目录不存在：{declared}")
    if not declared.is_dir():
        pytest.fail(f"{ENV_VAR} 指向的不是目录：{declared}")
    if not any(declared.iterdir()):
        pytest.fail(f"{ENV_VAR} 指向的目录为空，未声明已构建 Candidate 产物：{declared}")
    return declared


@pytest.fixture(scope="session")
def release_version() -> ModuleType:
    return _load_sibling_module(
        "release_version_artifact_gate", ROOT / "tools" / "release_version.py"
    )


@pytest.fixture(scope="session")
def build_info(artifact_dir: Path, release_version: ModuleType) -> dict[str, Any]:
    """The Candidate's own provenance document.

    Every artifact name below is derived from *this* file's ``candidate_id``
    (ECQ-RS05): a Candidate directory is verified under its Candidate names, and
    a document that named the wrong identity would fail on the missing files
    instead of passing against the formal-release names by accident.
    """
    name = release_version.artifact_names(release_version.project_version())["build_info"]
    path = artifact_dir / name
    assert path.is_file(), f"缺少 {name}：{path}"
    info = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(info, dict), f"{name} 顶层必须是 JSON 对象"
    return info


@pytest.fixture(scope="session")
def candidate_id(build_info: dict[str, Any]) -> str | None:
    value = build_info.get("candidate_id")
    assert value is None or isinstance(value, str), (
        f"release-build-info.json 的 candidate_id 类型非法：{value!r}"
    )
    return value


@pytest.fixture(scope="session")
def names(
    release_version: ModuleType, candidate_id: str | None
) -> dict[str, str]:
    return release_version.artifact_names(release_version.project_version(), candidate_id)


@pytest.fixture(scope="session")
def sha256sums(artifact_dir: Path, names: dict[str, str]) -> dict[str, str]:
    path = artifact_dir / names["sha256sums"]
    assert path.is_file(), f"缺少 {names['sha256sums']}：{path}"
    entries: dict[str, str] = {}
    for number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        assert len(parts) == 2, f"{names['sha256sums']} 第{number}行格式错误：{line!r}"
        digest, filename = parts[0], parts[1].lstrip("*")
        assert re.fullmatch(r"[0-9a-fA-F]{64}", digest), (
            f"{names['sha256sums']} 第{number}行不是 SHA256：{digest!r}"
        )
        entries[filename] = digest.lower()
    return entries


# --------------------------------------------------------------------------
# 1. Presence of every required artifact
# --------------------------------------------------------------------------


#: The twelve artifacts a formal Candidate must contain.  Kept in sync with
#: ``tools/audit_release.required_files()`` by
#: ``test_required_files_list_matches_audit_release`` below, so neither list can
#: drift away from the other.
REQUIRED_KEYS: tuple[str, ...] = (
    "portable",
    "installer",
    "source",
    "standard_package",
    "template",
    "sha256sums",
    "payload_manifest",
    "build_info",
    "helper_ps1",
    "helper_cmd",
    "release_notes",
    "delivery_list",
)

#: ``SHA256SUMS.txt`` cannot contain its own hash for obvious reasons; every
#: other required artifact must be listed and must recompute.
HASHED_KEYS: tuple[str, ...] = tuple(key for key in REQUIRED_KEYS if key != "sha256sums")


@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_required_artifact_exists(
    artifact_dir: Path, names: dict[str, str], key: str
) -> None:
    path = artifact_dir / names[key]
    assert path.is_file(), f"缺少必需交付物 {names[key]}（{key}）：{path}"
    assert path.stat().st_size > 0, f"交付物为空文件：{path}"


@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_required_key_is_declared_by_the_version_tool(
    names: dict[str, str], key: str
) -> None:
    """No required artifact may be missing from ``artifact_names()``."""
    assert key in names, f"{key} 不在 tools/release_version.artifact_names() 中"


def test_no_legacy_confirmation_workbook_is_required_or_shipped(
    artifact_dir: Path,
) -> None:
    """Legacy reference material is not a Candidate deliverable."""
    assert not (artifact_dir / LEGACY_CONFIRMATION_WORKBOOK).exists(), (
        f"Candidate 目录不得包含 {LEGACY_CONFIRMATION_WORKBOOK}"
        "（LEGACY_REFERENCE_ONLY，不是发布正确性依据）"
    )


def test_required_files_list_matches_audit_release() -> None:
    """The product's own verifier must expect exactly the same artifact set.

    ``tools/audit_release.required_files()`` deliberately lists
    ``SHA256SUMS.txt`` even though a checksum file cannot carry its own digest;
    that is handled inside the audit, and mirrored by
    ``test_sha256sums_does_not_claim_to_hash_itself`` below.
    """
    audit_release = _load_sibling_module(
        "audit_release_artifact_gate", ROOT / "tools" / "audit_release.py"
    )
    release_version = _load_sibling_module(
        "release_version_for_required_list", ROOT / "tools" / "release_version.py"
    )
    expected = release_version.artifact_names(release_version.project_version())
    assert tuple(audit_release.required_files()) == tuple(
        expected[key] for key in REQUIRED_KEYS
    ), "Artifact Gate 的必需交付物清单与 tools/audit_release.required_files() 不一致"


# --------------------------------------------------------------------------
# 2. SHA256SUMS covers everything and every hash recomputes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("key", HASHED_KEYS)
def test_sha256sums_covers_artifact(
    names: dict[str, str], sha256sums: dict[str, str], key: str
) -> None:
    filename = names[key]
    assert filename in sha256sums, f"SHA256SUMS.txt 未登记必需交付物：{filename}"


@pytest.mark.parametrize("key", HASHED_KEYS)
def test_sha256sums_hash_matches_recomputed(
    artifact_dir: Path, names: dict[str, str], sha256sums: dict[str, str], key: str
) -> None:
    filename = names[key]
    path = artifact_dir / filename
    assert path.is_file(), f"缺少交付物：{filename}"
    assert filename in sha256sums, f"SHA256SUMS.txt 未登记必需交付物：{filename}"
    recomputed = _sha256(path)
    assert recomputed == sha256sums[filename], (
        f"{filename} 的 SHA256 与 SHA256SUMS.txt 不一致："
        f"{recomputed} != {sha256sums[filename]}"
    )


def test_sha256sums_declares_no_unexpected_required_artifact(
    names: dict[str, str], sha256sums: dict[str, str]
) -> None:
    """Every registered name must be a real Candidate artifact (no stale lines)."""
    known = {value for value in names.values()} | {names["sha256sums"]}
    unknown = sorted(set(sha256sums) - known)
    assert not unknown, f"SHA256SUMS.txt 登记了非交付物条目：{unknown}"


# --------------------------------------------------------------------------
# 3. The product's own release auditor passes
# --------------------------------------------------------------------------


def test_sha256sums_does_not_claim_to_hash_itself(
    names: dict[str, str], sha256sums: dict[str, str]
) -> None:
    """A file cannot contain its own hash.

    ``tools/build_source_zip.py`` / ``scripts/sync_release.ps1`` therefore do not
    register ``SHA256SUMS.txt`` in itself — the same rule this gate applies.
    """
    assert names["sha256sums"] not in sha256sums, (
        "SHA256SUMS.txt 不应登记自身哈希（自指哈希不可构造）"
    )


def test_audit_release_reports_valid(artifact_dir: Path) -> None:
    audit_release = _load_sibling_module(
        "audit_release_for_gate", ROOT / "tools" / "audit_release.py"
    )
    report = audit_release.audit_release(artifact_dir)
    assert report["valid"] is True, (
        "tools/audit_release.py 审计失败：\n" + "\n".join(report.get("errors", []))
    )
    assert report["legacy_reference_only"]["correctness_basis"] is False
    assert report["no_standard_pdf"]["clean"] is True, (
        "audit_release 的 no_standard_pdf 检查未通过："
        + json.dumps(report["no_standard_pdf"], ensure_ascii=False)
    )


# --------------------------------------------------------------------------
# 3b. ECQ-RS05 —— no standard PDF in a formal Candidate (owner decision 0.2.0)
# --------------------------------------------------------------------------


def test_release_directory_contains_no_pdf_anywhere(
    artifact_dir: Path, names: dict[str, str]
) -> None:
    """A Candidate must not distribute standard原文: no ``*.pdf`` at all.

    The check is recursive and excludes nothing, so a PDF dropped next to the
    package, into a subfolder, or under the payload tree is caught.  The standard
    package itself is one of the files scanned here, which is exactly the leak
    this gate exists for.
    """
    pdfs = sorted(
        str(path.relative_to(artifact_dir)).replace("\\", "/")
        for path in artifact_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    )
    assert not pdfs, (
        f"Candidate 目录包含 {len(pdfs)} 个 PDF（0.2.0 不得分发标准原文）：{pdfs[:5]}"
    )
    assert names["standard_package"] in {path.name for path in artifact_dir.iterdir()}


def test_standard_package_contains_no_sources_member(
    artifact_dir: Path, names: dict[str, str]
) -> None:
    """The shipped standard package must be source_policy=provenance-only."""
    package = artifact_dir / names["standard_package"]
    assert package.is_file(), f"缺少标准包：{package}"
    with zipfile.ZipFile(package) as archive:
        members = [info.filename for info in archive.infolist() if not info.is_dir()]
        manifest = json.loads(archive.read("manifest.json"))
    source_members = sorted(name for name in members if name.startswith("sources/"))
    assert not source_members, (
        f"标准包仍包含 sources/* 成员：{source_members[:5]}（共 {len(source_members)}）"
    )
    assert not [name for name in members if name.lower().endswith(".pdf")]
    source_entries = [
        entry for entry in manifest.get("files", []) if entry.get("kind") == "source"
    ]
    assert not source_entries, f"标准包清单仍登记 source 条目：{source_entries[:5]}"
    assert manifest.get("source_policy") == "provenance-only", (
        f"标准包必须声明 source_policy=provenance-only，实际 {manifest.get('source_policy')!r}"
    )


def test_portable_zip_contains_no_pdf_member(
    portable_members: list[str],
) -> None:
    offenders = sorted(
        member for member in portable_members if Path(member).suffix.lower() == ".pdf"
    )
    assert not offenders, (
        f"便携包含 PDF 成员：{offenders[:5]}（共 {len(offenders)}）"
    )


def test_payload_manifest_lists_no_pdf(
    artifact_dir: Path, names: dict[str, str]
) -> None:
    manifest = json.loads(
        (artifact_dir / names["payload_manifest"]).read_text(encoding="utf-8")
    )
    offenders = sorted(
        str(entry.get("path"))
        for entry in manifest["files"]
        if str(entry.get("path", "")).lower().endswith(".pdf")
    )
    assert not offenders, f"payload 清单登记了 PDF：{offenders[:5]}（共 {len(offenders)}）"


# --------------------------------------------------------------------------
# 4. Portable ZIP contents
# --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def portable_members(artifact_dir: Path, names: dict[str, str]) -> list[str]:
    with zipfile.ZipFile(artifact_dir / names["portable"]) as archive:
        return [info.filename for info in archive.infolist() if not info.is_dir()]


def test_portable_zip_contains_no_incompatible_icu_binaries(
    portable_members: list[str],
) -> None:
    offenders = sorted(
        member
        for member in portable_members
        if Path(member).name.lower() in FORBIDDEN_PAYLOAD_BINARIES
    )
    assert not offenders, f"便携包含不兼容的 ICU 二进制：{offenders}"


def test_portable_zip_contains_the_application_and_qt_runtime(
    portable_members: list[str],
) -> None:
    lowered = {member.replace("\\", "/").lower() for member in portable_members}
    assert any(member.endswith("/uebench.exe") or member == "uebench.exe" for member in lowered), (
        "便携包缺少 UEBench.exe"
    )
    assert any(member.endswith("pyside6/qtgui.pyd") for member in lowered), (
        "便携包缺少 PySide6/QtGui.pyd"
    )


# --------------------------------------------------------------------------
# 5. Installer EXE is a real PE binary
# --------------------------------------------------------------------------


def test_installer_is_a_real_pe_binary(artifact_dir: Path, names: dict[str, str]) -> None:
    path = artifact_dir / names["installer"]
    assert path.is_file(), f"缺少安装程序：{path}"
    with path.open("rb") as stream:
        magic = stream.read(2)
    assert magic == b"MZ", f"安装程序不是 PE 可执行文件（缺少 MZ 文件头）：{magic!r}"
    size = path.stat().st_size
    assert size > MIN_INSTALLER_BYTES, (
        f"安装程序大小不合理（{size} 字节，应 > {MIN_INSTALLER_BYTES}）：{path}"
    )


# --------------------------------------------------------------------------
# 6. Unsigned-release declaration
# --------------------------------------------------------------------------


def test_build_info_declares_an_unsigned_release(
    build_info: dict[str, Any]
) -> None:
    assert build_info.get("authenticode_signed") is False, (
        "release-build-info.json 必须声明 authenticode_signed = false"
    )
    assert build_info.get("unsigned_reason") == UNSIGNED_REASON, (
        f"release-build-info.json 必须声明 unsigned_reason = {UNSIGNED_REASON}"
    )


def test_build_info_carries_the_full_candidate_provenance(
    build_info: dict[str, Any], release_version: ModuleType, names: dict[str, str]
) -> None:
    """ECQ-RS05: a Candidate must be traceable to one exact commit."""
    version = release_version.project_version()
    for key in (
        "product_version",
        "candidate_id",
        "source_commit",
        "source_dirty",
        "standard_package_id",
        "standard_data_version",
        "standard_package_sha256",
        "payload_tree_sha256",
        "build_time_utc",
    ):
        assert key in build_info, f"release-build-info.json 缺少溯源字段：{key}"
    assert build_info["product_version"] == version
    assert build_info["version"] == version
    assert re.fullmatch(r"[0-9a-f]{40}", str(build_info["source_commit"])), (
        f"source_commit 必须是 40 位小写十六进制：{build_info['source_commit']!r}"
    )
    assert build_info["source_dirty"] is False, "正式候选必须声明 source_dirty = false"
    assert re.fullmatch(r"[0-9a-f]{64}", str(build_info["payload_tree_sha256"]))
    assert re.fullmatch(r"[0-9a-f]{64}", str(build_info["standard_package_sha256"]))
    if build_info["candidate_id"] is not None:
        assert build_info["candidate_id"] in names["portable"]
        assert build_info["candidate_id"] in names["installer"]
        assert build_info["candidate_id"] in names["source"]


# --------------------------------------------------------------------------
# 6b. §11 — the ACTIVE Candidate marker
# --------------------------------------------------------------------------


ACTIVE_MARKER = "ACTIVE-CANDIDATE.json"


@pytest.fixture(scope="session")
def active_marker(artifact_dir: Path) -> dict[str, Any]:
    path = artifact_dir / ACTIVE_MARKER
    assert path.is_file(), (
        f"候选目录缺少 {ACTIVE_MARKER}；§11 要求装配完成的候选目录声明唯一 ACTIVE 候选"
    )
    marker = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(marker, dict)
    return marker


def test_active_marker_declares_one_active_candidate(
    active_marker: dict[str, Any], build_info: dict[str, Any], release_version: ModuleType
) -> None:
    assert active_marker.get("schema") == "ecq.active-candidate.v1"
    assert active_marker.get("status") == "ACTIVE"
    assert active_marker.get("candidate_id") == build_info.get("candidate_id")
    assert active_marker.get("product_version") == release_version.project_version()
    assert active_marker.get("source_commit") == build_info.get("source_commit")
    assert re.fullmatch(r"[0-9a-f]{40}", str(active_marker.get("source_commit")))
    assert active_marker.get("source_dirty") is False
    assert active_marker.get("standard_package_id") == build_info.get("standard_package_id")
    assert active_marker.get("standard_data_version") == build_info.get(
        "standard_data_version"
    )
    assert active_marker.get("standard_package_sha256") == build_info.get(
        "standard_package_sha256"
    )
    assert active_marker.get("assembled_at_utc")


def test_active_marker_payload_tree_sha256_equals_the_manifest(
    active_marker: dict[str, Any], artifact_dir: Path, names: dict[str, str]
) -> None:
    """The marker must pin the payload it names, not a different build's."""
    manifest = json.loads(
        (artifact_dir / names["payload_manifest"]).read_text(encoding="utf-8")
    )
    assert active_marker.get("payload_tree_sha256") == manifest["payload_tree_sha256"], (
        "ACTIVE-CANDIDATE.json 的 payload_tree_sha256 与 payload-manifest.json 不一致"
    )


def test_active_marker_is_not_hashed_by_sha256sums(
    sha256sums: dict[str, str]
) -> None:
    """A document that names the assembly cannot be one of the files it pins."""
    assert ACTIVE_MARKER not in sha256sums


# --------------------------------------------------------------------------
# 7. Payload manifest matches the portable ZIP exactly (independent check)
# --------------------------------------------------------------------------


def test_payload_manifest_matches_the_portable_zip(
    artifact_dir: Path, names: dict[str, str], release_version: ModuleType
) -> None:
    manifest = json.loads(
        (artifact_dir / names["payload_manifest"]).read_text(encoding="utf-8")
    )
    entries = manifest["files"]
    expected = {entry["path"]: entry for entry in entries}

    assert manifest["version"] == release_version.project_version(), (
        "payload-manifest.json 的版本与 pyproject.toml 不一致"
    )
    assert manifest["file_count"] == len(entries), "file_count 与 files 数量不一致"
    assert manifest["total_bytes"] == sum(entry["size"] for entry in entries), (
        "total_bytes 与各条目大小之和不一致"
    )
    assert manifest["payload_tree_sha256"] == _dataset_sha256(entries), (
        "payload_tree_sha256 与清单自身条目不一致"
    )

    root_prefix = str(manifest["root"]).rstrip("/") + "/"
    mismatched: list[str] = []
    extra: list[str] = []
    with zipfile.ZipFile(artifact_dir / names["portable"]) as archive:
        present: set[str] = set()
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            if not name.startswith(root_prefix):
                extra.append(f"{name}（不在 {root_prefix} 下）")
                continue
            relative = name[len(root_prefix):]
            present.add(relative)
            entry = expected.get(relative)
            if entry is None:
                extra.append(relative)
                continue
            payload = archive.read(info.filename)
            if (
                hashlib.sha256(payload).hexdigest() != entry["sha256"]
                or len(payload) != entry["size"]
            ):
                mismatched.append(relative)

    missing = sorted(set(expected) - present)
    assert not missing, f"便携包缺少 payload 清单中的文件：{missing[:5]}（共 {len(missing)}）"
    assert not extra, f"便携包含 payload 清单之外的文件：{extra[:5]}（共 {len(extra)}）"
    assert not mismatched, (
        f"便携包文件与 payload 清单哈希/大小不一致：{mismatched[:5]}（共 {len(mismatched)}）"
    )


# --------------------------------------------------------------------------
# 8. GB 29446 template really is an Excel workbook with the 评价数据 sheet
# --------------------------------------------------------------------------


def test_template_is_a_valid_xlsx_with_the_evaluation_sheet(
    artifact_dir: Path, names: dict[str, str]
) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    path = artifact_dir / names["template"]
    workbook = openpyxl.load_workbook(path, read_only=False, data_only=False)
    try:
        assert "评价数据" in workbook.sheetnames, (
            f"{names['template']} 缺少“评价数据”工作表；实际：{workbook.sheetnames}"
        )
    finally:
        workbook.close()


# --------------------------------------------------------------------------
# 9. The acceptance helper is version-agnostic
# --------------------------------------------------------------------------


def test_acceptance_helper_does_not_hard_code_the_previous_version(
    artifact_dir: Path,
    names: dict[str, str],
    release_version: ModuleType,
    build_info: dict[str, Any],
) -> None:
    text = (artifact_dir / names["helper_ps1"]).read_text(encoding="utf-8")
    version = release_version.project_version()
    assert "0.1.0" not in text, (
        f"{names['helper_ps1']} 仍硬编码旧产品版本 0.1.0"
    )
    assert "release-build-info.json" in text, (
        f"{names['helper_ps1']} 必须从 release-build-info.json 读取版本，而不是写死"
    )
    # ECQ-RS05: the version alone is not enough any more -- the Candidate
    # identity is part of the file names, so the helper must read it too, or it
    # would report every Candidate as "missing files".
    assert "buildInfo.candidate_id" in text, (
        f"{names['helper_ps1']} 必须从 release-build-info.json 读取 candidate_id"
    )
    assert "$candidateSuffix" in text
    assert "UEBench-$version$candidateSuffix-win-x64.zip" in text
    assert "UEBench-Setup-$version$candidateSuffix-x64.exe" in text
    assert "UEBench-source-$version$candidateSuffix.zip" in text
    assert names["helper_ps1"] == "验收助手.ps1"

    # The names the helper composes are exactly the names this Candidate ships.
    suffix = f"-{build_info['candidate_id']}" if build_info.get("candidate_id") else ""
    assert names["portable"] == f"UEBench-{version}{suffix}-win-x64.zip"
    assert names["installer"] == f"UEBench-Setup-{version}{suffix}-x64.exe"
    assert names["source"] == f"UEBench-source-{version}{suffix}.zip"
    assert build_info.get("version") == version, (
        "release-build-info.json 的版本必须是当前产品版本，验收助手据此定位产物"
    )
