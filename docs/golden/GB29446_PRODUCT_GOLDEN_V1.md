# GB29446 Product Golden v1

状态：**ADOPTED (v1)** ｜ 所属阶段：`ECQ-RS04 — GB29446 Product Golden Gate`
相关任务书：`ECQ-RS04`

本文件是 GB 29446—2019《选煤电力消耗限额》参考标准产品级 Golden 的人读说明。
它解释权威来源、案例选择理由、手工推导、冻结边界与更新规则，**不重复 Golden 数据本身**。
机读数据见 [`tests/golden/gb29446_product_golden_v1.json`](../../tests/golden/gb29446_product_golden_v1.json)，
门禁见 [`tests/test_gb29446_product_golden.py`](../../tests/test_gb29446_product_golden.py)。

---

## 1. Golden 权威来源

Golden 的 expected **不是**由当前软件输出反向生成的。每一个 expected 都来自以下三类来源之一，
并在每个 case 中通过 `source_type` / `confirmation_degree` / `source_clause` / `source_table` /
`derivation` / `software_interpretation_ref` 显式登记：

```text
标准原文事实（表1 / 表2 / 式（1） / 附录A 表A.1）
+ 已批准的技术判断
+ 软件实现决定（Numeric Contract v1 / 项目 Numeric Profile）
→ 独立推导 expected
→ Golden fixture
→ 用于验证软件
```

| 权威层 | 内容 | 本 Golden 中的角色 |
|---|---|---|
| 标准原文 | GB 29446—2019《选煤电力消耗限额》正文、表1、表2、式（1）、附录A 表A.1 | 给出 12 个工艺系数 k 与 6 个等级阈值；SHA-256 `72011768…cb15d`（与 Definition 记录一致，本次已实际核对） |
| 已发布 Definition | `data/definitions/gb-29446-2019.json`（`rule_revision=2`） | 标准事实的软件可执行转写；Golden 逐项比对 k 与阈值 |
| Numeric Contract v1 + 项目 Profile | `ECQUOTA_DECIMAL_FULL_VALUE_V1`（full-value exact，无隐式修约） | 决定边界比较语义 |
| Standard Issue | `ECQ-STD-GB29446-001`（`PROVISIONAL`） | 说明“无隐式修约”这一口径的来源与确认程度 |

**判级规则（来自标准原文）**：`e_d = E_d × k ÷ m`（式(1)），等级按表1/表2 的 `≤` 限值逐级判定：

| 煤种 | 1级 | 2级 | 3级 |
|---|---|---|---|
| 炼焦煤（表1） | ≤ 5.0 | ≤ 7.0 | ≤ 8.5 |
| 动力煤（表2） | ≤ 2.0 | ≤ 3.0 | ≤ 4.5 |

超过 3 级上限即不满足最低要求（软件显示口径为“超出3级”，`Grade.NOT_QUALIFIED`）。

---

## 2. 12 个正常案例为什么这样选

任务书要求：附录A 的 **12 个工艺系数每个至少一条**，并整体覆盖两煤种、1/2/3级与超出3级、
**6 个等级 exact threshold**、至少一个 **full-value trap**。

因此正常案例按“**一个系数簇一个案例**”组织，共 12 个系数簇 + 1 个 trap＝**13 个正常案例**：

| # | case_id | 煤种 | 工艺 | k | E_d | m | e_d | 等级 | 关闭什么风险 |
|---|---|---|---|---|---|---|---|---|
| 1 | `…coking-grade1-exact-l1` | 炼焦煤 | 跳汰、浮选联合 | 1.00 | 500 | 100 | **5.0** | 1级 | 炼焦煤 level_1 exact |
| 2 | `…coking-grade2-exact-l2` | 炼焦煤 | 跳汰 | 1.26 | 350 | 63 | **7.0** | 2级 | 炼焦煤 level_2 exact |
| 3 | `…coking-grade3-exact-l3` | 炼焦煤 | 重介 | 1.12 | 212.5 | 28 | **8.5** | 3级 | 炼焦煤 level_3 exact |
| 4 | `…coking-not-qualified-above-l3` | 炼焦煤 | 重介、浮选联合 | 0.83 | 1100 | 100 | 9.13 | 超出3级 | 炼焦煤上限之外 |
| 5 | `…coking-grade2-above-l1` | 炼焦煤 | 重介、跳汰、浮选联合 | 0.78 | 710 | 100 | 5.538 | 2级 | 刚高于 level_1 |
| 6 | `…coking-full-value-trap` | 炼焦煤 | 跳汰、浮选联合 | 1.00 | 500.00004 | 100 | **5.0000004** | 2级 | **无隐式修约**（见 §3） |
| 7 | `…power-grade1-exact-l1` | 动力煤 | 干法选煤 | 1.04 | 125 | 65 | **2.0** | 1级 | 动力煤 level_1 exact |
| 8 | `…power-grade2-exact-l2` | 动力煤 | 跳汰 | 0.94 | 375 | 117.5 | **3.0** | 2级 | 动力煤 level_2 exact |
| 9 | `…power-grade3-exact-l3` | 动力煤 | 跳汰、浮选联合 | 0.80 | 337.5 | 60 | **4.5** | 3级 | 动力煤 level_3 exact |
| 10 | `…power-not-qualified-above-l3` | 动力煤 | 跳汰、重介联合 | 0.85 | 600 | 100 | 5.1 | 超出3级 | 动力煤上限之外 |
| 11 | `…power-grade1-boundary-above-l1` | 动力煤 | 重介 | 0.89 | 400 | 178 | **2.0** | 1级 | 第二个 level_1 边界样本 |
| 12 | `…power-grade3-below-l3` | 动力煤 | 重介、浮选联合 | 0.76 | 440 | 76 | 4.4 | 3级 | 严格低于 level_3 |
| 13 | `…power-grade1-exact-l1-second` | 动力煤 | 重介、跳汰、浮选联合 | 0.72 | 260 | 93.6 | **2.0** | 1级 | 最后一个系数 |

**为什么是 13 而不是 12**：12 个系数簇已满足“每个系数至少一条”。第 13 个（#6）是
**full-value trap**，它使用非阈值精确值 `500.00004 × 1.00 ÷ 100 = 5.0000004`。
**13 不是数学上的最小案例数**：trap 完全可以与另一个系数案例（例如 #2 跳汰）合并为
“同一系数、两个 E_d 输入”的形式，从而压到 12 个案例。本 Golden 选择独立成例，是因为
trap 的 `source_type` 是 `技术判断`（依赖 `ECQ-STD-GB29446-001` 口径），而 12 个系数簇
都是 `标准原文事实` —— 把两类依据不同的期望放在同一个案例里会削弱来源可追溯性。
这是**可读性与证据分离**的取舍，不是覆盖能力的下限。门禁同时断言“13 个正常案例”
与“12 个系数簇”，因此压缩案例数会被立即发现。

**m 不统一为 100**：实际使用 100 / 63 / 28 / 100 / 100 / 100 / 65 / 117.5 / 60 / 100 / 178 / 76 / 93.6。

---

## 3. expected 如何手算

所有案例都刻意选成**有限位且可精确表达**的 Decimal 运算，便于人工复核。示例：

```text
#1  e_d = 500      × 1.00 ÷ 100   = 5.0        → 5.0 ≤ 5.0  → 1级
#2  e_d = 350      × 1.26 ÷ 63    = 441 ÷ 63 = 7.0      → 5.0 < 7.0 ≤ 7.0  → 2级
#3  e_d = 212.5    × 1.12 ÷ 28    = 238 ÷ 28 = 8.5      → 7.0 < 8.5 ≤ 8.5  → 3级
#7  e_d = 125      × 1.04 ÷ 65    = 130 ÷ 65 = 2.0      → 2.0 ≤ 2.0  → 1级
#13 e_d = 260      × 0.72 ÷ 93.6  = 187.2 ÷ 93.6 = 2.0  → 2.0 ≤ 2.0  → 1级
```

**full-value trap（#6）**：

```text
e_d = 500.00004 × 1.00 ÷ 100 = 5.0000004
表1 1级为 ≤ 5.0；5.0000004 > 5.0，因此不得判 1级
5.0 < 5.0000004 ≤ 7.0  → 2级
```

若在比较前执行六位小数 `ROUND_HALF_UP`，`5.0000004` 会被抹平为 `5.000000` 而**误判 1级**。
该案例正是用来冻结这一差异。其来源类型登记为 `技术判断`，因为它依赖的不是标准明文，
而是 `ECQ-STD-GB29446-001` 记录的口径。

**独立复核机制**：门禁中的 `independently_derive()` 从 Definition 的 表A.1 系数与表1/表2 阈值
重新计算 e_d 与等级，**不使用软件输出**，并与 Golden 声明的 expected 逐例比对
（`test_expected_values_are_independently_derivable`）。该机制在本次建立过程中实际发现并纠正了
一个手工推导错误（原 `…power-grade3-below-l3` 写为 `600×0.76÷100=4.56` 却期望 3级；
4.56 > 4.5 应为超出3级，已改为 `440×0.76÷76=4.4`）。**这是 Golden 推导错误，不是软件缺陷**，
因此只修改 Golden，未改动任何生产代码。

---

## 4. 冻结什么

比较使用**明确的白名单业务投影**（`business_projection()`），**不是**
`result.model_dump_json() == expected`。冻结项：

| 类别 | 冻结内容 |
|---|---|
| 标准身份 | `standard_id` / `standard_number` / `standard_version` / `rule_revision` / `numeric_profile_id` / `numeric_contract_version` |
| 产品与选择 | `product_id`（煤种）、`process`（选煤工艺）、`indicator_id`（指标身份） |
| 输入 | `e_d_input`（E_d 原 lexical 文本）、`m_input` |
| 计算 | `k`（表A.1 系数）、`actual_value`（精确 e_d） |
| 阈值 | `base_thresholds` 与 `corrected_thresholds`（LEVEL_1/2/3，且必须等于**该煤种自己的**阈值） |
| 结论 | `grade`、`unit` |
| 依据 | 相关 `source_reference` 的**完整精确集合**（标准号 / clause / table），逐条相等，不只是“存在某类来源” |
| 正常案例 | `warnings_empty == True` |
| 业务 trace 不变量 | `has_grade_comparison == True`；`has_explicit_rounding_step == False`；trace 中无 `round_places` 声明 |

**来源冻结是逐条精确比较**：每个案例在 Golden 中登记 `expected_sources`（该煤种对应的
完整 clause/table 集合）与 `expected_indicator_id`，由
[`test_expected_sources_match_the_definition`](../../tests/test_gb29446_product_golden.py)
核对 Golden 与 Definition 一致，并由
[`test_expected_sources_match_the_definition`](../../tests/test_gb29446_product_golden.py)
保证炼焦煤不得引用 表2、动力煤不得引用 表1。

> 早期版本只断言“存在 GB 29446 标准号 + 存在任意 表1/表2 + 存在 表A.1”，
> 因此把炼焦煤来源改成**错误条款 + 动力煤表2**仍能通过。该缺陷已修复：
> 现在比较的是**精确来源集合**，且 `indicator_id`、冻结输入 lexical 值、
> `standard_number` 均参与比较。

## 5. 明确不冻结什么

`evaluation_id`、`evaluated_at`、SQLite row id、绝对路径、来源 `page`、JSON key 顺序、
`rule_snapshot_sha256`、整份 Definition SHA、完整 `calculation_trace` 文本、
warning 完整中文文案、UI 标点与几何、`calculator_version`、`numeric_behavior_version`、
Python 版本、依赖锁哈希。

环境信息（`calculator_version` / `numeric_behavior_version` / Python 版本 / `requirements.lock` 哈希）
**只用于诊断**；它们变化**不得**自动跳过 Golden —— Golden 的目的之一正是验证新 Calculator /
新依赖环境是否保持相同业务语义。

---

## 6. Business Data Summary（业务事实漂移探测）

Golden 内含 `business_data_summary`：12 个 k、6 个等级阈值、关键 clause 与 table 集合。
门禁将其与当前 Definition 逐项比对（`test_business_data_summary_matches_definition`），
用于发现**业务事实漂移**。

刻意**不**使用“整份 Definition hash”作为业务 Golden：哈希会因为注释、排版或无关字段变化而失效，
却无法说明**哪一个业务事实**发生了变化。

---

## 7. Standard Issue 的角色

`ECQ-STD-GB29446-001`（**仍为 `PROVISIONAL`**）记录“正式比较中历史 ROUND6 缺少标准依据”。

- 本 Golden **不关闭**该问题，**不**把它写成官方解释；
- 本 Golden 只把当前软件口径（full-value exact，无隐式修约）冻结为 **可回归的产品证据**；
- trap 案例的 `confirmation_degree` 明确写有“**无发布机构正式解释**”，并由
  `test_golden_does_not_claim_official_interpretation` 守护；
- 若未来取得标准原文定位或发布机构解释，应重新评估该 Issue 与本 Golden 的 trap 案例。

**Applicability Gate**：Golden 加载时先核对 `standard_id` / `standard_version` /
`standard_source_sha256` / `rule_revision` / `numeric_profile_id` /
`ECQ-STD-GB29446-001` 当前 status。任一变化时**不报告普通业务 regression**，
而是明确报告“**Golden 上游依据已变化，需要重新复核/批准**”。

---

## 8. 安全语义案例

只冻结“**不得产生 1级 / 2级 / 3级 / 超出3级**”，**不**冻结是否保存为 INCOMPLETE Record：

| case | 输入 | 冻结 |
|---|---|---|
| `…safety-missing-ed` | E_d 缺失 | 等级只能是 `INCOMPLETE` / `NOT_APPLICABLE` |
| `…safety-zero-ed` | E_d = 0 | 同上 |

**Excel 安全语义**（`…excel-authoritative-ingress`）：XLSX numeric cell（int/float）与 Excel 公式
（含 cached value）**不得**成为 GB29446 authoritative Decimal 输入；只有十进制文本单元格可接受。
这是本仓 RS03 的入口契约，**不代表**中央 lossless XLSX 公共方案已冻结（`D-ECQ-006` 仍 OPEN）。

**明确不冻结**：“煤种 + 不兼容工艺”究竟归类为哪一种 INCOMPLETE/error。
该语义继续由 RS01 linkage Gate 保护，不在本 Golden 中固化为公共语义。

---

## 9. 四类 Gate

| Gate | 内容 | 实现 |
|---|---|---|
| **A — Business Golden** | 全部正常案例 + 安全案例：Golden 输入 → 正式 Application/Engine → 白名单投影 → expected | `test_gate_a_business_golden`、`test_gate_a_safety_semantics` |
| **B — Product Lifecycle** | 正常案例正式评价 → Record → **真实独立进程重启** → history；恢复出的记录使用**与 Gate A 完全相同的完整白名单业务投影**核对；`engine_calls == 0` | `test_gate_b_product_lifecycle_real_restart` |
| **B′ — 损坏可检出** | 在真实 SQLite 中把已保存 `result_json` 改成错误标准号 / 错误 `standard_id` / 错误 `rule_revision` / 错误 Numeric Profile / 单位 `kg/t` / 阈值全 `999` / 来源清空 / 无关指标身份 / 错误等级 / 错误 actual / 错误 k，逐一证明 Gate B **必须失败** | `test_gate_b_detects_corrupted_saved_business_data` |
| **C — Excel Golden** | 一个普通案例 + 一个 full-value boundary 案例；GUI Request == Excel Request；两条路径的 Result 业务投影均等于 Golden | `test_gate_c_excel_golden`、`test_gate_c_excel_request_equals_gui_form_request`、`test_gate_c_excel_ingress_safety` |
| **D — Regression** | RS01 / RS02 / RS03 Gate、GB29446、N01-A、Frozen Numeric v1、Generic Excel、Architecture、Document hygiene、literal full suite | 由测试命令单独执行；Golden **不替代**既有 Gate |

**Gate C 关于两个可选产品级输入的说明**：GB29446 Excel 模板按设计只暴露 9 个用户字段
（企业名称 / 评价日期 / 核算周期 / 自定义周期 / 煤种 / 选煤工艺 / E_d / m / 备注），
不含 `single_coal_single_process` 与 `enterprise_status`。其中：

- `single_coal_single_process`：引擎对 GB29446 **显式豁免**，不参与校验，**不改变**业务结果；
- `enterprise_status`：只驱动“限定值 / 准入值”合规结论；该结论在 DETAIL 模式下为 `None`，
  且本 Golden **刻意不冻结**企业属性合规语义（RS01/RS02 负责）。

因此 Gate C 用“模板实际可承载的业务输入”构造对照请求，并额外用
`test_gate_c_excel_request_equals_gui_form_request` 显式证明：带与不带这两个可选输入时，
**业务投影完全相同**。

---

## 10. Golden 更新规则

1. Golden `expected` 一旦变化，`golden_version` **必须递增**；
2. 必须记录 `approval_basis`；
3. 必须同步更新 `derivation` 与证据；
4. **Golden expected 的修改必须与生产代码修改分开 commit**；
5. 本次为 v1 首次建立，因此 Golden JSON + Golden Gate + 本文件作为**同一个 Golden adoption commit**；
6. 若执行中发现生产代码 bug：**不得**通过同时修改代码与 expected 来让 Gate 变绿，
   必须先判定属于“软件错误 / Golden 推导错误 / 证据不足”。

---

## 11. 未覆盖范围与已知风险

### 11.1 Product Golden v1 **不**证明

- Windows 10/11 实机通过；
- 高 DPI 显示；
- installer / portable 交付物；
- 安装 / 升级 / 卸载；
- corrupted-row resilience 已解决；
- 中央 XLSX Contract 已冻结；
- Standard Issue 已获官方解释；
- 其余 46 个标准达到同等成熟度。

`READY FOR RS05 WINDOWS ACCEPTANCE` **不等于“可发布”**；Windows 正式交付证据尚未建立。

### 11.2 corrupted historical row 爆炸半径（登记为 RS05 Release Gate）

RS04 **不修复**、**不修改 repository**，仅记录事实：

- `SqlEvaluationRepository.list_recent()` 逐行执行
  `EvaluationResult.model_validate_json(row.result_json)` 且**无异常隔离**
  （`src/uebench/infrastructure/repositories.py:293`）；
- 因此**单条无法反序列化的 `result_json` 会中断整个 `list_recent()`**，
  进而使 `ApplicationFacade.list_recent_evaluations()`、UI 的“评价记录”页与首页最近记录
  一并失败；
- `get(evaluation_id)` 同样直接反序列化 `request_json` / `result_json` /
  `rule_snapshot_json`（同文件 271–280 行），单条损坏记录只影响该记录本身，
  但**没有**面向用户的损坏提示。

**分类**：`LOCAL DEFECT`（本仓 infrastructure），**不是**本 Golden Adoption 的 blocker。
**处置**：登记为 **RS05 Release Gate**，须在 Windows 正式交付前处理。

### 11.3 其他未覆盖

- RS02 deferred 的历史列表 `result_json` 性能优化未处理；
- `data/catalog.json` 中 `gb-29435-2025` 的 `lifecycle_status` 与定义文件不一致仍只登记未修；
- 本 Golden 不覆盖批量 / 多企业 / 多 workbook 场景（RS03 明确一个 workbook = 一次评价）。

---

## 12. 结论

```text
GB29446 Product Golden = ADOPTED (v1)
Reference Standard 产品证据 = READY FOR RS05 WINDOWS ACCEPTANCE

RS01 = DONE   RS02 = DONE   RS03 = DONE   RS04 = DONE
Reference Standard Product Closure = PARTIAL
RS05 = NOT STARTED   RS06 = NOT STARTED
```

`READY FOR RS05 WINDOWS ACCEPTANCE` 不等于“可发布”。

---

## 13. R1 返工记录（独立验收后）

独立验收判定 **FAIL — REWORK REQUIRED**，提出两个 blocker，均成立并已修复。
两个 blocker 都属于本仓 **LOCAL DEFECT（验收门禁缺陷）**：不改生产代码、
不改标准解释、不需要修改中央 Contract。

### Blocker 1 — Gate A 未保护声明的完整业务白名单

**问题**：断言只检查“存在标准号 + 存在任意 表1/表2 + 存在 表A.1”，
没有核对正确条款与煤种对应表。独立故障注入实证三处漏检：

| 注入 | 修复前 |
|---|---|
| 炼焦煤来源改为**错误条款（3.2）+ 动力煤表2** | 仍通过 |
| 指标身份改为无关指标 | 仍通过 |
| 声明冻结的输入 lexical 值改错 | 仍通过 |

**修复**：为每个正常案例登记从 Definition 推导的 `expected_sources`
（该煤种完整 clause/table 集合）与 `expected_indicator_id`，
`assert_matches_golden()` 现在逐条精确比较：

- 完整来源集合（标准号 + clause + table），逐条相等；
- `standard_number`（此前完全未断言）；
- `indicator_id`（指标身份）；
- `e_d_input` / `m_input`（冻结的 lexical 输入）；
- `base_thresholds` **与** `corrected_thresholds`，且必须等于该煤种自己的阈值。

新增守护测试：`test_expected_sources_match_the_definition`（Golden 与 Definition 一致、
炼焦煤不得引用表2、动力煤不得引用表1）、
`test_case_source_clause_and_table_agree_with_expected_sources`、
`test_expected_indicator_id_matches_definition`。

**复验**：三类注入现在全部被捕获（来源依据不符 / 指标身份不符 / E_d 输入不符）。

### Blocker 2 — Gate B 未证明历史业务投影等于 Golden

**问题**：真实重启测试只比较等级、actual、k 与部分版本、trace 标记。
独立验收在真实 SQLite 中于重启前把已保存结果改成
错误标准号 / 单位 `kg/t` / 阈值全 `999` / 来源引用清空，**Gate B 仍通过**。

**修复**：

- 重启探针改为返回**完整恢复投影**（顶层身份 + 冻结输入 + `indicator_id` /
  `actual_value` / `unit` / `k` / `base_thresholds` / `corrected_thresholds` /
  `grade` / `warnings_empty` / 精确来源集合）；
- Gate B 通过 `assert_projection_matches_golden()` 复用**与 Gate A 相同的**
  `assert_matches_golden()`，两条路径不再各自维护一份弱断言；
- 新增 `test_gate_b_detects_corrupted_saved_business_data`：在真实 SQLite 中注入
  11 种业务损坏（含错误标准号、`standard_id`、`rule_revision`、Numeric Profile、
  单位、阈值、来源清空、指标身份、等级、actual、k），逐一证明 Gate B **必须失败**。

### 其他更正

- **CI 修复（cp1252 控制台）**：新增的重启探针把中文条款字符串打印到 stdout，
  而 GitHub Windows runner 的控制台是 cp1252，探针因
  `UnicodeEncodeError: 'charmap' codec can't encode characters in position 467-468`
  退出 1，使 Gate B 只在 CI 失败（本地 UTF-8 控制台不失败）。同一失败模式 RS03 的
  ingress probe 已遇到过一次。修复：探针显式
  `sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")`（stderr 同理），
  并新增 `test_gate_b_probe_survives_a_cp1252_console` 在 `PYTHONIOENCODING=cp1252`
  与 `utf-8` 两种控制台下各跑一次探针。**已实证**：去掉 reconfigure 的探针在 cp1252 下
  `rc=1` 并复现同一条 UnicodeEncodeError；修复版 `rc=0` 且恢复出 `LEVEL_2`。
- 撤回“13 是数学上的最小案例数”的说法；13 是可读性与证据分离的取舍（见 §2）；
- `HANDOFF.md` 中遗留的“本任务停在 RS03，未开始 RS04”已更正为停在 RS04；
- 全文测试计数改为如实区分 passed / xfailed，不再把两者相加后混称。

### R1 后测试

```text
tests/test_gb29446_product_golden.py -q -ra    36 passed

literal full suite -q -ra
  tests = 560   passed = 556   xfailed = 4   failed = 0   errors = 0   exit = 0
```

R1 之前（即本次验收的 final head `2781696`）：`tests = 555`、`passed = 551`、
`xfailed = 4`。**该 head 的完成报告把“总数 555”写成了“passed 555”**，与独立验收
实测的 `551 passed` 不一致；正确写法是 `551 passed, 4 xfailed`（合计 555）。本次已更正，
全文不再把 xfailed 计入 passed。
