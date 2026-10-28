"""真实子进程验证候选自检等待、失败关闭和中文路径隔离。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

from tools.run_candidate_self_check import SelfCheckError, run_self_check


# Windows venv python.exe 是转发器；使用实际解释器才能验证被 Popen 拥有的 PID。
PROBE_PYTHON = getattr(sys, '_base_executable', sys.executable)


PROBE = r'''
import argparse, json, os, pathlib, sys, time
parser = argparse.ArgumentParser()
parser.add_argument('--self-check', action='store_true')
parser.add_argument('--data-dir')
parser.add_argument('--output')
args = parser.parse_args()
mode = pathlib.Path(__file__).stem
data = pathlib.Path(args.data_dir)
data.joinpath('probe.txt').write_text('isolated', encoding='utf-8')
pathlib.Path(os.environ['TEMP']).joinpath('temp.txt').write_text('temporary')
print('probe stdout', flush=True)
print('probe stderr', file=sys.stderr, flush=True)
payload = {'schema': 'uebench.self-check-report', 'overall_status': 'passed',
           'frozen': True, 'failed_checks': [], 'checks': [],
           'observed': {'args': vars(args), 'cwd': os.getcwd(),
                        'environment': {k: os.environ[k] for k in ['TEMP','TMP','UEBENCH_DATA_DIR']}}}
report = pathlib.Path(args.output)
if mode == 'timeout':
    data.parent.parent.joinpath('probe-pid.txt').write_text(str(os.getpid()))
    time.sleep(30)
elif mode == 'nonzero':
    report.write_text(json.dumps(payload), encoding='utf-8')
    sys.exit(7)
elif mode == 'missing':
    pass
elif mode == 'corrupt':
    report.write_text('{broken', encoding='utf-8')
else:
    if mode == 'schema': payload['schema'] = 'other'
    if mode == 'unfrozen': payload['frozen'] = False
    if mode == 'failed': payload['overall_status'] = 'failed'
    if mode == 'failed_checks': payload['failed_checks'] = ['bad']
    if mode == 'missing_failed_checks': payload.pop('failed_checks')
    time.sleep(0.2)  # 报告在进程退出前才落盘，不能只启动就视为通过。
    report.write_text(json.dumps(payload), encoding='utf-8')
'''


def probe(tmp_path: Path, mode: str) -> tuple[Path, list[str]]:
    root = tmp_path / '候选 中文 空格 & 路径'
    root.mkdir()
    script = root / f'{mode}.py'
    script.write_text(PROBE, encoding='utf-8')
    return root, [PROBE_PYTHON, str(script)]


def evidence(root: Path) -> Path:
    return next((root / 'work').glob('candidate-self-check-*'))


def test_waits_for_report_and_isolates_environment_without_mutating_parent(tmp_path, monkeypatch):
    root, command = probe(tmp_path, 'success')
    for key in ('TEMP', 'TMP', 'UEBENCH_DATA_DIR'):
        monkeypatch.setenv(key, str(tmp_path / 'parent data must not be used'))
    original = {key: os.environ[key] for key in ('TEMP', 'TMP', 'UEBENCH_DATA_DIR')}
    report = run_self_check(command, root, timeout_seconds=10)
    payload = json.loads(report.read_text(encoding='utf-8'))
    observed = payload['observed']
    assert Path(observed['cwd']) == root
    assert observed['args']['self_check'] is True
    assert Path(observed['args']['output']) == report
    assert observed['environment']['UEBENCH_DATA_DIR'] == observed['args']['data_dir']
    assert observed['environment']['TEMP'] == observed['environment']['TMP']
    for value in observed['environment'].values():
        assert Path(value).is_relative_to(report.parent / 'scratch')
    assert {key: os.environ[key] for key in original} == original
    assert not (report.parent / 'scratch').exists()
    assert not (tmp_path / 'parent data must not be used').exists()
    assert 'probe stdout' in (report.parent / 'stdout.log').read_text()
    assert 'probe stderr' in (report.parent / 'stderr.log').read_text()
    assert json.loads((report.parent / 'runner.json').read_text(encoding='utf-8'))['status'] == 'passed'


def test_nonzero_exit_cannot_be_overridden_by_a_passing_report(tmp_path):
    root, command = probe(tmp_path, 'nonzero')
    with pytest.raises(SelfCheckError, match='7'):
        run_self_check(command, root, timeout_seconds=10)
    run = evidence(root)
    assert json.loads((run / 'runner.json').read_text(encoding='utf-8'))['returncode'] == 7
    assert (run / 'report.json').exists()
    assert (run / 'scratch' / 'data' / 'probe.txt').exists()


def test_timeout_kills_only_owned_process_and_preserves_evidence(tmp_path):
    root, command = probe(tmp_path, 'timeout')
    unrelated = subprocess.Popen([PROBE_PYTHON, '-c', 'import time; time.sleep(30)'])
    started = time.monotonic()
    try:
        with pytest.raises(SelfCheckError, match='超时'):
            run_self_check(command, root, timeout_seconds=2)
        assert time.monotonic() - started < 10
        assert unrelated.poll() is None
        run = evidence(root)
        outcome = json.loads((run / 'runner.json').read_text(encoding='utf-8'))
        assert outcome['timed_out'] is True
        assert outcome['returncode'] != 0
        assert int((run / 'probe-pid.txt').read_text()) == outcome['pid']
        assert (run / 'scratch').exists()
    finally:
        unrelated.kill()
        unrelated.wait(timeout=10)


@pytest.mark.parametrize('mode', ['missing', 'corrupt', 'schema', 'unfrozen', 'failed', 'failed_checks', 'missing_failed_checks'])
def test_missing_corrupt_or_unpassed_reports_fail_closed(tmp_path, mode):
    root, command = probe(tmp_path, mode)
    with pytest.raises(SelfCheckError):
        run_self_check(command, root, timeout_seconds=10)
    assert json.loads((evidence(root) / 'runner.json').read_text(encoding='utf-8'))['status'] == 'failed'


def test_each_attempt_keeps_distinct_evidence(tmp_path):
    root, command = probe(tmp_path, 'success')
    first = run_self_check(command, root, timeout_seconds=10)
    second = run_self_check(command, root, timeout_seconds=10)
    assert first != second
    assert first.exists() and second.exists()


@pytest.mark.parametrize('shell_name', ['pwsh', 'powershell'])
@pytest.mark.parametrize('io_encoding', [None, 'cp936'])
def test_powershell_pipeline_decodes_chinese_report_path_without_utf8_environment(
    tmp_path, shell_name, io_encoding
):
    shell = shutil.which(shell_name)
    if shell is None:
        pytest.skip(f'{shell_name} 不可用')
    root, command = probe(tmp_path, 'success')
    repo = Path(__file__).resolve().parents[1]
    # CLI 固定接收 EXE，不接收脚本参数。测试只将子进程命令替换为真实 Python 探针；
    # main() 的参数解析、报告验证、stdout JSON 协议和 PowerShell 管道均实际执行。
    shim = root / '进程探针入口.py'
    shim.write_text(
        'import sys\n'
        f'sys.path.insert(0, {str(repo)!r})\n'
        'import tools.run_candidate_self_check as runner\n'
        'original = runner.run_self_check\n'
        'def run_probe(command, project_root, *, timeout_seconds):\n'
        f'    return original({command!r}, project_root, timeout_seconds=timeout_seconds)\n'
        'runner.run_self_check = run_probe\n'
        'raise SystemExit(runner.main())\n',
        encoding='utf-8',
    )
    script = root / '管道集成.ps1'
    # 与正式脚本相同的 JSON 解码表达式，验证得到的路径可 Test-Path 且报告可读。
    script.write_text(r'''
param($PythonExe, $Shim, $ProjectRoot)
$ErrorActionPreference = 'Stop'
$SelfCheckOutput = (& $PythonExe $Shim --exe $PythonExe --project-root $ProjectRoot --timeout-seconds 10)
if ($LASTEXITCODE -ne 0) { throw 'runner failed' }
if (($SelfCheckOutput -join '') -match '[^\x00-\x7f]') { throw 'stdout must be ASCII' }
$SelfCheckReport = ([string](($SelfCheckOutput -join [Environment]::NewLine) | ConvertFrom-Json).report_path).Trim()
if (-not (Test-Path -LiteralPath $SelfCheckReport -PathType Leaf)) { throw 'report path corrupted' }
$report = Get-Content -LiteralPath $SelfCheckReport -Raw -Encoding UTF8 | ConvertFrom-Json
if ($report.schema -ne 'uebench.self-check-report' -or $report.overall_status -ne 'passed') { throw 'report unreadable' }
Write-Output 'PIPELINE_PASS'
''', encoding='utf-8-sig')
    environment = os.environ.copy()
    environment.pop('PYTHONUTF8', None)
    environment.pop('PYTHONIOENCODING', None)
    if io_encoding is not None:
        environment['PYTHONIOENCODING'] = io_encoding
    result = subprocess.run(
        [shell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
         str(script), PROBE_PYTHON, str(shim), str(root)],
        env=environment, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, repr(result.stderr)
    assert b'PIPELINE_PASS' in result.stdout
    assert (evidence(root) / 'report.json').exists()
