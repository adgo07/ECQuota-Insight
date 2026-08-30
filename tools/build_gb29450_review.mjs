import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const dataDir = path.resolve(process.env.UEBENCH_WORKBOOK_DATA_DIR || "work/next-scope-63/data");
const outputDir = path.resolve(process.env.UEBENCH_WORKBOOK_OUTPUT_DIR || "work/next-scope-63");
const previewDir = path.resolve("work/artifact-next29450/review-previews");
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
const definition = JSON.parse(await fs.readFile(path.join(dataDir, "definitions/gb-29450-2012.json"), "utf8"));
const products = definition.products || [];
const indicators = products.flatMap((product) => (product.indicators || []).map((indicator) => ({ product, indicator })));
const navy = "#17365D", blue = "#2F75B5", lightBlue = "#D9EAF7", paleBlue = "#F4F7FB", border = "#B4C6E7", white = "#FFFFFF", green = "#E2F0D9", orange = "#FCE4D6";
function title(sheet, range, text, subtitle) {
  sheet.getRange(range).merge();
  const start = range.split(":")[0], row = Number(start.match(/\d+/)[0]), first = start.match(/[A-Z]+/)[0], last = range.split(":")[1].match(/[A-Z]+/)[0];
  sheet.getRange(start).values = [[text]];
  sheet.getRange(range).format = { fill: navy, font: { bold: true, color: white, size: 18 }, horizontalAlignment: "center", verticalAlignment: "center" };
  sheet.getRange(range).format.rowHeight = 34;
  sheet.getRange(first + (row + 1) + ":" + last + (row + 1)).merge();
  sheet.getRange(first + (row + 1)).values = [[subtitle]];
  sheet.getRange(first + (row + 1) + ":" + last + (row + 1)).format = { fill: lightBlue, font: { color: navy, italic: true }, horizontalAlignment: "left", verticalAlignment: "center", wrapText: true };
  sheet.getRange(first + (row + 1) + ":" + last + (row + 1)).format.rowHeight = 46;
}
function header(range) {
  range.format = { fill: blue, font: { bold: true, color: white }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: border } };
  range.format.rowHeight = 30;
}
function body(range) {
  range.format = { fill: white, font: { color: "#1F2937" }, verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: border } };
}
function widths(sheet, values, rows = 240) {
  for (const [column, width] of Object.entries(values)) sheet.getRange(column + "1:" + column + rows).format.columnWidth = width;
}
function threshold(indicator, level) {
  const expression = (indicator.thresholds || {})[level] || (indicator.base_thresholds || {})[level];
  return expression ? (expression.op === "constant" ? expression.value : "按条件选择") : "—";
}
function thresholdText(indicator, level) {
  const value = threshold(indicator, level);
  return value === "—" ? value : "≤" + value;
}
function sourceSummary(indicator) {
  return (indicator.source_references || []).map((item) => "PDF第" + item.page + "页；" + (item.clause || "") + (item.table ? "；" + item.table : "")).join("\n");
}
function reviewValidation(range) {
  range.dataValidation = { rule: { type: "list", values: ["待确认", "一致", "需修改"] } };
  range.conditionalFormats.add("cellIs", { operator: "equal", formula: '"一致"', format: { fill: green, font: { color: "#006100", bold: true } } });
  range.conditionalFormats.add("cellIs", { operator: "equal", formula: '"需修改"', format: { fill: orange, font: { color: "#9C0006", bold: true } } });
}
const wb = Workbook.create();
const summary = wb.worksheets.add("确认汇总"), rules = wb.worksheets.add("规则确认"), formulas = wb.worksheets.add("公式核对"), corrections = wb.worksheets.add("订正记录");
wb.comments.setSelf({ displayName: "User" });

title(summary, "A1:G1", "GB 29450-2012标准规则专项复核表", "本标准规则为draft草案；确认前不参与正式评价。请核对6个产品/工序、指标名称、三级限额、池窑纱公式（3）～（5）、坩埚法公式（1）～（8）及表4线密度折算系数。表2未列的4个产品保留2级缺级，不补值。软件评价日期读取运行当天；旧版或尚未实施标准由用户手动选择并显示提示。");
summary.getRange("A4:B12").values = [
  ["标准编号", definition.number], ["标准名称", definition.title],
  ["发布日期/实施日期", String(definition.publication_date) + " / " + String(definition.effective_date)],
  ["标准状态", "draft（待确认）"], ["生命周期", "active（2013-10-01已实施，规则尚未发布）"],
  ["原文文件", definition.source_file], ["原文SHA-256", definition.source_sha256],
  ["产品/工序数", products.length], ["指标数", null],
];
summary.getRange("A4:A12").format = { fill: lightBlue, font: { bold: true, color: navy }, verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: border } };
body(summary.getRange("B4:B12"));
summary.getRange("B12").formulas = [["=COUNTA('规则确认'!$E$4:$E$" + (3 + indicators.length) + ")"]];
summary.getRange("A14:G14").values = [["标准编号", "产品/工序", "指标名称", "单位", "1级/2级/3级基础限额", "复核状态", "确认结论"]]; header(summary.getRange("A14:G14"));
const summaryRows = indicators.map(({ product, indicator }) => [definition.number, product.name, indicator.name, indicator.unit, thresholdText(indicator, "level_1") + " / " + thresholdText(indicator, "level_2") + " / " + thresholdText(indicator, "level_3"), definition.publication_status, "待确认"]);
summary.getRange("A15:G" + (14 + summaryRows.length)).values = summaryRows; body(summary.getRange("A15:G" + (14 + summaryRows.length)));
summary.getRange("A22:G28").merge();
summary.getRange("A22").values = [["范围与判定口径：本标准适用于中碱或无碱玻璃球、池窑法或坩埚法生产E、ECR和中碱玻璃纤维，不适用于高强、高硅氧、耐碱等特种玻璃纤维。产品/工序名称已包含工艺方法和工序，指标名称统一为“单位产品综合能耗”。表2只给出E和E(ECR)纱准入值，其他4行的2级限额以“—”保留。池窑细纱/粗纱按公式（3）～（5）选择主体产量；坩埚拉丝的每条产量折算系数按表4录入。"]];
summary.getRange("A22:G28").format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
summary.freezePanes.freezeRows(3); summary.showGridLines = false; widths(summary, { A: 20, B: 38, C: 24, D: 18, E: 32, F: 14, G: 14 }, 90);

title(rules, "A1:T1", "GB 29450-2012规则逐项确认", "请逐行核对产品/工序、指标名称、单位、三级限额、工艺条件、池窑折算公式、坩埚法统计边界、表4系数和原文页码；确认结论必须填写。表2没有对应准入值的产品必须保持缺级。");
const ruleHeaders = ["序号", "标准编号", "标准名称", "产品/工序", "指标ID", "指标名称", "单位", "1级基础限额", "2级基础限额", "3级基础限额", "修正与适用说明", "来源定位", "PDF页码", "条款", "表号", "复核状态", "确认结论", "确认人", "确认日期", "确认备注"];
rules.getRange("A3:T3").values = [ruleHeaders]; header(rules.getRange("A3:T3"));
const ruleRows = indicators.map(({ product, indicator }, index) => {
  const first = indicator.source_references[0];
  return [index + 1, definition.number, definition.title, product.name, indicator.id, indicator.name, indicator.unit, threshold(indicator, "level_1"), threshold(indicator, "level_2"), threshold(indicator, "level_3"), (indicator.notes || []).join("\n"), sourceSummary(indicator), first.page, first.clause || "", first.table || "", definition.publication_status, "待确认", "", null, ""];
});
rules.getRange("A4:T" + (3 + ruleRows.length)).values = ruleRows; body(rules.getRange("A4:T" + (3 + ruleRows.length))); rules.getRange("M4:M" + (3 + ruleRows.length)).format.numberFormat = "0"; rules.getRange("S4:S" + (3 + ruleRows.length)).format.numberFormat = "yyyy-mm-dd"; reviewValidation(rules.getRange("Q4:Q" + (3 + ruleRows.length))); rules.freezePanes.freezeRows(3); rules.freezePanes.freezeColumns(2); rules.showGridLines = false; widths(rules, { A: 8, B: 20, C: 38, D: 38, E: 54, F: 24, G: 18, H: 16, I: 16, J: 16, K: 78, L: 52, M: 10, N: 30, O: 24, P: 12, Q: 14, R: 14, S: 14, T: 34 }, 90);

title(formulas, "A1:H1", "公式、统计范围与适用条件核对", "公式文字按GB 29450-2012原文整理；Excel只复现软件规则说明，不建立第二套判级逻辑。请重点核对池窑混合型窑主体选择、坩埚法制球分摊、表4线密度系数和表2缺级处理。");
formulas.getRange("A3:H3").values = [["编号", "原文项目", "标准公式/定义", "软件规则实现", "单位/录入要求", "PDF页码", "条款/表号", "复核结论"]]; header(formulas.getRange("A3:H3"));
const formulaRows = [
  ["公式（1）", "玻璃球综合能耗 Qm", "Qm=Σ(ei×ki)−Σ(ej×kj)", "能源明细按输入/输出方向折标汇总；制球产品共同能耗按企业实际分摊比例记录。", "kgce；输出能源用direction=output；分摊比例0～1", 5, "5.2.1.1；公式（1）", "待确认"],
  ["公式（2）", "玻璃球单位产品综合能耗 Em", "Em=Qm×1000/Gm", "软件使用energy.total_standard_coal（kgce）除以合格玻璃球折算产量（t），与×1000 tce换算等价。", "kgce/t；Gm必须大于0", 6, "5.2.1.2；公式（2）", "待确认"],
  ["公式（3）", "池窑单纯细纱折算产量", "Gyz9=Gy9+1.5Gy5", "选择“单纯细纱”时使用；细纱直径大于5μm和小于等于5μm分别录入。", "t；Gy9、Gy5均为合格产量", 6, "5.2.2.1；公式（3）", "待确认"],
  ["公式（4）", "混合型窑粗纱主体折算产量", "Gyz粗=Gy粗+1.4G细", "选择“混合型窑（粗纱为主体）”时使用；软件保留主体选择和1.4折算轨迹。", "t；粗纱产品直径＞9μm", 6, "5.2.2.1；公式（4）", "待确认"],
  ["公式（5）", "混合型窑细纱主体折算产量", "Gyz细=G细+G粗/1.4", "选择“混合型窑（细纱为主体）”时使用；G细=Gy9+Gy5。", "t；除数1.4不得改写为近似值", 6, "5.2.2.1；公式（5）", "待确认"],
  ["公式（6）", "坩埚法玻璃纤维纱折算产量", "Gyz=Σ(Gyi×λi)", "生产明细的conversion_factor记录表4线密度折算系数λ；每条合格产量在计算轨迹中保留。", "t；λ按表4的tex区间取值", 7, "5.2.2.1；公式（6）；表4", "待确认"],
  ["公式（7）", "玻璃纤维纱综合能耗 Qy", "Qy=Σ(ei×ki)−Σ(ej×kj)", "池窑或坩埚拉丝按所选产品/工序统计生产系统和辅助生产系统能源，外供能源单独抵扣。", "kgce；不同工艺不得混合统计", 7, "5.2.2.2；公式（7）", "待确认"],
  ["公式（8）", "玻璃纤维纱单位产品综合能耗 Ey", "Ey=Qy×1000/Gy", "软件使用能源折标合计除以合格折算产量，结果单位kgce/t。", "kgce/t；Gy必须大于0", 7, "5.2.2.3；公式（8）", "待确认"],
  ["表2缺级", "四类产品准入值", "表2仅列E纱（≤9μm）750、E(ECR)纱（＞9μm）550", "中碱纱、无碱玻璃球、中碱玻璃球、坩埚拉丝纱的level_2保存为None并在结果中显示“—”。", "禁止用表1或表3数值补齐2级", 4, "4.2；表2", "待确认"],
  ["表4", "坩埚拉丝线密度折算系数", "≤2.75:9.5；>2.75~5.5:5；>5.5~11:2.5；>11~22.5:1；>22.5~33:0.9；>33~50:0.7；>50~90:0.6；>90:0.5", "产量明细由用户按适用tex区间填写conversion_factor并留存来源，软件记录逐条折算轨迹。", "tex和λ必须逐条对应；不确定时返回不完整", 7, "5.2.2.1；表4", "待确认"],
  ["附录A/B", "能源和耗能工质折标", "按GB/T 2589实测或附录参考系数折标", "每条EnergyLine保存实物量、折标系数、方向、分摊比例和来源；不把参考系数当作强制固定值。", "系数分母必须与实物量单位一致", 9, "5.1.1；附录A、B", "待确认"],
];
formulas.getRange("A4:H" + (3 + formulaRows.length)).values = formulaRows; body(formulas.getRange("A4:H" + (3 + formulaRows.length))); reviewValidation(formulas.getRange("H4:H" + (3 + formulaRows.length)));
formulas.getRange("A17:H17").values = [["适用条件/边界", "原文要求", "软件处理", "错误风险", "PDF页码", "条款/表号", "当前状态", "复核结论"]]; header(formulas.getRange("A17:H17"));
const conditionRows = [
  ["标准适用范围", "中碱或无碱玻璃球；池窑法或坩埚法生产E、ECR和中碱玻璃纤维；排除特种玻璃纤维", "产品/工序列表只保留表1～表3列出的六类产品；特种玻璃纤维不进入评价。", "把特种玻璃纤维套用本标准", 3, "第1章", "draft", "待确认"],
  ["池窑纱主体选择", "混合型窑按主体产量选择公式（4）或（5）", "细纱、粗纱产品分别提供生产方式选择；缺少选择或缺少混合产量返回不完整。", "主体选择错误会改变折算产量", 6, "5.2.2.1；公式（3）～（5）", "draft", "待确认"],
  ["坩埚制球工序", "从原料计量进厂到玻璃球包装入库；既生产两类玻璃球时按产量分摊", "共同能源通过EnergyLine allocation_ratio分摊；无碱、中碱玻璃球分别独立判级。", "共同能耗重复计入或漏计", 5, "5.1.2.2；5.2.1", "draft", "待确认"],
  ["坩埚拉丝工序", "从玻璃球计量进厂到玻璃纤维纱计量入库；产量按表4折算", "选择“坩埚法—拉丝—玻璃纤维纱”，每条生产明细填写表4λ。", "按实物吨数直接相加会错用限额", 5, "5.1.2.2；5.2.2.1", "draft", "待确认"],
  ["表2缺级", "中碱纱和三类坩埚产品未给准入值", "结果保留2级为“—”；实际值≤1级仍为1级，超过1级后按3级比较，不能虚构2级。", "误把限定值当准入值", 4, "4.2；表2", "draft", "待确认"],
  ["生产/辅助系统边界", "生产系统与辅助生产系统能源计入；输出能源扣除；不同工艺辅助能源合理分摊", "按EnergyLine的category_key、direction和allocation_ratio记录计算轨迹。", "把生活用能或其他工序混入", 5, "5.1；5.2.1；5.2.2", "draft", "待确认"],
];
formulas.getRange("A18:H23").values = conditionRows; body(formulas.getRange("A18:H23")); reviewValidation(formulas.getRange("H18:H23"));
formulas.getRange("A26:H30").merge(); formulas.getRange("A26").values = [["关键确认：本轮按原文表1～表3建立6条产品/工序规则，产品/工序名称包含工艺方法和工序，指标名称统一为“单位产品综合能耗”。表2缺失的4个准入值以“—”保留；池窑纱公式（3）～（5）通过生产方式选择明确分支；坩埚拉丝按表4折算系数逐条记录。任何原文与草案不一致，都应在订正记录中填写原因后再修改。"]]; formulas.getRange("A26:H30").format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } }; formulas.freezePanes.freezeRows(3); formulas.freezePanes.freezeColumns(2); formulas.showGridLines = false; widths(formulas, { A: 18, B: 32, C: 58, D: 70, E: 44, F: 12, G: 32, H: 16 }, 60);

title(corrections, "A1:H1", "GB 29450-2012来源、产品拆分与订正记录", "本表记录产品/工序、指标名称、缺级、公式、分摊和表4系数口径；不修改标准原文。确认结论填写“一致”或“需修改”后，再进入规则发布流程。");
corrections.getRange("A3:H3").values = [["订正ID", "标准编号", "字段/事项", "原值/候选表述", "确认值/软件处理", "原因", "依据", "处理状态"]]; header(corrections.getRange("A3:H3"));
const correctionRows = [
  ["GB29450-products", definition.number, "产品/工序与指标名称", "产品名称中混有“单位产品综合能耗”后缀，且只保留两类池窑纱", "按表1～表3拆为6个产品/工序；指标名称统一为“单位产品综合能耗”", "遵循产品/工序+指标名称命名规则并补全原文表格行", "PDF第4页；表1～表3", "待确认"],
  ["GB29450-levels", definition.number, "三级限额", "仅录入有完整三级值的两类产品", "6行分别录入1级先进值、2级准入值、3级限定值；4行的2级保留“—”", "表2仅列E和E(ECR)纱准入值，缺级不得补值", "PDF第4页；4.1～4.3；表1～表3", "待确认"],
  ["GB29450-scope", definition.number, "适用范围", "玻璃纤维泛化处理", "只纳入中碱/无碱玻璃球、池窑E/ECR/中碱纱和坩埚法制球/拉丝产品；排除特种玻璃纤维", "按第1章范围逐项限定", "PDF第3页；第1章", "待确认"],
  ["GB29450-pool-formula", definition.number, "池窑纱产量折算", "细纱直接使用实物产量", "单纯细纱使用公式（3）；混合型窑按粗纱主体公式（4）或细纱主体公式（5）选择", "按5.2.2.1保留主体分支，缺条件不猜测", "PDF第6页；5.2.2.1；公式（3）～（5）", "待确认"],
  ["GB29450-ball-boundary", definition.number, "玻璃球能耗和分摊", "玻璃球能源统一合计", "制球工序执行公式（1）（2）；同时生产无碱/中碱玻璃球时按产量分摊共同能源", "按5.1.2.2和5.2.1核对统计边界", "PDF第5～6页；5.1.2.2；5.2.1", "待确认"],
  ["GB29450-crucible-yarn", definition.number, "坩埚拉丝产量", "按吨数直接累计", "执行公式（6），每条产量使用表4线密度折算系数λ；不确定时返回不完整", "表4是规范性口径，避免量级错误", "PDF第7页；5.2.2.1；表4", "待确认"],
  ["GB29450-boundary", definition.number, "能源边界和折标", "把所有能源明细直接相加", "按输入能源−输出能源折标，区分生产/辅助系统并记录分摊比例；系数优先实测或供应单位数据", "按5.1、5.2及附录A/B实现可审计轨迹", "PDF第5、7、9～10页", "待确认"],
];
corrections.getRange("A4:H10").values = correctionRows; body(corrections.getRange("A4:H10")); reviewValidation(corrections.getRange("H4:H10")); corrections.freezePanes.freezeRows(3); corrections.showGridLines = false; widths(corrections, { A: 26, B: 20, C: 24, D: 50, E: 68, F: 48, G: 38, H: 14 }, 50);

const tableCheck = await wb.inspect({ kind: "table", range: "确认汇总!A1:G28", include: "values,formulas", tableMaxRows: 90, tableMaxCols: 10, tableMaxCellChars: 300 });
process.stdout.write(tableCheck.ndjson + "\n");
const errorCheck = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "GB 29450-2012 review workbook formula errors" });
process.stdout.write(errorCheck.ndjson + "\n");
for (const [sheetName, fileName, range] of [["确认汇总", "gb29450-2012-summary.png", "A1:G29"], ["规则确认", "gb29450-2012-rules.png", "A1:T11"], ["公式核对", "gb29450-2012-formulas.png", "A1:H32"], ["订正记录", "gb29450-2012-corrections.png", "A1:H12"]]) {
  const preview = await wb.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
const exported = await SpreadsheetFile.exportXlsx(wb);
const outPath = path.join(outputDir, "GB 29450-2012标准规则专项复核表.xlsx");
await exported.save(outPath);
process.stdout.write("OUTPUT=" + outPath + "\nPREVIEWS=" + previewDir + "\n");
