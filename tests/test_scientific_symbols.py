"""实际Qt/Word角标属性、复合符号及用户文本转义。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtGui import QTextDocument, QTextCharFormat
from uebench.application.scientific_symbols import symbols_html, symbol_runs, append_symbol_runs


COKE_FORMULAS = "E′_JT = E_JT + Δe_0；Δe_0 = Σ f_i(x′_i−x_i)；(e_yl + e_jg − e_jt − e_jf − e_yr) ÷ p_JT；V_d、M_t"
COKE_SUBSCRIPTS = ["JT", "JT", "0", "0", "i", "i", "i", "yl", "jg", "jt", "jf", "yr", "JT", "d", "t"]
SYMBOL_CASES = [("P_H Q_idw m_i", ["H", "idw", "i"]), (COKE_FORMULAS, COKE_SUBSCRIPTS)]


def test_symbols_preserve_multi_letter_case_and_escape():
    source = '<b> E_d P_H Q_idw m_i P_shx unknown_key E_unknown'
    rendered = symbols_html(source)
    assert rendered == '&lt;b&gt; E<sub>d</sub> P<sub>H</sub> Q<sub>idw</sub> m<sub>i</sub> P<sub>shx</sub> unknown_key E_unknown'
    assert ''.join(text for text, _ in symbol_runs(source)) == source.replace('E_d', 'Ed').replace('P_H', 'PH').replace('Q_idw', 'Qidw').replace('m_i', 'mi').replace('P_shx', 'Pshx')


def test_coke_symbols_preserve_primes_and_leave_machine_fields_intact():
    assert symbols_html("E′_JT x′_i e_JT p_jt V_t coke_e_jt e_jt_raw E_actual") == (
        "E′<sub>JT</sub> x′<sub>i</sub> e_JT p_jt V_t coke_e_jt e_jt_raw E_actual"
    )


@pytest.mark.parametrize("formula, expected", SYMBOL_CASES)
def test_qt_uses_real_subscript_for_complete_suffix(formula, expected):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    document = QTextDocument()
    document.setHtml(symbols_html(formula))
    found = []
    block = document.begin()
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.charFormat().verticalAlignment() == QTextCharFormat.VerticalAlignment.AlignSubScript:
            found.append(fragment.text())
        iterator += 1
    assert found == expected


@pytest.mark.parametrize("formula, expected", SYMBOL_CASES)
def test_word_uses_real_subscript_for_complete_suffix(formula, expected, tmp_path):
    from docx import Document
    document = Document()
    paragraph = document.add_paragraph()
    append_symbol_runs(paragraph, formula)
    path = tmp_path / "symbols.docx"
    document.save(path)
    reopened = Document(path).paragraphs[0]
    assert [run.text for run in reopened.runs if run.font.subscript] == expected
