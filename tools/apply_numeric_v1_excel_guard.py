from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


path = ROOT / "src/uebench/infrastructure/excel.py"
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''def _decimal_from_cell(value, *, sheet: str, cell: str, issues: list[ImportIssue]) -> Decimal | None:
    if value is None or value == "":
        issues.append(ImportIssue(severity="error", sheet=sheet, cell=cell, message="数值不能为空"))
        return None
    try:
        return Decimal(str(value))
''',
    '''def _decimal_from_cell(value, *, sheet: str, cell: str, issues: list[ImportIssue]) -> Decimal | None:
    if value is None or value == "":
        issues.append(ImportIssue(severity="error", sheet=sheet, cell=cell, message="数值不能为空"))
        return None
    if isinstance(value, float):
        issues.append(
            ImportIssue(
                severity="error",
                sheet=sheet,
                cell=cell,
                message=(
                    "正式数值不能使用 XLSX 数值单元格导入：openpyxl 已将其物化为二进制浮点。"
                    "请将单元格设为文本并录入十进制字符串。"
                ),
            )
        )
        return None
    try:
        return Decimal(str(value))
''',
    "decimal cell float guard",
)
text = replace_once(
    text,
    '''            "所有数值使用十进制，不要录入带单位的文本。",
''',
    '''            "正式数值请使用文本格式录入十进制字符串（模板数值输入列已设为文本）；不要使用 XLSX 浮点数值单元格，也不要录入带单位的文本。",
''',
    "template instruction",
)
text = replace_once(
    text,
    '''        for _ in range(20):
            sheet.append(["", "", "", "", ""])
        widths = [28, 34, 20, 18, 48]
''',
    '''        for _ in range(20):
            sheet.append(["", "", "", "", ""])
        for row in range(2, 22):
            sheet.cell(row=row, column=3).number_format = "@"
        widths = [28, 34, 20, 18, 48]
''',
    "generic text format",
)
text = replace_once(
    text,
    '''        for _ in range(50):
            sheet.append(["", "", "", "input", "", "", "", "", 1, ""])
        validation = DataValidation(type="list", formula1='"input,output"', allow_blank=False)
''',
    '''        for _ in range(50):
            sheet.append(["", "", "", "input", "", "", "", "", 1, ""])
        for row in range(2, 52):
            for column in (5, 7, 9):
                sheet.cell(row=row, column=column).number_format = "@"
        validation = DataValidation(type="list", formula1='"input,output"', allow_blank=False)
''',
    "energy text format",
)
text = replace_once(
    text,
    '''        for _ in range(30):
            sheet.append(["", "", "", "", "", 1, "是", ""])
        validation = DataValidation(type="list", formula1='"是,否"', allow_blank=False)
''',
    '''        for _ in range(30):
            sheet.append(["", "", "", "", "", 1, "是", ""])
        for row in range(2, 32):
            for column in (4, 6):
                sheet.cell(row=row, column=column).number_format = "@"
        validation = DataValidation(type="list", formula1='"是,否"', allow_blank=False)
''',
    "production text format",
)
text = replace_once(
    text,
    '''                value = _excel_value(row[2].value)
                if value is None or value == "":
''',
    '''                raw_value = row[2].value
                if isinstance(raw_value, float):
                    issues.append(
                        ImportIssue(
                            severity="error",
                            sheet=sheet_name,
                            cell=f"C{row_number}",
                            message=(
                                "正式输入不能使用 XLSX 数值单元格：openpyxl 已将其物化为二进制浮点。"
                                "请将单元格设为文本并录入十进制字符串。"
                            ),
                        )
                    )
                    continue
                value = _excel_value(raw_value)
                if value is None or value == "":
''',
    "generic input float guard",
)
path.write_text(text, encoding="utf-8")
print("Excel authoritative binary-float guard applied successfully.")
