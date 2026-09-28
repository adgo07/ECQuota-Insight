# PLATFORM_ADOPTION_REPORT

任务：`QZC-A01 — 接入 Qingzhou-contracts 公共治理`  
接入日期：2026-09-28  
业务仓：`adgo07/ECQuota-Insight`  
业务仓基线 main SHA：`d857f70acbc476f30decc2e0bd367d692a1447d1`  
工作分支：`chore/qingzhou-contracts-adoption`

## 1. 当前仓信息

- repo: `https://github.com/adgo07/ECQuota-Insight.git`
- default branch: `main`
- baseline head: `d857f70acbc476f30decc2e0bd367d692a1447d1`
- product: 单位产品能耗对标软件（UEBench / ECQuota-Insight）
- Qingzhou module id: `qz.energy_quota`
- 当前业务阶段：GB 29446 专用评价页面源码已独立验收；仓库文档报告完整测试 303 项通过；新版 EXE/安装包及公式 Excel 尚未同步验收；正式范围 47 项，开发基线仍有 16 项草案。
- baseline 时仓库不存在 `AGENTS.md` 与 `TASK_STATE.md`；QZC-A01 在接入分支中新增最小治理文件。

## 2. Qingzhou-contracts 锁定信息

公共仓：`https://github.com/adgo07/Qingzhou-contracts.git`

当前中央仓：

- default branch: `main`
- locked commit: `0cd74d783fa23add6dc881b408a8c8ba8503f8e8`
- release/tag: **无**
- baseline type: **pre-release / bootstrap baseline**
- Architecture: `V2.1 FROZEN`
- Numeric Contract: `draft-v1` — **DRAFT / NOT YET RELEASED**
- Unit Contract: `draft-v1` — **DRAFT / NOT YET RELEASED**
- Module / Capability Contract: `draft-v1` — **DRAFT / NOT YET RELEASED**
- Workspace / Attempt / Record / Result Contract: `draft-v1` — **DRAFT / NOT YET RELEASED**
- qzpack / Canonical Package Contract: `draft-v1` — **DRAFT / NOT YET RELEASED**

本业务仓不得实时跟随 Qingzhou-contracts `main`。后续中央仓变化只有在显式升级 `PLATFORM_BASELINE.md` 和 `platform-lock.json` 后才对本仓生效。

## 3. Adoption Matrix

| 公共能力 | 当前状态 | 当前仓真实情况 | QZC-A01处理 |
|---|---|---|---|
| Domain/Application 与 UI 分离 | **已满足（结构层面）** | `src/uebench/domain`、`application`、`infrastructure`、`ui` 已分层；现有宏观结构审计明确 Domain 不依赖 Qt/SQLite/Excel，UI 通过 ApplicationFacade | 仅记录，不改代码 |
| Canonical-first | **部分满足** | `data/definitions` / development rules、来源 SHA、结构化规则、签名 `.uebench` 包已形成较强 Canonical 基础；但尚未具备 Qingzhou 完整 Business Truth + Conformance/qzpack 公共外围 | 记录差距 |
| Numeric | **部分满足 / 存在硬冲突** | 使用 `Decimal`、显式拒绝 binary float；但本仓全局 ROUND6 与 Architecture V2.1 FROZEN 的默认 full-value comparison 冲突 | **BLOCKED 记录，不修** |
| Unit | **部分满足** | 模型保存单位并进行部分输入单位一致性校验；能源明细存在单位/系数分母校验 | 尚无正式 Unit Contract、稳定公共 Unit ID/Conversion Contract |
| Module ID | **尚未在运行实现中实施** | 中央 FROZEN ID 为 `qz.energy_quota`；当前代码/manifest 尚无正式 Module Manifest | 治理层登记，不改运行代码 |
| Capability | **尚未实施** | 当前产品有功能和发布范围，但没有 Qingzhou Capability Manifest / Conformance Gate | 后续实施 |
| Workspace | **尚未实施公共 Contract** | 当前有评价输入/页面状态，但没有平台无关、可恢复的 Qingzhou Workspace Envelope | 后续实施 |
| Attempt / Record | **部分满足** | 已有一次评价计算、保存记录、审计；`SqlEvaluationRepository` 保存 request/result/rule snapshot；没有明确 Attempt Envelope / business-vs-execution status 分层 | 后续增量兼容 |
| Result | **部分满足** | `EvaluationResult`/`IndicatorResult` 有结构化结果、trace、source refs、rule snapshot hash | 尚缺公共 Result Envelope 的 contract/module/numeric/unit/package 等版本外围 |
| Conformance | **尚未正式实施** | 当前有 pytest、边界测试、GB29446 专项测试，但不是 Qingzhou 平台无关 Conformance Vectors | 后续代表标准试点 |
| qzpack | **部分满足 / prototype-adjacent** | `.uebench` 已有 manifest、文件 SHA-256、Ed25519 签名、版本、父包、安装验证/备份等能力 | 不伪称 qzpack v1；后续 prototype 对齐 |
| 跨平台 Workspace | **尚未实施** | 当前仍为 Windows Desktop 产品；不存在 `.qzproj` / 跨平台 Workspace Contract | 当前不做 |

## 4. 已满足

### 4.1 分层基础

现有工程已经形成：

```text
UI → Application → Domain
                 ↓
           Infrastructure ports/adapters
```

现有 `docs/宏观结构审计-20260905.md` 明确记录：

- Domain：标准模型、Decimal 计算、条件/公式、判级、trace；不依赖 Qt、SQLite、Excel；
- Application：用例与端口；
- Infrastructure：SQLite、Excel、签名标准包、备份、日志；
- UI：PySide6 展示与输入。

这与 Architecture V2.1 的长期分层方向基本一致。

### 4.2 Decimal / float 防护

当前 Domain 模型明确拒绝 float 进入规则和正式评价模型，主要业务数值使用 `Decimal`。这一点与中央 Numeric 的十进制确定性方向一致。

### 4.3 历史结果快照方向

当前保存评价时同时保存：

- request；
- result；
- rule snapshot；
- evaluation id / timestamp；
- audit event。

标准更新不会要求自动改写历史评价，方向与中央 Record 历史不漂移原则一致。

### 4.4 现有标准包具备可验证基础

`.uebench` 当前已包含/实现部分未来 qzpack 需要的基础能力：

- manifest；
- 文件 SHA-256；
- Ed25519 签名；
- package id / data version；
- full/incremental 与 parent package；
- app/rule engine version check；
- 安装前后审计、备份等。

但其 schema 与生命周期不是正式 qzpack Contract，不能视为已经完成 qzpack。

## 5. 部分满足

### 5.1 Canonical-first

当前 JSON definitions、标准来源 SHA、结构化 Rule、签名包构成较强 Canonical 基础；SQLite 主要保存安装后的 definition JSON 和运行记录。

差距：

- 尚无正式公共 Canonical Envelope；
- provenance 结构仍是业务仓私有模型；
- Conformance 尚未成为 Canonical package 的权威资产；
- 当前开发/正式/历史副本仍需后续明确生成与唯一事实源关系。

### 5.2 Unit

当前 `InputValue`/`InputDefinition`/明细模型保存单位，并在部分路径检查输入单位与系数分母一致性。

差距：

- 没有公共 Unit ID；
- 没有正式 UnitService / conversion_id/version；
- 产品专属单位与公共 SI/工业单位尚未按 Unit Contract 分层；
- 单位转换与标准公式系数的公共治理尚未正式化。

### 5.3 Attempt / Record / Result

当前评价可以计算并保存为不可回写的历史记录式对象，并保存规则快照。

差距：

- 没有显式 Workspace；
- 没有独立 Attempt 模型；
- 业务“无法判定/不适用”等仍主要混在 `Grade` 中，尚未与 execution error 清晰分层；
- Result/Record 缺少公共 Envelope 的 module/contract/package 版本字段；
- 没有 lineage/recalculation 公共结构。

## 6. 尚未实施

以下不能因为 Architecture V2.1 已存在就宣称当前产品已经支持：

1. Qingzhou Module/Capability Manifest；
2. Capability Conformance Gate；
3. 平台无关 Workspace Contract；
4. Attempt / Record / Result v1 公共 Envelope；
5. Qingzhou 公共 Unit Contract 实现；
6. Qingzhou 平台无关 Conformance Vectors；
7. 正式 `.qzpack`；
8. `.qzproj`；
9. Suite；
10. Mobile / Mini / macOS / Linux 正式实现；
11. Qingzhou 共享 Python/native core。

## 7. 当前冲突

### BLOCKED-01 — ECQuota 全局 ROUND6 与 Architecture V2.1 FROZEN 冲突

**本仓当前规则**：`docs/统一判定规范.md` 明确要求所有数值边界比较两侧先 `ROUND(value,6)`，`ROUND_HALF_UP` 后再执行 `< <= > >= == !=`。

**上位 FROZEN**：Architecture V2.1 明确规定 Numeric 默认：

- full-value comparison；
- 禁止 implicit rounding；
- 标准显式要求修约时才允许显式修约；
- 显示位数不得改变正式判定；
- 页面不得自行 round 后参与正式计算。

中央 Numeric DRAFT 进一步明确将“ECQuota 废止无标准依据的全局 ROUND6”列为迁移原则。

**判断**：这是无法通过单纯文档接入消除的硬冲突。QZC-A01 禁止修改算法和现有业务治理，因此只登记为 BLOCKED，不在本分支修复。

**后续要求**：单独立项，按标准原文/修改单证据区分：

- 标准明文要求修约：进入 Canonical explicit_round；
- 标准未要求修约：评估迁移到 full-value comparison；
- 用 GB 29446 Golden/Conformance case 验证边界变化；
- 不得由本次 Adoption 自动改变正式结果。

### 其他差距

Module/Capability、Workspace/Record、Unit、qzpack、Conformance 当前主要属于“尚未实施/部分满足”，没有发现与 FROZEN Architecture 形成第二项同等级硬冲突；本任务不把这些差距误报为已经完成。

## 8. RFC Candidates

### RFC-CANDIDATE-01 — ECQuota Recordable Business Outcomes

**问题**：当前 `Grade` 同时含 `INCOMPLETE`、`NOT_APPLICABLE` 与正式等级；中央 Workspace/Attempt/Record/Result DRAFT 明确要求 Business Outcome 与 Execution Error 分离，并在 D-005 留出各模块可保存 Outcome 的决定。

**为什么属于公共问题**：影响 Attempt/Record/Result 公共外围、Suite/跨平台历史记录一致性。

**影响 Contract**：Workspace / Attempt / Record / Result Contract。

**ECQuota真实案例**：`LEVEL_1/2/3/NOT_QUALIFIED/INCOMPLETE/NOT_APPLICABLE` 当前均由 `Grade` 表达。

**建议**：是。待 Numeric 冲突处理后，可用 GB 29446 作为记录语义试点，形成 RFC/模块规范候选。

### RFC-CANDIDATE-02 — `.uebench` 到 qzpack Prototype 映射

**问题**：ECQuota 已有成熟的签名 `.uebench` 标准包，但中央 qzpack 的签名算法、granularity、manifest schema、dependency 规则仍是 DRAFT/OPEN。

**为什么属于公共问题**：EquipEffi/GHGTOOL 未来也需要同一 Package Contract。

**影响 Contract**：qzpack / Canonical Package Contract；D-002、D-006。

**ECQuota真实案例**：当前已有 Ed25519、manifest、hash、full/incremental/parent lineage、安装校验和备份，可作为 prototype 输入，但不能直接升级为公共规范。

**建议**：是，但不是 QZC-A01 范围。等三个业务仓接入完成后统一决定。

## 9. 当前最小预留

为了以后不走偏，当前项目近期只需保持以下低成本预留，不要求本次实现：

1. 新增公共语义前先判断是否属于 Qingzhou-contracts；
2. 不再扩大无标准依据的全局 numeric 特例，Numeric 冲突解决前保留现状并明确标注；
3. 新增长期标识时避免与冻结 Module ID `qz.energy_quota` 冲突；
4. 新的正式结果字段尽量不要丢失 standard/rule/package/hash/provenance 信息；
5. 继续保持 Domain/Application 与 UI、SQLite、Excel 解耦；
6. 新的跨平台设计不要保存 Qt objectName/ComboBox index 作为业务 Workspace；
7. 新增标准包能力时保留 manifest/hash/version/rollback 方向，为 qzpack prototype 留接口；
8. Golden tests 后续可逐步整理成平台无关 Conformance candidates，但本任务不迁移测试格式。

## 10. 当前不做

本次明确不做：

- 不合仓；
- 不开发 Suite；
- 不开发移动端；
- 不重写 Native Core；
- 不把所有算法 DSL 化；
- 不全量 qzpack 化；
- 不因为统一架构重写成熟 UI；
- 不修改业务公式；
- 不修改 Canonical 标准数据；
- 不修改 evaluator/calculator；
- 不修改数据库 schema/migration；
- 不修改中央 Contract；
- 不将 DRAFT 宣称为 FROZEN。

## 11. CI / Tests 当前状态

基线 `d857f70acbc476f30decc2e0bd367d692a1447d1`：

- 仓库没有 `.github` 工作流目录；
- 该 head 未发现 GitHub Actions workflow run；
- `README.md` / `docs/仓库使用说明.md` 报告 2026-09-26 独立验收为 **303 项完整测试通过**；
- QZC-A01 仅修改治理文件，不修改 Python/JSON/DB/UI，因此本接入任务没有以“远程 CI 已通过”作虚假声明；
- 后续合并前若在本地可运行，仍建议执行既有源码回归/全量测试以确认工作树无意外污染。

## 12. Adoption Verdict

治理接入框架已能够建立：baseline/lock/upper-governance/adoption report 均可独立存在，且不要求业务重构。

但是由于 `BLOCKED-01` 为 Architecture V2.1 FROZEN 与当前本仓已确认 Numeric 治理的真实硬冲突：

> **QZC-A01 当前总体状态：BLOCKED（governance adoption established, full conformance blocked）。**

这不是代码故障，也不授权本任务修改 ROUND6。完成本分支后应由总负责人决定：

1. 是否允许先合并“带已知偏差的治理接入”；
2. 或先单独处理 Numeric 冲突，再完成最终 adoption 验收。
