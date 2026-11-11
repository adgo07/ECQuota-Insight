"""水泥报告写入器；只消费应用层保存视图，不读取规则或运行计算器。"""
import os
from pathlib import Path
import re
import tempfile


def _text(paragraph, text):
    for part in re.split(r"([EeWwPQ]_(?:shx|sh|sg|he|fm|fz|fc|BM|idw|s|h|m|g|0))", str(text)):
        if re.fullmatch(r"[EeWwPQ]_[A-Za-z0-9]+", part):
            base, sub = part.split("_", 1)
            paragraph.add_run(base)
            paragraph.add_run(sub).font.subscript = True
        elif part:
            paragraph.add_run(part)


def write_cement_report(view, path):
    from docx import Document
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(1.6)
    section.left_margin = section.right_margin = Cm(1.9)
    for name in ("Normal", "Title", "Heading 1", "Heading 2"):
        style = document.styles[name]
        style.font.name = "Microsoft YaHei"
        style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.size = Pt(15 if name == "Title" else 11 if name.startswith("Heading") else 9)
        style.paragraph_format.space_after = Pt(4 if name != "Normal" else 2)
        style.paragraph_format.space_before = Pt(6 if name.startswith("Heading") else 0)
        if style._element.pPr is not None:
            borders = style._element.pPr.find(qn("w:pBdr"))
            if borders is not None:
                style._element.pPr.remove(borders)
    title = document.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _text(title, view.title)

    def table(headers, rows, widths):
        output = document.add_table(rows=1, cols=len(headers))
        output.style = "Table Grid"
        output.alignment = WD_TABLE_ALIGNMENT.CENTER
        output.autofit = False
        for col, width in zip(output.columns, widths, strict=True):
            col.width = Cm(width)
        for cell, label in zip(output.rows[0].cells, headers, strict=True):
            _text(cell.paragraphs[0], label)
            shade = OxmlElement("w:shd")
            shade.set(qn("w:fill"), "EAF1F7")
            cell._tc.get_or_add_tcPr().append(shade)
            for run in cell.paragraphs[0].runs:
                run.bold = True
        repeat = OxmlElement("w:tblHeader")
        output.rows[0]._tr.get_or_add_trPr().append(repeat)
        for values in rows:
            row = output.add_row()
            for cell, value in zip(row.cells, values, strict=True):
                _text(cell.paragraphs[0], value)
        for row in output.rows:
            row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
            for cell, width in zip(row.cells, widths, strict=True):
                cell.width = Cm(width)
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.keep_with_next = False
                    paragraph.paragraph_format.space_after = Pt(3)
                    paragraph.paragraph_format.space_before = Pt(3)
        borders = OxmlElement("w:tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            item = OxmlElement("w:" + side)
            for attr, value in (("val", "single"), ("sz", "4"), ("color", "D9D9D9")):
                item.set(qn("w:" + attr), value)
            borders.append(item)
        output._tbl.tblPr.append(borders)
        document.add_paragraph().paragraph_format.space_after = Pt(0)
        return output

    document.add_heading("评价信息", level=1)
    table(("项目", "保存时信息"), ((f.label, f"{f.value} {f.unit}".strip()) for f in view.information), (4.5, 12.7))
    for line in view.lines:
        document.add_heading(line.name, level=1)
        document.add_paragraph("生产模式：" + line.mode)
        table(("指标", "实际值", "等级", "基准上限\n1 / 2 / 3级", "有效上限\n1 / 2 / 3级"),
              ((m.name, f"{m.actual} {m.unit}", m.grade,
                " / ".join(f.value for f in m.base_thresholds) or "—",
                " / ".join(f.value for f in m.thresholds) or "—") for m in line.metrics),
              (4.1, 2.6, 1.8, 3.7, 5.0))
        document.add_heading("输入数据", level=2)
        pairs = []
        fields = list(line.inputs)
        for index in range(0, len(fields), 2):
            row = []
            for field in fields[index:index + 2]:
                row.extend((field.label, f"{field.value} {field.unit}".strip()))
            pairs.append(row + [""] * (4 - len(row)))
        table(("输入项", "保存值", "输入项", "保存值"), pairs, (4.3, 4.3, 4.3, 4.3))
        document.add_heading("计算与判级依据", level=2)
        for text in (*line.calculations, *line.basis):
            _text(document.add_paragraph(), text)
    if view.shared:
        document.add_heading("共用系统分摊", level=1)
        for text in view.shared:
            _text(document.add_paragraph(), text)
    document.add_heading("统计范围与软件解释", level=1)
    for text in view.explanations:
        _text(document.add_paragraph(), text)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("第 ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    footer.add_run(" 页")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=f".{path.stem}-", suffix=".docx", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
        document.save(temporary)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path
