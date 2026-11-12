"""实际Qt/Word角标属性、复合符号及用户文本转义。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QTextDocument, QTextCharFormat
from uebench.application.scientific_symbols import symbols_html, symbol_runs, append_symbol_runs


def test_symbols_preserve_multi_letter_case_and_escape():
    source = '<b> E_d P_H Q_idw m_i P_shx unknown_key E_unknown'
    rendered = symbols_html(source)
    assert rendered == '&lt;b&gt; E<sub>d</sub> P<sub>H</sub> Q<sub>idw</sub> m<sub>i</sub> P<sub>shx</sub> unknown_key E_unknown'
    assert ''.join(text for text, _ in symbol_runs(source)) == source.replace('E_d', 'Ed').replace('P_H', 'PH').replace('Q_idw', 'Qidw').replace('m_i', 'mi').replace('P_shx', 'Pshx')


def test_qt_uses_real_subscript_for_complete_suffix():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    document = QTextDocument()
    document.setHtml(symbols_html('P_H Q_idw m_i'))
    found = []
    block = document.begin()
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.charFormat().verticalAlignment() == QTextCharFormat.VerticalAlignment.AlignSubScript:
            found.append(fragment.text())
        iterator += 1
    assert found == ['H', 'idw', 'i']


def test_word_uses_real_subscript_for_complete_suffix():
    from docx import Document
    document = Document()
    paragraph = document.add_paragraph()
    append_symbol_runs(paragraph, 'P_H Q_idw m_i')
    assert [(run.text, run.font.subscript) for run in paragraph.runs if run.font.subscript] == [('H', True), ('idw', True), ('i', True)]
