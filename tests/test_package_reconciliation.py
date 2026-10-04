"""ECQ-RS05 运行时标准包对账（Runtime Standard Package Reconciliation）测试。

覆盖决策表 A–F、升级、冲突、损坏内置包、历史评价快照保全、内置包发现的
确定性，以及纯决策函数的表驱动用例。

数据目录一律使用 ``tmp_path`` 隔离（``--basetemp`` 必须指向 ``$env:TEMP``：
仓库 ``work\\`` 目录存在 ACL 问题，会让 SQLite 写入慢约 200 倍）。
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
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
from uebench.infrastructure.packages import StandardPackageBuilder, _data_version_key
from uebench.main import reconcile_standard_package

from .test_engine import make_standard

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = ROOT / "src" / "uebench" / "resources" / "update_public_key.pem"
PACKAGE_DIR = ROOT / "release" / "standard-packages"
#: 固定（已发布）标准包：旧 = 2026.09-published.2（GB29446 r1），当前 = 2026.10-published.3（r2）。
CURRENT_PACKAGE = PACKAGE_DIR / "initial-standard-package-published.uebench"
#: 旧包已移出仓库（REFERENCE ONLY）；取得的是归档件的**副本**。
try:  # 测试目录既可能是普通目录，也可能被当作包
    from _legacy_assets import session_legacy_package
except ModuleNotFoundError:  # pragma: no cover - 取决于 pytest 的导入模式
    from tests._legacy_assets import session_legacy_package

OLD_PACKAGE = session_legacy_package()
#: 开发签名私钥（绝不复制进仓库，只按路径引用）。
DEVELOPMENT_KEY = ROOT / "work" / "signing" / "development-private-key.pem"

GB29446 = "gb-29446-2019"
GB29446_COKING_PRODUCT = "gb_29446-2019-coking-coal"
AUDIT_ACTION_INSTALL = "STANDARD_PACKAGE_INSTALL"


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def require_pinned_packages() -> None:
    for path in (OLD_PACKAGE, CURRENT_PACKAGE):
        if not path.is_file():
            pytest.skip(f"缺少固定标准包：{path}（release/standard-packages/）")


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


def evaluation_rows(context, evaluation_id: str) -> int:
    with context.database.engine.connect() as connection:
        return int(
            connection.execute(
                text("SELECT COUNT(*) FROM evaluations WHERE evaluation_id = :id"),
                {"id": evaluation_id},
            ).scalar_one()
        )


def developer_private_key() -> Ed25519PrivateKey:
    if not DEVELOPMENT_KEY.is_file():
        pytest.skip("缺少开发签名私钥：work/signing/development-private-key.pem")
    try:
        key = serialization.load_pem_private_key(DEVELOPMENT_KEY.read_bytes(), password=None)
    except Exception as exc:  # pragma: no cover - 私钥不可读时明确跳过而不是误判
        pytest.skip(f"开发签名私钥无法加载：{type(exc).__name__}: {exc}")
    assert isinstance(key, Ed25519PrivateKey)
    return key


def build_test_package(
    directory: Path,
    private_key: Ed25519PrivateKey,
    *,
    package_id: str,
    data_version: str,
    level_1: str = "10",
    issue_day: int = 23,
) -> Path:
    """用真实 ``StandardPackageBuilder`` 生成可验签的测试标准包。"""
    definition = make_standard()
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
        directory / f"{package_id}.uebench",
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


@pytest.fixture
def context(tmp_path: Path):
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


def test_older_installed_package_is_upgraded_to_bundled(context, tmp_path: Path) -> None:
    require_pinned_packages()
    old_manifest = manifest_of(OLD_PACKAGE)
    current_manifest = manifest_of(CURRENT_PACKAGE)
    service = reconciler(context)

    old_directory = bundled_directory(tmp_path / "old", (OLD_PACKAGE, OLD_PACKAGE.name))
    installed = service.reconcile(old_directory)
    assert installed.action is ReconciliationAction.INSTALL
    assert context.standards.get_published(GB29446).rule_revision == 1

    # 备份文件名精确到秒：先跨过一秒，升级备份才可以被独立观察到。
    time.sleep(1.05)
    backups_before = backup_names(context)

    current_directory = bundled_directory(tmp_path / "current", (CURRENT_PACKAGE, CURRENT_PACKAGE.name))
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
    # 新规则就位：r2 作为新修订加入，r1 仍然保留（历史评价必须可复算）。
    assert context.application.get_published_standard(GB29446).rule_revision == 2
    gb29446_revisions = sorted(
        item.rule_revision
        for item in context.application.list_all_standards()
        if item.id == GB29446
    )
    assert gb29446_revisions == [1, 2], "升级必须新增 r2 而不是替换 r1"
    assert len(context.application.list_all_standards()) == 49
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


# ---------------------------------------------------------------------------
# D. 已安装更新 → NO_DOWNGRADE
# ---------------------------------------------------------------------------


def test_newer_installed_package_refuses_downgrade(context, tmp_path: Path) -> None:
    require_pinned_packages()
    current_manifest = manifest_of(CURRENT_PACKAGE)
    service = reconciler(context)

    current_directory = bundled_directory(tmp_path / "current", (CURRENT_PACKAGE, CURRENT_PACKAGE.name))
    assert service.reconcile(current_directory).action is ReconciliationAction.INSTALL
    before = policy_state(context)

    old_directory = bundled_directory(tmp_path / "old", (OLD_PACKAGE, OLD_PACKAGE.name))
    outcome = service.reconcile(old_directory)

    assert outcome.action is ReconciliationAction.NO_DOWNGRADE
    assert outcome.reason is ReconciliationReason.INSTALLED_NEWER
    assert outcome.executed is False
    assert "降级" in outcome.message
    # 内置包本身是有效的：拒绝降级来自版本比较，不是完整性失败。
    assert outcome.bundled is not None and outcome.bundled.valid is True
    assert policy_state(context) == before, "拒绝降级时不得改动任何已安装状态"
    assert context.standards.get_published(GB29446).rule_revision == 2
    assert context.application.list_package_history(5)[0].package_id == current_manifest["package_id"]


# ---------------------------------------------------------------------------
# E. 同版本不同身份 / 与已安装规则内容冲突 → CONFLICT
# ---------------------------------------------------------------------------


def test_same_data_version_different_identity_conflicts_without_overwrite(context, tmp_path: Path) -> None:
    """内容一致、仅包身份不同：判 E（SAME_DATA_VERSION_DIFFERENT_IDENTITY）。"""
    private_key = developer_private_key()
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


def test_invalid_bundled_package_installs_nothing_and_keeps_existing_data(context, tmp_path: Path) -> None:
    require_pinned_packages()
    service = reconciler(context)
    old_directory = bundled_directory(tmp_path / "old", (OLD_PACKAGE, OLD_PACKAGE.name))
    assert service.reconcile(old_directory).action is ReconciliationAction.INSTALL
    before = policy_state(context)

    work = tmp_path / "broken"
    work.mkdir(parents=True)
    tampered = tampered_copy(CURRENT_PACKAGE, work / "tampered.uebench")
    truncated = work / "truncated.uebench"
    truncated.write_bytes(CURRENT_PACKAGE.read_bytes()[: CURRENT_PACKAGE.stat().st_size // 2])
    unsigned = unsigned_copy(CURRENT_PACKAGE, work / "unsigned.uebench")

    for damaged in (tampered, truncated, unsigned):
        directory = bundled_directory(work / damaged.stem, (damaged, CURRENT_PACKAGE.name))
        outcome = service.reconcile(directory)

        assert outcome.action is ReconciliationAction.INVALID, damaged.name
        assert outcome.reason is ReconciliationReason.BUNDLED_INVALID
        assert outcome.executed is False
        assert outcome.succeeded is False, "校验失败绝不能上报为已更新"
        assert outcome.errors, "必须给出校验失败原因"
        assert policy_state(context) == before, f"{damaged.name} 之后存量数据/备份/审计必须不变"

    assert context.standards.get_published(GB29446).rule_revision == 1
    assert context.application.list_package_history(5)[0].package_id == manifest_of(OLD_PACKAGE)["package_id"]


def test_content_conflict_with_installed_rules_is_conflict_not_invalid(context, tmp_path: Path) -> None:
    """集成评审缺陷回归：同 (标准, 版本, 规则版本) 内容不同 → CONFLICT，不得抛异常。

    缺陷版本把 ``标准版本已存在：`` 当成安装闸门吞掉，于是 bundled.valid 仍为 True、
    决策为 UPGRADE，随后 ``install()`` 以 44 条 ``StandardPackageError`` 抛出。
    """
    require_pinned_packages()
    private_key = developer_private_key()
    service = reconciler(context)

    current_directory = bundled_directory(
        tmp_path / "current", (CURRENT_PACKAGE, CURRENT_PACKAGE.name)
    )
    assert service.reconcile(current_directory).action is ReconciliationAction.INSTALL
    before = policy_state(context)
    assert len(context.application.list_package_history(200)) == 1

    mutated = mutate_pinned_definition(
        CURRENT_PACKAGE,
        tmp_path / "mutated" / "mutated.uebench",
        private_key,
        package_id="recon-mutated-gb29446-content",
        data_version="2026.11-published.4",  # 严格更新：不拦内容冲突就会走 UPGRADE
        issued_at="2026-11-05T00:00:00Z",
    )
    mutated_manifest = manifest_of(mutated)
    current_key = _data_version_key(manifest_of(CURRENT_PACKAGE)["data_version"])
    mutated_key = _data_version_key(mutated_manifest["data_version"])
    assert current_key is not None and mutated_key is not None and mutated_key > current_key

    directory = bundled_directory(
        tmp_path / "mutated-bundled", (mutated, CURRENT_PACKAGE.name)
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
    assert "GB 29446-2019 2019" in outcome.message
    assert outcome.errors

    # 无新备份、无新 standard_packages 行、已安装标准行逐字节不变。
    assert policy_state(context) == before
    assert len(context.application.list_package_history(200)) == 1
    assert context.application.get_published_standard(GB29446).rule_revision == 2
    assert context.application.last_package_reconciliation() is outcome


# ---------------------------------------------------------------------------
# 7. 历史评价快照在升级后保持原样（不按新规则重算）
# ---------------------------------------------------------------------------


def test_upgrade_preserves_saved_evaluation_snapshot(context, tmp_path: Path) -> None:
    require_pinned_packages()
    service = reconciler(context)

    old_directory = bundled_directory(tmp_path / "old", (OLD_PACKAGE, OLD_PACKAGE.name))
    assert service.reconcile(old_directory).action is ReconciliationAction.INSTALL
    assert context.standards.get_published(GB29446).rule_revision == 1

    # r1（合并前的 GB29446）使用 direct_input_key = actual.coking-coal。
    request = EvaluationRequest(
        evaluation_date=date(2026, 9, 26),
        standard_id=GB29446,
        product_id=GB29446_COKING_PRODUCT,
        input_mode=InputMode.DIRECT,
        inputs={"actual.coking-coal": InputValue(value="5.0", unit="kW·h/t")},
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

    current_directory = bundled_directory(tmp_path / "current", (CURRENT_PACKAGE, CURRENT_PACKAGE.name))
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


# ---------------------------------------------------------------------------
# 8. 内置包发现的确定性：data_version 最高者胜出（不是文件名字典序最后者）
# ---------------------------------------------------------------------------


def test_bundled_discovery_prefers_highest_data_version_not_last_filename(
    context, tmp_path: Path
) -> None:
    require_pinned_packages()
    current_manifest = manifest_of(CURRENT_PACKAGE)
    directory = bundled_directory(
        tmp_path,
        # 文件名故意让“旧包”排在字典序最后：旧实现取 sorted()[-1] 会选错。
        (OLD_PACKAGE, "initial-standard-package-z-older.uebench"),
        (CURRENT_PACKAGE, "initial-standard-package-a-newer.uebench"),
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
    assert context.standards.get_published(GB29446).rule_revision == 2


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
