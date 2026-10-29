# TASK_STATE

## 2026-10-29 水泥Stage D候选交接

已从干净源码`a89b2c166214451bf6f6692099548979a4953483`构建`rc-a89b2c1`完整候选（配套.6/r2）：Artifact Gate63/63、冻结基础自检6/6及便携ZIP解包同EXE水泥四模式/双修正5记录5 Word、独立只读进程核三JSON与规则hash均通过。原生进程PID25296已在独立目录启动，但工具无法枚举窗口，UI交互、Word视觉/分页与安装升级卸载待验；安装器未执行。完整身份、资产hash、独立矩阵与证据见[Stage D记录](docs/governance/GB16780-2021_STAGE_D_ACCEPTANCE.md)。治理补录提交不是构建输入，不因此重打包。水泥仍IMPLEMENTED、尚未SUPPORTED；正常正式范围仅选煤，RS05 IN PROGRESS/产品PARTIAL/0.2.0未发布；不合并发布，Excel新工作簿延期。


## 2026-10-29 水泥Stage D隔离候选（当前推进）

Owner授权继续Stage D。功能分支以专用显式入口构建隔离候选，将相同实例许可传入Application与既有UI，常规入口及正式评价清单仍仅选煤。强制指定隔离目录并拒真实用户目录、未标识数据及内部重解析点；不覆盖用户安装，不执行现有同AppId安装器，不自动合并或发布。精确候选身份、独立手算矩阵与待验边界见[Stage D记录](docs/governance/GB16780-2021_STAGE_D_ACCEPTANCE.md)。当前仍IMPLEMENTED，尚未SUPPORTED；RS05 IN PROGRESS、产品PARTIAL、0.2.0未发布、Excel新工作簿延期。

## 2026-10-29 水泥Stage C源码实施（当前任务补充）

Owner已批准[水泥Stage B设计](docs/GB16780-2021_StageB_软件接入设计.md)修正并授权Stage C实现及隔离验证，取代下文历史任务中“本轮不开发水泥”的限制。唯一业务依据仍为V1.2冻结映射；软件源码状态为 `IMPLEMENTED`；Stage C验证见实施报告，Stage D尚未完成，不称 `SUPPORTED`。生产正式评价白名单仍仅选煤；后续验收与审查前不自动合并、发布或开放水泥。RS05保持IN PROGRESS、产品闭环PARTIAL、0.2.0未发布；Excel新工作簿延期。

源码配套签名规则库已同步为 `.6`（48项/765条，水泥r2）；这是规则库一致性更新，不是水泥EXE/Candidate或旧安装升级。原生验收因工具应用批准超时保持待验，未merge/release。详细证据见[实施报告](docs/governance/GB16780-2021_STAGE_C_EXECUTION_REPORT.md)。

实施从已fetch核对的 `origin/main@b538ac6729d39eafbb6903d1ecfbb1cd94a26d1e`（PR35）开始；Frozen lock不升级，历史结果不重算。先核DSL能力与规则差异，固定公式和阈值进入唯一Rule及共用Engine，UI/Word精炼。分摊保存原始输入、公式、Decimal28派生值和残差；普通有限精度残差不阻保存，业务边界不明才阻断依赖结果。


更新时间：2026-10-29

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

### 2026-10-28 rc-69562ee 定向复验与治理补录

- 实际构建仍为干净源码 `69562eed5d072b9a1a1a77ab6a71f63ea0196788`、候选 `rc-69562ee`：完整回归 1214 passed / 66 skipped，Artifact Gate 63 passed；据设计独立确认，该精确提交三项 CI 全部 success。[PR #34](https://github.com/adgo07/ECQuota-Insight/pull/34) 已获 Owner 授权在最终审查和精确提交 CI 通过后合并；合并不等于正式发布。
- C 已完成该包 Win11 原生 150% 的 12 项短定向复验；设计已独立核阅报告、三张关键原生图、合成数据库原快照及保护备份 CRC／哈希。C-DEF-001／002 两项 P3 在此定向范围关闭。旧 `rc-3bfbbeb` 完整原生证据保持其原版本，不能平移为本候选全矩阵通过；本候选 DOCX 只有导出及 XML／快照短冒烟，未实开 Word／WPS／Writer。
- 本次只补录治理证据，不改生产或实际打包输入，不重打包。剩余可执行条件见[RS05 报告最新节](docs/governance/RS05_EXECUTION_REPORT.md)：可丢弃安装隔离环境、可审计断网条件、Win10／其他 DPI／双屏、真实 IME，以及 Word／WPS 和官方网页呈现实测。`RS05=IN PROGRESS`、产品闭环 `PARTIAL`、`0.2.0=NOT RELEASED`；PR #34 按本轮 Owner 授权审查合并，不发布产品；水泥排除、Excel 正式流程延后。下节“新包待验”为 10-27 当时状态。

### 2026-10-27 候选实测续更（源码已修提示，新包待验）

- `rc-3bfbbeb`（干净源码 `3bfbbeb148b9724580c51518857c5dbedde01dd2`）已完成构建：完整回归 1183 passed / 66 skipped、Artifact Gate 63 passed，冻结 EXE 与隔离启动器自检各 6 passed。设计独立核对三资产哈希、326 载荷文件、身份与 ZIP CRC；证据位置见[RS05 报告末节](docs/governance/RS05_EXECUTION_REPORT.md)。不将该全套沿用为后续源码或新包全套。
- C 在该冻结包上完成 Win11 原生 150% 主要页面、保存重启及快照保真、225 条分页／损坏隔离、备份恢复等实测。DOCX 仅经 LibreOffice Writer 实开，未取得该候选 MS Word／WPS 实开证据。真实安装／升级／卸载、离线、Win10、其他 DPI／跨屏、真实 IME 等缺口继续保留。
- C-DEF-001 损坏备份失败提示、C-DEF-002 英文按钮已在 `96aa3cb0b69e55c069dc692c8def74c39cb75656` 源码修复；据设计复核反馈，独立 66 项与 B 定向 70 项通过。新包尚未构建、C 尚未原生复验，两项不提前关闭为实包 PASS。最终候选须先纳入本次经审核文档，再锁定实际干净 SHA；当前不预设该 SHA。
- `RS05=IN PROGRESS`、产品闭环 `PARTIAL`、`0.2.0=NOT RELEASED`；不合并或发布，水泥排除，Excel 正式流程延期。下节首轮文档核对的缺口以本续更及其精确候选边界补充，不抹去历史记录。

### 2026-10-27 UI 已合并（本日首轮文档核对）

- [PR #33](https://github.com/adgo07/ECQuota-Insight/pull/33) 已按用户验收授权合并，文档收口共同起点为 main `77665b87c9f1ff77c24d26fa5ffbd057c1d12cee`；不是待合并状态。统一导航、固定选煤标准摘要、单页计算自动保存、只读历史详情、全库检索分页、设置及禁用入口、紧凑表格、长名称完整显示与官方地址请求反馈已进入源码。当前操作见[用户手册](docs/用户手册.md)，实施及历史测试边界见[UI 状态](docs/ui/UI_IMPLEMENTATION_STATUS.md)。
- 已有 Win11 原生 150%（窗口 DPI 144、无 Qt 缩放环境覆盖）的源码 UI 隔离观察；早期“无 Win11 环境”仅对应 2026-10-20 的旧设备与旧候选。第二轮主体 `1425241` 的完整回归为 1165 passed / 66 skipped / 2 warnings；后续长名称 `e53ebb5` 为定向 25 passed，不能把前者全套冒充后者或合并提交的新全套。
- 当前推进文档收口、最终候选构建与隔离验收。构建须纳入经审核文档，记录实际干净 source SHA；不能用旧 UI 测试包或 `rc-b102e36` 代替最终候选。最终安装包／EXE／Artifact Gate、对应源码 CI、Win10/11 基本业务链、真实离线、125%／跨屏、真实输入法预编辑、官方网页实际呈现及 0.1.0 两代安装器覆盖等，按[RS05 执行报告最新节](docs/governance/RS05_EXECUTION_REPORT.md)及构建／验收线实际证据逐项收口，不预写 PASS。
- `RS05=IN PROGRESS`、`Reference Standard Product Closure=PARTIAL`、`0.2.0=NOT RELEASED`、`RS06=NOT STARTED`；Excel 正式用户流程继续 DEFERRED。本轮不启动水泥，不改公式、批准映射、支持范围、Schema 或 Frozen lock，不操作真实用户数据库、已安装产品及旧 UI 测试包数据。

### 2026-10-23 Owner 确认与软件边界（历史：当时源码与安装已验，GUI 视觉待验）

- Owner 表示当前选煤软件业务表现已无新增问题；[选煤入口](standards/mappings/GB29446-2019/README.md)将此限定记录为对**已验核算、判级、页面及 Word 业务表现**的认可。唯一正式业务映射仍为 2026-10-18 批准版；本次不更改公式、限值或 D01/D02，不把该认可扩展为所有环境验收通过、RS05 完成或 0.2.0 正式发布。
- Owner 重申水泥标准已确认：[水泥入口](standards/mappings/GB16780-2021/README.md)继续以 V1.2 冻结版为唯一批准业务映射。Stage B/C/D 尚未完成，现有水泥 JSON／核算输出未经 V1.2 差异修复及独立 Golden、正式验收，不得标为软件已正确支持；标准问题 001/003 保持原状态。
- 其余几十项旧规则即使能计算，也是待逐项批准映射和重审的工程基线。用户指出错误较多，作为审查风险记录；具体错误须逐项给出证据、差异与处置，未核项不写成已证实错误。64 项定义、48 项随包和“仅选煤正式评价”的范围不因此改变。
- 本轮源码已在标准库选中详情分别投影**映射确认状态**与**软件正式评价支持状态**；非正式评价标准的产品/工序、指标、单位及限值明细表不在普通详情展示，结构化登记不自动扩大正式评价范围。审查返修后的 4 个定向模块 60 项、构建门禁与精确源码提交三项 CI 已通过；修正手册已进入新 Candidate 并在真实用户持久目录安装，隔离数据进程已启动、关闭。GUI 三态视觉与选煤最短操作链未实测，仍待补验。当前 Candidate 构建源码为 `b102e36a564e5b8874e676e4a1799395d211254b`；此前 `f6896584ad8fa9c2dd6cbe4e3b1f3fa5b51dbe17` 的实物记录保留为历史，最终治理文档提交只作交接，不代表重建实物。详情见[RS05 本轮记录](docs/governance/RS05_EXECUTION_REPORT.md)。标准确认继续记录于现有总索引与各标准入口，不新建平行台账或运行时解析 Markdown。

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

RS05 既有 Candidate 已包含 GB29446 r2 配套、启动期标准库对账、安全升级、Candidate 溯源与基础自检能力。原阶段未取得 Win11、多显示器跨屏及多档 DPI 实机证据；后续源码 UI 的 Win11 原生 150% 证据以上方 2026-10-27 节为准。最终候选仍须重建并记录真实 Gate 结果，不得把历史 Candidate 当作当前源码交付。
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
- `PARTIAL` 不等于“可发布”；PR #33 已合并，下一步纳入经审核文档、从实际干净源码构建最终候选，再由构建／验收线提交真实 Gate 与环境证据。Win11 源码原生 150% 局部观察已取得；最终候选安装版、真实离线、125%／跨屏、输入法／原文网页及 0.1.0 两代真实安装器覆盖等仍按[RS05 最新交付矩阵](docs/governance/RS05_EXECUTION_REPORT.md)收口；
- 旧阶段“便携 ZIP 缺失”及 `rc-4e43490`、`rc-f689658`、`rc-b102e36` 的已验与未验结果保留各自历史身份；旧候选的哈希、启动或 Word/WPS 证据不能直接移作最终候选验收。旧 UI 试用包及其数据也保持原状。

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

## 2026-10-29 剩余验收续记

文档head f571bac三项远端CI均success，构建仍rc-a89b2c1/a89b2c1。UI/Word工具阻塞；真实原安装器在独立sandbox SID、专属目录静默尝试一次，因HKCU注册权限错误退出4并自动回滚，未提升重试；安装/卸载不记通过、旧→新覆盖未试。前置快照未完成即启动的执行偏差及事后证据边界如实记于[Stage D报告](docs/governance/GB16780-2021_STAGE_D_ACCEPTANCE.md)，不能声明完整前后数据保真。Stage D未完成、水泥IMPLEMENTED尚未SUPPORTED；RS05 IN PROGRESS/产品PARTIAL/0.2.0未发布，PR36草稿，不自动合并发布，Excel延期。
