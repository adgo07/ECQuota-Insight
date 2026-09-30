from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_UI = ROOT / "tests" / "test_ui.py"


def main() -> None:
    text = TEST_UI.read_text(encoding="utf-8")
    replacements = {
        '    assert "6.272000 <= 7.000000" in window.gb29446_explanation.text()\n':
            '    assert "判级比较：6.272 <= 7；结果：2级" in window.gb29446_explanation.text()\n',
        '    assert "显示位数不参与判级" in window.gb29446_explanation.text()\n':
            '    assert "显示位数仅用于展示，不参与判级" in window.gb29446_explanation.text()\n',
    }
    changed = text
    for old, new in replacements.items():
        if old not in changed:
            raise SystemExit(f"expected UI regression assertion not found: {old.strip()}")
        changed = changed.replace(old, new, 1)
    TEST_UI.write_text(changed, encoding="utf-8")


if __name__ == "__main__":
    main()
