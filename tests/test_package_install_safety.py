"""ECQ-RS05 第 7 阶段验收阻塞项 #2 / #3 —— 标准包安装的两条安全契约。

阻塞项 #2（用户数据目录不得留存标准原文）
----------------------------------------
``StandardPackageService.install()`` 过去把包里每个 ``sources`` 成员复制进
``paths.standards/<package_id>/``，于是「安装产品自带的标准包」就会在用户数据目录
留下全套标准 PDF；旧版本已经写下的那些目录还会被安全备份一起带上。

新契约（fail-closed）：

* 任何包（含仍携带 ``sources/*`` 的旧包）安装时都**不再**把原文写入用户数据目录；
* 安装前先检测并删除旧版本在产品数据目录下创建的原文，范围严格限定为
  ``paths.standards/<package_id>/sources`` **以及** 同一层的历史平铺
  ``paths.standards/<package_id>/*.pdf``（不跟随符号链接 / junction、不越出
  ``standards/``）；
* 删除之后必须**重新扫描确认目标确实消失**，只有确认后才写成功审计；
* 确认失败（占用 / 权限 / 删除失败 / 目标仍在）时**中止安装**：不写成功审计、
  不产生携带旧 PDF 的新备份、不改数据库、不留半安装目录，并抛出中文错误；
* 清理发生在**迁移前安全备份之前**，所以该次安装留下的
  ``pre-package-*.uebackup`` 里同样没有 PDF；
* 清理既写日志（``logging.getLogger(__name__)``）又写审计行。

旧版两种历史布局（平铺 / ``sources/`` / 两者同时）的完整矩阵、fail-closed 的
Windows 真实占用用例、以及合成夹具见 ``test_package_legacy_layouts.py``。

阻塞项 #3（安全备份不得被静默覆盖）
----------------------------------
备份名过去只精确到秒，而 ``BackupService.create`` 写入时直接覆盖同名文件：同一秒内
连续安装两次会得到同一个备份路径，第二次覆盖第一次，安装前状态从此不可恢复。

新契约：备份名带亚秒精度 **并且** 带显式碰撞保护，永不覆盖已有备份，同时保持
``pre-package-*.uebackup`` 前缀以便既有代码/测试继续 glob。

本模块只做真实（非 mock）测试：真实 Ed25519 签名包、真实 SQLite、真实安装流程。
本模块不依赖 ``G:\\ECQuota-Archive``，也不依赖 ``work/signing/development-private-key.pem``：
包一律用测试时生成的临时密钥签名，公钥按路径交给服务。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from uebench.domain.models import (
    EvaluationRequest,
    InputMode,
    InputValue,
    PublicationStatus,
    StandardDefinition,
    StandardSelectionMode,
)
from uebench.infrastructure.backup import BackupService
from uebench.infrastructure.database import DatabaseManager
from uebench.infrastructure.logging import close_logging
from uebench.infrastructure.packages import (
    AUDIT_LEGACY_SOURCES_REMOVED,
    BACKUP_NAME_PREFIX,
    PackageInstallResult,
    StandardPackageBuilder,
    StandardPackageError,
    StandardPackageService,
    _backup_path,
)
from uebench.infrastructure.paths import AppPaths
from uebench.infrastructure.repositories import AuditRepository, SqlStandardRepository

from .test_engine import make_standard

try:  # 测试目录既可能是普通目录，也可能被当作包
    from _legacy_assets import (
        LEGACY_LAYOUT_BOTH,
        LEGACY_LAYOUT_FLAT,
        LEGACY_LAYOUT_SOURCES_DIR,
        materialize_legacy_layout,
        synthetic_legacy_library,
    )
except ModuleNotFoundError:  # pragma: no cover - 取决于 pytest 的导入模式
    from tests._legacy_assets import (
        LEGACY_LAYOUT_BOTH,
        LEGACY_LAYOUT_FLAT,
        LEGACY_LAYOUT_SOURCES_DIR,
        materialize_legacy_layout,
        synthetic_legacy_library,
    )

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = ROOT / "src" / "uebench" / "resources" / "update_public_key.pem"
BUNDLED_PACKAGE = (
    ROOT / "release" / "standard-packages" / "initial-standard-package-published.uebench"
)
GLOB = f"{BACKUP_NAME_PREFIX}*.uebackup"

#: 真实 GB 29446-2019（唯一纳入正式评价范围的标准）的 id / 取值。
GB29446_ID = "gb-29446-2019"
GB29446_PRODUCT = "gb_29446-2019-coking-coal"
GB29446_DIRECT_INPUT_KEY = "actual.coking-coal"

ISSUED_AT = datetime(2026, 10, 5, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def require_bundled_package() -> None:
    """固定正式标准包是仓库内固定件，CI 可用；缺失即硬失败，不 skip。"""
    assert BUNDLED_PACKAGE.is_file(), f"缺少固定正式标准包：{BUNDLED_PACKAGE}"


def make_service(tmp_path: Path, private_key: Ed25519PrivateKey):
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
    return paths, database, standards, audit, service


def make_service_with_public_key(tmp_path: Path, public_key_path: Path, *, root: str = "appdata"):
    """用夹具自带公钥装配真实服务（与真实产品公钥无关，可离线运行）。"""
    from cryptography.hazmat.primitives import serialization

    paths = AppPaths.from_root(tmp_path / root)
    paths.ensure()
    database = DatabaseManager(paths.database)
    database.initialize()
    audit = AuditRepository(database)
    backup = BackupService(paths, database, audit)
    standards = SqlStandardRepository(database, audit)
    public_key = serialization.load_pem_public_key(public_key_path.read_bytes())
    service = StandardPackageService(paths, database, public_key, backup, standards, audit)
    return paths, database, standards, audit, service


def real_key_paths(tmp_path: Path):
    """数据目录 + 真实产品公钥（校验仓库内固定正式包时必须用它）。"""
    from cryptography.hazmat.primitives import serialization

    assert PUBLIC_KEY.is_file(), f"缺少内置更新公钥：{PUBLIC_KEY}"
    paths = AppPaths.from_root(tmp_path / "real-appdata")
    paths.ensure()
    database = DatabaseManager(paths.database)
    database.initialize()
    audit = AuditRepository(database)
    backup = BackupService(paths, database, audit)
    standards = SqlStandardRepository(database, audit)
    public_key = serialization.load_pem_public_key(PUBLIC_KEY.read_bytes())
    service = StandardPackageService(paths, database, public_key, backup, standards, audit)
    return paths, database, standards, audit, service


def definition_with_source(tmp_path: Path, *, rule_revision: int = 1):
    """一个 published 定义 + 与之哈希匹配的原文文件。"""
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


def build_embedded_package(
    tmp_path: Path,
    private_key: Ed25519PrivateKey,
    *,
    package_id: str,
    data_version: str,
    definition: StandardDefinition | None = None,
    source: Path | None = None,
):
    """构造一个仍然携带 ``sources/*``（embedded）的真实签名包。"""
    if definition is None or source is None:
        definition, source = definition_with_source(tmp_path)
    return StandardPackageBuilder(private_key).build(
        tmp_path / f"{package_id}.uebench",
        [definition],
        {definition.source_file: source},
        data_version=data_version,
        package_id=package_id,
        issued_at=ISSUED_AT,
        corrections=[{"id": "corr-safety", "note": "安全用例勘误"}],
    )


def build_provenance_only_package(
    tmp_path: Path,
    private_key: Ed25519PrivateKey,
    *,
    package_id: str,
    data_version: str,
    definition: StandardDefinition | None = None,
):
    """构造一个 provenance-only 的后继包（默认新造定义，也可复用已安装定义）。"""
    if definition is None:
        definition, _source = definition_with_source(tmp_path)
    return StandardPackageBuilder(private_key).build(
        tmp_path / f"{package_id}.uebench",
        [definition],
        None,
        data_version=data_version,
        package_id=package_id,
        issued_at=ISSUED_AT,
        distribute_sources=False,
    )


def backup_paths(paths: AppPaths) -> list[Path]:
    return sorted(paths.backups.glob(GLOB))


def backup_names(paths: AppPaths) -> set[str]:
    return {path.name for path in backup_paths(paths)}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pdf_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.pdf") if path.is_file())


def archive_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return archive.namelist()


def backup_database_bytes(path: Path) -> bytes:
    """备份包内嵌的 ``uebench.sqlite3`` 字节。"""
    with zipfile.ZipFile(path) as archive:
        return archive.read("uebench.sqlite3")


def backup_package_rows(path: Path) -> int:
    """备份内嵌数据库里已安装标准包的行数（用于证明备份是哪个时点的状态）。"""
    import sqlite3
    import tempfile

    with tempfile.TemporaryDirectory(prefix="uebench-safety-backup-") as temporary:
        extracted = Path(temporary) / "uebench.sqlite3"
        extracted.write_bytes(backup_database_bytes(path))
        connection = sqlite3.connect(extracted)
        try:
            return int(
                connection.execute("SELECT COUNT(*) FROM standard_packages").fetchone()[0]
            )
        finally:
            connection.close()


def audit_rows(audit: AuditRepository, action: str) -> list:
    return [entry for entry in audit.list_recent(500) if entry.action == action]


# ---------------------------------------------------------------------------
# 1. 携带原文的旧包：安装后用户数据目录里 0 个 PDF
# ---------------------------------------------------------------------------


def test_source_bearing_package_installs_zero_source_files(tmp_path: Path) -> None:
    """契约更新（owner decision）：含原文包也只安装非原文产物。"""
    private_key = Ed25519PrivateKey.generate()
    paths, _database, standards, _audit, service = make_service(tmp_path, private_key)
    definition, source = definition_with_source(tmp_path)
    package = build_embedded_package(
        tmp_path,
        private_key,
        package_id="safety-embedded",
        data_version="2026.10-published.10",
        definition=definition,
        source=source,
    )

    # 用例前提：包本身确实携带并声明了原文。
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        members = archive.namelist()
    assert manifest["source_policy"] == "embedded"
    assert len([item for item in manifest["files"] if item["kind"] == "source"]) == 1
    assert [name for name in members if name.startswith("sources/")]

    # 校验能力不受影响：preview 仍然逐文件核验哈希/大小。
    report = service.preview(package)
    assert report.valid, report.errors

    result = service.install(package)
    assert result.standards_installed == 1
    assert result.removed_source_directory_count == 0
    assert result.removed_source_file_count == 0

    destination = paths.standards / result.package_id
    assert pdf_files(paths.standards) == [], "用户数据目录不得出现任何 PDF"
    assert not (destination / "sources").exists()
    assert sorted(path.name for path in destination.iterdir()) == ["corrections.json"]
    assert standards.get_published(definition.id) is not None


# ---------------------------------------------------------------------------
# 2. 升级一个已含旧版落盘原文的数据目录：清理 + 审计 + 备份里也没有 PDF
# ---------------------------------------------------------------------------


def test_upgrade_of_legacy_data_directory_removes_installed_pdfs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """旧版落盘原文（``sources/`` 布局）→ 安装新版：活目录与本次备份都必须 0 个 PDF。

    夹具为合成旧包 + 临时密钥（不依赖归档区与开发私钥）。
    """
    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    paths, _database, _standards, audit, service = make_service_with_public_key(
        tmp_path, library.public_key_path
    )

    # 第一步：旧版本行为 —— 安装一个仍携带 sources/* 的旧包。
    first = service.install(library.package)
    legacy_directory = paths.standards / first.package_id
    assert first.removed_source_directory_count == 0
    assert first.removed_flat_source_file_count == 0

    # 第二步：复现「上一版本已落盘原文」的数据目录（sources/ 布局）。
    legacy_sources = legacy_directory / "sources"
    legacy_sources.mkdir(parents=True, exist_ok=True)
    for index in range(3):
        (legacy_sources / f"{index:02d}.legacy.pdf").write_bytes(b"%PDF-1.4 legacy")
    (legacy_sources / "note.txt").write_text("旧版本残留", encoding="utf-8")
    expected_files = len(list(legacy_sources.rglob("*")))
    assert expected_files == 4
    backups_before = backup_names(paths)

    assert len(pdf_files(paths.standards)) == 3

    # 第三步：安装新版（provenance-only），清理必须先于安全备份发生。
    # 复用旧包里的同一份定义（同一 id/版本/规则版本、内容一致），只提高数据版本。
    successor = build_provenance_only_package(
        tmp_path,
        library.private_key,
        package_id="safety-successor",
        data_version="2026.11-published.1",
        definition=library.definition,
    )
    with caplog.at_level(logging.WARNING):
        result = service.install(successor)

    # 活目录：产品安装的原文目录及其 3 个 PDF 全部消失。
    assert not legacy_sources.exists()
    assert list(paths.standards.rglob("sources")) == []
    assert pdf_files(paths.standards) == [], "升级后用户数据目录必须 0 个 PDF"
    assert result.removed_source_directory_count == 1
    assert result.removed_source_file_count == expected_files
    assert result.removed_flat_source_file_count == 0
    assert pdf_files(legacy_directory) == []

    # 日志证据：同一数据目录、同一进程内可观察到清理记录。
    removal_records = [
        record
        for record in caplog.records
        if record.name == "uebench.infrastructure.packages"
        and record.levelno >= logging.WARNING
        and "移除旧版本写入用户数据目录的标准原文" in record.getMessage()
    ]
    assert removal_records, [record.getMessage() for record in caplog.records]
    message = removal_records[0].getMessage()
    assert "1 个目录" in message and f"{expected_files} 个文件" in message
    assert str(paths.standards.resolve()) in message

    # 审计证据。
    rows = audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED)
    assert len(rows) == 1, [entry.action for entry in audit.list_recent(50)]
    details = json.loads(rows[0].details_json)
    assert details["directories_removed"] == 1
    assert details["files_removed"] == expected_files
    assert details["flat_files_removed"] == 0
    assert details["verified"] is True
    assert rows[0].entity_type == "standard_package"

    # 备份证据：本次安装新增的 pre-package 备份里同样 0 个 PDF。
    new_backups = backup_names(paths) - backups_before
    assert len(new_backups) == 1
    assert Path(result.backup_path).name in new_backups
    backup = paths.backups / next(iter(new_backups))
    backup_members = archive_names(backup)
    assert backup_members, backup_members
    assert [name for name in backup_members if name.lower().endswith(".pdf")] == [], (
        f"本次安装的安全备份仍包含 PDF：{backup_members}"
    )
    # 备份里连旧包的 versions/sources 目录都不应存在。
    assert not [name for name in backup_members if name.endswith("/sources/")]
    assert not [
        name
        for name in backup_members
        if Path(name).name == "note.txt" or name.endswith(".legacy.pdf")
    ], f"本次安装的安全备份仍包含旧版原文目录内容：{backup_members}"
    # 备份里必须有该包安装目录（只是里面不再有 sources/）。
    assert any(
        name.endswith("corrections.json") and first.package_id in name
        for name in backup_members
    ), backup_members


def test_upgrade_removes_flat_legacy_pdfs_too(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """真实旧版布局：PDF 平铺在 ``standards/<package>/*.pdf`` 也必须被清理。"""
    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    paths, _database, _standards, audit, service = make_service_with_public_key(
        tmp_path, library.public_key_path
    )
    first = service.install(library.package)
    legacy_directory = paths.standards / first.package_id
    materialize_legacy_layout(legacy_directory, LEGACY_LAYOUT_FLAT, pdf_count=3)
    keep = legacy_directory / "corrections.json"
    assert keep.is_file()
    backups_before = backup_names(paths)
    assert len(pdf_files(paths.standards)) == 3

    successor = build_provenance_only_package(
        tmp_path,
        library.private_key,
        package_id="safety-flat-successor",
        data_version="2026.11-published.1",
        definition=library.definition,
    )
    with caplog.at_level(logging.WARNING):
        result = service.install(successor)

    assert result.removed_source_directory_count == 0
    assert result.removed_source_file_count == 0
    assert result.removed_flat_source_file_count == 3
    assert pdf_files(paths.standards) == []
    assert list(legacy_directory.glob("*.pdf")) == []
    # 非原文产物原样保留。
    assert keep.is_file()
    details = json.loads(audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED)[0].details_json)
    assert details["flat_files_removed"] == 3
    assert details["directories_removed"] == 0
    # 备份在清理之后：打开备份，里面没有 PDF。
    new_backups = backup_names(paths) - backups_before
    assert len(new_backups) == 1
    members = archive_names(paths.backups / next(iter(new_backups)))
    assert [name for name in members if name.lower().endswith(".pdf")] == [], members
    assert any(name.endswith("corrections.json") for name in members), members


def test_cleanup_scope_never_touches_user_documents(tmp_path: Path) -> None:
    """清理范围严格限定为包目录直接子级：``sources/`` 与平铺 ``*.pdf``。"""
    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    paths, _database, _standards, audit, service = make_service_with_public_key(
        tmp_path, library.public_key_path
    )
    first = service.install(library.package)
    legacy_sources = paths.standards / first.package_id / "sources"
    legacy_sources.mkdir(parents=True, exist_ok=True)
    (legacy_sources / "product-installed.pdf").write_bytes(b"%PDF-1.4 product")
    flat_pdf = paths.standards / first.package_id / "loose-legacy.pdf"
    flat_pdf.write_bytes(b"%PDF-1.4 flat legacy")

    # 同一契约下会被清理的第二个目录：另一个包目录的直接子级 ``sources``。
    second_package = paths.standards / "second-installed-package"
    second_package.mkdir()
    second_sources = second_package / "sources"
    second_sources.mkdir()
    (second_sources / "product-installed-2.pdf").write_bytes(b"%PDF-1.4 product 2")

    # 必须被保留的用户内容：包目录之外的散落文件、非 sources 目录里的 PDF、
    # 以及「不是包目录直接子级」的 sources（严格范围之外）。
    loose_pdf = paths.standards / "loose-user-file.pdf"
    loose_pdf.write_bytes(b"%PDF-1.4 loose user file")
    other_package = paths.standards / "user-imported-package"
    other_package.mkdir()
    user_pdf = other_package / "documents" / "user-document.pdf"
    user_pdf.parent.mkdir()
    user_pdf.write_bytes(b"%PDF-1.4 user document")
    nested = legacy_sources.parent / "archive" / "sources"
    nested.mkdir(parents=True)
    nested_pdf = nested / "nested.pdf"
    nested_pdf.write_bytes(b"%PDF-1.4 nested")

    successor = build_provenance_only_package(
        tmp_path,
        library.private_key,
        package_id="safety-scope-successor",
        data_version="2026.11-published.3",
        definition=library.definition,
    )
    result = service.install(successor)

    # 删了「包目录/sources」两个目录（各 1 个文件）与 1 个平铺 PDF。
    assert result.removed_source_directory_count == 2
    assert result.removed_source_file_count == 2
    assert result.removed_flat_source_file_count == 1
    assert not legacy_sources.exists()
    assert not second_sources.exists()
    assert not flat_pdf.exists()
    assert loose_pdf.read_bytes() == b"%PDF-1.4 loose user file"
    assert user_pdf.read_bytes() == b"%PDF-1.4 user document"
    assert nested_pdf.read_bytes() == b"%PDF-1.4 nested"
    details = json.loads(audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED)[0].details_json)
    assert details["directories_removed"] == 2
    assert details["files_removed"] == 2
    assert details["flat_files_removed"] == 1


def test_second_install_after_cleanup_is_a_noop_for_source_state(tmp_path: Path) -> None:
    """清理是幂等的：没有旧原文目录时不再产生第二条清理审计。"""
    private_key = Ed25519PrivateKey.generate()
    paths, _database, _standards, audit, service = make_service(tmp_path, private_key)
    first = build_provenance_only_package(
        tmp_path, private_key, package_id="idempotent-a", data_version="2026.10-published.11"
    )
    second = build_provenance_only_package(
        tmp_path, private_key, package_id="idempotent-b", data_version="2026.10-published.12"
    )

    service.install(first)
    assert audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED) == []

    result = service.install(second)
    assert result.removed_source_directory_count == 0
    assert result.removed_source_file_count == 0
    assert audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED) == []
    assert pdf_files(paths.standards) == []


def test_cleanup_legacy_sources_port_method_reports_real_counts_and_is_idempotent(
    tmp_path: Path,
) -> None:
    """§五 端口方法：与 ``install`` 用同一个 Gate，返回真实计数且幂等。

    ``StandardPackagePort.cleanup_legacy_sources()`` 是启动/对账路径唯一允许调用
    的入口（application 层不得导入 infrastructure）。它必须是**同一份**实现：
    计数、审计、失败语义都与 ``install`` 内部那一次完全一致。
    """
    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    paths, _database, _standards, audit, service = make_service_with_public_key(
        tmp_path, library.public_key_path
    )
    first = service.install(library.package)
    legacy_directory = paths.standards / first.package_id
    created = materialize_legacy_layout(legacy_directory, LEGACY_LAYOUT_BOTH, pdf_count=2)
    assert created["sources"].is_dir()
    assert len(pdf_files(paths.standards)) == 4

    # 真实计数：(1 个 sources 目录, 目录内 2 个文件, 2 个平铺 PDF)。
    assert service.cleanup_legacy_sources() == (1, 2, 2)
    assert pdf_files(paths.standards) == []
    assert not (legacy_directory / "sources").exists()
    # 非原文产物原样保留。
    assert (legacy_directory / "corrections.json").is_file()
    details = json.loads(audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED)[0].details_json)
    assert details["directories_removed"] == 1
    assert details["files_removed"] == 2
    assert details["flat_files_removed"] == 2
    assert details["verified"] is True

    # 幂等：没有旧原文时全零且不新增审计行。
    assert service.cleanup_legacy_sources() == (0, 0, 0)
    assert len(audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED)) == 1


def test_cleanup_legacy_sources_port_method_is_fail_closed_when_it_cannot_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§五 端口方法的 fail-closed：删不掉就中止，绝不写成功审计。

    与 ``test_cleanup_keeps_retrying_then_aborts_when_target_never_disappears``
    同一套做法（在删除动作这一层注入永久失败，因此跨平台可复现），但驱动的是
    **端口方法本身**——也就是启动/对账路径真正调用的那一个入口。
    """
    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    paths, database, _standards, audit, service = make_service_with_public_key(
        tmp_path, library.public_key_path
    )
    first = service.install(library.package)
    legacy_directory = paths.standards / first.package_id
    materialize_legacy_layout(legacy_directory, LEGACY_LAYOUT_SOURCES_DIR, pdf_count=1)
    sources = legacy_directory / "sources"
    target = next(sources.glob("*.pdf"))
    payload = target.read_bytes()

    attempts: list[int] = []
    real_rmtree = shutil.rmtree
    real_remove = os.remove

    def never_deletes(directories, flat_files):
        for directory in directories:
            if directory.exists():
                real_rmtree(directory)
        for path in flat_files:
            if path.exists():
                real_remove(path)
        attempts.append(1)
        sources.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return [(sources, f"PermissionError: 模拟永久占用：{target}")]

    monkeypatch.setattr(StandardPackageService, "_delete_legacy_targets", staticmethod(never_deletes))
    monkeypatch.setattr(StandardPackageService, "LEGACY_CLEANUP_RETRY_DELAY", 0.0)

    with pytest.raises(StandardPackageError) as failure:
        service.cleanup_legacy_sources()

    assert len(attempts) == StandardPackageService.LEGACY_CLEANUP_ATTEMPTS, attempts
    message = str(failure.value)
    assert "无法删除旧版本遗留在用户数据目录中的标准原文" in message
    assert "安装已中止" in message and "PermissionError" in message
    assert "模拟永久占用" in message
    # 无成功审计、数据库完好、目标仍在（而不是"装作删掉了"）。
    assert audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED) == []
    assert database.path.exists()
    assert [entry.package_id for entry in service.list_history(50)] == [first.package_id]
    assert target.is_file() and target.read_bytes() == payload


# ---------------------------------------------------------------------------
# 3. 业务数据在升级（含清理）后原样保留
# ---------------------------------------------------------------------------


def test_business_data_survives_the_upgrade_and_cleanup(tmp_path: Path) -> None:
    """真实 GB 29446 端到端：安装正式包时清理旧版原文，业务数据与快照不受影响。

    评价走真实 GB 29446-2019（唯一纳入正式评价范围的标准），定义来自仓库内固定的
    正式标准包，用**真实产品公钥**装配真实组合根。旧版落盘原文在安装之前就已存在
    （这正是历史布局在真实环境里的样子），因此走的是一条完整的 ``install`` 路径：
    检测 → 删除 → 重新扫描验证 → 审计 → 安全备份 → 落盘定义。本用例不依赖外部
    归档区，也不依赖 ``work/signing/development-private-key.pem``。
    """
    from uebench.bootstrap import create_context

    require_bundled_package()
    # 真实组合根路径（bootstrap + facade），真实产品公钥。
    context = create_context(tmp_path / "appdata", public_key_path=PUBLIC_KEY)
    try:
        # 安装前：旧版本留下的两种历史布局同时存在。
        legacy_directory = context.paths.standards / "legacy-package-from-old-version"
        materialize_legacy_layout(legacy_directory, LEGACY_LAYOUT_BOTH, pdf_count=1)
        keep_note = legacy_directory / "user-notes.txt"
        keep_note.write_text("用户自己的说明", encoding="utf-8")
        assert len(pdf_files(context.paths.standards)) == 2

        backups_before = backup_names(context.paths)
        first = context.package_service.install(BUNDLED_PACKAGE)

        # 清理发生在同一条 install 路径内，并且是真实、可复核的结果。
        assert first.removed_source_directory_count == 1
        assert first.removed_source_file_count == 1
        assert first.removed_flat_source_file_count == 1
        assert pdf_files(context.paths.standards) == []
        assert not (legacy_directory / "sources").exists()
        # 非原文内容原样保留。
        assert keep_note.read_text(encoding="utf-8") == "用户自己的说明"
        # 本次安装的安全备份在清理之后：里面没有 PDF。
        new_backups = backup_names(context.paths) - backups_before
        assert len(new_backups) == 1
        members = archive_names(context.paths.backups / next(iter(new_backups)))
        assert [name for name in members if name.lower().endswith(".pdf")] == [], members
        # 安装目录只落非原文产物。
        destination = context.paths.standards / first.package_id
        assert sorted(path.name for path in destination.iterdir()) == ["corrections.json"]

        revisions = sorted(
            item.rule_revision
            for item in context.application.list_all_standards()
            if item.id == GB29446_ID
        )
        assert revisions, "正式包必须提供 GB 29446 定义"
        current_revision = max(revisions)

        request = EvaluationRequest(
            evaluation_date=date(2026, 9, 26),
            standard_id=GB29446_ID,
            product_id=GB29446_PRODUCT,
            selection_mode=StandardSelectionMode.CURRENT,
            input_mode=InputMode.DIRECT,
            inputs={GB29446_DIRECT_INPUT_KEY: InputValue(value="5.0", unit="kW·h/t")},
            organization_name="升级清理回归企业",
        )
        evaluation = context.application.evaluate(request)
        loaded = context.application.get_evaluation(evaluation.evaluation_id)
        assert loaded is not None
        assert loaded[1].rule_revision == current_revision
        assert context.application.count_evaluations() == 1
        # 标准目录与数据库都没有半升级状态。
        assert pdf_files(context.paths.standards) == []
        assert context.database.path.exists()
        assert context.application.get_published_standard(GB29446_ID) is not None
        assert [entry.package_id for entry in context.application.list_package_history(5)] == [
            first.package_id
        ]
    finally:
        context.database.dispose()
        close_logging()


# ---------------------------------------------------------------------------
# 4. 备份碰撞回归（阻塞项 #3 的核心复现）
# ---------------------------------------------------------------------------


def test_two_back_to_back_installs_never_overwrite_a_backup(tmp_path: Path) -> None:
    """同一秒内连续两次安装必须留下两个**不同**的、内容各自完好的备份。"""
    private_key = Ed25519PrivateKey.generate()
    paths, _database, _standards, _audit, service = make_service(tmp_path, private_key)
    first_package = build_provenance_only_package(
        tmp_path, private_key, package_id="collision-a", data_version="2026.10-published.13"
    )
    second_package = build_provenance_only_package(
        tmp_path, private_key, package_id="collision-b", data_version="2026.10-published.14"
    )

    assert backup_paths(paths) == []

    # 刻意不 sleep：旧的「精确到秒 + 直接覆盖」实现会在这里返回同一个路径。
    result_a = service.install(first_package)
    snapshots_after_a = backup_paths(paths)
    assert len(snapshots_after_a) == 1
    path_a = Path(result_a.backup_path)
    bytes_a = path_a.read_bytes()
    sha_a = sha256_file(path_a)

    result_b = service.install(second_package)
    snapshots_after_b = backup_paths(paths)

    # 两个不同的备份路径、两个真实存在的文件。
    assert result_a.backup_path != result_b.backup_path, (
        "连续两次安装返回了同一个备份路径：第二次会覆盖第一次"
    )
    assert len(snapshots_after_b) == 2, [item.name for item in snapshots_after_b]
    path_b = Path(result_b.backup_path)
    assert path_a.is_file() and path_b.is_file()
    assert all(path.name.startswith(BACKUP_NAME_PREFIX) for path in snapshots_after_b)
    assert all(path.suffix == ".uebackup" for path in snapshots_after_b)

    # 第一次的备份逐字节未变。
    assert path_a.read_bytes() == bytes_a
    assert sha256_file(path_a) == sha_a
    assert sha256_file(path_b) != sha_a, "两个备份必须可区分"

    # 第二次的备份必须是「安装第一个包之前」的状态，而不是被覆盖后的残骸：
    # 第一次的备份里还没有任何已安装包行，第二次的备份里正好有第一个包。
    assert backup_package_rows(path_a) == 0, "第一次备份必须是安装前的状态"
    assert backup_package_rows(path_b) == 1, "第二次备份必须包含第一个包，而不是第二次安装的结果"
    assert backup_database_bytes(path_a) != backup_database_bytes(path_b)
    # 且两份备份都通过真实备份校验（含逐文件哈希）。
    backup_service = BackupService(None, DatabaseManager(paths.database))
    for snapshot in snapshots_after_b:
        manifest = backup_service.validate(snapshot)
        assert manifest["schema_version"] == "1.0"
        assert "uebench.sqlite3" in manifest["files"]


# ---------------------------------------------------------------------------
# 5. 备份命名护栏：不允许只有秒级精度、不允许返回已存在的路径
# ---------------------------------------------------------------------------


def test_backup_path_is_unique_within_the_same_second(tmp_path: Path) -> None:
    """同一时刻（同一秒内）连续取 200 个名字必须互不相同且都不存在。"""
    directory = tmp_path / "backups"
    directory.mkdir(parents=True)
    names = [_backup_path(directory) for _ in range(200)]

    assert len(set(names)) == len(names), "备份路径出现重名：可能覆盖已有安全备份"
    assert all(not name.exists() for name in names)
    assert all(name.name.startswith(BACKUP_NAME_PREFIX) for name in names)
    # 名字必须带亚秒精度：``YYYYmmdd-HHMMSS-ffffff``，第三段是 6 位微秒。
    for name in names:
        core = name.name[len(BACKUP_NAME_PREFIX) : -len(".uebackup")]
        parts = core.split("-")
        assert len(parts) >= 3, core
        assert len(parts[0]) == 8 and parts[0].isdigit(), core
        assert len(parts[1]) == 6 and parts[1].isdigit(), core
        assert len(parts[2]) == 6 and parts[2].isdigit(), f"缺少微秒精度：{core}"


def test_backup_path_never_returns_an_existing_path(tmp_path: Path) -> None:
    """显式碰撞保护：目标已存在时必须换一个不同的名字（-1 后缀），绝不覆盖。"""
    directory = tmp_path / "backups"
    directory.mkdir(parents=True)

    taken = _backup_path(directory)
    taken.write_bytes(b"existing safety backup")
    taken_bytes = taken.read_bytes()

    fresh = _backup_path(directory)

    assert fresh != taken
    assert not fresh.exists()
    assert fresh.name.startswith(BACKUP_NAME_PREFIX)
    assert taken.exists() and taken.read_bytes() == taken_bytes, "已有安全备份不得被触碰"


def test_package_install_result_reports_removed_source_counts(tmp_path: Path) -> None:
    """清理结果必须可从 ``PackageInstallResult`` 读出（新增字段，默认 0）。"""
    private_key = Ed25519PrivateKey.generate()
    paths, _database, _standards, _audit, service = make_service(tmp_path, private_key)
    package = build_provenance_only_package(
        tmp_path, private_key, package_id="counts-default", data_version="2026.10-published.15"
    )

    result = service.install(package)

    assert isinstance(result, PackageInstallResult)
    assert result.removed_source_directory_count == 0
    assert result.removed_source_file_count == 0
    # 旧字段语义不变。
    assert result.package_id == "counts-default"
    assert result.data_version == "2026.10-published.15"
    assert result.standards_installed == 1
    assert Path(result.backup_path).is_file()
    assert pdf_files(paths.standards) == []


def test_real_legacy_package_ships_sources_but_never_lands_them(tmp_path: Path) -> None:
    """真实携带原文的旧包：安装后用户数据目录 0 个 PDF（端到端，可离线）。

    夹具用合成旧包（临时密钥、真实签名），包里确实含 ``sources/*``，安装后一个
    PDF 都不落盘。
    """
    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    paths, _database, _standards, _audit, service = make_service_with_public_key(
        tmp_path, library.public_key_path
    )

    with zipfile.ZipFile(library.package) as archive:
        source_members = [name for name in archive.namelist() if name.startswith("sources/")]
    assert source_members, "用例前提：旧包确实携带 sources/*"

    report = service.preview(library.package)
    assert report.valid, report.errors
    assert report.manifest is not None and report.manifest.source_policy == "embedded"
    result = service.install(library.package)

    assert pdf_files(paths.standards) == [], "用户数据目录不得出现标准原文"
    assert list(paths.standards.rglob("sources")) == []
    destination = paths.standards / result.package_id
    assert sorted(path.name for path in destination.iterdir()) == ["corrections.json"]
    assert not (destination / library.source_file_name).exists()
