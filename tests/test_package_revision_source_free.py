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
