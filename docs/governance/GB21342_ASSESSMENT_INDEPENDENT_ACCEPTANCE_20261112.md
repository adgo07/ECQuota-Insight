# GB 21342—2025 完整判级独立验收记录

日期：2026-11-12。性质：纯Domain完整判级与Application/Facade只读预览验收；不是GUI、正式记录、Word或整标准Stage D验收，不开放正式评价。

## 平台 / Contract预检查

已实际核验受验树`work/coke-core-20261112`的origin为`https://github.com/adgo07/ECQuota-Insight.git`、分支`codex/coke-core-20261112`、基线HEAD`47d50b51a992a04cf167fb60f0b6de632877771a`。开始时clean。本验收阶段实现尚未提交，最终按下列内容hash固定：

| 文件 | SHA256 |
|---|---|
| src/uebench/domain/gb21342.py | 2F3FCD60A2F3D0710280EDC2A73E828DE170A662E10FACD560A3F8BE5BC4B7F2 |
| src/uebench/application/gb21342.py | 4F14F6D99AB732E0D6A7775D2238A9E5F33915902B1F8041677F38590AECFE69 |
| src/uebench/application/facade.py | D3A46806750314EB59E510F6300AA3D07CB39B0F74CA722614C0D517359B92D7 |

Frozen锁定中央`ee5feb0cc34dbd99790500fadd0c4c932e202a20`；Numeric Contract/Profile/Conformance v1保持原基线，Decimal28/ROUND_HALF_EVEN，全值精确比较、无默认ROUND6/epsilon/显示回流、无float恢复、ambient/DefaultContext独立。没有CENTRAL CONTRACT GAP，无须中央Contract修改；Unit仍DRAFT。本次fetch在共享.git/worktrees路径写FETCH_HEAD被权限拒绝，未改权限或声称该命令成功，继续基于已核HEAD和父已同步的分支只读审查。

001已采用Owner确认的最高级别软件策略，不区分企业/项目属性，不输出限定/准入合规主结论；相邻线性为本轮明确常规软件算法选择，不冒充原文唯一算法。002部分外属、003表外、004混合熄焦保持对应未知；005已折标五量入口不涉及气种别名。other/unknown燃料F未知而非0是父本轮确认的软件处理。scope默认None、False不适用；保留有效energy输入要求。

## 独立预期来源

先于实现编制[独立Golden候选（归档版）](../golden/GB21342_ASSESSMENT_GOLDEN_CANDIDATES_20261112.md)（本机原稿`work/coke-grading-review-20261112/INDEPENDENT_GOLDEN_CANDIDATES_20261112.md`），初始定稿SHA256`B18B4A6D1305C51EBE13B27FD877CCD0E8B872A8F32B3A27B84A6B5E9DF7E947`。16个全部节点、14个相邻中点的修正和阈值逐行手算；节点邻点以原表端点的有理数线段独立推导；未调用实际实现或旧Engine反生预期。

原PDF SHA256`00fcc51c02c6d73d39bcab3103227fca2ee93841abce45d1576edaeba25595a0`，表1/表2与式1/2、式3及26调整对应PDF6—8；本轮重读PDF7表2。全部节点/中点、F/M/A/Q修正均有原表依据。最高级别优先级是独立记录的软件决定。

## 已执行结果

1. 独立`probe.py`：269/269 PASS。覆盖两炉型全部节点/中点各L1/L3的T−1e−7、T、T+1e−7；所有表内节点邻点、C02/C03、F0/1、两水分基准±1百分点、炉龄15/15+δ/25/25+δ、湿熄仅3级、全部未知分支、类型拒绝、ambient与DefaultContext独立及Application预览一致。
2. 独立`integration_probe.py`：9/9 PASS。实际Facade在standards/evaluations/evaluation_service/audit/word_report_writer全部Forbidden替身下完成预览，证明不读legacy r1或写库/审计/报告；实际EvaluationService.evaluate对CURRENT/HISTORICAL/FUTURE三种selection_mode均在解析/计算/保存前明确拒绝焦炭。不是只检查supports登记值。
3. 额外集成断言已包含于上述9项：全部8个assessment原始正规化输入进入trace；每级partial26、scope未知/不适用给出未定原因；可缺参数省略仍保留actual；显式unknown fuel不当0。
4. 独立pytest：`tests/test_gb21342_assessment.py`253项＋`tests/test_gb21342_core.py`151项＋`tests/conformance/numeric/test_ecquota_numeric_v1.py`20项，共424 passed，exit0，2.75s。执行器为主checkout `.venv/Scripts/python.exe`，Python3.13.3、pytest8.4.2；cwd受验树，参数`-o addopts='' -p no:cacheprovider`。

本机探针证据均位于当前执行机器`G:/Python Project/能耗限额/work/coke-grading-review-20261112/`，文件为`probe.py`、`integration_probe.py`、`report_final.json`、`integration_final.json`、`docstring_audit.json`。该绝对路径仅为本次环境记录，不是跨机器仓库入口或运行依赖；JSON/探针保留于ignored work，不声称已随Git归档。两份final JSON固定受验功能版hash `8D1F197C3FEBD0E980AE3D9F5761F73DFBA336618F151F7FA1B7E57A5EFDC8F7`及逐探针结果；`report_initial.json`仅初版追溯，不替代最终验收。源码最终注释差异另见下一节。验收线没有写实现文件、生产规则或生产测试期望。

## 最终模块说明文字差异核验

全部探针及424项测试运行时Domain文件hash为`8D1F197C3FEBD0E980AE3D9F5761F73DFBA336618F151F7FA1B7E57A5EFDC8F7`。之后仅模块首行说明由“式（3）的独立未发布核心；不形成等级或正式记录”改为“独立未发布的能耗与判级预览；不形成正式记录”，消除新增判级后过时的“不形成等级”文字。

本验收线独立将最终首行替换回原文，所得整文件SHA256精确复得上述受验hash；两版移除首个模块docstring节点后的AST完全相同。因此当前表列最终hash `2F3FCD60A2F3D0710280EDC2A73E828DE170A662E10FACD560A3F8BE5BC4B7F2`与受验功能体一致，复用既有通过证据，没有重跑或虚报新一轮测试。证据为上述本机目录`docstring_audit.json`。

归档导航：[Stage B设计](GB21342_STAGE_B_DESIGN_20261112.md) · [本轮实施记录](GB21342_STAGE_C_ASSESSMENT_REPORT_20261112.md) · [独立Golden候选](../golden/GB21342_ASSESSMENT_GOLDEN_CANDIDATES_20261112.md)。这些相对链接以本记录归档路径`docs/governance/GB21342_ASSESSMENT_INDEPENDENT_ACCEPTANCE_20261112.md`为基准。

## 关键结论与边界

- C02原阈值126.57/124.07/198.03、E125最终1级；基准顶装20年E111最终1级、E113最终3级。没有排序阈值、强制单调或由1级满足推断2级满足。
- 已知1级满足不要求补Q/L3；未知1级不能被已知2级满足冒充最高级别；1/2已失败且Q未知不能报未达3级；评价值未定无级；全部已知且全部失败才未达3级。
- 真实完整工况L1=L2+A≥L2，因此真实最终2级不可达。验收未伪造真实2级工况，也未为此改规则；选择循环保留对2级的正常优先级分支。合成状态机说明与原文工况严格分开。
- preview_coke只通过专属Domain链，不依赖生产r1；现有旧preview_evaluation路径作为基线未改，不能把它与本次专属预览混同。formal evaluate仍拒焦炭，未新增正式记录/合规主结论。
- 静态检索新API的src引用仅Domain、新Application入口和Facade薄委托；UI、Word/基础设施报告及reporting.py均无该API调用，未改这些路径。本内部001解释保留治理资料，没有新接入UI/Word/外部导出。此处不声称完成未来GUI/Word实机验收。

审查无剩余阻塞缺陷。可交父审核PR40；不授权合并，不代表整标准正式支持或Stage D通过。full suite、原N01-A及其它所需门禁由实施/父执行记录，不以本次定向424项冒充。
