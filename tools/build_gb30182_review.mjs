import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const dataDir = path.resolve(process.env.UEBENCH_WORKBOOK_DATA_DIR || "work/next-scope-63/data");
const outputDir = path.resolve(process.env.UEBENCH_WORKBOOK_OUTPUT_DIR || "work/next-scope-63");
const previewDir = path.resolve("work/artifact-next30182/review-previews");
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const definition = JSON.parse(await fs.readFile(path.join(dataDir, "definitions/gb-30182-2013.json"), "utf8"));
const products = definition.products || [];
const indicators = products.flatMap(function (product) {
  return (product.indicators || []).map(function (indicator) {
    return { product: product, indicator: indicator };
  });
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
  const row = Number(start.match(/\d+/)[0]);
  const first = start.match(/[A-Z]+/)[0];
  const last = range.split(":")[1].match(/[A-Z]+/)[0];
  sheet.getRange(start).values = [[text]];
  sheet.getRange(range).format = { fill: navy, font: { bold: true, color: white, size: 18 }, horizontalAlignment: "center", verticalAlignment: "center" };
  sheet.getRange(range).format.rowHeight = 34;
  const subtitleRange = first + (row + 1) + ":" + last + (row + 1);
  sheet.getRange(subtitleRange).merge();
  sheet.getRange(first + (row + 1)).values = [[subtitle]];
  sheet.getRange(subtitleRange).format = { fill: lightBlue, font: { color: navy, italic: true }, horizontalAlignment: "left", verticalAlignment: "center", wrapText: true };
  sheet.getRange(subtitleRange).format.rowHeight = 48;
}

function header(range) {
  range.format = { fill: blue, font: { bold: true, color: white }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: border } };
  range.format.rowHeight = 30;
}

function body(range) {
  range.format = { fill: white, font: { color: "#1F2937" }, verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: border } };
}

function widths(sheet, values, rows) {
  const rowCount = rows || 240;
  for (const entry of Object.entries(values)) {
    sheet.getRange(entry[0] + "1:" + entry[0] + rowCount).format.columnWidth = entry[1];
  }
}

function threshold(indicator, level) {
  const expression = (indicator.thresholds || {})[level] || (indicator.base_thresholds || {})[level];
  if (!expression) return "—";
  return expression.op === "constant" ? expression.value : "按条件选择";
}

function sourceSummary(indicator) {
  return (indicator.source_references || []).map(function (item) {
    return "PDF第" + item.page + "页；" + (item.clause || "") + (item.table ? "；" + item.table : "");
  }).join("\n");
}

function reviewValidation(range) {
  range.dataValidation = { rule: { type: "list", values: ["待确认", "一致", "需修改"] } };
  range.conditionalFormats.add("cellIs", { operator: "equal", formula: '"一致"', format: { fill: green, font: { color: "#006100", bold: true } } });
  range.conditionalFormats.add("cellIs", { operator: "equal", formula: '"需修改"', format: { fill: orange, font: { color: "#9C0006", bold: true } } });
}

const wb = Workbook.create();
const summary = wb.worksheets.add("确认汇总");
const rules = wb.worksheets.add("规则确认");
const formulas = wb.worksheets.add("公式核对");
const corrections = wb.worksheets.add("订正记录");
wb.comments.setSelf({ displayName: "User" });

title(summary, "A1:G1", "GB 30182-2013标准规则专项复核表", "本标准规则为draft草案；本标准只有1个产品/工序、2项指标，请分别核对“单位产品综合能耗”和“电耗”。确认前不参与正式评价。软件评价日期读取运行当天；旧版或尚未实施标准由用户手动选择并显示提示。");
summary.getRange("A4:B12").values = [
  ["标准编号", definition.number],
  ["标准名称", definition.title],
  ["发布/实施日期", String(definition.publication_date) + " / " + String(definition.effective_date)],
  ["标准状态", "draft（待确认）"],
  ["生命周期", "active（2014-12-01已实施，规则尚未发布）"],
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
const summaryRows = indicators.map(function (pair) {
  return [definition.number, pair.product.name, pair.indicator.name, pair.indicator.unit, "≤" + threshold(pair.indicator, "level_1") + " / ≤" + threshold(pair.indicator, "level_2") + " / ≤" + threshold(pair.indicator, "level_3"), definition.publication_status, "待确认"];
});
summary.getRange("A15:G" + (14 + summaryRows.length)).values = summaryRows;
body(summary.getRange("A15:G" + (14 + summaryRows.length)));
summary.getRange("A19:G25").merge();
summary.getRange("A19").values = [["适用范围与判定口径：本标准仅适用于不带钢背（或蹄铁）的模压型摩擦材料。明细模式按式（1）将煤、油、气和电力折算为产品综合能耗EZN，再按式（2）除以合格产品产量P得到单位产品综合能耗；电耗按式（3）以产品综合电耗QZD除以P。生活设施、运输保管、采暖、技术改造动力设备，以及以检测为目的且功率超过15 kW的设备不计入。原文前言说明4.1、4.2为强制性条款，4.3先进值为推荐性条款；软件仍将先进值作为1级对标线并明确提示。"]];
summary.getRange("A19:G25").format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
summary.freezePanes.freezeRows(3);
summary.showGridLines = false;
widths(summary, { A: 20, B: 38, C: 24, D: 18, E: 34, F: 14, G: 14 }, 90);

title(rules, "A1:T1", "GB 30182-2013规则逐项确认", "请逐行核对产品/工序、指标名称、单位、三级限额、明细公式、能源统计范围、排除项和原文页码；确认结论必须填写。同一产品/工序的两个指标必须分别确认。");
const ruleHeaders = ["序号", "标准编号", "标准名称", "产品/工序", "指标ID", "指标名称", "单位", "1级基础限额", "2级基础限额", "3级基础限额", "修正与适用说明", "来源定位", "PDF页码", "条款", "表号", "复核状态", "确认结论", "确认人", "确认日期", "确认备注"];
rules.getRange("A3:T3").values = [ruleHeaders];
header(rules.getRange("A3:T3"));
const ruleRows = indicators.map(function (pair, index) {
  const indicator = pair.indicator;
  const first = (indicator.source_references || [])[0] || {};
  return [index + 1, definition.number, definition.title, pair.product.name, indicator.id, indicator.name, indicator.unit, threshold(indicator, "level_1"), threshold(indicator, "level_2"), threshold(indicator, "level_3"), (indicator.notes || []).join("\n"), sourceSummary(indicator), first.page || "", first.clause || "", first.table || "", definition.publication_status, "待确认", "", null, ""];
});
rules.getRange("A4:T" + (3 + ruleRows.length)).values = ruleRows;
body(rules.getRange("A4:T" + (3 + ruleRows.length)));
rules.getRange("M4:M" + (3 + ruleRows.length)).format.numberFormat = "0";
rules.getRange("S4:S" + (3 + ruleRows.length)).format.numberFormat = "yyyy-mm-dd";
reviewValidation(rules.getRange("Q4:Q" + (3 + ruleRows.length)));
rules.freezePanes.freezeRows(3);
rules.freezePanes.freezeColumns(2);
rules.showGridLines = false;
widths(rules, { A: 8, B: 20, C: 38, D: 40, E: 56, F: 24, G: 18, H: 16, I: 16, J: 16, K: 82, L: 50, M: 10, N: 32, O: 30, P: 12, Q: 14, R: 14, S: 14, T: 34 }, 90);

title(formulas, "A1:H1", "公式、能源分类与等级映射核对", "公式文字按GB 30182-2013原文整理；Excel只复现软件规则和计算轨迹，不在Excel中建立第二套判级逻辑。请重点核对折标系数单位、直接电力分类、合格产量和排除项。");
formulas.getRange("A3:H3").values = [["编号", "原文项目", "标准公式/定义", "软件规则实现", "单位/录入要求", "PDF页码", "条款/表号", "复核结论"]];
header(formulas.getRange("A3:H3"));
const formulaRows = [
  ["（1）", "摩擦材料产品综合能耗 EZN", "EZN = Ma×QaDW/29308 + Mb×1.4286×QbDW/41868 + Mc×1.2143×QcDW/35588 + 0.1229×QZD", "energy.total_standard_coal；每条能源明细按实物量×折标系数计算，direction=output的外供能源抵扣；直接电力按direct_electricity分类进入QZD。", "EZN：kgce；煤/油：kg；气：m³；电：kWh；折标系数分母必须与实物量单位一致", 5, "5.3.2；式（1）", "待确认"],
  ["（2）", "单位产品综合能耗 EDN", "EDN = EZN / P", "per_unit(energy.total_standard_coal, production.total_equivalent)", "kgce/t；P为合格产品产量，P必须大于0", 5, "5.3.3；式（2）", "待确认"],
  ["（3）", "单位产品综合电耗 QDD", "QDD = QZD / P", "per_unit(energy.category.direct_electricity.net_amount, production.total_equivalent)", "kWh/t；QZD只统计产品直接消耗电量，不能缺少direct_electricity明细", 5, "5.3.4；式（3）", "待确认"],
  ["输入/分类", "煤、油、气等能源", "按实物量和低位发热量折算标准煤", "每条EnergyLine保留实物量、折标系数、单位、方向、分类、分摊比例和来源；实测低位发热量优先，无实测时才参考附录A。", "输入量和系数分母单位一致；不确定时返回不完整", 5, "5.3.2；附录A", "待确认"],
  ["输入/分类", "直接电力 QZD", "0.1229×QZD（进入EZN）；QZD/P（进入QDD）", "category_key=direct_electricity的电力明细用于电耗分子；同一明细按0.1229 kgce/kWh折标后计入综合能耗。", "电量单位kWh；不能把生活电力或排除设备电力混入", 5, "5.3.2～5.3.4；附录A", "待确认"],
  ["输入/分类", "合格产品产量 P", "统计期合格产品产量", "production.total_equivalent；与能源明细统计期一致；不合格品不计入，P=0或缺失返回不完整。", "t；必须大于0", 5, "5.3.3～5.3.4", "待确认"],
  ["边界", "排除项", "生活设施、运输保管、采暖、技改动力设备、检测功率超过15 kW设备不计入", "排除项不得录入能源明细；若无法确认边界，软件不猜测并返回不完整或提示。", "按标准第5章逐项核对", 4, "5.1；5.2；5.3", "待确认"],
];
formulas.getRange("A4:H" + (3 + formulaRows.length)).values = formulaRows;
body(formulas.getRange("A4:H" + (3 + formulaRows.length)));
reviewValidation(formulas.getRange("H4:H" + (3 + formulaRows.length)));

const gradeHeaderRow = 13;
formulas.getRange("A" + gradeHeaderRow + ":H" + gradeHeaderRow).values = [["等级映射", "标准原文值", "软件等级", "比较方向", "边界处理", "软件提示", "来源页", "复核结论"]];
header(formulas.getRange("A" + gradeHeaderRow + ":H" + gradeHeaderRow));
const gradeRows = [
  ["先进值（表3）", "≤115 kgce/t；≤800 kWh/t", "1级", "越低越好（≤）", "等于边界仍达到该级", "4.3先进值为推荐性条款，作为1级对标线并提示", 4, "待确认"],
  ["准入值（表2）", "≤135 kgce/t；≤1000 kWh/t", "2级", "越低越好（≤）", "超过1级但不超过2级", "4.2为强制性准入值；项目类型提示由评价场景处理", 4, "待确认"],
  ["限定值（表1）", "≤175 kgce/t；≤1300 kWh/t", "3级", "越低越好（≤）", "超过2级但不超过3级", "超过3级返回未达标", 4, "待确认"],
  ["等级输出", "每项指标分别比较", "单项等级", "不合并", "不生成产品总体等级", "单位产品综合能耗和电耗分别输出；任一缺失只影响对应指标", 4, "待确认"],
];
formulas.getRange("A14:H17").values = gradeRows;
body(formulas.getRange("A14:H17"));
reviewValidation(formulas.getRange("H14:H17"));

formulas.getRange("A20:H24").merge();
formulas.getRange("A20").values = [["关键确认：产品/工序名称只保留“不带钢背（或蹄铁）的模压型摩擦材料”，指标名称分别为“单位产品综合能耗”和“电耗”。直接模式只接受已经按式（2）或式（3）核算的单位值；明细模式必须保留能源折标、直接电力分类和合格产品产量。缺少对应数据、单位不一致或产量为零时，该指标返回“不完整”。"]];
formulas.getRange("A20:H24").format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
formulas.freezePanes.freezeRows(3);
formulas.freezePanes.freezeColumns(2);
formulas.showGridLines = false;
widths(formulas, { A: 18, B: 32, C: 60, D: 76, E: 48, F: 12, G: 34, H: 16 }, 60);

title(corrections, "A1:H1", "GB 30182-2013范围、命名与订正记录", "本表记录产品/工序、指标名称、等级映射、计算边界和录入口径；不修改标准原文。确认结论填写“一致”或“需修改”后，再进入规则发布流程。");
corrections.getRange("A3:H3").values = [["订正ID", "标准编号", "字段/事项", "原值/候选表述", "确认值/软件处理", "原因", "依据", "处理状态"]];
header(corrections.getRange("A3:H3"));
const correctionRows = [
  ["GB30182-name-1", definition.number, "指标名称", "摩擦材料单位产品综合能耗", "单位产品综合能耗", "指标列只保留通用指标名，产品名单独放在产品/工序列", "PDF第4～5页；术语3.2", "待确认"],
  ["GB30182-name-2", definition.number, "指标名称", "摩擦材料单位产品电耗", "电耗", "指标列只保留通用指标名，避免与产品名称重复", "PDF第4～5页；术语3.3", "待确认"],
  ["GB30182-scope", definition.number, "产品/工序", "摩擦材料", "不带钢背（或蹄铁）的模压型摩擦材料", "原文第1章限定适用产品范围；带钢背或蹄铁的产品不适用", "PDF第3页；第1章", "待确认"],
  ["GB30182-level", definition.number, "等级映射", "限定值、准入值、先进值", "1级=先进值；2级=准入值；3级=限定值；并提示4.3为推荐性", "统一为软件固定的1/2/3级判定顺序，同时保留强制性说明", "PDF第2、4页；前言、第4章", "待确认"],
  ["GB30182-formula", definition.number, "明细公式", "摩擦材料单位指标使用通用候选公式", "按式（1）EZN、式（2）EDN、式（3）QDD结构化计算；直接电力分类独立保留", "避免把电耗和综合能耗混成一个指标", "PDF第5页；5.3.2～5.3.4", "待确认"],
  ["GB30182-boundary", definition.number, "计算边界", "综合能耗、综合电耗直接汇总", "排除生活/运输保管/采暖/技改动力/检测功率超过15 kW设备；输出能源抵扣", "按第5章统计范围逐项实现", "PDF第4～5页；5.1～5.3", "待确认"],
  ["GB30182-input-unit", definition.number, "输入单位", "把单位产品单位写在总量输入节点", "综合能耗总量输入单位kgce，电耗总量输入单位kWh，产量输入单位t；结果节点才使用kgce/t或kWh/t", "保证计算轨迹单位与实际量一致", "PDF第5页；式（1）～（3）", "待确认"],
];
corrections.getRange("A4:H10").values = correctionRows;
body(corrections.getRange("A4:H10"));
reviewValidation(corrections.getRange("H4:H10"));
corrections.freezePanes.freezeRows(3);
corrections.showGridLines = false;
widths(corrections, { A: 28, B: 20, C: 24, D: 52, E: 70, F: 48, G: 38, H: 14 }, 50);

const tableCheck = await wb.inspect({ kind: "table", range: "确认汇总!A1:G25", include: "values,formulas", tableMaxRows: 80, tableMaxCols: 10, tableMaxCellChars: 320 });
process.stdout.write(tableCheck.ndjson + "\n");
const errorCheck = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "GB 30182-2013 review workbook formula errors" });
process.stdout.write(errorCheck.ndjson + "\n");

const renderTargets = [
  ["确认汇总", "gb30182-2013-summary.png", "A1:G26"],
  ["规则确认", "gb30182-2013-rules.png", "A1:T7"],
  ["公式核对", "gb30182-2013-formulas.png", "A1:H25"],
  ["订正记录", "gb30182-2013-corrections.png", "A1:H12"],
];
for (const target of renderTargets) {
  const preview = await wb.render({ sheetName: target[0], range: target[2], scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, target[1]), new Uint8Array(await preview.arrayBuffer()));
}

const exported = await SpreadsheetFile.exportXlsx(wb);
const outPath = path.join(outputDir, "GB 30182-2013标准规则专项复核表.xlsx");
await exported.save(outPath);
process.stdout.write("OUTPUT=" + outPath + "\nPREVIEWS=" + previewDir + "\n");
