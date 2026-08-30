import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const dataDir = path.resolve(process.env.UEBENCH_WORKBOOK_DATA_DIR || "work/next-scope-63/data");
const outputDir = path.resolve(process.env.UEBENCH_WORKBOOK_OUTPUT_DIR || "work/next-scope-63");
const previewDir = path.resolve("work/artifact-next31823/review-previews");
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const definition = JSON.parse(await fs.readFile(path.join(dataDir, "definitions/gb-31823-2021.json"), "utf8"));
const products = definition.products;
const indicators = products.flatMap((product) => product.indicators.map((indicator) => ({ product, indicator })));

const navy = "#17365D";
const blue = "#2F75B5";
const lightBlue = "#D9EAF7";
const paleBlue = "#F4F7FB";
const border = "#B4C6E7";
const white = "#FFFFFF";
const green = "#E2F0D9";
const orange = "#FCE4D6";

function title(sheet, range, text, subtitle) {
  sheet.getRange(range).merge();
  const start = range.split(":")[0];
  sheet.getRange(start).values = [[text]];
  sheet.getRange(range).format = { fill: navy, font: { bold: true, color: white, size: 18 }, horizontalAlignment: "center", verticalAlignment: "center" };
  sheet.getRange(range).format.rowHeight = 34;
  const row = Number(start.match(/\d+/)[0]) + 1;
  const first = start.match(/[A-Z]+/)[0];
  const last = range.split(":")[1].match(/[A-Z]+/)[0];
  sheet.getRange(first + row + ":" + last + row).merge();
  sheet.getRange(first + row).values = [[subtitle]];
  sheet.getRange(first + row + ":" + last + row).format = { fill: lightBlue, font: { color: navy, italic: true }, horizontalAlignment: "left", verticalAlignment: "center", wrapText: true };
  sheet.getRange(first + row + ":" + last + row).format.rowHeight = 34;
}
function header(range) {
  range.format = { fill: blue, font: { bold: true, color: white }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: border } };
  range.format.rowHeight = 30;
}
function body(range) {
  range.format = { fill: white, font: { color: "#1F2937" }, verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: border } };
}
function widths(sheet, values, rows = 220) {
  for (const [column, width] of Object.entries(values)) sheet.getRange(column + "1:" + column + rows).format.columnWidth = width;
}
function threshold(indicator, level) {
  const expression = indicator.thresholds[level] || indicator.base_thresholds[level];
  if (!expression) return "—";
  return expression.op === "constant" ? expression.value : "按条件选择";
}
function sourceSummary(indicator) {
  return indicator.source_references.map((item) => "PDF第" + item.page + "页；" + (item.clause || "") + "；" + (item.table || "")).join("\n");
}

const wb = Workbook.create();
const summary = wb.worksheets.add("确认汇总");
const rules = wb.worksheets.add("规则确认");
const formulas = wb.worksheets.add("公式核对");
const corrections = wb.worksheets.add("订正记录");
wb.comments.setSelf({ displayName: "User" });

title(summary, "A1:G1", "GB 31823-2021标准规则专项复核表", "本标准规则为draft草案；3类码头逐项核对，确认前不参与正式评价。软件评价日期读取运行当天；旧版或尚未实施标准须由用户手动选择并显示提示。");
summary.getRange("A4:B12").values = [
  ["标准编号", definition.number],
  ["标准名称", definition.title],
  ["发布日期/实施日期", String(definition.publication_date) + " / " + String(definition.effective_date)],
  ["标准状态", "draft（待确认）"],
  ["生命周期", "active（2022-11-01已实施，规则尚未发布）"],
  ["原文文件", definition.source_file],
  ["原文SHA-256", definition.source_sha256],
  ["产品/工序数", products.length],
  ["指标数", indicators.length],
];
summary.getRange("A4:A12").format = { fill: lightBlue, font: { bold: true, color: navy }, verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: border } };
body(summary.getRange("B4:B12"));
summary.getRange("A14:G14").values = [["标准编号", "产品/工序", "指标名称", "单位", "1级/2级/3级基础限额", "复核状态", "确认结论"]];
header(summary.getRange("A14:G14"));
const summaryRows = indicators.map(({ product, indicator }) => [
  definition.number, product.name, indicator.name, indicator.unit,
  "≤" + threshold(indicator, "level_1") + " / ≤" + threshold(indicator, "level_2") + " / ≤" + threshold(indicator, "level_3"),
  definition.publication_status, "待确认",
]);
summary.getRange("A15:G" + (14 + summaryRows.length)).values = summaryRows;
body(summary.getRange("A15:G" + (14 + summaryRows.length)));
const noteRow = 19;
summary.getRange("A" + noteRow + ":G" + (noteRow + 5)).merge();
summary.getRange("A" + noteRow).values = [["本标准把专业化集装箱、干散货（煤炭/矿石）和原油码头分别列为产品/工序，指标名称统一为“单位产品可比综合能耗”。表1三级限额分别为：集装箱码头24/28/45 tce/10^4TEU，干散货码头1.8/2.0/2.7 tce/10^4t，原油码头0.36/0.51/0.88 tce/10^4t。现有码头执行3级；新建、改建和扩建码头执行2级。"]];
summary.getRange("A" + noteRow + ":G" + (noteRow + 5)).format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
summary.freezePanes.freezeRows(3);
summary.showGridLines = false;
widths(summary, { A: 20, B: 34, C: 24, D: 18, E: 36, F: 14, G: 14 }, 80);

title(rules, "A1:T1", "GB 31823-2021规则逐项确认", "请逐行核对产品/工序、指标名称、单位、三级限额、统计范围、公式和原文页码；确认结论必须填写。");
const ruleHeaders = ["序号", "标准编号", "标准名称", "产品/工序", "指标ID", "指标名称", "单位", "1级基础限额", "2级基础限额", "3级基础限额", "修正与适用说明", "来源定位", "PDF页码", "条款", "表号", "复核状态", "确认结论", "确认人", "确认日期", "确认备注"];
rules.getRange("A3:T3").values = [ruleHeaders];
header(rules.getRange("A3:T3"));
const ruleRows = indicators.map(({ product, indicator }, index) => {
  const first = indicator.source_references[0];
  return [index + 1, definition.number, definition.title, product.name, indicator.id, indicator.name, indicator.unit,
    threshold(indicator, "level_1"), threshold(indicator, "level_2"), threshold(indicator, "level_3"),
    indicator.notes.join("\n"), sourceSummary(indicator), first.page, first.clause || "", first.table || "",
    definition.publication_status, "待确认", "", null, ""];
});
rules.getRange("A4:T" + (3 + ruleRows.length)).values = ruleRows;
body(rules.getRange("A4:T" + (3 + ruleRows.length)));
rules.getRange("Q4:Q" + (3 + ruleRows.length)).dataValidation = { rule: { type: "list", values: ["待确认", "同意发布", "退回修改"] } };
rules.getRange("S4:S" + (3 + ruleRows.length)).format.numberFormat = "yyyy-mm-dd";
rules.getRange("Q4:Q" + (3 + ruleRows.length)).conditionalFormats.add("cellIs", { operator: "equal", formula: '"同意发布"', format: { fill: green, font: { color: "#006100", bold: true } } });
rules.getRange("Q4:Q" + (3 + ruleRows.length)).conditionalFormats.add("cellIs", { operator: "equal", formula: '"退回修改"', format: { fill: orange, font: { color: "#9C0006", bold: true } } });
rules.freezePanes.freezeRows(3);
rules.freezePanes.freezeColumns(2);
rules.showGridLines = false;
widths(rules, { A: 8, B: 20, C: 38, D: 30, E: 52, F: 24, G: 18, H: 16, I: 16, J: 16, K: 78, L: 48, M: 10, N: 30, O: 24, P: 12, Q: 14, R: 14, S: 14, T: 34 }, 80);

title(formulas, "A1:H1", "公式、统计范围与适用条件核对", "本表把标准原文计算方法对应到软件规则；Excel只复现软件计算轨迹，不建立第二套判级逻辑。");
formulas.getRange("A3:H3").values = [["编号", "原文项目", "标准公式/定义", "软件规则实现", "单位/录入要求", "PDF页码", "条款/表号", "复核结论"]];
header(formulas.getRange("A3:H3"));
const formulaRows = [
  ["（1）", "集装箱码头单位产品可比综合能耗", "eₖ=(Ez+Ef)/T×a", "生产、辅助、附属系统折标量分别汇总并换算为tce，除以10^4TEU吞吐量，再乘吞吐量适应系数a。", "T为折算后的10^4TEU；L=设计通过能力/实际完成吞吐量", 5, "6.2.1.1；公式（1）", "待确认"],
  ["（2）", "集装箱码头吞吐量适应系数", "0＜L≤2:1.0；2＜L≤3:0.95；3＜L≤4:0.9；L＞4:0.85", "condition.GB31823.container.adaptation_degree分段piecewise。", "L为ratio且必须大于0；边界按原文闭开区间处理", 5, "6.2.1.2", "待确认"],
  ["（3）", "集装箱箱型折算", "48ft/45ft/40ft/35ft/20ft/10ft=2.40/2.25/2.00/1.75/1.00/0.50TEU", "产量明细用conversion_factor折算后汇总；附录B数值由录入模板提示。", "产量单位10^4TEU；记录箱型和折算系数来源", 10, "附录B；表B.1", "待确认"],
  ["（4）", "干散货码头单位产品可比综合能耗", "eₖ=(gkEz+Ef)/T×c", "生产系统Ez乘g、k；辅助及附属系统Ef不乘g/k；合计除以10^4t吞吐量，再乘c。", "T为10^4t；所有能源先按折标系数换算为tce", 6, "6.2.2.1；公式（4）", "待确认"],
  ["（5）", "干散货卸货量修正系数", "50%≤w≤100%: g=1/(1.4w+0.04)；0≤w＜50%: g=1/(1−0.53w)", "unloading_share按fraction录入；门座式起重机时g=1.0，直接卸货至后方工厂时g=1.3。", "w取0～1；两种特殊条件优先于比例分段", 6, "6.2.2.2；公式（5）及脚注", "待确认"],
  ["（6）", "干散货作业线长度修正系数", "L≤500:1.1；500<L≤1000:1.05；1000<L≤1500:1.0；1500<L≤2000:0.95；2000<L≤3000:0.9；L>3000:0.85", "work_line_length按m录入并piecewise；不引入汇编或其他资料中的额外区域系数。", "L≥0m；边界按原文闭开区间", 7, "6.2.2.3；公式（6）", "待确认"],
  ["（7）", "干散货采暖修正系数", "采暖地区c=0.95；非采暖地区c=1.0", "heating_region限定为“采暖地区/非采暖地区”，piecewise选择c。", "选择项必须与GB 50189口径一致", 6, "6.2.2.1；公式（4）", "待确认"],
  ["（8）", "原油码头单位产品可比综合能耗", "eₖ=(Ez+Ef)/T", "生产、辅助、附属系统及βt修正后的管道伴热能耗合计，除以10^4t吞吐量。", "原油吞吐量占总吞吐量应符合范围条件；后方储存区不计入", 8, "6.3.2.1；公式（8）", "待确认"],
  ["（9）", "原油管道伴热温度修正", "Ebp按βt修正：0℃条件0.95，其他条件1.0", "pipeline_heat单独分类；pipeline_heat_temperature按℃录入，当前按≤0℃/＞0℃分段，边界需复核。", "不得把管道伴热重复放入辅助/附属系统", 8, "6.3.2.2～6.3.2.3；公式（10）", "待确认"],
  ["（10）", "能源折标与统计边界", "E=Σ(Ei×pi)；生产/辅助/附属系统按标准边界计入", "每条EnergyLine保留实物量、折标系数、方向、分摊比例和来源；kgce统一换算为tce。", "生活用能、超范围储存区等不得混入", 5, "6.1；附录A", "待确认"],
];
formulas.getRange("A4:H" + (3 + formulaRows.length)).values = formulaRows;
body(formulas.getRange("A4:H" + (3 + formulaRows.length)));
formulas.getRange("A" + (6 + formulaRows.length) + ":H" + (9 + formulaRows.length)).merge();
formulas.getRange("A" + (6 + formulaRows.length)).values = [["重点核对：GB 31823-2021已替代GB 31823-2015和GB 31827-2015。产品/工序只写“集装箱码头、干散货码头、原油码头”，指标名称统一为“单位产品可比综合能耗”。原油管道伴热温度边界当前按≤0℃实现，若原文明确为“低于0℃”或其他口径，请在本表确认结论中选择“退回修改”。"]];
formulas.getRange("A" + (6 + formulaRows.length) + ":H" + (9 + formulaRows.length)).format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
formulas.getRange("H4:H" + (3 + formulaRows.length)).dataValidation = { rule: { type: "list", values: ["待确认", "一致", "需修改"] } };
formulas.getRange("H4:H" + (3 + formulaRows.length)).conditionalFormats.add("cellIs", { operator: "equal", formula: '"一致"', format: { fill: green, font: { color: "#006100", bold: true } } });
formulas.getRange("H4:H" + (3 + formulaRows.length)).conditionalFormats.add("cellIs", { operator: "equal", formula: '"需修改"', format: { fill: orange, font: { color: "#9C0006", bold: true } } });
formulas.freezePanes.freezeRows(3);
formulas.freezePanes.freezeColumns(2);
formulas.showGridLines = false;
widths(formulas, { A: 12, B: 30, C: 52, D: 72, E: 42, F: 10, G: 32, H: 16 }, 40);

title(corrections, "A1:H1", "GB 31823-2021来源、替代与订正记录", "本表记录标准替代关系和当前需要确认的实现口径，不修改标准原文。");
corrections.getRange("A3:H3").values = [["订正ID", "标准编号", "字段/事项", "原值/候选表述", "确认值/软件处理", "原因", "依据", "处理状态"]];
header(corrections.getRange("A3:H3"));
const correctionRows = [
  ["GB31823-replace", definition.number, "标准替代", "GB 31823-2015、GB 31827-2015分别管理集装箱和干散货码头", "GB 31823-2021统一管理专业化集装箱、干散货和原油码头；旧版仅历史选择", "按现行强制文本封面和前言替代关系记录", "PDF第1页；前言", "待确认"],
  ["GB31823-date", definition.number, "发布日期/实施日期", "旧版日期", "2021-10-11发布；2022-11-01实施", "按新标准封面记录", "PDF第1页", "待确认"],
  ["GB31823-scope", definition.number, "适用范围", "码头类型范围需拆分", "专业化集装箱、干散货（煤炭/矿石）、原油码头；自动化集装箱、原油后方储存区等排除条件按原文确认", "按第1章和第3章范围、术语核对", "PDF第4页", "待确认"],
  ["GB31823-levels", definition.number, "等级与企业类型", "表中1级/2级/3级", "软件分别输出三级；现有码头执行3级，新建改建扩建执行2级准入提示", "区分判级和准入要求", "PDF第4页；第5章", "待确认"],
  ["GB31823-container", definition.number, "集装箱公式与箱型折算", "eₖ=(Ez+Ef)/T×a；L区间和附录B折算", "规则已实现a分段、TEU折算提示和完整计算轨迹", "避免吞吐量适应度和箱型换算遗漏", "PDF第5页、第10页；公式（1）；表B.1", "待确认"],
  ["GB31823-dry", definition.number, "干散货修正", "g、k、c修正及门座式起重机脚注", "规则已实现g/k/c；不引入其他资料中的区域修正系数", "按第6章公式（4）～（7）实现", "PDF第6～7页", "待确认"],
  ["GB31823-crude", definition.number, "原油伴热修正", "Ebp和βt边界需确认", "pipeline_heat独立分类；当前≤0℃取0.95、＞0℃取1.0，边界保留退回修改入口", "避免管道伴热重复计入并保留不确定性", "PDF第8页；公式（8）～（10）", "待确认"],
  ["GB31823-energy", definition.number, "能源折标与计量", "附录A折标系数", "用户可录入实测或标准参考折标系数；每条能源保留来源和分摊比例", "保证明细模式可审计", "PDF第5页、第9页；附录A", "待确认"],
];
corrections.getRange("A4:H" + (3 + correctionRows.length)).values = correctionRows;
body(corrections.getRange("A4:H" + (3 + correctionRows.length)));
corrections.getRange("H4:H" + (3 + correctionRows.length)).dataValidation = { rule: { type: "list", values: ["待确认", "一致", "需修改"] } };
corrections.getRange("H4:H" + (3 + correctionRows.length)).conditionalFormats.add("cellIs", { operator: "equal", formula: '"一致"', format: { fill: green, font: { color: "#006100", bold: true } } });
corrections.getRange("H4:H" + (3 + correctionRows.length)).conditionalFormats.add("cellIs", { operator: "equal", formula: '"需修改"', format: { fill: orange, font: { color: "#9C0006" } } });
corrections.freezePanes.freezeRows(3);
corrections.showGridLines = false;
widths(corrections, { A: 24, B: 20, C: 24, D: 48, E: 58, F: 48, G: 36, H: 14 }, 40);

const tableCheck = await wb.inspect({ kind: "table", range: "确认汇总!A1:G" + (noteRow + 5), include: "values,formulas", tableMaxRows: 80, tableMaxCols: 10, tableMaxCellChars: 260 });
process.stdout.write(tableCheck.ndjson + "\n");
const errorCheck = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "GB 31823-2021 review workbook formula errors" });
process.stdout.write(errorCheck.ndjson + "\n");

for (const [sheetName, fileName, range] of [
  ["确认汇总", "gb31823-2021-summary.png", "A1:G24"],
  ["规则确认", "gb31823-2021-rules.png", "A1:T8"],
  ["公式核对", "gb31823-2021-formulas.png", "A1:H24"],
  ["订正记录", "gb31823-2021-corrections.png", "A1:H12"],
]) {
  const preview = await wb.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
const exported = await SpreadsheetFile.exportXlsx(wb);
const outPath = path.join(outputDir, "GB 31823-2021标准规则专项复核表.xlsx");
await exported.save(outPath);
process.stdout.write("OUTPUT=" + outPath + "\nPREVIEWS=" + previewDir + "\n");

