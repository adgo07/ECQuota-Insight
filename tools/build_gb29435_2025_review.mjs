import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const dataDir = path.resolve(process.env.UEBENCH_WORKBOOK_DATA_DIR || "work/next-scope-63/data");
const outputDir = path.resolve(process.env.UEBENCH_WORKBOOK_OUTPUT_DIR || "work/next-scope-63");
const previewDir = path.resolve("work/artifact-next29435-2025/review-previews");
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
const definition = JSON.parse(await fs.readFile(path.join(dataDir, "definitions/gb-29435-2025.json"), "utf8"));
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
  sheet.getRange(subtitleRange).format.rowHeight = 34;
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

title(summary, "A1:G1", "GB 29435-2025标准规则专项复核表", "新标准为draft草案；51个产品/工序条目逐项核对，实施日期为2027-01-01，确认前不参与正式评价。");
summary.getRange("A4:B12").values = [
  ["标准编号", definition.number],
  ["标准名称", definition.title],
  ["发布日期/实施日期", String(definition.publication_date) + " / " + String(definition.effective_date)],
  ["标准状态", "draft（待确认）"],
  ["生命周期", "future（尚未实施）"],
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
summary.getRange("A" + noteRow).values = [["本标准表1～表6均为“单位产品综合能耗”指标，单位tce/t；1级、2级、3级直接对应原文表中1级、2级、3级，实际值不大于限额即达到该等级。现有企业按3级限定值，新建、改建和扩建企业按2级准入值。氟碳铈矿生产氧化镨钕还须选择工艺：氧化焙烧-盐酸浸出按表3，浓硫酸强化焙烧按表2。明细模式按公式（1）计算，缺少统计分类或合格产量时返回不完整。"]];
summary.getRange("A" + noteRow + ":G" + (noteRow + 4)).format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
summary.freezePanes.freezeRows(3); summary.showGridLines = false;
widths(summary, { A: 20, B: 44, C: 24, D: 14, E: 34, F: 14, G: 14 }, 80);

title(rules, "A1:T1", "GB 29435-2025规则逐项确认", "请逐行核对产品/工序、指标名称、单位、三级限额、条件/统计范围和原文页码；确认结论必须填写。");
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
widths(rules, { A: 8, B: 20, C: 40, D: 44, E: 50, F: 24, G: 14, H: 16, I: 16, J: 16, K: 72, L: 48, M: 10, N: 22, O: 24, P: 12, Q: 14, R: 14, S: 14, T: 34 }, 80);

title(formulas, "A1:H1", "公式、能源分类与适用条件核对", "本表把标准原文计算方法对应到软件规则；软件与Excel不各自判级，Excel只复现软件计算轨迹。");
formulas.getRange("A3:H3").values = [["编号", "原文项目", "标准公式/定义", "软件规则实现", "单位/录入要求", "PDF页码", "条款/表号", "复核结论"]]; header(formulas.getRange("A3:H3"));
const formulaRows = [
  ["（1）", "单位产品综合能耗 e_z", "e_z=[Σ(k_i·e_i)+E_FZ+E_FS−E_HW]/M_Z", "四类能源明细折标后相加；output方向的外供回收能源为负；kgce×0.001换成tce，再除以合格产品产量", "最终tce/t；能源明细折标结果kgce，产量t", 9, "6.2.1；公式（1）", "待确认"],
  ["（2）", "主要生产系统", "从原料投入至合格产品产出所耗能源", "分类键 energy.category.production_system", "折标准煤kgce", 8, "6.1.2.1～6.1.2.2", "待确认"],
  ["（3）", "辅助生产系统", "服务生产正常完成的设备设施耗能", "分类键 energy.category.auxiliary_system", "折标准煤kgce", 9, "6.1.2.3", "待确认"],
  ["（4）", "附属生产系统", "原料检测、化验、倒运、维修、食堂、行政等耗能", "分类键 energy.category.affiliated_system", "折标准煤kgce", 9, "6.1.2.4", "待确认"],
  ["（5）", "二次能源回收并外供量 E_HW", "公式中扣除外供量；自用、转供按原文归属", "分类键 energy.category.external_output，明细方向填output", "折标准煤kgce；没有外供也要填0行", 9, "6.1.2.5；公式（1）", "待确认"],
  ["（6）", "合格产品实物产量 M_Z", "报告期内合格产品产量", "production.total_equivalent", "t；统计期与能源明细一致", 9, "6.2.1；公式（1）", "待确认"],
];
formulas.getRange("A4:H9").values = formulaRows; body(formulas.getRange("A4:H9"));
formulas.getRange("A11:H11").values = [["条件/边界", "原文要求", "软件处理", "可能影响", "PDF页码", "条款/表号", "当前状态", "复核结论"]]; header(formulas.getRange("A11:H11"));
const conditionRows = [
  ["氟碳铈矿生产工艺", "氧化焙烧-盐酸浸出执行表3；浓硫酸强化焙烧按表2", "必填条件下拉框；限额用piecewise分支", "未选择工艺不得判级", 6, "4.1.3；表3脚注a", "draft", "待确认"],
  ["同线多产品无法分别计量", "按投入原料的稀土元素含量比例分摊", "能源明细填分摊比例；缺失时返回不完整", "影响各产品实际值", 8, "6.1.1", "draft", "待确认"],
  ["余热利用", "装置用能计入；回收自用/外供/转供按原文归属，避免重复计算", "输入方向和分类必须明确，软件保留逐步轨迹", "影响公式分子", 9, "6.1.2.5", "draft", "待确认"],
  ["能源折标系数", "实测或供应数据优先；无法获得时参考附录A、附录B", "每条能源明细携带折标系数和来源备注", "影响折标合计", 10, "6.2.2；附录A", "draft", "待确认"],
  ["非生产用途", "标准范围外的生活等用途不计入产品能耗", "不应录入四类生产能源分类", "错误录入会高估实际值", 8, "6.1.2", "draft", "待确认"],
];
formulas.getRange("A12:H16").values = conditionRows; body(formulas.getRange("A12:H16"));
formulas.getRange("H4:H9").dataValidation = { rule: { type: "list", values: ["待确认", "一致", "需修改"] } };
formulas.getRange("H12:H16").dataValidation = { rule: { type: "list", values: ["待确认", "一致", "需修改"] } };
["H4:H9", "H12:H16"].forEach(function(cellRange) {
  formulas.getRange(cellRange).conditionalFormats.add("cellIs", { operator: "equal", formula: '"一致"', format: { fill: green, font: { color: "#006100", bold: true } } });
  formulas.getRange(cellRange).conditionalFormats.add("cellIs", { operator: "equal", formula: '"需修改"', format: { fill: orange, font: { color: "#9C0006", bold: true } } });
});
formulas.getRange("A18:H21").merge();
formulas.getRange("A18").values = [["重点核对：2025版删除灯用稀土三基色荧光粉和抛光粉，增加钕铁硼废料综合回收产品；表1～表6的相同化学产品因生产类别不同分别列为不同“产品/工序”，指标名称仍统一为“单位产品综合能耗”。"]];
formulas.getRange("A18:H21").format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
formulas.freezePanes.freezeRows(3); formulas.freezePanes.freezeColumns(2); formulas.showGridLines = false;
widths(formulas, { A: 24, B: 34, C: 52, D: 62, E: 34, F: 12, G: 28, H: 16 }, 40);

title(corrections, "A1:H1", "GB 29435-2025替代、来源与订正记录", "本表显式记录标准替代关系和需要用户确认的实现口径，不修改标准原文。");
corrections.getRange("A3:H3").values = [["订正ID", "标准编号", "字段/事项", "原值/候选表述", "确认值/软件处理", "原因", "依据", "处理状态"]]; header(corrections.getRange("A3:H3"));
const correctionRows = [
  ["GB29435-replace", definition.number, "标准替代", "GB 29435-2012；稀土冶炼加工企业", "GB 29435-2025；稀土冶炼企业；旧版仅历史记录", "用户确认新标准替代关系", "新标准封面；PDF第1页/第3页", "待确认"],
  ["GB29435-date", definition.number, "发布日期/实施日期", "旧版2012-12-31/2013-10-01", "2025-12-31发布；2027-01-01实施", "按新标准封面记录", "PDF第1页", "待确认"],
  ["GB29435-scope", definition.number, "适用范围变化", "旧版含灯用稀土三基色荧光粉、抛光粉", "2025版删除上述产品，增加钕铁硼废料综合回收工艺产品", "按前言a、b记录", "PDF第3页；前言a、b", "待确认"],
  ["GB29435-levels", definition.number, "等级映射", "表中1级/2级/3级", "软件按原文1级/2级/3级直接比较；现有企业3级，新建改扩建2级", "按第4章和第5章实现", "PDF第5～8页；第4章、5.1、5.2", "待确认"],
  ["GB29435-footnote", definition.number, "表3脚注a", "氟碳铈矿生产氧化镨钕", "氧化焙烧-盐酸浸出用表3；浓硫酸强化焙烧用表2；工艺必填", "避免误套限额", "PDF第6页；4.1.3表3脚注a", "待确认"],
];
corrections.getRange("A4:H8").values = correctionRows; body(corrections.getRange("A4:H8"));
corrections.getRange("H4:H8").dataValidation = { rule: { type: "list", values: ["待确认", "一致", "需修改"] } };
corrections.getRange("H4:H8").conditionalFormats.add("cellIs", { operator: "equal", formula: '"一致"', format: { fill: green, font: { color: "#006100", bold: true } } });
corrections.getRange("H4:H8").conditionalFormats.add("cellIs", { operator: "equal", formula: '"需修改"', format: { fill: orange, font: { color: "#9C0006", bold: true } } });
corrections.freezePanes.freezeRows(3); corrections.showGridLines = false;
widths(corrections, { A: 24, B: 20, C: 24, D: 44, E: 52, F: 48, G: 34, H: 14 }, 30);

const tableCheck = await wb.inspect({ kind: "table", range: "确认汇总!A1:G" + (noteRow + 4), include: "values,formulas", tableMaxRows: 80, tableMaxCols: 10, tableMaxCellChars: 240 });
process.stdout.write(tableCheck.ndjson + "\n");
const errorCheck = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "GB 29435-2025 review workbook formula errors" });
process.stdout.write(errorCheck.ndjson + "\n");
const renders = [
  ["确认汇总", "gb29435-2025-summary.png", "A1:G" + (noteRow + 4)],
  ["规则确认", "gb29435-2025-rules.png", "A1:T12"],
  ["公式核对", "gb29435-2025-formulas.png", "A1:H21"],
  ["订正记录", "gb29435-2025-corrections.png", "A1:H9"],
];
for (const item of renders) {
  const preview = await wb.render({ sheetName: item[0], range: item[2], scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, item[1]), new Uint8Array(await preview.arrayBuffer()));
}
const exported = await SpreadsheetFile.exportXlsx(wb);
const outPath = path.join(outputDir, "GB 29435-2025标准规则专项复核表.xlsx");
await exported.save(outPath);
process.stdout.write("OUTPUT=" + outPath + "\nPREVIEWS=" + previewDir + "\n");

