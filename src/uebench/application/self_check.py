"""无头候选版本自检（Headless candidate self-check, ECQ-RS05 §14）。

本模块让**打包后的 UEBench.exe** 与源码检出都能在不启动界面的前提下证明自身完整性：

.. code-block:: text

    UEBench.exe --self-check --output <json path> --data-dir <isolated dir>

设计约束（必须保持）：

* **不导入 PySide6**，不创建 ``QApplication``，不需要显示器，也不依赖
  ``QT_QPA_PLATFORM=offscreen``；本模块因此不属于 UI 层。
* **不引入第二套算法**：等级判定只经过真实 ``ApplicationFacade`` →
  ``EvaluationService`` → ``EvaluationEngine``；本模块只负责构造请求与比较期望值。
* **不触碰 ``%LOCALAPPDATA%``**：所有写入都发生在调用方给出的隔离 ``--data-dir`` 内。
* 本模块位于 application 层，受 ``tests/test_architecture_boundaries.py`` 约束，
  因此**不得**导入 ``PySide6`` / ``sqlalchemy`` / ``openpyxl`` /
  ``uebench.infrastructure`` / ``uebench.ui`` / ``uebench.bootstrap``。
  组合根（``uebench.main``）通过下面两个**端口**注入被禁止的直接依赖：

  - ``ContextFactory``：以 ``--data-dir`` 构造真实的 ``AppContext``
    （真实的 ``DatabaseManager`` / 仓储 / ``ApplicationFacade``）；
  - ``WorkbookRowWriter``：用真实 Excel 引擎把单元格写入模板
    （``openpyxl`` 由组合根持有）。

报告 Schema（JSON，UTF-8）
-------------------------

.. code-block:: json

    {
      "schema": "uebench.self-check-report",
      "schema_version": 1,
      "generated_at": "2026-10-04T00:00:00Z",
      "data_dir": "<绝对路径>",
      "product_version": "<uebench.__version__>",
      "frozen": false,
      "overall_status": "passed" | "failed",
      "exit_code": 0 | 1,
      "failed_checks": ["<check id>", "..."],
      "warnings": ["<不阻断通过、但必须人工阅读的发现>"],
      "checks": [
        {
          "id": "build_info"
              | "standard_package"
              | "database"
              | "golden_replay"
              | "record_roundtrip"
              | "excel_import_chain",
          "title": "<中文标题>",
          "status": "passed" | "failed",
          "errors": ["<失败原因，已本地化>"],
          "details": { "<机器可读证据，键名稳定；随检查项不同>" }
        }
      ]
    }

``checks`` 的顺序即执行顺序，``id`` 唯一。各检查项的 ``details`` 至少包含：

``build_info``
    ``product_version`` / ``rule_engine_version`` / ``python_version`` /
    ``python_implementation`` / ``frozen`` / ``platform`` / ``executable`` /
    ``source_root`` / ``qt_imported`` / ``qt_imported_by_self_check``。

    其中 ``qt_imported`` 是**绝对**状态（宿主进程是否已加载 Qt，仅作证据）；
    ``qt_imported_by_self_check`` 是自检开始前后的**差值**，只有它为真才判失败，
    因为宿主进程（桌面界面、pytest 会话）本来就可能已经导入 PySide6。

``standard_package``
    ``package_path`` / ``package_sha256`` / ``public_key_path`` /
    ``public_key_sha256`` / ``signature_verified`` / ``package_id`` /
    ``data_version`` / ``package_mode`` / ``issued_at`` / ``standard_count`` /
    ``rule_count`` / ``preview_valid`` / ``definition_count`` /
    ``packaged_golden_rule_revision`` / ``install_verified`` /
    ``installed_standard_count``。

``database``
    ``data_dir`` / ``database_path`` / ``schema_revision`` /
    ``expected_revision`` / ``repository_migration_head`` /
    ``migrations_directory``。

``golden_replay``
    ``golden_id`` / ``golden_version`` / ``standard_id`` / ``rule_revision`` /
    ``rule_source`` (``standard-package`` | ``repository-definition``) /
    ``rule_source_path`` / ``installed_rule_revision`` / ``cases``（每例含
    ``case_id`` / ``expected_grade`` / ``actual_grade`` /
    ``expected_actual_value`` / ``actual_value`` / ``passed`` /
    ``evaluation_id``）。

``record_roundtrip``
    ``case_id`` / ``evaluation_id`` / ``restored`` / ``grade`` /
    ``actual_value`` / ``rule_revision`` / ``snapshot_rule_revision`` /
    ``record_count``。

``excel_import_chain``
    ``case_id`` / ``template_path`` / ``template_sha256`` / ``valid`` /
    ``import_id`` / ``issues`` / ``evaluation_id`` / ``grade`` /
    ``actual_value`` / ``matches_golden``。

进程退出码（由组合根 ``uebench.main`` 落实）
-------------------------------------------

======  ==================================================================
退出码  含义
======  ==================================================================
``0``   全部检查通过（``overall_status == "passed"``）
``1``   至少一项检查失败；报告 ``failed_checks`` 列出失败项
``2``   用法/参数错误，例如缺少 ``--data-dir``、``--output`` 不可写
        （由 ``argparse`` 的 ``parser.error`` 产生）
======  ==================================================================

内嵌 Golden 子集的来源（不得凭软件输出反推）
-------------------------------------------

下面 :data:`GOLDEN_CASES` 的三个案例**逐字抄录**自
``tests/golden/gb29446_product_golden_v1.json``（``golden_version`` 为 1，
``golden_status`` 为 ``ADOPTED``）：

* ``gb29446-coking-grade1-exact-l1`` — 炼焦煤 / k=1.00 /
  E_d=500 / m=100 → e_d = 5.0，恰等于表1 的 1 级上限 ≤5.0，判 ``LEVEL_1``；
* ``gb29446-coking-not-qualified-above-l3`` — 炼焦煤 / k=0.83 /
  E_d=1100 / m=100 → e_d = 9.13 > 8.5，判 ``NOT_QUALIFIED``；
* ``gb29446-coking-full-value-trap`` — 炼焦煤 / k=1.00 /
  E_d=500.00004 / m=100 → e_d = 5.0000004。full-value exact 比较下
  5.0000004 > 5.0，因此**不得**判 1 级，而是 ``LEVEL_2``。

打包 payload 不包含 ``tests/``，所以这三个案例只能内嵌；它们是 RS04 Product
Golden 的**子集**，既不替代完整 Golden，也不得被修改成软件当前输出的样子。
一旦 ``tests/golden/gb29446_product_golden_v1.json`` 升级（``golden_version``
变化），必须同步复核本模块。

Golden 规则来源（payload 漂移的处置）
-------------------------------------

RS04 Golden 冻结的是 ``gb-29446-2019`` 的 ``rule_revision = 2``。自检按以下顺序
解析用于回放的规则定义，并在 ``golden_replay.details`` 中如实记录
``rule_source``：

1. **standard-package** — 内置已签名标准包内已经是 ``rule_revision 2`` 的
   ``gb-29446-2019`` 定义（打包 payload 的正常状态，也是唯一能让
   ``UEBench.exe --self-check`` 通过的状态）；
2. **repository-definition** — 标准包内定义版本落后、而仓库
   ``data/definitions/gb-29446-2019.json`` 满足 Golden 要求的
   ``rule_revision`` 时，改用该仓库定义（仅源码检出可用），同时写入
   ``warnings``，指出 payload 与 Golden 的版本落差；
3. 两者都不可用时，回放**失败**（退出码 ``1``），错误信息直接说明 payload
   落后，不静默跳过。

第 2 条是当前 ``release/standard-packages/`` 固定标准包已知缺口的显式处置；
缺口本身记录在 ``release/standard-packages/PIN.json`` 的 ``known_gap`` 中，属于
发布治理决定，本模块只负责如实暴露，不修改标准包。
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import zipfile
from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from uebench import RULE_ENGINE_VERSION, __version__
from uebench.domain.models import (
    EvaluationRequest,
    InputMode,
    InputValue,
    StandardDefinition,
    StandardSelectionMode,
)

from .gb29446 import (
    FIELD_COAL_TYPE,
    FIELD_CUSTOM_PERIOD,
    FIELD_ELECTRICITY,
    FIELD_EVALUATION_DATE,
    FIELD_NOTES,
    FIELD_ORGANIZATION_NAME,
    FIELD_PERIOD,
    FIELD_RAW_COAL,
    FIELD_WASHING_PROCESS,
    PERIOD_FULL_YEAR,
    encode_period_notes,
)

# ---------------------------------------------------------------------------
# 退出码与报告 Schema
# ---------------------------------------------------------------------------

#: 全部检查通过。
EXIT_OK = 0
#: 至少一项检查失败。
EXIT_CHECKS_FAILED = 1
#: 用法/参数错误（由 argparse 产生）。
EXIT_USAGE = 2

#: 报告顶层标识与版本；升级报告结构时必须同时递增 ``schema_version``。
REPORT_SCHEMA = "uebench.self-check-report"
REPORT_SCHEMA_VERSION = 1

#: 内置标准包/公钥的固定文件名与相对位置。
PREFERRED_PACKAGE_FILENAME = "initial-standard-package-published.uebench"
PACKAGE_FILENAME_GLOB = "initial-standard-package-*.uebench"
PUBLIC_KEY_FILENAME = "update_public_key.pem"
RELEASE_PACKAGE_DIRECTORY = ("release", "standard-packages")
PACKAGED_RESOURCE_DIRECTORY = ("uebench", "resources")

#: ECQ-RS05 发布基线：Alembic head 为 ``0003``（schema 变更时必须同步）。
EXPECTED_SCHEMA_REVISION = "0003"

# ---------------------------------------------------------------------------
# 内嵌 RS04 Golden 子集（逐字来自 tests/golden/gb29446_product_golden_v1.json）
# ---------------------------------------------------------------------------

GOLDEN_ID = "gb29446_product_golden"
GOLDEN_VERSION = 1
GOLDEN_STANDARD_ID = "gb-29446-2019"
GOLDEN_RULE_REVISION = 2
GOLDEN_EVALUATION_DATE = date(2026, 6, 1)
GOLDEN_ORGANIZATION = "RS05 自检"
GOLDEN_NOTE = "RS05 self-check（RS04 Product Golden v1 子集）"
GOLDEN_REPOSITORY_DEFINITION_DIRECTORY = ("data", "definitions")

#: 逐字抄录自 ``tests/golden/gb29446_product_golden_v1.json`` 的 ``cases``。
GOLDEN_CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "gb29446-coking-grade1-exact-l1",
        "coal_type": "炼焦煤",
        "washing_process": "跳汰、浮选联合",
        "electricity_consumption": "500",
        "raw_coal_input": "100",
        "enterprise_status": "现有",
        "single_coal_single_process": True,
        "expected_k": "1.00",
        "expected_e_d": "5.0",
        "expected_grade": "LEVEL_1",
    },
    {
        "case_id": "gb29446-coking-not-qualified-above-l3",
        "coal_type": "炼焦煤",
        "washing_process": "重介、浮选联合",
        "electricity_consumption": "1100",
        "raw_coal_input": "100",
        "enterprise_status": "现有",
        "single_coal_single_process": True,
        "expected_k": "0.83",
        "expected_e_d": "9.13",
        "expected_grade": "NOT_QUALIFIED",
    },
    {
        "case_id": "gb29446-coking-full-value-trap",
        "coal_type": "炼焦煤",
        "washing_process": "跳汰、浮选联合",
        "electricity_consumption": "500.00004",
        "raw_coal_input": "100",
        "enterprise_status": "现有",
        "single_coal_single_process": True,
        "expected_k": "1.00",
        "expected_e_d": "5.0000004",
        "expected_grade": "LEVEL_2",
    },
)

#: 用于记录往返与 Excel 链路的 Golden 案例（exact-threshold 案例）。
ROUNDTRIP_CASE_ID = "gb29446-coking-grade1-exact-l1"

#: GB29446 模板中“评价数据”表的行号（值写入 B 列）。
#: 与 ``uebench.infrastructure.excel.GB29446_DATA_ROWS`` 的表头顺序一致；
#: 与 ``tests/test_gb29446_product_golden.py`` 的 ``EXCEL_DATA_ROWS`` 相同。
GOLDEN_TEMPLATE_SHEET = "评价数据"
GOLDEN_TEMPLATE_ROWS: dict[str, int] = {
    FIELD_ORGANIZATION_NAME: 2,
    FIELD_EVALUATION_DATE: 3,
    FIELD_PERIOD: 4,
    FIELD_CUSTOM_PERIOD: 5,
    FIELD_COAL_TYPE: 6,
    FIELD_WASHING_PROCESS: 7,
    FIELD_ELECTRICITY: 8,
    FIELD_RAW_COAL: 9,
    FIELD_NOTES: 10,
}

#: 自检在工作簿中写入的说明文字（不参与业务判定）。
GOLDEN_TEMPLATE_NOTE = "RS05 self-check"


# ---------------------------------------------------------------------------
# 组合根注入的端口（application 层不得直接依赖 infrastructure / openpyxl）
# ---------------------------------------------------------------------------


class ContextFactory(Protocol):
    """以隔离数据目录构造真实应用上下文。

    实现由组合根提供（``uebench.bootstrap.create_context``），返回对象需要具备
    ``paths``（含 ``database``）、``database``（含 ``current_revision`` /
    ``dispose``）、``standards``（含 ``install``）与 ``application``
    （``ApplicationFacade``）四个属性。之所以不在本模块导入
    ``uebench.bootstrap``，是因为 application 层被禁止依赖组合根。
    """

    def __call__(self, data_dir: Path) -> object: ...


class WorkbookRowWriter(Protocol):
    """把 ``rows``（行号 → 值）写入 ``sheet_name`` 表的 B 列。

    实现由组合根提供（``openpyxl``），因为 application 层不得导入
    ``openpyxl``。应用层只决定“写什么”，不决定“怎么写”。
    """

    def __call__(self, path: Path, sheet_name: str, rows: Mapping[int, object]) -> None: ...


# ---------------------------------------------------------------------------
# 失败类型
# ---------------------------------------------------------------------------


class SelfCheckError(RuntimeError):
    """一项检查无法继续；``details`` 可携带已经收集到的证据。"""

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details: dict[str, Any] = dict(details or {})


# ---------------------------------------------------------------------------
# 路径与格式化工具
# ---------------------------------------------------------------------------


def source_root() -> Path | None:
    """返回源码检出根目录；打包运行时返回 ``None``。

    本模块位于 ``<root>/src/uebench/application/self_check.py``，因此
    ``parents[3]`` 即仓库根。
    """
    if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
        return None
    candidate = Path(__file__).resolve().parents[3]
    return candidate if (candidate / "src" / "uebench").is_dir() else None


def _packaged_resource_roots() -> list[Path]:
    """PyInstaller 打包后可能暴露资源的位置（一对一 folder 与 onefile 均覆盖）。"""
    roots: list[Path] = []
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root is not None:
        base = Path(frozen_root)
        roots.extend([base, base / "_internal"])
    if getattr(sys, "frozen", False):
        executable_root = Path(sys.executable).resolve().parent
        roots.extend([executable_root, executable_root / "_internal"])
    return roots


def _package_candidates() -> list[Path]:
    """按优先级列出内置标准包候选路径（去重、保序）。"""
    candidates: list[Path] = []
    for root in _packaged_resource_roots():
        resource_directory = root.joinpath(*PACKAGED_RESOURCE_DIRECTORY)
        candidates.append(resource_directory / PREFERRED_PACKAGE_FILENAME)
        candidates.extend(sorted(resource_directory.glob(PACKAGE_FILENAME_GLOB)))
    root = source_root()
    if root is not None:
        release_directory = root.joinpath(*RELEASE_PACKAGE_DIRECTORY)
        candidates.append(release_directory / PREFERRED_PACKAGE_FILENAME)
        candidates.extend(sorted(release_directory.glob(PACKAGE_FILENAME_GLOB)))
        candidates.extend(
            sorted(root.joinpath("src", *PACKAGED_RESOURCE_DIRECTORY).glob(PACKAGE_FILENAME_GLOB))
        )
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def locate_standard_package() -> Path | None:
    """定位内置已签名标准包；找不到时返回 ``None``。

    打包运行：``sys._MEIPASS`` / ``_internal`` 下的 ``uebench/resources``。
    源码运行：``release/standard-packages/initial-standard-package-published.uebench``
    （其次 ``src/uebench/resources/``）。
    """
    candidates = _package_candidates()
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _public_key_candidates() -> list[Path]:
    candidates: list[Path] = []
    for root in _packaged_resource_roots():
        candidates.append(root.joinpath(*PACKAGED_RESOURCE_DIRECTORY) / PUBLIC_KEY_FILENAME)
    root = source_root()
    if root is not None:
        candidates.append(root.joinpath("src", *PACKAGED_RESOURCE_DIRECTORY) / PUBLIC_KEY_FILENAME)
    candidates.append(
        Path(__file__).resolve().parents[1].joinpath("resources") / PUBLIC_KEY_FILENAME
    )
    return candidates


def locate_public_key() -> Path | None:
    """定位内置 Ed25519 公钥 ``update_public_key.pem``；找不到时返回 ``None``。"""
    for candidate in _public_key_candidates():
        if candidate.is_file():
            return candidate
    return None


def _repository_definition_path(standard_id: str) -> Path | None:
    """源码检出中的标准定义文件 ``data/definitions/<id>.json``。"""
    root = source_root()
    if root is None:
        return None
    return root.joinpath(*GOLDEN_REPOSITORY_DEFINITION_DIRECTORY, f"{standard_id}.json")


def _resolve_migrations_directory() -> Path | None:
    """与 ``DatabaseManager.initialize`` 相同的迁移目录搜索顺序（只读探测）。"""
    candidates: list[Path] = []
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root is not None:
        base = Path(frozen_root)
        candidates.extend([base / "migrations", base / "_internal" / "migrations"])
    if getattr(sys, "frozen", False):
        executable_root = Path(sys.executable).resolve().parent
        candidates.extend(
            [executable_root / "migrations", executable_root / "_internal" / "migrations"]
        )
    candidates.append(Path(__file__).resolve().parents[3] / "migrations")
    return next((path for path in candidates if path.exists()), None)


def _migration_head(directory: Path | None) -> str | None:
    """按 ``migrations/versions/NNNN_*.py`` 文件名推断 head 修订号。"""
    if directory is None:
        return None
    versions = directory / "versions"
    if not versions.is_dir():
        return None
    revisions = sorted(
        path.name.split("_", 1)[0]
        for path in versions.glob("[0-9][0-9][0-9][0-9]_*.py")
    )
    return revisions[-1] if revisions else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_public_key(path: Path) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise SelfCheckError(f"更新公钥不是 Ed25519 公钥：{path}")
    return key


def _dec_text(value: Any) -> str | None:
    """规范化十进制文本；数值相等即文本相等（去掉多余的尾随零）。"""
    if value is None:
        return None
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return format(value.normalize(), "f")


def _grade_text(grade: Any) -> str:
    return str(getattr(grade, "value", grade))


def _issue_text(issue: Any) -> str:
    severity = getattr(issue, "severity", "?")
    sheet = getattr(issue, "sheet", "?")
    cell = getattr(issue, "cell", "?")
    message = getattr(issue, "message", str(issue))
    return f"{severity} {sheet}!{cell} {message}"


def _qt_modules() -> set[str]:
    return {name for name in sys.modules if name == "PySide6" or name.startswith("PySide6.")}


def _qt_imported() -> bool:
    return bool(_qt_modules())


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# 自检执行器
# ---------------------------------------------------------------------------


class _Runner:
    """按固定顺序执行六项检查并汇总为可序列化报告。"""

    def __init__(
        self,
        *,
        data_dir: Path,
        context_factory: ContextFactory | None,
        workbook_writer: WorkbookRowWriter | None,
        package_path: Path | None,
        public_key_path: Path | None,
        definition_path: Path | None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.context_factory = context_factory
        self.workbook_writer = workbook_writer
        self.package_path = Path(package_path) if package_path is not None else None
        self.public_key_path = Path(public_key_path) if public_key_path is not None else None
        self.definition_path = Path(definition_path) if definition_path is not None else None
        self.warnings: list[str] = []
        self._context: Any = None
        self._bootstrap_error: str | None = None
        self._golden_cases: dict[str, dict[str, Any]] = {}
        #: 自检开始时的 Qt 状态。宿主进程（例如桌面界面或 pytest 会话）可能早已
        #: 导入 PySide6；只有**自检自己**引入的 Qt 才是违规，因此按差值判定。
        self._qt_at_start: set[str] = set()

    # -- 编排 -------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        self._qt_at_start = _qt_modules()
        self._bootstrap()
        try:
            checks = [
                self._execute("build_info", "构建信息", self._check_build_info),
                self._execute("standard_package", "内置标准包校验", self._check_standard_package),
                self._execute("database", "数据库初始化", self._check_database),
                self._execute("golden_replay", "GB29446 Golden 回放", self._check_golden_replay),
                self._execute("record_roundtrip", "评价记录往返校验", self._check_record_roundtrip),
                self._execute(
                    "excel_import_chain", "Excel 模板与导入链路", self._check_excel_import_chain
                ),
            ]
        finally:
            self._dispose()
        failed = [check["id"] for check in checks if check["status"] != "passed"]
        return {
            "schema": REPORT_SCHEMA,
            "schema_version": REPORT_SCHEMA_VERSION,
            "generated_at": _timestamp(),
            "data_dir": self._data_dir_text(),
            "product_version": __version__,
            "frozen": self._frozen(),
            "overall_status": "passed" if not failed else "failed",
            "exit_code": EXIT_OK if not failed else EXIT_CHECKS_FAILED,
            "failed_checks": failed,
            "warnings": list(self.warnings),
            "checks": checks,
        }

    def _execute(
        self, check_id: str, title: str, function: Callable[[], tuple[dict[str, Any], list[str]]]
    ) -> dict[str, Any]:
        try:
            details, errors = function()
        except SelfCheckError as exc:
            details, errors = dict(exc.details), [str(exc)]
        except Exception as exc:  # pragma: no cover - 兜底，保证报告总能产出
            details, errors = {}, [f"未预期异常：{type(exc).__name__}: {exc}"]
        return {
            "id": check_id,
            "title": title,
            "status": "passed" if not errors else "failed",
            "errors": [str(error) for error in errors],
            "details": details,
        }

    def _bootstrap(self) -> None:
        if self.context_factory is None:
            self._bootstrap_error = "组合根未提供应用上下文工厂（ContextFactory）"
            return
        try:
            self._context = self.context_factory(self.data_dir)
        except Exception as exc:
            self._bootstrap_error = f"{type(exc).__name__}: {exc}"

    def _dispose(self) -> None:
        if self._context is None:
            return
        try:
            self._context.database.dispose()
        except Exception:  # pragma: no cover - 释放失败不影响报告
            pass

    def _require_context(self) -> Any:
        if self._context is not None:
            return self._context
        raise SelfCheckError(f"隔离数据目录初始化失败：{self._bootstrap_error or '未知原因'}")

    def _data_dir_text(self) -> str:
        try:
            return str(self.data_dir.resolve())
        except OSError:  # pragma: no cover - 仅用于无法解析的异常路径
            return str(self.data_dir)

    @staticmethod
    def _frozen() -> bool:
        return bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS")

    # -- 1. 构建信息 -------------------------------------------------------

    def _check_build_info(self) -> tuple[dict[str, Any], list[str]]:
        qt_imported = _qt_imported()
        qt_by_self_check = bool(_qt_modules() - self._qt_at_start)
        root = source_root()
        details: dict[str, Any] = {
            "product_version": __version__,
            "rule_engine_version": RULE_ENGINE_VERSION,
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "frozen": self._frozen(),
            "platform": platform.platform(),
            "executable": sys.executable,
            "source_root": str(root) if root is not None else None,
            "self_check_module": str(Path(__file__).resolve()),
            "qt_imported": qt_imported,
            "qt_imported_by_self_check": qt_by_self_check,
            "data_dir": self._data_dir_text(),
            "report_schema": REPORT_SCHEMA,
            "report_schema_version": REPORT_SCHEMA_VERSION,
        }
        errors: list[str] = []
        if not __version__:
            errors.append("uebench.__version__ 为空，产品版本不可信")
        if qt_by_self_check:
            errors.append("自检过程导入了 PySide6，违反“不启动界面、不依赖 Qt”的约束")
        return details, errors

    # -- 2. 标准包校验 -----------------------------------------------------

    def _check_standard_package(self) -> tuple[dict[str, Any], list[str]]:
        errors: list[str] = []
        package_path = self.package_path or locate_standard_package()
        details: dict[str, Any] = {
            "package_path": str(package_path) if package_path is not None else None,
            "package_candidates": [str(path) for path in _package_candidates()],
        }
        if package_path is None or not package_path.is_file():
            reason = (
                f"指定的标准包不存在或不是文件：{package_path}"
                if self.package_path is not None
                else "未找到内置已签名标准包（已搜索："
                + "、".join(details["package_candidates"])
                + "）"
            )
            raise SelfCheckError(reason, details=details)
        details["package_size"] = package_path.stat().st_size
        details["package_sha256"] = _sha256_file(package_path)

        key_path = self.public_key_path or locate_public_key()
        details["public_key_path"] = str(key_path) if key_path is not None else None
        if key_path is None or not key_path.is_file():
            raise SelfCheckError("未找到内置更新公钥 update_public_key.pem", details=details)
        details["public_key_sha256"] = _sha256_file(key_path)
        try:
            public_key = _load_public_key(key_path)
        except SelfCheckError:
            raise
        except Exception as exc:
            raise SelfCheckError(f"更新公钥无法加载：{exc}", details=details) from exc

        try:
            with zipfile.ZipFile(package_path) as archive:
                manifest_bytes = archive.read("manifest.json")
                signature = archive.read("signature.ed25519")
        except (zipfile.BadZipFile, KeyError, OSError) as exc:
            raise SelfCheckError(
                f"标准包无法读取：{type(exc).__name__}: {exc}", details=details
            ) from exc

        try:
            public_key.verify(signature, manifest_bytes)
        except InvalidSignature as exc:
            raise SelfCheckError("标准包 Ed25519 签名校验失败", details=details) from exc
        details["signature_verified"] = True

        try:
            documented = json.loads(manifest_bytes)
        except json.JSONDecodeError as exc:
            raise SelfCheckError(f"标准包清单不是合法 JSON：{exc}", details=details) from exc
        for field in (
            "schema_version",
            "package_id",
            "data_version",
            "package_mode",
            "issued_at",
            "minimum_app_version",
            "rule_engine_version",
            "standard_count",
            "rule_count",
        ):
            details[field] = documented.get(field)

        context = self._require_context()
        try:
            preview = context.application.preview_package(package_path)
        except Exception as exc:
            raise SelfCheckError(
                f"应用层标准包预览失败：{type(exc).__name__}: {exc}", details=details
            ) from exc

        details["preview_valid"] = bool(preview.valid)
        details["preview_errors"] = [str(error) for error in preview.errors]
        details["preview_warnings"] = [str(warning) for warning in preview.warnings]
        manifest = preview.manifest
        if manifest is None:
            errors.append("标准包清单缺失，无法核对 package_id / data_version / 数量")
        else:
            for field in ("package_id", "data_version", "standard_count", "rule_count"):
                reported = getattr(manifest, field)
                if documented.get(field) != reported:
                    errors.append(
                        f"标准包清单字段 {field} 与应用层解析不一致："
                        f"{reported!r} != {documented.get(field)!r}"
                    )

        definitions = list(preview.definitions)
        details["definition_count"] = len(definitions)
        golden_definition = next(
            (item for item in definitions if item.id == GOLDEN_STANDARD_ID), None
        )
        details["packaged_golden_standard_id"] = GOLDEN_STANDARD_ID
        details["packaged_golden_available"] = golden_definition is not None
        details["packaged_golden_rule_revision"] = (
            golden_definition.rule_revision if golden_definition is not None else None
        )
        details["golden_rule_revision"] = GOLDEN_RULE_REVISION

        # 同一个隔离数据目录被重复使用时，应用层预览会以“该标准包已安装”判为无效。
        # 这不是缺 integrity，而是“已安装”；判定依据取自真实的标准包历史仓储，
        # 不做错误文案匹配。
        installed_ids: set[str] = set()
        try:
            for entry in context.application.list_package_history(200):
                package_id = getattr(entry, "package_id", None)
                if package_id:
                    installed_ids.add(str(package_id))
        except Exception as exc:
            details["package_history_error"] = f"{type(exc).__name__}: {exc}"
        already_installed = bool(documented.get("package_id")) and (
            documented.get("package_id") in installed_ids
        )
        details["already_installed"] = already_installed

        if not preview.valid and not already_installed:
            errors.extend(details["preview_errors"])
            details["install_verified"] = False
            errors.append("标准包未通过应用层校验，已跳过安装验证")
            return details, errors

        if already_installed:
            details["install_verified"] = True
            details["install_note"] = "隔离数据目录已安装同一标准包，跳过重复安装"
            if not preview.valid:
                details["preview_errors_tolerated"] = details["preview_errors"]
            return details, errors

        try:
            installed = context.application.install_package(package_path)
        except Exception as exc:
            details["install_verified"] = False
            errors.append(f"标准包安装失败：{type(exc).__name__}: {exc}")
            return details, errors

        details["install_verified"] = True
        details["installed_package_id"] = installed.package_id
        details["installed_data_version"] = installed.data_version
        details["installed_standard_count"] = installed.standards_installed
        if manifest is not None and installed.package_id != manifest.package_id:
            errors.append(
                f"安装结果 package_id 与清单不一致：{installed.package_id} != {manifest.package_id}"
            )
        if installed.standards_installed != documented.get("standard_count"):
            errors.append(
                "安装标准数量与清单 standard_count 不一致："
                f"{installed.standards_installed} != {documented.get('standard_count')}"
            )
        return details, errors

    # -- 3. 数据库初始化 ---------------------------------------------------

    def _check_database(self) -> tuple[dict[str, Any], list[str]]:
        errors: list[str] = []
        context = self._require_context()
        database = getattr(context, "database", None)
        paths = getattr(context, "paths", None)
        if database is None:
            raise SelfCheckError("应用上下文未提供 database（DatabaseManager）")
        database_path = Path(getattr(paths, "database")) if paths is not None else None
        migrations = _resolve_migrations_directory()
        head = _migration_head(migrations)
        details: dict[str, Any] = {
            "data_dir": self._data_dir_text(),
            "database_path": str(database_path) if database_path is not None else None,
            "schema_revision": None,
            "expected_revision": EXPECTED_SCHEMA_REVISION,
            "repository_migration_head": head,
            "migrations_directory": str(migrations) if migrations is not None else None,
        }
        if database_path is None:
            errors.append("应用上下文未提供数据库路径")
        elif not database_path.is_file():
            errors.append(f"隔离数据目录中未生成 SQLite 数据库文件：{database_path}")
        else:
            try:
                if database_path.parent != self.data_dir.resolve():
                    errors.append(
                        "数据库文件不在隔离 --data-dir 内，可能写入了真实数据目录："
                        f"{database_path}"
                    )
            except OSError:  # pragma: no cover - 路径不可解析时忽略该附加判断
                pass
        try:
            revision = database.current_revision()
        except Exception as exc:
            errors.append(f"无法读取数据库 schema 版本：{type(exc).__name__}: {exc}")
            revision = None
        details["schema_revision"] = revision
        accepted = {EXPECTED_SCHEMA_REVISION}
        if head is not None:
            accepted.add(head)
        if revision is None:
            errors.append("数据库未写入 alembic_version 标记，schema 版本未知")
        elif revision not in accepted:
            suffix = f"（仓库迁移 head 为 {head}）" if head is not None else ""
            errors.append(
                f"数据库 schema 版本为 {revision}，期望 {EXPECTED_SCHEMA_REVISION}{suffix}"
            )
        return details, errors

    # -- 4. Golden 回放 ----------------------------------------------------

    def _check_golden_replay(self) -> tuple[dict[str, Any], list[str]]:
        errors: list[str] = []
        context = self._require_context()
        application = getattr(context, "application", None)
        if application is None:
            raise SelfCheckError("应用上下文未提供 application（ApplicationFacade）")
        details: dict[str, Any] = {
            "golden_id": GOLDEN_ID,
            "golden_version": GOLDEN_VERSION,
            "standard_id": GOLDEN_STANDARD_ID,
            "rule_revision": GOLDEN_RULE_REVISION,
            "evaluation_date": GOLDEN_EVALUATION_DATE.isoformat(),
            "rule_source": None,
            "rule_source_path": None,
            "installed_rule_revision": None,
            "cases": [],
        }
        standard = self._resolve_golden_rule(context, details, errors)
        if standard is None:
            errors.append(
                "未安装可驱动 RS04 Product Golden 的 GB 29446 规则；"
                "内置标准包内定义落后，且找不到仓库定义 data/definitions/"
                f"{GOLDEN_STANDARD_ID}.json"
            )
            return details, errors

        details["installed_rule_revision"] = standard.rule_revision
        details["selection_schema_keys"] = [level.key for level in standard.selection_schema]
        if standard.rule_revision != GOLDEN_RULE_REVISION:
            errors.append(
                f"已安装 GB 29446 规则版本为 r{standard.rule_revision}，"
                f"RS04 Product Golden 要求 r{GOLDEN_RULE_REVISION}"
            )

        passed = 0
        for case in GOLDEN_CASES:
            entry: dict[str, Any] = {
                "case_id": case["case_id"],
                "expected_grade": case["expected_grade"],
                "expected_actual_value": _dec_text(case["expected_e_d"]),
                "expected_process_factor": _dec_text(case["expected_k"]),
                "actual_grade": None,
                "actual_value": None,
                "process_factor": None,
                "evaluation_id": None,
                "passed": False,
                "errors": [],
            }
            try:
                product = next(
                    (
                        item
                        for item in standard.products
                        if item.selection_values.get("coal_type") == case["coal_type"]
                    ),
                    None,
                )
                if product is None:
                    raise SelfCheckError(
                        f"标准未声明煤种 {case['coal_type']}"
                        "（products[].selection_values 缺失，payload 规则过旧）"
                    )
                request = _build_golden_request(standard, product.id, case)
                result = application.evaluate(request)
                item = result.results[0]
                entry["evaluation_id"] = result.evaluation_id
                entry["actual_grade"] = _grade_text(item.grade)
                entry["actual_value"] = _dec_text(item.actual_value)
                entry["process_factor"] = _dec_text(item.display_values.get("process_factor"))
                entry["result_rule_revision"] = result.rule_revision
                if entry["actual_grade"] != case["expected_grade"]:
                    entry["errors"].append(
                        f"等级不符：实际 {entry['actual_grade']}，期望 {case['expected_grade']}"
                    )
                if entry["actual_value"] != entry["expected_actual_value"]:
                    entry["errors"].append(
                        f"单位产品电耗不符：实际 {entry['actual_value']}，"
                        f"期望 {entry['expected_actual_value']}"
                    )
                if entry["process_factor"] != entry["expected_process_factor"]:
                    entry["errors"].append(
                        f"折算系数 k 不符：实际 {entry['process_factor']}，"
                        f"期望 {entry['expected_process_factor']}"
                    )
            except SelfCheckError as exc:
                entry["errors"].append(str(exc))
            except Exception as exc:
                entry["errors"].append(f"{type(exc).__name__}: {exc}")
            entry["passed"] = not entry["errors"]
            if entry["passed"]:
                passed += 1
            else:
                errors.extend(f"{case['case_id']}：{message}" for message in entry["errors"])
            details["cases"].append(entry)
            self._golden_cases[case["case_id"]] = entry

        details["passed_case_count"] = passed
        details["failed_case_count"] = len(GOLDEN_CASES) - passed
        return details, errors

    def _resolve_golden_rule(
        self, context: Any, details: dict[str, Any], errors: list[str]
    ) -> StandardDefinition | None:
        """解析回放所用规则，并如实记录来源与版本落差。"""
        application = context.application
        try:
            published = application.get_published_standard(GOLDEN_STANDARD_ID)
        except Exception as exc:
            raise SelfCheckError(
                f"读取已发布标准失败：{type(exc).__name__}: {exc}", details=details
            ) from exc

        if published is not None and published.rule_revision == GOLDEN_RULE_REVISION:
            details["rule_source"] = "standard-package"
            return published

        packaged_revision = published.rule_revision if published is not None else None
        definition_path = self.definition_path or _repository_definition_path(GOLDEN_STANDARD_ID)
        if definition_path is not None and definition_path.is_file():
            details["rule_source_path"] = str(definition_path)
            try:
                definition = StandardDefinition.model_validate_json(
                    definition_path.read_text(encoding="utf-8")
                )
            except Exception as exc:
                errors.append(
                    f"仓库标准定义无法加载：{definition_path}（{type(exc).__name__}: {exc}）"
                )
                return published
            if definition.id != GOLDEN_STANDARD_ID:
                errors.append(
                    f"仓库标准定义 id 不符：{definition.id} != {GOLDEN_STANDARD_ID}"
                )
                return published
            if definition.rule_revision != GOLDEN_RULE_REVISION:
                errors.append(
                    f"仓库标准定义规则版本为 r{definition.rule_revision}，"
                    f"RS04 Product Golden 要求 r{GOLDEN_RULE_REVISION}"
                )
                return published
            try:
                context.standards.install(definition)
            except Exception as exc:
                errors.append(f"仓库标准定义安装失败：{type(exc).__name__}: {exc}")
                return published
            try:
                resolved = application.get_published_standard(GOLDEN_STANDARD_ID)
            except Exception as exc:
                errors.append(f"读取已发布标准失败：{type(exc).__name__}: {exc}")
                return published
            if resolved is None or resolved.rule_revision != GOLDEN_RULE_REVISION:
                errors.append("仓库标准定义安装后仍未成为已发布的 GB 29446 规则")
                return published
            details["rule_source"] = "repository-definition"
            self.warnings.append(
                f"内置标准包内 {GOLDEN_STANDARD_ID} 规则版本为 r{packaged_revision}，"
                f"RS04 Product Golden 需要 r{GOLDEN_RULE_REVISION}；"
                f"本次回放改用仓库定义 {definition_path}，"
                "该 payload 落差见 release/standard-packages/PIN.json 的 known_gap。"
            )
            return resolved

        details["rule_source"] = "standard-package"
        return published

    # -- 5. 记录往返 -------------------------------------------------------

    def _check_record_roundtrip(self) -> tuple[dict[str, Any], list[str]]:
        errors: list[str] = []
        context = self._require_context()
        application = getattr(context, "application", None)
        if application is None:
            raise SelfCheckError("应用上下文未提供 application（ApplicationFacade）")
        case = next(item for item in GOLDEN_CASES if item["case_id"] == ROUNDTRIP_CASE_ID)
        entry = self._golden_cases.get(ROUNDTRIP_CASE_ID)
        details: dict[str, Any] = {
            "case_id": ROUNDTRIP_CASE_ID,
            "evaluation_id": None,
            "restored": False,
            "grade": None,
            "actual_value": None,
            "expected_grade": case["expected_grade"],
            "expected_actual_value": _dec_text(case["expected_e_d"]),
            "rule_revision": None,
            "snapshot_rule_revision": None,
            "record_count": None,
        }
        if entry is None or not entry.get("evaluation_id"):
            raise SelfCheckError(
                "Golden 回放未产生可读回的评价记录，无法校验记录往返", details=details
            )
        evaluation_id = str(entry["evaluation_id"])
        details["evaluation_id"] = evaluation_id
        try:
            loaded = application.get_evaluation(evaluation_id)
        except Exception as exc:
            raise SelfCheckError(
                f"读取评价记录失败：{type(exc).__name__}: {exc}", details=details
            ) from exc
        if loaded is None:
            errors.append(f"仓库未能读回评价记录：{evaluation_id}")
            return details, errors
        request, result, snapshot = loaded
        item = result.results[0]
        details["restored"] = True
        details["grade"] = _grade_text(item.grade)
        details["actual_value"] = _dec_text(item.actual_value)
        details["rule_revision"] = result.rule_revision
        details["snapshot_rule_revision"] = snapshot.rule_revision
        details["standard_id"] = result.standard_id
        details["input_electricity_consumption"] = _dec_text(
            request.inputs["electricity_consumption"].value
            if "electricity_consumption" in request.inputs
            else None
        )
        details["input_raw_coal"] = _dec_text(
            request.inputs["raw_coal_input"].value if "raw_coal_input" in request.inputs else None
        )
        try:
            details["record_count"] = application.count_evaluations()
        except Exception as exc:  # 记录数量只是附加证据
            details["record_count_error"] = f"{type(exc).__name__}: {exc}"
        if details["grade"] != case["expected_grade"]:
            errors.append(
                f"读回等级不符：实际 {details['grade']}，期望 {case['expected_grade']}"
            )
        if details["actual_value"] != details["expected_actual_value"]:
            errors.append(
                f"读回单位产品电耗不符：实际 {details['actual_value']}，"
                f"期望 {details['expected_actual_value']}"
            )
        if details["snapshot_rule_revision"] != GOLDEN_RULE_REVISION:
            errors.append(
                f"记录内标准快照版本为 r{details['snapshot_rule_revision']}，"
                f"期望 r{GOLDEN_RULE_REVISION}"
            )
        if details["input_electricity_consumption"] != _dec_text(case["electricity_consumption"]):
            errors.append(
                "读回输入 E_d 不符：实际 "
                f"{details['input_electricity_consumption']}，"
                f"期望 {_dec_text(case['electricity_consumption'])}"
            )
        if details["input_raw_coal"] != _dec_text(case["raw_coal_input"]):
            errors.append(
                f"读回输入 m 不符：实际 {details['input_raw_coal']}，"
                f"期望 {_dec_text(case['raw_coal_input'])}"
            )
        return details, errors

    # -- 6. Excel 模板 / 导入链路 ------------------------------------------

    def _check_excel_import_chain(self) -> tuple[dict[str, Any], list[str]]:
        errors: list[str] = []
        context = self._require_context()
        application = getattr(context, "application", None)
        if application is None:
            raise SelfCheckError("应用上下文未提供 application（ApplicationFacade）")
        if self.workbook_writer is None:
            raise SelfCheckError("组合根未提供 Excel 模板填写适配器（WorkbookRowWriter）")
        case = next(item for item in GOLDEN_CASES if item["case_id"] == ROUNDTRIP_CASE_ID)
        details: dict[str, Any] = {
            "case_id": case["case_id"],
            "standard_id": GOLDEN_STANDARD_ID,
            "template_path": None,
            "template_sha256": None,
            "sheet": GOLDEN_TEMPLATE_SHEET,
            "valid": False,
            "import_id": None,
            "issues": [],
            "evaluation_id": None,
            "grade": None,
            "actual_value": None,
            "expected_grade": case["expected_grade"],
            "expected_actual_value": _dec_text(case["expected_e_d"]),
            "matches_golden": False,
        }
        workbook_directory = self.data_dir / "imports"
        try:
            workbook_directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise SelfCheckError(
                f"无法在隔离数据目录创建导入目录：{type(exc).__name__}: {exc}", details=details
            ) from exc
        template = workbook_directory / "gb29446-self-check-template.xlsx"
        details["template_path"] = str(template)
        try:
            application.create_template(template, GOLDEN_STANDARD_ID)
        except Exception as exc:
            raise SelfCheckError(
                f"创建 GB29446 导入模板失败：{type(exc).__name__}: {exc}", details=details
            ) from exc
        if not template.is_file():
            raise SelfCheckError(f"模板未生成：{template}", details=details)
        details["template_sha256"] = _sha256_file(template)

        rows = {
            GOLDEN_TEMPLATE_ROWS[FIELD_ORGANIZATION_NAME]: GOLDEN_ORGANIZATION,
            GOLDEN_TEMPLATE_ROWS[FIELD_EVALUATION_DATE]: GOLDEN_EVALUATION_DATE,
            GOLDEN_TEMPLATE_ROWS[FIELD_PERIOD]: PERIOD_FULL_YEAR,
            GOLDEN_TEMPLATE_ROWS[FIELD_COAL_TYPE]: case["coal_type"],
            GOLDEN_TEMPLATE_ROWS[FIELD_WASHING_PROCESS]: case["washing_process"],
            GOLDEN_TEMPLATE_ROWS[FIELD_ELECTRICITY]: case["electricity_consumption"],
            GOLDEN_TEMPLATE_ROWS[FIELD_RAW_COAL]: case["raw_coal_input"],
            GOLDEN_TEMPLATE_ROWS[FIELD_NOTES]: GOLDEN_TEMPLATE_NOTE,
        }
        details["filled_rows"] = sorted(int(row) for row in rows)
        try:
            self.workbook_writer(template, GOLDEN_TEMPLATE_SHEET, rows)
        except Exception as exc:
            raise SelfCheckError(
                f"填写 GB29446 模板失败：{type(exc).__name__}: {exc}", details=details
            ) from exc

        try:
            report = application.validate_workbook(template)
        except Exception as exc:
            raise SelfCheckError(
                f"校验导入工作簿失败：{type(exc).__name__}: {exc}", details=details
            ) from exc
        details["profile_id"] = getattr(report, "profile_id", None)
        details["valid"] = bool(report.valid)
        details["import_id"] = getattr(report, "import_id", None)
        details["issues"] = [_issue_text(issue) for issue in report.issues]
        if not report.valid:
            errors.append("Excel 导入校验未通过：" + "；".join(details["issues"]))
            return details, errors

        try:
            result = application.evaluate_workbook(report.import_id)
        except Exception as exc:
            raise SelfCheckError(
                f"Excel 导入评价失败：{type(exc).__name__}: {exc}", details=details
            ) from exc
        item = result.results[0]
        details["evaluation_id"] = result.evaluation_id
        details["grade"] = _grade_text(item.grade)
        details["actual_value"] = _dec_text(item.actual_value)
        details["process_factor"] = _dec_text(item.display_values.get("process_factor"))
        details["matches_golden"] = (
            details["grade"] == case["expected_grade"]
            and details["actual_value"] == details["expected_actual_value"]
        )
        if details["grade"] != case["expected_grade"]:
            errors.append(
                f"Excel 链路等级不符：实际 {details['grade']}，期望 {case['expected_grade']}"
            )
        if details["actual_value"] != details["expected_actual_value"]:
            errors.append(
                f"Excel 链路单位产品电耗不符：实际 {details['actual_value']}，"
                f"期望 {details['expected_actual_value']}"
            )
        return details, errors


def _build_golden_request(
    standard: StandardDefinition, product_id: str, case: Mapping[str, Any]
) -> EvaluationRequest:
    inputs: dict[str, InputValue] = {
        "washing_process": InputValue(value=case["washing_process"]),
        "single_coal_single_process": InputValue(value=case["single_coal_single_process"]),
        "electricity_consumption": InputValue(value=case["electricity_consumption"], unit="kW·h"),
        "raw_coal_input": InputValue(value=case["raw_coal_input"], unit="t"),
    }
    if case.get("enterprise_status"):
        inputs["enterprise_status"] = InputValue(value=case["enterprise_status"])
    return EvaluationRequest(
        evaluation_date=GOLDEN_EVALUATION_DATE,
        standard_id=standard.id,
        product_id=product_id,
        selection_mode=StandardSelectionMode.CURRENT,
        input_mode=InputMode.DETAIL,
        inputs=inputs,
        organization_name=GOLDEN_ORGANIZATION,
        notes=encode_period_notes(PERIOD_FULL_YEAR, "", GOLDEN_NOTE),
    )


def run_self_check(
    *,
    data_dir: Path,
    context_factory: ContextFactory | None,
    workbook_writer: WorkbookRowWriter | None,
    package_path: Path | None = None,
    public_key_path: Path | None = None,
    definition_path: Path | None = None,
) -> dict[str, Any]:
    """执行全部检查并返回可直接 ``json.dumps`` 的报告。

    本函数**不抛出**业务异常：任何失败都会落到报告的某个 ``checks`` 项里，调用方
    只需读取 ``report["exit_code"]``（``0`` 全部通过，``1`` 有失败项）。

    参数：

    ``data_dir``
        隔离数据目录；数据库、日志、备份、导入工作簿都写在这里，绝不触碰
        ``%LOCALAPPDATA%``。
    ``context_factory``
        组合根注入的真实应用上下文工厂（``uebench.bootstrap.create_context``）。
    ``workbook_writer``
        组合根注入的 Excel 单元格写入适配器（``openpyxl``）。
    ``package_path`` / ``public_key_path`` / ``definition_path``
        可选覆盖；默认自动定位内置标准包、内置公钥与仓库定义，供测试与诊断使用。
    """
    runner = _Runner(
        data_dir=data_dir,
        context_factory=context_factory,
        workbook_writer=workbook_writer,
        package_path=package_path,
        public_key_path=public_key_path,
        definition_path=definition_path,
    )
    return runner.run()
