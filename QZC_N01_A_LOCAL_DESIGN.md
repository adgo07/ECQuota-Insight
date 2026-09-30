# QZC-N01-A — ECQuota Exact Decimal / Rounding Pilot 设计

状态：**DESIGN ONLY / NOT EXECUTED**  
Pilot ID：`N01-A`  
Repository：`adgo07/ECQuota-Insight`  
Representative standard：`GB 29446—2019 选煤电力消耗限额`  
Module ID：`qz.energy_quota`

> 本文件只做静态设计与证据整理。不得据此声称已迁移 Numeric 语义、已删除 ROUND6、已完成真实数值重算或已通过 Gate 1。

---

## 1. Baseline 与权威层级

### 1.1 ECQuota Design baseline

- default branch：`main`
- Design baseline SHA：`74b3deccfe74559cd08cc16a0705f1589ea6ecdc`
- 当前业务仓 `platform-lock.json` 锁定 Contract baseline SHA：`0cd74d783fa23add6dc881b408a8c8ba8503f8e8`
- 本设计不修改 `platform-lock.json`

### 1.2 Central Numeric Pilot baseline

中央仓：`adgo07/Qingzhou-contracts`

本设计读取：

- `docs/architecture/ARCHITECTURE_V2.1_FROZEN.md`
- `contracts/numeric/NUMERIC_CONTRACT_V1_DRAFT.md`
- `DECISIONS_NEEDED.md`
- `pilots/numeric/QZC_N01_MASTER_PLAN.md`
- `pilots/numeric/N01_A_ECQUOTA_DISTRIBUTION.md`
- `pilots/numeric/N01_PILOT_RETURN_TEMPLATE.md`

说明：任务文字中的 `contracts/numeric/NUMERIC_CONTRACT_DRAFT.md` 在中央仓不存在；实际文件名为 `NUMERIC_CONTRACT_V1_DRAFT.md`。本设计按实际文件读取，不创建别名、不修改中央仓。

中央 N01 分发已核实：

- Contract baseline tag：`contracts-v0.1.0`
- Contract baseline SHA：`0cd74d783fa23add6dc881b408a8c8ba8503f8e8`
- N01-A 分发时 ECQuota head：`74b3deccfe74559cd08cc16a0705f1589ea6ecdc`
- Gate 0：PASS

本 Pilot 只提出 candidate evidence，不自行冻结 Numeric Contract v1。

### 1.3 标准原文证据

ECQuota canonical：`data/definitions/gb-29446-2019.json`

当前定义记录：

- standard：GB 29446—2019
- source file：`28.GB 29446-2019选煤电力消耗限额.pdf`
- source SHA-256：`72011768d81cc35db8e53f6470fadc3b14140b61bd4f9ee3546a3e225e9cb15d`
- rule revision：2

本次设计已取得并检查与该文件名对应的 5 页标准原文。标准正文包括：

- 第 3 页表 1：炼焦煤 `1级≤5.0 / 2级≤7.0 / 3级≤8.5 kW·h/t`；
- 第 3 页表 2：动力煤 `1级≤2.0 / 2级≤3.0 / 3级≤4.5 kW·h/t`；
- 第 4 页 5.2 式（1）：`e_d = E_d × k / m`；
- 第 5 页附录 A 表 A.1：选煤工艺折算系数 `k`。

对完整 PDF 检索“修约”“四舍五入”“小数”“保留”“精确”，均未发现匹配；逐页阅读也未发现要求在等级比较前执行 ROUND6、指定 `ROUND_HALF_UP`、或要求把最终 `e_d` 先保留固定小数位再比较的条款。

**本设计结论：在 GB 29446—2019 原文中未发现 ROUND6 / ROUND_HALF_UP 的标准依据。**

这不等于平台永久禁止所有 rounding；如果未来其他标准原文明文要求修约，仍应作为 `explicit_round` 单独表达。

---

## 2. 当前 Numeric 正式链路

GB 29446 当前真实 UI 路径不是“用户直接输入一个已算好的 e_d”，而是专用页面采集：

```text
QLineEdit 文本
  E_d（kW·h）
  m（t）
+ 煤种
+ 选煤工艺
        ↓
_collect_gb29446_request()
        ↓
InputValue（字符串数值）
EvaluationRequest（DETAIL）
        ↓
Application evaluate / preview
        ↓
EvaluationEngine._validate_inputs()
        ↓
parse_decimal()
        ↓
Decimal
        ↓
Canonical Rule
  lookup k
  e_d = E_d × k / m
        ↓
ExpressionEvaluator
  Decimal multiply/divide
  中间计算保持 Decimal 精度
        ↓
actual Decimal
        ↓
threshold expressions → Decimal
        ↓
EvaluationEngine._grade()
        ↓
actual 与 threshold 各自 ROUND(..., 6)
ROUND_HALF_UP
        ↓
<= 等级比较
        ↓
Grade
        ↓
IndicatorResult / EvaluationResult / trace
        ↓
UI 读取 Engine 的 actual + Grade
        ↓
结果显示通常 2 位
说明显示最多约 8 位
```

### 2.1 当前链路中哪些值是权威值

- 输入：`InputValue` 最终进入 Domain 时转换为 `Decimal`；
- 公式：`ExpressionEvaluator` 使用 Decimal；
- `actual_value`：保留公式实际 Decimal 结果；
- thresholds：Canonical rule 中的 Decimal；
- **当前正式 comparison value**：并不是 raw actual，而是 `_round_threshold_value(actual)` 和 `_round_threshold_value(threshold)`；
- grade：基于上述 ROUND6 comparison value；
- display value：UI 格式化字符串，不是等级判定输入。

### 2.2 当前 binary float 情况

Domain 模型显式拒绝 Python `float` 作为正式 InputValue/Canonical numeric truth，核心 Engine 使用 Decimal。

但通用 Excel 导入适配器存在独立风险：openpyxl 读取数值单元格时可能产生 Python float，`_excel_value()` 再将其 `str(...)`，随后解析为 Decimal。该路径不属于 GB 29446 专用 UI 的主 Pilot 链路，但它说明“Domain 拒绝 float”不等于“所有 ingress 从未经过 binary float”。

N01-A 必须记录该事实，但本 Pilot 的最小执行不应因此重写 Excel 导入系统。

---

## 3. ROUND / ROUND6 / ROUND_HALF_UP 实际清单

### 3.1 正式等级比较：进入正式业务判定

文件：`src/uebench/domain/engine.py`

当前存在：

```text
_THRESHOLD_COMPARISON_QUANTUM = Decimal("0.000001")
_round_threshold_value(value)
```

其实现使用：

```text
Decimal.quantize(0.000001, rounding=ROUND_HALF_UP)
```

`EvaluationEngine._grade()` 会：

1. 对 actual 执行 `_round_threshold_value()`；
2. 对 LEVEL_1 / LEVEL_2 / LEVEL_3 threshold 执行同样 ROUND6；
3. 再执行 `<=` 或 `>=`；
4. 结果直接决定正式 `Grade`。

因此：**ROUND6 当前明确进入正式等级判定。**

### 3.2 Compliance：进入正式合规比较，但 GB 29446 当前专用路径跳过

同一文件中 compliance 判定也对 actual / compliance limit 做 ROUND6 后比较。

GB 29446 当前专用逻辑不生成该 compliance 主结论，因此它不是代表标准当前等级结果的决定路径；但它仍是 ECQuota 公共 Engine 中的 implicit ROUND6 使用点。

### 3.3 Condition / range：当前反而是 full-value Decimal

`ConditionEvaluator` 当前：

- numeric `eq`：Decimal exact equality；
- `lt/lte/gt/gte`：直接 Decimal 比较；
- `range`：直接 Decimal 比较。

因此当前软件内部已经存在两套 Numeric 语义：

```text
condition / range / piecewise / lookup conditions → full-value Decimal
final grade / compliance                         → implicit ROUND6
```

这既不完全符合当前《统一判定规范》声称的“所有边界统一 ROUND6”，也不完全符合中央 candidate 的 full-value 默认语义。

### 3.4 Expression.round_places：显式公式修约能力，不等于全局 ROUND6

模型 `Expression` 已有：

```text
round_places: int | None
```

`ExpressionEvaluator` 在该字段存在时使用 `ROUND_HALF_UP` 对表达式结果做 quantize，且修约后的结果可继续参与后续正式计算。

这是**显式公式修约能力**，语义上必须与全局 `_round_threshold_value()` 分开看。

问题在于当前 schema 只记录 `round_places`，没有显式记录：

- rounding mode；
- stage；
- purpose；
- source/provenance；
- 是 calculation normalization 还是 comparison rounding。

GB 29446 当前 canonical 中**没有** `round_places`，因此该能力不构成本代表标准 ROUND6 的依据。

### 3.5 display_places：仅显示

GB 29446 canonical 的两个 indicator 都有：

```text
display_places = 2
```

专用 UI 中：

- `_format_result_number()` 默认格式化为 2 位；
- `_format_explanation_number()` 最多展示约 8 位并去掉尾零；
- grade 直接使用 Engine 返回的 `item.grade`，没有根据显示值重新判级。

因此这些 round/format 属于 **display-only**，不应升级为 comparison rule。

---

## 4. ROUND_HALF_UP 的性质判断

### 4.1 GB 29446 标准要求？

**否。当前核验未发现。**

标准只规定公式、阈值、折算系数和 `≤` 关系，没有规定六位小数修约，也没有指定 HALF_UP。

### 4.2 当前 ECQuota 正式业务规则？

**是，但来源是项目现行治理/历史实现，而不是标准原文。**

`docs/统一判定规范.md` 当前明确要求：

- 所有数值边界两侧先 ROUND6；
- 使用 Decimal + ROUND_HALF_UP；
- 设计理由包含与 Excel ROUND 一致。

因此在当前软件基线下，它是“现行项目规则”；N01-A 不能假装它不存在，也不能在 Design 阶段直接删除。

### 4.3 平台公共规则？

**不能由 N01-A 单方面冻结。**

中央 N01 分发明确禁止从一个业务 Pilot 推导“所有青舟项目都必须使用 ROUND_HALF_UP”。

N01-A 可以提供证据支持：

- 默认 exact/full-value comparison candidate；
- explicit rounding 必须带来源/阶段/rounding mode candidate；

但平台最终冻结要等 Gate 4/5。

---

## 5. T-δ / T / T+δ 行为分析

### 5.1 选择 δ

主差异向量使用：

```text
δ = 0.0000004
```

因为它满足：

```text
ROUND_HALF_UP(T + 0.0000004, 6) == T
但
T + 0.0000004 > T
```

同时建议补充：

```text
0.0000001
0.0000004
0.0000005
0.0000006
```

用来完整展示六位 HALF_UP 的临界转换。

### 5.2 对 GB 29446 `<=` 阈值的通用结论

| Exact actual | 当前 implicit ROUND6 | full-value candidate | 是否可能改变等级 |
|---|---|---|---|
| `T-δ` | `< = T` | `< T` | 否 |
| `T` | `=T` | `=T` | 否 |
| `T+0.0000001` | ROUND 后 `=T` | `>T` | 是 |
| `T+0.0000004` | ROUND 后 `=T` | `>T` | 是 |
| `T+0.0000005` | ROUND 后 `>T` | `>T` | 通常否 |
| `T+0.0000006` | ROUND 后 `>T` | `>T` | 否 |

### 5.3 六个正式阈值的 expected changed behavior

使用 `δ=0.0000004`：

| 煤种 | T | Current ROUND6 | full-value candidate |
|---|---:|---|---|
| 炼焦煤 | 5.0 | `5.0000004 → 1级` | `→ 2级` |
| 炼焦煤 | 7.0 | `7.0000004 → 2级` | `→ 3级` |
| 炼焦煤 | 8.5 | `8.5000004 → 3级` | `→ 未达标` |
| 动力煤 | 2.0 | `2.0000004 → 1级` | `→ 2级` |
| 动力煤 | 3.0 | `3.0000004 → 2级` | `→ 3级` |
| 动力煤 | 4.5 | `4.5000004 → 3级` | `→ 未达标` |

当前 `tests/test_gb29446.py` 已明确把部分旧语义锁为测试预期，例如：

```text
5.0000004 → LEVEL_1
5.0000005 → LEVEL_2
8.5000004 → LEVEL_3
8.5000005 → NOT_QUALIFIED
```

因此如果未来迁移到 full-value，这些不是“测试坏了”，而是**预期需要重新审批的 breaking numeric behavior**。

---

## 6. 多步公式近边界证据

Pilot 不能只用“直接拿 actual 与 T 比”的人工数值，还必须证明公式链不会因为显示或中间转换把差异吃掉。

GB 29446 可用标准真实公式构造：

```text
炼焦煤
工艺：跳汰、浮选联合
k = 1.00
m = 10 t
E_d = 50.000004 kW·h

exact:
e_d = 50.000004 × 1.00 / 10
    = 5.0000004 kW·h/t
```

预期：

```text
current Engine ROUND6 → 1级
full-value candidate  → 2级
UI display(2 places)  → 5.00
```

这是 N01-A 最重要的完整 trace vector：

```text
raw input
→ exact Decimal formula
→ calculation value 5.0000004
→ current comparison value 5.000000
→ candidate comparison value 5.0000004
→ display value 5.00
→ current grade 1级
→ candidate grade 2级
```

它直接证明：**display value 与 comparison value 必须分离。**

---

## 7. 当前问题清单

### P1 — 标准未要求 ROUND6，但正式 grade 使用全局 ROUND6

影响：极窄边界区间的等级可与 full-value 不同。

### P2 — 当前项目内部 Numeric 语义不一致

- Condition/range：full-value Decimal；
- Grade/compliance：ROUND6；
- 文档却声称所有边界统一 ROUND6。

### P3 — ROUND_HALF_UP 被硬编码成全局阈值行为

它有当前项目治理依据，但没有 GB 29446 标准依据，也不能直接升级为平台公共规则。

### P4 — Explicit rounding schema 信息不足

`Expression.round_places` 只有位数，没有 mode/stage/purpose/source，无法完整满足中央 DRAFT 对可审计 explicit rounding 的候选要求。

### P5 — 旧专项测试固化了 implicit ROUND6

测试需要在 Pilot 中被当作“current behavior evidence”，而不是直接删除或改成新值。

### P6 — 显示值可能掩盖 exact 越界

例如 `5.0000004` 页面结果可显示 `5.00`，但 full-value candidate 已经越过 5.0。等级不能从显示字符串倒推。

### P7 — Excel ingress 存在 binary float 边界风险

通用 Excel 适配器可能先得到 Python float，再 `str` → Decimal。代表标准专用 UI 主链没有这个问题，但全产品 Numeric conformance 后续必须处理或明确 ingress contract。

### P8 — RULE_ENGINE_VERSION 当前为 `1.0`

若将来真正修改生产比较语义，这是可观测业务行为变化，必须设计版本/历史兼容策略；但 N01-A Pilot evidence 阶段不应因为试验先修改生产版本。

### P9 — 当前 Result 记录没有把 Numeric Contract / engine version 作为完整公共 envelope

历史结果保存本身不会自动重算，已有 rule snapshot/hash；但未来迁移时仍应确保可以追溯“结果使用了哪一种 comparison semantics”。该问题属于后续 Result/Contract 演进，不应扩大 N01-A 为数据库迁移。

---

## 8. Pilot 的最小实现原则

### 8.1 核心决定

**N01-A Execution 不直接迁移生产算法。**

本 Pilot 的最小实现应采用：

> current Engine + candidate full-value comparator 的旁路 A/B evidence harness。

即：

```text
同一 exact Decimal vector
        ├─→ 当前真实 EvaluationEngine → current result
        └─→ Pilot-only exact comparator → candidate result

输出：current / candidate / delta / provenance
```

这样可以真实验证差异，同时不把中央 DRAFT 提前变成生产规则。

### 8.2 Pilot Execution 原则上不修改

- `src/uebench/domain/engine.py`
- `src/uebench/domain/models.py`
- `data/definitions/gb-29446-2019.json`
- UI
- DB/migrations
- package schema
- `RULE_ENGINE_VERSION`

### 8.3 Pilot 可新增的最小资产

建议：

```text
tests/pilots/numeric/
  test_qzc_n01_a_ecquota.py
  qzc_n01_a_vectors.json

docs/governance/
  QZC_N01_A_EXECUTION_REPORT.md   # Execution 阶段才创建
```

也可复用仓库现有 tests/fixtures 结构，但必须保证：

- vector 与 test driver 分离；
- JSON 数字使用字符串；
- candidate comparator 只存在于 Pilot/test scope；
- 不被生产 Application/Engine import。

### 8.4 为什么不先重构 NumericComparisonPolicy

中央 Numeric Contract 仍是 DRAFT，D-004/D-012 仍 OPEN；本 Pilot 目标是获得证据，不是提前设计公共库。

现在抽大型 `NumericComparisonPolicy`、重写 Engine、改所有标准，会把“Pilot”变成“迁移”，违反最小范围原则。

---

## 9. Proposed tests

### 9.1 Current behavior preservation tests

Execution 期间现有测试不得为了 full-value candidate 被直接改写。

继续运行：

```text
tests/test_gb29446.py
tests/test_engine.py
全量 pytest
```

目的：证明 Pilot evidence 没有改变生产行为。

### 9.2 Pilot A/B tests

新增 Pilot-only tests：

1. current Engine 对同一 vector 的真实输出；
2. candidate full-value comparator 输出；
3. vector 声明两者是否应相同/不同；
4. 差异必须与 expected delta 完全一致；
5. 不允许用 float 构造 vector。

### 9.3 Exact Decimal parse tests

至少：

```text
"5"
"5.0"
"5.000000"
"5.0000004"
"5E+0"
```

进入 Decimal 后 exact equality/ordering 可审计。

### 9.4 T-δ/T/T+δ

六个正式 threshold 全部覆盖：

- `T - 0.0000004`
- `T`
- `T + 0.0000004`

并至少选一个 threshold 加：

- `T + 0.0000001`
- `T + 0.0000005`
- `T + 0.0000006`

### 9.5 Multi-step formula

至少一个 `E_d × k / m` 产生 `T+δ` 的案例，不能只测试直接 comparison helper。

### 9.6 Display separation

证明：

```text
calculation = 5.0000004
display = 5.00
```

但 candidate decision 使用 calculation/comparison value，而不是 display 字符串。

### 9.7 Invalid numeric

复用现有 Domain 测试确认：

- Python float 被模型拒绝；
- NaN / Infinity 不进入正式 numeric truth；
- 0/负值等 GB29446 已冻结输入约束保持原结果。

### 9.8 Explicit rounding capability

GB 29446 没有标准明文 explicit round，因此**不应为它伪造 explicit-round vector**。

可以在 generic test fixture 中记录当前 `Expression(round_places=3)` + HALF_UP 行为作为“existing capability evidence”，但不得把它写成 GB29446 标准要求或平台冻结规则。

---

## 10. Proposed Conformance Vectors

Candidate schema 名称建议：

```text
qzc-n01-a-candidate-v0
```

明确标记：**NOT FROZEN PLATFORM SCHEMA**。

每个 vector 建议字段：

```text
vector_id
pilot_id
module_id
standard_id
standard_version
source_sha256
source_locator
input_decimal_strings
calculation_value
current_comparison_value
candidate_comparison_value
display_value
threshold
operator
current_numeric_policy
candidate_numeric_policy
current_grade
candidate_grade
expected_delta
rounding
provenance
notes
```

其中 `rounding` 至少允许：

```text
null
```

或用于记录真实 explicit rule 的结构化对象；GB29446 candidate vectors 应为 `null`，因为未发现标准修约要求。

### 10.1 最低 vector 集

#### C01 — exact equality

```text
actual="5.0"
T="5.0"
current=LEVEL_1
candidate=LEVEL_1
```

#### C02 — just below

```text
actual="4.9999996"
T="5.0"
current=LEVEL_1
candidate=LEVEL_1
```

#### C03 — just above / ROUND6 collapses to T

```text
actual="5.0000004"
T="5.0"
current=LEVEL_1
candidate=LEVEL_2
```

#### C04 — HALF_UP transition

```text
actual="5.0000005"
T="5.0"
current=LEVEL_2
candidate=LEVEL_2
```

#### C05 — level 2 transition

```text
actual="7.0000004"
T="7.0"
current=LEVEL_2
candidate=LEVEL_3
```

#### C06 — minimum qualification boundary

```text
actual="8.5000004"
T="8.5"
current=LEVEL_3
candidate=NOT_QUALIFIED
```

#### C07-C12 — power coal 2.0/3.0/4.5 对称覆盖

分别验证 exact 与 `T+δ`，至少确保三类迁移：1→2、2→3、3→未达标。

#### C13 — formula-generated boundary

```text
E_d="50.000004"
k="1.00"
m="10"
calculation="5.0000004"
current=LEVEL_1
candidate=LEVEL_2
```

#### C14 — display isolation

```text
calculation="5.0000004"
display="5.00"
candidate comparison="5.0000004"
```

#### C15 — decimal lexical equivalence

```text
"5" / "5.0" / "5.000000"
```

应在 exact Decimal equality 下相等。

#### C16 — float rejection

正式 Domain 输入传 Python float，应被拒绝；vector 记录为 invalid input evidence，不把 float 转成合法业务真值。

---

## 11. 哪些 candidate 适合上升到公共 Numeric Contract

N01-A 只能提交 candidate，不得宣称已冻结。

### Candidate P-01 — 默认 full-value Decimal comparison

证据：GB29446 原文只规定 `≤` 与 Decimal thresholds，没有标准修约要求；implicit ROUND6 会使 `T+δ` 与 exact ordering 产生差异。

### Candidate P-02 — 禁止 display value 回流正式判定

证据：`5.0000004` 可显示为 `5.00`，但 exact value 已越过 `5.0`。

### Candidate P-03 — Explicit rounding 必须声明 provenance

若标准确实要求 rounding，应至少能够说明：

- target；
- stage；
- places/significant digits；
- mode；
- purpose；
- source locator。

### Candidate P-04 — Conformance Vector 必须保留 exact decimal text

边界输入、threshold 和 comparison value 不应通过 JSON binary float 表达。

### Candidate P-05 — tolerance 与 exact comparison 分离

本 Pilot 不需要 tolerance；不得用 epsilon 模拟 ROUND6 或“修复”边界。

### Candidate P-06 — current/candidate 可并列记录

在 breaking numeric migration 前，Conformance evidence 最好能同时记录 current behavior 和 candidate behavior，避免通过改测试期望值隐藏行为变化。

---

## 12. 必须继续留在 ECQuota 的规则

以下不应上升为通用 Numeric Contract：

- GB29446 炼焦煤/动力煤的具体阈值；
- `e_d = E_d × k / m`；
- 附录 A 的工艺 `k`；
- GB29446 的煤种/工艺选择；
- 1/2/3级及“未达标”的该标准映射；
- ECQuota 对历史评价的具体保存/查看流程；
- 中文 UI 文案；
- 当前 `.uebench` 包实现细节；
- ECQuota 是否以及何时从旧 ROUND6 迁移到 full-value 的发布节奏。

---

## 13. Expected changed behavior

### 13.1 Pilot Execution 本身

**生产行为预期变化：0。**

Pilot 只增加测试/向量/报告，当前 Engine 仍保持 ROUND6。

### 13.2 若后续批准 full-value migration

预计变化只发生在“raw actual 已越过 threshold，但 implicit ROUND6 后仍等于 threshold”的窄区间。

对于 GB29446 `<=`：

```text
0 < actual - T < 0.0000005
```

是主要 breaking window（以当前 HALF_UP 六位规则为前提）。

普通远离边界案例、exact equality、`T-δ`、`T+0.0000005` 及更大偏移通常不改变现有等级。

**这只是 Pilot candidate impact，不授权立即修改生产结果。**

---

## 14. Regression strategy

### R1 — 双轨而不是覆盖旧测试

保留当前 ROUND6 专项测试作为 current behavior evidence；Pilot 新增 candidate vector，不直接把旧 expected 改成 full-value。

### R2 — 普通业务回归必须全通过

Pilot 不修改 production，因此现有：

- GB29446 tests；
- engine tests；
- UI tests；
- save/read；
- package tests；
- 全量 pytest；

都应保持原结果。

### R3 — 差异白名单

Pilot A/B 输出中的 current/candidate difference 必须只出现在设计列明的边界窗口；任何非预期差异都视为 Pilot FAIL，需要调查。

### R4 — 标准证据绑定

每个 GB29446 vector 记录 source SHA 和 page/table/formula locator，不能仅写“按 Contract”。

### R5 — 历史 Record 不自动重算

Pilot 不修改数据库、不重算历史结果。未来若批准迁移，也必须保留当时保存的 request/result/rule snapshot 与当时 Numeric 语义的可追溯证据。

### R6 — 扩大 rollout 前先扫描其他标准

GB29446 Pilot PASS 不代表 47 项正式标准可以批量迁移。后续 rollout 应先扫描：

- `round_places`；
- 标准原文明确修约；
- compliance；
- condition/range；
- Excel/import ingress；
- 可能依赖旧 ROUND6 的 tests。

---

## 15. Proposed implementation scope（Execution 阶段）

### 必做

1. 从真实 Execution baseline 新建独立分支；
2. 增加 Pilot candidate vector JSON；
3. 增加 Pilot-only A/B test harness；
4. 通过真实当前 Engine 获得 current outputs；
5. 通过独立、极小、测试作用域内的 exact Decimal comparator 获得 candidate outputs；
6. 输出 `T-δ/T/T+δ` 和多步公式的实际执行证据；
7. 运行现有定向与全量测试；
8. 生成 `QZC_N01_A_EXECUTION_REPORT.md`；
9. 按中央 Return Template 准备回报素材；
10. 停止，不迁移 production Engine。

### 可选但不应扩大范围

- 增加一个只供 Pilot 使用的报告生成脚本；
- 增加 vector schema 校验；
- 增加 source SHA/page locator 自动校验。

### 不在本 Pilot Execution 做

- 删除 `_round_threshold_value()`；
- 修改 `_grade()` production semantics；
- 修改 canonical threshold；
- 修改 `Expression.round_places` schema；
- 改 Excel ingress；
- 升级 Rule Engine version；
- 发布新标准包/EXE；
- 做 47 项标准全量 Numeric migration。

---

## 16. Files likely to change（Execution 阶段）

建议只允许新增/修改 Pilot evidence 文件：

```text
tests/pilots/numeric/test_qzc_n01_a_ecquota.py
tests/pilots/numeric/qzc_n01_a_vectors.json
docs/governance/QZC_N01_A_EXECUTION_REPORT.md
```

如果仓库现有测试目录约定不允许上述路径，可以等价放入现有 `tests/fixtures/` / `tests/`，但必须保持 Pilot-only 边界。

设计完成后，本设计文件自身：

```text
QZC_N01_A_LOCAL_DESIGN.md
```

也是合法治理资产。

---

## 17. Files explicitly forbidden to change（本 Pilot Execution）

除非后续用户重新批准扩大范围，否则 N01-A Pilot Execution 禁止修改：

```text
src/uebench/domain/engine.py
src/uebench/domain/models.py
src/uebench/application/**
src/uebench/ui/**
src/uebench/infrastructure/database.py
migrations/**
data/definitions/**
standards/development/**
platform-lock.json
PLATFORM_BASELINE.md
packaging/**
scripts/build_release.ps1
scripts/sync_release.ps1
```

同时禁止：

- 修改 Qingzhou-contracts；
- 修改中央 Numeric DRAFT；
- 修改标准原文 PDF；
- 修改正式 release artifact；
- 修改外部 GB29446 公式 Excel；
- 创建公共 Numeric Python package；
- 大规模重构 UI/Engine/DB。

如果 Pilot evidence 证明未来必须修改这些文件，应把它写进**后续 migration proposal**，而不是在当前 Pilot 偷偷实施。

---

## 18. Future migration candidate（不是本 Pilot Execution）

只有 N01-A 独立验收 + 中央 Gate 4/5 后，如果用户批准真正迁移，才考虑单独任务：

```text
implicit ROUND6
        ↓
default full-value comparison
+
standard-mandated explicit_round
```

届时才评估：

- `_round_threshold_value()` 的移除/隔离；
- grade/compliance/condition 的统一 comparator；
- `Expression.round_places` 是否升级为显式 rounding contract；
- Rule Engine version；
- package compatibility；
- Excel ingress；
- canonical rule revision；
- release candidate；
- 历史结果兼容。

N01-A Design 不预先批准这些 migration 动作。

---

## 19. Execution Prompt Draft

以下提示词供后续 Execution 阶段使用；**当前设计任务不得执行它**。

```text
仓库：
https://github.com/adgo07/ECQuota-Insight.git

任务：
QZC-N01-A — ECQuota Exact Decimal / Rounding Pilot Execution

这不是生产 Numeric migration。
不要修改正式计算算法，不要删除 ROUND6，不要修改 canonical/UI/DB/platform-lock。

开始前完整读取：
- AGENTS.md
- PLATFORM_BASELINE.md
- platform-lock.json
- QZC_N01_A_LOCAL_DESIGN.md
- docs/统一判定规范.md
- src/uebench/domain/engine.py
- src/uebench/domain/models.py
- tests/test_engine.py
- tests/test_gb29446.py
- data/definitions/gb-29446-2019.json
以及中央 contracts-v0.1.0 对应的 Architecture/Numeric baseline 和 N01-A Distribution。

记录最新 main SHA，从最新 main 新建独立执行分支。

只实现 Pilot evidence：
1. 建立 qzc-n01-a candidate conformance vectors，数字全部使用十进制字符串；
2. 覆盖 GB29446 六个正式 threshold 的 T-δ/T/T+δ；
3. δ 至少包含 0.0000004，并覆盖 0.0000005 的 HALF_UP 临界；
4. 增加至少一个 E_d × k / m 产生 T+δ 的真实公式案例；
5. current result 必须由真实现有 EvaluationEngine 执行得到；
6. candidate result 使用 Pilot/test scope 内极小的 full-value Decimal comparator 得到；
7. current 与 candidate 同时记录，不修改旧 expected 来掩盖差异；
8. 验证 display value 不参与 candidate comparison；
9. 验证 Domain float rejection；
10. 生成 docs/governance/QZC_N01_A_EXECUTION_REPORT.md。

严格禁止修改：
- src/uebench/domain/engine.py
- src/uebench/domain/models.py
- src/uebench/application/**
- src/uebench/ui/**
- database/migrations
- data/definitions/**
- standards/development/**
- platform-lock.json
- Qingzhou-contracts
- release artifacts
- GB29446 Excel

必须真实运行：
- Pilot tests
- tests/test_gb29446.py
- tests/test_engine.py
- 全量 pytest

最终报告必须区分：
- 静态审计
- 测试真实运行
- 数值真实重算
- boundary/conformance vectors 真实验证

给出：
- baseline SHA
- execution head SHA
- actual diff
- vector count
- current/candidate delta table
- test commands/results
- unresolved issues
- candidate platform rules
- ECQuota-specific rules

完成后停止，不合并 main，等待独立验收。
```

---

## 20. Acceptance criteria（未来 Independent Acceptance）

### A. Scope

- [ ] 真实 Acceptance head SHA 已记录；
- [ ] diff 只包含 Pilot tests/vectors/report 等批准范围；
- [ ] production Engine/Canonical/UI/DB 没有改变；
- [ ] 未修改 platform-lock；
- [ ] 未修改中央仓。

### B. Standard evidence

- [ ] 使用 source SHA `72011768...cb15d` 对应 GB29446 原文；
- [ ] 表1/表2、式（1）、附录A来源可追溯；
- [ ] 没有把项目 ROUND6 误称为标准明文；
- [ ] “未发现明确修约要求”的结论有全文检索/页级核对说明。

### C. Current implementation evidence

- [ ] 正确定位 `_round_threshold_value()`；
- [ ] 证明 `_grade()` 当前 ROUND6 会影响正式等级；
- [ ] 证明 condition/range 当前使用 full-value；
- [ ] 正确区分 `Expression.round_places` 与 implicit ROUND6；
- [ ] 正确区分 `display_places` / UI formatting 与 comparison。

### D. Boundary execution

- [ ] 六个 threshold 全部有 T-δ/T/T+δ；
- [ ] `δ=0.0000004` 已真实执行；
- [ ] `0.0000005` HALF_UP transition 已真实执行；
- [ ] 至少一个多步公式 T+δ 已真实执行；
- [ ] actual/current/candidate/display 四类值没有混用。

### E. Expected delta

必须至少复现：

```text
5.0000004: current 1级 → candidate 2级
7.0000004: current 2级 → candidate 3级
8.5000004: current 3级 → candidate 未达标
2.0000004: current 1级 → candidate 2级
3.0000004: current 2级 → candidate 3级
4.5000004: current 3级 → candidate 未达标
```

如实际执行不同，不得改 vector 迎合；必须 FAIL/BLOCKED 并解释。

### F. Numeric hygiene

- [ ] vector numeric fields 使用 decimal string；
- [ ] candidate comparator 不使用 binary float；
- [ ] 不使用 epsilon 偷换 full-value semantics；
- [ ] display rounding 不参与 candidate decision；
- [ ] explicit rounding 未被无依据引入 GB29446。

### G. Regression

- [ ] Pilot tests 通过；
- [ ] `tests/test_gb29446.py` 原有 current behavior tests 仍通过；
- [ ] `tests/test_engine.py` 通过；
- [ ] 全量 tests 无本 Pilot 引入的新失败；
- [ ] 没有通过修改 production expected 值伪造 PASS。

### H. Evidence level

验收报告必须明确填写：

```text
Static code audit completed: YES/NO
Tests actually executed: YES/NO
Numerical results actually recomputed: YES/NO
Boundary cases actually executed: YES/NO
Conformance vectors actually executed: YES/NO
Cross-language implementation: NOT IN SCOPE
```

不能把静态设计或代码阅读写成“数值已验证”。

### I. Platform boundary

- [ ] candidate rules 只写 candidate；
- [ ] 不宣称 Numeric Contract v1 已冻结；
- [ ] 不宣称所有项目必须 HALF_UP；
- [ ] 不宣称所有项目必须相同 precision；
- [ ] 不关闭 D-004/D-012；
- [ ] 最终材料可填写中央 N01 Pilot Return Template。

---

## 21. 对中央未决事项的建议

### D-004 Conformance Vector exact schema

N01-A 建议中央 Schema 至少考虑：

- exact decimal input text；
- calculation/comparison/display 分离；
- current policy 与 candidate policy（迁移期）；
- source/provenance；
- expected warnings/status；
- explicit rounding metadata（如存在）。

但单个 Pilot 不足以冻结最终 Schema。

### D-012 tolerance / is_close vs exact comparison

N01-A 的 GB29446 边界不需要 tolerance。证据支持：

> 标准限值比较应能用 exact Decimal 表达，不能用全局 epsilon 代替标准未规定的 rounding/tolerance。

但 EquipEffi/GHGTOOL 仍需分别验证算法内部 tolerance 与工程/测试 tolerance，因此 N01-A 不建议单独关闭 D-012。

### D-001

GB29446 不使用 sqrt/ln/fractional pow/exp，本 Pilot 对 D-001 无新增冻结证据。

---

## 22. Design answers to the 12 required questions

1. **当前 Numeric 正式链路**：文本输入 → InputValue → Decimal → Canonical formula/threshold → Decimal calculation → `_grade()` ROUND6/HALF_UP → comparison → Grade → UI display。
2. **ROUND6 在哪里**：主要在 `engine.py` 的 `_round_threshold_value()`、grade、compliance；同时存在治理文档和专项测试预期。
3. **是否进入正式等级判定**：是，`_grade()` 直接用 ROUND6 后的值决定 Grade。
4. **ROUND_HALF_UP 性质**：GB29446 原文未要求；当前是项目治理/历史实现规则；不能自行升级为平台规则。
5. **仅显示的 round**：`display_places=2`、`_format_result_number()`、`_format_explanation_number()` 属 presentation；不决定 grade。
6. **是否有 T-δ/T/T+δ 变化**：有；`T+0.0000001..0.0000004` 是最直接 breaking window。
7. **标准是否明确要求修约**：本次完整 5 页 PDF 检索与页级核对未发现。
8. **full-value 替代 implicit ROUND 的影响**：六个 threshold 的 `T+0.0000004` 均会向下一等级/未达标迁移；普通非边界案例预计不变。
9. **需要哪些 vectors**：exact/below/above、beyond-6-decimal、HALF_UP transition、display isolation、多步公式、decimal round-trip、invalid float/non-finite；GB29446 不伪造 explicit-round vector。
10. **适合上升公共 Contract**：default exact/full-value candidate、display/comparison separation、explicit rounding provenance、decimal-text vectors、tolerance taxonomy 边界。
11. **必须留在 ECQuota**：GB29446 formula/threshold/k/grade mapping、业务 UI/Record 流程、迁移发布节奏等。
12. **最小实现 Pilot**：不改 production；只加 Pilot A/B harness + vectors + execution report，真实执行 current Engine 与 candidate exact comparator 并列证据。

---

## 23. Explicit final design statement

- **Design completed:** YES
- **Production code changed by this design:** NO
- **ROUND6 removed:** NO
- **Numeric migration executed:** NO
- **Tests actually executed as part of this Design:** NO
- **Numerical results actually recomputed as part of this Design:** NO
- **Conformance vectors actually executed:** NO
- **Platform-wide Numeric rule frozen:** NO

下一步若获批准，应进入独立的 `N01-A Execution` 分支，只实施本设计定义的 evidence Pilot；Execution 完成后再由独立验收决定 Gate 1 的 PASS / FAIL / BLOCKED。
