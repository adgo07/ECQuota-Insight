from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0 and new in text:
        print(f"already patched: {path}")
        return
    if count != 1:
        raise SystemExit(f"expected exactly one legacy block in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched: {path}")


replace_once(
    Path("src/uebench/ui/main_window.py"),
    '''        comparison_line = (\n            f"判级比较：{comparison_step.expression}；结果：{grade_label}"\n            if comparison_step is not None\n            else f"判级比较：计算值和阈值分别 ROUND(..., 6) 后比较；正式结果：{grade_label}"\n        )\n        current_grade_line = (\n            f"{raw_value_line}\\n{comparison_line}\\n"\n            "判级时将计算值和阈值分别 ROUND(..., 6) 后比较；显示位数不参与判级。"\n        )''',
    '''        if comparison_step is not None:\n            comparison_expression = comparison_step.expression\n            if comparison_expression.startswith("numeric_behavior=") and "; " in comparison_expression:\n                comparison_expression = comparison_expression.split("; ", 1)[1]\n            comparison_line = f"判级比较：{comparison_expression}；结果：{grade_label}"\n        else:\n            comparison_line = f"判级比较：按未修约 Decimal 全值与阈值直接比较；正式结果：{grade_label}"\n        current_grade_line = (\n            f"{raw_value_line}\\n{comparison_line}\\n"\n            "正式判级使用未修约 Decimal 全值与阈值直接比较；显示位数仅用于展示，不参与判级。"\n        )''',
)

replace_once(
    Path("tests/test_ui.py"),
    '''def test_gb29446_six_place_boundary_explanation_matches_formal_grade(tmp_path: Path, monkeypatch) -> None:\n    application = QApplication.instance() or QApplication([])\n    context = create_context(tmp_path / "appdata")\n    context.standards.install(_gb29446_standard())\n    window = MainWindow(context)\n    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)\n    window.navigation.setCurrentRow(2)\n    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("跳汰、浮选联合"))\n    window.gb29446_electricity.setText("5.0000004")\n    window.gb29446_raw_coal.setText("1")\n    window.calculate_evaluation()\n\n    assert window.gb29446_result_grade.text() == "1级"\n    assert "原始计算值（未修约）：5.0000004 kW·h/t" in window.gb29446_explanation.text()\n    assert (\n        "ROUND(5.0000004, 6) = 5.000000；ROUND(5, 6) = 5.000000；"\n        "5.000000 <= 5.000000"\n    ) in window.gb29446_explanation.text()\n    assert "结果：1级" in window.gb29446_explanation.text()\n    assert "判级时将计算值和阈值分别 ROUND(..., 6) 后比较" in window.gb29446_explanation.text()\n    assert "显示位数不参与判级" in window.gb29446_explanation.text()\n    assert "未舍入的计算值" not in window.gb29446_explanation.text()\n\n    window.close()\n    context.database.dispose()''',
    '''def test_gb29446_full_value_boundary_explanation_matches_formal_grade(tmp_path: Path, monkeypatch) -> None:\n    application = QApplication.instance() or QApplication([])\n    context = create_context(tmp_path / "appdata")\n    context.standards.install(_gb29446_standard())\n    window = MainWindow(context)\n    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)\n    window.navigation.setCurrentRow(2)\n    window.gb29446_process.setCurrentIndex(window.gb29446_process.findData("跳汰、浮选联合"))\n    window.gb29446_electricity.setText("5.0000004")\n    window.gb29446_raw_coal.setText("1")\n    window.calculate_evaluation()\n\n    assert window.gb29446_result_grade.text() == "2级"\n    explanation = window.gb29446_explanation.text()\n    assert "原始计算值（未修约）：5.0000004 kW·h/t" in explanation\n    assert "判级比较：5.0000004 <= 7；结果：2级" in explanation\n    assert "正式判级使用未修约 Decimal 全值与阈值直接比较" in explanation\n    assert "显示位数仅用于展示，不参与判级" in explanation\n    assert "ROUND(" not in explanation\n    assert "numeric_behavior=" not in explanation\n\n    window.close()\n    context.database.dispose()''',
)
