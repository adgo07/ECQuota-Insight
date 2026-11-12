"""配比辅助输入：合成数值、请求入口及离屏表单。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal, Inexact, ROUND_DOWN, localcontext
import pytest
from PySide6.QtWidgets import QApplication

from uebench.domain.gb16780 import clinker_ratio, NodeError
from uebench.domain.models import InputValue
from uebench.domain.models import Grade
from uebench.application.gb16780 import IncompleteCementEvaluationError
from uebench.ui.gb16780_form import CementLineForm
from .test_gb16780_application import cement_context, request, state
from .test_gb16780_core import put
from .test_gb16780_ui import window


def inputs(consumption, production):
    return {"cement.clinker_consumption_t": InputValue(value=consumption, unit="t"),
            "cement.production_t": InputValue(value=production, unit="t")}


@pytest.mark.parametrize("consumption,production,expected", [("0", "3", "0"), ("3", "3", "100"),
    ("1", "3", "33.33333333333333333333333333"), ("1500", "2000", "75.00")])
def test_ratio_profile_owns_precision_rounding_and_traps(consumption, production, expected):
    with localcontext() as context:
        context.prec = 3
        context.rounding = ROUND_DOWN
        context.traps[Inexact] = True
        assert clinker_ratio(inputs(consumption, production)) == Decimal(expected)


@pytest.mark.parametrize("consumption,production", [("", "2"), ("1", ""), ("bad", "2"),
    ("NaN", "2"), ("-1", "2"), ("1", "0"), ("1", "-2"),
    ("1.00000000000000000000000000001", "1"), ("1e9999999", "2")])
def test_ratio_invalid_never_returns_stale_or_over_100(consumption, production):
    with pytest.raises(NodeError):
        clinker_ratio(inputs(consumption, production))


def test_ratio_units_are_checked():
    value = inputs("1", "2")
    value["cement.production_t"].unit = "kg"
    with pytest.raises(NodeError, match="单位"):
        clinker_ratio(value)


@pytest.mark.parametrize("bad", ["74.99", "", "NaN"])
def test_automatic_request_cannot_bypass_consistency(cement_context, bad):
    value = request()
    line = value.cement_lines[0]
    line.clinker_ratio_mode = "automatic"
    put(line, "cement.clinker_percent", bad)
    with pytest.raises(IncompleteCementEvaluationError) as caught:
        cement_context.application.evaluate(value)
    assert caught.value.preview_result.results[0].grade is Grade.INCOMPLETE
    assert any(item.grade in {Grade.LEVEL_1, Grade.LEVEL_2, Grade.LEVEL_3} for item in caught.value.preview_result.results[1:])
    assert state(cement_context) == (0, 0)


def test_legacy_manual_difference_preserved_and_warning_saved(cement_context):
    value = request()
    line = value.cement_lines[0]
    assert line.clinker_ratio_mode == "manual"
    put(line, "cement.clinker_percent", "76")
    result = cement_context.application.evaluate(value)
    item = next(item for item in result.results if item.indicator_id == "cement.comprehensive_energy")
    assert any("手工熟料配比" in warning for warning in item.warnings)
    assert line.inputs["cement.clinker_percent"].value == "76"
    saved = cement_context.application.get_evaluation(result.evaluation_id)
    assert saved[1].model_dump() == result.model_dump()
    assert state(cement_context) == (1, 1)


def test_form_automatic_manual_load_and_line_isolation():
    app = QApplication.instance() or QApplication([])
    line, second = CementLineForm(), CementLineForm()
    try:
        field = line.fields["cement.clinker_percent"]
        line.fields["cement.clinker_consumption_t"].setText("1")
        line.fields["cement.production_t"].setText("3")
        assert field.isReadOnly() and field.text() == "33.33333333333333333333333333"
        assert second.fields["cement.clinker_percent"].text() == ""
        line.fields["cement.production_t"].setText("0")
        assert field.text() == "" and "大于0" in line.ratio_notice.text()
        line.fields["cement.production_t"].setText("2")
        assert field.text() == "50.0"
        line.ratio_mode.setCurrentIndex(1)
        field.setText("60")
        line.fields["cement.production_t"].setText("4")
        assert field.text() == "60" and "不一致" in line.ratio_notice.text()
        line.ratio_mode.setCurrentIndex(0)
        assert field.text() == "25.00"
        saved = line.collect()
        line.load(saved)
        assert field.text() == "25.00" and not field.isReadOnly()
        line.fields["cement.production_t"].setText("5")
        assert field.text() == "25.00" and "不一致" in line.ratio_notice.text()
        for mode in ("clinker_only", "purchased_clinker_grinding"):
            line.mode.setCurrentIndex(line.mode.findData(mode))
            assert line.ratio_controls.isHidden()
            assert "cement.clinker_percent" not in line.collect().inputs
    finally:
        line.close()
        second.close()
        app.processEvents()


def test_repeated_load_preserves_values_without_duplicating_fuels():
    app = QApplication.instance() or QApplication([])
    widget = CementLineForm()
    try:
        original = request().cement_lines[0]
        put(original, "cement.clinker_percent", "76.00000000000000000000000001")
        widget.load(original)
        widget.load(original)
        assert widget.fuels.table.rowCount() == len(original.fuels)
        assert {k: v.value for k, v in widget.collect().inputs.items()} == {k: v.value for k, v in original.inputs.items()}
        assert "不一致" in widget.ratio_notice.text()
    finally:
        widget.close()
        app.processEvents()


def test_automatic_save_once_and_production_change_invalidates(window):
    line = window.cement_form.lines[0]
    line.ratio_mode.setCurrentIndex(0)
    window.calculate_evaluation()
    first_id = window.last_result_id
    assert first_id and state(window.context) == (1, 1)
    window.calculate_evaluation()
    assert window.last_result_id == first_id and state(window.context) == (1, 1)
    line.fields["cement.production_t"].setText("2500")
    assert window.last_result_id is None
    assert line.fields["cement.clinker_percent"].text() == "60.0"
    window.calculate_evaluation()
    assert window.last_result_id != first_id and state(window.context) == (2, 2)


def test_old_request_without_mode_read_keeps_three_json_bytes(cement_context, monkeypatch):
    import json
    from sqlalchemy import text
    value = request()
    result = cement_context.application.evaluate(value)
    query = text("SELECT request_json,result_json,rule_snapshot_json FROM evaluations")
    with cement_context.database.engine.begin() as connection:
        raw = json.loads(connection.execute(query).one()[0])
        for line in raw["cement_lines"]:
            line.pop("clinker_ratio_mode", None)
        connection.execute(text("UPDATE evaluations SET request_json=:raw"), {"raw": json.dumps(raw, ensure_ascii=False)})
        before = tuple(connection.execute(query).one())
    def forbidden(*args, **kwargs):
        raise AssertionError("历史读取不得重算")
    monkeypatch.setattr(cement_context.evaluation_service.engine, "evaluate", forbidden)
    loaded = cement_context.application.get_evaluation(result.evaluation_id)
    assert loaded[0].cement_lines[0].clinker_ratio_mode == "manual"
    assert cement_context.application.get_report_view(result.evaluation_id)
    with cement_context.database.engine.connect() as connection:
        assert tuple(connection.execute(query).one()) == before
