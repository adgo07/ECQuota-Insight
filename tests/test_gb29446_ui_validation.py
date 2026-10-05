"""ECQ-RS05 §五 — GB 29446「新建评价」输入校验的 MUST BLOCK / WARN ONLY 分类门。

Owner 本轮口径：普通用户界面**不新增任何输入项、也不新增确认勾选**，只把现有校验按
“标准结果还能不能算出来”重新分类：

* MUST BLOCK —— ``e_d = E_d × k ÷ m`` 无法完成：标准公式必需的两个数量为空、非数字或
  非有限值、``m`` 为 0（除零）、``E_d``/``m`` 不大于 0（领域守卫同样要求大于 0）；
* WARN ONLY —— 看起来异常但标准并未禁止的取值（例如 ``1e999`` 这类极大但有限的合法值、
  可选的企业名称留空）一律放行，界面不发明上限，也不要求用户“确认无误”。

被阻止的输入必须**在生成评价请求之前**就被拦下：既不能到达引擎，也不能留下任何评价记录
（旧行为会先保存一条“不完整”记录，再让用户去结果页里找原因）。

本门驱动真实控件（offscreen + 真实应用上下文）。所有模态框都被 autouse 夹具截获并记录，
需要断言提示文字的用例直接读记录；函数体内若再 patch，补丁在后、优先级更高。
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
)

from uebench.bootstrap import create_context
from uebench.domain.models import Grade, StandardDefinition
from uebench.ui.main_window import MainWindow

ROOT = Path(__file__).resolve().parents[1]
GB29446_DEFINITION = ROOT / "data" / "definitions" / "gb-29446-2019.json"

#: 两个必填数量的业务标签（与规则定义逐字一致，界面不得另写一套）。
ELECTRICITY_LABEL = "统计期选煤电力消耗量 E_d"
RAW_COAL_LABEL = "统计期入选原煤量 m"


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _never_block_on_a_modal_dialog(monkeypatch):
    """兜底：任何用例都不得因真实模态框永久阻塞事件循环（offscreen 下没人点按钮）。"""

    for name in ("warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.Ok))
    yield


@pytest.fixture
def window(tmp_path: Path, qt_app: QApplication, monkeypatch):
    """真实组合根 + 仓库权威 GB 29446 r2 规则 + 「新建评价」页；返回 (窗口, 上下文, 提示)。"""

    context = create_context(tmp_path / "appdata")
    context.standards.install(
        StandardDefinition.model_validate_json(GB29446_DEFINITION.read_text(encoding="utf-8"))
    )
    win = MainWindow(context)
    win.navigation.setCurrentRow(2)

    warnings: list[str] = []

    def capture(_parent, _title, message):
        warnings.append(message)
        return QMessageBox.Ok

    monkeypatch.setattr(QMessageBox, "warning", capture)
    try:
        yield win, context, warnings
    finally:
        win.close()
        context.database.dispose()


def _fill(
    window: MainWindow,
    *,
    coal: str = "炼焦煤",
    process: str = "重介",
    electricity: str = "560",
    raw_coal: str = "100",
) -> None:
    window.gb29446_coal_type.setCurrentIndex(window.gb29446_coal_type.findText(coal))
    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData(process))
    window.gb29446_electricity.setText(electricity)
    window.gb29446_raw_coal.setText(raw_coal)


def _forbid_engine(monkeypatch, context) -> list[str]:
    """拦截正式评价用例的调用；被阻止的输入根本不应该走到这里。"""

    calls: list[str] = []

    def recorder(request):
        calls.append(request.standard_id)
        raise AssertionError("被阻止的输入不得到达正式评价用例")

    monkeypatch.setattr(context.application, "evaluate", recorder)
    return calls


def test_valid_input_computes_and_saves_exactly_one_record(window) -> None:
    """先守住“没有过度拦截”：合法输入照旧算出等级并落库。"""

    win, context, warnings = window
    _fill(win)
    win.calculate_button.click()

    assert warnings == []
    assert win.last_result_id is not None
    assert win.gb29446_result_grade.text() == "2级"
    assert context.application.count_evaluations() == 1


@pytest.mark.parametrize(
    ("field", "label"),
    [("electricity", ELECTRICITY_LABEL), ("raw_coal", RAW_COAL_LABEL)],
)
def test_empty_required_quantity_blocks_before_the_engine(window, monkeypatch, field, label) -> None:
    """空值（标准公式必需）→ MUST BLOCK，且在校验阶段就拒绝。"""

    win, context, warnings = window
    calls = _forbid_engine(monkeypatch, context)
    _fill(win, **{field: ""})

    win.calculate_button.click()

    assert warnings == [f"{label} 不能为空。"]
    assert calls == [], "被阻止的输入不得到达正式评价用例"
    assert win.last_result_id is None
    assert context.application.count_evaluations() == 0
    # 页面提示按真下标呈现该输入项，且不泄露内部键。
    assert label.replace("E_d", "E<sub>d</sub>") in win.gb29446_result_message.text()
    assert "electricity_consumption" not in win.gb29446_result_message.text()
    assert "raw_coal_input" not in win.gb29446_result_message.text()


@pytest.mark.parametrize("field", ["electricity", "raw_coal"])
@pytest.mark.parametrize(
    ("lexical", "fragment"),
    [
        ("abc", "不是有效十进制数"),
        ("NaN", "必须是有限十进制数"),
        ("sNaN", "必须是有限十进制数"),
        ("Infinity", "必须是有限十进制数"),
        ("-inf", "必须是有限十进制数"),
    ],
)
def test_non_numeric_required_quantity_blocks_before_the_engine(
    window, monkeypatch, field, lexical, fragment
) -> None:
    """非数字 / 非有限值 → MUST BLOCK（提示沿用领域解析器的中文口径）。"""

    win, context, warnings = window
    calls = _forbid_engine(monkeypatch, context)
    _fill(win, **{field: lexical})

    win.calculate_button.click()

    label = ELECTRICITY_LABEL if field == "electricity" else RAW_COAL_LABEL
    assert warnings == [f"{label} {fragment}。"]
    assert calls == []
    assert win.last_result_id is None
    assert context.application.count_evaluations() == 0
    assert "decimal.InvalidOperation" not in win.gb29446_result_message.text()


@pytest.mark.parametrize(
    ("field", "value", "label"),
    [
        ("electricity", "0", ELECTRICITY_LABEL),
        ("electricity", "-1", ELECTRICITY_LABEL),
        ("raw_coal", "0", RAW_COAL_LABEL),
        ("raw_coal", "-1", RAW_COAL_LABEL),
    ],
)
def test_non_positive_required_quantity_blocks_including_zero_denominator(
    window, monkeypatch, field, value, label
) -> None:
    """``m = 0`` 是除零、``E_d ≤ 0`` 被领域守卫拒绝 → 两者都是 MUST BLOCK。"""

    win, context, warnings = window
    calls = _forbid_engine(monkeypatch, context)
    _fill(win, **{field: value})

    win.calculate_button.click()

    assert warnings == [f"{label} 必须大于 0。"]
    assert calls == []
    assert win.last_result_id is None
    assert context.application.count_evaluations() == 0
    assert win.gb29446_result_grade.text() == "—"


def test_extreme_but_finite_values_are_warn_only_and_still_computed(window) -> None:
    """看起来异常但标准未禁止的取值只能照算，界面不得发明上限。"""

    win, context, warnings = window
    _fill(win, process="跳汰、浮选联合", electricity="1e999", raw_coal="1")
    win.calculate_button.click()

    assert warnings == []
    assert win.last_result_id is not None
    assert win.gb29446_result_grade.text() == "超出3级"
    saved = context.application.get_evaluation(win.last_result_id)[1].results[0]
    assert saved.actual_value == Decimal("1e999") and saved.actual_value.is_finite()
    assert saved.grade is Grade.NOT_QUALIFIED


def test_optional_metadata_never_blocks(window) -> None:
    """可选企业名称留空、没有备注：既不需要填写也不需要确认。"""

    win, context, warnings = window
    _fill(win)
    assert win.gb29446_organization.text() == ""

    win.calculate_button.click()

    assert warnings == []
    assert win.last_result_id is not None
    request = context.application.get_evaluation(win.last_result_id)[0]
    assert request.organization_name is None
    assert request.notes == "核算周期：全年"


def test_ordinary_form_has_no_new_field_and_no_confirmation_checkbox(window) -> None:
    """§五：不新增普通用户输入项，也不新增“我已确认/是否准确/是否异常”式勾选。"""

    win, _context, _warnings = window
    form: QFormLayout = win.gb29446_form_layout
    labels = []
    for row in range(form.rowCount()):
        item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
        widget = item.widget() if item is not None else None
        if widget is not None:
            labels.append(widget.text())
    assert labels == [
        "企业名称（可选）",
        "核算周期",
        "煤种",
        "选煤工艺",
        "统计期选煤电力消耗量 E<sub>d</sub>（kW·h）",
        "统计期入选原煤量 m（t）",
        "折算系数 k（自动匹配，只读）",
    ]
    assert not any("备注" in text for text in labels)

    assert win.findChildren(QCheckBox) == [], "普通界面不得新增确认勾选框"
    texts = [label.text() for label in win.findChildren(QLabel)]
    texts += [button.text() for button in win.findChildren(QPushButton)]
    for forbidden in ("我已确认", "是否准确", "是否异常", "确认无误", "数据准确"):
        assert not any(forbidden in text for text in texts), forbidden
