"""ECQ-RS05 §五 —— source-free (provenance-only) standard packages.

Owner decision for 0.2.0: the product must **not** distribute, store or open
full standard PDFs.  Before this change the shipped package carried 48
``sources/*.pdf`` members and ``StandardPackageService.install()`` copied them
into ``paths.standards/<package_id>/`` — i.e. installing the product's own
standard package wrote 48 PDFs into the user's data directory.

These tests pin the replacement behaviour:

* a source-free package previews and installs, and writes **no** PDF;
* its definitions and ``corrections.json`` are byte-identical to the same build
  with sources (only ``sources/*`` differ);
* ``source_policy`` is recorded in the manifest, so a consumer can tell a
  source-free package from a source-bearing one without guessing;
* **legacy packages that DO carry ``sources/*`` keep working unchanged** —
  preview and install verify every listed file exactly as before (a tampered
  ``sources/*`` member is still rejected).  What changed by owner decision is
  only the *user data lifecycle*: ``install()`` no longer copies any source
  file into ``paths.standards/<package_id>/``, for **any** package, so a legacy
  package cannot put standard PDFs into the user data directory either.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from uebench.domain.models import PublicationStatus, StandardDefinition
from uebench.infrastructure.backup import BackupService
from uebench.infrastructure.database import DatabaseManager
from uebench.infrastructure.packages import (
    PackageManifest,
    StandardPackageBuilder,
    StandardPackageError,
    StandardPackageService,
)
from uebench.infrastructure.paths import AppPaths
from uebench.infrastructure.repositories import AuditRepository, SqlStandardRepository

from .test_engine import make_standard

ISSUED_AT = datetime(2026, 10, 5, tzinfo=timezone.utc)
GHOST = "signature.ed25519"
STRUCTURAL = {"manifest.json", GHOST}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _definition_with_source(tmp_path: Path, *, rule_revision: int = 1) -> tuple[StandardDefinition, Path]:
    """A published definition plus a real source file whose hash it records."""
    definition = make_standard()
    definition.rule_revision = rule_revision
    definition.publication_status = PublicationStatus.PUBLISHED
    source = tmp_path / definition.source_file
    source.write_bytes(b"%PDF-1.4 placeholder standard original")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    definition.source_sha256 = digest
    for product in definition.products:
        for indicator in product.indicators:
            for reference in indicator.source_references:
                reference.source_sha256 = digest
                reference.source_file = definition.source_file
                reference.standard_number = definition.number
    return definition, source


def _make_service(tmp_path: Path, private_key: Ed25519PrivateKey):
    paths = AppPaths.from_root(tmp_path / "appdata")
    paths.ensure()
    database = DatabaseManager(paths.database)
    database.initialize()
    audit = AuditRepository(database)
    backup = BackupService(paths, database, audit)
    standards = SqlStandardRepository(database, audit)
    service = StandardPackageService(
        paths, database, private_key.public_key(), backup, standards, audit
    )
    return paths, database, standards, service


def _members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _content_members(path: Path) -> dict[str, bytes]:
    return {name: data for name, data in _members(path).items() if name not in STRUCTURAL}


def _manifest_of(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("manifest.json"))


def _build_pair(tmp_path: Path, private_key: Ed25519PrivateKey, *, package_prefix: str):
    """Build the SAME catalogue twice: with sources and without."""
    definition, source = _definition_with_source(tmp_path)
    with_sources = StandardPackageBuilder(private_key).build(
        tmp_path / f"{package_prefix}-with-sources.uebench",
        [definition],
        {definition.source_file: source},
        data_version="2026.10-published.4",
        package_id=f"{package_prefix}-embedded",
        issued_at=ISSUED_AT,
        corrections=[{"id": "corr-1", "note": "勘误"}],
    )
    without_sources = StandardPackageBuilder(private_key).build(
        tmp_path / f"{package_prefix}-source-free.uebench",
        [definition],
        None,
        data_version="2026.10-published.5",
        package_id=f"{package_prefix}-provenance-only",
        issued_at=ISSUED_AT,
        corrections=[{"id": "corr-1", "note": "勘误"}],
        distribute_sources=False,
    )
    return definition, source, with_sources, without_sources


# --------------------------------------------------------------------------
# 1. A source-free package is buildable, previews and installs
# --------------------------------------------------------------------------


def test_source_free_package_previews_and_installs_without_writing_pdfs(
    tmp_path: Path,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    paths, _, standards, service = _make_service(tmp_path, private_key)
    _definition, _source, _embedded, source_free = _build_pair(
        tmp_path, private_key, package_prefix="sf"
    )

    report = service.preview(source_free)
    assert report.valid, report.errors
    assert report.manifest is not None
    assert report.manifest.source_policy == "provenance-only"
    assert report.manifest.package_mode == "full"
    assert report.manifest.standard_count == 1

    result = service.install(source_free)
    assert result.standards_installed == 1

    destination = paths.standards / result.package_id
    assert destination.is_dir()
    written = sorted(path.name for path in destination.iterdir())
    assert written == ["corrections.json"], f"安装目录出现非预期文件：{written}"
    assert list(destination.rglob("*.pdf")) == [], (
        "安装去原文包不得向用户数据目录写入任何 PDF"
    )
    assert standards.get_published(report.definitions[0].id) is not None

def test_source_free_package_has_no_source_member_or_manifest_entry(
    tmp_path: Path,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    _definition, _source, _embedded, source_free = _build_pair(
        tmp_path, private_key, package_prefix="sf-nosource"
    )

    members = _members(source_free)
    assert not [name for name in members if name.startswith("sources/")]
    assert not [name for name in members if name.lower().endswith(".pdf")]

    manifest = _manifest_of(source_free)
    assert manifest["source_policy"] == "provenance-only"
    assert [entry for entry in manifest["files"] if entry["kind"] == "source"] == []
    # ... and every listed file is a real, correctly hashed member.
    assert {entry["path"] for entry in manifest["files"]} == set(members) - STRUCTURAL
    for entry in manifest["files"]:
        payload = members[entry["path"]]
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"]
        assert len(payload) == entry["size"]


def test_provenance_stays_on_the_definitions_of_a_source_free_package(
    tmp_path: Path,
) -> None:
    """Only the *distribution* of the原文 is removed; provenance must survive."""
    private_key = Ed25519PrivateKey.generate()
    definition, source, _embedded, source_free = _build_pair(
        tmp_path, private_key, package_prefix="sf-prov"
    )
    payload = next(
        data for name, data in _members(source_free).items() if name.startswith("definitions/")
    )
    parsed = StandardDefinition.model_validate_json(payload)
    assert parsed.source_file == definition.source_file
    assert parsed.source_sha256 == definition.source_sha256
    assert parsed.source_sha256.lower() == hashlib.sha256(source.read_bytes()).hexdigest()
    for product in parsed.products:
        for indicator in product.indicators:
            assert indicator.source_references, "指标必须保留原文依据"
            for reference in indicator.source_references:
                assert reference.source_file == parsed.source_file
                assert reference.source_sha256.lower() == parsed.source_sha256.lower()


def test_definitions_and_corrections_are_byte_identical_to_the_embedded_build(
    tmp_path: Path,
) -> None:
    """The only difference between the two modes must be the sources/* members."""
    private_key = Ed25519PrivateKey.generate()
    _definition, _source, embedded, source_free = _build_pair(
        tmp_path, private_key, package_prefix="sf-identical"
    )
    embedded_members = _content_members(embedded)
    free_members = _content_members(source_free)

    removed = sorted(set(embedded_members) - set(free_members))
    added = sorted(set(free_members) - set(embedded_members))
    changed = sorted(
        name
        for name in set(embedded_members) & set(free_members)
        if embedded_members[name] != free_members[name]
    )
    assert all(name.startswith("sources/") for name in removed), removed
    assert removed, "含原文包应当有 sources/* 成员"
    assert added == [], f"去原文包不得新增成员：{added}"
    assert changed == [], f"去原文包不得改动成员：{changed}"

    embedded_definitions = {
        name: data for name, data in embedded_members.items() if name.startswith("definitions/")
    }
    free_definitions = {
        name: data for name, data in free_members.items() if name.startswith("definitions/")
    }
    assert embedded_definitions == free_definitions
    assert embedded_members["corrections.json"] == free_members["corrections.json"]


def test_source_free_manifest_signature_verifies_with_a_public_key(
    tmp_path: Path,
) -> None:
    """A real Ed25519 verification of the source-free manifest."""
    pytest.importorskip("cryptography")
    from cryptography.exceptions import InvalidSignature

    private_key = Ed25519PrivateKey.generate()
    _definition, _source, _embedded, source_free = _build_pair(
        tmp_path, private_key, package_prefix="sf-sig"
    )
    members = _members(source_free)
    try:
        private_key.public_key().verify(members[GHOST], members["manifest.json"])
    except InvalidSignature:  # pragma: no cover - would be a real failure
        pytest.fail("去原文包的 Ed25519 签名无法验证")
    assert PackageManifest.model_validate_json(members["manifest.json"]).source_policy == (
        "provenance-only"
    )


def test_pinned_release_package_signature_verifies_with_the_shipped_public_key() -> None:
    """The real release input, not a synthetic build: shipped key must verify it."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization

    root = Path(__file__).resolve().parents[1]
    package = root / "release" / "standard-packages" / "initial-standard-package-published.uebench"
    assert package.is_file(), f"缺少固定的正式标准包：{package}"
    public_key = serialization.load_pem_public_key(
        (root / "src" / "uebench" / "resources" / "update_public_key.pem").read_bytes()
    )
    with zipfile.ZipFile(package) as archive:
        manifest_bytes = archive.read("manifest.json")
        signature = archive.read(GHOST)
    try:
        public_key.verify(signature, manifest_bytes)
    except InvalidSignature:  # pragma: no cover - would be a real failure
        pytest.fail("正式标准包的 Ed25519 签名无法用随产品发布的公钥验证")
    manifest = PackageManifest.model_validate_json(manifest_bytes)
    assert manifest.source_policy == "provenance-only"
    assert manifest.minimum_app_version == "0.2.0"


# --------------------------------------------------------------------------
# 2. Builder contract
# --------------------------------------------------------------------------


def test_builder_refuses_sources_for_a_provenance_only_package(tmp_path: Path) -> None:
    """Supplying原文 together with distribute_sources=False is a builder mistake."""
    private_key = Ed25519PrivateKey.generate()
    definition, source = _definition_with_source(tmp_path)
    with pytest.raises(StandardPackageError, match="不写入 sources"):
        StandardPackageBuilder(private_key).build(
            tmp_path / "contradiction.uebench",
            [definition],
            {definition.source_file: source},
            data_version="2026.10-published.6",
            package_id="contradiction",
            issued_at=ISSUED_AT,
            distribute_sources=False,
        )


def test_embedded_build_still_hard_fails_on_a_missing_source(tmp_path: Path) -> None:
    """The default mode keeps its guard: no silent drop of a standard原文."""
    private_key = Ed25519PrivateKey.generate()
    definition, _source = _definition_with_source(tmp_path)
    with pytest.raises(StandardPackageError, match="缺少标准原文"):
        StandardPackageBuilder(private_key).build(
            tmp_path / "missing-source.uebench",
            [definition],
            {},
            data_version="2026.10-published.7",
            package_id="missing-source",
            issued_at=ISSUED_AT,
        )


def test_source_free_incremental_package_is_supported(tmp_path: Path) -> None:
    """The incremental path accepts the same mode, inheriting it from the child."""
    private_key = Ed25519PrivateKey.generate()
    _paths, _database, _standards, service = _make_service(tmp_path, private_key)
    definition, source = _definition_with_source(tmp_path)
    parent = StandardPackageBuilder(private_key).build(
        tmp_path / "inc-parent.uebench",
        [definition],
        {definition.source_file: source},
        data_version="2026.10-published.8",
        package_id="inc-parent",
        issued_at=ISSUED_AT,
    )
    changed = definition.model_copy(deep=True)
    changed.rule_revision = 2
    changed.products[0].indicators[0].thresholds.level_1.value = "11"

    child = StandardPackageBuilder(private_key).build_incremental(
        tmp_path / "inc-child.uebench",
        [changed],
        None,
        parent_package=parent,
        data_version="2026.10-published.9",
        package_id="inc-child",
        issued_at=ISSUED_AT,
        distribute_sources=False,
    )
    manifest = _manifest_of(child)
    assert manifest["source_policy"] == "provenance-only"
    assert manifest["package_mode"] == "incremental"
    assert [entry for entry in manifest["files"] if entry["kind"] == "source"] == []

    service.install(parent)
    report = service.preview(child)
    assert report.valid, report.errors
    service.install(child)


# --------------------------------------------------------------------------
# 3. Backward compatibility: legacy source-bearing packages keep installing
#    (but never write原文 into the user data directory)
# --------------------------------------------------------------------------


def test_legacy_source_bearing_package_still_previews_and_installs(
    tmp_path: Path,
) -> None:
    """The historical embedded layout must keep working, verification included.

    Owner decision: the software must not keep full standard PDFs in the user
    data directory.  ``install()`` therefore no longer copies ``sources/*``
    members for a legacy package either — while still hash-verifying every
    declared file during preview/install.
    """
    private_key = Ed25519PrivateKey.generate()
    paths, _database, _standards, service = _make_service(tmp_path, private_key)
    _definition, _source, embedded, _source_free = _build_pair(
        tmp_path, private_key, package_prefix="legacy"
    )

    members = _members(embedded)
    manifest = _manifest_of(embedded)
    assert manifest["source_policy"] == "embedded"
    source_entries = [entry for entry in manifest["files"] if entry["kind"] == "source"]
    assert len(source_entries) == 1
    # 用例前提：包里确实携带（并声明）了原文，且逐文件哈希可复核。
    assert [name for name in members if name.startswith("sources/")], sorted(members)
    assert all(entry["path"].startswith("sources/") for entry in source_entries)
    for entry in source_entries:
        payload = members[entry["path"]]
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"]

    report = service.preview(embedded)
    assert report.valid, report.errors
    assert report.manifest is not None
    assert report.manifest.source_policy == "embedded"

    result = service.install(embedded)
    destination = paths.standards / result.package_id
    assert destination.is_dir()
    # 契约更新（owner decision）：安装不再把任何原文写入用户数据目录。
    assert list(destination.rglob("*.pdf")) == [], (
        "含原文旧包同样不得向用户数据目录写入 PDF"
    )
    assert not (destination / "sources").exists(), "安装目录不得出现 sources/ 子目录"
    assert list(destination.rglob("*")) == [destination / "corrections.json"], (
        "安装目录只应保留非原文产物："
        f"{sorted(path.name for path in destination.rglob('*'))}"
    )
    assert result.removed_source_directory_count == 0
    assert result.removed_source_file_count == 0


def test_legacy_manifest_without_source_policy_defaults_to_embedded() -> None:
    """An archived manifest predates the field: absence must mean 'embedded'."""
    manifest = PackageManifest(
        package_id="legacy-without-field",
        data_version="2026.09-published.2",
        issued_at=ISSUED_AT,
        minimum_app_version="0.1.0",
        package_mode="full",
        standard_count=0,
        rule_count=0,
        files=[],
    )
    assert manifest.source_policy == "embedded"
    serialized = json.loads(manifest.model_dump_json())
    assert serialized["source_policy"] == "embedded"


def test_preview_rejects_a_package_that_claims_provenance_only_but_ships_sources(
    tmp_path: Path,
) -> None:
    """The self-declared mode is enforced, not advisory."""
    private_key = Ed25519PrivateKey.generate()
    _paths, _database, _standards, service = _make_service(tmp_path, private_key)
    _definition, _source, embedded, _source_free = _build_pair(
        tmp_path, private_key, package_prefix="liar"
    )

    members = _members(embedded)
    manifest = json.loads(members["manifest.json"])
    manifest["source_policy"] = "provenance-only"
    manifest_bytes = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    members["manifest.json"] = manifest_bytes
    members[GHOST] = private_key.sign(manifest_bytes)
    tampered = tmp_path / "liar.uebench"
    with zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)

    report = service.preview(tampered)
    assert not report.valid
    assert any("provenance-only" in error for error in report.errors), report.errors


def test_legacy_source_bearing_package_with_a_tampered_source_is_rejected(
    tmp_path: Path,
) -> None:
    """Per-file verification of ``sources/*`` is still mandatory for旧包."""
    private_key = Ed25519PrivateKey.generate()
    _paths, _database, _standards, service = _make_service(tmp_path, private_key)
    _definition, _source, embedded, _source_free = _build_pair(
        tmp_path, private_key, package_prefix="tamper"
    )

    members = _members(embedded)
    source_name = next(name for name in members if name.startswith("sources/"))
    members[source_name] = b"%PDF-1.4 tampered"
    # The manifest still lists the original hash, so preview must flag the member.
    tampered = tmp_path / "tampered.uebench"
    with zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)

    report = service.preview(tampered)
    assert not report.valid
    assert any("哈希不匹配" in error for error in report.errors), report.errors
