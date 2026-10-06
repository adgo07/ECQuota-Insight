"""ECQ-RS05 — GB 29446 evaluate-button wiring and library revision resolution.

Two real defects found by manual acceptance of the packaged Candidate, both of
which every existing test missed because the tests drove the *methods* instead of
the *signal*, and the *facade*:

1. ``calculate.clicked.connect(self.calculate_evaluation)`` — ``QPushButton.clicked``
   passes ``checked: bool`` as the first positional argument, and
   ``calculate_evaluation``'s first parameter is an *optional*
   ``EvaluationRequest``.  Qt therefore handed ``False`` in as the request, and
   ``request.standard_id`` raised ``AttributeError`` **before** the method's own
   ``try``.  PySide6 swallowed it, so clicking 计算并判级 produced no result, no
   dialog and no record — the button looked dead.  Calling
   ``calculate_evaluation()`` directly (as the old tests did) never exercises the
   wiring, so the wiring itself has to be tested.

2. ``ApplicationFacade.list_library_standards`` collapsed installed revisions with
   ``{item.id: item}``, keeping whichever row the repository yielded last.  The
   repository orders by ``desc(rule_revision)``, so the *oldest* revision won: the
   standard library and the diagnostics view reported GB 29446 ``rule_revision 1``
   even though the installed package supplies r2.

The fixtures deliberately install the **published r1 package first and the bundled
r2 package second** — the real upgrade path — so both revisions are present.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from uebench.bootstrap import create_context
from uebench.ui.main_window import MainWindow

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = ROOT / "src" / "uebench" / "resources" / "update_public_key.pem"
#: 旧包已移出仓库（REFERENCE ONLY）；取得的是归档件的**副本**。
try:  # 测试目录既可能是普通目录，也可能被当作包
    from _legacy_assets import session_legacy_package
except ModuleNotFoundError:  # pragma: no cover - 取决于 pytest 的导入模式
    from tests._legacy_assets import session_legacy_package

LEGACY_PACKAGE = session_legacy_package()
BUNDLED_PACKAGE = (ROOT / "release" / "standard-packages"
                   / "initial-standard-package-published.uebench")

STANDARD_ID = "gb-29446-2019"
POWER_COAL_PRODUCT_ID = "gb_29446-2019-power-coal"


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _silence_dialogs(monkeypatch):
    """No modal box may block: clicking really does open message boxes.

    Static ``QMessageBox.warning/information/critical`` run a nested event loop,
    which would hang an offscreen test run forever.  Individual tests re-patch
    these to capture the text they care about.
    """
    for name in ("warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.Ok))
    yield


@pytest.fixture()
def window(qt_app: QApplication, tmp_path: Path):
    """A real MainWindow; holds GB 29446 r2, and r1 too when the archive is present."""
    context = create_context(tmp_path / "appdata", public_key_path=PUBLIC_KEY)
    application = context.application
    if not application.has_package_service():
        pytest.skip("标准包服务不可用（缺少更新公钥）")
    # 当前正式包是必需的；旧包只用于让库中同时存在 r1+r2。旧包已移出仓库、只存在
    # 于项目外只读归档，CI 上不可用，因此它是**可选**的：否则按钮接线这类与旧包
    # 无关的回归会在 CI 上整片 skip，等于丢失覆盖。
    if not BUNDLED_PACKAGE.is_file():
        pytest.skip(f"缺少当前正式标准包：{BUNDLED_PACKAGE.name}")
    if LEGACY_PACKAGE.is_file():
        application.install_package(LEGACY_PACKAGE)
    application.install_package(BUNDLED_PACKAGE)

    win = MainWindow(context)
    win.eval_standard.setCurrentIndex(win.eval_standard.findData(STANDARD_ID))
    win._standard_changed()
    try:
        yield win
    finally:
        win.close()
        context.database.dispose()


def _fill_power_coal(win: MainWindow, process: str = "干法选煤") -> None:
    coal = win.gb29446_coal_type
    for index in range(coal.count()):
        if coal.itemData(index) == POWER_COAL_PRODUCT_ID:
            coal.setCurrentIndex(index)
            break
    else:  # pragma: no cover - data problem
        pytest.fail("煤种下拉框缺少动力煤")
    combo = win.gb29446_process
    for index in range(combo.count()):
        if str(combo.itemData(index)) == process:
            combo.setCurrentIndex(index)
            break
    else:  # pragma: no cover - data problem
        pytest.fail(f"选煤工艺下拉框缺少 {process}")
    win.gb29446_electricity.setText("1000")
    win.gb29446_raw_coal.setText("200")


def test_setup_has_both_revisions_installed(window) -> None:
    """Guard the fixture itself: this is the post-upgrade state."""
    revisions = {
        item.rule_revision
        for item in window.context.application.list_all_standards()
        if item.id == STANDARD_ID
    }
    if not LEGACY_PACKAGE.is_file():
        pytest.skip("旧包归档不可用（CI 无项目外只读归档），无法构造 r1+r2 并存状态")
    assert revisions == {1, 2}, f"夹具应同时装有 r1 与 r2，实际 {revisions}"


def test_clicked_signal_does_not_pass_its_bool_into_the_request(window) -> None:
    """The exact regression: invoked through the signal, not called directly."""
    _fill_power_coal(window)
    monkeypatch_target = window.calculate_button
    assert monkeypatch_target.isEnabled()

    # click() emits clicked(False) into the connected slot — what a user does.
    monkeypatch_target.click()

    assert "未预期错误" not in window.gb29446_result_message.text()
    explanation = window.gb29446_explanation.text()
    assert explanation.strip(), "点击后应显示本次代入计算与阈值说明"
    assert "e_d" in explanation or "折算" in explanation


def test_clicked_signal_saves_an_evaluation_record(window, monkeypatch) -> None:
    _fill_power_coal(window)
    shown: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information",
        lambda *args, **kwargs: shown.append(str(args[2]) if len(args) > 2 else ""),
    )
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)

    before = window.context.application.count_evaluations()
    window.calculate_button.click()
    after = window.context.application.count_evaluations()

    assert after == before + 1, "通过按钮点击必须真正生成评价记录"
    assert any("已生成评价记录" in text for text in shown), shown


def test_power_coal_with_dry_cleaning_is_accepted(window) -> None:
    """动力煤 + 干法选煤 is a valid combination (干法选煤 is in 动力煤's choices)."""
    _fill_power_coal(window, process="干法选煤")
    window.calculate_evaluation()
    explanation = window.gb29446_explanation.text()
    assert "不在允许选项中" not in explanation
    # k = 1.04 and e_d = 1000 * 1.04 / 200 = 5.2 -> beyond level 3 for 动力煤
    assert "5.2" in explanation, explanation


def test_bool_first_argument_is_treated_as_no_request(window) -> None:
    """A bare bool must never be mistaken for an EvaluationRequest."""
    _fill_power_coal(window)
    window.calculate_evaluation(False)  # what clicked(bool) can hand over
    window.calculate_evaluation(True)
    assert "未预期错误" not in window.gb29446_result_message.text()


def test_unexpected_error_is_reported_not_swallowed(window, monkeypatch) -> None:
    """A slot that raises must surface something instead of doing nothing."""
    _fill_power_coal(window)
    critical: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "critical",
        lambda *args, **kwargs: critical.append(str(args[2]) if len(args) > 2 else ""),
    )

    def boom(*args, **kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(window, "_calculate_evaluation", boom)
    window.calculate_button.click()

    assert critical, "计算槽函数抛出异常时必须给出可见提示，而不是静默无反应"


def test_library_lists_the_newest_revision_of_each_standard(window) -> None:
    """With r1 and r2 both installed, the library must show r2."""
    application = window.context.application
    revisions = {
        item.rule_revision
        for item in application.list_library_standards()
        if item.id == STANDARD_ID
    }
    assert revisions == {2}, f"标准库必须显示最新规则修订，实际 {revisions}"


def test_library_has_one_entry_per_standard_while_rows_retain_history(window) -> None:
    application = window.context.application
    identifiers = [item.id for item in application.list_library_standards()]
    assert len(identifiers) == len(set(identifiers)), "标准库不应出现重复标准"
    rows = len(application.list_all_standards())
    assert rows >= len(identifiers), "标准库条目不应多于已安装标准行数"
    if LEGACY_PACKAGE.is_file():
        assert rows > len(identifiers), (
            "list_all_standards 应保留 r1 历史行，因此多于标准库条目数"
        )
    else:
        assert rows == len(identifiers), "仅装 r2 时行数与标准库条目数相同"


def test_diagnostics_reports_the_current_revision(window) -> None:
    """The diagnostics view must not report the superseded revision."""
    application = window.context.application
    current = application.get_published_standard(STANDARD_ID)
    assert current is not None and current.rule_revision == 2
    library = next(
        item for item in application.list_library_standards() if item.id == STANDARD_ID
    )
    assert library.rule_revision == current.rule_revision
