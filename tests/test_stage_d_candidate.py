"""候选必须隔离，默认生产入口与许可不扩张。"""
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from uebench.stage_d_candidate import CANDIDATE_STANDARD_IDS, MARKER, main, prepare_isolated_root
from uebench.application.evaluation_support import SUPPORTED_EVALUATION_STANDARD_IDS


def test_new_candidate_root_can_reopen_but_unmarked_data_cannot(tmp_path, monkeypatch):
    monkeypatch.delenv("UEBENCH_DATA_DIR", raising=False)
    root = prepare_isolated_root(tmp_path / "验收")
    (root / "uebench.sqlite3").write_bytes(b"candidate")
    assert prepare_isolated_root(root) == root
    copied = tmp_path / "copied"
    copied.mkdir()
    (copied / MARKER).write_text((root / MARKER).read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ValueError, match="标记无效"):
        prepare_isolated_root(copied)
    (tmp_path / "unmarked").mkdir()
    (tmp_path / "unmarked/user.txt").write_text("user")
    with pytest.raises(ValueError, match="未标识"):
        prepare_isolated_root(tmp_path / "unmarked")


def test_default_user_root_and_overlap_refused_even_with_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    for root in [tmp_path / "local/UEBench", tmp_path / "local", tmp_path / "local/UEBench/child"]:
        with pytest.raises(ValueError, match="重叠"):
            prepare_isolated_root(root)
    assert not (tmp_path / "local").exists()


def test_configured_existing_user_data_refused(tmp_path, monkeypatch):
    user = tmp_path / "configured"
    user.mkdir()
    (user / "uebench.sqlite3").write_bytes(b"user")
    monkeypatch.setenv("UEBENCH_DATA_DIR", str(user))
    with pytest.raises(ValueError, match="重叠"):
        prepare_isolated_root(user)
    assert (user / "uebench.sqlite3").read_bytes() == b"user"


def test_explicit_candidate_entry_uses_one_scope_and_leaves_default_fixed(tmp_path, monkeypatch):
    from uebench import main as application_main
    run = Mock(return_value=0)
    monkeypatch.setattr(application_main, "_run_desktop_application", run)
    assert main(["--data-dir", str(tmp_path / "candidate")]) == 0
    assert run.call_args.kwargs["evaluation_standard_ids"] == CANDIDATE_STANDARD_IDS
    assert run.call_args.kwargs["root"] == (tmp_path / "candidate").resolve()
    assert "Stage D" in run.call_args.kwargs["candidate_title"]
    assert SUPPORTED_EVALUATION_STANDARD_IDS == {"gb-29446-2019"}
    runtime = json.loads((tmp_path / "candidate/candidate-runtime.json").read_text(encoding="utf-8"))
    assert runtime["evaluation_standard_ids"] == ["gb-16780-2021", "gb-29446-2019"]
    with pytest.raises(SystemExit) as error:
        main([])
    assert error.value.code == 2


def test_candidate_ui_and_application_share_scope_while_default_refuses(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from uebench.bootstrap import create_context
    from uebench.ui.main_window import create_main_window
    from uebench.domain.models import EvaluationRequest, InputValue, InputMode
    def grinding_request():
        return EvaluationRequest(evaluation_date="2026-10-29", standard_id="gb-16780-2021", product_id="cement",
            input_mode=InputMode.DETAIL, inputs={
                "production_mode": InputValue(value="grinding_station"),
                "evaluation_period": InputValue(value="2025年"), "production_line_id": InputValue(value="A"),
                "cement_production_t": InputValue(value="1000", unit="t"),
                "grinding_electricity_kwh": InputValue(value="23000", unit="kW·h")})
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[1]
    context = create_context(tmp_path / "candidate", public_key_path=root / "src/uebench/resources/update_public_key.pem",
                             formal_standard_ids=CANDIDATE_STANDARD_IDS)
    default = None
    window = None
    try:
        context.application.reconcile_standard_library(root / "release/standard-packages")
        window = create_main_window(context, evaluation_standard_ids=CANDIDATE_STANDARD_IDS)
        assert window.open_evaluation_for_standard("gb-16780-2021")
        assert window.cement_panel.isHidden() is False
        assert "尚未正式支持" in window._support_label("gb-16780-2021")
        assert window._supports_evaluation("gb-21252-2023") is False
        result = context.application.evaluate(grinding_request())
        assert context.evaluations.get(result.evaluation_id) is not None
        default = create_context(tmp_path / "default", public_key_path=root / "src/uebench/resources/update_public_key.pem")
        default.application.reconcile_standard_library(root / "release/standard-packages")
        with pytest.raises(ValueError, match="尚未纳入正式评价范围"):
            default.application.evaluate(grinding_request())
        assert default.evaluations.count() == 0
    finally:
        if window:
            window.close()
        app.processEvents()
        context.database.dispose()
        if default:
            default.database.dispose()


def test_reopened_candidate_rejects_internal_junction_before_writes(tmp_path, monkeypatch):
    import os
    import subprocess
    monkeypatch.delenv("UEBENCH_DATA_DIR", raising=False)
    root = prepare_isolated_root(tmp_path / "candidate")
    outside = tmp_path / "outside"
    outside.mkdir()
    original_marker = (root / MARKER).read_bytes()
    target = root / "standards"
    if os.name == "nt":
        # One native shell, explicit fixed test paths; junction creation needs no admin.
        outcome = subprocess.run(["cmd", "/c", "mklink", "/J", str(target), str(outside)], capture_output=True)
        if outcome.returncode:
            pytest.skip("当前环境无法创建测试junction")
    else:
        try:
            target.symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip("当前环境无法创建测试symlink")
    try:
        with pytest.raises(ValueError, match="重解析点"):
            prepare_isolated_root(root)
        assert list(outside.iterdir()) == []
        assert (root / MARKER).read_bytes() == original_marker
    finally:
        if os.name == "nt":
            target.rmdir()  # remove the junction only, never its target
        else:
            target.unlink()


def test_readonly_probe_refuses_snapshot_drift_without_changing_database(tmp_path):
    import sqlite3
    from uebench.stage_d_smoke import digests, readback
    database = tmp_path / "uebench.sqlite3"
    original = ('original-input', 'original-result', 'original-rule')
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE evaluations (evaluation_id TEXT, request_json TEXT, result_json TEXT, rule_snapshot_json TEXT)')
        connection.execute('INSERT INTO evaluations VALUES (?,?,?,?)', ('id', 'changed-input', *original[1:]))
    (tmp_path / 'smoke-ledger.json').write_text(json.dumps({'records':[{'evaluation_id':'id','snapshot_digests':digests(original)}]}), encoding='utf-8')
    before = database.read_bytes()
    with pytest.raises(RuntimeError, match='字节漂移'):
        readback(tmp_path)
    assert database.read_bytes() == before
    assert not (tmp_path / 'smoke-readback.json').exists()


def test_probe_checks_survive_optimized_python():
    import subprocess
    import sys
    outcome = subprocess.run([sys.executable, '-O', '-c',
        'from uebench.stage_d_smoke import require; require(False, "optimized guard")'], capture_output=True)
    assert outcome.returncode != 0
    assert b'optimized guard' in outcome.stderr
