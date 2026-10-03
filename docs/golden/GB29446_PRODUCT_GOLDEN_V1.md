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
**full-value trap**，它必须使用非阈值精确值 `500.00004 × 1.00 ÷ 100 = 5.0000004`，
在数学上不可能与任何一个 exact-threshold 案例合并，因此 13 是满足任务书**全部**覆盖要求的
最小案例数。门禁 `test_normal_case_count_is_twelve_coefficient_clusters_plus_trap`
同时断言“13 个正常案例”与“12 个系数簇”。

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
| 标准身份 | `standard_id` / `standard_version` / `rule_revision` / `numeric_profile_id` / `numeric_contract_version` |
| 产品与选择 | `product_id`（煤种）、`process`（选煤工艺） |
| 输入 | `e_d_input`（E_d 原 lexical 文本）、`m_input` |
| 计算 | `k`（表A.1 系数）、`actual_value`（精确 e_d） |
| 阈值 | `corrected_thresholds`（LEVEL_1/2/3） |
| 结论 | `grade` |
| 依据 | 相关 `source_reference` 的 标准号 / clause / table |
| 正常案例 | `warnings_empty == True` |
| 业务 trace 不变量 | `has_grade_comparison == True`；`has_explicit_rounding_step == False`；trace 中无 `round_places` 声明 |

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
| **B — Product Lifecycle** | 正常案例正式评价 → Record → **真实独立进程重启** → history；保存后业务投影仍等于 Golden；查看历史不得重跑 Engine（`engine_calls == 0`） | `test_gate_b_product_lifecycle_real_restart` |
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
