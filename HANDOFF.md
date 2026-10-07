# HANDOFF — ECQuota 当前交接

更新时间：2026-10-07

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

当前状态：Reference Standard Product Closure = PARTIAL。GB29446 Business Capability = COMPLETE；GB29446 Product Lifecycle = COMPLETE；RS01–RS04 = DONE。RS03 已建立的 Excel Adapter 技术能力继续保留；Excel Adapter technical capability = RETAINED，Excel user-facing formal workflow = DEFERRED。RS05 = IN PROGRESS，当前目标为 Product Simplification & Standard Library Pairing；RS06 = NOT STARTED。普通用户无需管理标准包，标准库随完整软件版本配套更新。不得宣布 RS05 完成或发布 v0.2.0。详见 参考标准开发路线.md。

> `PARTIAL` **不等于“可发布”**；Windows 正式交付证据尚未建立。

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

已完成：标准库 / 标准选择 / 新建评价 / 输入与校验 / Calculator / 等级 / Numeric v1 Conformance / GB29446 专用页面基础 / 标准包签名与安装 / 备份恢复 / 审计日志 / Excel Adapter 后台能力（用户正式流程暂缓） / Windows 打包链。

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
→ RS05 Product Simplification & Standard Library Pairing                     IN PROGRESS  ← 当前阶段
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

**RS05 已修复（RS04 登记的 Release Gate）**：

- corrupted historical `result_json`：RS05 已按行隔离反序列化，单条损坏记录降级显示并记录 WARNING，
  不再中断“评价记录”页、首页或应用启动；detail 明确提示“记录损坏”。

**RS05 Blocker 状态**：

- 已关闭：内置标准包的 GB29446 落后问题已按批准的方案 B 修复 —— 以已签名
  `2026.09-published.2` 为父基线，只替换 GB29446 定义（r1 → r2），其余标准逐字节不变，
  重新签名生成 `2026.10-published.3`；RS04 Golden 15/15、冻结自检 `exit 0`。
  其后 Phase 7 收口又把该包改为**不含标准原文 PDF** 的 `2026.10-published.4`（provenance-only，定义内容不变），旧 `.3` 已归档为 SUPERSEDED。
  详见 `release/standard-packages/PIN.json` 与执行报告 §5.2A / §7.4。
- 已关闭：升级后旧用户数据目录的规则不会自动更新 —— 现已改为**每次启动执行标准包对账**
  （空库安装 / 完全相同 NO-OP / 旧包安全升级 / 不降级 / 冲突不覆盖 / 验签失败不安装）；
  旧包升级前用安全备份 API，历史评价与规则快照不被重算。
- 已关闭：不同内容的 Candidate 同名难以区分 —— Candidate 资产名与 CI artifact 名现在携带
  `-rc-<short7>`，并由 `release-build-info.json` / `ACTIVE-CANDIDATE.json` 记录
  `source_commit`（完整 40 位）、`source_dirty=false` 与标准包身份。
- 仍未关闭（由环境决定）：Windows 验收证据不完整 —— 无 Windows 11 环境、单显示器，
  无法实测多 DPI 与跨屏拖动（如实记为 BLOCKED / PENDING-MANUAL）。

## 9. 下一步

- 当前阶段：RS05 — Product Simplification & Standard Library Pairing（IN PROGRESS）；RS06 保持 NOT STARTED；
- 普通用户只使用随软件配套的标准库，不再手动安装、导入、扫描或管理标准包；
- Excel Adapter / Canonical Input / 共用 Calculator / Decimal 安全链继续保留；Excel 正式用户流程暂缓开放；
- 完成本阶段设置页收敛、标准包普通入口移除、版本配套与 Application readiness gate、恢复后即时 reconciliation；
- 按本任务要求运行定向回归、RS04 Golden、Numeric/N01-A、literal full suite、Source Gate、Windows Candidate、Artifact Gate、自检及 exact-head CI；
- 不发布 v0.2.0，不合并本任务 PR，不开始 RS06。

Reference Standard Product Closure 仍为 PARTIAL。

## 10. 历史材料索引

以下均为**历史证据**，默认不必通读；仅在需要追溯历史结论时按需读取。

| 文件 | 内容 | 状态 |
|---|---|---|
| [`HANDOFF_LEGACY_2026-09.md`](docs/history/legacy/HANDOFF_LEGACY_2026-09.md) | QZC-A01 bootstrap、Numeric DRAFT/BLOCKED 时期、UEBench 时期发布流水账 | `HISTORICAL` |
| [`QZC_N01_A_LOCAL_DESIGN.md`](docs/history/numeric/QZC_N01_A_LOCAL_DESIGN.md) | N01-A Pilot 静态设计证据 | `HISTORICAL-SUPERSEDED` |
| [`QZC_N01_A_EXECUTION_REPORT.md`](docs/history/numeric/QZC_N01_A_EXECUTION_REPORT.md) | N01-A Pilot 执行报告 | `HISTORICAL` |
| [`交接清单-2026-08-31.md`](docs/交接清单-2026-08-31.md) | 2026-08-31 交接清单（保留 `docs/` 原位，已加历史标识） | `HISTORICAL` |
| [`宏观结构审计-20260905.md`](docs/宏观结构审计-20260905.md) | 2026-09-05 宏观结构审计（保留 `docs/` 原位；该文件无任何脚本 / 测试 / 构建引用，可随时移入 `docs/history/`） | `HISTORICAL` |
| [`开发基线待复核清单-20260905.md`](docs/开发基线待复核清单-20260905.md) | 2026-09-05 开发基线待复核清单（保留 `docs/` 原位，已加历史标识） | `HISTORICAL` |
| [`验收记录.md`](docs/验收记录.md) | 历史验收台账（Historical Acceptance Ledger） | `HISTORICAL LEDGER` |
| [`UI_CURRENT_STATE_AUDIT.md`](docs/audits/UI_CURRENT_STATE_AUDIT.md) | UI 现状盘点，对 RS02 仍有参考价值 | `AUDIT ONLY` |
| [`NUMERIC_V1_ADOPTION_REPORT.md`](docs/governance/NUMERIC_V1_ADOPTION_REPORT.md) | Numeric v1 Adoption 证据（**现仍为 Numeric 权威证据**） | `CURRENT EVIDENCE` |
| [`PLATFORM_ADOPTION_REPORT.md`](docs/governance/PLATFORM_ADOPTION_REPORT.md) | 平台接入证据 | `EVIDENCE` |

`docs/验收记录.md` 是**历史验收台账**，**不得**作为普通新任务的 Current State Authority。

### 0.2.0 正式评价范围与标准原文（Phase 7 收口）

- 0.2.0 的**正式评价范围只有 GB 29446—2019《选煤电力消耗限额》**。其他标准可以继续出现在
  标准库中作为目录/参考信息，但**不得**作为正式评价对象，界面显示「尚未纳入正式评价范围」。
  “标准库里有该标准”不等于“软件已正式支持评价”。
- 0.2.0 **不随软件分发、也不在软件数据目录保存标准原文 PDF**；普通界面提供
  「查看标准原文」，点击后打开**全国标准信息公共服务平台**上预先登记的官方页面
  （不进行运行时搜索或抓取）。未登记官方地址的标准，该入口禁用并提示
  「官方来源地址尚未登记」。
- 标准定义中仍保留标准编号、原文文件名与 SHA-256 等**追溯元数据**，但不再分发原文文件本身。
- 评价记录的时间按**操作系统本地时区**显示，精确到秒（数据库仍以 UTC 存储）。
