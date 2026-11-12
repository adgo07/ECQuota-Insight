"""水泥保存视图的只读HTML；不计算指标或阈值。"""
from html import escape
from uebench.application.scientific_symbols import symbols_html
from uebench.domain.models import GRADE_LABELS
from uebench.application.reporting import _plain, _display_two_places


def section(title, lines):
    return f"<h3>{escape(title)}</h3>" + "".join(f"<p>{symbols_html(line)}</p>" for line in lines)


def metric_table(metrics):
    rows = ["<table width='100%' cellpadding='6' border='1' cellspacing='0'><tr><th>指标</th><th>实际值</th><th>等级</th><th>基准上限 1/2/3</th><th>有效上限 1/2/3</th></tr>"]
    for name, actual, unit, grade, base, limits in metrics:
        rows.append("<tr>" + "".join(f"<td>{symbols_html(v)}</td>" for v in (name, f"{actual} {unit}", grade, base, limits)) + "</tr>")
    return "".join(rows) + "</table>"


def result_html(result):
    body = ""
    line_ids = list(dict.fromkeys(item.line_id for item in result.results))
    for line_id in line_ids:
        items = [i for i in result.results if i.line_id == line_id]
        body += f"<h3>{escape(items[0].line_name or '生产线')}</h3>"
        body += metric_table((i.indicator_name, "—" if i.actual_value is None else _display_two_places(i.actual_value),
            i.unit, GRADE_LABELS[i.grade], " / ".join(_plain(v) for v in i.base_thresholds.values()),
            " / ".join(_plain(v) for v in i.corrected_thresholds.values())) for i in items)
        body += section("数据检查", list(dict.fromkeys(w for i in items for w in i.warnings))) if any(i.warnings for i in items) else ""
    return body


def report_results_html(view):
    body = section("基本信息", (f"{f.label}：{f.value} {f.unit}".strip() for f in view.information))
    for line in view.lines:
        body += f"<h3>{escape(line.name)} · {escape(line.mode)}</h3>"
        body += metric_table((i.name, i.actual, i.unit, i.grade,
            " / ".join(f.value for f in i.base_thresholds), " / ".join(f.value for f in i.thresholds)) for i in line.metrics)
    return body


def report_inputs_html(view):
    body = ""
    for line in view.lines:
        body += section(f"{line.name} · 输入数据", (f"{f.label}：{f.value} {f.unit}".strip() for f in line.inputs))
        body += section(f"{line.name} · 计算与依据", (*line.calculations, *line.basis))
    if view.shared:
        body += section("共用系统分摊", view.shared)
    return body + section("统计范围与解释", view.explanations)
