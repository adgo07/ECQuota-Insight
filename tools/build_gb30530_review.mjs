import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const dataDir = path.resolve(process.env.UEBENCH_WORKBOOK_DATA_DIR || "work/next-scope-63/data");
const outputDir = path.resolve(process.env.UEBENCH_WORKBOOK_OUTPUT_DIR || "work/next-scope-63");
const previewDir = path.resolve("work/artifact-next30530/review-previews");
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
const definition = JSON.parse(await fs.readFile(path.join(dataDir, "definitions/gb-30530-2024.json"), "utf8"));
const products = definition.products;
const indicators = products.flatMap(function(product) {
  return product.indicators.map(function(indicator) { return { product: product, indicator: indicator }; });
});

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
  const a = start.match(/[A-Z]+/)[0];
  const b = range.split(":")[1].match(/[A-Z]+/)[0];
  const subtitleRange = a + row + ":" + b + row;
  sheet.getRange(subtitleRange).merge();
  sheet.getRange(a + row).values = [[subtitle]];
  sheet.getRange(subtitleRange).format = { fill: lightBlue, font: { color: navy, italic: true }, horizontalAlignment: "left", verticalAlignment: "center", wrapText: true };
  sheet.getRange(subtitleRange).format.rowHeight = 36;
}
function header(range) {
  range.format = { fill: blue, font: { bold: true, color: white }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: border } };
  range.format.rowHeight = 30;
}
function body(range) {
  range.format = { fill: white, font: { color: "#1F2937" }, verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: border } };
}
function widths(sheet, values, rows) {
  const maxRows = rows || 220;
  Object.entries(values).forEach(function(pair) {
    sheet.getRange(pair[0] + "1:" + pair[0] + maxRows).format.columnWidth = pair[1];
  });
}
function threshold(indicator, level) {
  const expression = (indicator.thresholds || {})[level] || (indicator.base_thresholds || {})[level];
  if (!expression) return "—";
  if (expression.op === "constant") return expression.value;
  return "按条件选择";
}
function sourceSummary(indicator) {
  return indicator.source_references.map(function(item) {
    return "PDF第" + item.page + "页；" + (item.clause || "") + (item.table ? "；" + item.table : "");
  }).join("\n");
}

const wb = Workbook.create();
const summary = wb.worksheets.add("确认汇总");
const rules = wb.worksheets.add("规则确认");
const formulas = wb.worksheets.add("公式核对");
const corrections = wb.worksheets.add("订正记录");
wb.comments.setSelf({ displayName: "User" });

title(summary, "A1:G1", "GB 30530-2024标准规则专项复核表", "新标准为draft草案；1个产品/工序、1个指标逐项核对，实施日期为2025-05-01，确认前不参与正式评价。评价日期为软件运行当天；标准选择需由用户确认。" );
summary.getRange("A4:B12").values = [
  ["标准编号", definition.number],
  ["标准名称", definition.title],
  ["发布日期/实施日期", String(definition.publication_date) + " / " + String(definition.effective_date)],
  ["标准状态", "draft（待确认）"],
  ["生命周期", "active（已实施，尚未发布规则）"],
  ["原文文件", definition.source_file],
  ["原文SHA-256", definition.source_sha256],
  ["产品/工序数", products.length],
  ["指标数", null],
];
summary.getRange("A4:A12").format = { fill: lightBlue, font: { bold: true, color: navy }, verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: border } };
body(summary.getRange("B4:B12"));
summary.getRange("B12").formulas = [["=COUNTA('规则确认'!$E$4:$E$" + (3 + indicators.length) + ")"]];
summary.getRange("A14:G14").values = [["标准编号", "产品/工序", "指标名称", "单位", "1级/2级/3级基础限额", "复核状态", "确认结论"]];
header(summary.getRange("A14:G14"));
const summaryRows = indicators.map(function(item) {
  const product = item.product;
  const indicator = item.indicator;
  return [definition.number, product.name, indicator.name, indicator.unit,
    "≤" + threshold(indicator, "level_1") + " / ≤" + threshold(indicator, "level_2") + " / ≤" + threshold(indicator, "level_3"),
    definition.publication_status, "待确认"];
});
summary.getRange("A15:G" + (14 + summaryRows.length)).values = summaryRows;
body(summary.getRange("A15:G" + (14 + summaryRows.length)));
const noteRow = 17 + summaryRows.length;
summary.getRange("A" + noteRow + ":G" + (noteRow + 4)).merge();
summary.getRange("A" + noteRow).values = [["本标准表1只有一项“二甲基硅氧烷单位产品能耗”指标，单位kgce/t，三级限额为650、750、1000，实际值不大于限额即达到相应等级。现有企业执行3级限定值，新（扩、改）建企业执行2级准入值。明细模式按公式（1）计入生产、辅助、附属系统以及外购硅粉和氯甲烷原材料能耗，按公式（2）合并合格水解物、环体、线性体和外售二甲基二氯硅烷折算产量，最后按公式（3）计算。回收利用和向外输出的能源不计入。"]];
summary.getRange("A" + noteRow + ":G" + (noteRow + 4)).format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
summary.freezePanes.freezeRows(3); summary.showGridLines = false;
widths(summary, { A: 20, B: 44, C: 24, D: 18, E: 34, F: 14, G: 14 }, 80);

title(rules, "A1:T1", "GB 30530-2024规则逐项确认", "请核对产品/工序、指标名称、单位、三级限额、原材料能耗、产量折算和原文页码；确认结论必须填写。" );
const headers = ["序号", "标准编号", "标准名称", "产品/工序", "指标ID", "指标名称", "单位", "1级基础限额", "2级基础限额", "3级基础限额", "修正与适用说明", "来源定位", "PDF页码", "条款", "表号", "复核状态", "确认结论", "确认人", "确认日期", "确认备注"];
rules.getRange("A3:T3").values = [headers]; header(rules.getRange("A3:T3"));
const ruleRows = indicators.map(function(item, index) {
  const product = item.product;
  const indicator = item.indicator;
  const first = indicator.source_references[0];
  return [index + 1, definition.number, definition.title, product.name, indicator.id, indicator.name, indicator.unit,
    threshold(indicator, "level_1"), threshold(indicator, "level_2"), threshold(indicator, "level_3"),
    (indicator.notes || []).join("\n"), sourceSummary(indicator), first.page, first.clause || "", first.table || "",
    definition.publication_status, "待确认", "", null, ""];
});
rules.getRange("A4:T" + (3 + ruleRows.length)).values = ruleRows;
body(rules.getRange("A4:T" + (3 + ruleRows.length)));
rules.getRange("M4:M" + (3 + ruleRows.length)).format.numberFormat = "0";
rules.getRange("S4:S" + (3 + ruleRows.length)).format.numberFormat = "yyyy-mm-dd";
rules.getRange("Q4:Q" + (3 + ruleRows.length)).dataValidation = { rule: { type: "list", values: ["待确认", "同意发布", "退回修改"] } };
rules.getRange("Q4:Q" + (3 + ruleRows.length)).conditionalFormats.add("cellIs", { operator: "equal", formula: '"同意发布"', format: { fill: green, font: { color: "#006100", bold: true } } });
rules.getRange("Q4:Q" + (3 + ruleRows.length)).conditionalFormats.add("cellIs", { operator: "equal", formula: '"退回修改"', format: { fill: orange, font: { color: "#9C0006", bold: true } } });
rules.freezePanes.freezeRows(3); rules.freezePanes.freezeColumns(2); rules.showGridLines = false;
widths(rules, { A: 8, B: 20, C: 40, D: 32, E: 50, F: 24, G: 18, H: 16, I: 16, J: 16, K: 72, L: 48, M: 10, N: 24, O: 24, P: 12, Q: 14, R: 14, S: 14, T: 34 }, 80);

title(formulas, "A1:H1", "公式、原材料能耗与产量折算核对", "本表把标准原文计算方法对应到软件规则；软件与Excel不各自判级，Excel只复现软件计算轨迹。" );
formulas.getRange("A3:H3").values = [["编号", "原文项目", "标准公式/定义", "软件规则实现", "单位/录入要求", "PDF页码", "条款/表号", "复核结论"]]; header(formulas.getRange("A3:H3"));
const formulaRows = [
  ["（1）", "二甲基硅氧烷产品综合能耗 E", "E=Σ(ci×pi)+Σ(ej×pj)+Σ(gk×qk)", "生产、辅助、附属系统能源明细先折标准煤后分类汇总；外购硅粉量×单位能源消耗、外购氯甲烷量×单位能源消耗另行相加。", "E为kgce；每条能源须有实测/供应数据或GB/T2589、附录A/B折标依据；原材料g为t、q为kgce/t", 7, "6.2.2；公式（1）", "待确认"],
  ["（2）", "二甲基硅氧烷产品产量 M", "M=M1+M2+M3+μ×M4", "产量与分摊工作表分别录入合格水解物、环体、线性体和外售二甲基二氯硅烷；外售二甲基二氯硅烷行的conversion_factor作为μ。", "各产量单位t；μ按当期监测值，无当期数据可取0.56；水解物不得重复计入", 7, "6.2.3；公式（2）", "待确认"],
  ["（3）", "二甲基硅氧烷单位产品能耗 e", "e=E/M", "detail_formula按E除以production.total_equivalent；结果kgce/t；产量为0或缺失返回不完整。", "E为kgce，M为t；不得为0", 8, "6.2.4；公式（3）", "待确认"],
  ["（4）", "生产系统", "硅粉加工至成品入库及废物预处理送出全过程", "分类键energy.category.production_system.net_standard_coal", "折标准煤kgce；包含标准列出的完整工艺过程", 6, "6.1.2", "待确认"],
  ["（5）", "辅助/附属系统", "供电、供水、供气、采暖、制冷、机修、仪修、照明、库房、检验等", "分类键energy.category.auxiliary_system或affiliated_system.net_standard_coal", "折标准煤kgce；生活、基建、技改不计入", 6, "6.1.3～6.1.4", "待确认"],
  ["（6）", "回收利用和外供能源", "综合能耗不包括生产过程中回收利用的和向外输出的能源量", "外供/回收能源不得并入三类计入分类；软件保留明细但本规则公式不使用external_output。", "分类和方向必须明确", 6, "6.1.5", "待确认"],
];
formulas.getRange("A4:H9").values = formulaRows; body(formulas.getRange("A4:H9"));
formulas.getRange("A11:H11").values = [["条件/边界", "原文要求", "软件处理", "可能影响", "PDF页码", "条款/表号", "当前状态", "复核结论"]]; header(formulas.getRange("A11:H11"));
const conditionRows = [
  ["现有企业", "执行表1中的3级限定值", "等级仍按1/2/3阈值分别输出；评价信息记录企业类型供提示。", "影响限定值提示，不改变三级限额", 6, "5.1", "draft", "待确认"],
  ["新（扩、改）建企业", "执行表1中的2级准入值", "选择企业类型后显示2级准入提示；超过2级但不超过3级可判3级，但提示不满足准入要求。", "影响准入提示", 6, "5.2", "draft", "待确认"],
  ["外购硅粉/氯甲烷", "外购原料能耗按当期单位能源消耗计入；无监测时使用0.0275tce/t、0.0797tce/t参考值", "两个原料数量和单位能源消耗均为必填DETAIL输入；没有外购量填0并说明。", "影响公式（1）分子", 7, "6.2.2；公式（1）", "draft", "待确认"],
  ["外售二甲基二氯硅烷", "按μ折算为二甲基硅氧烷产量；无当期检测数据时μ可取0.56", "在产量明细行中填写conversion_factor；缺少折算行会导致产量不完整。", "影响公式（2）分母", 7, "6.2.3；公式（2）", "draft", "待确认"],
  ["水解物重复计量", "用于生产环体或线性体的水解物不重复计入产量", "用户需在产量明细备注中说明内部转用水解物；软件不自动推断，无法确定时返回不完整。", "影响公式（2）分母", 7, "6.2.3注", "draft", "待确认"],
  ["折标系数", "实测或供应数据优先，无法获得时参考附录A、附录B", "每条能源明细记录系数及来源备注，保留计算轨迹。", "影响公式（1）分子", 9, "附录A、附录B", "draft", "待确认"],
];
formulas.getRange("A12:H17").values = conditionRows; body(formulas.getRange("A12:H17"));
formulas.getRange("H4:H9").dataValidation = { rule: { type: "list", values: ["待确认", "一致", "需修改"] } };
formulas.getRange("H12:H17").dataValidation = { rule: { type: "list", values: ["待确认", "一致", "需修改"] } };
["H4:H9", "H12:H17"].forEach(function(cellRange) {
  formulas.getRange(cellRange).conditionalFormats.add("cellIs", { operator: "equal", formula: '"一致"', format: { fill: green, font: { color: "#006100", bold: true } } });
  formulas.getRange(cellRange).conditionalFormats.add("cellIs", { operator: "equal", formula: '"需修改"', format: { fill: orange, font: { color: "#9C0006", bold: true } } });
});
formulas.getRange("A19:H22").merge();
formulas.getRange("A19").values = [["重点核对：本标准2024版已把旧版“有机硅环体”范围改为二甲基硅氧烷（包括水解物、环体和线性体），增加能耗等级、外购硅粉/氯甲烷能耗统计和外售二甲基二氯硅烷产量折算。产品/工序填写“二甲基硅氧烷”，指标名称填写“单位产品能耗”，合并后与原文完整表述一致。"]];
formulas.getRange("A19:H22").format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
formulas.freezePanes.freezeRows(3); formulas.freezePanes.freezeColumns(2); formulas.showGridLines = false;
widths(formulas, { A: 24, B: 34, C: 48, D: 68, E: 42, F: 12, G: 28, H: 16 }, 45);

title(corrections, "A1:H1", "GB 30530-2024来源、替代与订正记录", "本表显式记录标准替代关系和需要用户确认的实现口径，不修改标准原文。" );
corrections.getRange("A3:H3").values = [["订正ID", "标准编号", "字段/事项", "原值/候选表述", "确认值/软件处理", "原因", "依据", "处理状态"]]; header(corrections.getRange("A3:H3"));
const correctionRows = [
  ["GB30530-replace", definition.number, "标准替代", "GB 30530-2014；有机硅环体单位产品能源消耗限额", "GB 30530-2024；二甲基硅氧烷单位产品能源消耗限额；旧版仅历史选择", "按新标准封面及前言替代关系记录", "PDF第1、3页", "待确认"],
  ["GB30530-date", definition.number, "发布日期/实施日期", "旧版日期未作为当前目录元数据", "2024-04-29发布；2025-05-01实施", "按新标准封面记录", "PDF第1页", "待确认"],
  ["GB30530-scope", definition.number, "适用范围变化", "旧版主要针对有机硅环体", "二甲基硅氧烷包括水解物、环体和线性体；产品/工序统一填二甲基硅氧烷", "按前言a、术语3.1～3.6记录", "PDF第3、5～6页", "待确认"],
  ["GB30530-levels", definition.number, "等级与企业类型", "旧版无现行三级映射", "表1为1级650、2级750、3级1000kgce/t；现有企业3级，新改扩建2级准入", "区分判级和准入要求", "PDF第6页；第4、5章", "待确认"],
  ["GB30530-materials", definition.number, "外购原料能耗", "候选通用公式未体现外购原料", "硅粉、氯甲烷数量×单位能源消耗写入公式（1）；无监测时使用原文参考系数", "按2024版新增统计要求实现", "PDF第3、7页；6.2.2", "待确认"],
  ["GB30530-output", definition.number, "产量折算", "候选通用公式直接使用单一产量", "M=M1+M2+M3+μ×M4；外售二甲基二氯硅烷μ按监测值或0.56", "按公式（2）实现产量明细", "PDF第7页；6.2.3", "待确认"],
];
corrections.getRange("A4:H" + (3 + correctionRows.length)).values = correctionRows; body(corrections.getRange("A4:H" + (3 + correctionRows.length)));
corrections.getRange("H4:H" + (3 + correctionRows.length)).dataValidation = { rule: { type: "list", values: ["待确认", "一致", "需修改"] } };
corrections.getRange("H4:H" + (3 + correctionRows.length)).conditionalFormats.add("cellIs", { operator: "equal", formula: '"一致"', format: { fill: green, font: { color: "#006100", bold: true } } });
corrections.getRange("H4:H" + (3 + correctionRows.length)).conditionalFormats.add("cellIs", { operator: "equal", formula: '"需修改"', format: { fill: orange, font: { color: "#9C0006" } } });
corrections.freezePanes.freezeRows(3); corrections.showGridLines = false;
widths(corrections, { A: 24, B: 20, C: 24, D: 44, E: 58, F: 48, G: 34, H: 14 }, 35);

const tableCheck = await wb.inspect({ kind: "table", range: "确认汇总!A1:G" + (noteRow + 4), include: "values,formulas", tableMaxRows: 80, tableMaxCols: 10, tableMaxCellChars: 240 });
process.stdout.write(tableCheck.ndjson + "\n");
const errorCheck = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "GB 30530-2024 review workbook formula errors" });
process.stdout.write(errorCheck.ndjson + "\n");
const renders = [
  ["确认汇总", "gb30530-2024-summary.png", "A1:G" + (noteRow + 4)],
  ["规则确认", "gb30530-2024-rules.png", "A1:T8"],
  ["公式核对", "gb30530-2024-formulas.png", "A1:H22"],
  ["订正记录", "gb30530-2024-corrections.png", "A1:H10"],
];
for (const item of renders) {
  const preview = await wb.render({ sheetName: item[0], range: item[2], scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, item[1]), new Uint8Array(await preview.arrayBuffer()));
}
const exported = await SpreadsheetFile.exportXlsx(wb);
const outPath = path.join(outputDir, "GB 30530-2024标准规则专项复核表.xlsx");
await exported.save(outPath);
process.stdout.write("OUTPUT=" + outPath + "\nPREVIEWS=" + previewDir + "\n");
