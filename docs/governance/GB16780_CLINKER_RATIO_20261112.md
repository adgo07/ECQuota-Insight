# 水泥熟料配比辅助输入与一致性校核

日期：2026-11-12。状态：源码实施，待独立验收；水泥仍为 IMPLEMENTED、Stage D OPEN，唯一未发布 r3 候选不变。本次不开放正式评价、不发布产品。

## 平台 / Contract 预检查

- 仓库：`adgo07/ECQuota-Insight`，已实际核对 origin、clean 工作树并成功 fetch；默认分支 `main`，实施基线 `f6106ede07aa815a815e6f8cae07cc7103f9c08e`。原本地 `24f767295ed2040421f28ab37f930bfad794f470` 与该 main 文件树相同。
- `platform-lock.json` 中央锁定 SHA：`ee5feb0cc34dbd99790500fadd0c4c932e202a20`；相关 Frozen 为 Numeric Contract v1、Profiles v1、Conformance Vector v1，Architecture 2.1 保持采用基线。
- MUST：Decimal、28 位有效数字、ROUND_HALF_EVEN、全值比较，显示与计算分离，历史只读。MUST NOT：显示修约回流、隐含业务容差、调用方 ambient context 改变权威计算。
- 已按中央当前 `docs/GUIDE_INDEX.md` 读取 UI 家族规格、v0.2 指南及适用清单（2026-11-10 当前版本），Frozen 文件按锁定 SHA 读取。就近内联提示、保留 Decimal 文本、空白不视为零。
- 分类：ALLOWED PROJECT DIFFERENCE（本标准输入辅助与项目 Numeric Profile）；未发现 Frozen 冲突，不需要中央 Contract 修改。
- 相关 Standard Issue：001、003 的既有解释涉及原水泥核算与修正，本次不修改它们；未发现新标准原文问题，不新增台账编号。
- 本次改变软件输入辅助方式，不改变既有标准解释、判级、公式或阈值。

## 依据与行为

冻结映射 V1.2 §9.3、§16、§24 分别保留 `P_sh`、`P_shx`、`P_s` 与独立 `g` 输入。映射没有规定所有请求必须满足 `g=P_shx/P_s×100`；因此本次用户授权的比值是辅助输入及一致性提示，不冒称新增标准强制公式，不能用自产熟料产量代替熟料实际消耗量。

新建“自产熟料并生产水泥”“部分外购熟料生产水泥”生产线默认按“本期生产水泥消耗的熟料总量÷水泥总产量×100”自动填写配比。自动配比只读，数量更新后同步更新；缺失、非法、非有限、负数、零分母、单位错误和消耗量大于水泥产量时清除旧自动值并就近提示。对分子大于分母先作 Decimal 原始全值比较，避免极小超量被 working rounding 掩盖。仅生产熟料、全部外购熟料粉磨站不推导当前配比。

用户可明确切换“手工输入”。手工值与计算值精确不相等时显示差异及核对统计口径提示，不引入无来源容差，不阻止既有合法手工请求。新计算结果携带同一提示，报告仍使用保存结果，不从历史输入重新生成提示。切回自动会明确采用当前数量的计算值。

请求新增向后兼容 `CementLineInput.clinker_ratio_mode`（`manual` / `automatic`，旧请求缺失时按 `manual` 的兼容语义处理）。这不表示历史用户曾明确选择手工来源，故不新增历史来源断言。保存请求记录模式、原数量与完整配比，数据库 Schema 不变。历史表单加载一律保留保存的配比并转为可编辑手工状态；包括原自动请求也不在加载期间静默重写。重复加载清空旧字段、燃料行后载入，避免燃料叠加。

自动模式的请求在 Domain 的水泥综合能耗节点校核完整配比，调用 Application 或直接 Engine 均不能用过期/缺失/非法自动配比取得完整结果。失败仅使该指标不完整，其他正确适用指标仍可部分预览；Application 既有完整性门禁阻止保存整次评价，符合 Q1=A。默认手工的既有 r3 请求仍按其原 `g` 算法计算，不增加无条件相等约束。

## 精度边界

辅助函数使用 `ECQUOTA_DECIMAL_FULL_VALUE_V1.decimal_context()` 的独立局部上下文，包括项目精度、rounding 和 traps；调用方设置的精度、rounding、Inexact trap 不污染结果。顺序固定为 `P_shx/P_s×100`。28 位是 working precision，不是额外业务修约；循环小数保持该上下文完整结果字符串，如 `1/3×100=33.33333333333333333333333333`，不先格式化显示再回传。手工字符串保留原始十进制语义，精确一致性比较不使用显示两位或 epsilon。

## 验证与边界

测试全部使用合成数据、独立临时目录和本树 `src`，未读取真实用户 Excel 或业务库。执行解释器为现有 `work/venv313/Scripts/python.exe`；日志与临时数据在忽略的 `work/cement-ratio-*` 下。

- `.github/workflows/numeric-v1-adoption.yml` 的本地等效检查：`compileall src tests tools`、生产全局 ROUND6 禁止词断言、已发布规则隐含修约断言通过，已发布显式修约声明 0 项。
- Numeric workflow 所列 Frozen Conformance、N01-A migration、GB29446、Engine、Excel、UI 专项：138 passed，19.44 s；`work/cement-ratio-numeric.log` / `.xml`。
- 现有解释器没有 pip，未安装或升级依赖；依赖记录通过 `importlib.metadata` 读取：jsonschema 4.26.0、jsonschema-specifications 2025.9.1、attrs 26.1.0、referencing 0.37.0、rpds-py 2026.6.3。本地等效执行不冒称 GitHub workflow 已运行。
- 生产代码与测试定稿提交：`ffc3ce92ec06ca24f50f136342d3a4eb78fd7b88`。
- 水泥定向（core、application、UI、ratio）：202 passed，13.62 s；`work/cement-ratio-focused.log` / `.xml`。新增 22 项覆盖低精度/rounding/Inexact trap 的 ambient 隔离、0/100/原始略超100、循环小数、缺失/非法/零分母/单位、应用请求防绕过及部分预览、手工差异、模式/多线隔离、重复加载、自动保存恰一次和旧无 mode 请求三 JSON 原字节保真。
- 父任务独立源码审查通过；独立 ratio + cement_history：36 passed，4.22 s，`work/ratio-parent-acceptance/independent-tests.xml`；父任务已记录生产文件哈希。
- 完整回归与原生最终结果由 PR 验收记录补充，以实际日志为准，本文不预宣称通过。本地完整回归日志为 `work/cement-ratio-full.log` / `.xml`；最终文档提交之后生产代码保持上述定稿提交的相同字节，父任务按已记录哈希复核。

生产 `data`、配套 r1、PIN、公钥、冻结映射、唯一 r3 候选 Rule、数据库 Schema、Frozen lock 和正式支持集合均不变。原生 UI、候选打包、签名及 Stage D 不由离屏测试代替；独立验收由父任务承接。
