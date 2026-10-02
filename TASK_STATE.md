# TASK_STATE

更新时间：2026-10-02

## 当前产品目标

> **下一正式版必须完整支持 GB 29446—2019《选煤电力消耗限额》。**

Reference Standard：`GB 29446—2019 选煤电力消耗限额`
Module ID：`qz.energy_quota`
Canonical repository：`https://github.com/adgo07/ECQuota-Insight.git`

总体路线唯一入口：`参考标准开发路线.md`。

## 当前任务

`ECQ-GOV01 — 仓库治理清理 + 参考标准开发路线收口`

- 性质：治理 / 文档 / 路线收口，**不是业务开发**；
- 目标：清除会误导后续开发的过时状态、重复治理、历史发布表述和无必要人工确认要求；确立"下一正式版完整支持 GB29446"为唯一主线；将总体路线改为中文文件名 `参考标准开发路线.md`。

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
- GB29446 专用页面基础。

Numeric v1 已完成，**不再重新设计 ROUND6**。

## 当前路线

```text
ECQ-GOV01
→ RS01 GB29446 业务 Vertical Slice 闭环
→ RS02 GB29446 产品生命周期闭环
→ RS03 GB29446 Excel Adapter 闭环
→ RS04 GB29446 Product Golden Gate
→ RS05 Windows V1 最终验收与发布
→ RS06 第二标准架构验证
```

阶段定义与验收条件见 `参考标准开发路线.md`。

## 当前真实能力状态

| 能力 | 状态 |
|---|---|
| Numeric Contract v1 / Profile / Conformance | `DONE` |
| GB29446 Calculator / Numeric 主链 | `DONE` |
| GB29446 业务 Vertical Slice 完整闭环 | `PARTIAL`（RS01 处理） |
| GB29446 产品生命周期闭环（保存 / 历史恢复） | `PARTIAL`（RS02 处理） |
| GB29446 Excel Adapter 闭环 | `PARTIAL`（RS03 处理） |
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
- `D-ECQ-006` 中央 lossless XLSX numeric-cell 公共方案仍 OPEN。

标准问题：

- `ECQ-STD-GB29446-001` —— 状态 `PROVISIONAL`，见 `STANDARD_ISSUES_REGISTER.md`。

治理层 Deferred（不在 GOV01 处理，仅登记）：

- 现有"规则确认表"机制作为 legacy publication gate 保留；后续可在不降低标准可追溯性的前提下单独简化（`tools/publish_confirmed_rules.py` 本任务不修改）；
- 开发库 `standards/development/library-index.json` 记录的 `definition_sha256` 与实际定义文件不一致，根因是 `data/definitions/` 与 `standards/development/scope-63/definitions/` 存在两份同义但字节不同的 GB29446 定义副本。**GOV01 只登记，不修改任何标准数据**，应在后续独立任务中收口；
- `data/catalog.json` 中 `gb-29435-2025` 的 `lifecycle_status` 与定义文件不一致。**GOV01 只登记，不修改任何标准数据**，应在后续独立任务中收口。

## 下一步

GOV01 完成后：下一任务 = **RS01**。

本任务停在 GOV01 完成状态，不开始 RS01。
