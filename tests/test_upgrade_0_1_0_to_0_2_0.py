"""ECQ-RS05 §10 — 0.1.0 → 0.2.0 升级验证。

承诺范围
--------
只承诺 ``0.1.0 → 0.2.0`` 一条路径：

    0.1.0 数据目录
      → 构建测试业务数据
      → 0.2.0 升级（Alembic 迁移）
      → 旧记录仍在
      → 历史详情仍可查看
      → 新的 GB29446 评价可用

真实 0.1.0 证据（只读，未修改、未提交）
---------------------------------------
本地 ``dist/`` 下留存的 0.1.0 发布物里存在 **两种** schema head，因此两条真实 head
都被验证。注意 ``dist/`` 正被并发的发布工作流重建，下面的校验时间戳与 SHA256 是
本模块结论所依据的快照：

* ``0002`` —— ``dist/UEBench-0.1.0-win-x64.zip``（342,077,067 字节，
  SHA256 ``5FDAE95B…D30A``，mtime 2026-08-30 17:19:55，校验期间未变化）的
  ``_internal/migrations/versions`` 只含 ``0001``/``0002``。这是早期 0.1.0
  便携版，会产生真实的 schema 变更（0002 → 0003）。
* ``0003`` —— 校验开始时 ``dist/release/UEBench-0.1.0-win-x64.zip``
  （176,480,046 字节，SHA256 ``424AF9E4…85B4``，mtime 2026-09-09 10:10:03）及其
  解包目录 ``dist/UEBench``（``UEBench.exe`` FileVersion/ProductVersion = ``0.1.0``）
  已带 ``0003``。该 ZIP 已在本会话期间被并发发布工作流覆盖（现为
  342,682,363 字节、SHA256 ``EB78FBF8…FC77``、只含 ``0001_initial.py``），
  因此本模块刻意不依赖任何单一残留发布物。

``0002 → 0003`` 是唯一会产生真实迁移的路径，是本模块的主要验证对象；
``0003`` 那条用于证明「已是 head 的 0.1.0 数据目录」重复启动同样不丢数据。

数据来源（无真实业务数据）
--------------------------
夹具由 ``tools/build_legacy_0_1_0_fixture.py`` 在 ``tmp_path`` 中 **现场生成**，
仓库里不提交任何 ``.sqlite3`` / ``.uebackup`` 二进制。机构名固定为
``合成测试企业-0.1.0``，规则载荷是当前 GB29446 definition 的结构替身
（``rule_revision`` 固定为 1）。详见该脚本 docstring。
"""

from __future__ import annotations

import json
import sqlite3
import zipfile
from contextlib import closing
from datetime import date
from decimal import Decimal
from pathlib import Path

from alembic.script import ScriptDirectory

from tools.build_legacy_0_1_0_fixture import (
    DEFAULT_ORGANIZATION,
    SYNTHETIC_PROJECT,
    build_fixture,
    migrations_config,
)
from uebench.bootstrap import create_context
from uebench.domain.models import (
    EvaluationRequest,
    InputMode,
    InputValue,
    StandardDefinition,
    StandardSelectionMode,
)

ROOT = Path(__file__).resolve().parents[1]

#: 0.2.0 候选版的 Alembic head。
HEAD = "0003"

#: 早期 0.1.0 便携版的真实 head（只含 0001/0002）。
LEGACY_PORTABLE_HEAD = "0002"

#: 2026-09-09 那版 0.1.0 发布物的真实 head（已含 0003）。
LEGACY_RELEASE_HEAD = "0003"

GB29446_ID = "gb-29446-2019"
GB29446_DEFINITION = ROOT / "data" / "definitions" / "gb-29446-2019.json"
GB29446_GOLDEN = ROOT / "tests" / "golden" / "gb29446_product_golden_v1.json"
GOLDEN_CASE_ID = "gb29446-coking-grade2-exact-l2"

#: 与 Golden 一致的正式评价日期。
NEW_EVALUATION_DATE = date(2026, 6, 1)

MANAGED_TABLES = ("standards", "evaluations", "audit_log", "standard_packages", "import_batches")

#: 仓库里允许出现这些开发产物的目录；它们不是交付物，也不是本模块的承诺范围。
#: 夹具与验证只承诺「``tools/``/``tests/``/``src/``/``migrations/``/``packaging/``
#: 里不提交数据库二进制」。
_SOURCE_AREAS = ("tools", "tests", "src", "migrations", "packaging", "data")


# ---------------------------------------------------------------------------
# Raw-sqlite helpers — the pre-upgrade state is read without the application,
# so a passing assertion cannot be explained by application-side repair.
# ---------------------------------------------------------------------------


def revision_of(database: Path) -> str | None:
    with closing(sqlite3.connect(database)) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    return None if row is None else str(row[0])


def columns_of(database: Path, table: str) -> set[str]:
    with closing(sqlite3.connect(database)) as connection:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def table_count(database: Path, table: str) -> int:
    with closing(sqlite3.connect(database)) as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def evaluation_rows(database: Path) -> dict[str, dict[str, object]]:
    """Every stored evaluation, keyed by id, including its raw JSON payloads."""

    statement = (
        "SELECT evaluation_id, evaluation_date, standard_id, standard_number, product_id,"
        " organization_name, project_name, request_json, result_json, rule_snapshot_json,"
        " deleted_at FROM evaluations"
    )
    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(statement).fetchall()
    return {str(row["evaluation_id"]): dict(row) for row in rows}


def standard_rows(database: Path) -> list[dict[str, object]]:
    available = columns_of(database, "standards")
    selected = [
        name
        for name in ("standard_id", "number", "version", "standard_family_id", "rule_revision", "status")
        if name in available
    ]
    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(f"SELECT {', '.join(selected)} FROM standards").fetchall()
    return [dict(row) for row in rows]


def journal_mode_of(database: Path) -> str:
    with closing(sqlite3.connect(database)) as connection:
        return str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()


def managed_table_counters(database: Path) -> dict[str, int]:
    return {table: table_count(database, table) for table in MANAGED_TABLES}


#: ``audit_log`` 是只追加表：迁移本身可以合法地 **新增** 行
#: （``BackupService.create`` 会为迁移前快照写 ``BACKUP_CREATE``）。
#: 其余四张受管表必须逐行不变。
APPEND_ONLY_TABLES = ("audit_log",)


def assert_no_rows_lost(database: Path, before: dict[str, int]) -> dict[str, int]:
    after = managed_table_counters(database)
    for table, count in before.items():
        if table in APPEND_ONLY_TABLES:
            assert after[table] >= count, f"{table} 行数减少：{count} → {after[table]}"
        else:
            assert after[table] == count, f"{table} 行数变化：{count} → {after[table]}"
    return after


def audit_keys(database: Path) -> set[tuple[str, str, str, str | None]]:
    """Identity of every audit row, so a subset check can prove nothing was lost."""

    with closing(sqlite3.connect(database)) as connection:
        rows = connection.execute(
            "SELECT created_at, actor, action, entity_type, entity_id FROM audit_log"
        ).fetchall()
    return {
        (str(row[0]), str(row[1]), str(row[2]), str(row[3]), None if row[4] is None else str(row[4]))
        for row in rows
    }


def backup_snapshots(paths) -> list[Path]:
    """Any ``*.uebackup`` under ``backups/`` — the exact name is not assumed."""

    return sorted(item for item in paths.backups.iterdir() if item.suffix == ".uebackup")


def committed_database_binaries() -> list[Path]:
    """Database/backup binaries inside the source areas this module owns.

    ``work/`` and ``dist/`` are deliberately excluded: they hold local run
    artifacts and the read-only 0.1.0 release evidence.
    """

    found: list[Path] = []
    for area in _SOURCE_AREAS:
        directory = ROOT / area
        if not directory.is_dir():
            continue
        for pattern in ("*.sqlite3", "*.uebackup"):
            found.extend(directory.rglob(pattern))
    return sorted(found)


# ---------------------------------------------------------------------------
# Business projection helpers
# ---------------------------------------------------------------------------


def decimal_text(value: object) -> str | None:
    if value is None:
        return None
    return format(Decimal(str(value)).normalize(), "f")


def restored_business_fields(
    request: EvaluationRequest, result, snapshot: StandardDefinition
) -> dict[str, object]:
    indicator = result.results[0]
    return {
        "standard_id": result.standard_id,
        "standard_number": result.standard_number,
        "standard_version": result.standard_version,
        "rule_revision": result.rule_revision,
        "product_id": result.product_id,
        "organization_name": request.organization_name,
        "project_name": request.project_name,
        "indicator_id": indicator.indicator_id,
        "unit": indicator.unit,
        "grade": str(indicator.grade),
        "actual_value": decimal_text(indicator.actual_value),
        "process_factor": decimal_text(indicator.display_values["process_factor"]),
        "base_thresholds": {
            key: decimal_text(value) for key, value in sorted(indicator.base_thresholds.items())
        },
        "corrected_thresholds": {
            key: decimal_text(value)
            for key, value in sorted(indicator.corrected_thresholds.items())
        },
        "inputs": {key: value.value for key, value in sorted(request.inputs.items())},
        "snapshot_rule_revision": snapshot.rule_revision,
        "snapshot_standard_id": snapshot.id,
    }


def manifest_business_fields(entry: dict[str, object]) -> dict[str, object]:
    """The same projection, built from the builder's own manifest."""

    return {
        "standard_id": entry["standard_id"],
        "standard_number": entry["standard_number"],
        "standard_version": entry["standard_version"],
        "rule_revision": entry["rule_revision"],
        "product_id": entry["product_id"],
        "organization_name": entry["organization_name"],
        "project_name": entry["project_name"],
        "indicator_id": entry["indicator_id"],
        "unit": entry["unit"],
        "grade": entry["python_grade"],
        "actual_value": decimal_text(entry["actual_value"]),
        "process_factor": decimal_text(entry["process_factor"]),
        "base_thresholds": {
            key: decimal_text(value) for key, value in sorted(entry["base_thresholds"].items())
        },
        "corrected_thresholds": {
            key: decimal_text(value)
            for key, value in sorted(entry["corrected_thresholds"].items())
        },
        "inputs": entry["inputs_by_key"],
        "snapshot_rule_revision": entry["rule_revision"],
        "snapshot_standard_id": entry["standard_id"],
    }


def build_legacy(root: Path, revision: str = LEGACY_PORTABLE_HEAD) -> tuple[Path, dict]:
    """Generate the synthetic 0.1.0 fixture and return ``(data_dir, manifest)``."""

    manifest = build_fixture(root, revision=revision)
    recorded = json.loads((root / "legacy-fixture-manifest.json").read_text(encoding="utf-8"))
    assert recorded == manifest
    return root, manifest


def golden_case(case_id: str = GOLDEN_CASE_ID) -> tuple[dict, dict]:
    golden = json.loads(GB29446_GOLDEN.read_text(encoding="utf-8"))
    return golden, next(case for case in golden["cases"] if case["case_id"] == case_id)


def current_gb29446() -> StandardDefinition:
    return StandardDefinition.model_validate_json(
        GB29446_DEFINITION.read_text(encoding="utf-8")
    )


def golden_request(standard: StandardDefinition, case: dict) -> EvaluationRequest:
    inputs = case["inputs"]
    product = next(
        item
        for item in standard.products
        if item.selection_values["coal_type"] == inputs["coal_type"]
    )
    return EvaluationRequest(
        evaluation_date=NEW_EVALUATION_DATE,
        standard_id=standard.id,
        product_id=product.id,
        selection_mode=StandardSelectionMode.CURRENT,
        input_mode=InputMode.DETAIL,
        inputs={
            "washing_process": InputValue(value=inputs["washing_process"]),
            "electricity_consumption": InputValue(
                value=str(inputs["electricity_consumption"]), unit="kW·h"
            ),
            "raw_coal_input": InputValue(value=str(inputs["raw_coal_input"]), unit="t"),
        },
        organization_name=DEFAULT_ORGANIZATION,
        notes="核算周期：全年\n备注：升级后新评价",
    )


# ===========================================================================
# 1. 夹具本身：确实是 0.1.0 的 schema，且确实不含真实用户数据
# ===========================================================================


def test_legacy_fixture_is_a_synthetic_0_1_0_data_directory(tmp_path: Path) -> None:
    before_binaries = committed_database_binaries()
    root, manifest = build_legacy(tmp_path / "legacy-0.1.0")
    database = root / "uebench.sqlite3"

    assert revision_of(database) == LEGACY_PORTABLE_HEAD
    # 0003 才引入版本身份；缺少这两列证明这是货真价实的 0.1.0 schema。
    standards_columns = columns_of(database, "standards")
    assert "standard_family_id" not in standards_columns
    assert "rule_revision" not in standards_columns
    # 真实 0.1.0 安装同样运行在 WAL 下。
    assert journal_mode_of(database) == "wal"

    assert manifest["synthetic"] is True
    assert manifest["contains_real_user_data"] is False
    assert manifest["revision"] == LEGACY_PORTABLE_HEAD
    assert manifest["record_count"] == len(manifest["evaluations"]) == 4

    rows = evaluation_rows(database)
    assert set(rows) == {entry["evaluation_id"] for entry in manifest["evaluations"]}
    assert {str(row["organization_name"]) for row in rows.values()} == {DEFAULT_ORGANIZATION}
    assert {str(row["project_name"]) for row in rows.values()} == {SYNTHETIC_PROJECT}

    # 四条合成记录覆盖 GB29446 的全部四个等级结论。
    grades = {
        str(json.loads(str(row["result_json"]))["results"][0]["grade"]) for row in rows.values()
    }
    assert grades == {"LEVEL_1", "LEVEL_2", "LEVEL_3", "NOT_QUALIFIED"}

    # 五张受管表都有数据，``initialize`` 的 stamp/接管分支才会被真实覆盖。
    assert managed_table_counters(database) == {
        "standards": 1,
        "evaluations": 4,
        "audit_log": 5,
        "standard_packages": 1,
        "import_batches": 1,
    }

    # 夹具只存在于 tmp_path；仓库源码区不提交任何数据库/备份二进制；
    # 生成过程也只写 output_dir 内部的两个文件。
    assert root.is_relative_to(tmp_path)
    assert committed_database_binaries() == before_binaries == []
    assert sorted(item.name for item in root.iterdir()) == [
        "legacy-fixture-manifest.json",
        "uebench.sqlite3",
    ]


def test_legacy_fixture_supports_both_recorded_0_1_0_heads(tmp_path: Path) -> None:
    """两种真实 0.1.0 head 都能生成夹具（0002 早期便携版 / 0003 发布物）。"""

    portable, _ = build_legacy(tmp_path / "portable", LEGACY_PORTABLE_HEAD)
    release, _ = build_legacy(tmp_path / "release", LEGACY_RELEASE_HEAD)

    assert revision_of(portable / "uebench.sqlite3") == LEGACY_PORTABLE_HEAD
    assert revision_of(release / "uebench.sqlite3") == LEGACY_RELEASE_HEAD
    assert evaluation_rows(portable / "uebench.sqlite3").keys() == evaluation_rows(
        release / "uebench.sqlite3"
    ).keys()


# ===========================================================================
# 2. 0.1.0 → 0.2.0：迁移到 head，记录一条不少
# ===========================================================================


def test_0_1_0_data_directory_upgrades_to_head_without_losing_records(
    tmp_path: Path,
) -> None:
    root, manifest = build_legacy(tmp_path / "legacy-0.1.0")
    database = root / "uebench.sqlite3"

    pre_revision = revision_of(database)
    pre_rows = evaluation_rows(database)
    pre_standards = standard_rows(database)
    pre_counters = managed_table_counters(database)
    pre_audit = audit_keys(database)
    assert pre_revision == LEGACY_PORTABLE_HEAD
    assert len(pre_rows) == 4

    context = create_context(root)
    try:
        assert context.database.current_revision() == HEAD
    finally:
        context.database.dispose()

    # 用裸 sqlite3 复核，避免把应用侧读取当作迁移成功的证据。
    assert revision_of(database) == HEAD
    assert "standard_family_id" in columns_of(database, "standards")
    assert "rule_revision" in columns_of(database, "standards")

    post_rows = evaluation_rows(database)
    # 主键集合与每一条业务载荷都必须逐字节保持不变。
    assert set(post_rows) == set(pre_rows)
    for evaluation_id, before in pre_rows.items():
        after = post_rows[evaluation_id]
        assert after["deleted_at"] is None
        for field in before:
            assert after[field] == before[field], f"{evaluation_id} 的 {field} 发生变化"

    # 0003 迁移会回填 standard_family_id / rule_revision，其余列保持原值。
    assert len(standard_rows(database)) == len(pre_standards) == 1
    migrated_standard = standard_rows(database)[0]
    assert migrated_standard["standard_id"] == GB29446_ID
    assert migrated_standard["standard_family_id"] == "GB 29446"
    assert migrated_standard["rule_revision"] == 1
    assert migrated_standard["status"] == "published"

    # 其它四张受管表也不得丢行；audit_log 只允许追加。
    assert_no_rows_lost(database, pre_counters)
    assert pre_audit <= audit_keys(database)
    assert manifest["record_count"] == len(post_rows)


# ===========================================================================
# 3. 历史详情仍可查看
# ===========================================================================


def test_history_detail_remains_viewable_after_upgrade(tmp_path: Path) -> None:
    root, manifest = build_legacy(tmp_path / "legacy-0.1.0")
    pre_rows = evaluation_rows(root / "uebench.sqlite3")

    context = create_context(root)
    try:
        assert context.application.count_evaluations() == len(pre_rows) == 4
        for entry in manifest["evaluations"]:
            evaluation_id = str(entry["evaluation_id"])
            loaded = context.application.get_evaluation(evaluation_id)
            assert loaded is not None, f"升级后历史记录不可读：{evaluation_id}"
            request, result, snapshot = loaded

            assert result.evaluation_id == evaluation_id
            assert restored_business_fields(request, result, snapshot) == (
                manifest_business_fields(entry)
            )
            # 存下来的原文载荷必须与升级前解析出的对象完全相等。
            assert request == EvaluationRequest.model_validate_json(
                pre_rows[evaluation_id]["request_json"]
            )
            assert result.model_dump(mode="json") == json.loads(
                pre_rows[evaluation_id]["result_json"]
            )
            assert snapshot.model_dump(mode="json") == json.loads(
                pre_rows[evaluation_id]["rule_snapshot_json"]
            )

        # 历史列表也不会降级为「损坏记录」。
        summaries = context.application.list_recent_evaluations()
        assert {item.evaluation_id for item in summaries} == set(pre_rows)
        assert all(not item.is_corrupted for item in summaries)
    finally:
        context.database.dispose()


# ===========================================================================
# 4. 升级后新的 GB29446 评价可用
# ===========================================================================


def test_new_gb29446_evaluation_works_after_upgrade(tmp_path: Path) -> None:
    root, manifest = build_legacy(tmp_path / "legacy-0.1.0")
    golden, case = golden_case()

    context = create_context(root)
    try:
        current = current_gb29446()
        # 0.1.0 留下的是第 1 版规则；0003 的新唯一索引允许同版本号的第 2 版并存，
        # 这在 0001/0002 的 (standard_id, version) 唯一索引下是不可能的。
        assert current.rule_revision == golden["rule_revision"] == 2
        context.standards.install(current)
        revisions = sorted(
            row["rule_revision"] for row in standard_rows(root / "uebench.sqlite3")
        )
        assert revisions == [1, 2]

        published = context.application.get_published_standard(GB29446_ID)
        assert published is not None
        assert published.rule_revision == current.rule_revision == 2

        result = context.application.evaluate(golden_request(current, case))
        assert result.standard_id == GB29446_ID
        assert result.rule_revision == golden["rule_revision"]

        indicator = result.results[0]
        expected = case["expected"]
        assert str(indicator.grade) == expected["grade"] == "LEVEL_2"
        assert decimal_text(indicator.actual_value) == decimal_text(expected["e_d"]) == "7"
        assert decimal_text(indicator.display_values["process_factor"]) == decimal_text(
            expected["k"]
        )

        # 新评价可回读，且旧记录仍然完好。
        reloaded = context.application.get_evaluation(result.evaluation_id)
        assert reloaded is not None
        assert str(reloaded[1].results[0].grade) == "LEVEL_2"
        assert context.application.count_evaluations() == 5
        for entry in manifest["evaluations"]:
            assert context.application.get_evaluation(str(entry["evaluation_id"])) is not None
    finally:
        context.database.dispose()


# ===========================================================================
# 5. 迁移前自动备份不得破坏升级
# ===========================================================================


def test_pre_migration_backup_does_not_break_the_upgrade(tmp_path: Path) -> None:
    root, manifest = build_legacy(tmp_path / "legacy-0.1.0")
    database = root / "uebench.sqlite3"
    pre_rows = evaluation_rows(database)
    pre_counters = managed_table_counters(database)
    pre_audit = audit_keys(database)

    context = create_context(root)
    try:
        # 升级必须成功：备份逻辑不允许让迁移失败或丢数据。
        assert context.database.current_revision() == HEAD
        assert evaluation_rows(database).keys() == pre_rows.keys()
        assert_no_rows_lost(database, pre_counters)
        assert pre_audit <= audit_keys(database)

        snapshots = backup_snapshots(context.paths)
        assert len(snapshots) <= 1, [item.name for item in snapshots]
        # 不假设具体文件名；只要求「已记录的迁移前备份」真实存在且就在 backups/ 下。
        recorded = context.database.last_migration_backup
        if recorded is not None:
            assert recorded.exists()
            assert recorded in snapshots
        if snapshots:
            # 不假设具体文件名，只要求它是一个真实的迁移前快照：升级前的
            # revision 与全部记录都在里面。
            snapshot = snapshots[0]
            assert snapshot.name.startswith("pre-migration-")
            extracted = tmp_path / "pre-upgrade-snapshot.sqlite3"
            with zipfile.ZipFile(snapshot) as archive:
                assert "uebench.sqlite3" in archive.namelist()
                extracted.write_bytes(archive.read("uebench.sqlite3"))
            assert revision_of(extracted) == LEGACY_PORTABLE_HEAD
            assert evaluation_rows(extracted) == pre_rows
    finally:
        context.database.dispose()

    # 再次启动必须幂等：仍然在 head，仍然一条不少。
    second = create_context(root)
    try:
        assert second.database.current_revision() == HEAD
        assert second.application.count_evaluations() == len(pre_rows) == 4
        for entry in manifest["evaluations"]:
            assert second.application.get_evaluation(str(entry["evaluation_id"])) is not None
        assert len(backup_snapshots(second.paths)) <= 1
    finally:
        second.database.dispose()


# ===========================================================================
# 6. 2026-09-09 那版 0.1.0 发布物（head 已是 0003）
# ===========================================================================


def test_late_0_1_0_release_build_already_at_head_upgrades_without_data_loss(
    tmp_path: Path,
) -> None:
    root, manifest = build_legacy(tmp_path / "legacy-release", LEGACY_RELEASE_HEAD)
    database = root / "uebench.sqlite3"
    pre_rows = evaluation_rows(database)
    pre_counters = managed_table_counters(database)
    assert revision_of(database) == LEGACY_RELEASE_HEAD

    context = create_context(root)
    try:
        assert context.database.current_revision() == HEAD
        assert evaluation_rows(database) == pre_rows
        assert_no_rows_lost(database, pre_counters)
        for entry in manifest["evaluations"]:
            loaded = context.application.get_evaluation(str(entry["evaluation_id"]))
            assert loaded is not None
            assert restored_business_fields(*loaded) == manifest_business_fields(entry)
    finally:
        context.database.dispose()

    assert revision_of(database) == HEAD


# ===========================================================================
# 7. 回归护栏
# ===========================================================================


def test_migration_head_is_the_revision_this_module_promises(tmp_path: Path) -> None:
    """head 一旦前移，本模块的承诺（0.1.0 → 0.2.0 ≈ → 0003）必须重新评审。"""

    script = ScriptDirectory.from_config(migrations_config(tmp_path / "head-probe.sqlite3"))
    assert script.get_current_head() == HEAD
    assert HEAD == "0003"


def test_fixture_builder_is_reusable_and_deterministic(tmp_path: Path) -> None:
    """同一 revision 的两次生成必须产生同样的 id / 等级 / 记录内容。"""

    first_root, first = build_legacy(tmp_path / "first")
    second_root, second = build_legacy(tmp_path / "second")

    assert first["evaluations"] == second["evaluations"]
    assert first["database_sha256"] == second["database_sha256"]
    assert evaluation_rows(first_root / "uebench.sqlite3") == evaluation_rows(
        second_root / "uebench.sqlite3"
    )
