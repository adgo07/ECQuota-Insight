"""构造「0.1.0 → 0.2.0 升级校验」使用的 **合成** 旧版数据目录。

为什么存在
----------
ECQ-RS05 §10 要求证明「真实的 0.1.0 数据目录可以干净升级到 0.2.0 候选版」。
真实的用户业务数据库 **不得** 进入仓库，也不得作为二进制夹具提交，因此本工具
按 0.1.0 的 Alembic revision 现场生成一个结构等价、内容 **全部合成** 的数据目录。
测试在用完即弃的 ``tmp_path`` 中调用本工具，仓库里只保留这段生成脚本。

合成性质（重要，请勿误读为真实用户数据）
----------------------------------------
* 机构名称固定为 ``合成测试企业-0.1.0``，项目名固定为 ``合成测试项目-0.1.0``；
* 全部业务数字（煤种 / 选煤工艺 / E_d / m）都是为覆盖四个等级边界而人工选取的，
  不代表任何真实企业的生产数据；
* 标准规则载荷是仓库当前 ``data/definitions/gb-29446-2019.json`` 的 **结构替身**
  ：``rule_revision`` 被固定为 1，代表 0.1.0 时代的第 1 版规则。真正的 0.1.0
  规则载荷并不随本夹具分发；本夹具只用于证明「schema 迁移 + 历史记录仍可用」，
  不用于证明任何 0.1.0 时期的业务结论。
* 不含任何真实企业、真实项目、真实原始数据或个人信息。

``--revision`` 与真实的 0.1.0 发布物
------------------------------------
本地留存的 0.1.0 证据里存在两种 head，本工具因此把 revision 参数化：

* ``0002``（默认）—— 早期 0.1.0 便携版 ``dist/UEBench-0.1.0-win-x64.zip``
  （2026-08-30）的 ``_internal/migrations/versions`` 只含 ``0001``/``0002``，
  因此真实 0.1.0 数据目录停在 ``0002``。这是唯一会产生真实 schema 变更的路径。
* ``0003`` —— 2026-09-09 那版 0.1.0 发布物（``dist/release/`` 与安装包）已带
  ``0003``，其数据目录在启动时已是 head。

用法
----
    python tools/build_legacy_0_1_0_fixture.py --output-dir <dir> [--revision 0002]

    # 供测试导入
    from tools.build_legacy_0_1_0_fixture import build_fixture
    manifest = build_fixture(tmp_path / "legacy", revision="0002")
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:  # ``python tools/...`` run outside pytest
    sys.path.insert(0, str(REPO_ROOT / "src"))

# Importable both as ``python tools/build_legacy_0_1_0_fixture.py`` and as
# ``tools.build_legacy_0_1_0_fixture`` from a test module.
try:  # noqa: E402
    from release_version import ensure_utf8_console
except ModuleNotFoundError:  # pragma: no cover - package-import style
    from tools.release_version import ensure_utf8_console

from uebench.domain.engine import EvaluationEngine  # noqa: E402
from uebench.domain.models import (  # noqa: E402
    EvaluationRequest,
    InputMode,
    InputValue,
    StandardDefinition,
    StandardSelectionMode,
)
from uebench.domain.numeric import ECQUOTA_DECIMAL_FULL_VALUE_V1  # noqa: E402


MIGRATIONS_DIR = REPO_ROOT / "migrations"
DEFINITION_PATH = REPO_ROOT / "data" / "definitions" / "gb-29446-2019.json"

DATABASE_NAME = "uebench.sqlite3"
MANIFEST_NAME = "legacy-fixture-manifest.json"

DEFAULT_REVISION = "0002"
SUPPORTED_REVISIONS = ("0001", "0002", "0003")
DEFAULT_ORGANIZATION = "合成测试企业-0.1.0"
SYNTHETIC_PROJECT = "合成测试项目-0.1.0"

#: 0.1.0 只发布过第 1 版 GB 29446 规则；``0003`` 迁移正是为了引入版本身份。
LEGACY_RULE_REVISION = 1

LEGACY_EVALUATION_DATE = date(2024, 5, 20)
LEGACY_INSTALLED_AT = datetime(2024, 3, 1, 8, 0, 0, tzinfo=timezone.utc)
LEGACY_EVALUATED_AT = datetime(2024, 5, 20, 9, 30, 0, tzinfo=timezone.utc)

SYNTHETIC_PACKAGE_ID = "synthetic-legacy-package-0.1.0"

#: 固定 namespace，使 evaluation_id / import_id 在每次生成时完全可复现。
_FIXTURE_NAMESPACE = uuid.UUID("6f1b0d2a-0f5a-4c5e-9a5b-2f7c3d41e000")


@dataclass(frozen=True)
class LegacyCase:
    """One synthetic evaluation record.

    ``expected_grade`` is asserted against the real engine output while building,
    so the fixture cannot silently drift into a different grade.
    """

    key: str
    coal_type: str
    washing_process: str
    electricity_consumption: str
    raw_coal_input: str
    expected_grade: str


#: 四条记录覆盖 GB 29446 的四个等级结论（1/2/3 级 + 超出 3 级）。
LEGACY_CASES: tuple[LegacyCase, ...] = (
    LegacyCase("legacy-coking-l2", "炼焦煤", "跳汰", "350", "63", "LEVEL_2"),
    LegacyCase("legacy-coking-l3", "炼焦煤", "重介", "212.5", "28", "LEVEL_3"),
    LegacyCase("legacy-power-l1", "动力煤", "重介", "200", "100", "LEVEL_1"),
    LegacyCase("legacy-coking-not-qualified", "炼焦煤", "重介", "500", "50", "NOT_QUALIFIED"),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def migrations_config(database: Path) -> Config:
    """An Alembic ``Config`` pointing at this repository's migration scripts."""

    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{Path(database).as_posix()}")
    return config


def deterministic_id(key: str) -> str:
    return str(uuid.uuid5(_FIXTURE_NAMESPACE, key))


def synthetic_sha256(label: str) -> str:
    """A real digest of a synthetic label.

    The value is a genuine SHA-256, but its pre-image is a synthetic marker, so
    it can never be confused with a real source/package hash.
    """

    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _sqlite_timestamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S.%f")


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _insert_available(
    connection: sqlite3.Connection,
    table: str,
    values: dict[str, object],
) -> None:
    """INSERT only the columns this revision actually provides.

    ``0001``/``0002`` lack ``standard_family_id`` / ``rule_revision`` and
    ``0001`` additionally lacks the lifecycle columns, so a fixed column list
    cannot be used across the revisions this tool must reproduce.
    """

    available = _table_columns(connection, table)
    selected = {name: value for name, value in values.items() if name in available}
    if not selected:
        raise RuntimeError(f"{table} 在目标 revision 下没有任何可写入的列")
    placeholders = ", ".join("?" for _ in selected)
    connection.execute(
        f"INSERT INTO {table} ({', '.join(selected)}) VALUES ({placeholders})",
        list(selected.values()),
    )


# ---------------------------------------------------------------------------
# Fixture parts
# ---------------------------------------------------------------------------


def legacy_standard_definition() -> StandardDefinition:
    """The 0.1.0-era structural stand-in for GB 29446-2019.

    Today's repository definition with ``rule_revision`` forced to 1.  The
    genuine 0.1.0 rule payload is not part of this fixture's provenance; only the
    *shape* matters for proving that stored snapshots survive the migration.
    """

    definition = StandardDefinition.model_validate_json(
        DEFINITION_PATH.read_text(encoding="utf-8")
    )
    return definition.model_copy(update={"rule_revision": LEGACY_RULE_REVISION})


def _create_schema_at(database: Path, revision: str) -> None:
    command.upgrade(migrations_config(database), revision)
    with closing(sqlite3.connect(database)) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    applied = None if row is None else str(row[0])
    if applied != revision:
        raise RuntimeError(f"夹具创建失败：期望 revision {revision}，实际 {applied!r}")


def _build_standard_row(definition: StandardDefinition) -> dict[str, object]:
    return {
        "standard_id": definition.id,
        "number": definition.number,
        "title": definition.title,
        "version": definition.version,
        "standard_family_id": definition.family_id,
        "rule_revision": definition.rule_revision,
        "status": definition.publication_status.value,
        "publication_date": definition.publication_date.isoformat(),
        "effective_date": definition.effective_date.isoformat(),
        "source_file": definition.source_file,
        "source_sha256": definition.source_sha256.lower(),
        "lifecycle_status": definition.lifecycle_status.value,
        "obsolete_date": definition.obsolete_date,
        "replaced_by_json": json.dumps(definition.replaced_by, ensure_ascii=False),
        "supersedes_json": json.dumps(definition.supersedes, ensure_ascii=False),
        "package_id": SYNTHETIC_PACKAGE_ID,
        "definition_json": definition.model_dump_json(),
        "installed_at": _sqlite_timestamp(LEGACY_INSTALLED_AT),
    }


def _build_request(
    definition: StandardDefinition,
    case: LegacyCase,
    organization: str,
) -> EvaluationRequest:
    product = next(
        item for item in definition.products if item.selection_values["coal_type"] == case.coal_type
    )
    return EvaluationRequest(
        evaluation_date=LEGACY_EVALUATION_DATE,
        standard_id=definition.id,
        product_id=product.id,
        selection_mode=StandardSelectionMode.CURRENT,
        input_mode=InputMode.DETAIL,
        inputs={
            "washing_process": InputValue(value=case.washing_process),
            "single_coal_single_process": InputValue(value="是"),
            "electricity_consumption": InputValue(
                value=case.electricity_consumption, unit="kW·h"
            ),
            "raw_coal_input": InputValue(value=case.raw_coal_input, unit="t"),
        },
        organization_name=organization,
        project_name=SYNTHETIC_PROJECT,
        notes=f"核算周期：全年\n备注：合成升级夹具（{case.key}）",
    )


def _audit_details(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------


def build_fixture(
    output_dir: Path,
    *,
    revision: str = DEFAULT_REVISION,
    organization: str = DEFAULT_ORGANIZATION,
) -> dict[str, object]:
    """Generate a synthetic 0.1.0 data directory and return its manifest.

    The directory is created if missing; only this tool's own database and
    manifest files are replaced.  Nothing outside ``output_dir`` is touched.
    """

    if revision not in SUPPORTED_REVISIONS:
        raise ValueError(
            f"不支持的 revision {revision!r}；可选：{', '.join(SUPPORTED_REVISIONS)}"
        )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    database = output_dir / DATABASE_NAME
    for suffix in ("", "-wal", "-shm"):
        stale = Path(f"{database}{suffix}")
        if stale.exists():
            stale.unlink()

    _create_schema_at(database, revision)

    definition = legacy_standard_definition()
    engine = EvaluationEngine(ECQUOTA_DECIMAL_FULL_VALUE_V1)
    evaluations: list[dict[str, object]] = []

    with closing(sqlite3.connect(database)) as connection:
        # A genuine 0.1.0 install ran with the same WAL pragmas as the app.
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")

        _insert_available(connection, "standards", _build_standard_row(definition))
        connection.execute(
            "INSERT INTO audit_log (created_at, actor, action, entity_type, entity_id, details_json)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                _sqlite_timestamp(LEGACY_INSTALLED_AT),
                "LocalUser",
                "STANDARD_INSTALL",
                "standard",
                f"{definition.id}:{definition.version}:r{definition.rule_revision}",
                _audit_details({"number": definition.number, "package_id": SYNTHETIC_PACKAGE_ID}),
            ),
        )
        _insert_available(
            connection,
            "standard_packages",
            {
                "package_id": SYNTHETIC_PACKAGE_ID,
                "schema_version": "1.0",
                "issued_at": _sqlite_timestamp(LEGACY_INSTALLED_AT),
                "installed_at": _sqlite_timestamp(LEGACY_INSTALLED_AT),
                "manifest_json": json.dumps(
                    {
                        "package_id": SYNTHETIC_PACKAGE_ID,
                        "synthetic": True,
                        "note": "合成升级夹具：非真实发布的标准包",
                        "standard_count": 1,
                    },
                    ensure_ascii=False,
                ),
                "package_sha256": synthetic_sha256(f"package:{SYNTHETIC_PACKAGE_ID}"),
            },
        )

        for case in LEGACY_CASES:
            request = _build_request(definition, case, organization)
            result = engine.evaluate(definition, request)
            grade = str(result.results[0].grade)
            if grade != case.expected_grade:
                raise RuntimeError(
                    f"夹具自检失败：{case.key} 期望等级 {case.expected_grade}，引擎实际 {grade}"
                )
            evaluation_id = deterministic_id(case.key)
            result = result.model_copy(
                update={"evaluation_id": evaluation_id, "evaluated_at": LEGACY_EVALUATED_AT}
            )
            indicator = result.results[0]
            _insert_available(
                connection,
                "evaluations",
                {
                    "evaluation_id": evaluation_id,
                    "created_at": _sqlite_timestamp(LEGACY_EVALUATED_AT),
                    "evaluation_date": LEGACY_EVALUATION_DATE.isoformat(),
                    "standard_id": result.standard_id,
                    "standard_number": result.standard_number,
                    "product_id": result.product_id,
                    "organization_name": organization,
                    "project_name": SYNTHETIC_PROJECT,
                    "request_json": request.model_dump_json(),
                    "result_json": result.model_dump_json(),
                    "rule_snapshot_json": definition.model_dump_json(),
                    "deleted_at": None,
                },
            )
            connection.execute(
                "INSERT INTO audit_log (created_at, actor, action, entity_type, entity_id, details_json)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    _sqlite_timestamp(LEGACY_EVALUATED_AT),
                    "LocalUser",
                    "EVALUATION_CREATE",
                    "evaluation",
                    evaluation_id,
                    _audit_details(
                        {
                            "standard_number": result.standard_number,
                            "product_id": result.product_id,
                        }
                    ),
                ),
            )
            evaluations.append(
                {
                    "case_key": case.key,
                    "evaluation_id": evaluation_id,
                    "evaluation_date": LEGACY_EVALUATION_DATE.isoformat(),
                    "standard_id": result.standard_id,
                    "standard_number": result.standard_number,
                    "standard_version": result.standard_version,
                    "rule_revision": result.rule_revision,
                    "product_id": result.product_id,
                    "organization_name": organization,
                    "project_name": SYNTHETIC_PROJECT,
                    "python_grade": grade,
                    "indicator_id": indicator.indicator_id,
                    "actual_value": format(indicator.actual_value, "f"),
                    "unit": indicator.unit,
                    "process_factor": format(indicator.display_values["process_factor"], "f"),
                    "base_thresholds": {
                        key: format(value, "f")
                        for key, value in sorted(indicator.base_thresholds.items())
                    },
                    "corrected_thresholds": {
                        key: format(value, "f")
                        for key, value in sorted(indicator.corrected_thresholds.items())
                    },
                    "inputs": {
                        "coal_type": case.coal_type,
                        "washing_process": case.washing_process,
                        "electricity_consumption": case.electricity_consumption,
                        "raw_coal_input": case.raw_coal_input,
                    },
                    "inputs_by_key": {
                        key: value.value for key, value in sorted(request.inputs.items())
                    },
                }
            )

        _insert_available(
            connection,
            "import_batches",
            {
                "import_id": deterministic_id("legacy-import-batch"),
                "created_at": _sqlite_timestamp(LEGACY_EVALUATED_AT),
                "source_file": "合成导入-0.1.0.xlsx",
                "source_sha256": synthetic_sha256("import:synthetic-legacy-0.1.0"),
                "status": "evaluated",
                "payload_json": json.dumps(
                    {"synthetic": True, "rows": len(LEGACY_CASES)}, ensure_ascii=False
                ),
                "validation_json": json.dumps({"valid": True, "issues": []}, ensure_ascii=False),
            },
        )
        connection.commit()
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    manifest: dict[str, object] = {
        "fixture_kind": "synthetic-legacy-0.1.0-data-directory",
        "fixture_version": 1,
        "synthetic": True,
        "contains_real_user_data": False,
        "revision": revision,
        "database": DATABASE_NAME,
        "journal_mode": journal_mode,
        "organization_name": organization,
        "project_name": SYNTHETIC_PROJECT,
        "legacy_rule_revision": definition.rule_revision,
        "legacy_definition_basis": (
            "data/definitions/gb-29446-2019.json 的结构替身（rule_revision 固定为 1）；"
            "真正的 0.1.0 规则载荷不随本夹具分发"
        ),
        "standard_id": definition.id,
        "standard_number": definition.number,
        "standard_version": definition.version,
        "evaluations": evaluations,
        "record_count": len(evaluations),
        "database_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "database_size": database.stat().st_size,
    }
    (output_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_console()
    parser = argparse.ArgumentParser(
        description="生成 0.1.0 → 0.2.0 升级校验用的合成旧版数据目录（不含任何真实用户数据）",
    )
    parser.add_argument("--output-dir", required=True, type=Path, help="数据目录输出位置")
    parser.add_argument(
        "--revision",
        default=DEFAULT_REVISION,
        choices=SUPPORTED_REVISIONS,
        help=(
            "生成时的 0.1.0 Alembic revision；0002 = 早期 0.1.0 便携版 head（默认），"
            "0003 = 2026-09-09 那版 0.1.0 发布物 head"
        ),
    )
    parser.add_argument("--organization", default=DEFAULT_ORGANIZATION, help="合成机构名称")
    parser.add_argument("--json", action="store_true", help="把 manifest 打印到 stdout")
    args = parser.parse_args(argv)

    manifest = build_fixture(
        args.output_dir, revision=args.revision, organization=args.organization
    )
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print(
            f"已生成合成 0.1.0 数据目录：{args.output_dir}"
            f"（revision={manifest['revision']}，记录数={manifest['record_count']}）"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
