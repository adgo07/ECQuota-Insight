"""水泥受限签包工具。所有生成物均为tmp内合成签名测试件，不能用于发布。"""
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from tools import build_gb29446_package_revision as tool
from uebench.infrastructure.packages import PackageManifest

ROOT = Path(__file__).resolve().parents[1]
REAL_PARENT = ROOT / "release/standard-packages/initial-standard-package-published.uebench"
DEFINITION = ROOT / "standards/development/GB16780-2021/gb-16780-2021-r3-candidate.json"


def key_file(path, key):
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return path


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    key = Ed25519PrivateKey.generate()
    private = key_file(tmp_path / "SYNTHETIC-test-only-private.pem", key)
    public = tmp_path / "SYNTHETIC-test-only-public.pem"
    public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    monkeypatch.setattr(tool, "TRUSTED_PUBLIC_KEY_PATH", public)
    raw, members = tool._read_package(REAL_PARENT)
    manifest = PackageManifest.model_validate_json(raw)
    manifest.package_id = "SYNTHETIC-test-only-parent"
    parent = tmp_path / "SYNTHETIC-test-only-parent.uebench"
    contents = {k: v for k, v in members.items() if k not in tool.STRUCTURAL_MEMBERS}
    tool._write_signed_package(parent, manifest, key, contents)
    return parent, private, key


def build(synthetic, tmp_path, **kwargs):
    parent, private, _ = synthetic
    output = tmp_path / "SYNTHETIC-test-only-candidate.uebench"
    report = tool.build_revision_package(parent, DEFINITION, private, output,
        data_version=kwargs.pop("data_version", "2026.11-published.1"), minimum_app_version="0.2.0",
        target_standard_id="gb-16780-2021", **kwargs)
    return output, report


def rewrite(path, key, *, change_member=None, data_version=None):
    raw, members = tool._read_package(path)
    manifest = PackageManifest.model_validate_json(raw)
    contents = {k: v for k, v in members.items() if k not in tool.STRUCTURAL_MEMBERS}
    if change_member:
        contents[change_member] += b" "  # 语义相同的空白变动也必须被逐字节门禁发现。
        for entry in manifest.files:
            if entry.path == change_member:
                entry.size = len(contents[change_member])
                entry.sha256 = tool._sha256_bytes(contents[change_member])
    if data_version:
        manifest.data_version = data_version
    tool._write_signed_package(path, manifest, key, contents)


def test_cement_explicit_target_changes_only_one_definition_and_keeps_47_bytes(synthetic, tmp_path):
    parent, _, key = synthetic
    candidate, report = build(synthetic, tmp_path)
    verification = tool.verify_revision_package(parent, candidate, target_standard_id="gb-16780-2021")
    assert verification["valid"], verification["problems"]
    assert report["gb16780_rule_revision"] == 3 and report["target_standard_id"] == "gb-16780-2021"
    assert report["standard_count"] == 48 and report["rule_count"] == 765
    _, before = tool._read_package(parent)
    raw, after = tool._read_package(candidate)
    assert len(verification["removed"]) == len(verification["added"]) == 1
    assert verification["changed"] == []
    old = verification["removed"][0]
    new = verification["added"][0]
    assert "gb-16780-2021" in old and "gb-16780-2021" in new
    assert all(before[k] == after[k] for k in before if k not in tool.STRUCTURAL_MEMBERS and k != old)
    assert sum(k.startswith("definitions/") and k != old for k in before) == 47
    assert not any(k.startswith("sources/") or k.endswith(".pdf") for k in after)
    key.public_key().verify(after[tool.GHOST_MEMBER], raw)
    # 证明合成件没有借用/替换产品真实信任根；真实公钥不能把它当发布包。
    real_public = serialization.load_pem_public_key((ROOT / "src/uebench/resources/update_public_key.pem").read_bytes())
    with pytest.raises(InvalidSignature):
        real_public.verify(after[tool.GHOST_MEMBER], raw)


@pytest.mark.parametrize("which", ["correction", "unrelated-definition"])
def test_even_validly_signed_unrelated_content_change_is_rejected(synthetic, tmp_path, which):
    candidate, _ = build(synthetic, tmp_path)
    parent, _, key = synthetic
    raw, _ = tool._read_package(candidate)
    manifest = PackageManifest.model_validate_json(raw)
    entry = next(e for e in manifest.files if e.kind == ("correction" if which == "correction" else "definition")
                 and "gb-16780-2021" not in e.path)
    rewrite(candidate, key, change_member=entry.path)
    result = tool.verify_revision_package(parent, candidate, target_standard_id="gb-16780-2021")
    assert not result["valid"] and any("非目标成员内容被改变" in p for p in result["problems"])


@pytest.mark.parametrize("version", ["2026.10-published.5", "2026.10-published.4"])
def test_cement_build_refuses_reused_or_older_version_before_output(synthetic, tmp_path, version):
    with pytest.raises(SystemExit, match="必须晚于"):
        build(synthetic, tmp_path, data_version=version)
    assert not (tmp_path / "SYNTHETIC-test-only-candidate.uebench").exists()


def test_cement_verifier_refuses_signed_version_downgrade(synthetic, tmp_path):
    candidate, _ = build(synthetic, tmp_path)
    parent, _, key = synthetic
    rewrite(candidate, key, data_version="2026.10-published.4")
    result = tool.verify_revision_package(parent, candidate, target_standard_id="gb-16780-2021")
    assert not result["valid"] and "水泥新data_version必须晚于父基线" in result["problems"]


def test_wrong_signing_key_is_rejected_before_candidate_written(synthetic, tmp_path):
    parent, _, _ = synthetic
    other = key_file(tmp_path / "SYNTHETIC-other-private.pem", Ed25519PrivateKey.generate())
    output = tmp_path / "wrong-key.uebench"
    with pytest.raises(SystemExit, match="不匹配"):
        tool.build_revision_package(parent, DEFINITION, other, output, data_version="2026.11-published.1",
            minimum_app_version="0.2.0", target_standard_id="gb-16780-2021")
    assert not output.exists()


def test_real_trust_root_with_missing_private_key_is_a_clear_blocker(tmp_path):
    output = tmp_path / "must-not-exist.uebench"
    with pytest.raises(SystemExit, match="缺少本地开发签名私钥"):
        tool.build_revision_package(REAL_PARENT, DEFINITION, tmp_path / "missing.pem", output,
            data_version="2026.11-published.1", minimum_app_version="0.2.0", target_standard_id="gb-16780-2021")
    assert not output.exists()
    assert tool.TRUSTED_PUBLIC_KEY_PATH == ROOT / "src/uebench/resources/update_public_key.pem"


def test_real_pin_parent_is_readonly_verified_with_shipped_trust_root():
    import json
    before = tool._sha256_path(REAL_PARENT)
    pin = json.loads((ROOT / "release/standard-packages/PIN.json").read_text(encoding="utf-8"))
    assert before == pin["sha256"]
    raw, members = tool._read_package(REAL_PARENT)
    assert tool._verify_cement_trust(raw, members) is not None
    assert tool._sha256_path(REAL_PARENT) == before


def test_candidate_bad_signature_is_rejected(synthetic, tmp_path):
    candidate, _ = build(synthetic, tmp_path)
    parent, _, _ = synthetic
    _, members = tool._read_package(candidate)
    members[tool.GHOST_MEMBER] = b"0" * 64
    import zipfile
    with zipfile.ZipFile(candidate, "w") as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    result = tool.verify_revision_package(parent, candidate, target_standard_id="gb-16780-2021")
    assert not result["valid"] and "InvalidSignature" in result["problems"][0]


def test_cement_cannot_be_auto_detected_as_default_coal_target(synthetic, tmp_path):
    parent, private, _ = synthetic
    with pytest.raises(SystemExit, match="不是 gb-29446-2019"):
        tool.build_revision_package(parent, DEFINITION, private, tmp_path / "no-output.uebench",
            data_version="2026.11-published.1", minimum_app_version="0.2.0")


@pytest.mark.parametrize("target", ["gb-00000-2021", "gb-21342-2025", "", "../gb-16780-2021"])
def test_unapproved_target_is_rejected_without_opening_or_writing_files(tmp_path, target):
    with pytest.raises(SystemExit, match="未获本工具授权"):
        tool.build_revision_package(tmp_path / "absent", DEFINITION, tmp_path / "none", tmp_path / "none-output",
            data_version="2026.11-published.1", minimum_app_version="0.2.0", target_standard_id=target)


def test_missing_adoption_marker_cannot_be_signed(synthetic, tmp_path):
    parent, private, _ = synthetic
    from uebench.domain.models import StandardDefinition
    definition = StandardDefinition.model_validate_json(DEFINITION.read_text(encoding="utf-8"))
    definition.corrections = []
    path = tmp_path / "unadopted.json"
    path.write_text(definition.model_dump_json(), encoding="utf-8")
    with pytest.raises(SystemExit, match="明确采用V1.2"):
        tool.build_revision_package(parent, path, private, tmp_path / "none-output", data_version="2026.11-published.1",
            minimum_app_version="0.2.0", target_standard_id="gb-16780-2021")


def test_tampered_parent_content_or_signature_cannot_seed_new_package(synthetic, tmp_path):
    parent, private, _ = synthetic
    raw, members = tool._read_package(parent)
    manifest = PackageManifest.model_validate_json(raw)
    name = next(e.path for e in manifest.files if e.kind == "definition")
    members[name] += b" "
    import zipfile
    with zipfile.ZipFile(parent, "w") as archive:
        for key, value in members.items():
            archive.writestr(key, value)
    output = tmp_path / "none-output"
    with pytest.raises(SystemExit, match="既有信任根/清单校验"):
        tool.build_revision_package(parent, DEFINITION, private, output, data_version="2026.11-published.1",
            minimum_app_version="0.2.0", target_standard_id="gb-16780-2021")
    assert not output.exists()
