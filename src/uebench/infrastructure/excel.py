from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from pydantic import BaseModel, Field

from uebench.domain.models import (
    EnergyLine,
    GRADE_LABELS,
    EvaluationRequest,
    Grade,
    InputMode,
    InputValue,
    ProductionLine,
)

from .database import DatabaseManager, ImportBatchRow
from .repositories import AuditRepository, SqlEvaluationRepository


TEMPLATE_VERSION = "1.1"
IMPORT_SHEETS = ["填写说明", "评价信息", "适用条件", "实际值", "能源明细", "产量与分摊"]
EXPORT_SHEETS = ["对标结论", "评价信息", "输入数据", "计算过程", "标准依据", "校验与日志"]
IMPORT_HEADERS = {
    "评价信息": ["字段", "值", "说明"],
    "适用条件": ["键", "名称", "值", "单位", "数据来源/备注"],
    "实际值": ["键", "名称", "值", "单位", "数据来源/备注"],
    "能源明细": ["行ID", "能源名称", "分类键", "方向", "实物量", "实物量单位", "折标系数", "系数单位", "分摊比例", "数据来源/备注"],
    "产量与分摊": ["行ID", "产品名称", "分类键", "产量", "单位", "折算系数", "是否合格", "数据来源/备注"],
}


class ImportIssue(BaseModel):
    severity: str
    sheet: str
    cell: str
    message: str


class ImportReport(BaseModel):
    import_id: str
    valid: bool
    issues: list[ImportIssue] = Field(default_factory=list)
    request: EvaluationRequest | None = None


class EvaluationDraft(BaseModel):
    import_id: str
    request: EvaluationRequest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _excel_value(value):
    if isinstance(value, float):
        return str(value)
    return value


def _decimal_from_cell(value, *, sheet: str, cell: str, issues: list[ImportIssue]) -> Decimal | None:
    if value is None or value == "":
        issues.append(ImportIssue(severity="error", sheet=sheet, cell=cell, message="数值不能为空"))
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        issues.append(ImportIssue(severity="error", sheet=sheet, cell=cell, message="不是有效十进制数"))
        return None


class WorkbookTemplateService:
    def create_template(self, path: Path) -> Path:
        workbook = Workbook()
        workbook.remove(workbook.active)
        for name in IMPORT_SHEETS:
            workbook.create_sheet(name)
        self._instructions(workbook["填写说明"])
        self._evaluation_info(workbook["评价信息"])
        self._generic_inputs(workbook["适用条件"], "适用条件")
        self._generic_inputs(workbook["实际值"], "实际值")
        self._energy_lines(workbook["能源明细"])
        self._production_lines(workbook["产量与分摊"])
        for sheet in workbook.worksheets:
            sheet.sheet_view.showGridLines = False
            sheet.freeze_panes = "A2"
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(path)
        return path

    @staticmethod
    def _header(sheet, headers: list[str]) -> None:
        sheet.append(headers)
        fill = PatternFill("solid", fgColor="1F4E78")
        for cell in sheet[1]:
            cell.fill = fill
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center")
        sheet.row_dimensions[1].height = 26

    def _instructions(self, sheet) -> None:
        sheet["A1"] = "单位产品能耗对标数据导入模板"
        sheet["A1"].font = Font(size=16, bold=True, color="1F4E78")
        sheet.merge_cells("A1:D1")
        notes = [
            "模板版本和工作表名称不可修改。",
            "直接录入模式填写“实际值”；明细计算模式填写“能源明细”和“产量与分摊”。",
            "适用条件和实际值中的“键”应由软件生成的标准专用模板提供。",
            "所有数值使用十进制，不要录入带单位的文本。",
            "direction 只能填写 input 或 output；分摊比例范围为 0~1。",
        ]
        for row, note in enumerate(notes, start=3):
            sheet.cell(row=row, column=1, value=f"{row - 2}. {note}")
        sheet.column_dimensions["A"].width = 90

    def _evaluation_info(self, sheet) -> None:
        self._header(sheet, ["字段", "值", "说明"])
        rows = [
            ("template_version", TEMPLATE_VERSION, "固定值"),
            ("evaluation_date", date.today(), "日期，且不得早于标准实施日期"),
            ("standard_id", "", "标准唯一ID"),
            ("product_id", "", "产品或工序唯一ID"),
            ("input_mode", InputMode.DIRECT.value, "DIRECT 或 DETAIL"),
            ("organization_name", "", "单位名称，可空"),
            ("project_name", "", "项目名称，可空"),
            ("notes", "", "备注，可空"),
        ]
        for item in rows:
            sheet.append(item)
        sheet["B3"].number_format = "yyyy-mm-dd"
        validation = DataValidation(type="list", formula1='"DIRECT,DETAIL"', allow_blank=False)
        sheet.add_data_validation(validation)
        validation.add(sheet["B6"])
        sheet.column_dimensions["A"].width = 26
        sheet.column_dimensions["B"].width = 34
        sheet.column_dimensions["C"].width = 48

    def _generic_inputs(self, sheet, _title: str) -> None:
        self._header(sheet, ["键", "名称", "值", "单位", "数据来源/备注"])
        for _ in range(20):
            sheet.append(["", "", "", "", ""])
        widths = [28, 34, 20, 18, 48]
        for index, width in enumerate(widths, start=1):
            sheet.column_dimensions[chr(64 + index)].width = width

    def _energy_lines(self, sheet) -> None:
        self._header(
            sheet,
            ["行ID", "能源名称", "分类键", "方向", "实物量", "实物量单位", "折标系数", "系数单位", "分摊比例", "数据来源/备注"],
        )
        for _ in range(50):
            sheet.append(["", "", "", "input", "", "", "", "", 1, ""])
        validation = DataValidation(type="list", formula1='"input,output"', allow_blank=False)
        sheet.add_data_validation(validation)
        validation.add("D2:D51")
        widths = [16, 24, 18, 12, 16, 16, 16, 20, 14, 40]
        for index, width in enumerate(widths, start=1):
            sheet.column_dimensions[chr(64 + index)].width = width

    def _production_lines(self, sheet) -> None:
        self._header(sheet, ["行ID", "产品名称", "分类键", "产量", "单位", "折算系数", "是否合格", "数据来源/备注"])
        for _ in range(30):
            sheet.append(["", "", "", "", "", 1, "是", ""])
        validation = DataValidation(type="list", formula1='"是,否"', allow_blank=False)
        sheet.add_data_validation(validation)
        validation.add("G2:G31")
        widths = [16, 30, 18, 16, 14, 16, 14, 44]
        for index, width in enumerate(widths, start=1):
            sheet.column_dimensions[chr(64 + index)].width = width


class WorkbookImportService:
    def __init__(self, database: DatabaseManager, audit: AuditRepository | None = None, standards=None) -> None:
        self.database = database
        self.audit = audit or AuditRepository(database)
        self.standards = standards

    def validate(self, path: Path) -> ImportReport:
        import_id = str(uuid4())
        issues: list[ImportIssue] = []
        request: EvaluationRequest | None = None
        path = path.resolve()
        try:
            workbook = load_workbook(path, data_only=True, read_only=True)
            if workbook.sheetnames != IMPORT_SHEETS:
                issues.append(
                    ImportIssue(
                        severity="error",
                        sheet="工作簿",
                        cell="-",
                        message=f"工作表必须严格为：{', '.join(IMPORT_SHEETS)}",
                    )
                )
            else:
                self._validate_fixed_structure(workbook, issues)
                if not any(issue.severity == "error" for issue in issues):
                    request = self._parse(workbook, issues)
                if request is not None and self.standards is not None:
                    standard = self.standards.get_published(request.standard_id)
                    if standard is None:
                        issues.append(
                            ImportIssue(
                                severity="error",
                                sheet="评价信息",
                                cell="B4",
                                message=f"未找到已发布标准：{request.standard_id}",
                            )
                        )
                    elif not any(product.id == request.product_id for product in standard.products):
                        issues.append(
                            ImportIssue(
                                severity="error",
                                sheet="评价信息",
                                cell="B5",
                                message=f"产品/工序不属于标准 {standard.number}：{request.product_id}",
                            )
                        )
        except Exception as exc:
            issues.append(ImportIssue(severity="error", sheet="工作簿", cell="-", message=str(exc)))
        valid = request is not None and not any(issue.severity == "error" for issue in issues)
        report = ImportReport(import_id=import_id, valid=valid, issues=issues, request=request if valid else None)
        with self.database.session() as session:
            session.add(
                ImportBatchRow(
                    import_id=import_id,
                    source_file=str(path),
                    source_sha256=_sha256(path) if path.exists() else "0" * 64,
                    status="validated" if valid else "invalid",
                    payload_json=request.model_dump_json() if request is not None else "{}",
                    validation_json=report.model_dump_json(),
                )
            )
            self.audit.append(
                "WORKBOOK_VALIDATE",
                "import_batch",
                import_id,
                {"valid": valid, "issue_count": len(issues)},
                session=session,
            )
        return report

    @staticmethod
    def _validate_fixed_structure(workbook, issues: list[ImportIssue]) -> None:
        """Reject renamed, reordered, missing, or extra template columns.

        The import contract is intentionally strict: a workbook with a custom
        schema must be converted to the official template before it can enter
        the audit trail.  Empty data rows remain allowed; only the header and
        instruction sheet structure is checked here.
        """
        instructions = workbook["填写说明"]
        if instructions["A1"].value != "单位产品能耗对标数据导入模板":
            issues.append(ImportIssue(severity="error", sheet="填写说明", cell="A1", message="模板标题不正确"))
        for sheet_name, expected in IMPORT_HEADERS.items():
            sheet = workbook[sheet_name]
            actual = [sheet.cell(row=1, column=index).value for index in range(1, len(expected) + 1)]
            if actual != expected:
                issues.append(
                    ImportIssue(
                        severity="error",
                        sheet=sheet_name,
                        cell="A1",
                        message=f"表头必须严格为：{'、'.join(expected)}",
                    )
                )
            for column in range(len(expected) + 1, sheet.max_column + 1):
                extra = sheet.cell(row=1, column=column).value
                if extra not in (None, ""):
                    issues.append(
                        ImportIssue(
                            severity="error",
                            sheet=sheet_name,
                            cell=f"{get_column_letter(column)}1",
                            message="模板不允许增加自定义列",
                        )
                    )

    def commit(self, import_id: str) -> EvaluationDraft:
        with self.database.session() as session:
            row = session.get(ImportBatchRow, import_id)
            if row is None:
                raise LookupError("导入批次不存在")
            if row.status != "validated":
                raise ValueError("只有验证通过的导入批次可以提交")
            row.status = "committed"
            request = EvaluationRequest.model_validate_json(row.payload_json)
            self.audit.append("WORKBOOK_COMMIT", "import_batch", import_id, session=session)
            return EvaluationDraft(import_id=import_id, request=request)

    def _parse(self, workbook, issues: list[ImportIssue]) -> EvaluationRequest | None:
        info_sheet = workbook["评价信息"]
        info = {}
        for row_number, row in enumerate(info_sheet.iter_rows(min_row=2), start=2):
            key = row[0].value
            if not key:
                continue
            if key in info:
                issues.append(
                    ImportIssue(severity="error", sheet="评价信息", cell=f"A{row_number}", message=f"字段重复：{key}")
                )
                continue
            info[key] = _excel_value(row[1].value)
        if str(info.get("template_version")) != TEMPLATE_VERSION:
            issues.append(
                ImportIssue(severity="error", sheet="评价信息", cell="B2", message="模板版本不受支持")
            )
        evaluation_date = info.get("evaluation_date")
        if isinstance(evaluation_date, datetime):
            evaluation_date = evaluation_date.date()
        elif isinstance(evaluation_date, str):
            try:
                evaluation_date = date.fromisoformat(evaluation_date)
            except ValueError:
                issues.append(
                    ImportIssue(severity="error", sheet="评价信息", cell="B3", message="日期格式应为 yyyy-mm-dd")
                )
        if not isinstance(evaluation_date, date):
            issues.append(ImportIssue(severity="error", sheet="评价信息", cell="B3", message="评价日期不能为空"))
        for key, cell in (("standard_id", "B4"), ("product_id", "B5"), ("input_mode", "B6")):
            if not info.get(key):
                issues.append(ImportIssue(severity="error", sheet="评价信息", cell=cell, message=f"{key} 不能为空"))
        try:
            mode = InputMode(str(info.get("input_mode")))
        except ValueError:
            issues.append(
                ImportIssue(severity="error", sheet="评价信息", cell="B6", message="input_mode 必须为 DIRECT 或 DETAIL")
            )
            mode = InputMode.DIRECT

        inputs: dict[str, InputValue] = {}
        for sheet_name in ("适用条件", "实际值"):
            sheet = workbook[sheet_name]
            for row_number, row in enumerate(sheet.iter_rows(min_row=2), start=2):
                key = row[0].value
                if not key:
                    continue
                value = _excel_value(row[2].value)
                if value is None or value == "":
                    issues.append(
                        ImportIssue(severity="error", sheet=sheet_name, cell=f"C{row_number}", message="值不能为空")
                    )
                    continue
                if str(key) in inputs:
                    issues.append(
                        ImportIssue(
                            severity="error",
                            sheet=sheet_name,
                            cell=f"A{row_number}",
                            message=f"输入键重复或同时出现在两个输入表：{key}",
                        )
                    )
                    continue
                inputs[str(key)] = InputValue(value=value, unit=row[3].value, source_note=row[4].value)

        energy_lines: list[EnergyLine] = []
        energy_line_ids: set[str] = set()
        for row_number, row in enumerate(workbook["能源明细"].iter_rows(min_row=2), start=2):
            if not row[0].value:
                continue
            line_id = str(row[0].value)
            if line_id in energy_line_ids:
                issues.append(ImportIssue(severity="error", sheet="能源明细", cell=f"A{row_number}", message=f"行ID重复：{line_id}"))
                continue
            energy_line_ids.add(line_id)
            amount = _decimal_from_cell(row[4].value, sheet="能源明细", cell=f"E{row_number}", issues=issues)
            coefficient = _decimal_from_cell(
                row[6].value, sheet="能源明细", cell=f"G{row_number}", issues=issues
            )
            ratio = _decimal_from_cell(row[8].value, sheet="能源明细", cell=f"I{row_number}", issues=issues)
            if None in (amount, coefficient, ratio):
                continue
            try:
                energy_lines.append(
                    EnergyLine(
                        line_id=line_id,
                        energy_name=str(row[1].value or ""),
                        category_key=str(row[2].value) if row[2].value else None,
                        direction=str(row[3].value or "input"),
                        amount=amount,
                        unit=str(row[5].value or ""),
                        standard_coal_coefficient=coefficient,
                        coefficient_unit=str(row[7].value or ""),
                        allocation_ratio=ratio,
                        source_note=row[9].value,
                    )
                )
            except ValueError as exc:
                issues.append(ImportIssue(severity="error", sheet="能源明细", cell=f"A{row_number}", message=str(exc)))

        production_lines: list[ProductionLine] = []
        production_line_ids: set[str] = set()
        for row_number, row in enumerate(workbook["产量与分摊"].iter_rows(min_row=2), start=2):
            if not row[0].value:
                continue
            line_id = str(row[0].value)
            if line_id in production_line_ids:
                issues.append(ImportIssue(severity="error", sheet="产量与分摊", cell=f"A{row_number}", message=f"行ID重复：{line_id}"))
                continue
            production_line_ids.add(line_id)
            quantity = _decimal_from_cell(row[3].value, sheet="产量与分摊", cell=f"D{row_number}", issues=issues)
            factor = _decimal_from_cell(row[5].value, sheet="产量与分摊", cell=f"F{row_number}", issues=issues)
            if None in (quantity, factor):
                continue
            try:
                production_lines.append(
                    ProductionLine(
                        line_id=line_id,
                        product_name=str(row[1].value or ""),
                        category_key=str(row[2].value) if row[2].value else None,
                        quantity=quantity,
                        unit=str(row[4].value or ""),
                        conversion_factor=factor,
                        qualified=str(row[6].value or "是") == "是",
                        source_note=row[7].value,
                    )
                )
            except ValueError as exc:
                issues.append(
                    ImportIssue(severity="error", sheet="产量与分摊", cell=f"A{row_number}", message=str(exc))
                )
        if any(issue.severity == "error" for issue in issues):
            return None
        try:
            return EvaluationRequest(
                evaluation_date=evaluation_date,
                standard_id=str(info["standard_id"]),
                product_id=str(info["product_id"]),
                input_mode=mode,
                inputs=inputs,
                energy_lines=energy_lines,
                production_lines=production_lines,
                organization_name=info.get("organization_name") or None,
                project_name=info.get("project_name") or None,
                notes=info.get("notes") or None,
            )
        except ValueError as exc:
            issues.append(ImportIssue(severity="error", sheet="工作簿", cell="-", message=str(exc)))
            return None

class WorkbookExportService:
    def __init__(self, evaluations: SqlEvaluationRepository, audit: AuditRepository | None = None) -> None:
        self.evaluations = evaluations
        self.audit = audit or evaluations.audit

    def export(self, evaluation_id: str, path: Path) -> Path:
        loaded = self.evaluations.get(evaluation_id)
        if loaded is None:
            raise LookupError("评价记录不存在")
        request, result, standard = loaded
        workbook = Workbook()
        workbook.remove(workbook.active)
        for name in EXPORT_SHEETS:
            workbook.create_sheet(name)
        self._summary(workbook["对标结论"], result)
        self._info(workbook["评价信息"], request, result)
        self._inputs(workbook["输入数据"], request)
        self._trace(workbook["计算过程"], result)
        self._sources(workbook["标准依据"], standard, result)
        self._quality(workbook["校验与日志"], result)
        for sheet in workbook.worksheets:
            self._format_sheet(sheet)
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(path)
        self.audit.append("WORKBOOK_EXPORT", "evaluation", evaluation_id, {"path": str(path)})
        return path

    @staticmethod
    def _title(sheet, title: str, columns: int) -> None:
        sheet.append([title])
        sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=columns)
        cell = sheet.cell(1, 1)
        cell.font = Font(size=16, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="left", vertical="center")
        sheet.row_dimensions[1].height = 32

    @staticmethod
    def _table_header(sheet, row: int, headers: list[str]) -> None:
        for column, value in enumerate(headers, start=1):
            cell = sheet.cell(row=row, column=column, value=value)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="5B9BD5")
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def _summary(self, sheet, result) -> None:
        self._title(sheet, "单位产品能耗对标结论", 14)
        sheet.append(["标准", f"{result.standard_number} {result.standard_title}"])
        sheet.append(["产品/工序", result.product_name])
        sheet.append([])
        headers = [
            "指标", "实际值", "单位", "1级基础限额", "2级基础限额", "3级基础限额",
            "判定结果", "警告", "1级修正后限额", "2级修正后限额", "3级修正后限额",
            "依据页码", "条款/表号", "规则快照哈希",
        ]
        self._table_header(sheet, 5, headers)
        for item in result.results:
            base = item.base_thresholds
            thresholds = item.corrected_thresholds
            references = "; ".join(
                f"p.{ref.page}" + (f" {ref.clause}" if ref.clause else "") + (f" {ref.table}" if ref.table else "")
                for ref in item.source_references
            )
            sheet.append(
                [
                    item.indicator_name,
                    item.actual_value,
                    item.unit,
                    base.get("LEVEL_1"),
                    base.get("LEVEL_2"),
                    base.get("LEVEL_3"),
                    GRADE_LABELS[item.grade],
                    "；".join(item.warnings),
                    thresholds.get("LEVEL_1"),
                    thresholds.get("LEVEL_2"),
                    thresholds.get("LEVEL_3"),
                    ", ".join(str(ref.page) for ref in item.source_references),
                    "; ".join(filter(None, {ref.clause for ref in item.source_references} | {ref.table for ref in item.source_references})),
                    result.rule_snapshot_sha256,
                ]
            )
        red_fill = PatternFill("solid", fgColor="F4CCCC")
        green_fill = PatternFill("solid", fgColor="D9EAD3")
        sheet.conditional_formatting.add(
            f"G6:G{max(6, sheet.max_row)}",
            FormulaRule(formula=["G6=\"未达标\""], fill=red_fill),
        )
        sheet.conditional_formatting.add(
            f"G6:G{max(6, sheet.max_row)}",
            FormulaRule(formula=["OR(G6=\"1级\",G6=\"2级\",G6=\"3级\")"], fill=green_fill),
        )

    def _info(self, sheet, request, result) -> None:
        self._title(sheet, "评价信息", 2)
        rows = [
            ("评价ID", result.evaluation_id),
            ("评价日期", request.evaluation_date),
            ("计算时间", result.evaluated_at.astimezone().replace(tzinfo=None)),
            ("单位名称", request.organization_name),
            ("项目名称", request.project_name),
            ("标准编号", result.standard_number),
            ("标准版本", result.standard_version),
            ("产品/工序", result.product_name),
            ("录入模式", request.input_mode.value),
            ("备注", request.notes),
        ]
        for row in rows:
            sheet.append(row)
        sheet["B3"].number_format = "yyyy-mm-dd"
        sheet["B4"].number_format = "yyyy-mm-dd hh:mm:ss"

    def _inputs(self, sheet, request) -> None:
        self._title(sheet, "输入数据", 9)
        self._table_header(sheet, 3, ["类型", "键/行ID", "名称", "数值", "单位", "方向/合格", "系数", "分摊/折算", "来源/备注"])
        for key, value in request.inputs.items():
            sheet.append(["输入值", key, "", value.value, value.unit, "", "", "", value.source_note])
        for line in request.energy_lines:
            sheet.append(
                [
                    "能源明细",
                    line.line_id,
                    line.energy_name,
                    line.amount,
                    line.unit,
                    line.direction,
                    line.standard_coal_coefficient,
                    line.allocation_ratio,
                    line.source_note,
                ]
            )
        for line in request.production_lines:
            sheet.append(
                [
                    "产量",
                    line.line_id,
                    line.product_name,
                    line.quantity,
                    line.unit,
                    "是" if line.qualified else "否",
                    "",
                    line.conversion_factor,
                    line.source_note,
                ]
            )

    def _trace(self, sheet, result) -> None:
        self._title(sheet, "计算过程", 8)
        self._table_header(sheet, 3, ["指标", "序号", "步骤", "操作", "表达式", "结果", "单位", "警告"])
        for item in result.results:
            if not item.calculation_trace:
                sheet.append([item.indicator_name, "", "", "", "", "", item.unit, "；".join(item.warnings)])
            for step in item.calculation_trace:
                sheet.append(
                    [
                        item.indicator_name,
                        step.sequence,
                        step.label,
                        step.operation,
                        step.expression,
                        step.value,
                        step.unit,
                        "；".join(item.warnings),
                    ]
                )

    def _sources(self, sheet, standard, result) -> None:
        self._title(sheet, "标准依据", 8)
        self._table_header(sheet, 3, ["标准编号", "标准名称", "原文文件", "原文SHA-256", "页码", "条款", "表号", "备注"])
        seen = set()
        for item in result.results:
            for reference in item.source_references:
                key = (reference.page, reference.clause, reference.table, reference.note)
                if key in seen:
                    continue
                seen.add(key)
                sheet.append(
                    [
                        standard.number,
                        standard.title,
                        reference.source_file,
                        reference.source_sha256,
                        reference.page,
                        reference.clause,
                        reference.table,
                        reference.note,
                    ]
                )

    def _quality(self, sheet, result) -> None:
        self._title(sheet, "校验与日志", 3)
        self._table_header(sheet, 3, ["类型", "对象", "信息"])
        sheet.append(["规则快照", result.standard_number, result.rule_snapshot_sha256])
        for warning in result.warnings:
            sheet.append(["评价警告", result.evaluation_id, warning])
        for item in result.results:
            for warning in item.warnings:
                sheet.append(["指标警告", item.indicator_name, warning])
        if sheet.max_row == 4:
            sheet.append(["校验", "评价结果", "未发现警告"])

    @staticmethod
    def _format_sheet(sheet) -> None:
        sheet.sheet_view.showGridLines = False
        sheet.freeze_panes = "A4"
        sheet.auto_filter.ref = sheet.dimensions if sheet.max_row >= 3 else None
        thin = Side(style="thin", color="D9E2F3")
        for row in sheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                if cell.row > 1:
                    cell.border = Border(bottom=thin)
                if isinstance(cell.value, Decimal):
                    cell.number_format = "0.########"
        for column_index, column_cells in enumerate(sheet.columns, start=1):
            letter = get_column_letter(column_index)
            maximum = max((len(str(cell.value)) for cell in column_cells if cell.value is not None), default=8)
            sheet.column_dimensions[letter].width = min(max(maximum + 2, 12), 48)
