from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_refinement_tools_do_not_default_to_historical_scope() -> None:
    tools = ROOT / "tools"
    candidates = sorted(tools.glob("refine_*.py"))
    assert candidates
    for path in candidates:
        text = path.read_text(encoding="utf-8")
        assert "work/next-scope-65/data" not in text, path.name


def test_draft_generator_defaults_to_canonical_rebuild_workspace() -> None:
    text = (ROOT / "tools" / "prepare_next_scope_drafts.py").read_text(encoding="utf-8")
    assert 'default=ROOT / "work" / "next-scope-63"' in text