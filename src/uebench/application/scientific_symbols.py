"""跨渠道科学符号排版；仅识别批准的符号，不改机器字段或数值。"""
from html import escape
import re

# 标准接入时按批准映射扩展；大小写及多字母角标必须完整保留。
_SYMBOL = re.compile(r"(?<![A-Za-z0-9_])([EeWwPQm])_(shx|sh|sg|he|fm|fz|fc|BM|idw|H|d|s|h|m|g|i|0)(?![A-Za-z0-9_])")


def symbol_runs(value):
    """返回 (文字, 是否下标)，供 Qt/Word 共用。"""
    text = "" if value is None else str(value)
    start = 0
    for match in _SYMBOL.finditer(text):
        if match.start() > start:
            yield text[start:match.start()], False
        yield match[1], False
        yield match[2], True
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
