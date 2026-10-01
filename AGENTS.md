# AGENTS.md — ECQuota-Insight

本文件补充当前仓库的执行治理，不覆盖既有 `HANDOFF.md`、README、标准原文、用户已确认业务口径和其他有效项目结论。

## 1. 项目定位

本仓库是青舟工业能源软件体系中的单位产品能耗限额评价业务仓库。

永久 Module ID：

```text
qz.energy_quota
```

当前仍独立开发、独立安装、独立升级、独立离线运行。

## 2. Qingzhou Contracts 上位治理

公共规范权威仓库：

`https://github.com/adgo07/Qingzhou-contracts.git`

当前批准基线必须以本仓以下文件为准：

- `PLATFORM_BASELINE.md`
- `platform-lock.json`

当前锁定中央精确 commit：

`ee5feb0cc34dbd99790500fadd0c4c932e202a20`

不得自动跟随中央 `main`，不得虚构 release/tag。

当前正式采用：

- Architecture 2.1 — **FROZEN**；
- Numeric Contract v1 — **FROZEN / ADOPTED**；
- Numeric Profiles v1 — **FROZEN / ADOPTED**；
- Numeric Conformance Vector v1 — **FROZEN / ADOPTED**。

仍未正式采用/冻结：

- Unit Contract — **DRAFT**；
- Module/Capability Contract — **DRAFT**；
- Workspace/Attempt/Record/Result Contract — **DRAFT**；
- qzpack Contract — **DRAFT**。

## 3. 版本锁定规则

1. 不得实时采用或运行时依赖 `Qingzhou-contracts/main` 最新内容；
2. 中央仓后续 commit 默认不会自动对本项目生效；
3. 只有显式升级 `PLATFORM_BASELINE.md` 与 `platform-lock.json` 后，新公共 Contract 才进入本项目基线；
4. 有正式 release/tag 后，应锁定 release/tag + 对应精确 commit SHA；
5. 升级公共 Contract 后必须运行适用公共 Conformance 和本项目完整回归；
6. DRAFT Contract 必须明确标识为 DRAFT。

## 4. Numeric v1 正式执行规则

项目级 Numeric Profile：

`ECQUOTA_DECIMAL_FULL_VALUE_V1`

正式默认语义：

```text
representation      = Decimal
working_precision   = 28
working_rounding    = ROUND_HALF_EVEN
formal comparison   = full-value exact
implicit rounding   = forbidden
business tolerance  = none by default
display rounding    = presentation-only
```

公共 Engine **不得**恢复：

- 默认 ROUND6；
- 无来源的 pre-comparison quantize；
- global epsilon；
- display value 回流 formal comparison；
- caller ambient Decimal context 静默改变 authoritative result。

如果标准原文或正式 Rule 明确要求业务修约，必须显式声明：

- stage；
- places / precision / significant digits；
- rounding mode；
- purpose；
- source/provenance。

不得以“旧软件一直这样算”作为保留隐式修约的依据。

## 5. Numeric traceability 与 Conformance

新的正式计算结果至少必须能够识别：

- `numeric_contract_version`；
- `numeric_profile_id`；
- `calculator_version`；
- `rule_revision`；
- 必要时 `numeric_behavior_version`。

Numeric 相关修改至少运行：

- `tests/conformance/numeric/test_ecquota_numeric_v1.py`；
- 原 N01-A migration evidence；
- Numeric/domain/import tests；
- full suite；
- `.github/workflows/numeric-v1-adoption.yml`。

`tests/conformance/numeric/ecquota_numeric_v1_vectors.json` 必须继续符合中央 Frozen Conformance Vector v1 schema，并被真实执行，不能只生成 JSON。

## 6. 权威边界

- 标准原文、正式修改单和更具体法定/标准专属要求不得被通用公共 Contract 覆盖；
- Frozen Numeric Contract 规定默认 Numeric 语义；标准明确例外通过显式 Rule 表达；
- 普通业务问题、产品 Bug、单标准专属公式、专属 UI、产品内部实现继续在本仓解决；
- 公共 Contract 不得覆盖业务模块合法自治范围。

## 7. 当前已知上位偏差

已关闭：

- `D-ECQ-001-global-round6-vs-frozen-full-value` — Numeric v1 Full Adoption 已移除公共 Engine 无依据默认 ROUND6。

仍 OPEN：

- Module/Capability Manifest 尚未正式实施；
- Workspace/Attempt/Record/Result 公共外围仅部分具备；
- 现有 `.uebench` 包不是正式 qzpack v1；
- Unit Contract 仍未正式采用；
- 中央 lossless XLSX numeric-cell 公共方案仍 OPEN。

Excel 特别规则：authoritative XLSX 数值如被 openpyxl 物化为 Python `float`，必须拒绝；当前模板正式数值列要求以文本形式录入十进制 lexical value。不得再通过 `float -> str -> Decimal` 静默恢复为业务真值。

详见：

- `PLATFORM_BASELINE.md`
- `platform-lock.json`
- `docs/governance/NUMERIC_V1_ADOPTION_REPORT.md`

## 8. 公共 Contract 缺口与 RFC Candidate

如果问题同时影响三个产品、多平台公共语义或 Numeric / Unit / Module / qzpack / Record / Conformance 等公共能力，不得在本项目永久私自定义一套同名不同义的公共规则。

应记录 RFC candidate，由中央治理流程决定；本项目不得直接修改 Qingzhou-contracts 正式 Contract，除非任务明确切换到公共仓治理流程。

## 9. 禁止无关扩大范围

普通 Contract adoption / Numeric 任务不得借机默认要求：

- 重写业务 UI；
- 迁移数据库；
- 合并三个仓库；
- 启动 Suite / Mobile；
- 全量 qzpack 化；
- 为统一架构重写成熟业务能力。

只有与已冻结 Contract 直接冲突的生产行为，才允许做最小必要修复。

## 10. 当前仓执行原则

开始任务前至少检查：

1. `AGENTS.md`
2. `PLATFORM_BASELINE.md`
3. `platform-lock.json`
4. `HANDOFF.md`
5. 与任务相关的本仓业务规范

如任务涉及公共 Contract，再读取锁定 SHA 对应的 Qingzhou-contracts 文件，不得按中央仓最新 `main` 猜测规则。
