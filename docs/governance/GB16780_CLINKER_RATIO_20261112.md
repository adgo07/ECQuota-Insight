# 熟料配比强制计算及科学符号显示

2026-11-12 Owner 修订决定，源码实施与父独立源码审查已完成，测试证据见下；原生验收 OPEN。水泥 Stage D OPEN、未发布，正式支持集合不变。

## 平台 / Contract 预检查

- 业务仓 adgo07/ECQuota-Insight，基线 828e8b34f5fb165889e513d3aa1550df0590919b；已核工作树、origin、分支与 HEAD，默认远端分支 main。
- platform-lock.json 锁定中央 ee5feb0cc34dbd99790500fadd0c4c932e202a20；相关 Frozen：Architecture 2.1、Numeric v1、Profiles v1、Conformance Vector v1。
- MUST：Decimal、28位、ROUND_HALF_EVEN、全值比较、历史只读；MUST NOT：隐式修约、容差、显示回流、ambient context 污染。
- 中央当前 GUIDE_INDEX 及适用 UI v0.2 指南由本次父验收读取核对。分类 ALLOWED PROJECT DIFFERENCE，不需要中央 Contract 修改。Standard Issue 001、003 保持原解释，未发现新原文问题。
- 本次改变软件 g 输入来源策略，覆盖此前手工输入决定；不改变标准公式、阈值或 Frozen Mapping 原字节。

## 当前决定

Owner 明确要求熟料配比不可手填。适用生产线的新评价无条件按本期生产水泥消耗的熟料总量÷水泥总产量×100计算，不使用熟料自产产量替代。UI 只有只读自动值；Engine 同样计算，忽略请求中的 g 和历史兼容 mode，Application 保存深拷贝后的计算值与 automatic 来源，原调用方对象不变。计算 trace 保留原始数量和 P_shx/P_s×100。缺失、非法、非有限、负数、零分母、单位错误和分子超过分母时不得保存完整结果，允许其余指标部分预览。

计算仍使用 Numeric Profile 独立上下文及完整小数字符串。新 numeric_behavior_version 为 gb16780-v1.2-calculated-ratio-v2，因为旧 manual 不一致请求的新结果会改变；calculator_version 与规则修订不变，规则公式未改。历史读取明确兼容 gb16780-v1.2-full-value-v1，不重算，不重写 request/result/rule_snapshot 三 JSON。旧 Golden 继续保存原证据；当前测试以数量求 g 并独立断言。

所有标准的用户可见符号按真实上下标排版，范围及转义规则写入 AGENTS.md 和统一判定规范 §11。机器标识保持原值。

## 当前验证

- 完整依赖环境解释器：既有 rs05-pr34-closure-20261029/.venv，python-docx 1.2.0；测试 pythonpath 明确本树 src，临时数据库在系统 TEMP。
- 水泥 core/application/UI/ratio、历史、科学符号与选煤 Word 定向 244 passed（退出0，work/pr39-focused.log）。后续v1历史兼容与符号最终复验35 passed，2.83秒，work/pr39-final-ratio.log / .xml。
- Numeric workflow所列Frozen Conformance、N01-A、GB29446、Engine、Excel、UI：138 passed（退出0，work/pr39-numeric.log）。这是本地等效专项，不冒称GitHub workflow运行；完整full suite与最终三项CI由父验收在稳定提交执行。
- 首轮使用根.venv缺python-docx，7项Word测试环境失败；另1项测试对熟料超量的影响范围预期过宽，已按依赖修正为仅水泥综合能耗不完整。首轮日志被后轮覆盖，不能再作为原始证据链接。
- 父独立Engine探针通过：manual99、原数量800/2000时采用计算g40，阈值41.50/46.75/52.00，调用方原字节不变；零分母阻止E_s完整结果。
- compileall src/tests/tools、禁止全局ROUND6、已发布显式修约声明0项通过；生产data/release未改。静态初验误将autocrlf=true下的工作树CRLF与Git LF blob比原字节导致断言失败，保留work/pr39-static.log；最终work/pr39-static-final.log按批准工作树SHA256及Git index==HEAD、无diff核验通过，未修改冻结文件。
- Qt QTextDocument实际下标属性、Word run下标属性、P_H/Q_idw/m_i/P_shx完整复合角标及HTML转义通过。父已查看正确字体的离屏PNG，静态角标与自动g视觉通过，仅代表静态检查；原生工具因已有active request持续失败，Astra无原生通过结论，见work/pr39-native/README.md。原生 UI、Word 实开、签名与 Stage D 不由离屏测试代替。生产 data、PIN、公钥、锁定文件、唯一 r3 Rule 和 Frozen Mapping 不改。

---

## 历史记录：首次辅助输入方案（已被上述 Owner 决定覆盖）

以下为当时方案及测试证据，不再代表当前输入策略。

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


## 2026-11-12 PR #39 独立验收报告核实与后续修复

### 平台 / Contract 预检查

本轮基线为业务仓 `992c2cb31963001502f499afa2d98ea70ea89974`，实际 origin、工作树、分支、HEAD 与 clean 状态已核实并 fetch；远端默认分支仍为 main。本地 main 落后 origin/main 98 提交，不将其当作本轮起点。`platform-lock.json` 仍锁定中央 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`，Numeric Contract / Profiles / Conformance v1 按该 SHA 读取；当前中央 GUIDE_INDEX 按已验证 origin 的 main `829853a943c421e0b9864d84f3d94970d2ddf688` 读取。适用 MUST 为 Decimal、独立 Profile、全值比较与历史只读；MUST NOT 为无来源区间、隐式修约、显示值回流及重算历史。未发现公共 Contract 冲突，不修改中央 Contract 或锁定基线。本次属于本地保存防御完善（ALLOWED PROJECT DIFFERENCE），不将清理建议冒称已证实 Frozen 违规。相关 Standard Issue 为 ECQ-STD-GB16780-001、003；本次不改变既有软件解释，也未发现应新增登记的标准原文问题。

### 报告建议逐项核实

- P1 的 40% / 95% 探针证明软件执行了配比修正，不能证明违反标准或存在有来源的“表1常见范围”。冻结 V1.2 §8 引用标准 §5.4，明确对高于或低于75%的熟料配比按百分点增减限额；表1给出80/87/94基准限额，没有熟料配比区间。没有依据把40% / 95%称为异常或统一标注“表外外推”。因此本轮不添加无来源的区间和外推警告，也不把该建议登记为已证实标准缺陷。父验收另核对正式标准PDF同一条款。
- “低端完全无防护”的说法不准确：熟料消耗量必须非负、水泥产量必须正数，且消耗量不得超过产量，已有计算配比0～100%的数值域防护。但数值可计算不等于产品满足GB 175要求，也不证明任意配比均符合标准产品适用范围。按产品类型核对GB 175及同一统计期口径的证据需求追加至既有Stage B设计待核证事项；取得依据前不发明跨产品统一合理区间。
- P2-1 成立为死代码清理：新Engine路径直接从数量求g，删除 `input_number` 中仅针对外部g的 `>100` 守卫；真实数量边界继续由 `clinker_ratio` 执行。
- P2-2 采纳报告给出的“至少断言”方案：保留缺省manual用于旧快照反序列化，避免把历史来源改写成automatic。新保存完整性门禁额外要求automatic，适用线的保存g与原始数量重算值相等，且水泥综合能耗trace恰有一个 `P_shx/P_s×100` 步骤，其值为有限Decimal并与计算g一致、单位为%。不符合时抛完整性异常，不写评价或保存审计；历史只读路径跳过新增来源检查，保持三JSON原字节。
- 配比显示位数维持现有策略，本轮未采纳可选的显示位数调整建议。选煤Word跨标准下标外观及水泥原生/Word实开、EXE、安装包仍按原Stage D缺口验收。
- 报告的GitHub 403是审阅者当时环境限制，不能据此断言CI未通过。父任务已通过连接器独立核实992c2cb的严格完整回归、Numeric v1、N01-A三项均success。本轮新提交仍须取得自己的CI证据，旧head成功不代替新head。

### 本轮验证

测试日志使用新文件，未覆盖原PR证据。定向与历史保存验证通过；具体数量和最终代码复验见下方追加。首次扩展命令误写N01-A路径，pytest未收集测试即报路径不存在，原日志保留 `work/pr39-review-followup-final.log`，随后按真实 `tests/pilots/numeric/test_qzc_n01_a.py` 重跑。完整full suite与远端workflow由父任务对稳定提交单次执行；本轮不合并、不发布，不改变生产data、r3候选Rule、Frozen Mapping、PIN、公钥或Schema。


本轮实际结果：

- 水泥core/application/UI/ratio/package sources、历史、科学符号、选煤Word、Frozen Numeric/N01-A：311项通过，exit 0（`work/pr39-review-followup-verified.log` / `.xml`）；随后仅按父审查新增有限Decimal与布尔型trace边界，生产逻辑未再扩展。
- 最终来源门禁及保存/历史回归：61项通过，exit 0（`work/pr39-review-followup-edge-final.log` / `.xml`）。非有限trace首次普通赋值被Pydantic既有校验先行拒绝，原失败证据保留 `work/pr39-review-followup-edge.log`；最终测试明确注入损坏Engine对象验证门禁，未放松模型。最后将布尔用例特化为g=1、trace=True以覆盖数值相等陷阱，并在下一项复验。
- Numeric workflow本地等效专项（Frozen Conformance、N01-A、GB29446、Engine、Excel、UI）及8项最终来源门禁：146项通过，exit 0（`work/pr39-review-followup-numeric.log` / `.xml`）。compileall、公共Engine无全局ROUND6、生产规则显式修约声明检查通过，声明0项（`work/pr39-review-followup-static.log`）。本地等效不冒称远端workflow已执行。
- 父独立探针确认40%及95%配比阈值保持41.50/46.75/52.00与102/110/118；新manual来源被保存门禁拒绝，v1/manual历史读取允许且请求/结果序列化前后不变。远端新head完整full suite及三项CI由父任务追加，不以旧head通过代替。
