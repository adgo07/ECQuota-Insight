# 标准问题与解释台账

状态：**ACTIVE REGISTER**

本台账用于记录标准原文事实、技术判断与软件实现决定。不得用本台账改写标准原文，也不得把内部判断或软件选择表述成发布机构正式解释。

## 1. 类型代码

| type code | 中文解释 |
|---|---|
| `TYPO` | 疑似笔误 |
| `AMBIGUITY` | 歧义 |
| `CONFLICT` | 条款、公式或表格冲突 |
| `MISSING` | 标准未规定 |
| `TERM` | 术语或现实对象对应不清 |
| `REFERENCE` | 引用标准、版本或外部依据问题 |
| `IMPLEMENTATION` | 软件实现解释问题 |

## 2. 状态代码

| status code | 中文解释 |
|---|---|
| `OPEN` | 待解决 |
| `PROVISIONAL` | 已有临时处理口径 |
| `RESOLVED` | 已有充分依据确认 |

`RESOLVED` 不自动等于发布机构官方确认；是否有官方解释必须在“确认程度”中单独说明。

## 3. 登记规则

- 问题编号采用 `ECQ-STD-<标准号简写>-NNN`，一旦使用不得改号或复用。
- 每个问题必须分开记录“标准原文事实”“当前技术判断”“软件当前处理方式”。
- 无法准确复制标准原文时，不得凭记忆补写；应记录准确定位、事实摘要或“未复制原文”，并保留证据来源。
- 影响正式业务结果的问题必须可追踪：`Standard Issue → Software Decision → Rule / Calculator → Test / Golden Case`。
- 后续修改既有解释时，必须检查相关测试和历史结果兼容性。
- 当前只登记已有明确证据的问题，不重新审计全部标准，也不为填表制造问题。

## 4. 当前问题

### ECQ-STD-GB29446-001 — 正式比较中历史 ROUND6 缺少标准依据

| 字段 | 记录 |
|---|---|
| 问题编号 | `ECQ-STD-GB29446-001` |
| 标准编号及名称 | GB 29446—2019《选煤电力消耗限额》 |
| 标准版本 | 2019 |
| 条款 / 表 / 公式 / 页码 | 与正式等级/符合性边界比较相关；现有 Numeric 审计未把历史统一 ROUND6 追溯到具体标准条款，后续如取得原文定位应补充 |
| 标准原文 | 本台账不凭记忆复制标准原文。现有审计事实仅能确认：未识别到要求软件在正式比较前统一执行 6 位小数 `ROUND_HALF_UP` 的标准依据 |
| 问题类型 | `IMPLEMENTATION`（软件实现解释问题） |
| 问题说明 | 历史公共 Engine 曾在正式等级/符合性比较前执行统一 ROUND6；该行为会改变临界值附近结果，但审计未找到相应标准来源 |
| 支持证据 | `docs/governance/NUMERIC_V1_ADOPTION_REPORT.md`；N01-A migration evidence；`tests/conformance/numeric/test_ecquota_numeric_v1.py`；Numeric v1 Conformance vectors |
| 当前技术判断 | 历史 ROUND6 属于无明确来源的软件实现行为，不能表述为 GB 29446 明文要求；若未来标准原文或正式 Rule 发现明确修约要求，应重新评估 |
| 软件当前处理方式 | 当前采用 full-value exact Decimal 正式比较；显示修约与业务比较隔离；只有具有明确 `source/provenance` 的 Rule 才可声明业务修约 |
| 确认程度 | 内部审计证据充分；**无发布机构正式解释，不能标记为官方确认** |
| 业务影响 | 高：在等级或符合性阈值附近，ROUND6 与 full-value 比较可能给出不同正式结果 |
| 关联 Rule / Calculator | `ECQUOTA_DECIMAL_FULL_VALUE_V1`；`ecquota-full-value-exact-v1`；GB 29446 评价路径 |
| 关联测试 / Golden Case | N01-A conformance / migration evidence；`tests/conformance/numeric/test_ecquota_numeric_v1.py`；当前未以本台账新增 Golden Case |
| 状态 | `PROVISIONAL`（已有临时处理口径） |
| 首次发现日期 | 2026-10-01（本台账首次登记；历史发现过程见 Numeric 审计材料） |
| 最后更新日期 | 2026-10-01 |

### 追踪链

```text
ECQ-STD-GB29446-001
→ Software Decision: formal comparison uses full-value exact Decimal unless an explicit sourced Rule requires rounding
→ Rule / Calculator: ECQUOTA_DECIMAL_FULL_VALUE_V1 / GB 29446 evaluation path
→ Test: N01-A conformance + migration evidence + test_ecquota_numeric_v1.py
```

本登记只记录现状，不在本任务中再次修改 Calculator、标准判定或测试期望。
