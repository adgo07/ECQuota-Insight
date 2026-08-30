import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const dataDir = path.resolve(process.env.UEBENCH_WORKBOOK_DATA_DIR || "work/next-scope-63/data");
const outputDir = path.resolve(process.env.UEBENCH_WORKBOOK_OUTPUT_DIR || "work/next-scope-63");
const previewDir = path.resolve("work/artifact-next29145/review-previews");
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
const definition = JSON.parse(await fs.readFile(path.join(dataDir, "definitions/gb-29145-2023.json"), "utf8"));
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
  sheet.getRange(first + row + ":" + last + row).format.rowHeight = 40;
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

title(summary, "A1:G1", "GB 29145-2023标准规则专项复核表", "本标准规则为draft草案；确认前不参与正式评价。请核对6个产品/工序、指标名称、三级限额、可比能耗公式、附录C查表系数和产品产量折算口径。软件评价日期读取运行当天；旧版或尚未实施标准由用户手动选择并显示提示。");
summary.getRange("A4:B12").values = [
  ["标准编号", definition.number],
  ["标准名称", definition.title],
  ["发布日期/实施日期", String(definition.publication_date) + " / " + String(definition.effective_date)],
  ["标准状态", "draft（待确认）"],
  ["生命周期", "active（2024-12-01已实施，规则尚未发布）"],
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
const summaryRows = indicators.map(({ product, indicator }) => [definition.number, product.name, indicator.name, indicator.unit, "≤" + threshold(indicator, "level_1") + " / ≤" + threshold(indicator, "level_2") + " / ≤" + threshold(indicator, "level_3"), definition.publication_status, "待确认"]);
summary.getRange("A15:G" + (14 + summaryRows.length)).values = summaryRows;
body(summary.getRange("A15:G" + (14 + summaryRows.length)));
const summaryNoteRow = 22;
summary.getRange("A" + summaryNoteRow + ":G" + (summaryNoteRow + 6)).merge();
summary.getRange("A" + summaryNoteRow).values = [["适用范围：地下开采钨精矿、露天开采钼精矿及焙烧钼精矿；不适用于露天开采钨精矿、地下开采钼精矿或副产为钨/钼精矿的企业。钨精矿和钼精矿的指标名称为“单位产品可比能耗”，按公式（2）使用附录C的μ修正；焙烧钼精矿的指标名称为“单位产品能耗”，不执行μ修正。附录C只允许使用表内K值，未列值返回不完整，不插值。"]];
summary.getRange("A" + summaryNoteRow + ":G" + (summaryNoteRow + 6)).format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
summary.freezePanes.freezeRows(3); summary.showGridLines = false;
widths(summary, { A: 20, B: 36, C: 24, D: 18, E: 36, F: 14, G: 14 }, 90);

title(rules, "A1:T1", "GB 29145-2023规则逐项确认", "请逐行核对产品/工序、指标名称、单位、三级限额、适用范围、公式、附录C查表值和原文页码；确认结论必须填写。相同标准下不同产品/工序各自独立判级。");
const ruleHeaders = ["序号", "标准编号", "标准名称", "产品/工序", "指标ID", "指标名称", "单位", "1级基础限额", "2级基础限额", "3级基础限额", "修正与适用说明", "来源定位", "PDF页码", "条款", "表号", "复核状态", "确认结论", "确认人", "确认日期", "确认备注"];
rules.getRange("A3:T3").values = [ruleHeaders]; header(rules.getRange("A3:T3"));
const ruleRows = indicators.map(({ product, indicator }, index) => {
  const first = indicator.source_references[0];
  return [index + 1, definition.number, definition.title, product.name, indicator.id, indicator.name, indicator.unit, threshold(indicator, "level_1"), threshold(indicator, "level_2"), threshold(indicator, "level_3"), (indicator.notes || []).join("\n"), sourceSummary(indicator), first.page, first.clause || "", first.table || "", definition.publication_status, "待确认", "", null, ""];
});
rules.getRange("A4:T" + (3 + ruleRows.length)).values = ruleRows; body(rules.getRange("A4:T" + (3 + ruleRows.length)));
rules.getRange("M4:M" + (3 + ruleRows.length)).format.numberFormat = "0";
rules.getRange("S4:S" + (3 + ruleRows.length)).format.numberFormat = "yyyy-mm-dd";
reviewValidation(rules.getRange("Q4:Q" + (3 + ruleRows.length)));
rules.freezePanes.freezeRows(3); rules.freezePanes.freezeColumns(2); rules.showGridLines = false;
widths(rules, { A: 8, B: 20, C: 44, D: 34, E: 52, F: 24, G: 18, H: 16, I: 16, J: 16, K: 74, L: 48, M: 10, N: 30, O: 24, P: 12, Q: 14, R: 14, S: 14, T: 34 }, 90);

title(formulas, "A1:H1", "公式、查表、统计范围与适用条件核对", "公式文字按GB 29145-2023原文整理；Excel只复现软件规则说明，不建立第二套判级逻辑。请重点核对附录C选矿比K的查表方式和钨/钼产品产量折算标准。");
formulas.getRange("A3:H3").values = [["编号", "原文项目", "标准公式/定义", "软件规则实现", "单位/录入要求", "PDF页码", "条款/表号", "复核结论"]]; header(formulas.getRange("A3:H3"));
const formulaRows = [
  ["（1）", "单位产品能耗 e", "e=(Σ(k_i×e_i)+EFZ+EFS−EHW)/P", "生产系统能源明细按折标系数汇总；加辅助生产EFZ、附属生产EFS，减二次能源回收外供EHW，再除以合格产品产量P。", "kgce/t；P必须大于0；output方向按抵扣处理", 6, "6.2；公式（1）", "待确认"],
  ["（2）", "钨/钼单位产品可比能耗 eKB", "eKB=e/μ", "钨精矿、钼精矿指标在公式（1）基础上除以附录C查得的μ；焙烧钼精矿不执行此修正。", "kgce/t；K必须在对应附录C表内有明确值", 7, "6.2；公式（2）", "待确认"],
  ["（3）", "附录C钨原矿品位折算系数", "K=250、280、310…610时μ=0.89、1.00、1.11…2.18", "gb29145.tungsten.ore_ratio按ratio输入；lookup严格匹配表C.1，未列值不插值。", "K按选矿比倍数输入，例如280；不录“280:1”文字", 10, "附录C；表C.1", "待确认"],
  ["（4）", "附录C钼原矿品位折算系数", "K=330、380、430…730时μ=0.78、0.88、1.00…1.70", "gb29145.molybdenum.ore_ratio按ratio输入；lookup严格匹配表C.2，未列值不插值。", "K按选矿比倍数输入，例如430；不录“430:1”文字", 10, "附录C；表C.2", "待确认"],
  ["（5）", "钨精矿产品产量", "以含钨量65%的标准量为基准", "产量明细用conversion_factor折算到含钨65%标准量；记录原始实物产量和折算系数。", "合格产品、单位t；折算系数由企业口径提供", 6, "6.1.4.1～6.1.4.3", "待确认"],
  ["（6）", "钼精矿产品产量", "以含钼量45%的标准量为基准", "产量明细用conversion_factor折算到含钼45%标准量；记录原始实物产量和折算系数。", "合格产品、单位t；折算系数由企业口径提供", 6, "6.1.4.1～6.1.4.3", "待确认"],
  ["（7）", "焙烧钼精矿产品产量", "以含钼量48%的标准量为基准", "产量明细用conversion_factor折算到含钼48%标准量；不执行μ修正。", "合格产品、单位t；折算系数由企业口径提供", 6, "6.1.4.1～6.1.4.3", "待确认"],
  ["（8）", "生产系统统计范围", "采矿、选矿或焙烧全过程所需设备设施能源", "分类键production_system；按产品类型保留生产工艺边界，外供二次能源另列output。", "钨/钼采选和焙烧范围不同，按6.1.1～6.1.3确认", 5, "6.1.1～6.1.3", "待确认"],
  ["（9）", "辅助与附属系统", "EFZ、EFS计入；北方冬季采暖能源不计入", "分类键auxiliary_system、affiliated_system；生活/冬季采暖等不应混入。", "kgce；多产品共同能耗按分摊规则留痕", 5, "6.1.1.2～6.1.3.3", "待确认"],
  ["（10）", "能源折算系数", "优先实测或供应单位数据，否则参照附录A、B", "每条EnergyLine保存实物量、折标系数、方向、分摊比例和来源；不把附录参考值当成强制固定值。", "系数单位分母必须与实物量单位一致", 6, "6.1.5；附录A、B", "待确认"],
];
formulas.getRange("A4:H" + (3 + formulaRows.length)).values = formulaRows; body(formulas.getRange("A4:H" + (3 + formulaRows.length)));
reviewValidation(formulas.getRange("H4:H" + (3 + formulaRows.length)));
const conditionHeaderRow = 16;
formulas.getRange("A" + conditionHeaderRow + ":H" + conditionHeaderRow).values = [["适用条件/边界", "原文要求", "软件处理", "错误风险", "PDF页码", "条款/表号", "当前状态", "复核结论"]]; header(formulas.getRange("A" + conditionHeaderRow + ":H" + conditionHeaderRow));
const conditionRows = [
  ["钨精矿适用范围", "地下开采钨精矿；不适用露天开采钨精矿", "产品“钨精矿—黑钨/白钨”保留范围提示；露天开采应选择不适用或历史说明", "错用采矿方式会导致评价口径错误", 3, "第1章；6.1.1", "draft", "待确认"],
  ["钼精矿适用范围", "露天开采钼精矿；不适用地下开采钼精矿", "产品“三段一闭路/SABC”保留露天开采提示；地下开采返回不适用", "错用采矿方式会导致评价口径错误", 3, "第1章；6.1.2", "draft", "待确认"],
  ["焙烧钼精矿生产类型", "多膛炉、内热式回转窑分别列限额", "两个产品/工序独立判级，不使用附录Cμ", "工艺混用会选错限额", 4, "4.3；表3", "draft", "待确认"],
  ["现有企业", "现有生产企业执行表中3级限定值", "等级仍分别输出1/2/3；企业类型只影响准入提示，不改变三级阈值", "把准入要求误当成总体等级", 5, "5.1～5.3", "draft", "待确认"],
  ["新建、改建和扩建项目", "执行表中2级准入值", "选择项目类型后提示必须达到2级；超过2级但不超过3级仍可显示3级但提示不满足准入", "遗漏准入提示", 5, "5.1～5.3", "draft", "待确认"],
  ["附录C查表", "规范性附录，仅给定离散K值", "严格查表；K不在表内返回不完整，禁止插值", "插值会改变标准口径", 10, "附录C；表C.1～C.2", "draft", "待确认"],
];
formulas.getRange("A17:H" + (16 + conditionRows.length)).values = conditionRows; body(formulas.getRange("A17:H" + (16 + conditionRows.length)));
reviewValidation(formulas.getRange("H17:H" + (16 + conditionRows.length)));
const formulaNoteRow = 25;
formulas.getRange("A" + formulaNoteRow + ":H" + (formulaNoteRow + 4)).merge();
formulas.getRange("A" + formulaNoteRow).values = [["关键确认：本标准的产品/工序名称已拆为“钨精矿—黑钨、钨精矿—白钨、钼精矿—三段一闭路、钼精矿—SABC、焙烧钼精矿—多膛炉、焙烧钼精矿—内热式回转窑”；指标名称只保留“单位产品可比能耗”或“单位产品能耗”。附录C的K值是离散查表值，表内未列值必须返回“不完整”，不做线性插值。"]];
formulas.getRange("A" + formulaNoteRow + ":H" + (formulaNoteRow + 4)).format = { fill: paleBlue, font: { color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
formulas.freezePanes.freezeRows(3); formulas.freezePanes.freezeColumns(2); formulas.showGridLines = false;
widths(formulas, { A: 20, B: 34, C: 52, D: 70, E: 44, F: 12, G: 32, H: 16 }, 55);

title(corrections, "A1:H1", "GB 29145-2023来源、替代与订正记录", "本表记录标准替代关系、产品边界和附录C查表处理；不修改标准原文。确认结论填写“一致”或“需修改”后，再进入规则发布流程。");
corrections.getRange("A3:H3").values = [["订正ID", "标准编号", "字段/事项", "原值/候选表述", "确认值/软件处理", "原因", "依据", "处理状态"]]; header(corrections.getRange("A3:H3"));
const correctionRows = [
  ["GB29145-replace", definition.number, "标准替代", "GB 29145-2012、GB 29146-2012、GB 31340-2014分别规定", "GB 29145-2023整合替代三个旧标准；旧版仅历史选择，不作为默认标准", "按新标准封面和前言记录替代关系", "PDF第1～2页；前言", "待确认"],
  ["GB29145-date", definition.number, "发布日期/实施日期", "旧版日期", "2023-11-27发布；2024-12-01实施", "按新标准封面记录", "PDF第1页", "待确认"],
  ["GB29145-scope", definition.number, "适用范围", "钨、钼和焙烧钼精矿范围未拆分", "地下开采钨精矿、露天开采钼精矿及焙烧钼精矿；露天钨、地下钼和副产精矿不适用", "按第1章和6.1.1～6.1.3核对", "PDF第3～6页", "待确认"],
  ["GB29145-products", definition.number, "产品/工序与指标名称", "产品名中混有指标后缀", "6个产品/工序独立列出；指标名称仅为“单位产品可比能耗”或“单位产品能耗”", "遵循产品/工序+指标名称命名规则", "PDF第4页；表1～表3", "待确认"],
  ["GB29145-output", definition.number, "产品产量折算", "直接用实物产量P", "钨精矿按含钨65%、钼精矿按含钼45%、焙烧钼精矿按含钼48%折算为标准量", "按6.1.4产品产量规定实现", "PDF第6页；6.1.4", "待确认"],
  ["GB29145-lookup", definition.number, "附录C查表", "K不在表内时可按相邻值估计", "仅接受表C.1/C.2列出的K值；未列值返回不完整，不插值", "附录C为规范性离散查表", "PDF第10页；附录C", "待确认"],
  ["GB29145-boundary", definition.number, "能耗统计边界", "所有能源直接汇总", "生产系统+辅助系统+附属系统−二次能源回收外供；北方冬季采暖能源不计入", "按6.1和公式（1）核对", "PDF第5～7页", "待确认"],
];
corrections.getRange("A4:H" + (3 + correctionRows.length)).values = correctionRows; body(corrections.getRange("A4:H" + (3 + correctionRows.length)));
reviewValidation(corrections.getRange("H4:H" + (3 + correctionRows.length)));
corrections.freezePanes.freezeRows(3); corrections.showGridLines = false;
widths(corrections, { A: 24, B: 20, C: 24, D: 48, E: 62, F: 48, G: 36, H: 14 }, 45);

const tableCheck = await wb.inspect({ kind: "table", range: "确认汇总!A1:G" + (summaryNoteRow + 6), include: "values,formulas", tableMaxRows: 80, tableMaxCols: 10, tableMaxCellChars: 260 });
process.stdout.write(tableCheck.ndjson + "\n");
const errorCheck = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "GB 29145-2023 review workbook formula errors" });
process.stdout.write(errorCheck.ndjson + "\n");
for (const [sheetName, fileName, range] of [
  ["确认汇总", "gb29145-2023-summary.png", "A1:G29"],
  ["规则确认", "gb29145-2023-rules.png", "A1:T11"],
  ["公式核对", "gb29145-2023-formulas.png", "A1:H30"],
  ["订正记录", "gb29145-2023-corrections.png", "A1:H12"],
]) {
  const preview = await wb.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
const exported = await SpreadsheetFile.exportXlsx(wb);
const outPath = path.join(outputDir, "GB 29145-2023标准规则专项复核表.xlsx");
await exported.save(outPath);
process.stdout.write("OUTPUT=" + outPath + "\nPREVIEWS=" + previewDir + "\n");
