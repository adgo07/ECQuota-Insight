# TASK_STATE

更新时间：2026-10-02

## 当前产品目标

> **下一正式版必须完整支持 GB 29446—2019《选煤电力消耗限额》。**

Reference Standard：`GB 29446—2019 选煤电力消耗限额`
Module ID：`qz.energy_quota`
Canonical repository：`https://github.com/adgo07/ECQuota-Insight.git`

总体路线唯一入口：`参考标准开发路线.md`。

## 当前任务

**`ECQ-RS03` — `DONE`**（GB29446 Excel Adapter 闭环）

- `ECQ-GOV01 = DONE`（验收载体 PR #8）；
- `ECQ-RS01 = DONE`（验收载体 PR #9）；
- `ECQ-RS02 = DONE`（验收载体 PR #10）；
- `ECQ-RS03 = DONE`（验收载体 PR #11）；
- `GB29446 Business Capability = COMPLETE`；
- `GB29446 Product Lifecycle = COMPLETE`；
- `GB29446 Excel Adapter = COMPLETE`；
- `Reference Standard Product Closure = PARTIAL`（尚欠 RS04–RS05）；
- Excel 仅为 Adapter：模板 / 结构 / metadata / 类型校验 → Canonical `EvaluationRequest` → 同一个 `EvaluationService` → 同一个 `EvaluationEngine` → 同一个正式 Record；
- 权威数值入口收紧为 text 十进制 lexical；XLSX numeric cell（int / float）与 Excel 公式（含缓存值）一律拒绝；
- 正式入口 `ApplicationFacade.evaluate_workbook(import_id)`；批次成功后为 `evaluated`，失败保持 `validated` 可重试；
- 验收证据：`tests/test_gb29446_excel_adapter.py`、更新后的 `tools/qzc_n01_a_excel_ingress_probe.py`、RS01 / RS02 / Numeric 回归；
- 下一阶段 `RS04` = `NOT STARTED`；本任务未实施 RS04–RS06。

本文件只记录稳定状态。PR head SHA、审查进度与合并状态一律以对应 PR 为准，不写入本文件。

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
- 非有限 Decimal 入口拒绝；有限 `1e999` 可正常计算，没有新增业务上限。

Numeric v1 已完成，**不再重新设计 ROUND6**。

## 当前路线与阶段状态

```text
ECQ-GOV01 治理清理与路线收口                        DONE
→ RS01 GB29446 业务 Vertical Slice 闭环              DONE
→ RS02 GB29446 产品生命周期闭环                      DONE
→ RS03 GB29446 Excel Adapter 闭环                    DONE
→ RS04 GB29446 Product Golden Gate                   NOT STARTED  ← 下一阶段
→ RS05 Windows V1 最终验收与发布                     NOT STARTED
→ RS06 第二标准架构验证                              NOT STARTED
```

阶段定义与验收条件见 `参考标准开发路线.md`。

## 当前真实能力状态

| 能力 | 状态 |
|---|---|
| Numeric Contract v1 / Profile / Conformance | `DONE` |
| GB29446 Calculator / Numeric 主链 | `DONE` |
| GB29446 业务 Vertical Slice 完整闭环 | `DONE`（业务能力 `COMPLETE`） |
| Reference Standard Product Closure | `PARTIAL`（RS04–RS05 尚未完成） |
| GB29446 产品生命周期闭环（保存 / 历史恢复） | `DONE`（Product Lifecycle = `COMPLETE`） |
| GB29446 Excel Adapter 闭环 | `DONE`（Excel Adapter = `COMPLETE`） |
| GB29446 Product Golden Gate | `NOT STARTED`（RS04 处理） |
| Windows V1 最终验收与发布 | `NOT STARTED`（RS05 处理） |
| 第二标准架构验证 | `NOT STARTED`（RS06 处理） |

## 发布物状态

- **上一正式发布物 / Previous Release**：`UEBench 0.1.0`、standard package `2026.09-published.2`。历史已发布版本，**不代表当前 main 源码**。
- **当前开发源码 / Current Development Source**：以执行时实际 `main` SHA 为准；正在开发下一正式版；RS05 完成前不把旧 EXE 当作当前源码正式 Candidate。

## 当前 OPEN

中央已登记偏差（权威清单见 `platform-lock.json` 的 `known_deviations`）：

- `D-ECQ-002` Module/Capability Manifest 尚未正式实施；
- `D-ECQ-003` Workspace/Attempt/Record/Result 公共外围仅部分具备；
- `D-ECQ-004` 现有 `.uebench` 包不是正式 qzpack v1；
- `D-ECQ-005` Unit Contract 仍未正式采用；
- `D-ECQ-006` 中央 lossless XLSX numeric-cell 公共方案仍 OPEN。RS03 已把本仓 Excel 权威入口收紧为 text 十进制 lexical，但这**不表示中央公共方案已冻结**。

标准问题：

- `ECQ-STD-GB29446-001` —— 状态 `PROVISIONAL`，见 `STANDARD_ISSUES_REGISTER.md`。

治理层 Deferred（不在 RS03 处理，仅登记）：

- 现有"规则确认表"机制作为 legacy publication gate 保留；后续可在不降低标准可追溯性的前提下单独简化（`tools/publish_confirmed_rules.py` 本任务不修改）；
- `data/catalog.json` 中 `gb-29435-2025` 的 `lifecycle_status` 与定义文件不一致。**RS03 只登记，不修改任何标准数据**，应在后续独立任务中收口；
- corrupted / unparsable 历史行隔离与历史列表 result-json 性能优化仍留待 RS04 前治理（RS02 deferred）。

## 下一步

- `ECQ-GOV01 = DONE`；`ECQ-RS01 = DONE`；`ECQ-RS02 = DONE`；`ECQ-RS03 = DONE`；
- 下一阶段 = **`RS04` — GB29446 Product Golden Gate**（`NOT STARTED`）；RS05–RS06 均未开始；
- 历史便携 ZIP 缺失仍是已知发布资产问题；具体执行证据见对应 PR，不据此宣布 Windows 最终交付完成。

本任务停在 RS03，未开始 RS04。
