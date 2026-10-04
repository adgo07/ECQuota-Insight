"""ECQ-RS05 §运行时标准包对账（Runtime Standard Package Reconciliation）.

产品原先只在**首次初始化**时安装内置标准包：只要数据库里已有任何标准，
``install_bundled_package()`` 就整体跳过。结果是老用户数据库里的规则永远停留在
旧包（Win11 现场证据：用户库仍是 ``2026.09-published.1`` / GB29446
``rule_revision=1``，而随产品发布的标准包已是 ``2026.10-published.3`` /
revision 2）。

本模块把“一次性初始化”改成**每次正常启动都执行的确定性对账**：把内置标准包与
当前已安装标准包做身份/版本比较，再按固定决策表行动。

决策表（A–F，另有表外的 MISSING / UNAVAILABLE 两个“无事可做”结果）::

    A  从未安装过标准包（标准库为空）            INSTALL       安装内置包
    B  已安装包与内置包完全相同                  NOOP          不备份、不重装、不写审计
    C  已安装 data_version 严格早于内置          UPGRADE       安装内置包
    D  已安装 data_version 严格新于内置          NO_DOWNGRADE  不安装，记录原因
    E  同 data_version 但 package_id/sha256 不同 CONFLICT    不覆盖，显式上报
       （以及内置包内容与已安装规则行冲突）      CONFLICT / installed-content-conflict
    F  内置包签名/清单/文件校验不通过            INVALID       不安装，存量数据不动

补充口径（与上表同为契约）:

* B 的“相同”= 同一 ``package_id`` **且** 同一 ``package_sha256``
  （已安装侧取自 ``list_history`` 的 ``package_sha256``，内置侧取自
  ``preview`` 的 ``report.package_sha256``）。
* 任一侧 ``data_version`` 无法按 ``_data_version_key`` 解析时也判 E：无法安全
  排序时绝不覆盖。
* 已安装侧缺少 ``data_version`` 不得当成“更旧”。
* ``INVALID`` **严格**只用于包自身完整性失败（签名 / 清单 / 文件 sha256 /
  不安全路径）。``preview`` 里依赖数据库状态的错误（已安装同一包、禁止降级、
  与已安装规则内容冲突、增量包父包缺失）是“现在不能装”，归 CONFLICT：
  内容冲突给出 :attr:`ReconciliationReason.INSTALLED_CONTENT_CONFLICT` 并列出
  冲突标准（超过三条折叠为“等 N 项”），其它阻塞给出
  :attr:`ReconciliationReason.INSTALL_BLOCKED`。二者都绝不会去调用 ``install``
  （``preview`` 已拒绝，调用只会抛 ``StandardPackageError``）。
* 预期情形**从不抛异常**；只有真正的 I/O / 校验异常才向上传播，且安装动作全部
  交给 ``StandardPackageService.install``（它自己负责 ``pre-upgrade`` 备份与
  失败回滚），因此不存在半安装状态。

分层与依赖注入（重要）::

    版本排序语义只有一份实现：``uebench.infrastructure.packages._data_version_key``。
    但 application 层被架构门禁（``tests/test_architecture_boundaries.py``）
    禁止导入 ``uebench.infrastructure``，所以这里**不复制比较算法**，而是把排序
    函数作为依赖由组合根注入（``data_version_key=``）。测试与组合根都传入同一份
    真实实现，语义不会分叉。

本模块是 application 层代码：不导入 PySide6，也不导入任何基础设施实现。
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ports import PackageValidationReportPort, StandardPackagePort

logger = logging.getLogger(__name__)

#: 内置标准包的固定文件名模式（与 `uebench.spec` 打包位置 ``uebench/resources`` 一致）。
BUNDLED_PACKAGE_GLOB = "initial-standard-package-*.uebench"

#: 版本排序函数签名；唯一实现见 ``uebench.infrastructure.packages._data_version_key``。
DataVersionKey = Callable[[str], "tuple[int, int, int, int] | None"]

#: ``StandardPackageService.preview`` 中**依赖数据库当前状态**、而非包自身完整性
#: 的错误：它们说明“现在不能装”，不说明“这个包本身不可信”。对账必须自己判定
#: 这些情形（B/D/E 与内容冲突），否则会被误判为 F。
#:
#: 注意 ``标准版本已存在：`` **不是**普通安装闸门：它表示已安装的
#: ``(standard_id, version, rule_revision)`` 行与包内定义内容不同，属于 ECQ-RS05
#: 决策表 E 的“内容冲突”，必须显式上报为 CONFLICT，绝不能吞掉后去调用
#: ``install``（那会以 ``StandardPackageError`` 抛出 44 条冲突）。
_INSTALL_BLOCKER_PREFIXES: tuple[str, ...] = (
    "该标准包已安装",
    "标准包发布时间早于当前已安装版本，禁止降级",
    "标准包数据版本早于当前已安装版本，禁止降级",
    "标准版本已存在：",
    "增量标准包依赖的父包未安装：",
    "增量标准包父包不是当前最新包：",
)

#: 内容冲突（``packages.py`` 的 “标准版本已存在：<标准> <版本>，如需变更…”）。
_CONTENT_CONFLICT_PREFIX = "标准版本已存在："
_CONTENT_CONFLICT_SUFFIX = "，如需变更必须递增标准包/规则版本"

#: 冲突/阻塞说明里最多逐条列出多少项，其余折叠为“等 N 项”（可能有 44 项以上）。
_BLOCKER_MESSAGE_LIMIT = 3


def _is_install_blocker(error: str) -> bool:
    return any(error.startswith(prefix) for prefix in _INSTALL_BLOCKER_PREFIXES)


def _content_conflict_labels(blockers: list[str]) -> list[str]:
    """从内容冲突错误文案里取出“标准编号 版本”，例如 ``GB 29446-2019 2019``。"""
    labels: list[str] = []
    for error in blockers:
        if not error.startswith(_CONTENT_CONFLICT_PREFIX):
            continue
        label = error[len(_CONTENT_CONFLICT_PREFIX) :].split(_CONTENT_CONFLICT_SUFFIX)[0].strip()
        labels.append(label or error)
    return labels


def _describe_blockers(items: list[str], limit: int = _BLOCKER_MESSAGE_LIMIT) -> str:
    """把可能很长的冲突列表折叠成可读文案。"""
    if not items:
        return ""
    shown = "、".join(items[:limit])
    if len(items) > limit:
        shown += f" 等 {len(items)} 项"
    return shown


class ReconciliationAction(str, Enum):
    """对账动作（决策表的稳定机器标识）。"""

    #: A：从未安装过任何标准包 → 安装内置包。
    INSTALL = "install"
    #: B：内置包与已安装包完全相同 → 什么都不做。
    NOOP = "noop"
    #: C：已安装包严格旧于内置包 → 升级。
    UPGRADE = "upgrade"
    #: D：已安装包严格新于内置包 → 拒绝降级。
    NO_DOWNGRADE = "no-downgrade"
    #: E：同版本但身份不同（或版本无法排序）→ 冲突，不覆盖。
    CONFLICT = "conflict"
    #: F：内置包自身校验不通过 → 不安装。
    INVALID = "invalid"
    #: 表外：找不到内置标准包（源码运行或资源缺失）。
    MISSING = "missing"
    #: 表外：标准包服务不可用（例如缺少更新公钥）。
    UNAVAILABLE = "unavailable"


class ReconciliationReason(str, Enum):
    """对账原因码；与 :class:`ReconciliationAction` 一起构成稳定契约。"""

    NO_BUNDLED_PACKAGE = "no-bundled-package"
    PACKAGE_SERVICE_UNAVAILABLE = "package-service-unavailable"
    BUNDLED_INVALID = "bundled-invalid"
    NO_INSTALLED_PACKAGE = "no-installed-package"
    IDENTICAL_PACKAGE = "identical-package"
    BUNDLED_NEWER = "bundled-data-version-newer"
    INSTALLED_NEWER = "installed-data-version-newer"
    #: 内置包内容与已安装规则的 (standard_id, version, rule_revision) 行冲突（决策表 E）。
    INSTALLED_CONTENT_CONFLICT = "installed-content-conflict"
    #: 其它安装闸门（降级时间戳、同 package_id 但内容不同、增量包父包缺失等）。
    INSTALL_BLOCKED = "install-blocked-by-state"
    DATA_VERSION_NOT_ORDERABLE = "data-version-not-orderable"
    SAME_DATA_VERSION_DIFFERENT_IDENTITY = "same-data-version-different-identity"


#: 需要真正调用 ``install`` 的动作。
INSTALL_ACTIONS: frozenset[ReconciliationAction] = frozenset(
    {ReconciliationAction.INSTALL, ReconciliationAction.UPGRADE}
)


class InstalledPackageIdentity(BaseModel):
    """当前已安装标准包（标准库）的身份。"""

    model_config = ConfigDict(extra="forbid")

    package_id: str
    data_version: str = ""
    package_sha256: str | None = None
    installed_at: datetime | None = None


class BundledPackageIdentity(BaseModel):
    """内置标准包的候选身份、完整性判定与安装阻塞项。

    ``valid`` 只表示**包自身**通过签名/清单/文件 sha256 校验；决定安装的
    ``preview`` 错误另存于 ``install_blockers``：它们依赖数据库已有状态
    （已安装同一包、版本降级、与已安装规则内容冲突、增量包父包缺失），
    必须由 :func:`decide` 分类，而不是当作包完整性缺陷。

    ``valid=True`` 时保证 ``package_id`` / ``data_version`` /
    ``package_sha256`` 三者齐备；``errors`` 只在 ``valid=False`` 时非空。
    """

    model_config = ConfigDict(extra="forbid")

    path: str
    package_id: str | None = None
    data_version: str | None = None
    package_sha256: str | None = None
    valid: bool = True
    #: 包完整性错误（签名/清单/文件 sha256/不安全路径）；非空即 ``valid=False``。
    errors: list[str] = Field(default_factory=list)
    #: 依赖数据库状态的安装阻塞项（含内容冲突），不影响 ``valid``。
    install_blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_identity_when_valid(self) -> "BundledPackageIdentity":
        if self.valid and (
            self.package_id is None or self.data_version is None or self.package_sha256 is None
        ):
            raise ValueError(
                "valid 的内置标准包身份必须同时提供 package_id / data_version / package_sha256"
            )
        return self


class ReconciliationOutcome(BaseModel):
    """一次对账的完整、可序列化结果。

    纯决策函数 :func:`decide` 与编排器 :class:`PackageReconciliationService`
    返回同一个类型：前者只填 ``action`` / ``reason`` / ``message`` / 两个身份，
    后者额外填 ``executed`` / ``backup_path`` / ``standards_installed`` /
    ``installed_after``。
    """

    model_config = ConfigDict(extra="forbid")

    action: ReconciliationAction
    reason: ReconciliationReason
    message: str
    #: 是否真的执行了安装（NOOP / NO_DOWNGRADE / CONFLICT / INVALID 恒为 False）。
    executed: bool = False
    installed_before: InstalledPackageIdentity | None = None
    bundled: BundledPackageIdentity | None = None
    installed_after: InstalledPackageIdentity | None = None
    backup_path: str | None = None
    standards_installed: int | None = None
    errors: list[str] = Field(default_factory=list)

    @property
    def installed(self) -> InstalledPackageIdentity | None:
        """动作完成后的已安装身份；未安装时为动作前的身份。"""
        return self.installed_after or self.installed_before

    @property
    def succeeded(self) -> bool:
        """是否属于“产品处于期望状态”的结果（可安全展示为正常）。"""
        return self.action in {
            ReconciliationAction.INSTALL,
            ReconciliationAction.NOOP,
            ReconciliationAction.UPGRADE,
        }

    def to_dict(self) -> dict[str, object]:
        """JSON 友好字典（枚举降级为字符串），供 JSON 报告/诊断视图使用。"""
        return self.model_dump(mode="json")

    def summary(self) -> str:
        """中文单行摘要（日志、诊断视图、自检共用）。"""
        bundled_id = self.bundled.package_id if self.bundled is not None else None
        installed_id = self.installed.package_id if self.installed is not None else None
        parts = [
            f"action={self.action.value}",
            f"reason={self.reason.value}",
            f"已安装={installed_id or '（无）'}",
            f"内置={bundled_id or '（无）'}",
        ]
        if self.backup_path:
            parts.append(f"备份={self.backup_path}")
        if self.errors:
            parts.append("错误=" + "；".join(self.errors))
        return "标准包对账：" + "，".join(parts) + f"（{self.message}）"


def _outcome(
    action: ReconciliationAction,
    reason: ReconciliationReason,
    message: str,
    *,
    installed_before: InstalledPackageIdentity | None = None,
    bundled: BundledPackageIdentity | None = None,
    errors: list[str] | None = None,
) -> ReconciliationOutcome:
    return ReconciliationOutcome(
        action=action,
        reason=reason,
        message=message,
        installed_before=installed_before,
        bundled=bundled,
        errors=list(errors or []),
    )


def decide(
    installed: InstalledPackageIdentity | None,
    bundled: BundledPackageIdentity | None,
    *,
    data_version_key: DataVersionKey,
) -> ReconciliationOutcome:
    """纯决策函数：不访问数据库、不访问文件系统、不抛预期异常。

    ``installed=None`` 表示标准库为空；``bundled=None`` 表示未发现内置标准包。
    ``data_version_key`` 必须传入唯一版本排序实现
    （``uebench.infrastructure.packages._data_version_key``）。

    分类口径（与决策表一一对应）::

        bundled.valid is False              → INVALID（包自身不可信，绝不安装）
        bundled.install_blockers 含内容冲突 → CONFLICT / installed-content-conflict
        其它 install_blockers + 本应安装    → CONFLICT / install-blocked-by-state

    ``install_blockers`` 是 ``preview`` 明确拒绝安装的原因，因此**只要存在阻塞项
    且决策本会安装，就绝不会去调用 ``install``**（否则它必然抛出）。
    """
    return _guard_install(
        _decide_action(installed, bundled, data_version_key=data_version_key),
        bundled,
    )


def _decide_action(
    installed: InstalledPackageIdentity | None,
    bundled: BundledPackageIdentity | None,
    *,
    data_version_key: DataVersionKey,
) -> ReconciliationOutcome:
    if bundled is None:
        return _outcome(
            ReconciliationAction.MISSING,
            ReconciliationReason.NO_BUNDLED_PACKAGE,
            "未找到内置标准包，本次不做任何安装。",
            installed_before=installed,
        )

    if not bundled.valid:
        return _outcome(
            ReconciliationAction.INVALID,
            ReconciliationReason.BUNDLED_INVALID,
            "内置标准包未通过签名/清单/文件校验，已放弃安装，现有数据保持原样。",
            installed_before=installed,
            bundled=bundled,
            errors=list(bundled.errors),
        )

    bundled_version = bundled.data_version or ""

    # 决策表 E 的内容冲突：包内定义与已安装的同一 (标准, 版本, 规则版本) 行内容不同。
    # 必须显式上报，绝不能覆盖，也不能当作包损坏（F）。
    conflict_labels = _content_conflict_labels(bundled.install_blockers)
    if conflict_labels:
        return _outcome(
            ReconciliationAction.CONFLICT,
            ReconciliationReason.INSTALLED_CONTENT_CONFLICT,
            "内置标准包与已安装规则内容冲突（"
            + _describe_blockers(conflict_labels)
            + "），不覆盖已安装标准包；如需变更必须递增规则版本后重新发布标准包。",
            installed_before=installed,
            bundled=bundled,
            errors=list(bundled.install_blockers),
        )

    if installed is None:
        return _outcome(
            ReconciliationAction.INSTALL,
            ReconciliationReason.NO_INSTALLED_PACKAGE,
            f"标准库为空，安装内置标准包 {bundled.package_id}（{bundled_version}）。",
            bundled=bundled,
        )

    if (
        installed.package_id == bundled.package_id
        and installed.package_sha256 is not None
        and bundled.package_sha256 is not None
        and installed.package_sha256.lower() == bundled.package_sha256.lower()
    ):
        return _outcome(
            ReconciliationAction.NOOP,
            ReconciliationReason.IDENTICAL_PACKAGE,
            f"内置标准包与已安装包完全相同（{installed.package_id} / {installed.data_version}），无需处理。",
            installed_before=installed,
            bundled=bundled,
        )

    installed_key = data_version_key(installed.data_version) if installed.data_version else None
    bundled_key = data_version_key(bundled_version) if bundled_version else None
    if installed_key is None or bundled_key is None:
        return _outcome(
            ReconciliationAction.CONFLICT,
            ReconciliationReason.DATA_VERSION_NOT_ORDERABLE,
            "已安装包与内置包的数据版本无法安全排序"
            f"（已安装={installed.data_version or '（缺失）'}，内置={bundled_version or '（缺失）'}），"
            "不覆盖已安装标准包。",
            installed_before=installed,
            bundled=bundled,
        )

    if installed_key < bundled_key:
        return _outcome(
            ReconciliationAction.UPGRADE,
            ReconciliationReason.BUNDLED_NEWER,
            f"内置标准包更新（{installed.data_version} → {bundled_version}），执行升级安装。",
            installed_before=installed,
            bundled=bundled,
        )

    if installed_key > bundled_key:
        return _outcome(
            ReconciliationAction.NO_DOWNGRADE,
            ReconciliationReason.INSTALLED_NEWER,
            f"已安装标准包（{installed.data_version}）新于内置包（{bundled_version}），拒绝降级安装。",
            installed_before=installed,
            bundled=bundled,
        )

    return _outcome(
        ReconciliationAction.CONFLICT,
        ReconciliationReason.SAME_DATA_VERSION_DIFFERENT_IDENTITY,
        f"数据版本相同（{bundled_version}）但包身份不同"
        f"（已安装={installed.package_id}，内置={bundled.package_id}），不覆盖已安装标准包。",
        installed_before=installed,
        bundled=bundled,
    )


def _guard_install(
    outcome: ReconciliationOutcome,
    bundled: BundledPackageIdentity | None,
) -> ReconciliationOutcome:
    """安装前的最后一道闸门：``preview`` 已拒绝安装时绝不调用 ``install``。

    这保证 ``reconcile`` 对“本应安装但会被 ``install`` 拒绝”的输入返回
    CONFLICT 结果，而不是让 ``StandardPackageError`` 抛出（ECQ-RS05 §三 E）。
    """
    if outcome.action not in INSTALL_ACTIONS or bundled is None or not bundled.install_blockers:
        return outcome
    labels = _content_conflict_labels(bundled.install_blockers)
    if labels:  # 理论上已被 _decide_action 提前拦下；此处保持单一出口的兜底。
        message = (
            "内置标准包与已安装规则内容冲突（"
            + _describe_blockers(labels)
            + "），不覆盖已安装标准包。"
        )
        reason = ReconciliationReason.INSTALLED_CONTENT_CONFLICT
    else:
        message = (
            "内置标准包当前无法安装（"
            + _describe_blockers(bundled.install_blockers, limit=1)
            + "），已安装标准包保持原样。"
        )
        reason = ReconciliationReason.INSTALL_BLOCKED
    return _outcome(
        ReconciliationAction.CONFLICT,
        reason,
        message,
        installed_before=outcome.installed_before,
        bundled=bundled,
        errors=list(bundled.install_blockers),
    )


class PackageReconciliationService:
    """编排：发现内置包 → 预览 → 读取已安装身份 → 决策 → 执行 → 返回结果。

    ``packages=None`` 表示标准包服务不可用（例如缺少更新公钥）；此时
    :meth:`reconcile` 返回 ``UNAVAILABLE`` 结果而不是抛异常。
    """

    def __init__(
        self,
        packages: StandardPackagePort | None,
        *,
        data_version_key: DataVersionKey,
        history_limit: int = 50,
    ) -> None:
        self._packages = packages
        self._data_version_key = data_version_key
        self._history_limit = max(1, int(history_limit))
        self._last_outcome: ReconciliationOutcome | None = None

    @property
    def last_outcome(self) -> ReconciliationOutcome | None:
        """最近一次对账结果（供 UI / 自检 / 诊断视图读取）。"""
        return self._last_outcome

    # -- 编排 -------------------------------------------------------------

    def reconcile(self, directory: Path) -> ReconciliationOutcome:
        """对 ``directory`` 中的内置标准包执行一次对账。"""
        if self._packages is None:
            outcome = _outcome(
                ReconciliationAction.UNAVAILABLE,
                ReconciliationReason.PACKAGE_SERVICE_UNAVAILABLE,
                "标准包服务未配置（缺少更新公钥），跳过标准包对账。",
            )
        else:
            bundled = self.discover_bundled_package(Path(directory))
            installed = self.installed_identity()
            outcome = decide(installed, bundled, data_version_key=self._data_version_key)
            if outcome.action in INSTALL_ACTIONS:
                outcome = self._install(bundled, outcome)
        self._last_outcome = outcome
        logger.info("%s", outcome.summary())
        return outcome

    # -- 读取状态 ---------------------------------------------------------

    def installed_identity(self, *, package_id: str | None = None) -> InstalledPackageIdentity | None:
        """已安装标准包身份（``list_history`` 最新的那一条，即安装身份来源）。"""
        if self._packages is None:
            return None
        entries = list(self._packages.list_history(self._history_limit))
        if package_id is not None:
            matched = [entry for entry in entries if entry.package_id == package_id]
            if matched:
                entries = matched
        if not entries:
            return None
        newest = entries[0]
        return InstalledPackageIdentity(
            package_id=newest.package_id,
            data_version=newest.data_version,
            package_sha256=newest.package_sha256,
            installed_at=newest.installed_at,
        )

    def discover_bundled_package(self, directory: Path) -> BundledPackageIdentity | None:
        """确定性地挑选内置标准包；目录不存在或没有候选时返回 ``None``。

        多个候选时**按 ``data_version`` 取最高者（而不是文件名字典序最后者）**：
        先只看通过完整性校验的候选，全部无效时才退回“最有信息量的无效候选”
        （可读出 ``data_version`` 的优先），以便把真实失败原因上报为 INVALID。
        """
        if not directory.is_dir():
            return None
        candidates = sorted(path for path in directory.glob(BUNDLED_PACKAGE_GLOB) if path.is_file())
        if not candidates:
            return None
        identities = [self._identity_of(path) for path in candidates]
        valid = [identity for identity in identities if identity.valid]
        pool = valid or identities
        return max(pool, key=self._rank)

    # -- 内部实现 ---------------------------------------------------------

    def _identity_of(self, path: Path) -> BundledPackageIdentity:
        try:
            report: PackageValidationReportPort = self._packages.preview(path)
        except Exception as exc:  # preview 适配器可能直接拒绝损坏文件
            return BundledPackageIdentity(
                path=str(path),
                valid=False,
                errors=[f"标准包预览失败：{type(exc).__name__}: {exc}"],
            )
        integrity_errors: list[str] = []
        install_blockers: list[str] = []
        for raw_error in report.errors:
            error = str(raw_error)
            if _is_install_blocker(error):
                install_blockers.append(error)
            else:
                integrity_errors.append(error)
        manifest = report.manifest
        valid = (
            manifest is not None
            and report.package_sha256 is not None
            and not integrity_errors
        )
        return BundledPackageIdentity(
            path=str(path),
            package_id=manifest.package_id if manifest is not None else None,
            data_version=manifest.data_version if manifest is not None else None,
            package_sha256=report.package_sha256,
            valid=valid,
            errors=integrity_errors,
            install_blockers=install_blockers,
            warnings=[str(warning) for warning in report.warnings],
        )

    def _rank(self, identity: BundledPackageIdentity) -> tuple[int, tuple[int, int, int, int], str]:
        key = (
            self._data_version_key(identity.data_version)
            if identity.data_version
            else None
        )
        return (
            1 if key is not None else 0,
            key or (0, 0, 0, 0),
            Path(identity.path).name.casefold(),
        )

    def _install(
        self,
        bundled: BundledPackageIdentity | None,
        decision: ReconciliationOutcome,
    ) -> ReconciliationOutcome:
        """执行安装。任何异常都由 ``install`` 回滚后向上传播，绝不半安装。

        只有决策为 INSTALL/UPGRADE 时才会被调用，而 :func:`decide` 只在
        ``preview`` 没有任何安装阻塞项（``install_blockers``）时给出这两个动作，
        因此 ``install`` 不会因“已安装/禁止降级/内容冲突”被拒绝。
        """
        assert bundled is not None and bundled.path is not None  # INSTALL/UPGRADE 前提
        result = self._packages.install(Path(bundled.path))  # type: ignore[union-attr]
        after = self.installed_identity(package_id=result.package_id)
        if after is None:
            after = InstalledPackageIdentity(
                package_id=result.package_id,
                data_version=result.data_version,
                package_sha256=bundled.package_sha256,
            )
        return decision.model_copy(
            update={
                "executed": True,
                "installed_after": after,
                "backup_path": str(result.backup_path),
                "standards_installed": int(result.standards_installed),
            }
        )
