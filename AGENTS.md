# AGENTS.md — ECQuota-Insight

本文件补充当前仓库的执行治理，不覆盖既有 `HANDOFF.md`、README、标准原文、用户已确认业务口径和其他有效项目结论。

## 1. 仓库身份

| 项目 | 值 |
|---|---|
| Module ID | `qz.energy_quota` |
| 产品名称 | 单位产品能耗限额评价软件（程序包名 `uebench`） |
| 当前 Reference Standard | `GB 29446—2019 选煤电力消耗限额` |
| 当前产品阶段 | 参考标准核心纵向闭环；`PHASE_1` 类业务验收已有多批记录，无统一 Phase 编号 |
| 当前交付范围 | 47 项强制性能耗限额标准、753 条当前指标；开发基线 `standards/development/scope-63` |
| Canonical repository | `https://github.com/adgo07/ECQuota-Insight.git` |

本仓仍独立开发、独立安装、独立升级、独立离线运行。

### 1.1 仓库身份与本地执行环境

**仓库身份**以 GitHub owner/repository 与 `git origin` 为准，**不以本地文件夹名或绝对路径为准**：

| 仓库 | Canonical repository |
|---|---|
| 本仓（ECQuota-Insight） | `https://github.com/adgo07/ECQuota-Insight.git` |
| 中央治理仓（Qingzhou-contracts） | `https://github.com/adgo07/Qingzhou-contracts.git` |
| 兄弟业务仓 | `https://github.com/adgo07/EquipEffi.git`、`https://github.com/adgo07/GHGTOOL.git` |

规则：

1. 本仓长期身份以 GitHub owner/repository + `git origin` 为准；**本地绝对路径只是当前运行环境，不是仓库身份**；
2. **不得**把某台电脑的 `C:\` / `D:\` / `E:\` / `G:\` 等绝对路径当成跨机器固定路径；
3. 历史 HANDOFF / 报告中的绝对路径只是**历史执行环境记录**，不得直接作为当前 checkout 地址；
4. **不得仅凭文件夹名判断仓库**；本仓本地目录名与实际仓库名不一致是正常情况；
5. **不得假设** `Qingzhou-contracts` 一定位于 `../Qingzhou-contracts` 或任何固定相对位置。

**本地正式任务开始前必须实际确认**（不得凭记忆或上次会话推断）：

```powershell
git rev-parse --show-toplevel      # 实际工作树根
git remote get-url origin          # 实际 origin
git branch --show-current          # 当前分支
git rev-parse HEAD                 # 当前 head
git status --short                 # 工作区状态
git fetch origin                   # 同步远端
```

6. 必须确认当前 `origin` 与本任务指定的 GitHub 仓库**一致**；
7. **若 `origin` 不一致，必须 `BLOCKED` 停止，不得继续修改错误仓库**；
8. `fetch` 后检查默认分支 / `origin` 默认分支是否同步，并核对默认分支名（本仓默认分支为 `main`）；
9. 需要读取 `Qingzhou-contracts` 或其他青舟仓库时：
   - **已存在本地 clone**：先验证其 `origin` 指向预期 GitHub 仓库，再读取；
   - **没有可信本地 clone**：从 GitHub 读取；
   - 不得仅凭文件夹名判断仓库；
   - 不得假设中央仓位于任何固定相对路径。

## 2. 本仓专属硬规则

### 2.1 Numeric v1 正式执行规则

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

`Expression.round_places` 是**显式公式修约能力**（配合 `ExplicitRounding` 的 stage / mode / purpose / source），不是全局 ROUND6；不得把它当成隐式修约通道。

不得以“旧软件一直这样算”作为保留隐式修约的依据。

### 2.2 Numeric traceability 与 Conformance

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

### 2.3 Excel 数值入口特别规则

authoritative XLSX 数值如被 openpyxl 物化为 Python `float`，**必须拒绝**。

当前模板正式数值列要求以文本形式录入十进制 lexical value。不得再通过 `float -> str -> Decimal` 静默恢复为业务真值。

### 2.4 权威边界

- 标准原文、正式修改单和更具体法定/标准专属要求不得被通用公共 Contract 覆盖；
- Frozen Numeric Contract 规定默认 Numeric 语义；标准明确例外通过显式 Rule 表达；
- 普通业务问题、产品 Bug、单标准专属公式、专属 UI、产品内部实现继续在本仓解决；
- 公共 Contract 不得覆盖业务模块合法自治范围。

### 2.5 当前已知上位偏差

已关闭：

- `D-ECQ-001-global-round6-vs-frozen-full-value` — Numeric v1 Full Adoption 已移除公共 Engine 无依据默认 ROUND6。详见 `docs/governance/NUMERIC_V1_ADOPTION_REPORT.md`。

仍 OPEN（权威清单见 `platform-lock.json` 的 `known_deviations`）：

- `D-ECQ-002` Module/Capability Manifest 尚未正式实施；
- `D-ECQ-003` Workspace/Attempt/Record/Result 公共外围仅部分具备；
- `D-ECQ-004` 现有 `.uebench` 包不是正式 qzpack v1；
- `D-ECQ-005` Unit Contract 仍未正式采用；
- `D-ECQ-006` 中央 lossless XLSX numeric-cell 公共方案仍 OPEN。

### 2.6 禁止无关扩大范围

普通 Contract adoption / Numeric 任务不得借机默认要求：

- 重写业务 UI；
- 迁移数据库；
- 合并三个仓库；
- 启动 Suite / Mobile；
- 全量 qzpack 化；
- 为统一架构重写成熟业务能力。

只有与已冻结 Contract 直接冲突的生产行为，才允许做最小必要修复。

### 2.7 中文优先

在不破坏机器识别、稳定接口、Schema、API、代码标识符、自动化测试和跨平台兼容的前提下：

> 用户可见内容、治理文档、路线、执行报告、验收报告、PR/Issue 描述、错误/校验提示和面向人的说明优先使用中文。

稳定机器字段、JSON/YAML key、enum、API/schema field、Module ID、Contract ID、Python 类/函数/模块名等继续保持既有英文标识；面向人解释时优先使用“中文名称（英文标识）”。

### 2.8 本仓当前产品现实

- Windows Desktop 是当前第一交付平台；程序包名仍为 `uebench`；
- 普通页面不含企业属性、单一煤种工艺确认及合规主结论；
- GB 29446 专用页面显示“超出3级”，覆盖早期规范中的“未达标”措辞；
- 新版 EXE、安装包和独立公式 Excel 尚未同步完成最新口径验收；旧发布物不代表当前源码。

## 3. 青舟中央治理入口

中央仓：

`https://github.com/adgo07/Qingzhou-contracts.git`

当前批准基线以本仓以下文件为准：

- `PLATFORM_BASELINE.md`
- `platform-lock.json`

**Frozen 权威文件**（Frozen Contract / Frozen Schema / Frozen Conformance / Architecture Frozen）：

> 按本仓 `platform-lock.json` 锁定的 commit SHA 读取。

**ACTIVE / ACTIVE-EVOLVING 指南**：

> 先读中央 `docs/GUIDE_INDEX.md`，按其路由读取中央仓当前正式合并的适用版本。

当前本仓正式采用：

- Architecture 2.1 — **FROZEN**；
- Numeric Contract v1 — **FROZEN / ADOPTED**；
- Numeric Profiles v1 — **FROZEN / ADOPTED**；
- Numeric Conformance Vector v1 — **FROZEN / ADOPTED**。

仍未正式采用/冻结：

- Unit Contract — **DRAFT**；
- Module/Capability Contract — **DRAFT**；
- Workspace/Attempt/Record/Result Contract — **DRAFT**；
- qzpack Contract — **DRAFT**。

不得：

- 自动升级 Frozen Contract；
- 把 ACTIVE Guide 当 Frozen Contract；
- 用中央 Guide 覆盖本仓 locked Frozen Contract；
- 实时采用或运行时依赖 `Qingzhou-contracts/main` 最新内容；
- 虚构 release/tag。

DRAFT Contract 必须明确标识为 DRAFT。有正式 release/tag 后，应锁定 release/tag + 对应精确 commit SHA。升级公共 Contract 后必须运行适用公共 Conformance 和本项目完整回归。

两者冲突时：**以本仓 locked Frozen 权威文件为准。**

依据：中央 `docs/GUIDE_INDEX.md`、`docs/governance/VERSIONING.md`。

## 4. 开工前最小必要读取（Minimum Necessary Reading）

```text
1. AGENTS.md（本文件）
2. platform-lock.json
3. HANDOFF.md / TASK_STATE.md
4. STANDARD_ISSUES_REGISTER.md
5. 当前任务直接相关的本仓文件
6. 中央 docs/GUIDE_INDEX.md
7. 只读取 GUIDE_INDEX 为当前任务路由的中央文件
```

**不得**要求每个普通业务 Bug 都通读整个 `Qingzhou-contracts`。

如任务涉及公共语义，按第 3 节的**双轨读取**执行：Frozen 权威文件走 locked SHA，ACTIVE 指南走 central 当前正式合并版本。

只有任务明确要求“升级中央 Contract 基线”时，才能通过独立治理任务修改 `PLATFORM_BASELINE.md` / `platform-lock.json`。

### 4.1 当前权威读取顺序

新任务默认按以下顺序建立上下文，**不要默认通读历史资料**：

```text
1. AGENTS.md
2. TASK_STATE.md
3. 参考标准开发路线.md
4. STANDARD_ISSUES_REGISTER.md
5. platform-lock.json
6. 当前任务相关代码 / 测试
```

- **Numeric 任务**再读取 `docs/统一判定规范.md`；
- 中央文件由中央 `docs/GUIDE_INDEX.md` 路由；
- 历史资料（`docs/history/`、`docs/audits/`、`docs/验收记录.md`）按需读取，**不属于默认必读**。

`参考标准开发路线.md` 是本仓**唯一**总体产品开发路线；不得再新建与其并列的第二份总体路线。

### 4.2 正式报告必须写平台 / Contract 预检查

后续正式 Design、Execution Report、Acceptance Report 不得省略“平台 / Contract 预检查”。至少记录：

- 当前业务仓 SHA；
- `platform-lock.json` / 中央锁定 SHA；
- 本任务相关 Frozen Contract；
- 适用 MUST / MUST NOT；
- 是否发现冲突及其分类；
- 是否需要中央 Contract 修改；
- 是否存在与当前任务相关的 Standard Issue：是 / 否；
- 涉及的问题编号；
- 本任务是否改变既有软件解释。

若任务确实与中央公共语义无关，也必须明确写：`本任务不涉及中央公共 Contract。`

## 5. 冲突分类

发现不一致时必须标记为以下之一：

- `LOCAL DEFECT`：本地实现违反已采用 Frozen Contract；修本仓；
- `ALLOWED PROJECT DIFFERENCE`：中央允许项目自定义，例如 Numeric Profile precision；不得为了表面一致强行统一；
- `REGISTERED DEVIATION`：已有正式登记且尚未关闭；按治理状态执行；
- `CENTRAL CONTRACT GAP`：真实业务需求无法被中央 Contract 正确表达；不得本地永久发明中央规则，应整理业务证据 / 案例 / Contract 缺口 / Candidate 返回中央仓。

如果问题同时影响三个产品、多平台公共语义或 Numeric / Unit / Module / qzpack / Record / Conformance 等公共能力，必须按 `CENTRAL CONTRACT GAP` 处理，由中央治理流程决定；本仓不得直接修改 Qingzhou-contracts 正式 Contract，除非任务明确切换到公共仓治理流程。

## 6. 新标准开发入口

任何**新增标准**或**实质修改既有标准支持范围**的任务：

> 必须按中央 `docs/governance/STANDARD_DEVELOPMENT_GUIDE_V0.1.md` 执行。

顺序：

```text
Stage A 标准整理
→ Stage B 软件接入设计
→ Stage C 实现
→ Stage D 正式验收
```

不得：

- 拿到 PDF 就直接写 Calculator；
- 跳过 Standard Mapping；
- 在 Mapping 中静默纠正标准；
- UI 先发明业务规则；
- Excel 建第二套算法；
- 未经正式验收就宣布 `SUPPORTED`。

标准支持状态只使用：`CATALOG_ONLY` / `MAPPING` / `READY_FOR_IMPLEMENTATION` / `IMPLEMENTED` / `SUPPORTED`，不得无证据跳级。

详细规则见中央指南，不复制进本文件。

## 7. 标准问题与解释治理

开工前必须读取根目录 `STANDARD_ISSUES_REGISTER.md`，检查当前任务是否涉及已有 Standard Issue。

如果在标准映射、软件设计、Calculator、Golden Case、测试、Excel、用户实际使用或标准更新中发现新的疑似笔误、歧义、冲突、未规定、术语、引用或软件解释问题，必须先登记到 `STANDARD_ISSUES_REGISTER.md`，再完成正式实现说明。

每个问题必须明确分开记录“标准原文事实”“技术判断”“软件实现决定”。不得把内部技术判断或软件选择写成标准明文，不得在 Mapping、Rule、Calculator 或测试中静默纠正疑似标准错误。若问题会影响正式业务结果，必须能追踪：

```text
Standard Issue
→ Software Decision
→ Rule / Calculator
→ Test / Golden Case
```

修改既有解释时必须同步检查相关测试和历史结果兼容性。本规则只建立治理机制，不授权当前任务修复已登记问题。

`STANDARD_ISSUES_REGISTER.md` 保持独立文件，不得合并进 `AGENTS.md`、`HANDOFF.md`、knowledge 或 Mapping。

## 8. 桌面 UI 前置原则

后续涉及桌面 UI 的 Design / Execution / Acceptance 必须检查中央 `docs/ui/UI_DESIGN_GUIDELINES_V0.1.md` 的**当前适用版本**（ACTIVE / EVOLVING 指南，不是 Frozen Contract）。

本仓相关要点：

1. 当前 Windows Desktop 默认 UI 技术栈为 PySide6；
2. 用户可见内容中文优先；普通 UI 不得默认泄露内部 `key / field / field_id / rule_id / internal_id`、Python 变量或调试标识；
3. 简单业务采用 `One-page first`，但不是所有标准强制单页；
4. 技术 trace、Numeric Profile、Calculator version、内部 Rule 采用渐进展示，**不删除审计能力**；
5. UI 设计优先满足真实用户任务，不按数据库、JSON 或代码结构组织普通页面；
6. UI 只能重组展示层信息，不得自行改变 Calculator / Domain Rule / Canonical / Numeric 语义或标准解释；
7. AI 不得因为 v0.1 的推荐 AppShell、页面示意或当前实现而拒绝合理的页面改进，也不得把推荐模式误当强制布局。

该 UI Guideline 不改变本仓 `platform-lock.json` 的 Frozen Contract 锁定语义。

## 9. 知识沉淀入口

在标准开发、Mapping、Calculator、测试、UI、Excel 等任务中，如果产生**有长期价值**且**已有证据支持**的专业知识，允许顺手记录到本仓 `knowledge/`。

- 默认状态：`DRAFT`；
- 不要求每个任务必须产生知识；
- 不得为了 Knowledge 明显扩大主任务；
- 标准原文事实、官方资料、专业解释、工程建议必须区分；
- 知识文章不是 Calculator 的真值源或规则源，不得运行时解析 Markdown 决定业务结果。

详细规则见中央 `docs/governance/STANDARD_DEVELOPMENT_GUIDE_V0.1.md`，不复制进本文件。
