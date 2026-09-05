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

def test_source_extractors_allow_a_configured_source_directory() -> None:
    source_scripts = [
        ROOT / "tools" / name
        for name in (
            "build_gb29141_2024.py",
            "update_scope_46.py",
            "refine_gb29435_2025_rule.py",
            "refine_gb30185_rule.py",
            "refine_gb30530_rule.py",
            "refine_gb31823_rule.py",
        )
    ]
    for path in source_scripts:
        text = path.read_text(encoding="utf-8")
        assert "UEBENCH_SOURCE_DIR" in text, path.name

def test_review_tool_never_defaults_to_historical_scope() -> None:
    text = (ROOT / "tools" / "review_confirmed_rules.py").read_text(encoding="utf-8")
    assert 'data_dir / "scope-65.json"' not in text
    assert "不会默认使用历史scope-65.json" in text
