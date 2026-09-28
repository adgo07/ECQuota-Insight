# PLATFORM_BASELINE

本项目当前锁定的 Qingzhou Contracts 上位治理基线。

## 1. 基线来源

- repository: `https://github.com/adgo07/Qingzhou-contracts.git`
- baseline type: **pre-release / bootstrap baseline**
- contracts release/tag: **无（当前中央仓尚未发布正式 release/tag）**
- locked commit SHA: `0cd74d783fa23add6dc881b408a8c8ba8503f8e8`
- locked date: `2026-09-28`
- module id: `qz.energy_quota`

本仓库只受上述锁定 commit 中已经存在的公共治理内容约束，不自动采用 Qingzhou-contracts 后续 `main` 变化。

## 2. 版本与状态

| 项目 | 锁定版本/状态 | 权威文件 |
|---|---|---|
| Architecture | `2.1` — **FROZEN** | `docs/architecture/ARCHITECTURE_V2.1_FROZEN.md` |
| Numeric Contract | `draft-v1` — **DRAFT / NOT YET RELEASED** | `contracts/numeric/NUMERIC_CONTRACT_V1_DRAFT.md` |
| Unit Contract | `draft-v1` — **DRAFT / NOT YET RELEASED** | `contracts/units/UNIT_CONTRACT_V1_DRAFT.md` |
| Module / Capability Contract | `draft-v1` — **DRAFT / NOT YET RELEASED** | `contracts/module/MODULE_CAPABILITY_CONTRACT_V1_DRAFT.md` |
| Workspace / Attempt / Record / Result Contract | `draft-v1` — **DRAFT / NOT YET RELEASED** | `contracts/records/WORKSPACE_ATTEMPT_RECORD_RESULT_CONTRACT_V1_DRAFT.md` |
| qzpack / Canonical Package Contract | `draft-v1` — **DRAFT / NOT YET RELEASED** | `contracts/package/QZPACK_CONTRACT_V1_DRAFT.md` |

DRAFT 仅表示当前锁定 bootstrap baseline 中的试点参考，不得描述成 FROZEN，也不得在未显式升级 baseline 的情况下把中央仓后续修改自动视为本项目规则。

## 3. 权威关系

本项目采用以下原则：

1. 标准原文、正式修改单和更具体的法定/标准专属要求优先于通用公共 Contract；
2. Qingzhou Contracts 的 FROZEN 公共架构约束本项目的长期公共边界；
3. 已发布 Contract/Schema 在未来显式升级后成为对应公共语义的正式约束；
4. 当前 DRAFT Contract 仅按本文件锁定版本作为试点参考，不得自行宣称稳定；
5. 单产品合法自治范围继续由本仓库治理，普通产品 Bug、单标准公式、专属 UI 等仍在本仓解决。

## 4. 已知公共 Contract 偏差

### D-ECQ-001 — Numeric / 全局 ROUND6 硬冲突

当前本仓 `docs/统一判定规范.md` 要求所有数值边界在比较前统一 `ROUND(value, 6)`，并使用 `ROUND_HALF_UP`。

Qingzhou Architecture V2.1 FROZEN 则规定：

- 默认 full-value comparison；
- 禁止 implicit rounding；
- 只有标准或正式业务规则明确要求修约时，才允许显式修约；
- 显示位数不得改变正式判定。

因此这是当前已知的**真实上位治理冲突**。QZC-A01 只登记，不修改算法、规则或现有治理文件。本偏差必须在后续独立任务中依据标准证据和公共 Numeric 决策处理。

### D-ECQ-002 — Module / Capability Manifest 尚未实施

中央架构冻结了永久 Module ID `qz.energy_quota`，但当前产品尚未实现正式 Module/Capability Manifest。当前只在治理层登记 Module ID，不修改运行代码。

### D-ECQ-003 — Workspace / Attempt / Record / Result 公共外围尚未完整实施

当前已有 `EvaluationRequest`、`EvaluationResult`、保存记录、规则快照和审计能力，但尚未形成中央 DRAFT 所描述的完整 Workspace / Attempt / Record / Result Envelope，也没有跨平台 Workspace Contract。

### D-ECQ-004 — qzpack 尚未实施

当前 `.uebench` 签名标准包已经具备 manifest、SHA-256、Ed25519 签名、版本/父包和安装校验等能力，但并非 Qingzhou `qzpack` Contract 的正式实现。不得把现有 `.uebench` 包直接描述为已符合 qzpack v1。

### D-ECQ-005 — Unit / Conformance 公共契约尚未正式接入

当前代码已有单位字段、Decimal 计算、输入单位校验和产品测试，但尚无正式 Unit Contract 实现、公共 Unit ID/Conversion Contract，也尚无平台无关的 Qingzhou Conformance Vectors。

## 5. Upgrade Rule

- 本项目不得自动跟随 `Qingzhou-contracts/main`；
- 中央仓出现新 commit 不会自动改变本项目行为；
- 升级必须显式修改本文件与 `platform-lock.json`；
- 有正式 release/tag 后优先锁定 release/tag + 精确 SHA；
- 升级前检查 breaking changes、RFC/ADR/CHANGELOG；
- 升级后运行适用的公共 Conformance 与本项目完整回归；
- 如发现公共 Contract 缺口，记录 RFC candidate，不能在本项目永久私自发明同名不同义的公共规则。

## 6. 当前接入范围

本次 QZC-A01 仅建立治理锁定关系和差异记录：

- 不修改业务公式；
- 不修改 Canonical 标准数据；
- 不修改 evaluator/calculator；
- 不修改 UI；
- 不修改数据库 schema/migration；
- 不引入 Git Submodule；
- 不 vendor Qingzhou-contracts；
- 不创建公共 Python package；
- 不启动 Suite / Mobile / Native Core；
- 不修改中央 Contract。

详细差异见 `docs/governance/PLATFORM_ADOPTION_REPORT.md`。
