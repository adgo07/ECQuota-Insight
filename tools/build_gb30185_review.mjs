import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const dataDir = path.resolve(process.env.UEBENCH_WORKBOOK_DATA_DIR || "work/next-scope-63/data");
const outputDir = path.resolve(process.env.UEBENCH_WORKBOOK_OUTPUT_DIR || "work/next-scope-63");
const previewDir = path.resolve("work/artifact-next30185/review-previews");
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
const definition = JSON.parse(await fs.readFile(path.join(dataDir, "definitions/gb-30185-2025.json"), "utf8"));
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

title(summary, "A1:G1", "GB 30185-2025标准规则专项复核表", "新标准为draft草案；7个产品/工序条目逐项核对，实施日期为2026-03-01，确认前不参与正式评价。评价日期为软件运行当天；标准选择需由用户确认。" );
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
summary.getRange("A" + noteRow).values = [["本标准表1列出铝塑复合板、幕墙板、不燃铝复合板和装饰用铝单板的单位产品综合能耗限额，单位kgce/10^4m2，实际值不大于限额即达到相应等级。现有企业执行3级限定值，新建、改建和扩建企业执行2级准入值。明细模式按第6章先把能源实物量乘折标系数汇总为E，再按合格产品产量P计算eb=E/P；生产、辅助、附属系统计入，生活用能不计入。" ]];
summary.getRange("A" + noteRow + ":G" + (noteRow + 4)).format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
summary.freezePanes.freezeRows(3); summary.showGridLines = false;
widths(summary, { A: 20, B: 44, C: 24, D: 18, E: 34, F: 14, G: 14 }, 80);

title(rules, "A1:T1", "GB 30185-2025规则逐项确认", "请逐行核对产品/工序、指标名称、单位、三级限额、统计范围和原文页码；确认结论必须填写。" );
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
widths(rules, { A: 8, B: 20, C: 40, D: 44, E: 50, F: 24, G: 18, H: 16, I: 16, J: 16, K: 72, L: 48, M: 10, N: 24, O: 24, P: 12, Q: 14, R: 14, S: 14, T: 34 }, 80);

title(formulas, "A1:H1", "公式、统计范围与适用条件核对", "本表把标准原文计算方法对应到软件规则；软件与Excel不各自判级，Excel只复现软件计算轨迹。" );
formulas.getRange("A3:H3").values = [["编号", "原文项目", "标准公式/定义", "软件规则实现", "单位/录入要求", "PDF页码", "条款/表号", "复核结论"]]; header(formulas.getRange("A3:H3"));
const formulaRows = [
  ["（1）", "产品综合能耗 E", "E=Σ(E_i×k_i)", "每条能源明细先按折标系数计算kgce，再按生产系统、辅助生产系统、附属生产系统分类汇总；生活用能排除。", "E为kgce；每条能源须有实测或GB/T2589折标系数及来源", 7, "6.2.1；公式（1）", "待确认"],
  ["（2）", "单位产品综合能耗 eb", "eb=E/P", "detail_formula按三类系统能耗之和除以production.total_equivalent；结果kgce/10^4m2。", "P为合格产品产量，单位10^4m2；不得为0", 8, "6.2.2；公式（2）", "待确认"],
  ["（3）", "生产系统", "原料投入至合格产品产出的生产过程用能", "分类键energy.category.production_system.net_standard_coal", "折标准煤kgce", 7, "6.1.2.1", "待确认"],
  ["（4）", "辅助生产系统", "服务生产正常完成的设备、设施用能", "分类键energy.category.auxiliary_system.net_standard_coal", "折标准煤kgce", 7, "6.1.2.2", "待确认"],
  ["（5）", "附属生产系统", "为生产服务的维修、检验、仓储、运输、照明等用能", "分类键energy.category.affiliated_system.net_standard_coal", "折标准煤kgce；生活用能不计入", 7, "6.1.2.3", "待确认"],
  ["（6）", "多产品公用能耗分摊", "无法分开计量时按合理原则分摊", "分摊后的能源明细分别归入对应产品；同一统计期原则保持不变。", "记录分摊依据和比例", 7, "6.1.5", "待确认"],
];
formulas.getRange("A4:H9").values = formulaRows; body(formulas.getRange("A4:H9"));
formulas.getRange("A11:H11").values = [["条件/边界", "原文要求", "软件处理", "可能影响", "PDF页码", "条款/表号", "当前状态", "复核结论"]]; header(formulas.getRange("A11:H11"));
const conditionRows = [
  ["现有企业", "执行表1中3级限定值", "等级仍按1/2/3阈值分别输出；在评价信息中记录企业类型供提示。", "影响达标提示，不改变三级限额", 6, "5.1", "draft", "待确认"],
  ["新建、改建和扩建企业", "执行表1中2级准入值", "选择企业类型后显示2级准入提示；超2级但不超过3级可判为3级，但提示不满足准入要求。", "影响准入提示", 6, "5.2", "draft", "待确认"],
  ["统计范围", "生产、辅助、附属系统计入；生活用能不计入", "输入分类限定为三类生产用能；生活用能不允许作为能耗明细计入。", "错误分类会高估或低估实际值", 7, "6.1.1～6.1.4", "draft", "待确认"],
  ["能源折标", "优先使用实测热值；否则按GB/T2589等规定折算", "每条能源明细记录折标系数、来源和计算轨迹。", "影响E及最终eb", 7, "6.2.1", "draft", "待确认"],
  ["复合线脚注a", "用于铝蜂窝板、铝波纹芯复合铝板时，其产量和能耗均统计", "作为产品适用说明显示；用户需确认是否属于该情形。", "影响统计边界", 6, "表1脚注a", "draft", "待确认"],
];
formulas.getRange("A12:H16").values = conditionRows; body(formulas.getRange("A12:H16"));
formulas.getRange("H4:H9").dataValidation = { rule: { type: "list", values: ["待确认", "一致", "需修改"] } };
formulas.getRange("H12:H16").dataValidation = { rule: { type: "list", values: ["待确认", "一致", "需修改"] } };
["H4:H9", "H12:H16"].forEach(function(cellRange) {
  formulas.getRange(cellRange).conditionalFormats.add("cellIs", { operator: "equal", formula: '"一致"', format: { fill: green, font: { color: "#006100", bold: true } } });
  formulas.getRange(cellRange).conditionalFormats.add("cellIs", { operator: "equal", formula: '"需修改"', format: { fill: orange, font: { color: "#9C0006", bold: true } } });
});
formulas.getRange("A18:H21").merge();
formulas.getRange("A18").values = [["重点核对：本标准把铝塑复合板的不同生产工艺、幕墙板、不燃铝复合板和装饰用铝单板分别列为产品/工序；指标名称统一为“单位产品综合能耗”。7条限额全部来自表1，单位为kgce/10^4m2。若用户选择旧版GB 30185-2013或其他尚未实施标准，软件应显示提示并要求确认；当前标准已于2026-03-01实施，但本规则尚未发布。"]];
formulas.getRange("A18:H21").format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
formulas.freezePanes.freezeRows(3); formulas.freezePanes.freezeColumns(2); formulas.showGridLines = false;
widths(formulas, { A: 24, B: 34, C: 42, D: 62, E: 40, F: 12, G: 28, H: 16 }, 40);

title(corrections, "A1:H1", "GB 30185-2025来源、替代与订正记录", "本表显式记录标准替代关系和需要用户确认的实现口径，不修改标准原文。" );
corrections.getRange("A3:H3").values = [["订正ID", "标准编号", "字段/事项", "原值/候选表述", "确认值/软件处理", "原因", "依据", "处理状态"]]; header(corrections.getRange("A3:H3"));
const correctionRows = [
  ["GB30185-replace", definition.number, "标准替代", "GB 30185-2013；旧版限额", "GB 30185-2025；旧版仅历史选择，不作为默认标准", "按现行强制文本封面替代关系记录", "原文封面；前言", "待确认"],
  ["GB30185-date", definition.number, "发布日期/实施日期", "旧版日期", "2025-02-28发布；2026-03-01实施", "按新标准封面记录", "PDF第1页", "待确认"],
  ["GB30185-scope", definition.number, "适用范围", "铝塑复合板旧版范围", "铝塑复合板、不燃铝复合板和装饰用铝单板；具体工艺按表1分列", "按第1章和术语范围核对", "PDF第5页；第1章、3.1～3.3", "待确认"],
  ["GB30185-levels", definition.number, "等级与企业类型", "表中1级/2级/3级", "软件分别输出三级；现有企业3级，新建改扩建2级准入提示", "区分判级和准入要求", "PDF第6页；第5章", "待确认"],
  ["GB30185-formula", definition.number, "公式实现", "E=Σ(E_i×k_i)，eb=E/P", "能源明细折标后分类汇总，再按合格产品产量除算；保留计算轨迹", "避免把标准公式拆成第二套判级逻辑", "PDF第7～8页；第6.2节", "待确认"],
  ["GB30185-footnote", definition.number, "表1脚注a", "复合线产品范围不明确", "铝蜂窝板、铝波纹芯复合铝板复合线的产量和能耗一并统计", "避免遗漏统计边界", "PDF第6页；表1脚注a", "待确认"],
];
corrections.getRange("A4:H" + (3 + correctionRows.length)).values = correctionRows; body(corrections.getRange("A4:H" + (3 + correctionRows.length)));
corrections.getRange("H4:H" + (3 + correctionRows.length)).dataValidation = { rule: { type: "list", values: ["待确认", "一致", "需修改"] } };
corrections.getRange("H4:H" + (3 + correctionRows.length)).conditionalFormats.add("cellIs", { operator: "equal", formula: '"一致"', format: { fill: green, font: { color: "#006100", bold: true } } });
corrections.getRange("H4:H" + (3 + correctionRows.length)).conditionalFormats.add("cellIs", { operator: "equal", formula: '"需修改"', format: { fill: orange, font: { color: "#9C0006" } } });
corrections.freezePanes.freezeRows(3); corrections.showGridLines = false;
widths(corrections, { A: 24, B: 20, C: 24, D: 44, E: 52, F: 48, G: 34, H: 14 }, 30);

const tableCheck = await wb.inspect({ kind: "table", range: "确认汇总!A1:G" + (noteRow + 4), include: "values,formulas", tableMaxRows: 80, tableMaxCols: 10, tableMaxCellChars: 240 });
process.stdout.write(tableCheck.ndjson + "\n");
const errorCheck = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "GB 30185-2025 review workbook formula errors" });
process.stdout.write(errorCheck.ndjson + "\n");
const renders = [
  ["确认汇总", "gb30185-2025-summary.png", "A1:G" + (noteRow + 4)],
  ["规则确认", "gb30185-2025-rules.png", "A1:T12"],
  ["公式核对", "gb30185-2025-formulas.png", "A1:H21"],
  ["订正记录", "gb30185-2025-corrections.png", "A1:H10"],
];
for (const item of renders) {
  const preview = await wb.render({ sheetName: item[0], range: item[2], scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, item[1]), new Uint8Array(await preview.arrayBuffer()));
}
const exported = await SpreadsheetFile.exportXlsx(wb);
const outPath = path.join(outputDir, "GB 30185-2025标准规则专项复核表.xlsx");
await exported.save(outPath);
process.stdout.write("OUTPUT=" + outPath + "\nPREVIEWS=" + previewDir + "\n");
