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
    assert 'data_dir / "scope-65.json"' not in text

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


def test_draft_generator_replays_all_remaining_specialized_refinements() -> None:
    text = (ROOT / "tools" / "prepare_next_scope_drafts.py").read_text(encoding="utf-8")
    expected = {
        "GB 32032-2024": 'refine_complex(data_dir, "GB 32032-2024")',
        "GB 32044-2015": 'refine_gb32044(data_dir)',
        "GB 32051-2024": 'refine_simple(data_dir, "GB 32051-2024")',
        "GB 36887-2018": 'refine_gb36887(data_dir)',
        "GB 36890-2018": 'refine_gb36890(data_dir)',
        "GB 40877-2021": 'refine_gb40877(data_dir)',
        "GB 40878-2021": 'refine_gb40878(data_dir)',
        "GB 45246-2025": 'refine_simple(data_dir, "GB 45246-2025")',
    }
    for number, marker in expected.items():
        assert marker in text, f"{number} 的专项精化脚本未接入草案生成器"
def test_release_build_checks_unified_development_library() -> None:
    text = (ROOT / "scripts" / "build_release.ps1").read_text(encoding="utf-8")
    assert "tools\\build_development_manifest.py" in text
    assert "--check" in text
def test_release_sync_checks_unified_development_library() -> None:
    text = (ROOT / "scripts" / "sync_release.ps1").read_text(encoding="utf-8")
    assert "tools\\build_development_manifest.py" in text
    assert "--check" in text
