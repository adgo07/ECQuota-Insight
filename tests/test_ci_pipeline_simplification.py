"""ECQ-RS05 M2 §一/§二 —— CI 去重复与 Candidate 单一入口的可验证约束。

这些断言直接读 workflow 与构建脚本的源码文本，是 M2 收敛目标的回归网：
新增一个偷偷跑第二次 full suite 的 workflow、把 Candidate 构建重新挂到每个 PR、
或者再引入第二个 Artifact Gate 执行点，都必须在这里失败。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SCRIPTS = ROOT / "scripts"

#: A literal full-suite invocation: ``pytest -q -ra`` with no explicit test path.
_FULL_SUITE_RE = "python -m pytest -q -ra -p no:cacheprovider --basetemp"

#: An actual ``env:`` binding (YAML key), not a mention inside a message.
_ARTIFACT_DIR_BINDING_RE = re.compile(r"^\s*UEBENCH_ARTIFACT_DIR\s*:", re.MULTILINE)

#: An actual Artifact Gate execution (a pytest invocation), not a mention.
_ARTIFACT_GATE_RUN_RE = "python -m pytest tests/test_release_artifacts.py"


def _workflow_texts() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(WORKFLOWS.glob("*.yml"))}


def _without_comments(text: str) -> str:
    """Drop ``#`` comment lines so prose about a removed pattern is not a hit."""

    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _trigger_block(text: str) -> str:
    """Return the ``on:`` block body (the workflow's triggers only)."""

    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("on:"))
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if line and not line[0].isspace():
            break
        block.append(line)
    return "\n".join(block)


def _pull_request_workflows() -> dict[str, str]:
    return {
        name: text
        for name, text in _workflow_texts().items()
        if "pull_request:" in _trigger_block(text)
    }


def test_pull_request_gate_setup_is_discoverable() -> None:
    texts = _workflow_texts()
    assert set(texts) == {
        "numeric-v1-adoption.yml",
        "pull-request-gate.yml",
        "qzc-n01-a.yml",
        "windows-release-candidate.yml",
    }, sorted(texts)


def test_every_pull_request_workflow_cancels_superseded_runs() -> None:
    """同一 PR 新 Head 推送后，旧 Head 的运行必须被取消。"""

    pr_workflows = _pull_request_workflows()
    assert pr_workflows, "至少应有一个 pull_request workflow"
    for name, text in pr_workflows.items():
        assert "concurrency:" in text, f"{name} 缺少 concurrency"
        assert "cancel-in-progress: true" in text, f"{name} 未启用 cancel-in-progress"


def test_exactly_one_pull_request_workflow_runs_the_literal_full_suite() -> None:
    """普通 PR 只允许一条严格的 literal full suite。"""

    pr_workflows = _pull_request_workflows()
    runners = [name for name, text in pr_workflows.items() if _FULL_SUITE_RE in text]
    assert runners == ["pull-request-gate.yml"], runners
    assert pr_workflows["pull-request-gate.yml"].count(_FULL_SUITE_RE) == 1


def test_no_pull_request_workflow_uses_continue_on_error() -> None:
    """不得再用 continue-on-error 先跑一次、随后无条件重跑一次。"""

    for name, text in _pull_request_workflows().items():
        assert "continue-on-error" not in _without_comments(text), (
            f"{name} 仍在使用 continue-on-error"
        )


def test_numeric_special_gates_still_run_but_no_extra_full_suite() -> None:
    """Frozen Numeric v1 / N01-A 专项必须继续真实执行，但不再各自重复 full suite。"""

    texts = _workflow_texts()
    numeric = texts["numeric-v1-adoption.yml"]
    assert "tests/conformance/numeric/test_ecquota_numeric_v1.py" in numeric
    assert "tests/pilots/numeric/test_qzc_n01_a.py" in numeric
    pilot = texts["qzc-n01-a.yml"]
    assert "tests/pilots/numeric/test_qzc_n01_a.py" in pilot
    assert "tools/qzc_n01_a_excel_ingress_probe.py" in pilot
    for name in ("numeric-v1-adoption.yml", "qzc-n01-a.yml"):
        assert _FULL_SUITE_RE not in texts[name], f"{name} 不应再跑 full suite"


def test_candidate_workflow_is_manual_only_and_not_triggered_by_pull_requests() -> None:
    """Windows Release Candidate 不再对每个普通 PR 自动完整构建。"""

    candidate = _workflow_texts()["windows-release-candidate.yml"]
    trigger = _trigger_block(candidate)
    assert "pull_request:" not in trigger, "Candidate 构建不得再挂到普通 PR 上"
    assert "workflow_dispatch:" in trigger
    # provenance / 精确 SHA / source_dirty=false / payload identity 等保护必须保留。
    for kept in (
        "release-build-info.json",
        "ACTIVE-CANDIDATE.json",
        "payload_tree_sha256",
        "source_dirty",
    ):
        assert kept in candidate, f"Candidate workflow 不应删掉 {kept} 交叉检查"


def test_artifact_gate_has_exactly_one_authoritative_execution_point() -> None:
    """Artifact Gate 只在唯一正式 Candidate 构建入口里执行一次。"""

    candidates = sorted(SCRIPTS.glob("*.ps1"))
    gate_runners = [
        path.name
        for path in candidates
        if "test_release_artifacts.py" in path.read_text(encoding="utf-8")
    ]
    assert gate_runners == ["build_candidate.ps1"], gate_runners

    builder = (SCRIPTS / "build_candidate.ps1").read_text(encoding="utf-8")
    assert "UEBENCH_ARTIFACT_DIR" in builder, "构建脚本必须自己启用 Artifact Gate"
    assert "Artifact Gate 未通过" in builder, "Artifact Gate 失败必须让构建整体失败"

    # workflow 也不得再对同一个 Candidate 重跑一次同样的 Gate（按真实绑定/调用判断，
    # 不把说明文字里提到环境变量名当成执行）。
    for name, text in _workflow_texts().items():
        assert not _ARTIFACT_DIR_BINDING_RE.search(text), f"{name} 不应再单独执行 Artifact Gate"
        assert _ARTIFACT_GATE_RUN_RE not in text, f"{name} 不应再单独执行 Artifact Gate"


def test_legacy_release_scripts_are_marked_deprecated_in_favour_of_the_single_entry() -> None:
    """普通维护者只需要知道一个 Candidate build 入口。"""

    for name in ("build_release.ps1", "sync_release.ps1"):
        text = (SCRIPTS / name).read_text(encoding="utf-8")
        assert "DEPRECATED" in text, f"{name} 必须明确标注已弃用"
        assert "build_candidate.ps1" in text, f"{name} 必须指向唯一正式入口"
