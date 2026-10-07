"""ECQ-RS05 M3：删除已实测的重复工作。

本模块只覆盖两件事：

1. 标准定义不再被重复解析——按 ID 只读一个标准；一次刷新内同一份标准定义只解析
   一次，且**不跨刷新**保留（见 ``test_definitions_are_not_reused_across_refreshes``）；
2. 「评价记录」页只在首次进入（或变脏后再次进入）时加载，全局刷新不再为从未打开过
   的页面读取最近 200 条记录，首页的最近 10 条照旧加载。

既有行为——正式评价范围、标准库浏览语义、损坏记录降级、历史记录只读——一律保持不变，
因此本模块同时断言"新的数量"和"旧的语义"。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from sqlalchemy import text

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QMessageBox

from uebench.application.facade import ApplicationFacade
from uebench.bootstrap import create_context
from uebench.domain.models import RECORD_CORRUPTED_LABEL, StandardDefinition
from uebench.ui.main_window import MainWindow
from .test_gb29446 import _request

ROOT = Path(__file__).resolve().parents[1]
GB29446_DEFINITION = ROOT / "data" / "definitions" / "gb-29446-2019.json"
GB29446_ID = "gb-29446-2019"

#: 标准库规模保持小而可读。断言写的是"每个已安装标准最多解析一次"，不是任何和机器
#: 负载相关的绝对秒数。
LIBRARY_SIZE = 6


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def gb29446_definition() -> StandardDefinition:
    return StandardDefinition.model_validate_json(
        GB29446_DEFINITION.read_text(encoding="utf-8")
    )


def identity_variant(standard_id: str, number: str, version: str, **overrides) -> StandardDefinition:
    """GB 29446 的合法副本，身份不同：用于把标准库撑到多项或构造未来标准。"""

    data = json.loads(GB29446_DEFINITION.read_text(encoding="utf-8"))
    data.update(
        {
            "id": standard_id,
            "number": number,
            "version": version,
            "title": f"对照标准 {number}",
            "standard_family_id": number,
            "rule_revision": 1,
            "publication_status": "published",
            "publication_date": "2025-06-01",
            "effective_date": "2026-01-01",
        }
    )
    data.update(overrides)
    return StandardDefinition.model_validate(data)


def unsupported_definition(index: int) -> StandardDefinition:
    """GB 29446 的合法副本，身份不同，用于把标准库撑到多项。"""

    return identity_variant(
        f"gb-0000{index}-2026",
        f"GB 0000{index}-2026",
        "2026",
        title=f"未梳理对照标准{index}",
        standard_family_id=f"GB 0000{index}",
    )


def install_library(context) -> None:
    context.standards.install(gb29446_definition())
    for index in range(1, LIBRARY_SIZE):
        context.standards.install(unsupported_definition(index))


def save_one_record(context) -> None:
    standard = next(
        item for item in context.application.list_library_standards() if item.id == GB29446_ID
    )
    context.application.evaluate(
        _request(standard, "炼焦煤", process="重介", electricity="560", raw_coal="100")
    )


@pytest.fixture
def parse_counter(monkeypatch):
    """统计 ``StandardDefinition.model_validate_json`` 的真实调用次数。"""

    counter = {"count": 0}
    original = StandardDefinition.model_validate_json

    def counting(cls, *args, **kwargs):
        counter["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(StandardDefinition, "model_validate_json", classmethod(counting))
    return counter


def count_parses(parse_counter, action):
    parse_counter["count"] = 0
    action()
    return parse_counter["count"]


@pytest.fixture
def context(tmp_path):
    ctx = create_context(tmp_path / "appdata")
    install_library(ctx)
    try:
        yield ctx
    finally:
        ctx.database.dispose()


@pytest.fixture
def record_calls(monkeypatch, context):
    """记录 ``list_recent_evaluations`` 的每一次 limit 参数。"""

    calls: list[int] = []
    original = context.application.list_recent_evaluations

    def spy(limit: int = 100):
        calls.append(limit)
        return original(limit)

    monkeypatch.setattr(context.application, "list_recent_evaluations", spy)
    return calls


@pytest.fixture
def window(qt_app, context, record_calls, monkeypatch):
    """已存有一条评价记录的主窗口；``record_calls`` 先于窗口安装。"""

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: pytest.fail(str(args)))
    save_one_record(context)
    win = MainWindow(context)
    try:
        yield win
    finally:
        win.close()


# ---------------------------------------------------------------------------
# 1. 单个标准按 ID 读取
# ---------------------------------------------------------------------------


def test_get_standard_parses_only_the_requested_standard(context, parse_counter):
    parsed = count_parses(parse_counter, lambda: context.application.get_standard(GB29446_ID))
    assert parsed == 1, f"按 ID 读取只应解析目标标准，实际解析 {parsed} 个"
    standard = context.application.get_standard(GB29446_ID)
    assert standard is not None and standard.id == GB29446_ID


def test_get_standard_is_equivalent_to_the_library_entry(context):
    library_entry = next(
        item for item in context.application.list_library_standards() if item.id == GB29446_ID
    )
    by_id = context.application.get_standard(GB29446_ID)
    assert by_id is not None
    assert by_id.model_dump() == library_entry.model_dump(), (
        "按 ID 读取必须与标准库条目完全一致（同一份选择规则）"
    )


def test_get_standard_keeps_the_newest_installed_revision(context):
    newer = gb29446_definition().model_copy(update={"rule_revision": 2})
    context.standards.install(newer)
    by_id = context.application.get_standard(GB29446_ID)
    assert by_id is not None and by_id.rule_revision == 2
    library_revisions = {
        item.rule_revision
        for item in context.application.list_library_standards()
        if item.id == GB29446_ID
    }
    assert library_revisions == {2}


def test_get_standard_falls_back_to_the_catalogue_without_installing_it(tmp_path):
    catalogue_dir = tmp_path / "catalogue"
    catalogue_dir.mkdir()
    data = json.loads(GB29446_DEFINITION.read_text(encoding="utf-8"))
    data.update(
        {
            "id": "gb-99999-2026",
            "number": "GB 99999-2026",
            "version": "2026",
            "title": "目录中待确认标准",
            "standard_family_id": "GB 99999-2026",
            "publication_status": "draft",
            "effective_date": "2026-06-01",
        }
    )
    (catalogue_dir / "pending.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    context = create_context(tmp_path / "appdata")
    facade = ApplicationFacade(
        standards=context.standards,
        evaluations=context.evaluations,
        evaluation_service=context.evaluation_service,
        catalogue_dir=catalogue_dir,
    )
    try:
        # 目录条目可浏览，但绝不进入已安装标准库，也不进入正式评价入口。
        browsable = facade.get_standard("gb-99999-2026")
        assert browsable is not None and browsable.id == "gb-99999-2026"
        assert facade.get_published_standard("gb-99999-2026") is None
        assert facade.get_standard("never-exists") is None

        # 同一 id 同时存在于已安装库与目录时，已安装库优先（原语义）。
        context.standards.install(gb29446_definition())
        installed = facade.get_standard(GB29446_ID)
        assert installed is not None and installed.id == GB29446_ID
        assert installed.publication_status.value == "published"
    finally:
        context.database.dispose()


# ---------------------------------------------------------------------------
# 2. 一次刷新内复用已解析的标准定义
# ---------------------------------------------------------------------------


def test_one_refresh_parses_each_installed_definition_once(context, parse_counter, qt_app):
    window = MainWindow(context)
    try:
        single_page = count_parses(parse_counter, window.refresh_home)
        assert single_page <= LIBRARY_SIZE
        full = count_parses(parse_counter, window.refresh_all)
        assert full <= LIBRARY_SIZE
    finally:
        window.close()


def test_refresh_all_keeps_its_existing_results(context, qt_app):
    """复用解析不得改变刷新结果：计数、标准库表、评价下拉框都必须照旧。"""

    window = MainWindow(context)
    try:
        window.refresh_all()
        assert window.home_standard_count.text() == f"{LIBRARY_SIZE}/{LIBRARY_SIZE}"
        assert window.standard_table.rowCount() == LIBRARY_SIZE
        assert window.eval_standard.count() == 1
        assert window.eval_standard.currentData() == GB29446_ID
        assert window.home_formal_scope_count.text() == "1 项"
    finally:
        window.close()


def test_refresh_still_filters_current_standards_by_effective_date(context, qt_app):
    """延迟/复用读取不得改变"当前有效"过滤：尚未实施的标准不计入当前数量。"""

    future = identity_variant(
        "gb-77777-2099",
        "GB 77777-2099",
        "2099",
        title="尚未实施对照标准",
        publication_date="2098-01-01",
        effective_date="2099-01-01",
    )
    context.standards.install(future)
    window = MainWindow(context)
    try:
        assert window.home_standard_count.text() == f"{LIBRARY_SIZE}/{LIBRARY_SIZE + 1}"
        assert window.standard_table.rowCount() == LIBRARY_SIZE + 1
    finally:
        window.close()


def test_definitions_are_not_reused_across_refreshes(context, parse_counter, qt_app):
    """快照只活在一次刷新内：下一次刷新必须重新读取数据库。"""

    window = MainWindow(context)
    try:
        first = count_parses(parse_counter, window.refresh_all)
        second = count_parses(parse_counter, window.refresh_all)
        assert first == second, "跨刷新不得缓存标准定义"
        assert second > 0
    finally:
        window.close()


def test_definitions_are_not_reused_outside_the_scope(context, parse_counter):
    """作用域之外没有任何残留快照。"""

    outside = count_parses(
        parse_counter,
        lambda: (context.standards.list_all(), context.standards.list_all()),
    )
    assert outside == 2 * LIBRARY_SIZE, f"作用域之外应逐次解析，实际 {outside}"

    def two_reads_in_scope():
        with context.application.standard_definition_snapshot():
            context.standards.list_all()
            context.standards.list_all()

    in_scope = count_parses(parse_counter, two_reads_in_scope)
    assert in_scope == LIBRARY_SIZE, f"作用域内同一份定义只应解析一次，实际 {in_scope}"

    after = count_parses(parse_counter, context.standards.list_all)
    assert after == LIBRARY_SIZE, "作用域结束后不得保留任何解析结果"


def test_snapshot_returns_independent_definitions(context):
    """复用解析不得把同一个对象交给两个调用方（保持原有的对象隔离）。"""

    with context.application.standard_definition_snapshot():
        first = context.standards.list_all()
        second = context.standards.list_all()
    assert first[0] is not second[0]
    assert first[0].model_dump() == second[0].model_dump()


def test_snapshot_nested_data_is_deeply_isolated(context):
    """快照复用必须返回**深层**独立副本，保持原「每次新鲜解析」的嵌套隔离语义。

    浅拷贝（model_copy()）仍会共享 products / indicators：修改一份的嵌套内容会污染
    快照本身，并泄漏到同一作用域内之后的每一次读取。
    """

    with context.application.standard_definition_snapshot():
        first = context.standards.list_all()[0]
        assert first.products, "夹具必须含 products"
        assert first.products[0].indicators, "夹具必须含 indicators"
        expected_products = len(first.products)
        expected_name = first.products[0].indicators[0].name

        # 篡改第一份的嵌套内容
        first.products[0].indicators[0].name = "被篡改的指标名称"
        first.products.pop()

        second = context.standards.list_all()[0]
        third = context.standards.list_all()[0]

    assert len(second.products) == expected_products, "第一份的嵌套修改不得影响第二份"
    assert second.products[0].indicators[0].name == expected_name, "嵌套 indicator 必须独立"
    assert len(third.products) == expected_products, "快照不得被第一份的嵌套修改污染"
    assert third.products[0].indicators[0].name == expected_name
    assert second.model_dump() == third.model_dump()

    # 作用域结束后的全新解析当然也不受影响
    after = context.standards.list_all()[0]
    assert len(after.products) == expected_products
    assert after.products[0].indicators[0].name == expected_name


# ---------------------------------------------------------------------------
# 3. 「评价记录」页延迟加载
# ---------------------------------------------------------------------------


def test_construction_and_refresh_all_never_read_the_hidden_records_page(
    tmp_path, qt_app, monkeypatch
):
    context = create_context(tmp_path / "appdata")
    install_library(context)
    save_one_record(context)
    calls: list[int] = []
    original = context.application.list_recent_evaluations

    def spy(limit: int = 100):
        calls.append(limit)
        return original(limit)

    monkeypatch.setattr(context.application, "list_recent_evaluations", spy)
    window = MainWindow(context)
    try:
        assert 200 not in calls, "构造窗口不得读取隐藏的记录页"
        assert 10 in calls, "首页的最近 10 条必须照旧加载"
        calls.clear()
        window.refresh_all()
        assert 200 not in calls, "全局刷新不得读取隐藏的记录页"
        assert 10 in calls, "全局刷新仍必须刷新首页最近 10 条"
        assert window.record_table.rowCount() == 0
        assert window.home_recent.rowCount() == 1
    finally:
        window.close()
        context.database.dispose()


def test_records_page_loads_on_first_entry_and_is_not_read_again_when_clean(
    window, record_calls
):
    window.navigation.setCurrentRow(3)
    assert record_calls.count(200) == 1, "首次进入记录页必须加载"
    assert window.record_table.rowCount() == 1

    window.navigation.setCurrentRow(0)
    window.navigation.setCurrentRow(3)
    assert record_calls.count(200) == 1, "列表未变脏时重进页面不应重复读取"


def test_records_page_stays_retryable_when_the_first_load_fails(tmp_path, qt_app, monkeypatch):
    """首次加载失败不得把页面错标为已加载/干净：再次进入必须重新读取并成功。"""

    context = create_context(tmp_path / "appdata")
    install_library(context)
    save_one_record(context)
    calls: list[int] = []
    original = context.application.list_recent_evaluations
    failures = {"remaining": 1}

    def flaky(limit: int = 100):
        calls.append(limit)
        if limit == 200 and failures["remaining"] > 0:
            failures["remaining"] -= 1
            raise RuntimeError("临时读取失败")
        return original(limit)

    monkeypatch.setattr(context.application, "list_recent_evaluations", flaky)
    window = MainWindow(context)
    try:
        try:
            window.navigation.setCurrentRow(3)
        except RuntimeError:
            # 允许异常沿调用链向上传播的实现；状态不变量才是本用例的重点。
            pass
        assert calls.count(200) == 1, "首次进入记录页必须尝试加载"
        assert window._records_loaded is False, "读取失败后不得标记为已加载"
        assert window._records_dirty is True, "读取失败后必须保持可重试状态"
        assert window.record_table.rowCount() == 0, "失败时不得留下半填的表格"

        window.navigation.setCurrentRow(0)
        window.navigation.setCurrentRow(3)
        assert calls.count(200) == 2, "再次进入记录页必须重新读取"
        assert window._records_loaded is True
        assert window._records_dirty is False
        assert window.record_table.rowCount() == 1

        # 干净之后重进不应再读
        window.navigation.setCurrentRow(0)
        window.navigation.setCurrentRow(3)
        assert calls.count(200) == 2, "成功加载且未变脏后不得重复读取"
    finally:
        window.close()
        context.database.dispose()


def test_saving_a_record_marks_the_list_dirty_and_reloads_on_next_entry(
    window, context, record_calls
):
    standard = next(
        item for item in context.application.list_library_standards() if item.id == GB29446_ID
    )
    request = _request(standard, "炼焦煤", process="重介", electricity="560", raw_coal="100")

    window.navigation.setCurrentRow(2)
    window.calculate_evaluation(request)

    assert record_calls.count(200) == 0, "保存记录后不得立刻读取 200 条"
    assert window._records_dirty is True, "保存必须把记录页标记为待刷新"

    window.navigation.setCurrentRow(3)
    assert record_calls.count(200) == 1, "下次进入记录页必须刷新脏数据"
    assert window.record_table.rowCount() == 2


def test_delete_marks_dirty_when_hidden_and_refreshes_immediately_when_visible(
    window, context, record_calls, monkeypatch
):
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    )
    window.navigation.setCurrentRow(3)
    assert window.record_table.rowCount() == 1
    window.record_table.selectRow(0)

    # 记录页正在显示：删除后立即重建列表。
    window.delete_selected_record()
    assert record_calls.count(200) == 2, "记录页可见时应立即刷新"
    assert window.record_table.rowCount() == 0

    # 记录页隐藏时：只标记待刷新，下一次进入才读取。
    save_one_record(context)
    window.navigation.setCurrentRow(0)
    window.refresh_all()
    assert record_calls.count(200) == 2, "隐藏时 refresh_all 不得读取 200 条"
    assert window._records_dirty is True

    window.navigation.setCurrentRow(3)
    assert record_calls.count(200) == 3, "重新进入记录页必须刷新脏数据"
    assert window.record_table.rowCount() == 1


def test_explicit_refresh_still_reloads_the_list(window, record_calls):
    window.navigation.setCurrentRow(3)
    assert record_calls.count(200) == 1
    window.refresh_records()
    assert record_calls.count(200) == 2, "显式刷新必须重新读取"


def test_record_list_keeps_corrupted_row_degradation(window, context, record_calls):
    """损坏记录的显式降级语义不得因延迟加载而改变。"""

    with context.database.engine.begin() as connection:
        connection.execute(
            text("UPDATE evaluations SET result_json=:payload"),
            {"payload": '{"evaluation_id": "truncated", "results": ['},
        )

    window.navigation.setCurrentRow(3)
    assert window.record_table.rowCount() == 1
    assert RECORD_CORRUPTED_LABEL in window.record_table.item(0, 5).text()
    assert window.home_recent.rowCount() == 1, "损坏行不得从首页消失"
