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


@pytest.mark.parametrize("bad", ["74.99", "", "NaN", "101"])
@pytest.mark.parametrize("mode", ["manual", "automatic"])
def test_request_cannot_override_calculated_ratio(cement_context, bad, mode):
    value = request()
    line = value.cement_lines[0]
    line.clinker_ratio_mode = mode
    put(line, "cement.clinker_percent", bad)
    before = value.model_dump_json()
    result = cement_context.application.evaluate(value)
    assert value.model_dump_json() == before
    saved = cement_context.application.get_evaluation(result.evaluation_id)
    assert Decimal(saved[0].cement_lines[0].inputs["cement.clinker_percent"].value) == 75
    assert saved[0].cement_lines[0].clinker_ratio_mode == "automatic"
    assert any(step.expression == "P_shx/P_s×100" and step.value == 75
               for item in result.results for step in item.calculation_trace)
    assert saved[1].model_dump() == result.model_dump()


def test_form_only_calculated_keyboard_and_line_isolation():
    from PySide6.QtTest import QTest
    app = QApplication.instance() or QApplication([])
    line, second = CementLineForm(), CementLineForm()
    try:
        field = line.fields["cement.clinker_percent"]
        line.fields["cement.clinker_consumption_t"].setText("1")
        line.fields["cement.production_t"].setText("3")
        assert field.isReadOnly() and field.text() == "33.33333333333333333333333333"
        field.setFocus()
        QTest.keyClicks(field, "99")
        assert field.text() == "33.33333333333333333333333333"
        assert not hasattr(line, "ratio_mode")
        assert second.fields["cement.clinker_percent"].text() == ""
        line.fields["cement.production_t"].setText("0")
        assert field.text() == "" and "大于0" in line.ratio_notice.text()
        line.fields["cement.production_t"].setText("2")
        assert field.text() == "50.0"
        line.load(line.collect())
        assert field.isReadOnly() and field.text() == "50.0"
        line.fields["cement.production_t"].setText("4")
        assert field.text() == "25.00"
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
        assert Decimal(widget.collect().inputs["cement.clinker_percent"].value) == 75
        assert original.inputs["cement.clinker_percent"].value == "76.00000000000000000000000001"
        assert widget.fields["cement.clinker_percent"].isReadOnly()
    finally:
        widget.close()
        app.processEvents()


def test_automatic_save_once_and_production_change_invalidates(window):
    line = window.cement_form.lines[0]
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
        row = connection.execute(query).one()
        old_result = json.loads(row[1])
        old_result["numeric_behavior_version"] = "gb16780-v1.2-full-value-v1"
        raw = json.loads(row[0])
        for line in raw["cement_lines"]:
            line.pop("clinker_ratio_mode", None)
        connection.execute(text("UPDATE evaluations SET request_json=:raw,result_json=:result"),
                           {"raw": json.dumps(raw, ensure_ascii=False), "result": json.dumps(old_result, ensure_ascii=False)})
        before = tuple(connection.execute(query).one())
    def forbidden(*args, **kwargs):
        raise AssertionError("历史读取不得重算")
    monkeypatch.setattr(cement_context.evaluation_service.engine, "evaluate", forbidden)
    loaded = cement_context.application.get_evaluation(result.evaluation_id)
    assert loaded[0].cement_lines[0].clinker_ratio_mode == "manual"
    assert loaded[1].numeric_behavior_version == "gb16780-v1.2-full-value-v1"
    assert cement_context.application.get_report_view(result.evaluation_id)
    with cement_context.database.engine.connect() as connection:
        assert tuple(connection.execute(query).one()) == before


@pytest.mark.parametrize("bad", [None, "", "NaN", "0", "-2"])
def test_new_requests_reject_invalid_quantity_even_with_plausible_g(cement_context, bad):
    value = request()
    line = value.cement_lines[0]
    put(line, "cement.clinker_percent", "75")
    if bad is None:
        line.inputs.pop("cement.production_t")
    else:
        put(line, "cement.production_t", bad)
    with pytest.raises(IncompleteCementEvaluationError):
        cement_context.application.evaluate(value)
    assert state(cement_context) == (0, 0)


def test_engine_uses_quantities_for_each_line_even_if_manual(cement_context):
    value = request()
    first = value.cement_lines[0]
    second = first.model_copy(deep=True)
    second.line_id = "independent-line"
    put(first, "cement.clinker_percent", "99")
    put(second, "cement.clinker_percent", "1")
    put(second, "cement.clinker_consumption_t", "1600")
    value.cement_lines.append(second)
    snapshot = cement_context.application.get_published_standard(value.standard_id)
    result = cement_context.evaluation_service.engine.evaluate(snapshot, value)
    for line_id, expected in [(first.line_id, Decimal(75)), (second.line_id, Decimal(80))]:
        steps = [step for item in result.results if item.line_id == line_id for step in item.calculation_trace
                 if step.expression == "P_shx/P_s×100"]
        assert steps and all(step.value == expected for step in steps)
