# PLATFORM_ADOPTION_REPORT

任务：`QZC-A01 — 接入 Qingzhou-contracts 公共治理`  
接入日期：2026-09-28  
业务仓：`adgo07/ECQuota-Insight`  
业务仓基线 main SHA：`d857f70acbc476f30decc2e0bd367d692a1447d1`  
工作分支：`chore/qingzhou-contracts-adoption`

## 1. 最终结论

> **Governance Adoption PASS / Numeric Conformance BLOCKED**

解释：

- **Governance Adoption PASS**：本仓已经建立版本锁定的 Qingzhou-contracts 上位治理关系，接入文件完整，且未修改业务代码、算法、UI、数据库或 Canonical 标准数据。
- **Numeric Conformance BLOCKED**：ECQuota 当前全局 ROUND6 治理与 Architecture V2.1 FROZEN 的默认 full-value comparison 存在真实冲突；本任务只登记，不处理 ROUND6，也不因此阻止治理接入文件合并。
- 本结论不表示 ECQuota 已完全符合全部 Qingzhou Contract，仅表示 **QZC-A01 治理接入本身通过**。

## 2. 当前仓信息

- repo：`https://github.com/adgo07/ECQuota-Insight.git`
- default branch：`main`
- baseline head：`d857f70acbc476f30decc2e0bd367d692a1447d1`
- product：单位产品能耗对标软件（UEBench / ECQuota-Insight）
- Qingzhou module id：`qz.energy_quota`
- 当前业务阶段：GB 29446 专用评价页面源码已独立验收；仓库文档报告完整测试 303 项通过；新版 EXE/安装包及公式 Excel 尚未同步验收；正式范围 47 项，开发基线仍有 16 项草案。
- baseline 时仓库不存在 `AGENTS.md` 与 `TASK_STATE.md`；QZC-A01 在接入分支新增最小治理文件。

## 3. Qingzhou-contracts 锁定信息

公共仓：`https://github.com/adgo07/Qingzhou-contracts.git`

当前锁定：

- default branch：`main`
- locked commit：`0cd74d783fa23add6dc881b408a8c8ba8503f8e8`
- release/tag：**无**
- baseline type：**pre-release / bootstrap baseline**
- Architecture：`V2.1 FROZEN`
- Numeric Contract：`draft-v1` — **DRAFT / NOT YET RELEASED**
- Unit Contract：`draft-v1` — **DRAFT / NOT YET RELEASED**
- Module / Capability Contract：`draft-v1` — **DRAFT / NOT YET RELEASED**
- Workspace / Attempt / Record / Result Contract：`draft-v1` — **DRAFT / NOT YET RELEASED**
- qzpack / Canonical Package Contract：`draft-v1` — **DRAFT / NOT YET RELEASED**

本业务仓不得实时跟随 Qingzhou-contracts `main`。后续中央仓变化只有在显式升级 `PLATFORM_BASELINE.md` 与 `platform-lock.json` 后才对本仓生效。

## 4. Adoption Matrix

| 公共能力 | 当前状态 | 当前仓真实情况 | QZC-A01处理 |
|---|---|---|---|
| Domain/Application 与 UI 分离 | 已满足（结构层面） | `domain/application/infrastructure/ui` 已分层；现有审计记录 Domain 不依赖 Qt/SQLite/Excel | 仅记录 |
| Canonical-first | 部分满足 | 已有 JSON definitions、来源 SHA、结构化规则和签名 `.uebench` 包，但未具备完整公共 Envelope/Conformance | 记录差距 |
| Numeric | 部分满足 / **Conformance BLOCKED** | 使用 Decimal、拒绝 binary float；全局 ROUND6 与 FROZEN full-value comparison 冲突 | **只登记，不处理 ROUND6** |
| Unit | 部分满足 | 已保存单位并有部分单位一致性校验 | 后续对齐 |
| Module ID | 治理层已接入，运行层未实施 | FROZEN ID 为 `qz.energy_quota` | 不改运行代码 |
| Capability | 尚未实施 | 无正式 Capability Manifest / Conformance Gate | 后续实施 |
| Workspace | 尚未实施公共 Contract | 当前无平台无关 Workspace Envelope | 后续实施 |
| Attempt / Record | 部分满足 | 已有计算、保存、审计及规则快照；尚无公共 Attempt Envelope | 后续增量兼容 |
| Result | 部分满足 | 已有结构化 Result、trace、source refs、rule snapshot hash | 缺公共外围版本字段 |
| Conformance | 尚未正式实施 | 当前 pytest/Golden tests 不是公共平台无关 Conformance Vectors | 后续试点 |
| qzpack | 部分满足 / prototype-adjacent | `.uebench` 已有 manifest/hash/signature/version/parent/rollback 基础 | 不伪称 qzpack v1 |
| 跨平台 Workspace | 尚未实施 | 当前仍为 Windows Desktop | 当前不做 |

## 5. 已满足

### 5.1 分层基础

当前工程已形成：

```text
Presentation/UI
    ↓
Application
    ↓
Domain
    ↓
Infrastructure / Repository Adapter
```

现有 `docs/宏观结构审计-20260905.md` 已记录 Domain 不依赖 Qt、SQLite、Excel，方向与 Architecture V2.1 一致。

### 5.2 Decimal / float 防护

Domain 模型明确拒绝 float 进入规则和正式评价模型，正式数值以 Decimal 为主。这与公共 Numeric 的十进制确定性方向一致。

### 5.3 历史结果快照

当前评价保存 request、result、rule snapshot、evaluation id/timestamp 与 audit event，标准更新不会要求自动改写历史评价，方向与公共 Record 历史不漂移原则一致。

### 5.4 标准包可验证基础

现有 `.uebench` 已具备：

- manifest；
- SHA-256；
- Ed25519 签名；
- package id / data version；
- full/incremental 与 parent package；
- 安装验证、备份和部分回滚基础。

但当前 `.uebench` 不是正式 qzpack v1。

## 6. 部分满足与尚未实施

当前尚未完成或仅部分满足：

1. 公共 Canonical Envelope；
2. 正式 Unit Contract / UnitService / conversion id；
3. Qingzhou Module/Capability Manifest；
4. Capability Conformance Gate；
5. 平台无关 Workspace Contract；
6. 独立 Attempt 模型；
7. Attempt / Record / Result v1 公共 Envelope；
8. 公共 Result/Record 的 module/contract/package version 外围；
9. Qingzhou 平台无关 Conformance Vectors；
10. 正式 `.qzpack`；
11. `.qzproj`；
12. Suite / Mobile / Mini / macOS / Linux 正式实现；
13. Qingzhou 共享 Python/native core。

不得因为 Architecture V2.1 已存在就把以上内容描述成当前产品已经实现。

## 7. Numeric Conformance BLOCKED

### NC-B01 — ECQuota 全局 ROUND6 与 Architecture V2.1 FROZEN 冲突

本仓当前 `docs/统一判定规范.md` 要求所有数值边界比较两侧先 `ROUND(value,6)`，采用 `ROUND_HALF_UP` 后再执行比较。

Architecture V2.1 FROZEN 则规定公共默认：

- full-value comparison；
- 禁止无业务依据的 implicit rounding；
- 标准显式要求修约时才允许显式修约；
- 显示位数不得改变正式判定。

中央 Numeric DRAFT 进一步把 ECQuota 无标准依据的全局 ROUND6 列为后续迁移问题。

**本任务处理决定：**

- 不修改 `docs/统一判定规范.md`；
- 不修改 Engine；
- 不修改标准 Canonical 数据；
- 不修改正式判定结果；
- 不把 Numeric DRAFT 当作已经冻结的业务实现规则；
- 仅记录为 **Numeric Conformance BLOCKED**，另立后续任务处理。

因此该问题**不阻止 QZC-A01 Governance Adoption PASS**。

## 8. RFC Candidates

### RFC-CANDIDATE-01 — ECQuota Recordable Business Outcomes

当前 `Grade` 同时表达正式等级与 `INCOMPLETE`、`NOT_APPLICABLE` 等状态。公共 Workspace/Attempt/Record/Result DRAFT 要求区分业务 Outcome 与系统 Execution Error，但各模块哪些 Outcome 可形成 Record 仍是开放问题。

建议以后以 GB 29446 为真实案例形成模块规范/RFC 候选，本任务不改。

### RFC-CANDIDATE-02 — `.uebench` 到 qzpack Prototype 映射

ECQuota 现有 `.uebench` 已具备较成熟的 manifest、hash、签名、版本和 parent lineage，可作为 qzpack prototype 输入；但中央 qzpack 的签名治理、granularity、manifest schema 等仍是 DRAFT/OPEN。

建议等三个业务仓均接入后统一评估，本任务不改中央 Contract。

## 9. 当前最小预留

近期只保留低成本预留：

1. 新增公共语义前先判断是否属于 Qingzhou-contracts；
2. Numeric 冲突解决前不继续扩大无标准依据的全局 numeric 特例；
3. 新增长期标识时不与 `qz.energy_quota` 冲突；
4. 正式结果继续保留 standard/rule/package/hash/provenance 追溯信息；
5. 保持 Domain/Application 与 UI、SQLite、Excel 解耦；
6. 跨平台 Workspace 不保存 Qt objectName/ComboBox index 作为业务事实；
7. 标准包能力继续保留 manifest/hash/version/rollback 方向；
8. Golden tests 后续可整理为平台无关 Conformance candidates。

## 10. 当前不做

本次明确不做：

- 不合仓；
- 不开发 Suite；
- 不开发移动端；
- 不重写 Native Core；
- 不把所有算法 DSL 化；
- 不全量 qzpack 化；
- 不因为统一架构重写成熟 UI；
- **不处理 ROUND6**；
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
- QZC-A01 仅修改治理文件，不修改 Python/JSON/DB/UI；
- 因此本任务不虚构“新分支 CI 已通过”。

## 12. Merge Decision

QZC-A01 的治理接入目标已经完成，且 Numeric 冲突已明确隔离为后续事项。

> **Governance Adoption PASS / Numeric Conformance BLOCKED**

允许合并本次治理文件；合并本身不得被解释为 ROUND6 已处理或 Numeric Conformance 已通过。
