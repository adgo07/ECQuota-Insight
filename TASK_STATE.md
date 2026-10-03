# TASK_STATE

更新时间：2026-10-03

## 当前产品目标

> **下一正式版必须完整支持 GB 29446—2019《选煤电力消耗限额》。**

Reference Standard：`GB 29446—2019 选煤电力消耗限额`
Module ID：`qz.energy_quota`
Canonical repository：`https://github.com/adgo07/ECQuota-Insight.git`

总体路线唯一入口：`参考标准开发路线.md`。

## 当前任务

**`ECQ-RS04` — `DONE`**（GB29446 Product Golden Gate）

- `ECQ-GOV01 = DONE`（验收载体 PR #8）；
- `ECQ-RS01 = DONE`（验收载体 PR #9）；
- `ECQ-RS02 = DONE`（验收载体 PR #10）；
- `ECQ-RS03 = DONE`（验收载体 PR #11）；
- `ECQ-RS04 = DONE`（验收载体 PR #12）；
- `GB29446 Business Capability = COMPLETE`；
- `GB29446 Product Lifecycle = COMPLETE`；
- `GB29446 Excel Adapter = COMPLETE`；
- **`GB29446 Product Golden = ADOPTED (v1)`**；
- **`Reference Standard 产品证据 = READY FOR RS05 WINDOWS ACCEPTANCE`**；
- `Reference Standard Product Closure = PARTIAL`（尚欠 RS05）；
- Golden v1 由标准原文（表1 / 表2 / 式(1) / 附录A 表A.1）+ 已发布 Definition + Numeric Contract v1
  **独立推导**，**未**使用软件输出反向生成；
- 产物：`tests/golden/gb29446_product_golden_v1.json`、
  `tests/test_gb29446_product_golden.py`、`docs/golden/GB29446_PRODUCT_GOLDEN_V1.md`；
- 四类 Gate：A 业务 Golden（13 个正常案例 + 2 个安全案例）、B 产品生命周期（真实独立进程重启）、
  C Excel Golden（GUI Request == Excel Request，两条路径投影 == Golden）、D Regression；
- 覆盖：12 个附录A 系数、两煤种、1/2/3级与超出3级、6 个 exact threshold、
  1 个 full-value trap（`5.0000004 → 2级`）；
- 下一阶段 `RS05` = `NOT STARTED`；本任务未实施 RS05–RS06。

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
→ RS05 Windows V1 最终验收与发布                     NOT STARTED  ← 下一阶段
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
- `D-ECQ-006` 中央 lossless XLSX numeric-cell 公共方案仍 OPEN。RS03 已把本仓 Excel 权威入口收紧为 text 十进制 lexical，RS04 的 Excel 安全语义案例继续以此为前提，但这**不表示中央公共方案已冻结**。

标准问题：

- `ECQ-STD-GB29446-001` —— 状态 `PROVISIONAL`，见 `STANDARD_ISSUES_REGISTER.md`。
  RS04 **未关闭**该问题，也**未**写成官方解释；Golden 的 full-value trap 案例只把当前软件口径
  冻结为可回归的产品证据。

**RS05 Release Gate（RS04 登记，未修复）**：

- `corrupted historical result_json` 爆炸半径：`SqlEvaluationRepository.list_recent()` 逐行
  `EvaluationResult.model_validate_json(row.result_json)` 且**无异常隔离**
  （`src/uebench/infrastructure/repositories.py:293`），单条损坏会使整个“评价记录”页与首页
  最近记录加载失败。分类 `LOCAL DEFECT`，**不是** RS04 Golden Adoption 的 blocker，
  须在 RS05 Windows 正式交付前处理。详见 `docs/golden/GB29446_PRODUCT_GOLDEN_V1.md` §11.2。

其他 Deferred（仅登记）：

- 现有“规则确认表”机制作为 legacy publication gate 保留；后续可在不降低标准可追溯性的前提下单独简化
  （`tools/publish_confirmed_rules.py` 本阶段不修改）；
- `data/catalog.json` 中 `gb-29435-2025` 的 `lifecycle_status` 与定义文件不一致。
  **只登记，不修改任何标准数据**，应在后续独立任务中收口；
- 历史列表 `result-json` 性能优化（RS02 deferred）仍未处理。

## 下一步

- `ECQ-GOV01 = DONE`；`ECQ-RS01 = DONE`；`ECQ-RS02 = DONE`；`ECQ-RS03 = DONE`；`ECQ-RS04 = DONE`；
- 下一阶段 = **`RS05` — Windows V1 最终验收与发布**（`NOT STARTED`）；RS06 未开始；
- `READY FOR RS05 WINDOWS ACCEPTANCE` 不等于“可发布”；Windows 正式交付证据尚未建立；
- 历史便携 ZIP 缺失仍是已知发布资产问题；具体执行证据见对应 PR，不据此宣布 Windows 最终交付完成。

本任务停在 RS04，未开始 RS05。
