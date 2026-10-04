from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STABLE_DOCUMENTS = [ROOT / name for name in ("TASK_STATE.md", "HANDOFF.md", "参考标准开发路线.md")]


def test_user_facing_documents_have_no_hidden_control_characters() -> None:
    documents = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md")), *STABLE_DOCUMENTS]
    assert documents
    for path in documents:
        content = path.read_text(encoding="utf-8")
        assert not any(char in content for char in ("\t", "\x00", "\x0b", "\x0c")), path
    for path in STABLE_DOCUMENTS:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            assert line == line.rstrip(), (path, number)


#: Recognised lifecycle states for a stage.  ``IN PROGRESS / RELEASE CANDIDATE``
#: was added in ECQ-RS05: a release-candidate phase is genuinely neither DONE nor
#: NOT STARTED, and the RS05 mandate requires exactly this wording in the stable
#: documents.  Keeping it in one place preserves the cross-document consistency
#: check that is the real value of this test.
_STATE = r"(DONE|NOT STARTED|PARTIAL|BLOCKED|IN PROGRESS / RELEASE CANDIDATE)"


def _stage_states(content: str) -> dict[str, str]:
    states = {}
    for line in content.splitlines():
        table = re.match(r"^\| (RS0[1-6]) \| \x60" + _STATE + r"\x60 \|", line)
        flow = re.match(r"^(?:→ )?(ECQ-GOV01|RS0[1-6]) .*?\s+" + _STATE + r"(?:\s|$)", line)
        match = table or flow
        if match:
            stage, state = match.groups()
            assert stage not in states or states[stage] == state
            states[stage] = state
    if "ECQ-GOV01" not in states and re.search(r"ECQ-GOV01.*?DONE", content):
        states["ECQ-GOV01"] = "DONE"
    return states


def test_three_stable_documents_have_consistent_stage_states() -> None:
    by_document = {path.name: _stage_states(path.read_text(encoding="utf-8")) for path in STABLE_DOCUMENTS}
    expected_keys = {"ECQ-GOV01", *(f"RS0{i}" for i in range(1, 7))}
    for name, stages in by_document.items():
        assert set(stages) == expected_keys, (name, stages)
    assert len({tuple(sorted(stages.items())) for stages in by_document.values()}) == 1, by_document
    for path in STABLE_DOCUMENTS:
        content = path.read_text(encoding="utf-8")
        assert not re.search(r"等待独立验收|等待合并|不合并 PR", content), path
