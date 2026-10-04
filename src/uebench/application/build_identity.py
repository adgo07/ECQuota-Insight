"""构建身份读取与“关于 / 诊断信息”文本渲染（ECQ-RS05）。

本模块位于 application 层，**不导入 PySide6**（也不导入 SQLAlchemy / openpyxl /
``uebench.infrastructure`` / ``uebench.ui`` / ``uebench.bootstrap``），因此可以被
单元测试直接驱动。界面层只负责把这里读到的内容显示出来并允许复制。

构建身份来源契约（顺序固定，先命中者生效）
------------------------------------------

1. **打包（frozen）**：``<package dir>/resources/build-identity.json``，即与
   ``uebench/resources/*`` 同级；PyInstaller one-folder 打包后位于
   ``_internal/uebench/resources/build-identity.json``。
2. **源码检出（development）**：``<repo>/dist/release/release-build-info.json``。

两处都不存在、文件损坏或字段缺失时，返回**占位文本**
:data:`UNKNOWN_BUILD_IDENTITY`（``未知（未嵌入构建身份）``），绝不抛异常：诊断页本身
不能因为身份缺失而无法打开。

安全约束
--------

本模块只读构建身份 JSON 的**非敏感字段**，不读取、不输出私钥或其他凭据内容。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import sys

#: 未嵌入/不可用时的统一占位文本（中文，用户可见）。
UNKNOWN_BUILD_IDENTITY = "未知（未嵌入构建身份）"

#: 打包身份文件的 Schema 标识（仅记录，不用于拒绝读取）。
BUILD_IDENTITY_SCHEMA = "ecq.build-identity.v1"

#: 打包身份文件名与源码检出身份文件相对路径。
BUILD_IDENTITY_FILENAME = "build-identity.json"
PACKAGED_IDENTITY_DIRECTORY = ("uebench", "resources")
DEVELOPMENT_IDENTITY_PATH = ("dist", "release", "release-build-info.json")

#: 诊断页中“未知”的通用占位（用于数据版本、版本号等非身份字段）。
UNKNOWN_VALUE = "未知"

#: 尚未执行启动标准包对账时的占位（必须同时表达“未知”和“未执行”）。
RECONCILIATION_NOT_EXECUTED = "未知（本次启动未执行标准包对账）"


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuildIdentity:
    """一次构建的候选身份；缺字段时逐字段回落到占位文本。"""

    schema: str | None = None
    product_version: str = UNKNOWN_BUILD_IDENTITY
    candidate_id: str = UNKNOWN_BUILD_IDENTITY
    source_commit: str = UNKNOWN_BUILD_IDENTITY
    source_dirty: bool | None = None
    standard_package_id: str = UNKNOWN_BUILD_IDENTITY
    standard_data_version: str = UNKNOWN_BUILD_IDENTITY
    standard_package_sha256: str = UNKNOWN_BUILD_IDENTITY
    build_time_utc: str = UNKNOWN_BUILD_IDENTITY
    #: 是否真的读到了身份文件（``False`` 表示当前是占位身份）。
    embedded: bool = False
    #: 生效的身份文件路径（未嵌入时为 ``None``）。
    source_path: Path | None = None

    @property
    def source_dirty_text(self) -> str:
        if self.source_dirty is True:
            return "是"
        if self.source_dirty is False:
            return "否"
        return UNKNOWN_BUILD_IDENTITY


@dataclass(frozen=True)
class DiagnosticsFacts:
    """诊断页需要展示的非身份事实（由界面层从应用上下文收集）。"""

    product_version: str = UNKNOWN_VALUE
    data_directory: str = UNKNOWN_VALUE
    db_schema_revision: str = UNKNOWN_VALUE
    gb29446_rule_revision: str = UNKNOWN_VALUE
    bundled_package_id: str = UNKNOWN_BUILD_IDENTITY
    bundled_package_data_version: str = UNKNOWN_BUILD_IDENTITY
    installed_package_id: str = UNKNOWN_BUILD_IDENTITY
    installed_package_data_version: str = UNKNOWN_BUILD_IDENTITY
    installed_package_sha256: str = UNKNOWN_BUILD_IDENTITY


@dataclass(frozen=True)
class ReconciliationFacts:
    """最近一次启动标准包对账的可展示字段。

    由 :func:`reconciliation_facts` 从 application 层只读访问器返回的
    ``ReconciliationOutcome``（或同形对象）投影而来；本模块不导入
    ``package_reconciliation``，因此不存在循环依赖。
    """

    action: str = UNKNOWN_VALUE
    reason: str = UNKNOWN_VALUE
    message: str = UNKNOWN_VALUE
    installed_package_id: str = UNKNOWN_VALUE
    installed_data_version: str = UNKNOWN_VALUE
    bundled_package_id: str = UNKNOWN_VALUE
    bundled_data_version: str = UNKNOWN_VALUE
    #: 空字符串表示本次对账未创建备份。
    backup_path: str = ""
    errors: tuple[str, ...] = ()
    #: 是否属于“产品处于期望状态”（install / noop / upgrade）。
    succeeded: bool | None = None


def _enum_text(value: object) -> str:
    """枚举 → 稳定机器标识（``ReconciliationAction.CONFLICT`` → ``conflict``）。"""

    if value is None:
        return UNKNOWN_VALUE
    text = str(getattr(value, "value", value)).strip()
    return text or UNKNOWN_VALUE


def _identity_text(identity: object | None, attribute: str) -> str:
    if identity is None:
        return UNKNOWN_VALUE
    text = str(getattr(identity, attribute, "") or "").strip()
    return text or UNKNOWN_VALUE


def reconciliation_facts(outcome: object | None) -> ReconciliationFacts | None:
    """把对账结果投影为诊断页字段；``None``（未执行对账）时返回 ``None``。"""

    if outcome is None:
        return None
    succeeded = getattr(outcome, "succeeded", None)
    returns = getattr(outcome, "errors", None) or ()
    return ReconciliationFacts(
        action=_enum_text(getattr(outcome, "action", None)),
        reason=_enum_text(getattr(outcome, "reason", None)),
        message=str(getattr(outcome, "message", "") or "").strip() or UNKNOWN_VALUE,
        installed_package_id=_identity_text(getattr(outcome, "installed", None), "package_id"),
        installed_data_version=_identity_text(getattr(outcome, "installed", None), "data_version"),
        bundled_package_id=_identity_text(getattr(outcome, "bundled", None), "package_id"),
        bundled_data_version=_identity_text(getattr(outcome, "bundled", None), "data_version"),
        backup_path=str(getattr(outcome, "backup_path", "") or "").strip(),
        errors=tuple(str(item) for item in returns),
        succeeded=bool(succeeded) if succeeded is not None else None,
    )


# ---------------------------------------------------------------------------
# 身份文件定位与读取
# ---------------------------------------------------------------------------


def _deduplicate(paths: Iterable[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def identity_file_candidates() -> list[Path]:
    """按优先级列出构建身份候选文件（去重、保序）。

    打包位置优先于源码检出位置；``sys._MEIPASS`` / ``sys.frozen`` 的多种
    PyInstaller 布局都被覆盖，避免因为 ``_internal`` 层级差异而读不到身份。
    """

    candidates: list[Path] = []

    # 1. 打包：与 uebench/resources/* 同级。
    package_root = Path(__file__).resolve().parent.parent
    candidates.append(package_root.joinpath(*PACKAGED_IDENTITY_DIRECTORY[1:], BUILD_IDENTITY_FILENAME))

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root is not None:
        base = Path(frozen_root)
        candidates.extend(
            [
                base.joinpath(*PACKAGED_IDENTITY_DIRECTORY, BUILD_IDENTITY_FILENAME),
                base.joinpath("_internal", *PACKAGED_IDENTITY_DIRECTORY, BUILD_IDENTITY_FILENAME),
            ]
        )
    if getattr(sys, "frozen", False):
        executable_root = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                executable_root.joinpath("_internal", *PACKAGED_IDENTITY_DIRECTORY, BUILD_IDENTITY_FILENAME),
                executable_root.joinpath(*PACKAGED_IDENTITY_DIRECTORY, BUILD_IDENTITY_FILENAME),
            ]
        )

    # 2. 源码检出：<repo>/dist/release/release-build-info.json。
    candidates.append(Path(__file__).resolve().parents[3].joinpath(*DEVELOPMENT_IDENTITY_PATH))
    return _deduplicate(candidates)


def _text_field(document: dict, key: str) -> str:
    value = document.get(key)
    if value is None:
        return UNKNOWN_BUILD_IDENTITY
    text = str(value).strip()
    return text or UNKNOWN_BUILD_IDENTITY


def _dirty_field(document: dict) -> bool | None:
    value = document.get("source_dirty")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def read_build_identity(path: Path | str) -> BuildIdentity:
    """读取一个构建身份文件。

    文件不存在、不是合法 JSON、不是 JSON 对象时返回占位身份，**不抛异常**；
    缺少的字段逐个回落到占位文本。
    """

    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return BuildIdentity()
    if not isinstance(raw, dict):
        return BuildIdentity()
    schema = raw.get("schema")
    return BuildIdentity(
        schema=str(schema) if schema is not None else None,
        product_version=_text_field(raw, "product_version"),
        candidate_id=_text_field(raw, "candidate_id"),
        source_commit=_text_field(raw, "source_commit"),
        source_dirty=_dirty_field(raw),
        standard_package_id=_text_field(raw, "standard_package_id"),
        standard_data_version=_text_field(raw, "standard_data_version"),
        standard_package_sha256=_text_field(raw, "standard_package_sha256"),
        build_time_utc=_text_field(raw, "build_time_utc"),
        embedded=True,
        source_path=Path(path),
    )


def load_build_identity(candidates: Sequence[Path] | None = None) -> BuildIdentity:
    """按优先级读取第一个可用的构建身份；都不可用时返回占位身份。"""

    paths = list(candidates) if candidates is not None else identity_file_candidates()
    for path in paths:
        identity = read_build_identity(path)
        if identity.embedded:
            return identity
    return BuildIdentity()


# ---------------------------------------------------------------------------
# 诊断文本渲染（纯格式化；界面层只负责显示与复制）
# ---------------------------------------------------------------------------


def _reconciliation_section(reconciliation: ReconciliationFacts | None) -> list[str]:
    lines = ["四、最近一次标准包对账"]
    if reconciliation is None:
        # 尚未对账（或组合根未记录结果）时必须如实说明，不能显示成“已是最新”。
        lines.append(f"标准包对账状态：{RECONCILIATION_NOT_EXECUTED}")
        return lines
    lines.extend(
        [
            f"对账动作（action）：{reconciliation.action}",
            f"对账原因（reason）：{reconciliation.reason}",
            f"对账说明：{reconciliation.message}",
            f"已安装标准包 package_id：{reconciliation.installed_package_id}",
            f"已安装标准包 data_version：{reconciliation.installed_data_version}",
            f"内置标准包 package_id：{reconciliation.bundled_package_id}",
            f"内置标准包 data_version：{reconciliation.bundled_data_version}",
            "本次对账结果："
            + ("已处于期望状态" if reconciliation.succeeded else "未达到期望状态（需人工关注）"),
        ]
    )
    if reconciliation.backup_path:
        lines.append(f"升级前备份路径：{reconciliation.backup_path}")
    if reconciliation.errors:
        lines.append("对账错误：" + "；".join(reconciliation.errors))
    return lines


def render_diagnostics(
    identity: BuildIdentity,
    facts: DiagnosticsFacts,
    reconciliation: ReconciliationFacts | None = None,
) -> str:
    """把构建身份、诊断事实与最近一次标准包对账渲染为可复制的纯文本。

    只输出**元数据**：不读取、不输出 ``.pem`` 内容或任何私钥材料。
    """

    lines = [
        "单位产品能耗限额评价软件（uebench）— 关于 / 诊断信息",
        "",
        "一、产品与构建身份",
        f"产品版本：{facts.product_version}",
        f"候选构建标识（candidate_id）：{identity.candidate_id}",
        f"源码提交（source_commit）：{identity.source_commit}",
        f"源码工作区存在未提交修改（source_dirty）：{identity.source_dirty_text}",
        f"构建时间（build_time_utc）：{identity.build_time_utc}",
        "构建身份文件："
        + (
            str(identity.source_path)
            if identity.embedded and identity.source_path is not None
            else UNKNOWN_BUILD_IDENTITY
        ),
        "",
        "二、标准包",
        f"当前 bundled 标准包 package_id：{facts.bundled_package_id}",
        f"当前 bundled 标准包 data_version：{facts.bundled_package_data_version}",
        f"当前 installed 标准包 package_id：{facts.installed_package_id}",
        f"当前 installed 标准包 data_version：{facts.installed_package_data_version}",
        f"当前 installed 标准包 SHA256：{facts.installed_package_sha256}",
        "",
        "三、规则与数据库",
        f"当前 GB 29446 rule_revision：{facts.gb29446_rule_revision}",
        f"数据库 Schema 版本（数据库中实际存在的 Alembic 版本）：{facts.db_schema_revision}",
        f"当前数据目录：{facts.data_directory}",
        "",
        *_reconciliation_section(reconciliation),
        "",
        "本页为只读信息，不含私钥或其他凭据内容。",
    ]
    return "\n".join(lines)
