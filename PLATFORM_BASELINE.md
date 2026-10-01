# PLATFORM_BASELINE

本项目当前锁定的 Qingzhou Contracts 上位治理基线。

## 1. 基线来源

- repository: `https://github.com/adgo07/Qingzhou-contracts.git`
- baseline type: **frozen-contract adoption baseline**
- contracts release/tag: **无（本次锁定精确 commit，不虚构 release/tag）**
- locked commit SHA: `ee5feb0cc34dbd99790500fadd0c4c932e202a20`
- locked date: `2026-10-01`
- module id: `qz.energy_quota`

本仓库只受上述锁定 commit 中已经存在且被本项目显式采用的公共治理内容约束，不自动采用 Qingzhou-contracts 后续 `main` 变化。

## 2. 版本与状态

| 项目 | 锁定版本/状态 | 权威文件 |
|---|---|---|
| Architecture | `2.1` — **FROZEN** | `docs/architecture/ARCHITECTURE_V2.1_FROZEN.md` |
| Numeric Contract | `v1` — **FROZEN / ADOPTED** | `contracts/numeric/NUMERIC_CONTRACT_V1_FROZEN.md` |
| Numeric Profiles | `v1` — **FROZEN / ADOPTED** | `contracts/numeric/NUMERIC_PROFILES_V1_FROZEN.md` |
| Numeric Conformance Vector | `v1` — **FROZEN / ADOPTED** | `conformance/common/numeric/CONFORMANCE_VECTOR_V1_FROZEN.md` |
| Unit Contract | `draft-v1` — **DRAFT** | `contracts/units/UNIT_CONTRACT_V1_DRAFT.md` |
| Module / Capability Contract | `draft-v1` — **DRAFT** | `contracts/module/MODULE_CAPABILITY_CONTRACT_V1_DRAFT.md` |
| Workspace / Attempt / Record / Result Contract | `draft-v1` — **DRAFT** | `contracts/records/WORKSPACE_ATTEMPT_RECORD_RESULT_CONTRACT_V1_DRAFT.md` |
| qzpack / Canonical Package Contract | `draft-v1` — **DRAFT** | `contracts/package/QZPACK_CONTRACT_V1_DRAFT.md` |

本次 Numeric v1 Adoption 不改变 Unit、Module、Record、qzpack 的 DRAFT 状态。

## 3. Numeric v1 项目实现基线

项目级 Numeric Profile：

`ECQUOTA_DECIMAL_FULL_VALUE_V1`

核心语义：

- authoritative representation：`Decimal`；
- working precision：`28`；
- working rounding mode：`ROUND_HALF_EVEN`；
- default formal comparison：`full-value exact`；
- implicit business rounding：禁止；
- business tolerance：默认无；
- display rounding：仅展示；
- explicit business rounding：仅允许标准/Rule 明确声明，并带 stage / mode / purpose / source；
- authoritative evaluation 使用 profile-owned Decimal context，隔离 caller ambient context。

GB 29446 原 N01-A behavior marker `ecquota-gb29446-full-value-v2` 继续保留为 migration/audit marker；正式 Numeric Profile ID 为 `ECQUOTA_DECIMAL_FULL_VALUE_V1`。

正式新结果至少可追踪：

- `numeric_contract_version`；
- `numeric_profile_id`；
- `calculator_version`；
- `rule_revision`；
- `numeric_behavior_version`。

历史记录不自动重算，旧 JSON 仍可按可选 Numeric 元数据字段读取。

## 4. 已知公共 Contract 偏差

### D-ECQ-001 — CLOSED：全局 ROUND6 与 full-value 冲突

Numeric v1 Full Adoption 已取消公共 Engine 中无依据默认 ROUND6：

- grade 默认直接使用 Decimal full-value comparison；
- compliance 默认直接使用 Decimal full-value comparison；
- `_round_threshold_value()` / 全局 `ROUND(value, 6)` 正式比较机制已移除；
- 现有 published definitions 中 `round_places` 使用数为 `0`；
- 如未来标准确有显式修约要求，必须通过带 authority metadata 的 explicit Rule rounding 表达。

因此 `D-ECQ-001-global-round6-vs-frozen-full-value` 已关闭。

### D-ECQ-002 — Module / Capability Manifest 尚未实施

中央架构冻结了永久 Module ID `qz.energy_quota`，但当前产品尚未实现正式 Module/Capability Manifest。当前只在治理层登记 Module ID。

### D-ECQ-003 — Workspace / Attempt / Record / Result 公共外围尚未完整实施

当前已有 `EvaluationRequest`、`EvaluationResult`、保存记录、规则快照和审计能力，并已增加 Numeric v1 最小 traceability；但尚未形成中央 DRAFT 所描述的完整 Workspace / Attempt / Record / Result Envelope。

### D-ECQ-004 — qzpack 尚未实施

当前 `.uebench` 签名标准包并非 Qingzhou `qzpack` Contract 的正式实现。

### D-ECQ-005 — Unit Contract 尚未正式采用

Numeric Conformance v1 已正式接入；Unit Contract 仍为 DRAFT，现有单位字段与校验不得描述成 Unit Contract v1 已采用。

### D-ECQ-006 — lossless XLSX numeric-cell 公共方案仍 OPEN

实测证明：高精度 XLSX numeric cell 可被 openpyxl 物化为 Python binary float，并跨越 full-value 业务边界。

本项目已做最小安全修复：

- authoritative XLSX 数值单元格若被 openpyxl 读成 `float`，导入直接报错；
- 模板正式数值列设为文本格式，要求十进制 lexical text；
- 不再允许 `float -> str -> Decimal` 静默成为正式业务值。

中央统一 lossless XLSX numeric-cell interchange scheme 仍 OPEN，因此保留本 deviation；但该 OPEN 项不再构成 Numeric v1 Full Adoption 的 authoritative-path 违规。

## 5. 权威关系

1. 标准原文、正式修改单和更具体的法定/标准专属要求优先于通用公共 Contract；
2. Numeric Contract v1 的默认正式比较语义为 full-value exact；
3. 标准或正式 Rule 如要求显式修约，必须保留其来源和应用阶段；
4. 显示精度不得反馈正式 comparison；
5. Unit、Module、Record、qzpack 当前仍按 DRAFT 边界治理；
6. 中央后续 commit 不会自动改变本项目行为。

## 6. Conformance 与回归要求

本项目 Numeric v1 Adoption 的正式证据包括：

- `tests/conformance/numeric/ecquota_numeric_v1_vectors.json`；
- `tests/conformance/numeric/conformance_vector_v1.schema.json`；
- `tests/conformance/numeric/test_ecquota_numeric_v1.py`；
- 原 N01-A migration evidence；
- `.github/workflows/numeric-v1-adoption.yml`。

任何后续修改 Numeric Profile、formal comparison、explicit rounding、tolerance、authoritative ingress 或 traceability 时，必须运行对应 Frozen Numeric v1 Conformance 和完整回归。

## 7. Upgrade Rule

- 本项目不得自动跟随 `Qingzhou-contracts/main`；
- 中央仓出现新 commit 不会自动改变本项目行为；
- 升级必须显式修改本文件与 `platform-lock.json`；
- 有正式 release/tag 后优先锁定 release/tag + 精确 SHA；
- 升级后运行适用公共 Conformance 与本项目完整回归；
- 如发现公共 Contract 缺口，记录 RFC candidate，不能在本项目永久私自发明同名不同义的公共规则。
