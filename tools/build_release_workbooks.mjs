import fs from "node:fs/promises";
import path from "node:path";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const dataRoot = path.resolve(process.env.UEBENCH_WORKBOOK_DATA_DIR ?? "data");
const outputDir = path.resolve(process.env.UEBENCH_WORKBOOK_OUTPUT_DIR ?? "dist/release");
const previewDir = path.resolve("work/spreadsheet/previews");
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const navy = "#17365D";
const blue = "#2F75B5";
const lightBlue = "#D9EAF7";
const paleBlue = "#F4F7FB";
const border = "#B4C6E7";
const white = "#FFFFFF";

function title(sheet, range, text, subtitle) {
  sheet.getRange(range).merge();
  const start = range.split(":")[0];
  sheet.getRange(start).values = [[text]];
  sheet.getRange(range).format = {
    fill: navy,
    font: { bold: true, color: white, size: 18 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  sheet.getRange(range).format.rowHeight = 34;
  if (subtitle) {
    const row = Number(start.match(/\d+/)[0]) + 1;
    const startColumn = start.match(/[A-Z]+/)[0];
    const endColumn = range.split(":")[1].match(/[A-Z]+/)[0];
    const subtitleRange = `${startColumn}${row}:${endColumn}${row}`;
    sheet.getRange(subtitleRange).merge();
    sheet.getRange(`${startColumn}${row}`).values = [[subtitle]];
    sheet.getRange(subtitleRange).format = {
      fill: lightBlue,
      font: { color: navy, italic: true },
      horizontalAlignment: "left",
      verticalAlignment: "center",
      wrapText: true,
    };
    sheet.getRange(subtitleRange).format.rowHeight = 28;
  }
}

function header(range) {
  range.format = {
    fill: blue,
    font: { bold: true, color: white },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: border },
  };
  range.format.rowHeight = 28;
}

function body(range) {
  range.format = {
    fill: white,
    font: { color: "#1F2937" },
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: border },
  };
}

function setWidths(sheet, widths, rows = 200) {
  for (const [column, width] of Object.entries(widths)) {
    sheet.getRange(`${column}1:${column}${rows}`).format.columnWidth = width;
  }
}

function baseValue(indicator, level) {
  const set = indicator.base_thresholds ?? indicator.thresholds;
  const expression = set[level];
  if (expression === null || expression === undefined) return "—";
  return expression.op === "constant" ? expression.value : "按条件修正";
}

function sourceSummary(indicator) {
  return indicator.source_references
    .map((item) => `PDF第${item.page}页；${item.clause ?? ""}${item.table ? `；${item.table}` : ""}`)
    .join("\n");
}

const definitionFiles = (await fs.readdir(path.join(dataRoot, "definitions"))).filter((name) => name.endsWith(".json"));
const definitions = [];
for (const filename of definitionFiles) {
  const definition = JSON.parse(await fs.readFile(path.join(dataRoot, "definitions", filename), "utf8"));
  definitions.push(definition);
}
definitions.sort((a, b) => a.number.localeCompare(b.number, "zh-CN"));
const scopeCount = definitions.length;

const reviewWorkbook = Workbook.create();
const summary = reviewWorkbook.worksheets.add("确认汇总");
const rules = reviewWorkbook.worksheets.add("规则确认");
const corrections = reviewWorkbook.worksheets.add("订正记录");
reviewWorkbook.comments.setSelf({ displayName: "User" });

title(summary, "A1:G1", `${scopeCount}项单位产品能耗限额标准规则确认表`, `范围固定为${scopeCount}项；draft/reviewed候选数据必须回到强制性标准原文复核，只有确认通过的规则才可发布。`)
summary.getRange("A4:G4").values = [["标准编号", "标准名称", "产品/工序数", "指标数", "当前状态", "已同意指标数", "原文SHA-256"]];
header(summary.getRange("A4:G4"));
const summaryRows = definitions.map((definition) => [
  definition.number,
  definition.title,
  definition.products.length,
  null,
  definition.publication_status,
  null,
  definition.source_sha256,
]);
summary.getRange(`A5:G${4 + summaryRows.length}`).values = summaryRows;
for (let index = 0; index < definitions.length; index += 1) {
  const row = 5 + index;
  summary.getRange(`D${row}`).formulas = [[`=COUNTIF('规则确认'!$B$4:$B$5000,A${row})`]];
  summary.getRange(`F${row}`).formulas = [[`=COUNTIFS('规则确认'!$B$4:$B$5000,A${row},'规则确认'!$Q$4:$Q$5000,"同意发布")`]];
}
body(summary.getRange(`A5:G${4 + summaryRows.length}`));
summary.getRange(`C5:F${4 + summaryRows.length}`).format.horizontalAlignment = "center";
const summaryNoteStart = 5 + summaryRows.length + 2;
const summaryNoteEnd = summaryNoteStart + 3;
summary.getRange(`A${summaryNoteStart}:G${summaryNoteEnd}`).merge();
summary.getRange(`A${summaryNoteStart}`).values = [[
  "确认说明：逐项核对产品/工序、指标、单位、三级基础限额、修正规则以及原文页码/条款/表号。若任一内容不一致，请在“规则确认”工作表选择“退回修改”并填写备注。确认完成后由标准包制作人员生成published版本，软件端不允许直接编辑已发布规则。",
]];
summary.getRange(`A${summaryNoteStart}:G${summaryNoteEnd}`).format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
summary.freezePanes.freezeRows(4);
summary.showGridLines = false;
setWidths(summary, { A: 20, B: 48, C: 14, D: 12, E: 14, F: 16, G: 66 }, 30);

title(rules, "A1:T1", "规则逐项确认", "基础限额来自表格；修正规则以说明及结构化规则为准。结论栏必须逐项填写。")
const ruleHeaders = [
  "序号", "标准编号", "标准名称", "产品/工序", "指标ID", "指标名称", "单位", "1级基础限额", "2级基础限额", "3级基础限额",
  "修正与适用说明", "来源定位", "PDF页码", "条款", "表号", "复核状态", "确认结论", "确认人", "确认日期", "确认备注",
];
rules.getRange("A3:T3").values = [ruleHeaders];
header(rules.getRange("A3:T3"));
const ruleRows = [];
let sequence = 1;
for (const definition of definitions) {
  for (const product of definition.products) {
    for (const indicator of product.indicators) {
      const firstSource = indicator.source_references[0];
      ruleRows.push([
        sequence,
        definition.number,
        definition.title,
        product.name,
        indicator.id,
        indicator.name,
        indicator.unit,
        baseValue(indicator, "level_1"),
        baseValue(indicator, "level_2"),
        baseValue(indicator, "level_3"),
        (indicator.notes ?? []).join("\n") || "无附加修正",
        sourceSummary(indicator),
        firstSource.page,
        firstSource.clause ?? "",
        firstSource.table ?? "",
        definition.publication_status,
        "待确认",
        "",
        null,
        "",
      ]);
      sequence += 1;
    }
  }
}
rules.getRange(`A4:T${3 + ruleRows.length}`).values = ruleRows;
body(rules.getRange(`A4:T${3 + ruleRows.length}`));
rules.getRange(`A4:A${3 + ruleRows.length}`).format.numberFormat = "0";
rules.getRange(`M4:M${3 + ruleRows.length}`).format.numberFormat = "0";
rules.getRange(`S4:S${3 + ruleRows.length}`).format.numberFormat = "yyyy-mm-dd";
rules.getRange(`Q4:Q${3 + ruleRows.length}`).dataValidation = { rule: { type: "list", values: ["待确认", "同意发布", "退回修改"] } };
rules.getRange(`Q4:Q${3 + ruleRows.length}`).conditionalFormats.add("cellIs", { operator: "equal", formula: '"同意发布"', format: { fill: "#E2F0D9", font: { color: "#006100", bold: true } } });
rules.getRange(`Q4:Q${3 + ruleRows.length}`).conditionalFormats.add("cellIs", { operator: "equal", formula: '"退回修改"', format: { fill: "#FCE4D6", font: { color: "#9C0006", bold: true } } });
rules.freezePanes.freezeRows(3);
rules.freezePanes.freezeColumns(2);
rules.showGridLines = false;
setWidths(rules, { A: 8, B: 20, C: 38, D: 26, E: 42, F: 34, G: 14, H: 16, I: 16, J: 16, K: 56, L: 36, M: 10, N: 18, O: 14, P: 12, Q: 14, R: 14, S: 14, T: 38 }, 220);

const correctionData = JSON.parse(await fs.readFile(path.join(dataRoot, "corrections", "catalog-corrections.json"), "utf8"));
title(corrections, "A1:H1", "目录与原文订正记录", "所有订正均显式记录，冲突时按原文优先级处理。")
corrections.getRange("A3:H3").values = [["订正ID", "标准编号", "字段", "目录原值", "订正值", "原因", "依据", "处理状态"]];
header(corrections.getRange("A3:H3"));
const correctionRows = correctionData.corrections.map((item) => [
  item.id,
  item.standard_number,
  item.fields.join("、"),
  item.fields.map((field) => `${field}=${item.original[field]}`).join("\n"),
  item.fields.map((field) => `${field}=${item.corrected[field]}`).join("\n"),
  item.reason,
  item.source,
  "已订正",
]);
corrections.getRange(`A4:H${3 + correctionRows.length}`).values = correctionRows;
body(corrections.getRange(`A4:H${3 + correctionRows.length}`));
corrections.freezePanes.freezeRows(3);
corrections.showGridLines = false;
setWidths(corrections, { A: 12, B: 20, C: 22, D: 42, E: 42, F: 58, G: 34, H: 14 }, 30);

const reviewCheck = await reviewWorkbook.inspect({ kind: "table", range: "确认汇总!A1:G15", include: "values,formulas", tableMaxRows: 20, tableMaxCols: 10 });
process.stdout.write(`${reviewCheck.ndjson}\n`);
const reviewErrors = await reviewWorkbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "review workbook formula errors" });
process.stdout.write(`${reviewErrors.ndjson}\n`);
for (const [sheetName, fileName, range] of [["确认汇总", "review-summary.png", `A1:G${summaryNoteEnd}`], ["规则确认", "review-rules.png", "A1:T18"], ["订正记录", "review-corrections.png", "A1:H8"]]) {
  const preview = await reviewWorkbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
const reviewOutput = await SpreadsheetFile.exportXlsx(reviewWorkbook);
await reviewOutput.save(path.join(outputDir, "统一标准规则确认表.xlsx"));

const template = Workbook.create();
const templateSheets = ["填写说明", "评价信息", "适用条件", "实际值", "能源明细", "产量与分摊"];
for (const name of templateSheets) template.worksheets.add(name);
const instructions = template.worksheets.getItem("填写说明");
title(instructions, "A1:C1", "单位产品能耗对标导入模板", "模板版本1.1；工作表名、列名和结构不得修改。")
instructions.getRange("A4:C9").values = [
  ["序号", "填写要求", "说明"],
  [1, "评价信息", "填写评价日期、标准ID、产品/工序ID和录入模式。"],
  [2, "适用条件", "按软件标准库列出的键、单位和选项填写。"],
  [3, "实际值", "DIRECT模式填写已核算的单位产品能耗实际值。"],
  [4, "能源明细", "DETAIL模式逐行填写能源输入/输出、分类键、折标系数和分摊比例。"],
  [5, "产量与分摊", "DETAIL模式逐行填写合格产量、分类键和折算系数。"],
];
header(instructions.getRange("A4:C4"));
body(instructions.getRange("A5:C9"));
instructions.showGridLines = false;
setWidths(instructions, { A: 10, B: 24, C: 78 }, 20);

const info = template.worksheets.getItem("评价信息");
info.getRange("A1:B9").values = [
  ["字段", "值"],
  ["template_version", "1.1"],
  ["evaluation_date", null],
  ["standard_id", ""],
  ["product_id", ""],
  ["input_mode", "DIRECT"],
  ["organization_name", ""],
  ["project_name", ""],
  ["notes", ""],
];
header(info.getRange("A1:B1"));
body(info.getRange("A2:B9"));
info.getRange("B3").format.numberFormat = "yyyy-mm-dd";
info.getRange("B6").dataValidation = { rule: { type: "list", values: ["DIRECT", "DETAIL"] } };
info.freezePanes.freezeRows(1);
info.showGridLines = false;
setWidths(info, { A: 28, B: 56 }, 20);

for (const sheetName of ["适用条件", "实际值"]) {
  const sheet = template.worksheets.getItem(sheetName);
  sheet.getRange("A1:E21").values = [["键", "名称", "值", "单位", "数据来源/备注"], ...Array.from({ length: 20 }, () => ["", "", "", "", ""])];
  header(sheet.getRange("A1:E1"));
  body(sheet.getRange("A2:E21"));
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  setWidths(sheet, { A: 34, B: 36, C: 20, D: 18, E: 52 }, 30);
}

const energy = template.worksheets.getItem("能源明细");
energy.getRange("A1:J51").values = [["行ID", "能源名称", "分类键", "方向", "实物量", "实物量单位", "折标系数", "系数单位", "分摊比例", "数据来源/备注"], ...Array.from({ length: 50 }, () => ["", "", "", "input", "", "", "", "", 1, ""])];
header(energy.getRange("A1:J1"));
body(energy.getRange("A2:J51"));
energy.getRange("D2:D51").dataValidation = { rule: { type: "list", values: ["input", "output"] } };
energy.getRange("I2:I51").format.numberFormat = "0.0000";
energy.freezePanes.freezeRows(1);
energy.showGridLines = false;
setWidths(energy, { A: 16, B: 24, C: 22, D: 12, E: 16, F: 16, G: 16, H: 20, I: 14, J: 46 }, 60);

const production = template.worksheets.getItem("产量与分摊");
production.getRange("A1:H31").values = [["行ID", "产品名称", "分类键", "产量", "单位", "折算系数", "是否合格", "数据来源/备注"], ...Array.from({ length: 30 }, () => ["", "", "", "", "", 1, "是", ""])];
header(production.getRange("A1:H1"));
body(production.getRange("A2:H31"));
production.getRange("G2:G31").dataValidation = { rule: { type: "list", values: ["是", "否"] } };
production.freezePanes.freezeRows(1);
production.showGridLines = false;
setWidths(production, { A: 16, B: 30, C: 22, D: 16, E: 14, F: 16, G: 14, H: 48 }, 40);

const templateCheck = await template.inspect({ kind: "table", range: "评价信息!A1:B9", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 4 });
process.stdout.write(`${templateCheck.ndjson}\n`);
const templateErrors = await template.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "template formula errors" });
process.stdout.write(`${templateErrors.ndjson}\n`);
for (const [sheetName, fileName, range] of [["填写说明", "template-instructions.png", "A1:C9"], ["评价信息", "template-info.png", "A1:B9"], ["适用条件", "template-conditions.png", "A1:E12"], ["实际值", "template-values.png", "A1:E12"], ["能源明细", "template-energy.png", "A1:J15"], ["产量与分摊", "template-production.png", "A1:H15"]]) {
  const preview = await template.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
const templateOutput = await SpreadsheetFile.exportXlsx(template);
await templateOutput.save(path.join(outputDir, "单位产品能耗对标导入模板.xlsx"));

process.stdout.write(`${path.join(outputDir, `${scopeCount}项标准规则确认表.xlsx`)}\n${path.join(outputDir, "单位产品能耗对标导入模板.xlsx")}\n`);
