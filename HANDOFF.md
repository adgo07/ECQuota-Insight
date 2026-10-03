# HANDOFF — ECQuota 当前交接

更新时间：2026-10-02

> 本文件是**当前**交接入口，只描述现行权威状态。
> 历史材料（QZC-A01 bootstrap、Numeric DRAFT/BLOCKED 时期、UEBench 时期发布流水账、旧交付哈希、旧开发机绝对路径）已移至
> [`docs/history/legacy/HANDOFF_LEGACY_2026-09.md`](docs/history/legacy/HANDOFF_LEGACY_2026-09.md)（标注 `HISTORICAL`，非当前权威）。

## 1. 当前仓库身份

| 项目 | 值 |
|---|---|
| 产品名称 | 单位产品能耗限额评价软件（程序包名 `uebench`） |
| Module ID | `qz.energy_quota` |
| Canonical repository | `https://github.com/adgo07/ECQuota-Insight.git`（以 `git remote get-url origin` 为准） |
| 中央治理仓 | `https://github.com/adgo07/Qingzhou-contracts.git` |
| 默认分支 | `main` |

本地绝对路径只是当前运行环境，**不是仓库身份**。开工前必须实际执行 `git rev-parse --show-toplevel`、`git remote get-url origin`、`git branch --show-current`、`git rev-parse HEAD`、`git status --short`、`git fetch origin`，并确认 `origin` 与上述 Canonical repository 一致；不一致必须 `BLOCKED`。

## 2. 当前产品目标

> **下一正式版必须完整支持 GB 29446—2019《选煤电力消耗限额》。**

## 3. 当前 main / 当前治理基线

| 项目 | 值 |
|---|---|
| 上一正式发布物基线 | `main` 上的历史发布（`UEBench 0.1.0` / standard package `2026.09-published.2`） |
| **当前开发源码** | 以执行时实际 `main` SHA 为准；不要凭本文档记忆 SHA |
| 中央锁定 SHA | `ee5feb0cc34dbd99790500fadd0c4c932e202a20`（见 `platform-lock.json`，`auto_follow_main: false`） |
| Frozen Contract | Architecture V2.1；Numeric Contract v1；Numeric Profiles v1；Numeric Conformance Vector v1 |
| DRAFT（未采用） | Unit Contract；Module/Capability Contract；Workspace/Attempt/Record/Result Contract；qzpack Contract |

按当前治理规则，内部开发**不再**把"负责人手工逐字核对 64 位 SHA"当作日常 Gate；以脚本 / CI / release audit 输出为准。

## 4. Reference Standard

`GB 29446—2019 选煤电力消耗限额`

当前状态：**产品闭环 `PARTIAL`**。GB29446 Business Capability = `COMPLETE`；GB29446 Product Lifecycle = `COMPLETE`；GB29446 Excel Adapter = `COMPLETE`；**GB29446 Product Golden = `ADOPTED (v1)`**。RS01 / RS02 / RS03 / RS04 已完成，验收载体分别为 PR #9、PR #10、PR #11、PR #12。**Reference Standard 产品证据 = `READY FOR RS05 WINDOWS ACCEPTANCE`**；尚欠 Windows V1 最终验收。详见 `参考标准开发路线.md` 与 `docs/golden/GB29446_PRODUCT_GOLDEN_V1.md`。

> `READY FOR RS05 WINDOWS ACCEPTANCE` **不等于“可发布”**；Windows 正式交付证据尚未建立。

## 5. 当前 Numeric 规则

- 项目 Profile：`ECQUOTA_DECIMAL_FULL_VALUE_V1`（Decimal，working precision=28，working rounding=`ROUND_HALF_EVEN`，formal comparison=full-value exact，默认无 business epsilon）；
- 正式比较为 **full-value exact**，**不执行隐式 ROUND6**；`D-ECQ-001` 已关闭；
- explicit business rounding 只能由标准原文或正式 Rule 授权，并必须声明 stage / precision-or-places / mode / purpose / source；
- authoritative evaluation 使用 Profile-owned Decimal context，caller ambient context 不得静默改变正式结果；
- 正式结果可追踪 `numeric_contract_version`、`numeric_profile_id`、`calculator_version`、`rule_revision`、必要的 `numeric_behavior_version`；
- authoritative XLSX 数值若被 openpyxl 物化为 Python `float` 必须拒绝；模板正式数值列使用文本十进制输入。中央统一 lossless XLSX scheme 仍 OPEN（`D-ECQ-006`）。

> **不要再重新设计 ROUND6。** Numeric v1 已完成。
> Numeric 相关任务才需读取 `docs/统一判定规范.md` 与 `docs/governance/NUMERIC_V1_ADOPTION_REPORT.md`。

## 6. 当前产品能力

已完成：标准库 / 标准选择 / 新建评价 / 输入与校验 / Calculator / 等级 / Numeric v1 Conformance / GB29446 专用页面基础 / 标准包签名与安装 / 备份恢复 / 审计日志 / Excel 导入与导出报告 / Windows 打包链。

当前限制：

- 参考标准产品闭环仍为 `PARTIAL`（见第 4 节）；
- 47 项正式范围已发布，但开发基线 `standards/development/scope-63` 中仍有 16 项草案；
- GB 29435-2025 为 `published/future`，实施日期 2027-01-01 前只能预览；
- 当前只有 Windows 桌面版；Web / Linux / 安卓 / 苹果 / 鸿蒙 与网络更新仅为架构方向；
- 普通页面不含企业属性、单一煤种工艺确认及合规主结论；GB 29446 专用页面显示"超出3级"，覆盖早期规范中的"未达标"措辞。

## 7. 当前路线与阶段状态

```text
ECQ-GOV01 治理清理与路线收口                        DONE
→ RS01 GB29446 业务 Vertical Slice 闭环              DONE
→ RS02 GB29446 产品生命周期闭环                      DONE
→ RS03 GB29446 Excel Adapter 闭环                    DONE
→ RS04 GB29446 Product Golden Gate                   DONE
→ RS05 Windows V1 最终验收与发布                     NOT STARTED  ← 下一阶段
→ RS06 第二标准架构验证                              NOT STARTED
```

**唯一总体路线入口**：[`参考标准开发路线.md`](参考标准开发路线.md)。

## 8. 当前 OPEN

中央已登记偏差（权威清单见 `platform-lock.json` 的 `known_deviations`）：

- `D-ECQ-002` Module/Capability Manifest 尚未正式实施；
- `D-ECQ-003` Workspace/Attempt/Record/Result 公共外围仅部分具备；
- `D-ECQ-004` 现有 `.uebench` 包不是正式 qzpack v1；
- `D-ECQ-005` Unit Contract 仍未正式采用；
- `D-ECQ-006` 中央 lossless XLSX numeric-cell 公共方案仍 OPEN。

标准问题：

- `ECQ-STD-GB29446-001` —— 状态 `PROVISIONAL`，见 `STANDARD_ISSUES_REGISTER.md`。
  RS04 **未关闭**该问题，也**未**写成官方解释。

**RS05 Release Gate（RS04 登记，未修复）**：

- corrupted historical `result_json` 会使 `list_recent()` 整体失败
  （`src/uebench/infrastructure/repositories.py:293` 无异常隔离）。
  分类 `LOCAL DEFECT`，须在 RS05 Windows 正式交付前处理；
  详见 [`docs/golden/GB29446_PRODUCT_GOLDEN_V1.md`](docs/golden/GB29446_PRODUCT_GOLDEN_V1.md) §11.2。

## 9. 下一步

- `ECQ-GOV01 = DONE`；`ECQ-RS01 = DONE`；`ECQ-RS02 = DONE`；`ECQ-RS03 = DONE`；`ECQ-RS04 = DONE`；
- 下一阶段 = **`RS05` — Windows V1 最终验收与发布**（`NOT STARTED`）；RS06 未开始；
- RS01 业务 Gate：`tests/test_gb29446_reference_slice.py`；RS02 生命周期 Gate：`tests/test_gb29446_record_lifecycle.py`；RS03 Excel Adapter Gate：`tests/test_gb29446_excel_adapter.py`；**RS04 Product Golden Gate：`tests/test_gb29446_product_golden.py`**；
- Golden v1 数据：`tests/golden/gb29446_product_golden_v1.json`；说明：`docs/golden/GB29446_PRODUCT_GOLDEN_V1.md`；
- Golden 使用白名单业务投影比较，**禁止** `result.model_dump_json() == expected`；expected 由标准原文 / Definition / Numeric Contract 独立推导，**不得**由软件输出反向生成；
- Excel 仅为 Adapter：正式入口是 `ApplicationFacade.evaluate_workbook(import_id)`，计算仍由同一个 `EvaluationService` / `EvaluationEngine` 执行；权威数值入口为 text 十进制 lexical，XLSX numeric cell 与 Excel 公式一律拒绝；
- GUI 与 Excel 共用 `src/uebench/application/gb29446.py` 的周期 codec 与字段口径，同一输入产生同一 `EvaluationRequest` 与同一业务投影；
- Request / Result / Rule Snapshot 历史模型与 evaluate() 保存语义保持兼容；Calculator、Numeric、阈值、标准解释与数据库 Schema 不变；
- 验收载体：RS03 = PR #11；RS04 = PR #12；旧便携 ZIP 缺失仍是已知历史发布资产问题。

本任务停在 RS03，未开始 RS04。Reference Standard Product Closure 仍为 `PARTIAL`。

## 10. 历史材料索引

以下均为**历史证据**，默认不必通读；仅在需要追溯历史结论时按需读取。

| 文件 | 内容 | 状态 |
|---|---|---|
| [`HANDOFF_LEGACY_2026-09.md`](docs/history/legacy/HANDOFF_LEGACY_2026-09.md) | QZC-A01 bootstrap、Numeric DRAFT/BLOCKED 时期、UEBench 时期发布流水账 | `HISTORICAL` |
| [`QZC_N01_A_LOCAL_DESIGN.md`](docs/history/numeric/QZC_N01_A_LOCAL_DESIGN.md) | N01-A Pilot 静态设计证据 | `HISTORICAL-SUPERSEDED` |
| [`QZC_N01_A_EXECUTION_REPORT.md`](docs/history/numeric/QZC_N01_A_EXECUTION_REPORT.md) | N01-A Pilot 执行报告 | `HISTORICAL` |
| [`交接清单-2026-08-31.md`](docs/交接清单-2026-08-31.md) | 2026-08-31 交接清单（保留 `docs/` 原位，已加历史标识） | `HISTORICAL` |
| [`宏观结构审计-20260905.md`](docs/宏观结构审计-20260905.md) | 2026-09-05 宏观结构审计（保留 `docs/` 原位；`scripts/sync_release.ps1:86` 按该路径复制，故不物理移动） | `HISTORICAL` |
| [`开发基线待复核清单-20260905.md`](docs/开发基线待复核清单-20260905.md) | 2026-09-05 开发基线待复核清单（保留 `docs/` 原位，已加历史标识） | `HISTORICAL` |
| [`验收记录.md`](docs/验收记录.md) | 历史验收台账（Historical Acceptance Ledger） | `HISTORICAL LEDGER` |
| [`UI_CURRENT_STATE_AUDIT.md`](docs/audits/UI_CURRENT_STATE_AUDIT.md) | UI 现状盘点，对 RS02 仍有参考价值 | `AUDIT ONLY` |
| [`NUMERIC_V1_ADOPTION_REPORT.md`](docs/governance/NUMERIC_V1_ADOPTION_REPORT.md) | Numeric v1 Adoption 证据（**现仍为 Numeric 权威证据**） | `CURRENT EVIDENCE` |
| [`PLATFORM_ADOPTION_REPORT.md`](docs/governance/PLATFORM_ADOPTION_REPORT.md) | 平台接入证据 | `EVIDENCE` |

`docs/验收记录.md` 是**历史验收台账**，**不得**作为普通新任务的 Current State Authority。
