# GB 21342—2025 完整纯业务判级预览实施记录

日期：2026-11-12。本轮完成两炉型已折标明细→实际能耗/26→修正阈值→最高级别的只读业务链及Application/Facade入口。未做GUI、原始能源台账折标、正式记录、包签名发布或整标准Stage D；整体仍MAPPING，正式支持范围未扩大。

## 平台 / Contract预检查

业务起点为PR40的`47d50b51a992a04cf167fb60f0b6de632877771a`；最终源码以本次PR实际head及独立验收文件hash确定。`platform-lock.json`锁中央`ee5feb0cc34dbd99790500fadd0c4c932e202a20`，Architecture2.1、Numeric Contract/Profile/Conformance v1未升级。ACTIVE指南读取及局部采用依据见[当前Stage B](GB21342_STAGE_B_DESIGN_20261112.md)。

MUST：纯Domain、项目Decimal28/ROUND_HALF_EVEN、全值比较、完整Profile传递与ambient/DefaultContext独立、显示不回流、版本及来源trace。MUST NOT：默认ROUND6/epsilon/float恢复、运行时解析Mapping或知识文档、修改历史结果。Unit/Record/qzpack仍DRAFT，已登记偏差保持。无CENTRAL CONTRACT GAP，无须中央修改。

Issue001按Owner明确软件最高级别决定实施，PROVISIONAL，解释只在内部资料，不加入UI/Word/导出。003区间内相邻线性为本轮授权下明确采用的常规软件算法选择，非标准唯一算法；003表外仍OPEN。002部分外属未定、004混合熄焦未定、005气种术语不扩解释。局部原文依据为式1～3、表1/2及明确26条件，不代表整映射批准。不修改标准原文、Mapping正文、冻结水泥或生产r1。

## 实现及真实调用边界

- `CokeAssessmentInput`持有首块`CokeEnergyInput`；炉型/燃料/Vd/Mt/炉龄/熄焦/混合煤气时间比例/常规焦炉事实可缺，缺失与非法类型/值分开。常规焦炉默认None→未定，False→不适用，不静默当True，不新增企业属性或建设项目属性。
- 该API始终要求有效已折标energy，包括非适用/适用未知时，便于保留实际能耗参考；不为本轮扩展可选energy或原始台账折标。不同炉型/炉龄/分期聚合未实施。
- `assess_coke`复用首块式3/明确26；所有输入严格拒float/bool/非有限数。负能量输入按首块策略保留警示，不改P>0。各级阈值遵守修正矩阵；L3操作顺序B+F+V+M+Q+A，全程同一显式Context。
- `CokeAssessmentResult`保留energy、各级base/corrections/threshold/matched/undetermined_reasons、现有Grade、完整trace及局部版本/源SHA。八项评价原输入全部进入trace；调整未定或适用事实未知也保留每级matched未定原因。
- `application.gb21342.preview_coke`与`ApplicationFacade.preview_coke`提供真实可调用只读入口，直接消费上述Canonical；不访问标准库/legacy焦炭r1、数据库、审计、Word或保存服务。不改`EvaluationRequest`、共有Engine、正式evaluate门禁或Schema，不另建机器规则JSON。

## 判级与未定子项

按原等级阈值分别比较，不排序/夹取/强制单调；以1→2→3最高满足选择。高等级未知时不由较低满足项伪造最高等级；已过1不要求补Q/L3；1失败且2通过不要求补3；三者明确失败才未达3级。完整真实工况B1=B2、F/V/M共用、A≥0，故L1≥L2，真实完整工况不会最终2级；保留原表与软件策略自然结果，不制造阈值修复它。

部分外属导致Eeval未知时actual和可算阈值保留，无最终等级；表外Vd不外推/夹取，阈值未知但保留actual；混合/未知熄焦Q只影响L3；other/unknown燃料无表列修正，F未知不默认0；005不影响已折标五量入口。未定不是超限，不适用不伪等级。

## 本地验证与独立验收

独立预期来自先于实现编制的[判级Golden](../golden/GB21342_ASSESSMENT_GOLDEN_CANDIDATES_20261112.md)：全部16节点和14中点，两个阈值各T±1e-7/T、因素矩阵、C02/C03、15/25边界、r端点、表外/缺项/混合熄焦/partial26/scope及Context，不由实现反推。

- 最终焦炭判级253＋首块151共404项；连同Frozen Conformance、原N01-A、GB29446、Engine、Excel、UI、正式范围/支持门禁组合共568 passed，102.86s，exit0。未本地重复full suite。
- 既有`tests/test_application_facade.py`另9 passed，1.34s；`compileall -q src tests tools`通过。
- 独立验收269个业务/Numeric探针＋9个集成探针通过，独立执行判级253＋首块151＋Frozen20共424 passed，exit0；详见[独立验收记录](GB21342_ASSESSMENT_INDEPENDENT_ACCEPTANCE_20261112.md)。真实正式evaluate在三种选择模式均拒绝焦炭，Facade在所有存储/规则/审计/Word依赖禁止访问时仍可完成只读预览。
- 最终远端literal full suite与Numeric/N01-A工作流以PR40最终head为准；本记录提交时未核最终CI，不预写PASS。CI结果直接补PR正文，避免仅为报告再制造新head重跑全套。

当前未改生产data/PIN/签名包/支持清单，supersedes遗漏仍须后续真实配套规则修订并签名；签名私钥缺失未解。PR保持draft，不合并、不发布，局部业务链验证不是整标准IMPLEMENTED/SUPPORTED或产品全闭环验收。
