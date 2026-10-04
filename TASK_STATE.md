# TASK_STATE

更新时间：2026-10-03

## 当前产品目标

> **下一正式版必须完整支持 GB 29446—2019《选煤电力消耗限额》。**

Reference Standard：`GB 29446—2019 选煤电力消耗限额`
Module ID：`qz.energy_quota`
Canonical repository：`https://github.com/adgo07/ECQuota-Insight.git`

总体路线唯一入口：`参考标准开发路线.md`。

## 当前任务

**`ECQ-RS05` — `IN PROGRESS / RELEASE CANDIDATE`**（Windows V1 Release Candidate）

- `ECQ-GOV01 = DONE`（验收载体 PR #8）；
- `ECQ-RS01 = DONE`（验收载体 PR #9）；
- `ECQ-RS02 = DONE`（验收载体 PR #10）；
- `ECQ-RS03 = DONE`（验收载体 PR #11）；
- `ECQ-RS04 = DONE`（验收载体 PR #12）；
- **`ECQ-RS05 = IN PROGRESS / RELEASE CANDIDATE`**（验收载体 PR #13）——
  **不得**在本阶段写成 `DONE` 或 `UEBench 0.2.0 = RELEASED`；
  只有独立验收 + merge + final release cut 之后才能写 `DONE`；
- 目标版本：**`UEBench 0.2.0`**；唯一版本源为 `pyproject.toml` `[project] version`，
  其余正式发布链文件由 `tools/release_version.py` 生成或读取；
- `GB29446 Business Capability = COMPLETE`；`GB29446 Product Lifecycle = COMPLETE`；
  `GB29446 Excel Adapter = COMPLETE`；**`GB29446 Product Golden = ADOPTED (v1)`**；
- `Reference Standard 产品证据 = READY FOR RS05 WINDOWS ACCEPTANCE`；
- `Reference Standard Product Closure = PARTIAL`（尚欠 RS05 完成）；
- 本质检视结论：**Reference Standard Product Closure 保持 `PARTIAL`**，
  `D-ECQ-006` 仍 **OPEN**。

### RS05 Blocker 状态

**已关闭 Blocker 1（固定标准包内 GB29446 定义落后）** —— 项目负责人批准方案 B 后执行：
以已签名 `2026.09-published.2`（SHA256 `4f025b8a…1727`）为父基线，**只**把 GB29446 定义
由 `rule_revision=1` 替换为当前 `rule_revision=2`，其余 46 项标准内容逐字节保持不变，
重新签名生成新的完整正式标准包 `2026.10-published.3`（SHA256 `14db53be…32b0`）。
全程未使用 `统一标准规则确认表.xlsx`。RS04 Product Golden 回放 15/15 通过，
冻结 EXE 自检由 `exit 1` 变为 `exit 0`。详见 `release/standard-packages/PIN.json` 与
`docs/governance/RS05_EXECUTION_REPORT.md` §5.2A/§7.4。

**未关闭 Blocker 2（Windows 验收证据不完整，如实记录）**
2. **Windows 验收证据不完整（如实记录，不伪造 PASS）**
   - 本机仅有 **Windows 10 Build 19045**，**无 Windows 11 环境** → `BLOCKED`；
   - 本机仅 **1 个显示器**，无法实测“不同 DPI 显示器之间拖动窗口” → `BLOCKED`；
   - **DPI 100/125/150/175/200 五档实机实测** → `BLOCKED`；
   - 标准（非管理员）账户、Windows 10 实机 → `PASS`；
   - 离线运行 → 本次为 `OBSERVED-ONLINE`，需在断网验收机复测。

- RS05 的两个未关闭 blocker 见本文件“当前任务”一节；
> `READY FOR RS05 WINDOWS ACCEPTANCE` **不等于“可发布”**；Windows 正式交付证据尚未建立。
>
> 本文件只记录稳定状态。PR head SHA、审查进度与合并状态一律以对应 PR 为准，不写入本文件。

## 当前治理基线

| 项目 | 值 |
|---|---|
| 中央锁定 SHA | `ee5feb0cc34dbd99790500fadd0c4c932e202a20`（见 `platform-lock.json`，`auto_follow_main: false`） |
| Frozen Contract | Architecture V2.1；Numeric Contract v1；Numeric Profiles v1；Numeric Conformance Vector v1 |
| DRAFT（未采用） | Unit Contract；Module/Capability Contract；Workspace/Attempt/Record/Result Contract；qzpack Contract |
| 项目 Numeric Profile | `ECQUOTA_DECIMAL_FULL_VALUE_V1` |

## 已完成

- Qingzhou-contracts Governance Adoption（`PLATFORM_BASELINE.md` / `platform-lock.json`）；
- Architecture V2.1 baseline；
- Numeric Contract v1 Adoption；
- Numeric Profile / Numeric Conformance（Frozen v1，可执行）；
- implicit ROUND6 移除（`D-ECQ-001` 已关闭）；
- GB29446 Calculator / Numeric 主链；
- GB29446 专用页面基础；
- RS01 业务 Gate：两煤种、12 个 k、分级 / 边界、异常输入、原文入口与动态依据；
- GB29446 `data` / `scope-63` Definition 语义一致，开发库索引 hash 修复、目录规则修订号同步为 2；
- 非有限 Decimal 入口拒绝；有限 `1e999` 可正常计算，没有新增业务上限；
- RS02 产品生命周期：原记录只读、跨进程恢复、快照保真、基于原记录新评价；
- RS03 Excel Adapter：Profile 参数化、专用模板与 `_meta`、text 十进制 lexical 权威入口、
  SHA 提交保护、`evaluated` 生命周期、单一正式 use case `evaluate_workbook`；
- RS04 Product Golden v1（见“当前任务”）。

Numeric v1 已完成，**不再重新设计 ROUND6**。

## 当前路线与阶段状态

```text
ECQ-GOV01 治理清理与路线收口                        DONE
→ RS01 GB29446 业务 Vertical Slice 闭环              DONE
→ RS02 GB29446 产品生命周期闭环                      DONE
→ RS03 GB29446 Excel Adapter 闭环                    DONE
→ RS04 GB29446 Product Golden Gate                   DONE
→ RS05 Windows V1 最终验收与发布                     IN PROGRESS / RELEASE CANDIDATE  ← 当前阶段
→ RS06 第二标准架构验证                              NOT STARTED
```

阶段定义与验收条件见 `参考标准开发路线.md`。

## 当前真实能力状态

| 能力 | 状态 |
|---|---|
| Numeric Contract v1 / Profile / Conformance | `DONE` |
| GB29446 Calculator / Numeric 主链 | `DONE` |
| GB29446 业务 Vertical Slice 完整闭环 | `DONE`（业务能力 `COMPLETE`） |
| GB29446 产品生命周期闭环（保存 / 历史恢复） | `DONE`（Product Lifecycle = `COMPLETE`） |
| GB29446 Excel Adapter 闭环 | `DONE`（Excel Adapter = `COMPLETE`） |
| GB29446 Product Golden | `ADOPTED (v1)` |
| Reference Standard 产品证据 | `READY FOR RS05 WINDOWS ACCEPTANCE` |
| Reference Standard Product Closure | `PARTIAL`（尚欠 RS05） |
| Windows V1 最终验收与发布 | `IN PROGRESS / RELEASE CANDIDATE`（RS05 进行中，未 DONE） |
| 第二标准架构验证 | `NOT STARTED`（RS06 处理） |

## 发布物状态

- **上一正式发布物 / Previous Release**：`UEBench 0.1.0`、standard package `2026.09-published.2`。历史已发布版本，**不代表当前 main 源码**。
- **当前 Candidate / Current Release Candidate**：`UEBench 0.2.0`（RS05 产出；**未正式发布**，待独立验收与 final release cut）。
  便携包 / 安装程序 / 源码包的文件名与 SHA256 以交付目录中的 `SHA256SUMS.txt` 与 `release-build-info.json` 为准，不在本文件内固定。
- **当前开发源码 / Current Development Source**：以执行时实际 `main` SHA 为准。

## 当前 OPEN

中央已登记偏差（权威清单见 `platform-lock.json` 的 `known_deviations`）：

- `D-ECQ-002` Module/Capability Manifest 尚未正式实施；
- `D-ECQ-003` Workspace/Attempt/Record/Result 公共外围仅部分具备；
- `D-ECQ-004` 现有 `.uebench` 包不是正式 qzpack v1；
- `D-ECQ-005` Unit Contract 仍未正式采用；
- `D-ECQ-006` 中央 lossless XLSX numeric-cell 公共方案仍 OPEN。RS03 已把本仓 Excel 权威入口收紧为 text 十进制 lexical，RS04 的 Excel 安全语义案例继续以此为前提，但这**不表示中央公共方案已冻结**。

标准问题：

- `ECQ-STD-GB29446-001` —— 状态 `PROVISIONAL`，见 `STANDARD_ISSUES_REGISTER.md`。
  RS04 **未关闭**该问题，也**未**写成官方解释；Golden 的 full-value trap 案例只把当前软件口径
  冻结为可回归的产品证据。

**RS05 已修复（RS04 登记的 Release Gate）**：

- `corrupted historical result_json` 爆炸半径：RS05 已在 infrastructure 层按行隔离反序列化，
  单条损坏记录降级显示并记录 WARNING，不再中断“评价记录”页、首页或应用启动；
  detail 明确提示“记录损坏”，不伪装成“已删除 / 不存在”。详见 RS05 执行报告。

其他 Deferred（仅登记）：

- 现有“规则确认表”机制作为 legacy publication gate 保留；后续可在不降低标准可追溯性的前提下单独简化
  （`tools/publish_confirmed_rules.py` 本阶段不修改）；
- `data/catalog.json` 中 `gb-29435-2025` 的 `lifecycle_status` 与定义文件不一致。
  **只登记，不修改任何标准数据**，应在后续独立任务中收口；
- 历史列表 `result-json` 性能优化（RS02 deferred）仍未处理。

## RS05 本轮补充：运行时标准包对账 与 Candidate 身份闭环

- **已实现启动期标准包对账**（替代原“只要库里有标准就跳过”的一次性初始化）：
  空库安装 / 已同包 NO-OP（不重复备份、不重复安装）/ 旧包安全升级 /
  已装更新包不降级 / 同版本或内容冲突不覆盖并提示 / 内置包验签失败不安装。
  版本排序复用既有 `_data_version_key`，未另造第二套版本算法。
- **升级数据安全**：升级前用现有安全备份能力（`pre-package-<时间>.uebackup`），
  安装单事务、失败回滚、不留半升级状态；历史评价及其规则快照不被新规则重算。
- **GB29446 fail-fast**：当前定义缺少正式 r2 结构（煤种维度 / 工艺系数）时明确提示
  「标准规则数据不完整或版本不兼容」、禁止正式计算，不再用产品名冒充煤种。
- **Candidate 身份**：RC 阶段资产名与 CI artifact 名携带 `-rc-<short7>`；
  `release-build-info.json` 记录 `product_version` / `candidate_id` / `source_commit`(40位) /
  `source_dirty` / 标准包身份 / `payload_tree_sha256` / `build_time_utc`；
  正式 Candidate 要求 `source_dirty=false`；CI 校验 `source_commit` 与 exact head 一致。
- **应用内诊断**：菜单「帮助 → 关于 / 诊断信息…」可查看并复制产品版本、Candidate 身份、
  源码提交、内置/已安装标准包 id 与数据版本、标准包 SHA256、GB29446 `rule_revision`、
  DB schema、数据目录与最近一次对账结果。
- **单一 ACTIVE Candidate**：旧的 `dist/candidate` 已归档为
  `dist/archive/SUPERSEDED-candidate-2026-10-04-before-identity`（含 SHA256 证据）；
  构建脚本在组装前清空输出目录并写入 `ACTIVE-CANDIDATE.json`。
- 状态仍为 **`RS05 = IN PROGRESS / RELEASE CANDIDATE`**；`D-ECQ-006` 继续 OPEN；
  `Reference Standard Product Closure = PARTIAL`。

## 下一步

- `ECQ-GOV01 = DONE`；`ECQ-RS01 = DONE`；`ECQ-RS02 = DONE`；`ECQ-RS03 = DONE`；`ECQ-RS04 = DONE`；
- 当前阶段 = **`RS05` — Windows V1 最终验收与发布**（`IN PROGRESS / RELEASE CANDIDATE`）；RS06 未开始；
- `READY FOR RS05 WINDOWS ACCEPTANCE` 不等于“可发布”；Windows 正式交付证据尚未建立；
- 历史便携 ZIP 缺失仍是已知发布资产问题；具体执行证据见对应 PR，不据此宣布 Windows 最终交付完成。

本任务停在 RS05 候选阶段，未开始 RS06。
