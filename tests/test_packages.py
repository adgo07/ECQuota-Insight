from __future__ import annotations

import json
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from uebench.infrastructure.backup import BackupService
from uebench.infrastructure.database import DatabaseManager, PackageRow
from uebench.infrastructure.packages import PackageFile, PackageManifest, StandardPackageBuilder, StandardPackageError, StandardPackageService
from uebench.infrastructure.paths import AppPaths
from uebench.infrastructure.repositories import AuditRepository, SqlStandardRepository
from uebench.domain.models import PublicationStatus, StandardSelectionMode

from .test_engine import make_standard


def make_service(tmp_path: Path, private_key: Ed25519PrivateKey):
    paths = AppPaths.from_root(tmp_path / "appdata")
    paths.ensure()
    database = DatabaseManager(paths.database)
    database.initialize()
    audit = AuditRepository(database)
    backup = BackupService(paths, database, audit)
    standards = SqlStandardRepository(database, audit)
    service = StandardPackageService(paths, database, private_key.public_key(), backup, standards, audit)
    return paths, database, standards, service


def build_package(
    tmp_path: Path,
    private_key: Ed25519PrivateKey,
    *,
    package_id: str = "package-1",
    corrections: list[dict] | None = None,
    level_1: str | None = None,
    rule_revision: int = 1,
    rule_engine_version: str = "1.0",
    package_mode: str = "full",
    parent_package_id: str | None = None,
    data_version: str = "2026.1",
    issued_at: datetime | None = None,
) -> Path:
    definition = make_standard()
    definition.rule_revision = rule_revision
    if level_1 is not None:
        threshold = definition.products[0].indicators[0].thresholds.level_1
        assert threshold is not None
        threshold.value = level_1
    source = tmp_path / definition.source_file
    source.write_bytes(b"placeholder")
    definition.source_sha256 = __import__("hashlib").sha256(source.read_bytes()).hexdigest()
    for product in definition.products:
        for indicator in product.indicators:
            for reference in indicator.source_references:
                reference.source_sha256 = definition.source_sha256
    return StandardPackageBuilder(private_key).build(
        tmp_path / f"{package_id}.uebench",
        [definition],
        {definition.source_file: source},
        package_id=package_id,
        data_version=data_version,
        rule_engine_version=rule_engine_version,
        issued_at=issued_at or datetime(2026, 8, 23, tzinfo=timezone.utc),
        package_mode=package_mode,
        parent_package_id=parent_package_id,
        corrections=corrections,
    )


def test_discover_package_paths_supports_root_and_recursive_shared_directories(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    root = tmp_path / "packages"
    nested = root / "archive"
    nested.mkdir(parents=True)
    (root / "b.uebench").write_bytes(b"b")
    (root / "ignore.txt").write_bytes(b"ignore")
    (nested / "A.UEBENCH").write_bytes(b"a")

    assert [path.name for path in service.discover(root)] == ["b.uebench"]
    assert [path.name for path in service.discover(root, recursive=True)] == ["A.UEBENCH", "b.uebench"]

    with pytest.raises(FileNotFoundError):
        service.discover(root / "missing")

def test_signed_package_preview_and_install(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, standards, service = make_service(tmp_path, private_key)
    package = build_package(tmp_path, private_key)
    report = service.preview(package)
    assert report.valid, report.errors
    result = service.install(package)
    assert result.standards_installed == 1
    assert report.manifest is not None
    assert report.manifest.package_mode == "full"
    assert report.manifest.rule_engine_version == "1.0"
    assert standards.get_published("gb-00000-2026") is not None


def test_package_history_returns_installs_newest_first_as_domain_records(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    parent = build_package(
        tmp_path,
        private_key,
        package_id="history-parent",
        data_version="2026.1",
        issued_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
    )
    child = build_package(
        tmp_path,
        private_key,
        package_id="history-child",
        data_version="2026.2",
        issued_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )
    service.install(parent)
    service.install(child)

    history = service.list_history()
    assert [entry.package_id for entry in history[:2]] == ["history-child", "history-parent"]
    assert history[0].data_version == "2026.2"
    assert history[0].package_mode == "full"
    assert history[0].standard_count == 1
    assert history[0].rule_count >= 1
    assert len(history[0].package_sha256) == 64
    assert service.list_history(1)[0].package_id == "history-child"
    assert service.list_history(0) == []

def test_package_install_retains_correction_record(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    paths, _, _, service = make_service(tmp_path, private_key)
    package = build_package(
        tmp_path,
        private_key,
        corrections=[{"standard": "GB 00000-2026", "note": "勘误"}],
    )
    result = service.install(package)
    correction_files = list(paths.standards.joinpath(result.package_id).glob("corrections.json"))
    assert len(correction_files) == 1
    assert "勘误" in correction_files[0].read_text(encoding="utf-8")


def test_package_tamper_is_rejected(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    package = build_package(tmp_path, private_key)
    with zipfile.ZipFile(package, "a") as archive:
        archive.writestr("definitions/extra.json", b"{}")
    report = service.preview(package)
    assert not report.valid
    assert any("未登记文件" in error for error in report.errors)


def test_wrong_signature_is_rejected(tmp_path: Path) -> None:
    signer = Ed25519PrivateKey.generate()
    verifier = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, verifier)
    package = build_package(tmp_path, signer)
    report = service.preview(package)
    assert not report.valid
    assert any("签名无效" in error for error in report.errors)


def test_duplicate_package_is_rejected(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    package = build_package(tmp_path, private_key)
    service.install(package)
    with pytest.raises(StandardPackageError, match="已安装"):
        service.install(package)


def test_same_standard_version_with_identical_content_is_allowed(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    first = build_package(tmp_path, private_key, package_id="package-first")
    second = build_package(tmp_path, private_key, package_id="package-second")
    service.install(first)
    report = service.preview(second)
    assert report.valid, report.errors
    assert any("内容一致" in warning for warning in report.warnings)
    service.install(second)


def test_same_standard_version_with_changed_content_is_rejected(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    first = build_package(tmp_path, private_key, package_id="package-first")
    second = build_package(tmp_path, private_key, package_id="package-second", level_1="11")
    service.install(first)
    report = service.preview(second)
    assert not report.valid
    assert any("标准版本已存在" in error for error in report.errors)


def test_same_standard_version_with_new_rule_revision_is_allowed(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, standards, service = make_service(tmp_path, private_key)
    first = build_package(tmp_path, private_key, package_id="package-first", rule_revision=1)
    second = build_package(tmp_path, private_key, package_id="package-second", rule_revision=2, level_1="11")
    service.install(first)
    report = service.preview(second)
    assert report.valid, report.errors
    service.install(second)
    assert len(standards.list_all()) == 2


def test_unpublished_definition_is_rejected(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    definition = make_standard()
    definition.publication_status = PublicationStatus.REVIEWED
    source = tmp_path / definition.source_file
    source.write_bytes(b"placeholder")
    definition.source_sha256 = __import__("hashlib").sha256(source.read_bytes()).hexdigest()
    for product in definition.products:
        for indicator in product.indicators:
            for reference in indicator.source_references:
                reference.source_sha256 = definition.source_sha256
    package = StandardPackageBuilder(private_key).build(
        tmp_path / "reviewed.uebench",
        [definition],
        {definition.source_file: source},
        package_id="reviewed-package",
        data_version="2026.1",
        issued_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
    )
    report = service.preview(package)
    assert not report.valid
    assert any("只能包含 published" in error for error in report.errors)


def test_duplicate_definition_version_is_rejected(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    first = make_standard()
    source = tmp_path / first.source_file
    source.write_bytes(b"placeholder")
    digest = __import__("hashlib").sha256(source.read_bytes()).hexdigest()
    first.source_sha256 = digest
    for product in first.products:
        for indicator in product.indicators:
            for reference in indicator.source_references:
                reference.source_sha256 = digest
    duplicate = first.model_copy(deep=True)
    with pytest.raises(StandardPackageError, match="重复标准版本"):
        StandardPackageBuilder(private_key).build(
            tmp_path / "duplicate.uebench",
            [first, duplicate],
            {first.source_file: source},
            package_id="duplicate-package",
            data_version="2026.1",
            issued_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        )

def test_incremental_package_requires_installed_parent(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    package = build_package(
        tmp_path,
        private_key,
        package_id="incremental-without-parent",
        package_mode="incremental",
    )
    report = service.preview(package)
    assert not report.valid
    assert any("缺少 parent_package_id" in error for error in report.errors)


def test_incremental_package_must_follow_current_parent(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    first = build_package(tmp_path, private_key, package_id="parent-package")
    service.install(first)
    child = build_package(
        tmp_path,
        private_key,
        package_id="incremental-child",
        package_mode="incremental",
        parent_package_id="not-installed",
    )
    report = service.preview(child)
    assert not report.valid
    assert any("父包未安装" in error for error in report.errors)


def test_incremental_package_accepts_current_parent(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    first = build_package(tmp_path, private_key, package_id="parent-package")
    service.install(first)
    child = build_package(
        tmp_path,
        private_key,
        package_id="incremental-child",
        package_mode="incremental",
        parent_package_id="parent-package",
    )
    report = service.preview(child)
    assert report.valid, report.errors


def test_package_with_unknown_rule_engine_is_rejected(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    package = build_package(tmp_path, private_key, rule_engine_version="999.0")
    report = service.preview(package)
    assert not report.valid
    assert any("规则引擎版本" in error for error in report.errors)

def test_package_file_kind_and_manifest_lineage_are_rejected() -> None:
    with pytest.raises(ValueError, match="definition"):
        PackageFile(path="sources/source.pdf", sha256="0" * 64, size=1, kind="definition")
    with pytest.raises(ValueError, match="完整标准包"):
        PackageManifest(
            package_id="full-with-parent",
            data_version="2026.1",
            issued_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
            minimum_app_version="0.1.0",
            package_mode="full",
            parent_package_id="parent-package",
            standard_count=0,
            rule_count=0,
            files=[],
        )

def test_full_package_new_revision_selects_new_rule_and_keeps_history(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, standards, service = make_service(tmp_path, private_key)
    first = build_package(
        tmp_path,
        private_key,
        package_id="full-parent",
        rule_revision=1,
        issued_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
    )
    second = build_package(
        tmp_path,
        private_key,
        package_id="full-revision-2",
        rule_revision=2,
        level_1="11",
        issued_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )

    service.install(first)
    service.install(second)

    selected = standards.get_for_evaluation(
        "gb-00000-2026", date(2026, 8, 31), StandardSelectionMode.CURRENT
    )
    assert selected is not None
    assert selected.rule_revision == 2
    assert len(standards.list_all()) == 2
    assert [entry.package_id for entry in service.list_history(2)] == [
        "full-revision-2",
        "full-parent",
    ]

def test_incremental_install_preserves_parent_and_selects_new_revision(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, standards, service = make_service(tmp_path, private_key)
    parent = build_package(tmp_path, private_key, package_id="lineage-parent", rule_revision=1)
    service.install(parent)
    child = build_package(
        tmp_path, private_key, package_id="lineage-child", rule_revision=2,
        package_mode="incremental", parent_package_id="lineage-parent", level_1="11"
    )
    service.install(child)
    assert len(standards.list_all()) == 2
    selected = standards.get_for_evaluation(
        "gb-00000-2026", date(2026, 3, 1), StandardSelectionMode.CURRENT
    )
    assert selected is not None
    assert selected.rule_revision == 2

def test_package_file_rejects_unsafe_archive_paths() -> None:
    with pytest.raises(ValueError, match="路径"):
        PackageFile(path="sources/", sha256="0" * 64, size=0, kind="source")
    with pytest.raises(ValueError, match="路径"):
        PackageFile(path="sources/../source.pdf", sha256="0" * 64, size=1, kind="source")


def test_builder_rejects_unsafe_source_filename(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    definition = make_standard()
    definition.source_file = "../escape.pdf"
    source = tmp_path / "escape.pdf"
    source.write_bytes(b"placeholder")
    definition.source_sha256 = __import__("hashlib").sha256(source.read_bytes()).hexdigest()
    with pytest.raises(StandardPackageError, match="文件名不安全"):
        StandardPackageBuilder(private_key).build(
            tmp_path / "unsafe.uebench",
            [definition],
            {definition.source_file: source},
            package_id="unsafe-package",
            data_version="2026.1",
        )

def test_preview_rejects_source_basename_collision(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    package = build_package(tmp_path, private_key, package_id="collision-base")
    collision = tmp_path / "collision.uebench"
    with zipfile.ZipFile(package, "r") as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    source_item = next(item for item in manifest["files"] if item["kind"] == "source")
    source_name = source_item["path"].split("/")[-1]
    duplicate_path = "sources/sub/" + source_name
    duplicate_item = dict(source_item)
    duplicate_item["path"] = duplicate_path
    manifest["files"].append(duplicate_item)
    entries[duplicate_path] = entries[source_item["path"]]
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    entries["manifest.json"] = manifest_bytes
    entries["signature.ed25519"] = private_key.sign(manifest_bytes)
    with zipfile.ZipFile(collision, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    report = service.preview(collision)
    assert not report.valid
    assert any("原文文件名冲突" in error for error in report.errors)


def test_package_source_reference_mismatch_is_rejected(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    definition = make_standard()
    source = tmp_path / definition.source_file
    source.write_bytes(b"placeholder")
    digest = __import__("hashlib").sha256(source.read_bytes()).hexdigest()
    definition.source_sha256 = digest
    definition.products[0].indicators[0].source_references[0].source_sha256 = digest
    definition.products[0].indicators[0].source_references[0].standard_number = "GB 00001-2026"
    package = StandardPackageBuilder(private_key).build(
        tmp_path / "bad-reference.uebench",
        [definition],
        {definition.source_file: source},
        package_id="bad-reference-package",
        data_version="2026.1",
    )
    report = service.preview(package)
    assert not report.valid
    assert any("来源标准号不一致" in error for error in report.errors)


def test_package_data_version_rollback_is_rejected_even_with_newer_issue_time(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    first = build_package(
        tmp_path, private_key, package_id="version-first",
        data_version="2026.08-published.4",
        issued_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
    )
    second = build_package(
        tmp_path, private_key, package_id="version-rollback",
        data_version="2026.08-published.3",
        issued_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )
    service.install(first)
    report = service.preview(second)
    assert not report.valid
    assert any("数据版本早于" in error for error in report.errors)

def test_preview_rejects_directory_named_as_package_without_crashing(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, _, service = make_service(tmp_path, private_key)
    package_directory = tmp_path / "not-a-package.uebench"
    package_directory.mkdir()

    report = service.preview(package_directory)

    assert not report.valid
    assert "标准包路径不是文件" in report.errors


def test_install_rolls_back_directory_and_database_when_repository_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key = Ed25519PrivateKey.generate()
    paths, database, standards, service = make_service(tmp_path, private_key)
    package = build_package(tmp_path, private_key, package_id="rollback-package")

    def fail_install(*args, **kwargs):
        raise RuntimeError("模拟数据库写入失败")

    monkeypatch.setattr(standards, "install", fail_install)

    with pytest.raises(RuntimeError, match="模拟数据库写入失败"):
        service.install(package)

    assert not (paths.standards / "rollback-package").exists()
    with database.session() as session:
        assert session.query(PackageRow).count() == 0
