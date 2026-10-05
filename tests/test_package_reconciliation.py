"""ECQ-RS05 运行时标准包对账（Runtime Standard Package Reconciliation）测试。

覆盖决策表 A–F、升级、冲突、损坏内置包、历史评价快照保全、内置包发现的
确定性，以及纯决策函数的表驱动用例。

数据目录一律使用 ``tmp_path`` 隔离（``--basetemp`` 必须指向 ``$env:TEMP``：
仓库 ``work\\`` 目录存在 ACL 问题，会让 SQLite 写入慢约 200 倍）。

夹具与外部依赖
--------------
核心场景（A–F、升级、冲突、损坏包、历史评价、发现确定性）一律使用**仓库内**的
确定性夹具：

* ``CURRENT_PACKAGE``：仓库内固定的正式标准包（CI 一定有）；
* 合成包：由测试时临时生成的 Ed25519 密钥签名，公钥经
  ``create_context(..., public_key_path=...)`` 交给组合根。

因此核心场景既不需要 ``G:\\ECQuota-Archive``，也不需要
``work/signing/development-private-key.pem``，并且不会因为二者缺失而 skip。
只有显式以「归档历史证据」为目的的用例（``source_bearing_predecessor`` 逐字节对比、
真实 r1→r2 取代关系）才在归档不可用时优雅跳过，跳过原因会在 ``-ra`` 摘要里列出。
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text

from uebench.application.package_reconciliation import (
    BUNDLED_PACKAGE_GLOB,
    BundledPackageIdentity,
    InstalledPackageIdentity,
    PackageReconciliationService,
    ReconciliationAction,
    ReconciliationReason,
    decide,
)
from uebench.bootstrap import create_context
from uebench.domain.models import EvaluationRequest, InputMode, InputValue
from uebench.infrastructure.logging import close_logging
from uebench.infrastructure.packages import (
    AUDIT_LEGACY_SOURCES_REMOVED,
    StandardPackageBuilder,
    StandardPackageError,
    _data_version_key,
)
from uebench.main import reconcile_standard_package

from .test_engine import make_standard

try:  # 测试目录既可能是普通目录，也可能被当作包
    from _legacy_assets import (
        LEGACY_LAYOUT_BOTH,
        LEGACY_LAYOUT_FLAT,
        materialize_legacy_layout,
        session_legacy_package,
        synthetic_legacy_library,
    )
except ModuleNotFoundError:  # pragma: no cover - 取决于 pytest 的导入模式
    from tests._legacy_assets import (
        LEGACY_LAYOUT_BOTH,
        LEGACY_LAYOUT_FLAT,
        materialize_legacy_layout,
        session_legacy_package,
        synthetic_legacy_library,
    )

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = ROOT / "src" / "uebench" / "resources" / "update_public_key.pem"
PACKAGE_DIR = ROOT / "release" / "standard-packages"
#: 固定（已发布）标准包：当前 = 2026.10-published.4（GB29446 r2，去原文包）。
CURRENT_PACKAGE = PACKAGE_DIR / "initial-standard-package-published.uebench"
#: 旧包已移出仓库（REFERENCE ONLY）；取得的是归档件的**副本**。核心场景不再依赖它。
OLD_PACKAGE = session_legacy_package()

GB29446 = "gb-29446-2019"
GB29446_COKING_PRODUCT = "gb_29446-2019-coking-coal"
AUDIT_ACTION_INSTALL = "STANDARD_PACKAGE_INSTALL"


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def require_pinned_packages() -> None:
    """固定正式包是仓库内固定件：缺失即硬失败，绝不 skip。"""
    assert CURRENT_PACKAGE.is_file(), f"缺少固定标准包：{CURRENT_PACKAGE}"


def require_archived_old_package() -> None:
    """归档旧包只作历史证据：不可用时优雅跳过（核心场景不再依赖它）。

    **唯一**允许的跳过类型：不伪造归档件的替代物，也不把它算进核心兼容覆盖。
    """
    if not OLD_PACKAGE.is_file():
        pytest.skip(
            "历史归档证据用例（evidence-only）：仓内合成夹具无法替代真实归档旧包 "
            f"（G:\\ECQuota-Archive 不可用：{OLD_PACKAGE}）；不计入核心兼容覆盖"
        )


def manifest_of(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("manifest.json"))


def bundled_directory(tmp_path: Path, *entries: tuple[Path, str]) -> Path:
    """构造一个内置标准包目录（文件名可指定，用于发现顺序用例）。"""
    directory = tmp_path / "bundled"
    directory.mkdir(parents=True, exist_ok=True)
    for source, name in entries:
        shutil.copyfile(source, directory / name)
    return directory


def reconciler(context) -> PackageReconciliationService:
    return PackageReconciliationService(context.package_service, data_version_key=_data_version_key)


def backup_names(context) -> set[str]:
    return {path.name for path in context.paths.backups.glob("pre-package-*.uebackup")}


def install_audit_rows(context) -> int:
    return sum(1 for entry in context.application.list_audit(500) if entry.action == AUDIT_ACTION_INSTALL)


def standards_snapshot(context) -> dict[str, str]:
    """标准目录逐文件哈希；用于证明“未安装/未覆盖”。"""
    snapshot: dict[str, str] = {}
    for path in sorted(context.paths.standards.rglob("*")):
        if path.is_file():
            relative = str(path.relative_to(context.paths.standards))
            snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def policy_state(context) -> tuple[str | None, set[str], int, dict[str, str]]:
    """已安装身份 + 备份集合 + 安装审计行数 + 标准目录内容。"""
    history = context.application.list_package_history(5)
    newest = history[0].package_id if history else None
    return newest, backup_names(context), install_audit_rows(context), standards_snapshot(context)


def standards_pdfs(context) -> list[Path]:
    """活目录（``paths.standards``）下的真实 PDF 文件，排序。"""
    return sorted(
        path for path in context.paths.standards.rglob("*.pdf") if path.is_file()
    )


def legacy_cleanup_rows(context) -> list:
    """清理闸门的成功审计行（§五 的唯一成功凭证）。"""
    return [
        entry
        for entry in context.audit.list_recent(500)
        if entry.action == AUDIT_LEGACY_SOURCES_REMOVED
    ]


def evaluation_rows(context, evaluation_id: str) -> int:
    with context.database.engine.connect() as connection:
        return int(
            connection.execute(
                text("SELECT COUNT(*) FROM evaluations WHERE evaluation_id = :id"),
                {"id": evaluation_id},
            ).scalar_one()
        )


def developer_private_key() -> Ed25519PrivateKey:
    """临时（ephemeral）Ed25519 私钥：由测试现场生成，绝不读取仓库内私钥。

    键名保留是为了不改动调用点；语义已从「开发私钥」变为「本用例的临时签名密钥」。
    """
    return Ed25519PrivateKey.generate()


def synthetic_bundled_package(
    directory: Path,
    private_key: Ed25519PrivateKey,
    *,
    package_id: str,
    data_version: str,
    level_1: str = "10",
    issue_day: int = 23,
    standard_id: str | None = None,
    standard_number: str | None = None,
    rule_revision: int = 1,
) -> Path:
    """生成一个**名字匹配内置包 glob** 的合成包，可当内置包直接对账安装。"""
    directory.mkdir(parents=True, exist_ok=True)
    return build_test_package(
        directory,
        private_key,
        package_id=package_id,
        data_version=data_version,
        level_1=level_1,
        issue_day=issue_day,
        file_name=f"initial-standard-package-{package_id}.uebench",
        standard_id=standard_id,
        standard_number=standard_number,
        rule_revision=rule_revision,
    )


def build_test_package(
    directory: Path,
    private_key: Ed25519PrivateKey,
    *,
    package_id: str,
    data_version: str,
    level_1: str = "10",
    issue_day: int = 23,
    file_name: str | None = None,
    standard_id: str | None = None,
    standard_number: str | None = None,
    rule_revision: int = 1,
) -> Path:
    """用真实 ``StandardPackageBuilder`` 生成可验签的测试标准包。"""
    definition = make_standard(standard_id=standard_id, standard_number=standard_number)
    definition.rule_revision = rule_revision
    definition.products[0].indicators[0].thresholds.level_1.value = level_1
    source = directory / definition.source_file
    source.write_bytes(b"placeholder-source-for-reconciliation")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    definition.source_sha256 = digest
    for product in definition.products:
        for indicator in product.indicators:
            for reference in indicator.source_references:
                reference.source_sha256 = digest
    return StandardPackageBuilder(private_key).build(
        directory / (file_name or f"{package_id}.uebench"),
        [definition],
        {definition.source_file: source},
        package_id=package_id,
        data_version=data_version,
        issued_at=datetime(2026, 8, issue_day, tzinfo=timezone.utc),
    )


def tampered_copy(source: Path, target: Path) -> Path:
    """改写一个 definitions/*.json 成员的字节（签名/哈希必然不匹配）。"""
    with zipfile.ZipFile(source) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    name = sorted(item for item in entries if item.startswith("definitions/"))[0]
    payload = bytearray(entries[name])
    payload[-2] ^= 0x01
    entries[name] = bytes(payload)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member, data in entries.items():
            archive.writestr(member, data)
    return target


def unsigned_copy(source: Path, target: Path) -> Path:
    """移除 ``signature.ed25519`` 成员（未签名包）。"""
    with zipfile.ZipFile(source) as archive:
        entries = {
            name: archive.read(name)
            for name in archive.namelist()
            if name != "signature.ed25519"
        }
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member, data in entries.items():
            archive.writestr(member, data)
    return target


def mutate_pinned_definition(
    source: Path,
    target: Path,
    private_key: Ed25519PrivateKey,
    *,
    package_id: str,
    data_version: str,
    issued_at: str,
) -> Path:
    """取真实固定包，改一个 GB29446 r2 阈值（保持 id / version / rule_revision），重新签名。

    这是现场“用户库的规则来自其它渠道包、与内置包同 (标准, 版本, 规则版本) 但内容
    不同”的最小复现：包本身签名/哈希全部有效，但装不进已有规则行。
    """
    with zipfile.ZipFile(source) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(entries["manifest.json"])
    member = next(
        item
        for item in manifest["files"]
        if item["kind"] == "definition" and "gb-29446" in item["path"]
    )
    definition = json.loads(entries[member["path"]])
    assert definition["id"] == GB29446 and definition["rule_revision"] == 2
    definition["products"][0]["indicators"][0]["thresholds"]["level_1"]["value"] = "5.5"
    payload = json.dumps(
        definition, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    entries[member["path"]] = payload
    member["sha256"] = hashlib.sha256(payload).hexdigest()
    member["size"] = len(payload)
    manifest["package_id"] = package_id
    manifest["data_version"] = data_version
    manifest["issued_at"] = issued_at
    manifest_bytes = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    entries["manifest.json"] = manifest_bytes
    entries["signature.ed25519"] = private_key.sign(manifest_bytes)

    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return target


# ---------------------------------------------------------------------------
# 夹具
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def ephemeral_keypair(tmp_path_factory: pytest.TempPathFactory) -> tuple[Ed25519PrivateKey, Path]:
    """会话级临时密钥对：合成内置包用它的公钥装配组合根。

    这样核心对账场景不再依赖 ``work/signing/development-private-key.pem``。
    """
    directory = tmp_path_factory.mktemp("ephemeral-key")
    private_key = Ed25519PrivateKey.generate()
    public_key_path = directory / "ephemeral-public-key.pem"
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return private_key, public_key_path


@pytest.fixture
def context(tmp_path: Path):
    """真实组合根 + 真实产品公钥（安装仓库内固定正式包）。"""
    if not PUBLIC_KEY.is_file():
        pytest.skip(f"缺少内置更新公钥：{PUBLIC_KEY}")
    application_context = create_context(tmp_path / "data", public_key_path=PUBLIC_KEY)
    try:
        yield application_context
    finally:
        application_context.database.dispose()
        # ``configure_logging`` 为每个数据目录挂一个滚动文件 handler；Windows 上
        # 必须先释放句柄，pytest 才能删除 tmp_path。
        close_logging()


def synthetic_context(tmp_path: Path, ephemeral_keypair):
    """真实组合根 + 会话级临时公钥（安装合成内置包，无需开发私钥）。"""
    _private_key, ephemeral_public_key = ephemeral_keypair
    return create_context(tmp_path / "synthetic-data", public_key_path=ephemeral_public_key)


# ---------------------------------------------------------------------------
# 9. 纯决策函数：A–F 决策表 + 无法解析的 data_version
# ---------------------------------------------------------------------------


def _installed(
    package_id: str = "pkg-current",
    data_version: str = "2026.10-published.3",
    sha256: str = "a" * 64,
    installed_at: datetime | None = None,
) -> InstalledPackageIdentity:
    return InstalledPackageIdentity(
        package_id=package_id,
        data_version=data_version,
        package_sha256=sha256,
        installed_at=installed_at or datetime(2026, 10, 4, tzinfo=timezone.utc),
    )


def _bundled(
    package_id: str | None = "pkg-current",
    data_version: str | None = "2026.10-published.3",
    sha256: str | None = "a" * 64,
    *,
    valid: bool = True,
    errors: tuple[str, ...] = (),
) -> BundledPackageIdentity:
    if not valid:
        package_id, data_version, sha256 = None, None, None
    return BundledPackageIdentity(
        path="/bundled/initial-standard-package-published.uebench",
        package_id=package_id,
        data_version=data_version,
        package_sha256=sha256,
        valid=valid,
        errors=list(errors),
    )


TABLE_CASES = (
    # (case, installed, bundled, action, reason)
    ("A", None, _bundled(), ReconciliationAction.INSTALL, ReconciliationReason.NO_INSTALLED_PACKAGE),
    (
        "B",
        _installed(),
        _bundled(),
        ReconciliationAction.NOOP,
        ReconciliationReason.IDENTICAL_PACKAGE,
    ),
    (
        "C",
        _installed(package_id="pkg-old", data_version="2026.09-published.2", sha256="b" * 64),
        _bundled(),
        ReconciliationAction.UPGRADE,
        ReconciliationReason.BUNDLED_NEWER,
    ),
    (
        "D",
        _installed(package_id="pkg-newer", data_version="2026.11-published.4", sha256="e" * 64),
        _bundled(),
        ReconciliationAction.NO_DOWNGRADE,
        ReconciliationReason.INSTALLED_NEWER,
    ),
    (
        "E-sha",
        _installed(sha256="c" * 64),
        _bundled(),
        ReconciliationAction.CONFLICT,
        ReconciliationReason.SAME_DATA_VERSION_DIFFERENT_IDENTITY,
    ),
    (
        "E-id",
        _installed(package_id="pkg-other", sha256="c" * 64),
        _bundled(),
        ReconciliationAction.CONFLICT,
        ReconciliationReason.SAME_DATA_VERSION_DIFFERENT_IDENTITY,
    ),
    (
        "F",
        _installed(),
        _bundled(valid=False, errors=("标准包签名无效",)),
        ReconciliationAction.INVALID,
        ReconciliationReason.BUNDLED_INVALID,
    ),
    (
        "missing-bundled",
        _installed(),
        None,
        ReconciliationAction.MISSING,
        ReconciliationReason.NO_BUNDLED_PACKAGE,
    ),
)


@pytest.mark.parametrize(
    ("case", "installed", "bundled", "expected_action", "expected_reason"),
    TABLE_CASES,
    ids=[case[0] for case in TABLE_CASES],
)
def test_decision_table_is_exhaustive_and_never_raises(
    case: str,
    installed: InstalledPackageIdentity | None,
    bundled: BundledPackageIdentity | None,
    expected_action: ReconciliationAction,
    expected_reason: ReconciliationReason,
) -> None:
    outcome = decide(installed, bundled, data_version_key=_data_version_key)

    assert outcome.action is expected_action, case
    assert outcome.reason is expected_reason, case
    assert outcome.executed is False, "纯决策函数绝不执行安装"
    assert outcome.message, "每种结果都必须有可读原因"
    assert outcome.bundled is bundled
    # 可序列化：JSON 往返不丢信息（枚举降级为稳定字符串）。
    payload = json.loads(json.dumps(outcome.to_dict()))
    assert payload["action"] == expected_action.value
    assert payload["reason"] == expected_reason.value


def test_decision_reports_invalid_bundled_errors_and_never_succeeds() -> None:
    outcome = decide(
        _installed(),
        _bundled(valid=False, errors=("标准包签名无效", "文件大小或哈希不匹配：definitions/x.json")),
        data_version_key=_data_version_key,
    )
    assert outcome.action is ReconciliationAction.INVALID
    assert outcome.succeeded is False
    assert outcome.errors == ["标准包签名无效", "文件大小或哈希不匹配：definitions/x.json"]


def test_decision_treats_unparseable_or_missing_data_version_as_conflict() -> None:
    """任一侧无法排序（含已安装侧 data_version 缺失）都不得判为“更旧”。"""
    bundled = _bundled(data_version="2026.10-published.3")
    for data_version in ("", "not-a-version", "2026", "2026.十"):
        outcome = decide(
            # 身份不同（否则相同的 package_id + sha256 应先判 B/NOOP）。
            _installed(package_id="pkg-unknown", data_version=data_version, sha256="b" * 64),
            bundled,
            data_version_key=_data_version_key,
        )
        assert outcome.action is ReconciliationAction.CONFLICT, data_version
        assert outcome.reason is ReconciliationReason.DATA_VERSION_NOT_ORDERABLE
        assert outcome.executed is False

    # 内置侧无法解析时同样冲突（即使内置侧 issued_at 更晚）。
    unparseable_bundled = _bundled(data_version="unknown-version")
    outcome = decide(
        _installed(package_id="pkg-old", data_version="2026.09-published.2"),
        unparseable_bundled,
        data_version_key=_data_version_key,
    )
    assert outcome.action is ReconciliationAction.CONFLICT
    assert outcome.reason is ReconciliationReason.DATA_VERSION_NOT_ORDERABLE
    assert "不覆盖" in outcome.message


def test_decision_noop_identity_requires_same_package_id_and_sha256() -> None:
    """同 package_id 但 sha256 不同不是 B；sha256 相同但 package_id 不同也不是 B。"""
    same_version_other_sha = decide(
        _installed(sha256="d" * 64), _bundled(), data_version_key=_data_version_key
    )
    assert same_version_other_sha.action is ReconciliationAction.CONFLICT

    other_id_same_sha = decide(
        _installed(package_id="pkg-other"), _bundled(), data_version_key=_data_version_key
    )
    assert other_id_same_sha.action is ReconciliationAction.CONFLICT


# ---------------------------------------------------------------------------
# A. 空数据目录 → INSTALL
# ---------------------------------------------------------------------------


def test_empty_library_installs_bundled_package(context, tmp_path: Path) -> None:
    require_pinned_packages()
    manifest = manifest_of(CURRENT_PACKAGE)
    assert context.application.list_package_history() == []
    assert list(context.paths.standards.iterdir()) == [], "首次运行前标准目录应为空"

    directory = bundled_directory(tmp_path, (CURRENT_PACKAGE, CURRENT_PACKAGE.name))
    outcome = reconcile_standard_package(context, directory)

    assert outcome.action is ReconciliationAction.INSTALL
    assert outcome.reason is ReconciliationReason.NO_INSTALLED_PACKAGE
    assert outcome.executed is True
    assert outcome.installed_before is None
    assert outcome.standards_installed == manifest["standard_count"]
    assert outcome.backup_path and Path(outcome.backup_path).is_file()

    history = context.application.list_package_history(5)
    assert history[0].package_id == manifest["package_id"]
    assert history[0].data_version == manifest["data_version"]
    assert history[0].package_sha256 == hashlib.sha256(CURRENT_PACKAGE.read_bytes()).hexdigest()
    assert outcome.installed is not None and outcome.installed.package_id == manifest["package_id"]
    # 组合根把结果记录到 facade 上，界面/自检可直接读取。
    assert context.application.last_package_reconciliation() is outcome


def test_missing_bundled_directory_is_missing_and_installs_nothing(context, tmp_path: Path) -> None:
    outcome = reconciler(context).reconcile(tmp_path / "not-there")
    assert outcome.action is ReconciliationAction.MISSING
    assert outcome.reason is ReconciliationReason.NO_BUNDLED_PACKAGE
    assert outcome.executed is False
    assert context.application.list_package_history() == []
    assert backup_names(context) == set()


# ---------------------------------------------------------------------------
# B. 第二次对账 → NOOP（无备份、无第二次审计）
# ---------------------------------------------------------------------------


def test_second_reconciliation_is_noop_without_backup_or_audit_noise(context, tmp_path: Path) -> None:
    require_pinned_packages()
    directory = bundled_directory(tmp_path, (CURRENT_PACKAGE, CURRENT_PACKAGE.name))
    service = reconciler(context)

    first = service.reconcile(directory)
    assert first.action is ReconciliationAction.INSTALL
    backups_after_first = backup_names(context)
    audits_after_first = install_audit_rows(context)
    standards_after_first = standards_snapshot(context)
    assert len(backups_after_first) == 1 and audits_after_first == 1

    second = service.reconcile(directory)

    assert second.action is ReconciliationAction.NOOP
    assert second.reason is ReconciliationReason.IDENTICAL_PACKAGE
    assert second.executed is False, "NOOP 不得再次安装"
    # 已安装同一包时 preview 会报“该标准包已安装”（安装闸门，不是完整性缺陷），
    # 因此 NOOP 仍必须判定为“内置包有效”。
    assert second.bundled is not None and second.bundled.valid is True
    assert second.bundled.errors == []
    assert second.bundled.install_blockers == ["该标准包已安装"]
    assert backup_names(context) == backups_after_first, "NOOP 不得新增备份"
    assert install_audit_rows(context) == audits_after_first, "NOOP 不得新增安装审计"
    assert standards_snapshot(context) == standards_after_first
    assert len(context.application.list_package_history(5)) == 1


# ---------------------------------------------------------------------------
# C. 旧包 → 当前包 = UPGRADE
# ---------------------------------------------------------------------------


def test_older_installed_package_is_upgraded_to_bundled(
    tmp_path: Path, ephemeral_keypair
) -> None:
    """合成内置包：旧版本 → 新版本 = UPGRADE（真实安装、真实备份、不覆盖旧备份）。"""
    private_key, _public_key = ephemeral_keypair
    context = synthetic_context(tmp_path, ephemeral_keypair)
    try:
        work = tmp_path / "build"
        old_package = synthetic_bundled_package(
            work,
            private_key,
            package_id="recon-old",
            data_version="2026.09-published.2",
            rule_revision=1,
        )
        current_package = synthetic_bundled_package(
            work,
            private_key,
            package_id="recon-current",
            data_version="2026.10-published.3",
            level_1="11",
            issue_day=24,
            rule_revision=2,
        )
        old_manifest = manifest_of(old_package)
        current_manifest = manifest_of(current_package)
        service = reconciler(context)

        old_directory = bundled_directory(tmp_path / "old", (old_package, old_package.name))
        installed = service.reconcile(old_directory)
        assert installed.action is ReconciliationAction.INSTALL
        assert context.standards.get_published("gb-00000-2026").rule_revision == 1

        # 备份名带亚秒精度并带碰撞保护，因此连续两次安装必须各自留下一个可独立
        # 观察的备份——这里刻意不 sleep，正是要复现“同一秒内覆盖备份”的缺陷。
        backups_before = backup_names(context)
        assert backups_before, "首次安装必须留下 pre-package-*.uebackup 安全备份"
        first_backup = next(iter(backups_before))
        first_backup_bytes = (context.paths.backups / first_backup).read_bytes()
        first_backup_sha256 = hashlib.sha256(first_backup_bytes).hexdigest()

        current_directory = bundled_directory(
            tmp_path / "current", (current_package, current_package.name)
        )
        outcome = service.reconcile(current_directory)

        assert outcome.action is ReconciliationAction.UPGRADE
        assert outcome.reason is ReconciliationReason.BUNDLED_NEWER
        assert outcome.executed is True
        assert outcome.installed_before is not None
        assert outcome.installed_before.package_id == old_manifest["package_id"]
        assert outcome.installed_after is not None
        assert outcome.installed_after.package_id == current_manifest["package_id"]

        new_backups = backup_names(context) - backups_before
        assert len(new_backups) == 1, "升级必须留下 pre-package-*.uebackup 安全备份"
        # 回归：升级备份不得覆盖首次安装的备份，且首次备份字节/哈希逐字节不变。
        assert (context.paths.backups / first_backup).is_file()
        assert (context.paths.backups / first_backup).read_bytes() == first_backup_bytes
        assert (
            hashlib.sha256((context.paths.backups / first_backup).read_bytes()).hexdigest()
            == first_backup_sha256
        )
        assert outcome.backup_path not in backups_before
        # 新规则就位：r2 作为新修订加入，r1 仍然保留（历史评价必须可复算）。
        assert context.application.get_published_standard("gb-00000-2026").rule_revision == 2
        revisions = sorted(
            item.rule_revision
            for item in context.application.list_all_standards()
            if item.id == "gb-00000-2026"
        )
        assert revisions == [1, 2], "升级必须新增 r2 而不是替换 r1"
        assert len(context.application.list_all_standards()) == 2
        history = context.application.list_package_history(5)
        assert len(history) == 2
        assert history[0].package_id == current_manifest["package_id"]
        assert history[0].data_version == current_manifest["data_version"]
        assert install_audit_rows(context) == 2

        # 再跑一次：NOOP，且不得新增备份/审计。
        second = service.reconcile(current_directory)
        assert second.action is ReconciliationAction.NOOP
        assert second.reason is ReconciliationReason.IDENTICAL_PACKAGE
        assert second.executed is False
        assert backup_names(context) - backups_before == new_backups, "NOOP 不得新增备份"
        assert install_audit_rows(context) == 2
        assert len(context.application.list_package_history(5)) == 2
    finally:
        context.database.dispose()
        # ``configure_logging`` 为每个数据目录挂滚动文件 handler；Windows 上必须先
        # 释放句柄，pytest 才能删除 tmp_path。
        close_logging()


# ---------------------------------------------------------------------------
# D. 已安装更新 → NO_DOWNGRADE
# ---------------------------------------------------------------------------


def test_newer_installed_package_refuses_downgrade(tmp_path: Path, ephemeral_keypair) -> None:
    private_key, _public_key = ephemeral_keypair
    context = synthetic_context(tmp_path, ephemeral_keypair)
    try:
        work = tmp_path / "build"
        current_package = synthetic_bundled_package(
            work, private_key, package_id="recon-newer", data_version="2026.10-published.3"
        )
        old_package = synthetic_bundled_package(
            work,
            private_key,
            package_id="recon-older",
            data_version="2026.09-published.2",
            issue_day=22,
        )
        current_manifest = manifest_of(current_package)
        service = reconciler(context)

        current_directory = bundled_directory(
            tmp_path / "current", (current_package, current_package.name)
        )
        assert service.reconcile(current_directory).action is ReconciliationAction.INSTALL
        before = policy_state(context)

        old_directory = bundled_directory(tmp_path / "old", (old_package, old_package.name))
        outcome = service.reconcile(old_directory)

        assert outcome.action is ReconciliationAction.NO_DOWNGRADE
        assert outcome.reason is ReconciliationReason.INSTALLED_NEWER
        assert outcome.executed is False
        assert "降级" in outcome.message
        # 内置包本身是有效的：拒绝降级来自版本比较，不是完整性失败。
        assert outcome.bundled is not None and outcome.bundled.valid is True
        assert policy_state(context) == before, "拒绝降级时不得改动任何已安装状态"
        assert context.application.list_package_history(5)[0].package_id == current_manifest["package_id"]
    finally:
        context.database.dispose()
        close_logging()


# ---------------------------------------------------------------------------
# E. 同版本不同身份 / 与已安装规则内容冲突 → CONFLICT
# ---------------------------------------------------------------------------


def test_same_data_version_different_identity_conflicts_without_overwrite(
    tmp_path: Path, ephemeral_keypair
) -> None:
    """内容一致、仅包身份不同：判 E（SAME_DATA_VERSION_DIFFERENT_IDENTITY）。"""
    private_key, _public_key = ephemeral_keypair
    context = synthetic_context(tmp_path, ephemeral_keypair)
    try:
        work = tmp_path / "build"
        work.mkdir(parents=True)
        first = build_test_package(work, private_key, package_id="recon-conflict-a", data_version="2026.05-published.1")
        # 同一份定义内容（同一 level_1、同一原文），只有 manifest.package_id 不同。
        second = build_test_package(work, private_key, package_id="recon-conflict-b", data_version="2026.05-published.1")
        assert manifest_of(first)["package_id"] != manifest_of(second)["package_id"]

        service = reconciler(context)
        installed = service.reconcile(
            bundled_directory(
                tmp_path / "a", (first, "initial-standard-package-conflict-a.uebench")
            )
        )
        assert installed.action is ReconciliationAction.INSTALL
        before = policy_state(context)

        bundled = bundled_directory(
            tmp_path / "b", (second, "initial-standard-package-conflict-b.uebench")
        )
        identity = service.discover_bundled_package(bundled)
        assert identity is not None and identity.valid is True
        assert identity.install_blockers == [], "内容一致时 preview 只给 warning，不阻塞"

        outcome = service.reconcile(bundled)

        assert outcome.action is ReconciliationAction.CONFLICT
        assert outcome.reason is ReconciliationReason.SAME_DATA_VERSION_DIFFERENT_IDENTITY
        assert outcome.executed is False
        assert outcome.succeeded is False, "冲突必须显式上报，不能当作成功"
        assert "recon-conflict-a" in outcome.message and "recon-conflict-b" in outcome.message
        assert outcome.bundled is not None and outcome.bundled.valid is True
        # 已安装内容逐字节未变，也没有新增备份/审计/包记录。
        assert policy_state(context) == before
        assert len(context.application.list_package_history(200)) == 1
        assert context.application.list_package_history(5)[0].package_id == "recon-conflict-a"
    finally:
        context.database.dispose()
        close_logging()


def test_install_blockers_guard_never_calls_install() -> None:
    """``preview`` 已拒绝安装（非内容冲突）时不得给出 INSTALL/UPGRADE。"""
    bundled = _bundled()
    bundled = bundled.model_copy(
        update={
            "install_blockers": [
                "标准包发布时间早于当前已安装版本，禁止降级",
                "增量标准包依赖的父包未安装：pkg-parent",
            ]
        }
    )
    outcome = decide(
        _installed(package_id="pkg-old", data_version="2026.09-published.2", sha256="b" * 64),
        bundled,
        data_version_key=_data_version_key,
    )
    assert outcome.action is ReconciliationAction.CONFLICT
    assert outcome.reason is ReconciliationReason.INSTALL_BLOCKED
    assert outcome.executed is False
    assert outcome.errors == list(bundled.install_blockers)
    assert "无法安装" in outcome.message

    content_conflict = _bundled().model_copy(
        update={
            "install_blockers": [
                "标准版本已存在：GB 29446-2019 2019，如需变更必须递增标准包/规则版本",
            ]
        }
    )
    outcome = decide(
        _installed(package_id="pkg-old", data_version="2026.09-published.2", sha256="b" * 64),
        content_conflict,
        data_version_key=_data_version_key,
    )
    assert outcome.action is ReconciliationAction.CONFLICT
    assert outcome.reason is ReconciliationReason.INSTALLED_CONTENT_CONFLICT
    assert "GB 29446-2019 2019" in outcome.message


def test_content_conflict_message_truncates_long_conflict_lists() -> None:
    """真实场景一次可能有 44 条冲突：文案只列前三条 + “等 N 项”。"""
    blockers = [
        f"标准版本已存在：GB {10000 + index}-2021 2021，如需变更必须递增标准包/规则版本"
        for index in range(44)
    ]
    bundled = _bundled().model_copy(update={"install_blockers": blockers})
    outcome = decide(
        _installed(package_id="pkg-old", data_version="2026.09-published.2", sha256="b" * 64),
        bundled,
        data_version_key=_data_version_key,
    )
    assert outcome.action is ReconciliationAction.CONFLICT
    assert outcome.reason is ReconciliationReason.INSTALLED_CONTENT_CONFLICT
    assert "GB 10000-2021 2021" in outcome.message
    assert "GB 10001-2021 2021" in outcome.message
    assert "GB 10002-2021 2021" in outcome.message
    assert "GB 10003-2021 2021" not in outcome.message, "超出上限的标准不再逐条罗列"
    assert "等 44 项" in outcome.message
    assert len(outcome.errors) == 44, "原始冲突错误仍完整保留在 outcome.errors"


# ---------------------------------------------------------------------------
# F. 损坏/截断的内置包 → INVALID
# ---------------------------------------------------------------------------


def test_invalid_bundled_package_installs_nothing_and_keeps_existing_data(
    tmp_path: Path, ephemeral_keypair
) -> None:
    private_key, _public_key = ephemeral_keypair
    context = synthetic_context(tmp_path, ephemeral_keypair)
    try:
        work = tmp_path / "build"
        old_package = synthetic_bundled_package(
            work, private_key, package_id="recon-invalid-old", data_version="2026.09-published.2"
        )
        good_package = synthetic_bundled_package(
            work,
            private_key,
            package_id="recon-invalid-good",
            data_version="2026.10-published.3",
            level_1="11",
            issue_day=24,
        )
        service = reconciler(context)
        old_directory = bundled_directory(tmp_path / "old", (old_package, old_package.name))
        assert service.reconcile(old_directory).action is ReconciliationAction.INSTALL
        before = policy_state(context)

        broken = tmp_path / "broken"
        broken.mkdir(parents=True)
        tampered = tampered_copy(good_package, broken / "tampered.uebench")
        truncated = broken / "truncated.uebench"
        truncated.write_bytes(
            good_package.read_bytes()[: good_package.stat().st_size // 2]
        )
        unsigned = unsigned_copy(good_package, broken / "unsigned.uebench")

        for damaged in (tampered, truncated, unsigned):
            directory = bundled_directory(
                broken / damaged.stem, (damaged, good_package.name)
            )
            outcome = service.reconcile(directory)

            assert outcome.action is ReconciliationAction.INVALID, damaged.name
            assert outcome.reason is ReconciliationReason.BUNDLED_INVALID
            assert outcome.executed is False
            assert outcome.succeeded is False, "校验失败绝不能上报为已更新"
            assert outcome.errors, "必须给出校验失败原因"
            assert policy_state(context) == before, f"{damaged.name} 之后存量数据/备份/审计必须不变"

        assert context.standards.get_published("gb-00000-2026").rule_revision == 1
        assert (
            context.application.list_package_history(5)[0].package_id
            == manifest_of(old_package)["package_id"]
        )
    finally:
        context.database.dispose()
        close_logging()


def mutate_package_definition(
    source: Path,
    target: Path,
    private_key: Ed25519PrivateKey,
    *,
    package_id: str,
    data_version: str,
    issued_at: str,
    level_1: str = "5.5",
) -> Path:
    """取一个合成包，改其定义的内容但保持 (id, version, rule_revision)，重新签名。

    这是现场“用户库的规则来自其它渠道包、与内置包同 (标准, 版本, 规则版本) 但内容
    不同”的最小复现：包本身签名/哈希全部有效，但装不进已有规则行。
    """
    with zipfile.ZipFile(source) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(entries["manifest.json"])
    member = next(item for item in manifest["files"] if item["kind"] == "definition")
    definition = json.loads(entries[member["path"]])
    definition["products"][0]["indicators"][0]["thresholds"]["level_1"]["value"] = level_1
    payload = json.dumps(
        definition, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    entries[member["path"]] = payload
    member["sha256"] = hashlib.sha256(payload).hexdigest()
    member["size"] = len(payload)
    manifest["package_id"] = package_id
    manifest["data_version"] = data_version
    manifest["issued_at"] = issued_at
    manifest_bytes = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    entries["manifest.json"] = manifest_bytes
    entries["signature.ed25519"] = private_key.sign(manifest_bytes)

    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return target


def test_content_conflict_with_installed_rules_is_conflict_not_invalid(
    tmp_path: Path, ephemeral_keypair
) -> None:
    """集成评审缺陷回归：同 (标准, 版本, 规则版本) 内容不同 → CONFLICT，不得抛异常。

    缺陷版本把 ``标准版本已存在：`` 当成安装闸门吞掉，于是 bundled.valid 仍为 True、
    决策为 UPGRADE，随后 ``install()`` 以一批 ``StandardPackageError`` 抛出。
    夹具为合成包 + 会话级临时密钥，因此不依赖归档区与开发私钥。
    """
    private_key, _public_key = ephemeral_keypair
    context = synthetic_context(tmp_path, ephemeral_keypair)
    try:
        work = tmp_path / "build"
        current_package = synthetic_bundled_package(
            work,
            private_key,
            package_id="recon-content-conflict-base",
            data_version="2026.10-published.3",
        )
        service = reconciler(context)

        current_directory = bundled_directory(
            tmp_path / "current", (current_package, current_package.name)
        )
        assert service.reconcile(current_directory).action is ReconciliationAction.INSTALL
        before = policy_state(context)
        assert len(context.application.list_package_history(200)) == 1

        mutated = mutate_package_definition(
            current_package,
            tmp_path / "mutated" / "mutated.uebench",
            private_key,
            package_id="recon-mutated-content",
            data_version="2026.11-published.4",  # 严格更新：不拦内容冲突就会走 UPGRADE
            issued_at="2026-11-05T00:00:00Z",
        )
        mutated_manifest = manifest_of(mutated)
        current_key = _data_version_key(manifest_of(current_package)["data_version"])
        mutated_key = _data_version_key(mutated_manifest["data_version"])
        assert current_key is not None and mutated_key is not None and mutated_key > current_key

        directory = bundled_directory(
            tmp_path / "mutated-bundled", (mutated, current_package.name)
        )
        identity = service.discover_bundled_package(directory)
        assert identity is not None
        assert identity.valid is True, "内容冲突不是包损坏：不得判 INVALID"
        assert identity.errors == []
        assert any("标准版本已存在" in item for item in identity.install_blockers)

        # 组合根入口不得抛异常（这是被评审的失败点），必须返回可上报的 CONFLICT。
        outcome = reconcile_standard_package(context, directory)

        assert outcome.action is ReconciliationAction.CONFLICT
        assert outcome.reason is ReconciliationReason.INSTALLED_CONTENT_CONFLICT
        assert outcome.executed is False
        assert outcome.succeeded is False
        assert "GB 00000-2026 2026" in outcome.message
        assert outcome.errors

        # 无新备份、无新 standard_packages 行、已安装标准行逐字节不变。
        assert policy_state(context) == before
        assert len(context.application.list_package_history(200)) == 1
        assert context.application.get_published_standard("gb-00000-2026").rule_revision == 1
        assert context.application.last_package_reconciliation() is outcome
    finally:
        context.database.dispose()
        close_logging()


# ---------------------------------------------------------------------------
# 7. 历史评价快照在升级后保持原样（不按新规则重算）
# ---------------------------------------------------------------------------


def test_upgrade_preserves_saved_evaluation_snapshot(tmp_path: Path, ephemeral_keypair) -> None:
    """升级后历史评价快照保持原样（不按新规则重算）。

    定义沿用真实 GB 29446-2019 的 id / 编号（唯一纳入正式评价范围的标准，因此
    ``evaluate`` 会形成正式记录），但夹具本身是合成包 + 会话级临时密钥，所以本用例
    不依赖外部归档区与开发私钥。
    """
    private_key, _public_key = ephemeral_keypair
    context = synthetic_context(tmp_path, ephemeral_keypair)
    try:
        work = tmp_path / "build"
        old_package = synthetic_bundled_package(
            work,
            private_key,
            package_id="recon-snapshot-old",
            data_version="2026.09-published.2",
            standard_id=GB29446,
            standard_number="GB 29446-2019",
            rule_revision=1,
        )
        current_package = synthetic_bundled_package(
            work,
            private_key,
            package_id="recon-snapshot-new",
            data_version="2026.10-published.3",
            level_1="11",
            issue_day=24,
            standard_id=GB29446,
            standard_number="GB 29446-2019",
            rule_revision=2,
        )
        service = reconciler(context)

        old_directory = bundled_directory(tmp_path / "old", (old_package, old_package.name))
        assert service.reconcile(old_directory).action is ReconciliationAction.INSTALL
        assert context.standards.get_published(GB29446).rule_revision == 1

        # r1 定义使用 direct_input_key = actual（合成夹具的指标输入键）。
        request = EvaluationRequest(
            evaluation_date=date(2026, 9, 26),
            standard_id=GB29446,
            product_id="product",
            input_mode=InputMode.DIRECT,
            inputs={"actual": InputValue(value="5", unit="kgce/t")},
            organization_name="对账测试企业",
        )
        result = context.application.evaluate(request)
        assert result.rule_revision == 1
        assert evaluation_rows(context, result.evaluation_id) == 1

        loaded_before = context.application.get_evaluation(result.evaluation_id)
        assert loaded_before is not None
        revision_before = loaded_before[1].rule_revision
        snapshot_before = loaded_before[1].rule_snapshot_sha256
        rows_before = context.application.count_evaluations()

        current_directory = bundled_directory(
            tmp_path / "current", (current_package, current_package.name)
        )
        outcome = service.reconcile(current_directory)
        assert outcome.action is ReconciliationAction.UPGRADE

        # 新规则就位……
        assert context.standards.get_published(GB29446).rule_revision == 2
        # ……但历史记录仍然存在，而且仍是当时的 r1 规则快照（不被重算）。
        assert evaluation_rows(context, result.evaluation_id) == 1
        assert context.application.count_evaluations() == rows_before == 1
        loaded_after = context.application.get_evaluation(result.evaluation_id)
        assert loaded_after is not None
        assert loaded_after[0] == loaded_before[0]
        assert loaded_after[1].rule_revision == revision_before == 1
        assert loaded_after[1].rule_snapshot_sha256 == snapshot_before
        assert loaded_after[2].rule_revision == 1, "历史规则快照必须仍是升级前的 r1"
        summaries = context.application.list_recent_evaluations()
        assert [item.evaluation_id for item in summaries] == [result.evaluation_id]
    finally:
        context.database.dispose()
        close_logging()


# ---------------------------------------------------------------------------
# 8. 内置包发现的确定性：data_version 最高者胜出（不是文件名字典序最后者）
# ---------------------------------------------------------------------------


def test_bundled_discovery_prefers_highest_data_version_not_last_filename(
    tmp_path: Path, ephemeral_keypair
) -> None:
    private_key, _public_key = ephemeral_keypair
    context = synthetic_context(tmp_path, ephemeral_keypair)
    try:
        work = tmp_path / "build"
        newer = synthetic_bundled_package(
            work, private_key, package_id="recon-discover-newer", data_version="2026.10-published.3"
        )
        older = synthetic_bundled_package(
            work,
            private_key,
            package_id="recon-discover-older",
            data_version="2026.09-published.2",
            issue_day=22,
        )
        current_manifest = manifest_of(newer)
        directory = bundled_directory(
            tmp_path,
            # 文件名故意让“旧包”排在字典序最后：旧实现取 sorted()[-1] 会选错。
            (older, "initial-standard-package-z-older.uebench"),
            (newer, "initial-standard-package-a-newer.uebench"),
        )
        names = sorted(path.name for path in directory.glob(BUNDLED_PACKAGE_GLOB))
        assert names == [
            "initial-standard-package-a-newer.uebench",
            "initial-standard-package-z-older.uebench",
        ], "用例前提：字典序最后的是旧包"

        service = reconciler(context)
        identity = service.discover_bundled_package(directory)
        assert identity is not None
        assert identity.package_id == current_manifest["package_id"]
        assert identity.data_version == current_manifest["data_version"]
        assert identity.path.endswith("initial-standard-package-a-newer.uebench")

        outcome = service.reconcile(directory)
        assert outcome.action is ReconciliationAction.INSTALL
        assert outcome.installed is not None
        assert outcome.installed.package_id == current_manifest["package_id"]
        assert context.standards.get_published("gb-00000-2026").rule_revision == 1
        assert len(context.application.list_package_history(5)) == 1
    finally:
        context.database.dispose()
        close_logging()


def test_archived_legacy_package_upgrades_to_pinned_package(context, tmp_path: Path) -> None:
    """【历史归档证据用例 / EVIDENCE-ONLY，不计入核心兼容覆盖】

    验证真实归档旧包（``G:\\ECQuota-Archive`` 的 ``2026.09-published.2``）到当前固定
    包的 r1 → r2 取代关系。归档件按运维决定已移出仓库，本仓库无法再生成它的替代物
    （合成夹具可以覆盖同一契约，但覆盖不了「真实归档件本身的字节」），因此：

    * 归档可用时：跑完整断言；
    * 归档不可用（CI / 其它机器）时：以 ``require_archived_old_package`` 显式跳过，
      跳过原因明确写出这是历史归档证据、不计入核心覆盖。

    **核心对账契约**（安装 / 升级 / no-op / 冲突 / 损坏包 / 历史快照保全 / 内置包
    发现确定性）全部由本模块的合成夹具覆盖，不依赖这条用例。
    """
    require_pinned_packages()
    require_archived_old_package()
    old_manifest = manifest_of(OLD_PACKAGE)
    current_manifest = manifest_of(CURRENT_PACKAGE)
    service = reconciler(context)

    old_directory = bundled_directory(tmp_path / "old", (OLD_PACKAGE, OLD_PACKAGE.name))
    assert service.reconcile(old_directory).action is ReconciliationAction.INSTALL
    assert context.standards.get_published(GB29446).rule_revision == 1

    current_directory = bundled_directory(
        tmp_path / "current", (CURRENT_PACKAGE, CURRENT_PACKAGE.name)
    )
    outcome = service.reconcile(current_directory)

    assert outcome.action is ReconciliationAction.UPGRADE
    assert outcome.installed_before is not None
    assert outcome.installed_before.package_id == old_manifest["package_id"]
    assert outcome.installed_after is not None
    assert outcome.installed_after.package_id == current_manifest["package_id"]
    # r2 作为新修订加入，r1 仍然保留（历史评价必须可复算）。
    assert context.standards.get_published(GB29446).rule_revision == 2
    revisions = sorted(
        item.rule_revision
        for item in context.application.list_all_standards()
        if item.id == GB29446
    )
    assert revisions == [1, 2], "升级必须新增 r2 而不是替换 r1"
    assert len(context.application.list_all_standards()) == 49
    assert len(context.application.list_package_history(5)) == 2


def test_reconciliation_without_package_service_is_unavailable(tmp_path: Path) -> None:
    """缺少更新公钥（无标准包服务）时不得抛异常，而是上报 UNAVAILABLE。"""
    context = create_context(tmp_path / "data", public_key_path=None)
    try:
        assert context.package_service is None
        outcome = PackageReconciliationService(
            context.package_service, data_version_key=_data_version_key
        ).reconcile(tmp_path)
        assert outcome.action is ReconciliationAction.UNAVAILABLE
        assert outcome.reason is ReconciliationReason.PACKAGE_SERVICE_UNAVAILABLE
        assert outcome.executed is False
    finally:
        context.database.dispose()
        close_logging()


# ---------------------------------------------------------------------------
# 10. §五 —— 老备份恢复后，正常启动/对账必须再次经过同一个 cleanup Gate
#
# 缺口（本节的用例就是它的回归护栏）：``install`` 只在 INSTALL/UPGRADE 时被调用，
# 而 cleanup Gate 原先只存在于 ``install`` 内部。于是
#     BackupService.restore() 把老 ``sources/*`` PDF 放回活目录
#   → 内置包与恢复回来的已安装包完全相同
#   → 决策 NOOP
#   → 清理永不执行，旧 PDF 留在用户数据目录。
# 现在 ``PackageReconciliationService.reconcile()`` 在决策表**之前**无条件调用
# 端口方法 ``StandardPackagePort.cleanup_legacy_sources()``（应用层不导入
# infrastructure），因此 NOOP 也必须经过同一闸门。
#
# 夹具全部是合成的（临时 Ed25519 密钥 + dummy PDF 字节），因此不依赖
# ``G:\ECQuota-Archive`` 与 ``work/signing``，也不会因二者缺失而 skip。
# ---------------------------------------------------------------------------


def synthetic_bundled_ready_context(tmp_path: Path, *, root: str = "appdata", work: str = "work"):
    """装好合成包的真实组合根 + 与已安装包**逐字节相同**的内置包目录。

    返回 ``(library, context, directory)``：``directory`` 里的内置包与已安装包
    同 ``package_id``、同 ``package_sha256``，所以对账决策是真 NOOP。
    """
    library = synthetic_legacy_library(tmp_path / work)
    context = create_context(tmp_path / root, public_key_path=library.public_key_path)
    context.package_service.install(library.package)
    # 文件名必须匹配内置包 glob ``initial-standard-package-*.uebench``；
    # 复制的是**逐字节相同**的文件，所以 package_id / package_sha256 都不变。
    directory = bundled_directory(
        tmp_path / "bundled",
        (library.package, f"initial-standard-package-{library.package.name}"),
    )
    assert manifest_of(directory / f"initial-standard-package-{library.package.name}")[
        "package_id"
    ] == library.package_id
    return library, context, directory


def assert_cleanup_audit_matches(
    context, *, directories: int, files: int, flat: int, index: int = 0
) -> dict:
    """清理成功审计行必须是**验证后**的真实计数（并且只有一行）。"""
    rows = legacy_cleanup_rows(context)
    assert len(rows) == 1, [row.action for row in context.audit.list_recent(200)]
    details = json.loads(rows[index].details_json)
    assert details["directories_removed"] == directories
    assert details["files_removed"] == files
    assert details["flat_files_removed"] == flat
    assert details["verified"] is True
    assert details["scope"] == str(context.paths.standards.resolve())
    assert rows[index].entity_type == "standard_package"
    return details


def test_restore_then_noop_still_passes_the_cleanup_gate(tmp_path: Path) -> None:
    """核心缺口回归：从老备份恢复 → 决策 NOOP → 活目录仍然被清理干净。

    历史 ``.uebackup`` 里带着老 ``sources/*`` 与平铺 PDF（那是历史事实，不得改写），
    ``BackupService.restore()`` 会把它们原样放回活目录。随后正常启动路径
    （``reconcile_standard_package`` → ``PackageReconciliationService.reconcile``）
    必须**先过 cleanup Gate 再做决策**：即使决策是 NOOP 也要把活目录清干净。
    """
    library, context, directory = synthetic_bundled_ready_context(tmp_path)
    try:
        package_directory = context.paths.standards / library.package_id
        materialize_legacy_layout(package_directory, LEGACY_LAYOUT_BOTH, pdf_count=2)

        # 用例前提：老布局真的在活目录里，而且是**两种**布局同时存在。
        assert len(standards_pdfs(context)) == 4
        assert (package_directory / "sources").is_dir()
        assert len(list(package_directory.glob("*.pdf"))) == 2

        # 老版本/本次升级产生的历史安全备份：恢复后它必须逐字节不变。
        backup = context.application.create_backup(
            context.paths.backups / "pre-package-20260101-000000-000000.uebackup"
        )
        backup_bytes = backup.read_bytes()
        backup_sha256 = hashlib.sha256(backup_bytes).hexdigest()
        with zipfile.ZipFile(backup) as archive:
            assert [
                name for name in archive.namelist() if name.lower().endswith(".pdf")
            ], "用例前提：历史备份里确实带着老 PDF"

        context.application.restore_backup(backup)

        # ``restore`` 把老 PDF 放回活目录——这正是缺口现场。
        assert len(standards_pdfs(context)) == 4, "用例前提：恢复把老布局放回了活目录"
        assert not legacy_cleanup_rows(context)

        outcome = reconcile_standard_package(context, directory)

        # 1) 决策仍然是 NOOP：清理不得把 no-op 变成 install。
        assert outcome.action is ReconciliationAction.NOOP
        assert outcome.reason is ReconciliationReason.IDENTICAL_PACKAGE
        assert outcome.executed is False
        assert outcome.backup_path is None, "NOOP 不得顺手创建备份"
        assert context.application.last_package_reconciliation() is outcome

        # 2) 活目录里 0 个旧版 PDF，两种布局都被清掉，非原文产物保留。
        assert standards_pdfs(context) == []
        assert not (package_directory / "sources").exists()
        assert list(context.paths.standards.rglob("sources")) == []
        assert (package_directory / "corrections.json").is_file()

        # 3) 成功审计行存在，并且是**真实**计数（1 个目录 / 2 个文件 / 2 个平铺）。
        assert_cleanup_audit_matches(context, directories=1, files=2, flat=2)

        # 4) 没有新安装：包历史仍然只有那一条，也没有第二次安装审计。
        assert len(context.application.list_package_history(5)) == 1
        assert install_audit_rows(context) == 1

        # 5) 历史备份逐字节不变，而且它仍然携带老 PDF（不得为了“合规”回改历史）。
        assert backup.read_bytes() == backup_bytes
        assert hashlib.sha256(backup.read_bytes()).hexdigest() == backup_sha256
        with zipfile.ZipFile(backup) as archive:
            assert [
                name for name in archive.namelist() if name.lower().endswith(".pdf")
            ], "历史备份的内容属于历史事实，不得被改写"
    finally:
        context.database.dispose()
        close_logging()


def test_cleanup_gate_is_idempotent_across_repeated_startups(tmp_path: Path) -> None:
    """幂等：第二次及以后的对账不再新增审计行，也没有旧版 PDF 可清。"""
    library, context, directory = synthetic_bundled_ready_context(tmp_path)
    try:
        package_directory = context.paths.standards / library.package_id
        materialize_legacy_layout(package_directory, LEGACY_LAYOUT_FLAT, pdf_count=3)

        first = reconcile_standard_package(context, directory)
        assert first.action is ReconciliationAction.NOOP
        assert standards_pdfs(context) == []
        assert_cleanup_audit_matches(context, directories=0, files=0, flat=3)

        second = reconcile_standard_package(context, directory)
        assert second.action is ReconciliationAction.NOOP
        assert second.executed is False
        assert standards_pdfs(context) == []
        # 第二次没有东西可清：审计行数不变（不新增第二条）。
        assert len(legacy_cleanup_rows(context)) == 1

        # 直接经端口重复调用同样返回全零（真实计数的“没有东西可清”）。
        assert context.package_service.cleanup_legacy_sources() == (0, 0, 0)

        third = reconcile_standard_package(context, directory)
        assert third.action is ReconciliationAction.NOOP
        assert len(legacy_cleanup_rows(context)) == 1
        assert standards_pdfs(context) == []
    finally:
        context.database.dispose()
        close_logging()


def test_locked_legacy_pdf_aborts_reconciliation_fail_closed(tmp_path: Path) -> None:
    """Windows 真实占用句柄：对账在决策前中止，且没有任何“成功”痕迹。

    ``open(path, "rb")`` 保持打开会让删除在 Windows 上真实地以
    ``PermissionError``(winerror 32) 失败（与 install 路径的占用用例同款做法）。
    这里验证的是**对账路径**的 fail-closed：即使决策本会是 NOOP，闸门失败也必须
    中止，而不是“反正不装包，跳过清理”。
    """
    if sys.platform != "win32":
        pytest.skip("真实文件占用只能在 Windows 上复现（其他平台允许删除已打开的文件）")

    library, context, directory = synthetic_bundled_ready_context(tmp_path)
    try:
        package_directory = context.paths.standards / library.package_id
        materialize_legacy_layout(package_directory, LEGACY_LAYOUT_BOTH, pdf_count=2)
        sources_pdf = sorted((package_directory / "sources").glob("*.pdf"))[0]
        flat_pdf = sorted(package_directory.glob("*.pdf"))[0]
        locked_bytes = sources_pdf.read_bytes()
        backups_before = backup_names(context)
        history_before = [entry.package_id for entry in context.application.list_package_history(5)]

        with open(sources_pdf, "rb") as handle:
            assert handle.read(8).startswith(b"%PDF")
            with pytest.raises(StandardPackageError) as failure:
                reconcile_standard_package(context, directory)

        message = str(failure.value)
        # 与 install 路径**同一**中文错误与处置建议（同一份实现、同一套语义）。
        assert "无法删除旧版本遗留在用户数据目录中的标准原文" in message
        assert "安装已中止" in message
        assert "PermissionError" in message or "另一个程序正在使用此文件" in message
        assert "重试" in message
        assert str(sources_pdf.parent) in message

        # 1) 没有成功审计（这正是“不得记录成功”的断言）。
        assert legacy_cleanup_rows(context) == []
        # 2) 没有新备份，也没有新安装。
        assert backup_names(context) == backups_before
        assert [
            entry.package_id for entry in context.application.list_package_history(5)
        ] == history_before
        assert install_audit_rows(context) == 1
        # 3) 被占用的原文仍在原位、逐字节未变，其所在目录也未被删掉
        #    （删除失败的目标就是 ``sources`` 目录本身，rmtree 非 ignore_errors）。
        assert sources_pdf.is_file() and sources_pdf.read_bytes() == locked_bytes
        assert (package_directory / "sources").is_dir()
        #    失败并非「什么都没尝试」：未被占用的平铺 PDF 确实已被删除。
        assert not flat_pdf.exists()
        # 4) 数据库与业务状态可用：仍能正常读取已安装标准与包历史。
        assert context.standards.get_published(library.definition.id) is not None
        assert context.application.list_package_history(5)[0].package_id == library.package_id

        # 句柄释放后同一路径恢复正常：下一次启动即完成清理。
        # （本次失败尝试里未被占用的平铺 PDF 已在第一次尝试时删除，因此重试成功
        #   之后剩下的只有那个目录与其中 2 个文件——审计计数是**实测**结果。）
        outcome = reconcile_standard_package(context, directory)
        assert outcome.action is ReconciliationAction.NOOP
        assert standards_pdfs(context) == []
        assert_cleanup_audit_matches(context, directories=1, files=2, flat=0)
    finally:
        context.database.dispose()
        close_logging()


def test_historical_backup_is_byte_identical_after_the_cleanup_gate(tmp_path: Path) -> None:
    """§五：清理只动活目录，现存 ``.uebackup`` 逐字节（内容 + SHA256）不变。"""
    library, context, directory = synthetic_bundled_ready_context(tmp_path)
    try:
        package_directory = context.paths.standards / library.package_id
        materialize_legacy_layout(package_directory, LEGACY_LAYOUT_BOTH, pdf_count=2)

        historical = context.application.create_backup(
            context.paths.backups / "pre-package-20200101-000000-000000.uebackup"
        )
        before_bytes = historical.read_bytes()
        before_sha = hashlib.sha256(before_bytes).hexdigest()
        backups_before = backup_names(context)

        outcome = reconcile_standard_package(context, directory)

        assert outcome.action is ReconciliationAction.NOOP
        assert standards_pdfs(context) == []
        assert historical.is_file()
        assert historical.read_bytes() == before_bytes
        assert hashlib.sha256(historical.read_bytes()).hexdigest() == before_sha
        # 清理本身不创建备份：备份集合逐项不变（历史备份原样，也没有新增）。
        assert backup_names(context) == backups_before
    finally:
        context.database.dispose()
        close_logging()


def test_reconcile_always_calls_the_cleanup_gate_even_for_a_noop_decision(
    tmp_path: Path,
) -> None:
    """运行时契约：``reconcile()`` 在决策表之前**无条件**过闸门（NOOP 也算）。

    这是能抓住原缺口的断言：无论方法是否存在、无论决策是什么，只要活目录里有旧版
    原文，一次对账就必须把它清掉并留下真实计数。这里直接驱动
    ``PackageReconciliationService.reconcile``（而不是 ``reconcile_standard_package``），
    并断言决策确实是 NOOP——即清理不是靠 INSTALL/UPGRADE 顺带发生的。
    """
    library, context, directory = synthetic_bundled_ready_context(tmp_path)
    try:
        service = PackageReconciliationService(
            context.package_service, data_version_key=_data_version_key
        )
        # 先做一次真实对账确认它是 NOOP（同 id、同 sha256）。
        identity = service.discover_bundled_package(directory)
        assert identity is not None
        installed = service.installed_identity()
        assert installed is not None
        assert installed.package_id == identity.package_id
        assert installed.package_sha256 == identity.package_sha256
        assert service.reconcile(directory).action is ReconciliationAction.NOOP
        assert legacy_cleanup_rows(context) == []

        # 现在把旧版布局放回活目录：下一次对账仍然是 NOOP，但必须先清理。
        package_directory = context.paths.standards / library.package_id
        materialize_legacy_layout(package_directory, LEGACY_LAYOUT_BOTH, pdf_count=1)
        assert len(standards_pdfs(context)) == 2

        outcome = service.reconcile(directory)

        assert outcome.action is ReconciliationAction.NOOP, "清理不得把 no-op 变成 install"
        assert outcome.executed is False
        assert standards_pdfs(context) == []
        assert_cleanup_audit_matches(context, directories=1, files=1, flat=1)
        # 端口方法本身也必须能独立复现同一个 Gate（应用层访问基础设施的唯一入口）。
        assert context.package_service.cleanup_legacy_sources() == (0, 0, 0)
    finally:
        context.database.dispose()
        close_logging()

