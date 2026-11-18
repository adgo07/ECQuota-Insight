"""焦炭显式目标及dry-run；只生成临时合成签名测试件。"""
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tools import build_gb29446_package_revision as tool
from uebench.application.coke_records import candidate_snapshot
from uebench.domain.models import StandardDefinition
from tests.test_cement_package_revision import synthetic, key_file, rewrite, PREDECESSOR, ROOT


@pytest.fixture
def definition(tmp_path):
    base = StandardDefinition.model_validate_json((ROOT / "data/definitions/gb-21342-2025.json").read_text(encoding="utf-8"))
    candidate = candidate_snapshot(base)
    path = tmp_path / "SYNTHETIC-coke-r2.json"
    path.write_text(candidate.model_dump_json(), encoding="utf-8")
    return path


def build(synthetic, definition, tmp_path, **kwargs):
    parent, private, _ = synthetic
    output = tmp_path / "SYNTHETIC-coke-test-only.uebench"
    report = tool.build_revision_package(parent, definition, private, output,
        data_version="2026.11-published.1", minimum_app_version="0.2.0", target_standard_id="gb-21342-2025", **kwargs)
    return output, report


def test_coke_only_one_definition_and_47_original_bytes(synthetic, definition, tmp_path):
    output, report = build(synthetic, definition, tmp_path)
    parent, _, key = synthetic
    verification = tool.verify_revision_package(parent, output, target_standard_id="gb-21342-2025")
    assert verification["valid"], verification["problems"]
    assert report["gb21342_rule_revision"] == 2 and report["standard_count"] == 48
    assert report["rule_count"] == 765
    _, before = tool._read_package(parent)
    raw, after = tool._read_package(output)
    assert len(verification["removed"]) == len(verification["added"]) == 1
    old = verification["removed"][0]
    assert sum(k.startswith("definitions/") and k != old for k in before) == 47
    assert all(before[k] == after[k] for k in before if k not in tool.STRUCTURAL_MEMBERS and k != old)
    key.public_key().verify(after[tool.GHOST_MEMBER], raw)


@pytest.mark.parametrize("change", ["r1", "marker-only", "parameter", "source", "supersedes"])
def test_non_adopted_coke_cannot_sign_or_dry_run(synthetic, definition, tmp_path, change):
    candidate = StandardDefinition.model_validate_json(definition.read_text(encoding="utf-8"))
    if change == "r1": candidate.rule_revision = 1
    elif change == "marker-only": candidate.coke_rule_parameters = None
    elif change == "parameter": candidate.coke_rule_parameters["assessment"]["external_adjustment"] = "27"
    elif change == "source": candidate.source_sha256 = "f"*64
    else: candidate.supersedes = []
    definition.write_text(candidate.model_dump_json(), encoding="utf-8")
    for dry_run in (False, True):
        with pytest.raises(SystemExit, match="焦炭替换定义"):
            build(synthetic, definition, tmp_path, dry_run=dry_run)
    assert not (tmp_path / "SYNTHETIC-coke-test-only.uebench").exists()


def test_wrong_key_and_missing_key_cannot_write(synthetic, definition, tmp_path):
    parent, _, _ = synthetic
    output = tmp_path / "must-not-exist"
    for private in (key_file(tmp_path / "other.pem", Ed25519PrivateKey.generate()), tmp_path / "absent", None):
        with pytest.raises(SystemExit, match="不匹配|缺少本地开发签名私钥"):
            tool.build_revision_package(parent, definition, private, output, data_version="2026.11-published.1",
                minimum_app_version="0.2.0", target_standard_id="gb-21342-2025")
        assert not output.exists()


def test_real_trust_parent_dry_run_does_not_read_key_or_write(definition, tmp_path, monkeypatch):
    before = tool._sha256_path(PREDECESSOR)
    monkeypatch.setattr(tool, "_load_signing_key", lambda *_: pytest.fail("dry-run不能读取私钥"))
    output = tmp_path / "must-not-exist"
    report = tool.build_revision_package(PREDECESSOR, definition, None, output, data_version="2026.11-published.1",
        minimum_app_version="0.2.0", target_standard_id="gb-21342-2025", dry_run=True)
    assert report["dry_run"] and not report["signed"] and not report["output_written"]
    assert report["standard_count"] == 48 and report["unchanged_member_count"] == 48
    assert not output.exists() and tool._sha256_path(PREDECESSOR) == before


@pytest.mark.parametrize("which", ["correction", "definition"])
def test_even_valid_signed_other_content_change_rejected(synthetic, definition, tmp_path, which):
    output, _ = build(synthetic, definition, tmp_path)
    parent, _, key = synthetic
    raw, _ = tool._read_package(output)
    manifest = tool.PackageManifest.model_validate_json(raw)
    entry = next(e for e in manifest.files if e.kind == which and "gb-21342-2025" not in e.path)
    rewrite(output, key, change_member=entry.path)
    report = tool.verify_revision_package(parent, output, target_standard_id="gb-21342-2025")
    assert not report["valid"] and any("非目标成员内容被改变" in p for p in report["problems"])
