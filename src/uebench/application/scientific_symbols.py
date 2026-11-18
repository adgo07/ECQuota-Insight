"""跨渠道科学符号排版；仅识别批准的符号，不改机器字段或数值。"""
from html import escape
import re

# 大小写及多字母角标必须完整保留。焦炭符号取自已核对的 GB 21342—2025 式（1）至（3）及表2。
_COKE_SYMBOLS = r"e_(?:yl|jg|jt|jf|yr)|(?:E′?|p)_JT|Δe_0|(?:f|x′?)_i|V_d|M_t"
_COMMON_SYMBOLS = r"[EeWwPQm]_(?:shx|sh|sg|he|fm|fz|fc|BM|idw|H|d|s|h|m|g|i|0)"
_SYMBOL = re.compile(rf"(?<![A-Za-z0-9_])(?:{_COKE_SYMBOLS}|{_COMMON_SYMBOLS})(?![A-Za-z0-9_])")


def symbol_runs(value):
    """返回 (文字, 是否下标)，供 Qt/Word 共用。"""
    text = "" if value is None else str(value)
    start = 0
    for match in _SYMBOL.finditer(text):
        if match.start() > start:
            yield text[start:match.start()], False
        base, subscript = match[0].rsplit("_", 1)
        yield base, False
        yield subscript, True
        start = match.end()
    if start < len(text):
        yield text[start:], False


def symbols_html(value):
    return "".join(f"<sub>{escape(text)}</sub>" if sub else escape(text)
                   for text, sub in symbol_runs(value)).replace("\n", "<br>")


def append_symbol_runs(paragraph, value):
    for text, sub in symbol_runs(value):
        run = paragraph.add_run(text)
        if sub:
            run.font.subscript = True
