"""Pin the ECQ-RS05 standard-package revision (approved option B).

The Candidate bundles a **new** signed standard package derived from the
published ``2026.09-published.2`` baseline.  Exactly one member may differ: the
GB 29446—2019 definition (old ``rule_revision=1`` out, current ``rule_revision=2``
in).  Everything else must stay byte-identical, because the approval was
explicit: do not rebuild the other standards, and do not use
``统一标准规则确认表.xlsx`` (LEGACY_REFERENCE_ONLY) to regenerate any rule.

These tests fail loudly if a later change:
* re-pins a package whose GB29446 is not r2 (which would re-break the RS04 Golden),
* silently rewrites any other standard's bytes,
* or lets ``PIN.json`` drift from the file it claims to describe.
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
PARENT = PACKAGE_DIR / "initial-standard-package-2026.09-published.2.uebench"
PIN = PACKAGE_DIR / "PIN.json"

GHOST = "signature.ed25519"
TARGET = "gb-29446-2019"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pin() -> dict:
    return json.loads(PIN.read_text(encoding="utf-8"))


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


def test_pinned_package_matches_pin_json() -> None:
    record = pin()
    assert PINNED.is_file(), "缺少固定的标准包 release input"
    assert PINNED.stat().st_size == record["size"], "标准包大小与 PIN.json 不一致"
    assert sha256_of(PINNED) == record["sha256"], "标准包 SHA256 与 PIN.json 不一致"
    with zipfile.ZipFile(PINNED) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["data_version"] == record["data_version"]
    assert manifest["package_id"] == record["package_id"]
    assert manifest["standard_count"] == record["standard_count"]
    assert manifest["rule_count"] == record["rule_count"]
    assert manifest["package_mode"] == "full"


def test_pinned_package_gb29446_is_revision_2_with_coal_type() -> None:
    """Without this the RS04 Product Golden Applicability Gate fails again."""
    with zipfile.ZipFile(PINNED) as archive:
        members = [n for n in archive.namelist() if n.startswith("definitions/gb-29446")]
        assert len(members) == 1, f"GB29446 定义成员应唯一，实际 {members}"
        definition = json.loads(archive.read(members[0]))
    assert definition["rule_revision"] == 2, "固定标准包内 GB29446 必须是 r2"
    assert [entry["key"] for entry in definition["selection_schema"]] == ["coal_type"]
    assert all(
        "coal_type" in (product.get("selection_values") or {})
        for product in definition["products"]
    )


def test_only_gb29446_differs_from_the_parent_baseline() -> None:
    record = pin()
    assert PARENT.is_file(), "缺少父基线标准包"
    assert sha256_of(PARENT) == record["parent_baseline"]["sha256"], (
        "父基线标准包被修改；它必须保持为已发布资产的逐字节副本"
    )

    parent_defs = definitions_of(PARENT)
    pinned_defs = definitions_of(PINNED)

    # The parent carries GB29446 r1; the candidate must not.
    parent_gb = [key for key in parent_defs if key[0] == TARGET]
    assert len(parent_gb) == 1 and parent_gb[0][2] == 1, parent_gb
    pinned_gb = [key for key in pinned_defs if key[0] == TARGET]
    assert len(pinned_gb) == 1 and pinned_gb[0][2] == 2, pinned_gb

    # Every other standard must be present with identical bytes.
    differences: list[str] = []
    for key, (name, payload) in parent_defs.items():
        if key[0] == TARGET:
            continue
        candidate = pinned_defs.get(key)
        if candidate is None:
            differences.append(f"丢失：{name}")
            continue
        if candidate[1] != payload:
            differences.append(f"字节不同：{name}")
    for key, (name, _payload) in pinned_defs.items():
        if key[0] != TARGET and key not in parent_defs:
            differences.append(f"新增：{name}")
    assert not differences, f"除 GB29446 外不应有任何差异：{differences}"


def test_non_definition_members_are_byte_identical() -> None:
    """Sources and corrections.json must be untouched as well."""
    record = pin()
    with zipfile.ZipFile(PARENT) as pa, zipfile.ZipFile(PINNED) as na:
        parent_members = set(pa.namelist()) - {"manifest.json", GHOST}
        pinned_members = set(na.namelist()) - {"manifest.json", GHOST}
        # Only the GB29446 definition member name may move.
        moved = parent_members ^ pinned_members
        assert all(name.startswith("definitions/gb-29446") for name in moved), moved
        for name in sorted(parent_members & pinned_members):
            if name.startswith("definitions/gb-29446"):
                continue
            assert pa.read(name) == na.read(name), f"非目标成员被改动：{name}"
    assert record["revision_gap_resolution"]["changed_members"] == []


def test_pin_records_the_approval_constraints() -> None:
    record = pin()
    resolution = record["revision_gap_resolution"]
    assert "方案 B" in resolution["decision"]
    assert resolution["changed_members"] == []
    assert resolution["removed_members"] == ["definitions/gb-29446-2019-2019.json"]
    assert resolution["added_members"] == ["definitions/gb-29446-2019-2019-r2.json"]
    # The legacy confirmation workbook must never be the source of a rebuild.
    assert "统一标准规则确认表" in resolution["not_used"]
    assert "未读取" in resolution["not_used"] or "未使用" in resolution["not_used"]


def test_pinned_package_signature_verifies_against_the_shipped_public_key(
    tmp_path: Path,
) -> None:
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
