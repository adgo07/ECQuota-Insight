"""ECQ-RS05 第 7 阶段验收阻塞项 #2 / #3 —— 标准包安装的两条安全契约。

阻塞项 #2（用户数据目录不得留存标准原文）
----------------------------------------
``StandardPackageService.install()`` 过去把包里每个 ``sources`` 成员复制进
``paths.standards/<package_id>/``，于是「安装产品自带的标准包」就会在用户数据目录
留下全套标准 PDF；旧版本已经写下的那些目录还会被安全备份一起带上。

新契约：

* 任何包（含仍携带 ``sources/*`` 的旧包）安装时都**不再**把原文写入用户数据目录；
* 安装前先删除旧版本在产品数据目录下创建的 ``sources`` 目录，范围严格限定为
  ``paths.standards/<package_id>/sources``（不跟随符号链接、不越出 ``standards/``）；
* 清理发生在**迁移前安全备份之前**，所以该次安装留下的
  ``pre-package-*.uebackup`` 里同样没有 PDF；
* 清理既写日志（``logging.getLogger(__name__)``）又写审计行。

阻塞项 #3（安全备份不得被静默覆盖）
----------------------------------
备份名过去只精确到秒，而 ``BackupService.create`` 写入时直接覆盖同名文件：同一秒内
连续安装两次会得到同一个备份路径，第二次覆盖第一次，安装前状态从此不可恢复。

新契约：备份名带亚秒精度 **并且** 带显式碰撞保护，永不覆盖已有备份，同时保持
``pre-package-*.uebackup`` 前缀以便既有代码/测试继续 glob。

本模块只做真实（非 mock）测试：真实 Ed25519 签名包、真实 SQLite、真实安装流程。
"""

from __future__ import annotations

import hashlib
import json
import logging
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
    StandardPackageService,
    _backup_path,
)
from uebench.infrastructure.paths import AppPaths
from uebench.infrastructure.repositories import AuditRepository, SqlStandardRepository

from .test_engine import make_standard

try:  # 测试目录既可能是普通目录，也可能被当作包
    from _legacy_assets import session_legacy_package
except ModuleNotFoundError:  # pragma: no cover - 取决于 pytest 的导入模式
    from tests._legacy_assets import session_legacy_package

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = ROOT / "src" / "uebench" / "resources" / "update_public_key.pem"
#: 开发签名私钥（绝不复制进仓库，只按路径引用）。
DEVELOPMENT_KEY = ROOT / "work" / "signing" / "development-private-key.pem"
GLOB = f"{BACKUP_NAME_PREFIX}*.uebackup"

#: 真实归档的 r1（2026.09-published.2）旧包副本；归档不可用时是「不存在的路径」。
LEGACY_PACKAGE = session_legacy_package()
#: 旧包安装在真实环境里写入的原文文件名。
LEGACY_SOURCE_NAME = "28.GB 29446-2019选煤电力消耗限额.pdf"
#: 真实 GB 29446（r1 旧包）里用于正式评价的取值。
GB29446_ID = "gb-29446-2019"
GB29446_PRODUCT = "gb_29446-2019-coking-coal"
GB29446_DIRECT_INPUT_KEY = "actual.coking-coal"

ISSUED_AT = datetime(2026, 10, 5, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def require_legacy_package() -> None:
    if not LEGACY_PACKAGE.is_file():
        pytest.skip(f"缺少归档旧标准包：{LEGACY_PACKAGE}")


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


def real_key_paths(tmp_path: Path):
    """数据目录 + 真实产品公钥（校验归档/固定正式包时必须用它，不能用临时密钥）。"""
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


def developer_private_key() -> Ed25519PrivateKey:
    """开发签名私钥（绝不复制进仓库，只按路径引用）。

    用真实产品公钥校验的数据目录，只能安装用这把私钥签名的包。
    """
    from cryptography.hazmat.primitives import serialization

    if not DEVELOPMENT_KEY.is_file():
        pytest.skip(f"缺少开发签名私钥：{DEVELOPMENT_KEY}")
    key = serialization.load_pem_private_key(DEVELOPMENT_KEY.read_bytes(), password=None)
    assert isinstance(key, Ed25519PrivateKey)
    return key


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
):
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
    """真实归档 r1 旧包 → 安装新版：活目录与本次安装备份都必须 0 个 PDF。"""
    require_legacy_package()
    private_key = developer_private_key()
    paths, _database, _standards, audit, service = real_key_paths(tmp_path)

    # 第一步：旧版本行为 —— 安装真实归档 r1 包。
    first = service.install(LEGACY_PACKAGE)
    legacy_directory = paths.standards / first.package_id
    assert first.removed_source_directory_count == 0

    # 第二步：构造「上一版本已落盘原文」的数据目录。真实归档包里确有原文，
    # 若因环境差异没有，则按同样的布局自行写入，用例仍成立。
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
    successor = build_provenance_only_package(
        tmp_path,
        private_key,
        package_id="safety-successor",
        data_version="2026.11-published.1",
    )
    with caplog.at_level(logging.WARNING):
        result = service.install(successor)

    # 活目录：产品安装的原文目录及其 3 个 PDF 全部消失。
    assert not legacy_sources.exists()
    assert list(paths.standards.rglob("sources")) == []
    assert pdf_files(paths.standards) == [], "升级后用户数据目录必须 0 个 PDF"
    assert result.removed_source_directory_count == 1
    assert result.removed_source_file_count == expected_files
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


def test_cleanup_scope_never_touches_user_documents(tmp_path: Path) -> None:
    """清理范围严格限定为 ``standards/<package_id>/sources`` 直接子目录。"""
    require_legacy_package()
    private_key = developer_private_key()
    paths, _database, _standards, audit, service = real_key_paths(tmp_path)
    first = service.install(LEGACY_PACKAGE)
    legacy_sources = paths.standards / first.package_id / "sources"
    legacy_sources.mkdir(parents=True, exist_ok=True)
    (legacy_sources / "product-installed.pdf").write_bytes(b"%PDF-1.4 product")

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
        private_key,
        package_id="safety-scope-successor",
        data_version="2026.11-published.3",
    )
    result = service.install(successor)

    # 只删了「包目录/sources」这两个目录，各 1 个文件。
    assert result.removed_source_directory_count == 2
    assert result.removed_source_file_count == 2
    assert not legacy_sources.exists()
    assert not second_sources.exists()
    assert loose_pdf.read_bytes() == b"%PDF-1.4 loose user file"
    assert user_pdf.read_bytes() == b"%PDF-1.4 user document"
    assert nested_pdf.read_bytes() == b"%PDF-1.4 nested"
    details = json.loads(audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED)[0].details_json)
    assert details["directories_removed"] == 2
    assert details["files_removed"] == 2


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


# ---------------------------------------------------------------------------
# 3. 业务数据在升级（含清理）后原样保留
# ---------------------------------------------------------------------------


def test_business_data_survives_the_upgrade_and_cleanup(tmp_path: Path) -> None:
    """升级并清理原文目录不得影响已保存评价及其规则快照、定义与包历史。

    评价走真实 GB 29446-2019（正式评价范围内），因此这条用例同时证明清理不会
    破坏「历史记录 + 规则快照 + 已安装定义 + 包历史」。
    """
    require_legacy_package()
    private_key = developer_private_key()
    paths, database, standards, _audit, service = real_key_paths(tmp_path)
    first = service.install(LEGACY_PACKAGE)

    from uebench.bootstrap import create_context
    from uebench.application.services import EvaluationService
    from uebench.infrastructure.repositories import SqlEvaluationRepository

    evaluations = SqlEvaluationRepository(database, AuditRepository(database))
    request = EvaluationRequest(
        evaluation_date=date(2026, 9, 26),
        standard_id=GB29446_ID,
        product_id=GB29446_PRODUCT,
        selection_mode=StandardSelectionMode.CURRENT,
        input_mode=InputMode.DIRECT,
        inputs={GB29446_DIRECT_INPUT_KEY: InputValue(value="5.0", unit="kW·h/t")},
        organization_name="升级清理回归企业",
    )
    result_before = EvaluationService(standards, evaluations).evaluate(request)
    loaded_before = evaluations.get(result_before.evaluation_id)
    assert loaded_before is not None
    snapshot_sha_before = loaded_before[1].rule_snapshot_sha256
    assert loaded_before[1].rule_revision == 1
    assert database.path.exists()

    # 旧版本留下的原文目录（清理对象）。
    legacy_sources = paths.standards / first.package_id / "sources"
    legacy_sources.mkdir(parents=True, exist_ok=True)
    (legacy_sources / "legacy.pdf").write_bytes(b"%PDF-1.4 legacy")

    # 真实组合根路径（bootstrap + facade）跑一次升级，避免只测「手工装配」。
    context = create_context(paths.root, public_key_path=PUBLIC_KEY)
    try:
        upgrade = context.package_service.install(
            build_provenance_only_package(
                tmp_path,
                private_key,
                package_id="safety-business-successor",
                data_version="2026.11-published.2",
            )
        )
        assert upgrade.removed_source_directory_count == 1
        assert pdf_files(context.paths.standards) == []
        assert context.application.count_evaluations() >= 1
        reloaded = context.application.get_evaluation(result_before.evaluation_id)
        assert reloaded is not None, "升级后历史评价必须仍可读取"
        assert reloaded[1].rule_snapshot_sha256 == snapshot_sha_before
        assert reloaded[1].rule_revision == 1
        assert reloaded[2].rule_revision == 1, "规则快照必须仍是升级前的 r1"
        assert reloaded[0] == loaded_before[0]
        # 其它包历史与已安装定义都还在。
        history = context.application.list_package_history(50)
        assert {entry.package_id for entry in history} >= {first.package_id, upgrade.package_id}
        published = context.application.get_published_standard(GB29446_ID)
        assert published is not None and published.rule_revision == 1
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
    """真实归档 r1 包：包内含原文，安装后用户数据目录 0 个 PDF（端到端）。"""
    require_legacy_package()
    private_key = Ed25519PrivateKey.generate()
    paths, _database, _standards, _audit, service = real_key_paths(tmp_path)

    with zipfile.ZipFile(LEGACY_PACKAGE) as archive:
        source_members = [name for name in archive.namelist() if name.startswith("sources/")]
    assert source_members, "用例前提：归档旧包确实携带 sources/*"

    report = service.preview(LEGACY_PACKAGE)
    assert report.valid, report.errors
    result = service.install(LEGACY_PACKAGE)

    assert pdf_files(paths.standards) == [], "用户数据目录不得出现标准原文"
    assert list(paths.standards.rglob("sources")) == []
    destination = paths.standards / result.package_id
    assert sorted(path.name for path in destination.iterdir()) == ["corrections.json"]
    assert not (destination / LEGACY_SOURCE_NAME).exists()
