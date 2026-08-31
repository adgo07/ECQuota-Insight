from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from uebench.infrastructure.backup import BackupService
from uebench.infrastructure.database import DatabaseManager
from uebench.infrastructure.packages import StandardPackageBuilder, StandardPackageError, StandardPackageService
from uebench.infrastructure.paths import AppPaths
from uebench.infrastructure.repositories import AuditRepository, SqlStandardRepository
from uebench.domain.models import PublicationStatus

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
) -> Path:
    definition = make_standard()
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
        data_version="2026.1",
        issued_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        corrections=corrections,
    )


def test_signed_package_preview_and_install(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _, _, standards, service = make_service(tmp_path, private_key)
    package = build_package(tmp_path, private_key)
    report = service.preview(package)
    assert report.valid, report.errors
    result = service.install(package)
    assert result.standards_installed == 1
    assert standards.get_published("gb-00000-2026") is not None


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
