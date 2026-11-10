# 水泥 Stage C 第1块：核心计算与独立 Golden

日期：2026-11-11。状态：**已实现核心定向路径，交父Agent独立审查；尚未Stage D验收，不是SUPPORTED。** 本记录仅覆盖规则/Domain/兼容模型/独立Golden，不把后续页面、保存门禁、Word或配套包写成已完成。

## 平台 / Contract 预检查

业务仓起点 `298a966de8cec03f02daa646108911007c281aa3`，Stage B设计提交 `55d09fa8849aa1cf60f4e4ef5e58ac8bfef102bd` 已经父Agent独立审查通过并授权此块实施；提交范围与实际SHA由本块Git提交/PR追踪。origin已核为adgo07/ECQuota-Insight，中央origin为adgo07/Qingzhou-contracts。

锁仍为 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`；读取其Architecture 2.1、Numeric Contract/Profiles/Conformance v1；ACTIVE指南读取中央已合并 `829853a943c421e0b9864d84f3d94970d2ddf688` 的GUIDE_INDEX路由，详见[Stage B预检查](GB16780_STAGE_B_DESIGN_20261111.md)。本块MUST为Decimal28/HALF_EVEN、正式全值比较、相同Profile上下文、可追溯版本、历史保真；MUST NOT为权威float、隐式修约、epsilon、显示值回流、默认Q_BM、自动重算历史及修改Frozen。

业务仍以V1.2原字节为准；涉及Issue001（内部RESOLVED，e_sh非E_sh）及003（PROVISIONAL，先海拔后配比），没有新增或改变业务解释，没有取得官方勘误。修旧实现与映射差异属于LOCAL DEFECT；既有D-ECQ-002～006保持REGISTERED DEVIATION，无CENTRAL CONTRACT GAP，无中央Contract修改，Unit/Record/qzpack不宣称正式采用。

## 已完成的受测路径

- 水泥规则由r1升级为r2，单一 `cement-assessment` 产品承载四模式及五个原稳定指标ID；名称、单位、适用条件、五套基础/有效阈值及来源保存于唯一编辑源 `data/definitions/gb-16780-2021.json`。L1/L2系数1.10/1.15，L3仅94乘K后加1.20百分点修正；未新增W_s等级、熟料总等级或建设属性符合性。
- 通用Engine只在标准ID+r2+精确V1.2采用标识匹配时分派专用Domain；r2缺标识、标识错误版本、新明细套旧r1均拒绝。历史r1仍使用其原规则，测试以提交前r1完整fixture核对旧阈值，不把旧算法视为本次批准期望。
- 请求增量增加水泥生产线与有限共用能耗类型；结果仅增量可选线标识/线名称，复用原结果集合，不改数据库表或migration。水泥拒绝DIRECT和通用折标总量混入；其它标准不能混入水泥明细。
- 依赖节点实现式（2）～（9），燃料实物量/低位发热量与Q_BM分开，不静默给Q_BM默认。tce仅在源端乘1000，电量保持kWh；余热与四项各扣一次。P_sh/P_shx/P_s独立；下游使用净e_sh/W_sh，部分外购采用e_sh而非E_sh。
- 原始输入/共享燃料统一拒绝float、非有限数和非法单位/负数，保留缺失和四扣除空白状态。缺值或超额只影响依赖指标；缺压力保留四项实际值但其动态等级不完整，表3仍独立判级。仅熟料3项适用，纯外购仅表3正式适用，本轮不展示可选扩展E_s。
- 多线共用量按目标的P_sh/P_s产量比在Profile内分摊，仅合入源端；燃料按原始实物量先分摊再乘发热量。无最后一线补差，无显示修约。共享源非法/参与线缺产量只传播至相关消费节点，重复共享项/参与集合身份冲突拒绝请求。
- 独立Golden期望先来自Stage B手算，再固化JSON及[人读证据](../golden/GB16780_GOLDEN_CANDIDATES_V1.md)；测试另用有理数复算。五指标各三级T−δ/T/T+δ在基础与海拔+配比组合下均从DETAIL原始量驱动，δ=0.0000001；未使用DIRECT绕过新入口。104.70/105.00陷阱另有精确K节点fixture及真实压力端到端检查。

## 本地验证

全部通过，独立工作树src为明确PYTHONPATH，TEMP/TMP及pytest临时目录均隔离在该工作树work/cement-stagec；未使用真实用户库或旧测试包。

| 运行组 | 结果 |
|---|---|
| `tests/test_gb16780_core.py`、`tests/test_first_batch_rules.py`、`tests/test_engine.py`、`tests/conformance/numeric/test_ecquota_numeric_v1.py` | **196 passed**（最终本块源码，3.07s） |
| `tests/pilots/numeric/test_qzc_n01_a.py`、`tests/test_gb29446_product_golden.py`、`tests/test_gb29446_record_lifecycle.py`、`tests/test_evaluation_scope_enforcement.py`、`tests/test_evaluation_support.py`、`tests/test_scope_44.py` | **114 passed**（58.09s；随后仅水泥命名K节点/缓存与display_values依赖trace、规则缺产品错误及水泥测试变更，无选煤/公共逻辑再改） |
| 初轮历史fixture测试 | 138 passed/1 failed：历史r1旧引擎要求单位，测试请求补齐快照单位后通过；未修改旧算法或业务expected来消除失败 |

196项组含核心新增150项，覆盖五套阈值单源消费、所有模式、全值边界、两种g口径、源端扣一次、独立数量、依赖传播、共享尾差、错误共享源、非有限/float、旧r1与Numeric身份。K来自规则唯一命名节点，每线只执行一次并保存K=1或高海拔全值，四项阈值均引用该节点，后续展示层不重算。114项组验证选煤Golden/历史生命周期、原N01-A、当前正式范围阻断及真实签名包r1预览的原有边界，不据此宣称水泥正式保存或配套r2包已通过。

文档链接、冻结映射与platform-lock哈希及`git diff --check`提交前核对；完整pytest、精确提交CI及numeric-v1-adoption工作流留待最终实现稳定后执行。本块不提前跑约40分钟全套，不把历史全套或父侧独立早期观察平移为本提交全面验收。

## 明确未完成

1. Application水泥全部适用项完整性检查与 `IncompleteCementEvaluationError.preview_result` 的Facade/UI传递、无保存审计与防重复提交，属于下一块；本块生产正式范围仍仅选煤，现有服务会在计算前阻断水泥正式请求，没有临时开关或绕过。
2. 新建水泥表单、按线结果、两页签历史、保存快照Word视图与渲染/实开验证尚未实施；当前没有桌面原生或候选包水泥验收结论。
3. 交付索引、签名r2配套包与PIN/候选构建未更新；当前签名包仍含水泥r1，不能用它验证新水泥算法。后续只允许水泥定义和必要水泥corrections差异，其余47定义及无关corrections原字节不变；不改信任公钥、不造签名、私钥缺失由父协调受控位置。
4. Stage D前不改正式支持集合或宣称SUPPORTED，不发布/tag，PR由父提交，未获Owner授权不合并。RS05环境缺口仍保留、产品闭环PARTIAL，Excel正式用户流程继续DEFERRED。

Knowledge capture：无新增独立知识条目，标准事实/内部解释继续引用冻结映射与唯一问题台账。
