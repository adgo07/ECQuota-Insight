"""A revision may be cut from a provenance-only parent without adding PDFs."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.build_gb29446_package_revision import build_revision_package, verify_revision_package


ROOT = Path(__file__).resolve().parents[1]


def test_revision_from_source_free_parent_preserves_no_pdf_policy(tmp_path: Path) -> None:
    parent = ROOT / "release/standard-packages/initial-standard-package-published.uebench"
    with zipfile.ZipFile(parent) as archive:
        parent_version = json.loads(archive.read("manifest.json"))["data_version"]
    prefix, revision = parent_version.rsplit(".", 1)
    next_version = f"{prefix}.{int(revision) + 1}"
    definition = json.loads((ROOT / "data/definitions/gb-29446-2019.json").read_text(encoding="utf-8"))
    definition["rule_revision"] += 1
    definition_path = tmp_path / "definition.json"
    definition_path.write_text(json.dumps(definition, ensure_ascii=False), encoding="utf-8")
    test_key = tmp_path / "ephemeral-test-key.pem"
    test_key.write_bytes(Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    candidate = tmp_path / "test-only.uebench"

    result = build_revision_package(
        parent, definition_path, test_key, candidate,
        data_version=next_version, minimum_app_version="0.2.0",
        package_id="test-only-do-not-publish",
    )
    verification = verify_revision_package(parent, candidate)

    assert result["source_free"] is True
    assert verification["valid"] is True, verification["problems"]
    with zipfile.ZipFile(candidate) as archive:
        assert not any(name.startswith("sources/") for name in archive.namelist())
        assert json.loads(archive.read("manifest.json"))["source_policy"] == "provenance-only"

    reused_version = tmp_path / "invalid-reused-version.uebench"
    build_revision_package(
        parent, definition_path, test_key, reused_version,
        data_version=parent_version, minimum_app_version="0.2.0",
        package_id="test-only-reused-version",
    )
    invalid = verify_revision_package(parent, reused_version)
    assert invalid["valid"] is False
    assert "data_version 未变更" in invalid["problems"]


def test_explicit_cement_target_preserves_all_other_members_and_signature(tmp_path: Path) -> None:
    from tools.build_gb29446_package_revision import canonical_definition_payload
    from uebench.domain.models import StandardDefinition
    parent = ROOT / "release/standard-packages/initial-standard-package-published.uebench"
    with zipfile.ZipFile(parent) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        old_members = {name: archive.read(name) for name in archive.namelist()}
    old_path = next(entry["path"] for entry in manifest["files"] if entry["kind"] == "definition"
                    and json.loads(old_members[entry["path"]])["id"] == "gb-16780-2021")
    definition = json.loads((ROOT / "data/definitions/gb-16780-2021.json").read_text(encoding="utf-8"))
    definition["rule_revision"] = json.loads(old_members[old_path])["rule_revision"] + 1
    source = tmp_path / "cement.json"
    source.write_text(json.dumps(definition, ensure_ascii=False), encoding="utf-8")
    key = Ed25519PrivateKey.generate()
    private = tmp_path / "ephemeral.pem"
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    candidate = tmp_path / "cement-only-test.uebench"
    prefix, revision = manifest["data_version"].rsplit(".", 1)
    result = build_revision_package(parent, source, private, candidate, data_version=f"{prefix}.{int(revision)+1}",
        minimum_app_version="0.2.0", target_standard_id="gb-16780-2021")
    verification = verify_revision_package(parent, candidate, target_standard_id="gb-16780-2021")
    assert verification["valid"], verification["problems"]
    assert result["target_standard_id"] == "gb-16780-2021"
    assert result["standard_count"] == manifest["standard_count"] == 48
    assert result["rule_count"] == manifest["rule_count"]
    with zipfile.ZipFile(candidate) as archive:
        key.public_key().verify(archive.read("signature.ed25519"), archive.read("manifest.json"))
        assert archive.read(result["added_definition_member"]) == canonical_definition_payload(StandardDefinition.model_validate(definition))
        for name, payload in old_members.items():
            if name not in {old_path, "manifest.json", "signature.ed25519"}:
                assert archive.read(name) == payload
        assert not any(name.startswith("sources/") for name in archive.namelist())


def test_revision_target_must_match_source_and_exist_in_parent(tmp_path: Path) -> None:
    import pytest
    parent = ROOT / "release/standard-packages/initial-standard-package-published.uebench"
    source = tmp_path / "definition.json"
    definition = json.loads((ROOT / "data/definitions/gb-16780-2021.json").read_text(encoding="utf-8"))
    source.write_text(json.dumps(definition), encoding="utf-8")
    output = tmp_path / "not-written.uebench"
    with pytest.raises(SystemExit, match="待替换定义不是"):
        build_revision_package(parent, source, tmp_path / "no-key", output, data_version="2026.10-published.999",
            minimum_app_version="0.2.0")
    definition["id"] = "gb-test-not-in-parent"
    source.write_text(json.dumps(definition), encoding="utf-8")
    with pytest.raises(SystemExit, match="定义成员数应为 1"):
        build_revision_package(parent, source, tmp_path / "no-key", output, data_version="2026.10-published.999",
            minimum_app_version="0.2.0", target_standard_id="gb-test-not-in-parent")
    assert not output.exists()
