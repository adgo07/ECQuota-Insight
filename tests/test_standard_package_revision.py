"""Verify the current signed package and preserve ECQ-RS05 history.

History, compressed:

* approved option B derived ``2026.10-published.3`` from the published
  ``2026.09-published.2`` baseline by replacing **exactly one** member — the
  GB 29446—2019 definition (old ``rule_revision=1`` out, current
  ``rule_revision=2`` in).  That package still shipped 48 ``sources/*`` PDFs.
* The owner then decided that 0.2.0 must not distribute, store or open full
  standard PDFs.  So ``2026.10-published.4`` is derived from
  ``2026.10-published.3`` by removing **only** the ``sources/*`` members:
  every ``definitions/*.json`` member and ``corrections.json`` stays
  byte-identical, and the manifest declares ``source_policy=provenance-only``.

The signed 2026.10-published.4 fixture is the exact package from Git commit
``a230f806ec4fcfd384a25bb7bea239a9c38623f3`` (SHA256 below). It is
reference-only test evidence, never an installer or release input. Historical
2026.10-published.5 changed only GB29446 r2 to r3; it is now a signed reference
fixture. Current .6 changes only GB16780 r1 to r2, without expanding formal scope.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "release" / "standard-packages"
PINNED = PACKAGE_DIR / "initial-standard-package-published.uebench"
REVISION_PARENT = ROOT / "tests" / "fixtures" / "standard-packages" / "2026.10-published.4.uebench"
CURRENT_REVISION_PARENT = ROOT / "tests" / "fixtures" / "standard-packages" / "2026.10-published.5.uebench"
#: 直接父基线（含 sources/*）已移出仓库（SUPERSEDED，项目外只读归档）；这里取得的是**副本**。
try:  # 测试目录既可能是普通目录，也可能被当作包
    from _legacy_assets import session_source_bearing_predecessor
except ModuleNotFoundError:  # pragma: no cover - 取决于 pytest 的导入模式
    from tests._legacy_assets import session_source_bearing_predecessor

PARENT = session_source_bearing_predecessor()
PIN = PACKAGE_DIR / "PIN.json"

GHOST = "signature.ed25519"
STRUCTURAL = {"manifest.json", GHOST}
TARGET = "gb-29446-2019"
PINNED_SHA256 = "d5ff370d3728ad3dda2589ed72bc9c693425208084ed96d45ad1d036c91afa51"
CURRENT_REVISION_PARENT_SHA256 = "9547e8214124cd76e999c2949dcdcf45738282a56cc0d725df08cea2a49fa2b5"
REVISION_PARENT_SHA256 = "023d5caf81dd6ba1ce41a5b5d8a59676db20dd98db510b6c4329600aa47e77ff"
PARENT_SHA256 = "14db53be241bcaf41953fcd9a52e510c6762dad59e5c2ba541b866c10b2e32b0"

ARCHIVE_UNAVAILABLE = (
    "父基线标准包已归档为 SUPERSEDED / REFERENCE ONLY（项目外只读区）且当前不可用；"
    "不随仓库分发，需先复制归档副本再复核"
)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pin() -> dict:
    return json.loads(PIN.read_text(encoding="utf-8"))


def read_manifest(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("manifest.json"))


def definitions_of(path: Path) -> dict[tuple[str, str, int], tuple[str, bytes]]:
    """Map (id, version, rule_revision) -> (member name, raw payload bytes)."""
    out: dict[tuple[str, str, int], tuple[str, bytes]] = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.startswith("definitions/"):
                continue
            payload = archive.read(name)
            doc = json.loads(payload)
            out[(doc["id"], doc["version"], doc.get("rule_revision", 1))] = (name, payload)
    return out


def content_members(path: Path) -> dict[str, bytes]:
    """Every member except the two structural ones, by name."""
    with zipfile.ZipFile(path) as archive:
        return {
            name: archive.read(name)
            for name in archive.namelist()
            if name not in STRUCTURAL
        }


# --------------------------------------------------------------------------
# 1. Repository hygiene: the predecessors must not ship
# --------------------------------------------------------------------------


def test_legacy_parent_package_is_not_shipped_in_the_repository() -> None:
    """ECQ-RS05 清理决定：旧标准包不得再作为仓库/打包输入。

    两个旧包都已移出仓库、归档为项目外只读证据（REFERENCE ONLY /
    SUPERSEDED）。若它们重新出现在 release/standard-packages/ 下，说明清理被
    回退，必须失败。
    """
    legacy = PACKAGE_DIR / "initial-standard-package-2026.09-published.2.uebench"
    superseded = PACKAGE_DIR / "initial-standard-package-2026.10-published.3.uebench"
    assert not legacy.exists(), (
        "旧标准包重新出现在仓库中；它应是 REFERENCE ONLY 的外部归档证据"
    )
    assert not superseded.exists(), (
        "被去原文版本取代的标准包重新出现在仓库中；它应是 SUPERSEDED 的外部归档证据"
    )
    pointer = PACKAGE_DIR / "LEGACY-REFERENCE.json"
    assert pointer.is_file(), "缺少旧资产归档指针 LEGACY-REFERENCE.json"
    record = json.loads(pointer.read_text(encoding="utf-8"))
    assert record["status"] == "REFERENCE ONLY"
    assert record["parent_baseline"]["sha256"] == (
        "4f025b8a45f03fc5539b2d5eb76bdf6c3d127b863e7485b46fbb100b6f221727"
    )
    predecessor = record["source_bearing_predecessor"]
    assert predecessor["sha256"] == PARENT_SHA256
    assert predecessor["data_version"] == "2026.10-published.3"
    assert predecessor["status"] == "SUPERSEDED"
    # 归档资产必须可被测试定位（经复制使用，绝不原地使用原件）
    assert predecessor["relative_path"].startswith("superseded-packages/")


def test_pin_keeps_absolute_paths_out_of_committed_files() -> None:
    """归档根只在 LEGACY-REFERENCE.json 里出现一次，其它文件不得硬编码路径。"""
    record = pin()
    text = PIN.read_text(encoding="utf-8")
    assert "ECQuota-Archive" not in text, (
        "PIN.json 不得硬编码归档绝对路径；请引用 LEGACY-REFERENCE.json 的相对路径"
    )
    for key in ("parent_baseline", "ancestor_baseline"):
        entry = record[key]
        assert "archive_relative_path" in entry and not Path(
            entry["archive_relative_path"]
        ).is_absolute()
    assert record["ancestor_baseline"]["archive_pointer"].startswith(
        "release/standard-packages/LEGACY-REFERENCE.json#"
    )
    assert "Git" in record["parent_baseline"]["archive_pointer"]


# --------------------------------------------------------------------------
# 2. The pinned package and its PIN
# --------------------------------------------------------------------------


def test_pinned_package_matches_pin_json() -> None:
    record = pin()
    assert PINNED.is_file(), "缺少固定的标准包 release input"
    assert PINNED.stat().st_size == record["size"], "标准包大小与 PIN.json 不一致"
    assert sha256_of(PINNED) == record["sha256"], "标准包 SHA256 与 PIN.json 不一致"
    assert record["sha256"] == PINNED_SHA256
    manifest = read_manifest(PINNED)
    assert manifest["data_version"] == record["data_version"]
    assert manifest["package_id"] == record["package_id"]
    assert manifest["standard_count"] == record["standard_count"]
    assert manifest["rule_count"] == record["rule_count"]
    assert manifest["package_mode"] == "full"
    assert manifest["minimum_app_version"] == "0.2.0"
    assert manifest["source_policy"] == record["source_policy"] == "provenance-only"


def test_pinned_package_contains_no_standard_source_members() -> None:
    """0.2.0 决定：正式标准包不得分发标准原文。"""
    manifest = read_manifest(PINNED)
    with zipfile.ZipFile(PINNED) as archive:
        names = archive.namelist()
    assert not [name for name in names if name.startswith("sources/")], (
        "固定标准包仍包含 sources/* 成员"
    )
    assert [name for name in names if name.lower().endswith(".pdf")] == []
    assert [entry for entry in manifest["files"] if entry["kind"] == "source"] == []
    assert manifest["standard_count"] == 48
    assert manifest["rule_count"] == 765


def test_pinned_package_gb29446_is_revision_3_with_coal_type() -> None:
    """The current signed package must contain the approved mapping revision."""
    with zipfile.ZipFile(PINNED) as archive:
        members = [n for n in archive.namelist() if n.startswith("definitions/gb-29446")]
        assert len(members) == 1, f"GB29446 定义成员应唯一，实际 {members}"
        definition = json.loads(archive.read(members[0]))
    assert definition["rule_revision"] == 3, "固定标准包内 GB29446 必须是 r3"
    assert [entry["key"] for entry in definition["selection_schema"]] == ["coal_type"]
    assert all(
        "coal_type" in (product.get("selection_values") or {})
        for product in definition["products"]
    )


def test_pinned_package_signature_verifies_against_the_shipped_public_key() -> None:
    """A real Ed25519 verification, not a structural check."""
    cryptography = pytest.importorskip("cryptography")
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization

    public_key_path = ROOT / "src" / "uebench" / "resources" / "update_public_key.pem"
    public_key = serialization.load_pem_public_key(public_key_path.read_bytes())
    with zipfile.ZipFile(PINNED) as archive:
        manifest_bytes = archive.read("manifest.json")
        signature = archive.read(GHOST)
    try:
        public_key.verify(signature, manifest_bytes)
    except InvalidSignature:  # pragma: no cover - would be a real failure
        pytest.fail("固定标准包的 Ed25519 签名无法用随产品发布的公钥验证")
    assert cryptography is not None


# --------------------------------------------------------------------------
# 3. The pinned package vs. its archived parent: ONLY sources/* may differ
# --------------------------------------------------------------------------


def _parent_or_skip() -> Path:
    if not PARENT.is_file():
        pytest.skip(ARCHIVE_UNAVAILABLE)
    return PARENT


def test_revision_parent_is_the_signed_git_baseline() -> None:
    record = pin()
    assert sha256_of(REVISION_PARENT) == record["previous_parent_baseline"]["sha256"] == REVISION_PARENT_SHA256
    assert REVISION_PARENT.stat().st_size == record["previous_parent_baseline"]["size"]
    assert read_manifest(REVISION_PARENT)["data_version"] == "2026.10-published.4"


def test_every_definition_is_byte_identical_to_the_parent_baseline() -> None:
    """Historical .3→.4 source removal left all definitions untouched."""
    parent = _parent_or_skip()
    parent_defs = definitions_of(parent)
    pinned_defs = definitions_of(REVISION_PARENT)

    assert len(parent_defs) == len(pinned_defs) == 48
    assert set(parent_defs) == set(pinned_defs), (
        f"定义键集合发生变化：丢失 {sorted(set(parent_defs) - set(pinned_defs))}；"
        f"新增 {sorted(set(pinned_defs) - set(parent_defs))}"
    )
    differences = [
        name
        for key, (name, payload) in parent_defs.items()
        if pinned_defs[key][1] != payload
    ]
    assert not differences, f"定义成员字节不同：{differences}"

    # The parent already carries GB29446 r2 (approved option B); the去原文 build
    # must not have rolled it back or re-derived it.
    parent_gb = [key for key in parent_defs if key[0] == TARGET]
    pinned_gb = [key for key in pinned_defs if key[0] == TARGET]
    assert len(parent_gb) == 1 and parent_gb[0][2] == 2, parent_gb
    assert pinned_gb == parent_gb, pinned_gb


def test_only_sources_were_removed_from_the_parent_baseline() -> None:
    """Historical .3→.4 transition removed only sources/* members."""
    parent = _parent_or_skip()
    parent_members = content_members(parent)
    pinned_members = content_members(REVISION_PARENT)

    removed = sorted(set(parent_members) - set(pinned_members))
    added = sorted(set(pinned_members) - set(parent_members))
    changed = sorted(
        name
        for name in set(parent_members) & set(pinned_members)
        if parent_members[name] != pinned_members[name]
    )

    assert added == [], f"去原文版本不得新增成员：{added}"
    assert changed == [], f"去原文版本不得改动成员：{changed}"
    assert removed, "父基线应当有 sources/* 成员被移除"
    assert all(name.startswith("sources/") for name in removed), (
        f"只允许移除 sources/*，实际移除：{[n for n in removed if not n.startswith('sources/')]}"
    )
    assert len(removed) == 48, f"sources/* 成员数应为 48，实际 {len(removed)}"
    assert all(name.lower().endswith(".pdf") for name in removed), removed

    # corrections.json must be explicitly byte-identical (it is the only
    # non-definition, non-source member).
    assert parent_members["corrections.json"] == pinned_members["corrections.json"]

    # ... and the manifest must agree on counts.
    parent_manifest = read_manifest(parent)
    pinned_manifest = read_manifest(REVISION_PARENT)
    assert pinned_manifest["standard_count"] == parent_manifest["standard_count"] == 48
    assert pinned_manifest["rule_count"] == parent_manifest["rule_count"] == 765
    assert pinned_manifest["data_version"] != parent_manifest["data_version"]
    assert pinned_manifest["package_id"] != parent_manifest["package_id"]


def test_historical_point_five_changes_only_gb29446_definition() -> None:
    """The signed r3 package keeps the other 47 definitions byte-identical."""
    parent_defs = definitions_of(REVISION_PARENT)
    current_defs = definitions_of(CURRENT_REVISION_PARENT)
    parent_target = [key for key in parent_defs if key[0] == TARGET]
    current_target = [key for key in current_defs if key[0] == TARGET]
    assert len(parent_defs) == len(current_defs) == 48
    assert len(parent_target) == len(current_target) == 1
    assert parent_target[0][2] == 2
    assert current_target[0][2] == 3
    assert set(parent_defs) - {parent_target[0]} == set(current_defs) - {current_target[0]}
    for key in set(parent_defs) - {parent_target[0]}:
        assert parent_defs[key] == current_defs[key], key
    parent_members = content_members(REVISION_PARENT)
    current_members = content_members(CURRENT_REVISION_PARENT)
    assert set(parent_members) - set(current_members) == {parent_defs[parent_target[0]][0]}
    assert set(current_members) - set(parent_members) == {current_defs[current_target[0]][0]}
    for name in set(parent_members) & set(current_members):
        assert parent_members[name] == current_members[name], name
    assert read_manifest(CURRENT_REVISION_PARENT)["source_policy"] == "provenance-only"
    assert read_manifest(CURRENT_REVISION_PARENT)["data_version"] == "2026.10-published.5"


def test_pinned_data_version_sorts_after_the_retired_one() -> None:
    """版本约定 YYYY.MM-channel.revision 下，新包必须排在旧包之后。"""
    import sys

    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from uebench.infrastructure.packages import _data_version_key

    record = pin()
    new_key = _data_version_key(record["data_version"])
    old_key = _data_version_key(record["parent_baseline"]["data_version"])
    assert new_key is not None and old_key is not None
    assert new_key > old_key, (
        f"{record['data_version']} 必须排在 {record['parent_baseline']['data_version']} 之后"
    )


def test_pin_records_the_approval_constraints() -> None:
    record = pin()
    resolution = record["source_removal_resolution"]
    assert resolution["changed_members"] == []
    assert resolution["added_members"] == []
    assert resolution["removed_member_count"] == 48
    assert resolution["parent_data_version"] == "2026.10-published.3"
    assert "不分发" in resolution["decision"]
    assert "0.2.0" in resolution["decision"]
    assert "provenance-only" in resolution["summary"]
    # The legacy confirmation workbook must never be the source of a rebuild.
    assert "统一标准规则确认表" in resolution["not_used"]
    assert "未读取" in resolution["not_used"] or "未使用" in resolution["not_used"]

    # The historical option-B record is kept, still describing the r1→r2 swap.
    history = record["revision_gap_resolution"]
    assert history["removed_members"] == ["definitions/gb-29446-2019-2019.json"]
    assert history["added_members"] == ["definitions/gb-29446-2019-2019-r2.json"]
    assert history["changed_members"] == []


def test_current_revision_changes_only_gb16780_definition() -> None:
    """.5→.6只同步水泥r2定义；保留旧选煤历史证明和其余47定义原字节。"""
    assert sha256_of(CURRENT_REVISION_PARENT) == CURRENT_REVISION_PARENT_SHA256
    record = pin()
    assert record["parent_baseline"]["sha256"] == CURRENT_REVISION_PARENT_SHA256
    parent_defs = definitions_of(CURRENT_REVISION_PARENT)
    current_defs = definitions_of(PINNED)
    old_key = next(key for key in parent_defs if key[0] == "gb-16780-2021")
    new_key = next(key for key in current_defs if key[0] == "gb-16780-2021")
    assert old_key[2] == 1 and new_key[2] == 2
    assert len(parent_defs) == len(current_defs) == 48
    assert set(parent_defs) - {old_key} == set(current_defs) - {new_key}
    for key in set(parent_defs) - {old_key}:
        assert parent_defs[key] == current_defs[key], key
    parent_members = content_members(CURRENT_REVISION_PARENT)
    current_members = content_members(PINNED)
    assert set(parent_members) - set(current_members) == {parent_defs[old_key][0]}
    assert set(current_members) - set(parent_members) == {current_defs[new_key][0]}
    for name in set(parent_members) & set(current_members):
        assert parent_members[name] == current_members[name], name
    assert read_manifest(PINNED)["data_version"] == "2026.10-published.6"
    assert read_manifest(PINNED)["rule_count"] == read_manifest(CURRENT_REVISION_PARENT)["rule_count"] == 765
    assert record["current_revision_resolution"]["formal_evaluation_standard_ids"] == ["gb-29446-2019"]
    assert record["compatibility_boundary"]["old_install_upgrade_performed"] is False
    assert "extra_forbidden" in record["compatibility_boundary"]["legacy_source_probe"]
