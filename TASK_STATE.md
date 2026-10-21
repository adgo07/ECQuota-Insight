# TASK_STATE

更新时间：2026-10-18

## 当前产品目标

> **下一正式版必须完整支持 GB 29446—2019《选煤电力消耗限额》。**

Reference Standard：`GB 29446—2019 选煤电力消耗限额`
Module ID：`qz.energy_quota`
Canonical repository：`https://github.com/adgo07/ECQuota-Insight.git`

总体路线唯一入口：`参考标准开发路线.md`。

## 当前任务

**ECQ-RS05 — Product Simplification & Standard Library Pairing（IN PROGRESS）**

- ECQ-GOV01 = DONE（PR #8）；ECQ-RS01 = DONE（PR #9）；ECQ-RS02 = DONE（PR #10）；
  ECQ-RS03 = DONE（PR #11，Excel Adapter 技术能力）；ECQ-RS04 = DONE（PR #12）；
- ECQ-RS05 = IN PROGRESS：按“安装完整 UEBench → 自动使用配套标准库 → 用户直接评价”的产品模型收口；
  本阶段不得写成 DONE，不得发布 UEBench 0.2.0；
- ECQ-RS06 = NOT STARTED，不得开始第二标准；
- GB29446 Business Capability = COMPLETE；GB29446 Product Lifecycle = COMPLETE；
- Excel Adapter technical capability = RETAINED；Excel user-facing formal workflow = DEFERRED；
- 用户无需管理标准包；标准库随完整软件版本配套更新；
- Reference Standard Product Closure = PARTIAL；
- Numeric v1、数据库 Schema、Frozen Contract 与 platform-lock 保持现有基线；GB29446 业务解释以本次批准映射为准，机器规则身份及交付物按本轮实施验证。

### 2026-10-18 批准映射及本轮实施决定

- GB 29446—2019 的[现行批准业务映射](standards/mappings/GB29446-2019/标准映射表_2026-10-18_已批准.md)已由 Owner 确认为唯一现行**正式业务映射版本**；[标准入口](standards/mappings/GB29446-2019/README.md)记载原文件 SHA256 与版本关系，批准正文原字节不变。该映射是术语、规则、UI、Word 和独立 Golden 的业务依据；映射正式不等于 RS05 完成、0.2.0 发布或其余标准获正式支持。
- D01：有效结果超过对应 3 级上限统一称“未达3级”，旧“超出3级”已在本轮源码展示中同步；D02：仅本标准要求 $E_d>0$、$m>0$，这是软件防误录规则，不是标准明文。普通页面不恢复企业建设属性、限定值/准入值合规填写或符合性主结论。
- UI 与 Word 及未来可能的 Excel 使用现行批准映射中的专业名称、字段、单位、选项、说明和结果含义；特殊名称须 Owner 明确特批及采用记录。各渠道尽量表达同一业务内容，布局差异允许。
- **Excel 本轮暂不实施**：不生成、交付新版工作簿，也不把 Excel 模板作为本轮交付前置；既有 Adapter、历史样本和安全回归保留，未来若启动再按届时批准映射设计。
- 除选煤外，现有其他标准规则是**遗留待映射重审的工程基线**，不是批准业务真值源；不据此断言所有旧规则均已证实错误。用户逐项批准映射后，按“映射 → 差异清单 → 设计 → 实现 → 独立 Golden → 验收”重整核算、判定和展示；旧状态五态枚举不增加新值。历史评价与规则快照不自动重算。
- 已按 Owner 批准将 16 项原样 `draft` 候选迁入唯一可编辑机器定义源 `data/definitions/`：当前共 64 项。`data/delivery-scope.json` 显式选择随包 48 项（含既有历史项）、正式评价仅 `gb-29446-2019`；定义迁入不等于业务批准。`standards/development/scope-63/` 与 `scope-65/` 保留为只读历史快照，不是发布输入、不得反向覆盖当前定义。开发索引由单源及交付清单派生；旧 writer 入口退出，本轮源码集成验收已通过。
- 本轮新增选煤 Word 报告目标。中央 ACTIVE 产品家族规格 A-12、验收清单和 UI 指南已通过 [Qingzhou-contracts PR #13](https://github.com/adgo07/Qingzhou-contracts/pull/13) 同步并合并（`c5fc6d438c9200060649e47c016b9b48218de72c`）；这不是 Frozen Contract 变更，`platform-lock.json` 不升级。RS05 仍 IN PROGRESS，Reference Standard Product Closure 仍 PARTIAL，未授权发布。
- **标准包输入与上一轮 Candidate（非正式产品发布）：**[PIN](release/standard-packages/PIN.json) 指向 `2026.10-published.5`，`package_id=gb29446-r3-from-2026.10-published.4`，132,966 B，SHA256 `9547e8214124cd76e999c2949dcdcf45738282a56cc0d725df08cea2a49fa2b5`；其中 GB29446 规则修订为 r3、48 项随包、765 条规则、`source_policy=provenance-only`。上一轮 Candidate 构建源码 commit 为 `025d8c5a1bdb63afd53c61df7c5435604259d314`；PR #28 后新 Candidate 的独立构建与验收身份见下段，不能把旧实物冒充新源码产物。

**本轮源码集成验收通过**，详见[实施与验收记录](docs/governance/映射驱动单源规则与同源报告_V3_验收记录_20261018.md)：本地 full suite 为 1110 passed、62 skipped、0 failed、1 warning。实际 Candidate 的 Artifact Gate 63/63、安装版与便携版 EXE、自检、安装版保存重启及 Word 导出、真实 Microsoft Word 与 WPS 四场景、同版本覆盖与卸载保留数据、可信旧 0.2.0 Candidate `.4`→本轮 `.5` 升级保留 r2 历史结果、构建源码 exact-head 三项 GitHub CI 均已取得证据；具体边界见[交付补充验收记录](docs/governance/映射驱动单源规则与同源报告_V3_交付补充验收_20261018.md)。该次验收尚未执行 0.1.0→0.2.0 真实安装器覆盖；本次 RS05 收口已找回哈希吻合的历史安装器，升级及原生 Windows DPI／跨屏和 Windows 11 等环境覆盖仍待证据；中央 ACTIVE 四文件已合并。RS05 仍 IN PROGRESS，产品闭环仍 PARTIAL。

PR #13 的历史 Windows Candidate 与对账工作是本阶段既有基线；`025d8c5` Candidate 的已完成验收保持历史证据。[业务 PR #28](https://github.com/adgo07/ECQuota-Insight/pull/28) 已按 Owner 授权合并到 `main`（merge `8914d31da35ffb3e8f42cbea9a55a9075fea4d0e`），新 Candidate 的独立构建及受影响验收见下段。上述通过项不代表 RS05 已完成或正式发布。

**PR #28 合并后新 Candidate 已重建并完成本机受影响续验：**构建输入干净提交 `4e4349068bb56fa500d20cfab98ef6640e63605c`，`rc-4e43490`；身份、10 条文件哈希、冻结 EXE 自检 6/6、Artifact Gate 63/63 及该源码三项 exact-head CI 均通过。新安装版 GUI 保存／重启读回、临界与未达3级 Word/WPS 实开、中文路径便携 GUI 启停、可信旧 r2 数据克隆升级且历史 JSON 不变，证据与范围见[交付补充验收记录 §6](docs/governance/映射驱动单源规则与同源报告_V3_交付补充验收_20261018.md)。上段 `025d8c5` 仅是旧 Candidate 历史证据；新候选仍未正式发布。本次另取得可信 0.1.0 安装载荷的**库级**升级保真证据，未取得旧 GUI 保存及两代安装器真实覆盖；Win11、原生系统高 DPI／跨屏和离线仍缺环境证据，见 [RS05 本机收口结果](docs/governance/RS05_EXECUTION_REPORT.md)末节。RS05 仍 IN PROGRESS、产品闭环 PARTIAL。

### RS05 前置阶段背景（历史记录）

RS05 既有 Candidate 已包含 GB29446 r2 配套、启动期标准库对账、安全升级、Candidate 溯源与基础自检能力。原阶段的 Win11、多显示器跨屏及多档 DPI 实机证据仍未在本地环境完成；本任务须重建当前源码 Candidate 并记录真实 Gate 结果，不得把历史 Candidate 当作当前源码交付。
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
→ RS05 Product Simplification & Standard Library Pairing                     IN PROGRESS  ← 当前阶段
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
| GB29446 Excel Adapter 技术能力 | RETAINED（用户正式工作流 DEFERRED） |
| GB29446 Product Golden | `ADOPTED (v1)` |
| Reference Standard 产品证据 | `PARTIAL` |
| Reference Standard Product Closure | `PARTIAL`（尚欠 RS05） |
| Product Simplification & Standard Library Pairing | `IN PROGRESS`（RS05 进行中，未 DONE） |
| 第二标准架构验证 | `NOT STARTED`（RS06 处理） |

## 发布物状态

- **上一正式发布物 / Previous Release**：`UEBench 0.1.0`、standard package `2026.09-published.2`。历史已发布版本，**不代表当前 main 源码**。
- **0.2.0 Candidate 规则**：只有从本轮 RS05 最终干净 Head 构建并通过 Candidate 门禁的产物可代表当前源码；更早的候选产物不作为当前基线。产物身份与哈希记录在交付目录；本阶段不授权正式发布。
- **当前开发源码 / Current Development Source**：以执行时实际 `main` SHA 为准。

## 当前 OPEN

中央已登记偏差（权威清单见 `platform-lock.json` 的 `known_deviations`）：

- `D-ECQ-002` Module/Capability Manifest 尚未正式实施；
- `D-ECQ-003` Workspace/Attempt/Record/Result 公共外围仅部分具备；
- `D-ECQ-004` 现有 `.uebench` 包不是正式 qzpack v1；
- `D-ECQ-005` Unit Contract 仍未正式采用；
- `D-ECQ-006` 中央 lossless XLSX numeric-cell 公共方案仍 OPEN。RS03 已把本仓 Excel 权威入口收紧为 text 十进制 lexical，RS04 的 Excel 安全语义案例继续以此为前提，但这**不表示中央公共方案已冻结**。

标准问题与Numeric治理：

- 当前标准问题按 `STANDARD_ISSUES_REGISTER.md` 核对；GB 29446 的历史 ROUND6 属于**已修复的软件缺陷**，不再登记为标准问题。
- RS04 Golden 的 full-value trap 继续保留，以冻结Numeric v1正式全值比较的可回归业务证据；其上游锁定依据为 `platform-lock.json`、`docs/统一判定规范.md` 和Numeric v1。

**RS05 已修复（RS04 登记的 Release Gate）**：

- `corrupted historical result_json` 爆炸半径：RS05 已在 infrastructure 层按行隔离反序列化，
  单条损坏记录降级显示并记录 WARNING，不再中断“评价记录”页、首页或应用启动；
  detail 明确提示“记录损坏”，不伪装成“已删除 / 不存在”。详见 RS05 执行报告。

其他 Deferred（仅登记）：

- 旧“规则确认表”的只读校验与相关测试可作为历史证据保留；`tools/publish_confirmed_rules.py --apply` 和会覆盖多处目录的旧发布写入口不再作为现行发布路径。后续发布从 `data/definitions/` 与 `data/delivery-scope.json` 生成；派生索引和发布门禁仍按本轮集成结果验证；
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
- 状态仍为 **`RS05 = IN PROGRESS`**；`D-ECQ-006` 继续 OPEN；
  `Reference Standard Product Closure = PARTIAL`。

## 下一步

- `ECQ-GOV01 = DONE`；`ECQ-RS01 = DONE`；`ECQ-RS02 = DONE`；`ECQ-RS03 = DONE`；`ECQ-RS04 = DONE`；
- 当前阶段 = **`RS05` — Product Simplification & Standard Library Pairing**（`IN PROGRESS`）；RS06 未开始；
- `PARTIAL` 不等于“可发布”；`rc-4e43490` 已有 Win10 安装／便携、Word/WPS、Candidate Gate、旧 r2 和正式 0.1.0 载荷的隔离数据升级证据；仍缺 Win11、原生系统高 DPI、跨屏／离线及 0.1.0 真实安装器覆盖的收口裁定，见[RS05 当前交付收口计划与本机结果](docs/governance/RS05_EXECUTION_REPORT.md)末节；
- 旧阶段“便携 ZIP 缺失”是历史资产问题；当前 Candidate 的便携 ZIP 已生成并通过哈希、自检与中文路径 GUI 启停，不能继续把旧缺项当作本次未生成资产。

本任务停在 RS05 候选阶段，未开始 RS06。

## Phase 7 历史收口记录（原阶段记录）

> 本节记录 PR #13 所在阶段的历史事实；当前 RS05 目标、状态和交付约束以本文前部“当前任务”及最新 RS05 执行报告为准。


> 本节为**追加**记录，不改写上文历史。上文关于 `2026.10-published.3` 的叙述是其时事实；
> 以下记录的是 Phase 7 当时的标准包状态：其时 `.4` 替代 `.3` 且不含标准 PDF。**本次工作树现行 PIN 已指向 `.5` r3**（见上文当前任务）；`.4` 在当前 PIN 中为 `SUPERSEDED / REFERENCE ONLY`。本节不作为当前交付身份。

### 新正式标准包（去 PDF，provenance-only）

| 项目 | 值 |
|---|---|
| `package_id` | `gb29446-r2-provenance-only-from-2026.10-published.3` |
| `data_version` | `2026.10-published.4`（排序晚于 `.3`） |
| `minimum_app_version` | `0.2.0` |
| size / SHA256 | 132,837 B / `023d5caf81dd6ba1ce41a5b5d8a59676db20dd98db510b6c4329600aa47e77ff` |
| 标准 / 规则 | 48 / 765（业务内容不变） |
| 成员 | 48 × `definitions/*.json` + `corrections.json` + manifest + signature；**0** 个 `sources/*`、**0** 个 PDF |

- 去 PDF 方式：manifest 新增自描述字段 `source_policy ∈ {"embedded","provenance-only"}`，
  **默认 `embedded`** —— 因此所有历史/归档包仍按原语义校验，legacy 读取兼容未被破坏。
- 定义 provenance（`source_file` / `source_sha256` / `source_references`）**保留**，
  仅不再分发原文文件；`install()` 因而不再把 PDF 写入用户数据目录。
- 逐字节证据（对归档基线以 `--verify-only` 复核）：
  `removed_source_count=48, added=[], changed=[], unchanged_member_count=49` ——
  48 个定义与 `corrections.json` 逐字节一致，仅 `manifest.json` / `signature.ed25519` 变化。
- 旧 `2026.10-published.3` 已按既有规则归档为 SUPERSEDED / REFERENCE ONLY。
- 新增 Gate：`tools/audit_release.py` 的 `no_standard_pdf` 一节 + Artifact Gate 四项
  （发布目录 / 标准包 / 便携 ZIP / payload 清单均不得出现标准 PDF 或 `sources/*`）。

### 支持范围 / 官方来源 / 时间显示（基础模块已完成）

- `application/evaluation_support.py`：单一软件评价支持范围 = `{"gb-29446-2019"}`，
  **不读 `publication_status`**（有 AST 守卫测试）。
- `application/official_sources.py`：仅固定常量，**一个已核实**官方地址
  `https://std.samr.gov.cn/gb/search/gbDetailed?id=9A0A4FA998CDD4A5E05397BE0A0AD02D`
  （两次独立抓取 HTTP 200、内容与本仓标准快照逐项吻合）；其余标准一律未登记。
- `ui/presentation.py`：`naive → UTC → 系统本地时区`，显示 `YYYY-MM-DD HH:MM:SS`、无微秒。

### 尚未完成（因此本轮不构成完成报告）

UI 收口（标准库信息结构 / 新建评价页 / 时间显示接入 / 声明原文入口）、
release 文档中"当前包为 .3 / 48 项标准"表述的统一更新、重建 Candidate、
Source/Artifact Gate + RS04 Golden + self-check + Numeric v1 + N01-A + Generic Excel +
legacy upgrade + literal full suite、exact-head CI、本机 Win10 最短真实产品链人工验证。
**注意**：`dist/release` 仍是用旧包构建的 Candidate，新增"无 PDF"断言对它必然失败，
必须重建后才转绿（不得以删断言或 skip 掩盖）。
