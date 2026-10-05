"""ECQ-RS05 §四 —— 旧版「标准原文落盘布局」清理契约（合成夹具，可离线运行）。

旧的 UEBench 版本确实把标准原文写进了用户数据目录，而且先后出现过两种布局：

``flat``          ``standards/<package_id>/*.pdf``           （更早的版本，平铺）
``sources-dir``   ``standards/<package_id>/sources/*.pdf``   （较晚的版本）
``both``          两者同时存在（跨版本升级后可能出现的混合状态）

本模块用 ``tests/_legacy_assets.py`` 的**合成**夹具覆盖它们：PDF 只是最小 dummy
字节，包由测试时临时生成的 Ed25519 密钥签名，公钥经 ``create_context(...,
public_key_path=...)`` 交给组合根。因此本模块不依赖 ``G:\\ECQuota-Archive``、不依赖
``work/signing/development-private-key.pem``，也不会因为二者缺失而 skip。

覆盖的验收项：

1. layout A（平铺）清理；
2. layout B（``sources/``）清理；
3. layout C（两者同时）清理；
4. 顺序：清理先于安全备份，因此**本次**新备份里没有 PDF（打开备份列成员验证）；
5. 历史评价 / 规则快照存活，数据库不半升级；
6. 对账（reconciliation）与 no-op 路径仍可用；
7. **删除失败时 fail-closed**：Windows 上真实占用句柄 → 中止 + 无成功审计 +
   无新备份 + 中文错误 + 数据库完好；另有跨平台的注入失败用例验证同一语义。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization

from uebench.bootstrap import create_context
from uebench.domain.models import (
    EvaluationRequest,
    InputMode,
    InputValue,
)
from uebench.infrastructure.backup import BackupService
from uebench.infrastructure.database import DatabaseManager
from uebench.infrastructure.logging import close_logging
from uebench.infrastructure.packages import (
    AUDIT_LEGACY_SOURCES_REMOVED,
    BACKUP_NAME_PREFIX,
    PackageManifest,
    StandardPackageError,
    StandardPackageService,
)
from uebench.infrastructure.paths import AppPaths
from uebench.infrastructure.repositories import AuditRepository, SqlStandardRepository

try:  # 测试目录既可能是普通目录，也可能被当作包
    from _legacy_assets import (
        LEGACY_LAYOUT_BOTH,
        LEGACY_LAYOUT_FLAT,
        LEGACY_LAYOUT_SOURCES_DIR,
        expected_legacy_removal,
        materialize_legacy_layout,
        successor_library,
        synthetic_legacy_library,
    )
except ModuleNotFoundError:  # pragma: no cover - 取决于 pytest 的导入模式
    from tests._legacy_assets import (
        LEGACY_LAYOUT_BOTH,
        LEGACY_LAYOUT_FLAT,
        LEGACY_LAYOUT_SOURCES_DIR,
        expected_legacy_removal,
        materialize_legacy_layout,
        successor_library,
        synthetic_legacy_library,
    )

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = ROOT / "src" / "uebench" / "resources" / "update_public_key.pem"
BUNDLED_PACKAGE = (
    ROOT / "release" / "standard-packages" / "initial-standard-package-published.uebench"
)
GLOB = f"{BACKUP_NAME_PREFIX}*.uebackup"
GB29446 = "gb-29446-2019"
GB29446_COKING = "gb_29446-2019-coking-coal"

ALL_LAYOUTS = (LEGACY_LAYOUT_FLAT, LEGACY_LAYOUT_SOURCES_DIR, LEGACY_LAYOUT_BOTH)


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def make_service(root: Path, public_key_path: Path):
    """真实装配：真实 SQLite + 真实备份服务 + 夹具自带公钥。"""
    paths = AppPaths.from_root(root)
    paths.ensure()
    database = DatabaseManager(paths.database)
    database.initialize()
    audit = AuditRepository(database)
    backup = BackupService(paths, database, audit)
    standards = SqlStandardRepository(database, audit)
    public_key = serialization.load_pem_public_key(public_key_path.read_bytes())
    service = StandardPackageService(paths, database, public_key, backup, standards, audit)
    return paths, database, standards, audit, service


def backup_names(paths: AppPaths) -> set[str]:
    return {path.name for path in paths.backups.glob(GLOB)}


def all_pdfs(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.pdf") if path.is_file())


def archive_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return archive.namelist()


def audit_rows(audit: AuditRepository, action: str) -> list:
    return [entry for entry in audit.list_recent(500) if entry.action == action]


def audit_details(audit: AuditRepository, action: str) -> list[dict]:
    return [json.loads(entry.details_json) for entry in audit_rows(audit, action)]


def installed_package_ids(service: StandardPackageService) -> list[str]:
    return [entry.package_id for entry in service.list_history(50)]


def successor_package(work: Path, library, *, package_id: str, data_version: str) -> Path:
    """与夹具旧包同一密钥签名的 provenance-only 后继包。"""
    return successor_library(
        work,
        private_key=library.private_key,
        package_id=package_id,
        data_version=data_version,
    )


def install_synthetic_legacy(root: Path, work: Path, *, layout: str, pdf_count: int = 3):
    """安装合成旧包（真实签名），再按 ``layout`` 复现旧版落盘布局。"""
    library = synthetic_legacy_library(work)
    paths, database, standards, audit, service = make_service(root, library.public_key_path)
    result = service.install(library.package)
    legacy_directory = paths.standards / result.package_id
    created = materialize_legacy_layout(legacy_directory, layout, pdf_count=pdf_count)
    return paths, database, standards, audit, service, library, legacy_directory, created


def backup_package_row_count(backup: Path) -> int:
    """备份内嵌数据库里已安装标准包的行数（用于核对备份是哪个时点的状态）。"""
    with zipfile.ZipFile(backup) as archive:
        payload = archive.read("uebench.sqlite3")
    with tempfile.TemporaryDirectory(prefix="uebench-legacy-backup-") as temporary:
        extracted = Path(temporary) / "uebench.sqlite3"
        extracted.write_bytes(payload)
        connection = sqlite3.connect(extracted)
        try:
            return int(connection.execute("SELECT COUNT(*) FROM standard_packages").fetchone()[0])
        finally:
            connection.close()


def bundled_directory(tmp_path: Path, package: Path) -> Path:
    """内置包目录：文件名必须匹配 ``initial-standard-package-*.uebench``。"""
    directory = tmp_path / "bundled"
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(package, directory / f"initial-standard-package-{package.stem}.uebench")
    return directory


def package_id_of(package: Path) -> str:
    with zipfile.ZipFile(package) as archive:
        return PackageManifest.model_validate_json(archive.read("manifest.json")).package_id


# ---------------------------------------------------------------------------
# 1./2./3. layout A / B / C 的清理
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("layout", ALL_LAYOUTS)
def test_legacy_layout_is_cleaned_on_upgrade(tmp_path: Path, layout: str) -> None:
    """三种历史布局（平铺 / sources / 两者同时）都必须被清理干净。"""
    work = tmp_path / "work"
    (
        paths,
        _database,
        _standards,
        _audit,
        service,
        library,
        legacy_directory,
        _created,
    ) = install_synthetic_legacy(tmp_path / "appdata", work, layout=layout)
    directories, files_inside, flat = expected_legacy_removal(layout)
    assert directories + flat > 0, "用例前提：夹具确实复现了落盘原文"

    # 用例前提：布局真的落在磁盘上。
    if layout in (LEGACY_LAYOUT_SOURCES_DIR, LEGACY_LAYOUT_BOTH):
        assert (legacy_directory / "sources").is_dir()
    if layout in (LEGACY_LAYOUT_FLAT, LEGACY_LAYOUT_BOTH):
        assert len(list(legacy_directory.glob("*.pdf"))) == flat
    assert len(all_pdfs(paths.standards)) == files_inside + flat

    successor = successor_package(
        work,
        library,
        package_id=f"synthetic-successor-{layout}",
        data_version="2026.11-published.1",
    )
    result = service.install(successor)

    # 真实（而非估算）的清理计数。
    assert result.removed_source_directory_count == directories
    assert result.removed_source_file_count == files_inside
    assert result.removed_flat_source_file_count == flat

    # 数据目录 0 个 PDF，两个布局位置都为空。
    assert all_pdfs(paths.standards) == [], [str(path) for path in all_pdfs(paths.standards)]
    assert not (legacy_directory / "sources").exists()
    assert list(paths.standards.rglob("sources")) == []
    # 新包自身的安装目录只允许非原文产物。
    destination = paths.standards / result.package_id
    assert sorted(path.name for path in destination.iterdir()) == ["corrections.json"]


def test_flat_and_sources_layouts_in_separate_packages_are_both_cleaned(tmp_path: Path) -> None:
    """不同包目录使用不同历史布局时，一次安装必须把两种布局都清掉。"""
    work = tmp_path / "work"
    (
        paths,
        _database,
        _standards,
        _audit,
        service,
        library,
        legacy_directory,
        _created,
    ) = install_synthetic_legacy(
        tmp_path / "appdata", work, layout=LEGACY_LAYOUT_FLAT
    )
    # 第二个「历史包目录」用较晚的布局（模拟两次不同年代的安装）。
    other = paths.standards / "older-installed-package"
    other.mkdir()
    materialize_legacy_layout(other, LEGACY_LAYOUT_SOURCES_DIR, pdf_count=2)

    successor = successor_package(
        work,
        library,
        package_id="synthetic-successor-mixed",
        data_version="2026.11-published.1",
    )
    result = service.install(successor)

    assert result.removed_source_directory_count == 1
    assert result.removed_source_file_count == 2
    assert result.removed_flat_source_file_count == 3
    assert all_pdfs(paths.standards) == []
    assert not (other / "sources").exists()
    assert list(legacy_directory.glob("*.pdf")) == []


def test_cleanup_never_touches_non_legacy_content(tmp_path: Path) -> None:
    """严格边界：非 PDF、非 ``sources`` 的用户内容与范围外 PDF 一律保留。"""
    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    paths, _database, _standards, _audit, service = make_service(
        tmp_path / "appdata", library.public_key_path
    )
    service.install(library.package)

    # 复现旧版布局（两种同时）并加入必须保留的内容。
    inside = paths.standards / "legacy-package"
    materialize_legacy_layout(inside, LEGACY_LAYOUT_BOTH, pdf_count=1)
    keep_note = inside / "notes" / "user-note.txt"
    keep_note.parent.mkdir(parents=True, exist_ok=True)
    keep_note.write_bytes("用户自己的说明".encode("utf-8"))
    keep_doc = inside / "documents" / "user-document.pdf"
    keep_doc.parent.mkdir(parents=True, exist_ok=True)
    keep_doc.write_bytes(b"%PDF-1.4 user document")
    # standards 根目录下的散落 PDF（不是包目录的直接子级）。
    loose = paths.standards / "loose-user-file.pdf"
    loose.write_bytes(b"%PDF-1.4 loose user file")
    # 更深一层的 sources（严格范围之外）。
    nested = inside / "archive" / "sources"
    nested.mkdir(parents=True)
    nested_pdf = nested / "nested.pdf"
    nested_pdf.write_bytes(b"%PDF-1.4 nested")

    successor = successor_package(
        work,
        library,
        package_id="synthetic-boundary-successor",
        data_version="2026.11-published.1",
    )
    result = service.install(successor)

    assert result.removed_source_directory_count == 1
    assert result.removed_source_file_count == 1
    assert result.removed_flat_source_file_count == 1
    # 边界之外的一切逐字节未变。
    assert keep_note.read_bytes() == "用户自己的说明".encode("utf-8")
    assert keep_doc.read_bytes() == b"%PDF-1.4 user document"
    assert loose.read_bytes() == b"%PDF-1.4 loose user file"
    assert nested_pdf.read_bytes() == b"%PDF-1.4 nested"
    # 范围之内的旧原文确实没了。
    assert not (inside / "sources").exists()
    assert list(inside.glob("*.pdf")) == []


# ---------------------------------------------------------------------------
# 4. 顺序：清理先于安全备份（打开备份列成员验证）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("layout", ALL_LAYOUTS)
def test_new_backup_is_taken_after_cleanup_and_contains_no_pdf(
    tmp_path: Path, layout: str
) -> None:
    """本次安装的新备份里不得有 PDF：必须打开备份、列成员、逐条断言。"""
    work = tmp_path / "work"
    (
        paths,
        _database,
        _standards,
        _audit,
        service,
        library,
        _legacy_directory,
        _created,
    ) = install_synthetic_legacy(tmp_path / "appdata", work, layout=layout, pdf_count=2)
    directories, files_inside, flat = expected_legacy_removal(layout, pdf_count=2)
    assert len(all_pdfs(paths.standards)) == files_inside + flat
    backups_before = backup_names(paths)

    successor = successor_package(
        work,
        library,
        package_id=f"synthetic-backup-{layout}",
        data_version="2026.11-published.1",
    )
    result = service.install(successor)

    new_backups = backup_names(paths) - backups_before
    assert len(new_backups) == 1, sorted(new_backups)
    backup = paths.backups / next(iter(new_backups))
    assert backup.name == Path(result.backup_path).name

    members = archive_names(backup)
    assert members, "备份包不能为空"
    assert [name for name in members if name.lower().endswith(".pdf")] == [], (
        f"本次安装的安全备份仍包含 PDF：{members}"
    )
    assert not [
        name for name in members if name.endswith("/sources/") or name == "sources"
    ], members
    assert not [
        name for name in members if "legacy-flat" in name or "legacy-sources" in name
    ], members
    # 备份仍然覆盖本次安装前的*活目录状态*：前一个包的安装目录在备份里。
    assert any(
        name.endswith(f"standards/{library.package_id}/corrections.json") for name in members
    ), members
    # 备份是安装前时点：里面只有第一个包。
    assert backup_package_row_count(backup) == 1
    # 活目录同样 0 个 PDF。
    assert all_pdfs(paths.standards) == []
    assert list(paths.standards.rglob("sources")) == []


def test_audit_details_are_the_verified_post_cleanup_counts(tmp_path: Path) -> None:
    """审计里的计数必须是「验证后」的真实结果，而不是事前估算。"""
    work = tmp_path / "work"
    (
        paths,
        _database,
        _standards,
        audit,
        service,
        library,
        _legacy_directory,
        _created,
    ) = install_synthetic_legacy(
        tmp_path / "appdata", work, layout=LEGACY_LAYOUT_BOTH, pdf_count=3
    )
    successor = successor_package(
        work,
        library,
        package_id="synthetic-audit-successor",
        data_version="2026.11-published.1",
    )
    result = service.install(successor)

    details = audit_details(audit, AUDIT_LEGACY_SOURCES_REMOVED)
    assert len(details) == 1, details
    assert details[0]["directories_removed"] == 1
    assert details[0]["files_removed"] == 3
    assert details[0]["flat_files_removed"] == 3
    assert details[0]["verified"] is True
    assert details[0]["scope"] == str(paths.standards.resolve())
    # 审计与返回结果一致，并且磁盘上确实什么都没有了。
    assert result.removed_source_directory_count == details[0]["directories_removed"]
    assert result.removed_source_file_count == details[0]["files_removed"]
    assert result.removed_flat_source_file_count == details[0]["flat_files_removed"]
    assert all_pdfs(paths.standards) == []


# ---------------------------------------------------------------------------
# 5. 历史评价 / 规则快照存活，数据库不半升级
# ---------------------------------------------------------------------------


def test_historical_evaluation_row_and_rule_snapshot_survive_the_cleanup(tmp_path: Path) -> None:
    """历史评价行 / 规则快照 / 已装定义 / 包历史在清理与升级后逐项完好。

    合成夹具的标准不在正式评价范围内（``SUPPORTED_EVALUATION_STANDARD_IDS`` 只有
    ``gb-29446-2019``），``evaluate`` 按设计拒绝为它生成正式记录——这是 application
    层的正确闸门，不能为了测试放宽。因此这里用仓储层直接落一条与真实评价同构的行
    （完整请求载荷 + 当时的规则快照），再验证清理与升级都不会动它；真实标准的端到端
    正式评价由 ``test_real_bundled_gb29446_evaluation_survives_the_cleanup`` 覆盖。
    """
    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    context = create_context(tmp_path / "appdata", public_key_path=library.public_key_path)
    try:
        from uebench.infrastructure.repositories import (
            AuditRepository as _AuditRepository,
            SqlEvaluationRepository,
        )

        first = context.package_service.install(library.package)
        legacy_directory = context.paths.standards / first.package_id
        materialize_legacy_layout(legacy_directory, LEGACY_LAYOUT_BOTH, pdf_count=2)
        assert len(all_pdfs(context.paths.standards)) == 4

        definition = context.standards.get_published(library.definition.id)
        assert definition is not None
        product = definition.products[0]
        indicator = product.indicators[0]
        # 正式评价闸门如实拒绝范围外的标准（清理任务不得放宽它）。
        with pytest.raises(ValueError, match="尚未纳入正式评价范围"):
            context.application.evaluate(
                EvaluationRequest(
                    evaluation_date=date(2026, 3, 1),
                    standard_id=definition.id,
                    product_id=product.id,
                    input_mode=InputMode.DIRECT,
                    inputs={
                        indicator.direct_input_key: InputValue(value="5", unit=indicator.unit)
                    },
                )
            )

        # 用仓储层落一条与正式评价同构的历史行（含规则快照与请求载荷）。
        request = EvaluationRequest(
            evaluation_date=date(2026, 3, 1),
            standard_id=definition.id,
            product_id=product.id,
            input_mode=InputMode.DIRECT,
            inputs={indicator.direct_input_key: InputValue(value="5", unit=indicator.unit)},
            organization_name="旧版布局清理回归企业",
        )
        evaluations = SqlEvaluationRepository(
            context.database, _AuditRepository(context.database)
        )
        preview_result = context.application.preview_evaluation(request)
        evaluations.save(request, preview_result, definition)
        loaded_before = evaluations.get(preview_result.evaluation_id)
        assert loaded_before is not None
        snapshot_before = loaded_before[1].rule_snapshot_sha256
        revision_before = loaded_before[1].rule_revision
        rows_before = evaluations.count()

        successor = successor_package(
            work,
            library,
            package_id="synthetic-snapshot-successor",
            data_version="2026.11-published.1",
        )
        upgrade = context.package_service.install(successor)

        # 清理真的发生了……
        assert upgrade.removed_source_directory_count == 1
        assert upgrade.removed_source_file_count == 2
        assert upgrade.removed_flat_source_file_count == 2
        assert all_pdfs(context.paths.standards) == []
        # ……历史评价与规则快照逐字节存活（数据库没有半升级）。
        assert evaluations.count() == rows_before == 1
        reloaded = evaluations.get(preview_result.evaluation_id)
        assert reloaded is not None, "清理/升级后历史评价必须仍可读取"
        assert reloaded[0] == loaded_before[0]
        assert reloaded[1].rule_snapshot_sha256 == snapshot_before
        assert reloaded[1].rule_revision == revision_before
        assert reloaded[2].rule_revision == revision_before
        history = context.application.list_package_history(50)
        assert {entry.package_id for entry in history} >= {first.package_id, upgrade.package_id}
        # 两个规则修订都在：升级是追加 r2，不是替换 r1。
        revisions = sorted(
            item.rule_revision
            for item in context.application.list_all_standards()
            if item.id == library.definition.id
        )
        assert revisions == [1, 2]
        # 新包的安装目录只落非原文产物；没有半写入。
        destination = context.paths.standards / upgrade.package_id
        assert sorted(path.name for path in destination.iterdir()) == ["corrections.json"]
    finally:
        context.database.dispose()
        close_logging()


def test_real_bundled_gb29446_evaluation_survives_the_cleanup(tmp_path: Path) -> None:
    """真实 GB 29446 评价 + 真实内置包（真实产品公钥）：清理后快照仍完好。"""
    assert BUNDLED_PACKAGE.is_file(), f"缺少固定正式标准包：{BUNDLED_PACKAGE}"
    assert PUBLIC_KEY.is_file(), f"缺少内置更新公钥：{PUBLIC_KEY}"
    from uebench.main import reconcile_standard_package

    context = create_context(tmp_path / "appdata", public_key_path=PUBLIC_KEY)
    try:
        # 无已安装包时对账会安装内置包（这也是真实首次启动路径）。
        outcome = reconcile_standard_package(context, BUNDLED_PACKAGE.parent)
        assert outcome.executed is True
        assert outcome.installed_after is not None
        assert context.standards.get_published(GB29446) is not None

        legacy_directory = context.paths.standards / outcome.installed_after.package_id
        materialize_legacy_layout(legacy_directory, LEGACY_LAYOUT_BOTH, pdf_count=1)
        assert len(all_pdfs(context.paths.standards)) == 2

        request = EvaluationRequest(
            evaluation_date=date(2026, 3, 1),
            standard_id=GB29446,
            product_id=GB29446_COKING,
            input_mode=InputMode.DIRECT,
            inputs={"actual.coking-coal": InputValue(value="5.0", unit="kW·h/t")},
            organization_name="真实包清理回归企业",
        )
        evaluation = context.application.evaluate(request)
        loaded_before = context.application.get_evaluation(evaluation.evaluation_id)
        assert loaded_before is not None

        # 下一次安装（用真实产品公钥无法安装临时密钥签的包，因此直接调用清理闸门，
        # 它正是 install 在创建安全备份之前调用的那一个函数）。
        removed = context.package_service._remove_legacy_source_directories()
        assert removed == (1, 1, 1)
        assert all_pdfs(context.paths.standards) == []

        # 历史评价 / 规则快照 / 已安装定义 / 包历史逐项完好。
        loaded_after = context.application.get_evaluation(evaluation.evaluation_id)
        assert loaded_after is not None
        assert loaded_after[0] == loaded_before[0]
        assert loaded_after[1].rule_snapshot_sha256 == loaded_before[1].rule_snapshot_sha256
        assert loaded_after[1].rule_revision == loaded_before[1].rule_revision
        assert loaded_after[2].rule_revision == loaded_before[2].rule_revision
        assert context.application.count_evaluations() == 1
        assert context.standards.get_published(GB29446).rule_revision == 2
        assert len(context.application.list_package_history(5)) == 1
        # 已产生的备份仍然都在（清理不改写任何 .uebackup）。
        assert backup_names(context.paths)
    finally:
        context.database.dispose()
        close_logging()


# ---------------------------------------------------------------------------
# 6. 对账与 no-op 路径
# ---------------------------------------------------------------------------


def test_reconciliation_cleans_legacy_layouts_then_noops(tmp_path: Path) -> None:
    """对账装包时顺带清理旧布局；第二次对账 no-op，不新增备份/审计。"""
    from uebench.application.package_reconciliation import (
        PackageReconciliationService,
        ReconciliationAction,
    )
    from uebench.infrastructure.packages import _data_version_key
    from uebench.main import reconcile_standard_package

    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    context = create_context(tmp_path / "appdata", public_key_path=library.public_key_path)
    try:
        directory = bundled_directory(tmp_path, library.package)
        assert package_id_of(library.package) == library.package_id

        # 预置一个旧包目录（旧版落盘布局），对账安装必须把它清掉。
        legacy = context.paths.standards / "legacy-package-from-old-version"
        legacy.mkdir(parents=True)
        materialize_legacy_layout(legacy, LEGACY_LAYOUT_BOTH, pdf_count=2)
        assert len(all_pdfs(context.paths.standards)) == 4

        audit = AuditRepository(context.database)
        service = PackageReconciliationService(
            context.package_service, data_version_key=_data_version_key
        )
        first = service.reconcile(directory)

        assert first.action is ReconciliationAction.INSTALL
        assert first.executed is True
        assert all_pdfs(context.paths.standards) == []
        assert not (legacy / "sources").exists()
        backups_after_first = backup_names(context.paths)
        assert len(backups_after_first) == 1
        audits_after_first = len(audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED))
        assert audits_after_first == 1
        assert first.installed_after is not None
        assert first.installed_after.package_id == library.package_id

        second = service.reconcile(directory)

        assert second.action is ReconciliationAction.NOOP
        assert second.executed is False
        assert backup_names(context.paths) == backups_after_first, "no-op 不得新增备份"
        assert (
            len(audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED)) == audits_after_first
        ), "no-op 不得新增清理审计"
        assert all_pdfs(context.paths.standards) == []
        assert len(context.application.list_package_history(5)) == 1

        # 组合根入口与 application 层一致。
        third = reconcile_standard_package(context, directory)
        assert third.action is ReconciliationAction.NOOP
        assert backup_names(context.paths) == backups_after_first
    finally:
        context.database.dispose()
        close_logging()


def test_noop_cleanup_records_no_audit_and_keeps_existing_state(tmp_path: Path) -> None:
    """没有旧版原文时清理是 no-op：无审计、无改动、无 PDF。"""
    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    paths, _database, _standards, audit, service = make_service(
        tmp_path / "appdata", library.public_key_path
    )
    assert service.install(library.package).removed_source_directory_count == 0
    assert audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED) == []

    successor = successor_package(
        work,
        library,
        package_id="synthetic-noop-successor",
        data_version="2026.11-published.1",
    )
    result = service.install(successor)
    assert result.removed_source_directory_count == 0
    assert result.removed_source_file_count == 0
    assert result.removed_flat_source_file_count == 0
    assert audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED) == []
    assert all_pdfs(paths.standards) == []


def test_reconciliation_and_upgrade_without_any_legacy_layout_still_work(tmp_path: Path) -> None:
    """没有旧版布局时：对账 INSTALL → UPGRADE 正常，清理字段恒为 0。"""
    from uebench.application.package_reconciliation import (
        PackageReconciliationService,
        ReconciliationAction,
    )
    from uebench.infrastructure.packages import _data_version_key

    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    context = create_context(tmp_path / "appdata", public_key_path=library.public_key_path)
    try:
        first_directory = bundled_directory(tmp_path / "first", library.package)
        service = PackageReconciliationService(
            context.package_service, data_version_key=_data_version_key
        )
        installed = service.reconcile(first_directory)
        assert installed.action is ReconciliationAction.INSTALL

        successor = successor_package(
            work,
            library,
            package_id="synthetic-clean-upgrade",
            data_version="2026.11-published.1",
        )
        second_directory = bundled_directory(tmp_path / "second", successor)

        upgraded = service.reconcile(second_directory)

        assert upgraded.action is ReconciliationAction.UPGRADE
        assert upgraded.executed is True
        assert all_pdfs(context.paths.standards) == []
        # 没有旧版原文 → 没有清理审计。
        assert audit_rows(AuditRepository(context.database), AUDIT_LEGACY_SOURCES_REMOVED) == []
        assert context.standards.get_published(library.definition.id).rule_revision == 2
    finally:
        context.database.dispose()
        close_logging()


# ---------------------------------------------------------------------------
# 7. fail-closed：删除失败必须中止
# ---------------------------------------------------------------------------


def _require_windows() -> None:
    if sys.platform != "win32":
        pytest.skip("真实文件占用只能在 Windows 上复现（其他平台允许删除已打开的文件）")


def test_locked_legacy_pdf_aborts_install_fail_closed(tmp_path: Path) -> None:
    """Windows 真实占用句柄：删除真的失败 → 中止安装、无成功审计、无新备份。

    这是本模块最重要的一条：``open(path, "rb")`` 保持打开会让 ``os.remove`` 真实地
    以 ``PermissionError``(winerror 32) 失败——本机已实测。因此它验证的不是注入的
    假失败，而是 Windows 上真实会发生的占用。
    """
    _require_windows()
    work = tmp_path / "work"
    (
        paths,
        database,
        _standards,
        _audit,
        service,
        library,
        legacy_directory,
        created,
    ) = install_synthetic_legacy(
        tmp_path / "appdata", work, layout=LEGACY_LAYOUT_BOTH, pdf_count=2
    )
    sources = created["sources"]
    loose_pdfs = sorted(legacy_directory.glob("*.pdf"))
    sources_pdfs = sorted(sources.glob("*.pdf"))
    locked_pdf = sources_pdfs[0]
    flat_pdf = loose_pdfs[0]
    locked_bytes = locked_pdf.read_bytes()
    assert locked_bytes.startswith(b"%PDF-1.4")

    successor = successor_package(
        work,
        library,
        package_id="synthetic-locked-successor",
        data_version="2026.11-published.1",
    )

    audit = AuditRepository(database)
    backups_before = backup_names(paths)
    audits_before = audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED)
    history_before = installed_package_ids(service)
    assert history_before == [library.package_id]
    assert all_pdfs(paths.standards) != []

    with open(locked_pdf, "rb") as handle:
        assert handle.read(8).startswith(b"%PDF")
        with pytest.raises(StandardPackageError) as failure:
            service.install(successor)

    message = str(failure.value)
    # 中文错误 + 精确原因 + 处置建议。
    assert "无法删除旧版本遗留在用户数据目录中的标准原文" in message
    assert "安装已中止" in message
    assert "PermissionError" in message or "另一个程序正在使用此文件" in message
    # 错误里点名了删不掉的目标（被占用的 PDF 所在目录）。
    assert str(locked_pdf.parent) in message
    assert "重试" in message

    # 1) 新包没有安装。
    assert not (paths.standards / "synthetic-locked-successor").exists()
    # 2) 没有成功审计。
    assert audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED) == audits_before
    # 3) 没有新的 pre-package 备份（否则它会继续带着旧 PDF）。
    assert backup_names(paths) == backups_before
    # 4) 数据库完好：包历史没有新增，规则行没有新增。
    assert installed_package_ids(service) == history_before
    assert service.latest_manifest().package_id == library.package_id
    revisions = sorted(
        item.rule_revision
        for item in service.standards.list_all()
        if item.id == library.definition.id
    )
    assert revisions == [1]
    # 5) 被占用的原文仍在（句柄释放后依然在原位），且逐字节未变。
    assert locked_pdf.is_file()
    assert locked_pdf.read_bytes() == locked_bytes
    # 6) 未被占用的其余目标（另一类布局的平铺 PDF）确实已经删掉：
    #    失败并非「什么都没尝试」。被占用 PDF 的同级文件是否已删取决于
    #    ``rmtree`` 的遍历顺序，不作断言。
    assert not flat_pdf.exists()


def test_cleanup_retries_transient_failure_and_only_then_records_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """跨平台：第一次删除「名义成功但其实还在」时必须重试并重新扫描。

    这里不让 ``os.remove`` 真的失败（非 Windows 上打开的文件照样能删），而是让第一次
    删除后目标**故意重现**：只有「重试 → 重新扫描确认消失 → 再记审计」的实现才能通过。
    审计计数必须是真实清理结果。
    """
    import uebench.infrastructure.packages as packages_module

    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    paths, _database, _standards, audit, service = make_service(
        tmp_path / "appdata", library.public_key_path
    )
    service.install(library.package)
    legacy_directory = paths.standards / library.package_id
    materialize_legacy_layout(legacy_directory, LEGACY_LAYOUT_FLAT, pdf_count=2)
    target = sorted(legacy_directory.glob("*.pdf"))[0]
    payload = target.read_bytes()

    real_remove = os.remove
    injected: list[Path] = []
    errors: list[OSError] = []

    def flaky_remove(path, *args, **kwargs):
        real_remove(path, *args, **kwargs)
        candidate = Path(path)
        if candidate == target and not injected:
            injected.append(candidate)
            candidate.write_bytes(payload)  # 让它「复活」：重新扫描必须发现它还在
            errors.append(PermissionError(13, "模拟瞬时占用", str(candidate)))
            raise errors[-1]

    monkeypatch.setattr(packages_module.os, "remove", flaky_remove)

    successor = successor_package(
        work,
        library,
        package_id="synthetic-retry-successor",
        data_version="2026.11-published.1",
    )
    result = service.install(successor)

    assert errors, "用例前提：注入的失败确实发生过"
    assert result.removed_flat_source_file_count == 2
    assert result.removed_source_directory_count == 0
    assert all_pdfs(paths.standards) == []
    details = audit_details(audit, AUDIT_LEGACY_SOURCES_REMOVED)
    assert len(details) == 1, details
    assert details[0]["flat_files_removed"] == 2, "审计计数必须是重试后的真实结果"
    assert details[0]["verified"] is True
    # 重试成功后安装才继续。
    assert (paths.standards / "synthetic-retry-successor" / "corrections.json").is_file()


def test_cleanup_keeps_retrying_then_aborts_when_target_never_disappears(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """跨平台：重试到上限后目标依然存在 → 中止，且不产生任何成功痕迹。

    永久占用不可能在 POSIX 上靠文件句柄复现（打开的文件照样能删），所以这里在
    **删除动作这一层**注入永久失败：每一次尝试都删掉后立刻复原并抛
    ``PermissionError``。这样验证的是重试计数与「验证不过就不许成功」的判定，
    与 Windows 上的真实占用用例互补。
    """
    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    paths, database, _standards, audit, service = make_service(
        tmp_path / "appdata", library.public_key_path
    )
    service.install(library.package)
    legacy_directory = paths.standards / library.package_id
    materialize_legacy_layout(legacy_directory, LEGACY_LAYOUT_SOURCES_DIR, pdf_count=1)
    sources = legacy_directory / "sources"
    target = next(sources.glob("*.pdf"))
    payload = target.read_bytes()

    attempts: list[int] = []

    def never_deletes(directories, flat_files):
        # 真实删除动作被替换：每次都把目标复原并上报失败。
        for directory in directories:
            if directory.exists():
                shutil.rmtree(directory)
        for path in flat_files:
            if path.exists():
                os.remove(path)
        attempts.append(1)
        sources.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return [(sources, f"PermissionError: 模拟永久占用：{target}")]

    monkeypatch.setattr(StandardPackageService, "_delete_legacy_targets", staticmethod(never_deletes))
    monkeypatch.setattr(StandardPackageService, "LEGACY_CLEANUP_RETRY_DELAY", 0.0)

    successor = successor_package(
        work,
        library,
        package_id="synthetic-refused-successor",
        data_version="2026.11-published.1",
    )
    backups_before = backup_names(paths)
    with pytest.raises(StandardPackageError) as failure:
        service.install(successor)

    assert len(attempts) == StandardPackageService.LEGACY_CLEANUP_ATTEMPTS, attempts
    message = str(failure.value)
    assert "无法删除旧版本遗留在用户数据目录中的标准原文" in message
    assert "安装已中止" in message and "PermissionError" in message
    assert "模拟永久占用" in message
    # 无安装、无成功审计、无新备份、数据库可用。
    assert not (paths.standards / "synthetic-refused-successor").exists()
    assert audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED) == []
    assert backup_names(paths) == backups_before
    assert installed_package_ids(service) == [library.package_id]
    assert database.path.exists()
    assert target.is_file()


def test_fail_closed_cleanup_never_creates_a_backup_containing_old_pdfs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """删除失败后，现存备份里都不允许出现旧版 PDF，也没有新备份产生。"""
    import uebench.infrastructure.packages as packages_module

    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    paths, _database, _standards, _audit, service = make_service(
        tmp_path / "appdata", library.public_key_path
    )
    service.install(library.package)
    legacy_directory = paths.standards / library.package_id
    materialize_legacy_layout(legacy_directory, LEGACY_LAYOUT_BOTH, pdf_count=1)
    backups_before = backup_names(paths)

    real_rmtree = shutil.rmtree

    def refusing_rmtree(path, *args, **kwargs):
        if Path(path).name == "sources":
            raise PermissionError(13, "模拟占用", str(path))
        return real_rmtree(path, *args, **kwargs)

    def refusing_remove(path, *args, **kwargs):
        raise PermissionError(13, "模拟占用", str(path))

    monkeypatch.setattr(packages_module.shutil, "rmtree", refusing_rmtree)
    monkeypatch.setattr(packages_module.os, "remove", refusing_remove)
    monkeypatch.setattr(StandardPackageService, "LEGACY_CLEANUP_RETRY_DELAY", 0.0)

    successor = successor_package(
        work,
        library,
        package_id="synthetic-refused-backup-successor",
        data_version="2026.11-published.1",
    )
    with pytest.raises(StandardPackageError):
        service.install(successor)

    assert backup_names(paths) == backups_before
    for name in backup_names(paths):
        members = archive_names(paths.backups / name)
        assert [item for item in members if item.lower().endswith(".pdf")] == [], (
            f"备份 {name} 携带了旧版 PDF：{members}"
        )


# ---------------------------------------------------------------------------
# §五 既有 .uebackup 不得被改写
# ---------------------------------------------------------------------------


def test_existing_backups_are_byte_identical_after_cleanup(tmp_path: Path) -> None:
    """旧版本已产生的 .uebackup 保持逐字节不变，只有新备份才是无 PDF 的。"""
    work = tmp_path / "work"
    (
        paths,
        _database,
        _standards,
        _audit,
        service,
        library,
        _legacy_directory,
        _created,
    ) = install_synthetic_legacy(
        tmp_path / "appdata", work, layout=LEGACY_LAYOUT_SOURCES_DIR, pdf_count=2
    )
    # 手工造一个「历史备份」：内容任意但必须被原样保留。
    historical = paths.backups / "pre-package-19990101-000000-000000.uebackup"
    historical_bytes = b"historical backup produced by an older version"
    historical.write_bytes(historical_bytes)
    historical_sha = hashlib.sha256(historical_bytes).hexdigest()

    successor = successor_package(
        work,
        library,
        package_id="synthetic-historical-backup-successor",
        data_version="2026.11-published.1",
    )
    result = service.install(successor)

    assert historical.read_bytes() == historical_bytes
    assert hashlib.sha256(historical.read_bytes()).hexdigest() == historical_sha
    assert Path(result.backup_path) != historical
    assert all_pdfs(paths.standards) == []


# ---------------------------------------------------------------------------
# 边界：符号链接 / junction 绝不越出 standards 树
# ---------------------------------------------------------------------------


def test_symlinked_package_directory_is_never_followed_out_of_the_standards_tree(
    tmp_path: Path,
) -> None:
    """指向 standards 之外的链接目录不得导致树外 PDF 被删除。"""
    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    paths, _database, _standards, audit, service = make_service(
        tmp_path / "appdata", library.public_key_path
    )
    service.install(library.package)

    outside = tmp_path / "outside"
    outside.mkdir()
    outside_pdf = outside / "outside.pdf"
    outside_pdf.write_bytes(b"%PDF-1.4 outside the standards tree")

    link = paths.standards / "linked-package"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        # Windows 上创建目录符号链接需要开发者模式或提升权限；该环境不具备。
        # 真实的 reparse point 覆盖由下面的 junction 用例提供。
        pytest.skip("当前环境无法创建目录符号链接（需要开发者模式或管理员权限）")

    # 链接目录内部（树外）的 PDF 必须原样保留，也不计入清理。
    assert outside_pdf.is_file()
    removed = service._remove_legacy_source_directories()
    assert removed == (0, 0, 0)
    assert outside_pdf.read_bytes() == b"%PDF-1.4 outside the standards tree"
    assert audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED) == []


def test_junction_package_directory_is_never_followed_out_of_the_standards_tree(
    tmp_path: Path,
) -> None:
    """Windows junction（``mklink /J``，无需管理员）同样不得被跟随到树外。

    ``Path.is_symlink()`` 对 junction 返回 ``False``，所以这里真正验证的是
    「解析后的路径必须仍在 ``paths.standards`` 内」这道护栏。
    """
    if sys.platform != "win32":
        pytest.skip("junction 是 Windows 专有概念")
    import subprocess

    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    paths, _database, _standards, audit, service = make_service(
        tmp_path / "appdata", library.public_key_path
    )
    service.install(library.package)

    outside = tmp_path / "outside-junction-target"
    outside.mkdir()
    outside_flat = outside / "outside-flat.pdf"
    outside_flat.write_bytes(b"%PDF-1.4 outside flat")
    outside_sources = outside / "sources"
    outside_sources.mkdir()
    outside_nested = outside_sources / "outside-nested.pdf"
    outside_nested.write_bytes(b"%PDF-1.4 outside nested")

    junction = paths.standards / "junction-package"
    created = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        text=True,
    )
    if created.returncode != 0:
        pytest.skip(f"当前环境无法创建 junction：{created.stdout}{created.stderr}")
    assert junction.is_dir()

    # 树外内容必须原样保留，且完全不计入清理。
    removed = service._remove_legacy_source_directories()
    assert removed == (0, 0, 0)
    assert outside_flat.read_bytes() == b"%PDF-1.4 outside flat"
    assert outside_nested.read_bytes() == b"%PDF-1.4 outside nested"
    assert audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED) == []

    # 对照：树内真正的旧版布局仍然会被清理（证明扫描本身没被 junction 影响）。
    inside = paths.standards / "real-legacy-package"
    materialize_legacy_layout(inside, LEGACY_LAYOUT_BOTH, pdf_count=1)
    assert service._remove_legacy_source_directories() == (1, 1, 1)
    assert outside_flat.is_file() and outside_nested.is_file()
    assert list(inside.glob("*.pdf")) == []
    assert not (inside / "sources").exists()


# ---------------------------------------------------------------------------
# §五 老备份恢复之后的启动路径：同一个 Gate 必须再次经过
# ---------------------------------------------------------------------------


def protocol_methods(name: str) -> set[str]:
    """读 ``uebench.application.ports`` 的 AST，取出某个 Protocol 声明的方法名。

    应用层的端口方法只能从端口定义本身核对（application 层禁止导入
    infrastructure），所以这里用 AST 而不是导入。同模块内的基类（例如
    ``PackageDiscoveryPort``）会被递归合并；``Protocol`` 这类外来基类忽略。
    """
    import ast

    module = ROOT / "src" / "uebench" / "application" / "ports.py"
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    classes = {
        node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
    }
    assert name in classes, f"application/ports.py 未声明 Protocol：{name}"

    methods: set[str] = set()
    for item in classes[name].body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.add(item.name)
    for base in classes[name].bases:
        if isinstance(base, ast.Name) and base.id in classes:
            methods |= protocol_methods(base.id)
    return methods


def legacy_pdfs_under(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.pdf") if path.is_file())


def cleanup_audit_rows(audit: AuditRepository) -> list:
    return audit_rows(audit, AUDIT_LEGACY_SOURCES_REMOVED)


def test_cleanup_legacy_sources_is_declared_on_the_application_port() -> None:
    """端口必须声明 ``cleanup_legacy_sources``，应用层才可能不导入 infrastructure。

    应用层唯一可见的契约是 ``StandardPackagePort``；因此"启动对账也过闸门"这件事
    必须先在端口上声明。实现由 ``StandardPackageService`` 提供（下一个用例验证它真的
    落地、且与 ``install`` 用的是同一份代码、幂等、计数真实）。
    """
    declared = protocol_methods("StandardPackagePort")
    assert "cleanup_legacy_sources" in declared, sorted(declared)
    assert {"install", "preview", "discover", "latest_manifest", "list_history"} <= declared


def test_service_implements_every_declared_port_method() -> None:
    """声明与实现必须一一对应：端口上的方法在服务上都是可调用的真实实现。"""
    import inspect

    declared = protocol_methods("StandardPackagePort")
    missing = [
        name
        for name in sorted(declared)
        if not callable(getattr(StandardPackageService, name, None))
    ]
    assert not missing, f"StandardPackageService 未实现端口方法：{missing}"
    signature = inspect.signature(StandardPackageService.cleanup_legacy_sources)
    assert list(signature.parameters) == ["self"], signature
    # 三个真实计数：目录 / 目录内文件 / 平铺 PDF（源码带 ``from __future__ import
    # annotations``，所以注解是字符串）。
    assert str(signature.return_annotation) in {
        "tuple[int, int, int]",
        "<class 'tuple'>",
    }, signature.return_annotation


def test_cleanup_legacy_sources_is_the_same_gate_and_is_idempotent(tmp_path: Path) -> None:
    """端口方法 == ``install`` 用的那一个 Gate：真实计数 + 幂等零计数。"""
    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    paths, _database, _standards, audit, service = make_service(
        tmp_path / "appdata", library.public_key_path
    )
    service.install(library.package)
    package_directory = paths.standards / library.package_id
    materialize_legacy_layout(package_directory, LEGACY_LAYOUT_BOTH, pdf_count=3)

    # 真实计数（1 个 sources 目录 / 3 个文件 / 3 个平铺 PDF），与内部方法完全一致。
    assert service.cleanup_legacy_sources() == (1, 3, 3)
    assert all_pdfs(paths.standards) == []
    assert not (package_directory / "sources").exists()
    assert (package_directory / "corrections.json").is_file()
    details = audit_details(audit, AUDIT_LEGACY_SOURCES_REMOVED)
    assert len(details) == 1, details
    assert details[0]["directories_removed"] == 1
    assert details[0]["files_removed"] == 3
    assert details[0]["flat_files_removed"] == 3
    assert details[0]["verified"] is True

    # 幂等：第二次没有东西可清 → 全零、不新增审计行。
    assert service.cleanup_legacy_sources() == (0, 0, 0)
    assert len(cleanup_audit_rows(audit)) == 1


def test_startup_reconciliation_passes_the_gate_before_the_decision_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """运行时契约：对账在决策表之前、且**恰好一次**过闸门——包括 NOOP。

    这条断言是原缺口的直接护栏：只要 ``reconcile`` 把清理放在决策表之后（或者只在
    INSTALL/UPGRADE 时才做），"从老备份恢复 + 已安装包与内置包相同（NOOP）" 的场景
    就会漏掉清理。
    """
    from uebench.application.package_reconciliation import (
        PackageReconciliationService,
        ReconciliationAction,
    )
    from uebench.infrastructure.packages import _data_version_key

    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    context = create_context(tmp_path / "appdata", public_key_path=library.public_key_path)
    try:
        directory = bundled_directory(tmp_path, library.package)
        assert package_id_of(library.package) == library.package_id
        # 第一次对账：INSTALL 会把旧版布局一并清掉（install 自身的闸门）。
        service = PackageReconciliationService(
            context.package_service, data_version_key=_data_version_key
        )
        first = service.reconcile(directory)
        assert first.action is ReconciliationAction.INSTALL
        cleanup_after_first = len(cleanup_audit_rows(context.audit))

        # 复现旧版布局（等价于「从老备份恢复」把老 PDF 放回活目录）。
        package_directory = context.paths.standards / library.package_id
        materialize_legacy_layout(package_directory, LEGACY_LAYOUT_BOTH, pdf_count=2)
        assert len(all_pdfs(context.paths.standards)) == 4

        order: list[str] = []
        real_cleanup = StandardPackageService.cleanup_legacy_sources
        real_discover = PackageReconciliationService.discover_bundled_package
        # 记录顺序：只有先清理、再发现内置包（决策）才能得到 ["cleanup", "decide"]。
        calls: dict[object, list[str]] = {context.package_service: order}
        monkeypatch.setattr(
            PackageReconciliationService,
            "discover_bundled_package",
            lambda self, target: (
                calls[self._packages].append("decide"),
                real_discover(self, target),
            )[1],
        )
        monkeypatch.setattr(
            StandardPackageService,
            "cleanup_legacy_sources",
            lambda self: (
                calls[self].append("cleanup"),
                real_cleanup(self),
            )[1],
        )

        outcome = service.reconcile(directory)

        # 决策确实是 NOOP —— 清理绝不是靠 INSTALL/UPGRADE 顺带发生的。
        assert outcome.action is ReconciliationAction.NOOP
        assert outcome.executed is False
        # 顺序：清理先于「发现内置包/决策」，且只发生一次。
        assert order == ["cleanup", "decide"], order
        # 活目录被清干净，并且留下了**真实**计数的成功审计。
        assert all_pdfs(context.paths.standards) == []
        assert not (package_directory / "sources").exists()
        assert len(cleanup_audit_rows(context.audit)) == cleanup_after_first + 1
        details = audit_details(context.audit, AUDIT_LEGACY_SOURCES_REMOVED)[-1]
        assert details["directories_removed"] == 1
        assert details["files_removed"] == 2
        assert details["flat_files_removed"] == 2
        assert details["verified"] is True
        # 没有新备份、没有新安装、包历史不变。
        assert len(context.application.list_package_history(5)) == 1
    finally:
        context.database.dispose()
        close_logging()


def test_startup_reconciliation_aborts_fail_closed_on_a_locked_legacy_pdf(
    tmp_path: Path,
) -> None:
    """对账路径的 fail-closed：被占用的旧 PDF 让对账在决策前中止。

    与 install 路径的占用用例同款做法（``open(path, "rb")`` 保持打开，Windows 上
    删除真实失败），但这里驱动的是**正常启动/对账**路径，且决策本会是 NOOP ——
    这证明闸门不会因为"反正不装包"而被跳过。
    """
    if sys.platform != "win32":
        pytest.skip("真实文件占用只能在 Windows 上复现（其他平台允许删除已打开的文件）")

    from uebench.application.package_reconciliation import (
        PackageReconciliationService,
        ReconciliationAction,
    )
    from uebench.infrastructure.packages import _data_version_key

    work = tmp_path / "work"
    library = synthetic_legacy_library(work)
    context = create_context(tmp_path / "appdata", public_key_path=library.public_key_path)
    try:
        directory = bundled_directory(tmp_path, library.package)
        service = PackageReconciliationService(
            context.package_service, data_version_key=_data_version_key
        )
        assert service.reconcile(directory).action is ReconciliationAction.INSTALL

        package_directory = context.paths.standards / library.package_id
        created = materialize_legacy_layout(package_directory, LEGACY_LAYOUT_BOTH, pdf_count=2)
        locked_pdf = sorted(created["sources"].glob("*.pdf"))[0]
        locked_bytes = locked_pdf.read_bytes()
        backups_before = backup_names(context.paths)
        history_before = installed_package_ids(context.package_service)
        audits_before = cleanup_audit_rows(context.audit)

        with open(locked_pdf, "rb") as handle:
            assert handle.read(8).startswith(b"%PDF")
            with pytest.raises(StandardPackageError) as failure:
                service.reconcile(directory)

        message = str(failure.value)
        assert "无法删除旧版本遗留在用户数据目录中的标准原文" in message
        assert "安装已中止" in message
        assert "PermissionError" in message or "另一个程序正在使用此文件" in message
        assert "重试" in message
        assert str(locked_pdf.parent) in message

        # 中止语义：无成功审计、无新备份、无半安装、数据库完好。
        assert cleanup_audit_rows(context.audit) == audits_before
        assert backup_names(context.paths) == backups_before
        assert installed_package_ids(context.package_service) == history_before
        assert not (context.paths.standards / "synthetic-gate-locked").exists()
        assert locked_pdf.is_file() and locked_pdf.read_bytes() == locked_bytes
        assert context.database.path.exists()
    finally:
        context.database.dispose()
        close_logging()
