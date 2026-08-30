import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const dataDir = path.resolve(process.env.UEBENCH_WORKBOOK_DATA_DIR || "work/next-scope-63/data");
const outputDir = path.resolve(process.env.UEBENCH_WORKBOOK_OUTPUT_DIR || "work/next-scope-63");
const previewDir = path.resolve("work/artifact-next21345/review-previews");
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const definition = JSON.parse(await fs.readFile(path.join(dataDir, "definitions/gb-21345-2024.json"), "utf8"));
const products = definition.products || [];
const indicators = products.flatMap((product) => (product.indicators || []).map((indicator) => ({ product, indicator })));

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
  sheet.getRange(first + row + ":" + last + row).format.rowHeight = 38;
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
  const expression = (indicator.thresholds || {})[level] || (indicator.base_thresholds || {})[level];
  if (!expression) return "—";
  return expression.op === "constant" ? expression.value : "按条件选择";
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
const summary = wb.worksheets.add("确认汇总");
const rules = wb.worksheets.add("规则确认");
const formulas = wb.worksheets.add("公式核对");
const corrections = wb.worksheets.add("订正记录");
wb.comments.setSelf({ displayName: "User" });

const pair = indicators[0];
const indicator = pair.indicator;
const product = pair.product;

title(summary, "A1:G1", "GB 21345-2024标准规则专项复核表", "本标准规则为draft草案；确认前不参与正式评价。请核对产品/工序、指标名称、三级限额、统计范围、公式（1）～（10）及质量分数录入口径。软件评价日期读取运行当天；旧版或尚未实施标准由用户手动选择并显示提示。");
summary.getRange("A4:B12").values = [
  ["标准编号", definition.number],
  ["标准名称", definition.title],
  ["发布日期/实施日期", String(definition.publication_date) + " / " + String(definition.effective_date)],
  ["标准状态", "draft（待确认）"],
  ["生命周期", "active（2025-05-01已实施，规则尚未发布）"],
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
const summaryRows = indicators.map(({ product: itemProduct, indicator: itemIndicator }) => [
  definition.number, itemProduct.name, itemIndicator.name, itemIndicator.unit,
  "≤" + threshold(itemIndicator, "level_1") + " / ≤" + threshold(itemIndicator, "level_2") + " / ≤" + threshold(itemIndicator, "level_3"),
  definition.publication_status, "待确认",
]);
summary.getRange("A15:G" + (14 + summaryRows.length)).values = summaryRows;
body(summary.getRange("A15:G" + (14 + summaryRows.length)));
const summaryNoteRow = 17;
summary.getRange("A" + summaryNoteRow + ":G" + (summaryNoteRow + 5)).merge();
summary.getRange("A" + summaryNoteRow).values = [["本标准适用于电炉法黄磷生产。现有生产装置执行表1的3级限定值；新建和改扩建装置执行2级准入值。指标名称只保留“单位产品综合能耗”，单位kgce/t。明细模式按EPZD=(EPS+EPFF−EPW)/PP计算，输出能源抵扣，PP按公式（8）由合格黄磷、泥磷制磷酸/其他化学品折合量及外购泥磷回收量计算。NS、NH在本草案中按0～1小数录入，须在公式核对表中确认企业数据口径。"]];
summary.getRange("A" + summaryNoteRow + ":G" + (summaryNoteRow + 5)).format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
summary.freezePanes.freezeRows(3);
summary.showGridLines = false;
widths(summary, { A: 20, B: 30, C: 24, D: 18, E: 36, F: 14, G: 14 }, 80);

title(rules, "A1:T1", "GB 21345-2024规则逐项确认", "本标准目前只有1个产品/工序和1个必判指标。请逐行核对名称、单位、三级限额、统计范围、公式、录入口径和原文页码；确认结论必须填写。");
const ruleHeaders = ["序号", "标准编号", "标准名称", "产品/工序", "指标ID", "指标名称", "单位", "1级基础限额", "2级基础限额", "3级基础限额", "修正与适用说明", "来源定位", "PDF页码", "条款", "表号", "复核状态", "确认结论", "确认人", "确认日期", "确认备注"];
rules.getRange("A3:T3").values = [ruleHeaders];
header(rules.getRange("A3:T3"));
const ruleRows = indicators.map(({ product: itemProduct, indicator: itemIndicator }, index) => {
  const first = itemIndicator.source_references[0];
  return [index + 1, definition.number, definition.title, itemProduct.name, itemIndicator.id, itemIndicator.name, itemIndicator.unit,
    threshold(itemIndicator, "level_1"), threshold(itemIndicator, "level_2"), threshold(itemIndicator, "level_3"),
    (itemIndicator.notes || []).join("\n"), sourceSummary(itemIndicator), first.page, first.clause || "", first.table || "",
    definition.publication_status, "待确认", "", null, ""];
});
rules.getRange("A4:T" + (3 + ruleRows.length)).values = ruleRows;
body(rules.getRange("A4:T" + (3 + ruleRows.length)));
rules.getRange("M4:M" + (3 + ruleRows.length)).format.numberFormat = "0";
rules.getRange("S4:S" + (3 + ruleRows.length)).format.numberFormat = "yyyy-mm-dd";
reviewValidation(rules.getRange("Q4:Q" + (3 + ruleRows.length)));
rules.freezePanes.freezeRows(3);
rules.freezePanes.freezeColumns(2);
rules.showGridLines = false;
widths(rules, { A: 8, B: 20, C: 38, D: 24, E: 52, F: 24, G: 18, H: 16, I: 16, J: 16, K: 76, L: 48, M: 10, N: 32, O: 24, P: 12, Q: 14, R: 14, S: 14, T: 34 }, 80);

title(formulas, "A1:H1", "公式、统计范围与录入口径核对", "公式文字按GB 21345-2024原文整理；“软件规则实现”只说明结构化实现，不建立Excel第二套判级逻辑。重点确认NS、NH及炭质还原剂固定碳折算的实际数据口径。");
formulas.getRange("A3:H3").values = [["编号", "原文项目", "标准公式/定义", "软件规则实现", "单位/录入要求", "PDF页码", "条款/表号", "复核结论"]];
header(formulas.getRange("A3:H3"));
const formulaRows = [
  ["（1）", "黄磷单位产品综合能耗 EPZD", "EPZD = (EPS + EPFF − EPW) / PP", "净综合能耗除以黄磷产品产量PP；明细中的output能源按负号记录，因此在公式中抵扣。", "kgce/t；PP必须大于0", 7, "6.2.2.1；公式（1）", "待确认"],
  ["（2）", "黄磷生产系统综合能耗 EPS", "EPS = EPT + EPL + EPE", "炭质还原剂、修正后的电炉电耗和生产系统其他能源三项相加。", "kgce", 7, "6.2.2.2；公式（2）", "待确认"],
  ["（3）", "炭质还原剂综合能耗 EPT", "EPT = Σ(e_it × w_it) × 1.1564", "carbon_reducing分类汇总为kgce；能源明细的折标系数应反映实物量×固定碳质量分数×1.1564，必要时逐类录入。", "kgce；e_it为t，w_it为固定碳质量分数；确认标准原文%与录入小数的转换", 7, "6.2.2.3；公式（3）", "待确认"],
  ["（4）", "黄磷产品电炉电耗 EPL", "EPL = {QL − [170000/(N1−0.5) + (7750/(N1−8)−76)×N2 + (3200/(N1−3.5)+8)×N3 − 7234]×PP}×0.1229", "furnace_electricity分类读取QL；按N1、N2、N3和PP计算电量修正，再乘0.1229折成kgce。", "kgce；QL为kW·h，PP为t，N1/N2/N3为百分数；N1不得使分母为0", 8, "6.2.2.4；公式（4）", "待确认"],
  ["（5）", "生产系统其他能源 EPE", "EPE = Σ(e_jpe × k_j)", "production_other分类的能源折标煤合计作为EPE；不含炭质还原剂和电炉直接加热电耗。", "kgce；按实物量和折标系数逐条保留来源", 8, "6.2.2.5；公式（5）", "待确认"],
  ["（6）", "辅助、附属系统摊入能耗 EPFF", "EPFF = Σ(e_jpff × k_j)", "auxiliary_affiliated分类的能源折标煤合计作为EPFF；包含损失摊入量。", "kgce；辅助和附属系统按比例分摊，生活用能不计入", 8, "6.2.2.6；公式（6）", "待确认"],
  ["（7）", "向界区外输出的综合能源 EPW", "EPW = Σ(e_jpw × k_j)", "external_output分类且明细方向必须为output；引擎以负值保存，公式（1）中按输出量抵扣。", "kgce；仅计向黄磷生产界区外输出的能源", 8, "6.2.2.7；公式（7）", "待确认"],
  ["（8）", "黄磷产品产量 PP", "PP = PPZ + PPS + PPH − PPWN", "按合格黄磷PPZ、公式（9）的PPS、公式（10）的PPH和外购泥磷回收PPWN计算；产量明细的PPZ应与公式口径一致。", "t；PP必须大于0；外购泥磷和其他化学品折合量不得重复扣除", 8, "6.2.2.8；公式（8）", "待确认"],
  ["（9）", "泥磷制磷酸折合黄磷量 PPS", "PPS = 0.3163 × NS × PS − PPW", "NS、PS和磷酸外加/外购折合黄磷量作为输入后计算；当前草案NS按0～1小数录入。", "t；NS为以100%H3PO4计的质量分数；确认百分数与小数的输入界面换算", 9, "6.2.2.9；公式（9）", "待确认"],
  ["（10）", "泥磷制其他化学品折合黄磷量 PPH", "PPH = NH × PH − PPW", "NH、PH和其他化学品外加/外购折合黄磷量作为输入后计算；当前草案NH按0～1小数录入。", "t；NH为以磷计的质量百分数；确认百分数与小数的输入界面换算", 9, "6.2.2.10；公式（10）", "待确认"],
];
formulas.getRange("A4:H" + (3 + formulaRows.length)).values = formulaRows;
body(formulas.getRange("A4:H" + (3 + formulaRows.length)));
reviewValidation(formulas.getRange("H4:H" + (3 + formulaRows.length)));
const inputHeaderRow = 16;
formulas.getRange("A" + inputHeaderRow + ":H" + inputHeaderRow).values = [["关键输入变量", "软件输入键/类别", "单位", "标准含义", "来源页", "确认说明", "当前状态", "复核结论"]];
header(formulas.getRange("A" + inputHeaderRow + ":H" + inputHeaderRow));
const inputRows = [
  ["QL", "energy.category.furnace_electricity.net_amount", "kW·h", "实际用于黄磷电炉加热的电量", 8, "确认是否为报告期界区计量值；不含其他用电", "draft", "待确认"],
  ["N1", "yellow_phosphorus.feedstock.p2o5_pct", "%", "配合炉料P2O5加权平均质量分数", 8, "按百分数输入，如10表示10%；核对加权平均计算", "draft", "待确认"],
  ["N2", "yellow_phosphorus.feedstock.fe2o3_pct", "%", "配合炉料Fe2O3加权平均质量分数", 8, "按百分数输入；核对加权平均计算", "draft", "待确认"],
  ["N3", "yellow_phosphorus.feedstock.co2_pct", "%", "配合炉料CO2加权平均质量分数", 8, "按百分数输入；核对加权平均计算", "draft", "待确认"],
  ["PPZ", "yellow_phosphorus.product.qualified_t", "t", "符合GB/T 7816的黄磷量", 9, "确认合格产品统计口径", "draft", "待确认"],
  ["NS", "yellow_phosphorus.product.phosphoric_acid_mass_fraction", "fraction（草案）", "泥磷制得磷酸质量分数（以100% H3PO4计）", 9, "当前按0～1小数；若原始数据按百分数，软件界面需先换算并留痕", "draft", "待确认"],
  ["PS", "yellow_phosphorus.product.phosphoric_acid_production_t", "t", "泥磷制得磷酸产量", 9, "确认报告期产量", "draft", "待确认"],
  ["PPW（磷酸）", "yellow_phosphorus.product.phosphoric_acid_external_yellow_phosphorus_t", "t", "泥磷制磷酸外加的黄磷量和外购泥磷折算量", 9, "确认是否包含两部分，避免与PPWN重复", "draft", "待确认"],
  ["NH", "yellow_phosphorus.product.other_chemical_phosphorus_fraction", "fraction（草案）", "其他化学品中的磷质量百分数（以磷计）", 9, "当前按0～1小数；确认企业原始数据口径", "draft", "待确认"],
  ["PH", "yellow_phosphorus.product.other_chemical_production_t", "t", "泥磷制得的其他化学品产量", 9, "确认报告期产量", "draft", "待确认"],
  ["PPW（其他化学品）", "yellow_phosphorus.product.other_chemical_external_yellow_phosphorus_t", "t", "制备其他化学品中外加的黄磷量和外购泥磷折算量", 9, "确认是否包含两部分，避免与PPWN重复", "draft", "待确认"],
  ["PPWN", "yellow_phosphorus.product.external_mud_recovered_t", "t", "外购泥磷回收的黄磷量和其他化学品折合量", 9, "确认与两个PPW字段的边界，避免重复扣除", "draft", "待确认"],
  ["EPW", "energy.category.external_output.net_standard_coal", "kgce", "向黄磷生产界区外输出的综合能源量", 8, "明细方向必须为output；输出不得重复计入生产系统", "draft", "待确认"],
];
formulas.getRange("A17:H" + (inputHeaderRow + inputRows.length)).values = inputRows;
body(formulas.getRange("A17:H" + (inputHeaderRow + inputRows.length)));
reviewValidation(formulas.getRange("H17:H" + (inputHeaderRow + inputRows.length)));
const formulaNoteRow = inputHeaderRow + inputRows.length + 2;
formulas.getRange("A" + formulaNoteRow + ":H" + (formulaNoteRow + 4)).merge();
formulas.getRange("A" + formulaNoteRow).values = [["重点确认：标准原文把NS称为“泥磷制得磷酸的质量分数，以100% H3PO4计”，把NH称为“其他化学品中的磷质量百分数，以磷(P)计”。当前结构化规则统一按0～1小数录入并限制在0～1；如果确认表明企业资料按百分数记录，则应在软件录入层明确换算（例如85%→0.85），并在计算轨迹中保留原始值和换算值。炭质还原剂的EPT也应核对实物量、固定碳质量分数和1.1564折算系数，不能把未经说明的综合数值当作原文输入。"]];
formulas.getRange("A" + formulaNoteRow + ":H" + (formulaNoteRow + 4)).format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
formulas.freezePanes.freezeRows(3);
formulas.freezePanes.freezeColumns(2);
formulas.showGridLines = false;
widths(formulas, { A: 20, B: 34, C: 48, D: 70, E: 42, F: 12, G: 32, H: 16 }, 50);

title(corrections, "A1:H1", "GB 21345-2024来源、替代与订正记录", "本表记录标准替代关系、统计边界和待确认的录入口径；不修改标准原文。确认结论填写“一致”或“需修改”后，再进入规则发布流程。");
corrections.getRange("A3:H3").values = [["订正ID", "标准编号", "字段/事项", "原值/候选表述", "确认值/软件处理", "原因", "依据", "处理状态"]];
header(corrections.getRange("A3:H3"));
const correctionRows = [
  ["GB21345-replace", definition.number, "标准替代", "GB 21345-2015；旧版限额", "GB 21345-2024；旧版仅作为历史选择，不作为默认标准", "按新标准封面和前言的替代关系记录", "PDF第1页；前言", "待确认"],
  ["GB21345-date", definition.number, "发布日期/实施日期", "旧版日期", "2024-04-29发布；2025-05-01实施", "按新标准封面记录", "PDF第1页", "待确认"],
  ["GB21345-scope", definition.number, "适用范围", "黄磷产品范围需要确认", "仅适用于电炉法黄磷生产企业单位产品能耗计算、考核以及新建和改扩建项目能耗控制", "按第1章范围和3.1～3.4术语核对", "PDF第5页", "待确认"],
  ["GB21345-boundary", definition.number, "统计边界", "候选规则可能把所有能源直接合并", "生产、辅助、附属系统及耗能工质计入；独立磷矿粉成球装置、生活用能和建设改造用能不计入；界区外输出能源扣除", "按6.1.1～6.1.4和界区计量要求核对", "PDF第6～7页", "待确认"],
  ["GB21345-levels", definition.number, "等级与企业类型", "表1中1级/2级/3级", "软件分别输出三级；现有装置3级限定，新建和改扩建装置2级准入提示", "区分判级与准入要求", "PDF第6页；5.1～5.2", "待确认"],
  ["GB21345-formulas", definition.number, "公式（1）～（10）", "通用单位产品能耗公式", "按原文拆分EPS、EPT、EPL、EPE、EPFF、EPW和PP，并保留逐步计算轨迹", "避免遗漏电炉电耗修正和副产品折合产量", "PDF第7～9页；6.2.2.1～6.2.2.10", "待确认"],
  ["GB21345-fraction", definition.number, "NS/NH录入", "质量分数可能按百分数或小数录入", "草案暂按0～1小数；确认企业资料后再固定界面提示和换算规则", "公式结果对录入口径敏感，不能静默猜测", "PDF第9页；公式（9）～（10）", "待确认"],
];
corrections.getRange("A4:H" + (3 + correctionRows.length)).values = correctionRows;
body(corrections.getRange("A4:H" + (3 + correctionRows.length)));
reviewValidation(corrections.getRange("H4:H" + (3 + correctionRows.length)));
corrections.freezePanes.freezeRows(3);
corrections.showGridLines = false;
widths(corrections, { A: 24, B: 20, C: 24, D: 48, E: 60, F: 48, G: 36, H: 14 }, 40);

const tableCheck = await wb.inspect({ kind: "table", range: "确认汇总!A1:G" + (summaryNoteRow + 5), include: "values,formulas", tableMaxRows: 80, tableMaxCols: 10, tableMaxCellChars: 260 });
process.stdout.write(tableCheck.ndjson + "\n");
const errorCheck = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "GB 21345-2024 review workbook formula errors" });
process.stdout.write(errorCheck.ndjson + "\n");
for (const [sheetName, fileName, range] of [
  ["确认汇总", "gb21345-2024-summary.png", "A1:G22"],
  ["规则确认", "gb21345-2024-rules.png", "A1:T7"],
  ["公式核对", "gb21345-2024-formulas.png", "A1:H35"],
  ["订正记录", "gb21345-2024-corrections.png", "A1:H12"],
]) {
  const preview = await wb.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
const exported = await SpreadsheetFile.exportXlsx(wb);
const outPath = path.join(outputDir, "GB 21345-2024标准规则专项复核表.xlsx");
await exported.save(outPath);
process.stdout.write("OUTPUT=" + outPath + "\nPREVIEWS=" + previewDir + "\n");
