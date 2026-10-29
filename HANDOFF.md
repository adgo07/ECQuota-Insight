# HANDOFF — ECQuota 当前交接

## 2026-10-29 水泥Stage D隔离候选（当前推进）

Owner授权继续Stage D。功能分支以专用显式入口构建隔离候选，将相同实例许可传入Application与既有UI，常规入口及正式评价清单仍仅选煤。强制指定隔离目录并拒真实用户目录、未标识数据及内部重解析点；不覆盖用户安装，不执行现有同AppId安装器，不自动合并或发布。精确候选身份、独立手算矩阵与待验边界见[Stage D记录](docs/governance/GB16780-2021_STAGE_D_ACCEPTANCE.md)。当前仍IMPLEMENTED，尚未SUPPORTED；RS05 IN PROGRESS、产品PARTIAL、0.2.0未发布、Excel新工作簿延期。

## 2026-10-29 水泥Stage C源码实施（当前任务补充）

Owner已批准[水泥Stage B设计](docs/GB16780-2021_StageB_软件接入设计.md)修正并授权Stage C实现及隔离验证，取代下文历史任务中“本轮不开发水泥”的限制。唯一业务依据仍为V1.2冻结映射；软件源码状态为 `IMPLEMENTED`；Stage C验证见实施报告，Stage D尚未完成，不称 `SUPPORTED`。生产正式评价白名单仍仅选煤；后续验收与审查前不自动合并、发布或开放水泥。RS05保持IN PROGRESS、产品闭环PARTIAL、0.2.0未发布；Excel新工作簿延期。

源码配套签名规则库已同步为 `.6`（48项/765条，水泥r2）；这是规则库一致性更新，不是水泥EXE/Candidate或旧安装升级。原生验收因工具应用批准超时保持待验，未merge/release。详细证据见[实施报告](docs/governance/GB16780-2021_STAGE_C_EXECUTION_REPORT.md)。

实施从已fetch核对的 `origin/main@b538ac6729d39eafbb6903d1ecfbb1cd94a26d1e`（PR35）开始；Frozen lock不升级，历史结果不重算。先核DSL能力与规则差异，固定公式和阈值进入唯一Rule及共用Engine，UI/Word精炼。分摊保存原始输入、公式、Decimal28派生值和残差；普通有限精度残差不阻保存，业务边界不明才阻断依赖结果。


更新时间：2026-10-28

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

**2026-10-28 当前补录：** 实际候选 `rc-69562ee` 的干净构建源码为 `69562eed5d072b9a1a1a77ab6a71f63ea0196788`，完整回归 1214 passed / 66 skipped、Artifact Gate 63 passed；设计独立确认该 SHA 三项 CI 全部 success。[PR #34](https://github.com/adgo07/ECQuota-Insight/pull/34) 已获 Owner 授权在最终审查和精确提交 CI 通过后合并；合并不等于正式发布。C 的 Win11 原生 150% 短定向 12 项及设计独立复核通过，C-DEF-001／002 两项 P3 在本机定向范围关闭；保存快照、取消／恢复审计与保护备份已核。本次治理提交不改变实际打包输入、不重打包，不把其提交 SHA 当作被测构建。

证据和可行动的剩余环境条件见[RS05 报告最新节](docs/governance/RS05_EXECUTION_REPORT.md)。旧 `rc-3bfbbeb` 的完整原生验收不平移到新包；本候选未做 Word／WPS／Writer 实开。安装／升级／卸载、可信离线、Win10、其他 DPI／跨屏、真实 IME、MS Word／WPS 与官网实际呈现仍未验。保持 RS05 IN PROGRESS、产品 PARTIAL、0.2.0 未发布；本线按 Owner 授权推进审查与合并，不发布产品，水泥不开发、Excel 正式流程延后。以下 10-27 记录保留当时边界，其中“新包尚未构建／待原生复验”已由本次定向结果补充。

**2026-10-27 候选实测后续交接：**`rc-3bfbbeb`（干净源码 `3bfbbeb148b9724580c51518857c5dbedde01dd2`）完整回归 1183 passed / 66 skipped、Artifact Gate 63 passed，EXE／隔离启动器各 6 项自检通过；设计已独立核三资产哈希、326 载荷、身份及 CRC。C 已在该包实测 Win11 原生 150%、保存重启／快照与 Word、225 条分页／损坏隔离、备份恢复；DOCX 只在 LibreOffice Writer 实开，不称 MS Word／WPS 通过。证据入口集中在[RS05 报告末节](docs/governance/RS05_EXECUTION_REPORT.md)。

C-DEF-001／002 两处提示问题已由审核源码 `96aa3cb0b69e55c069dc692c8def74c39cb75656` 修复；设计反馈独立 66 项与 B 定向 70 项通过。新包尚未构建、C 尚未原生复验，两项保持“源码已修，实包待验”。最终包须纳入本次经审核文档后锁定实际干净 SHA，不预设 SHA，不把旧 `3bfbbeb` 全套移作新源码或新包结论。真实安装／升级／卸载、离线、Win10、其他 DPI／跨屏、真实 IME、MS Word／WPS 等仍缺证。RS05 仍 IN PROGRESS／未发布；本线不推送、合并或发布，不开发水泥，Excel 正式流程延期。以下首轮缺口按此精确版本进度补充。

**2026-10-27 首轮交接：**[PR #33](https://github.com/adgo07/ECQuota-Insight/pull/33) 已按用户验收授权合并到 main（`77665b87c9f1ff77c24d26fa5ffbd057c1d12cee`）。统一 UI、固定选煤单页、自动保存快照、记录全库分页与只读两页签详情、设置、紧凑表格及长名称返修已进入源码；官方原文请求后反馈无法确认网页呈现，并可复制地址。用户操作以[用户手册](docs/用户手册.md)为准，实施历史见[UI 状态](docs/ui/UI_IMPLEMENTATION_STATUS.md)。

源码 UI 已有 Win11 原生 150%／窗口 DPI 144 的隔离观察；下文旧候选“无 Win11／高 DPI 证据”只保留当时设备和版本边界，不是当前环境结论。最终候选安装包与 Win10/11 基本业务链、真实离线、125%／跨屏、真实输入法预编辑、网页实际呈现及 0.1.0 两代安装器覆盖仍待对应实测，详见[RS05 执行报告最新节](docs/governance/RS05_EXECUTION_REPORT.md)。当前构建须纳入经审核文档并记录实际干净源码身份；后续验收线使用独立证据文件，不能将本次文档整理或 UI 合并记为 Gate 通过。第二轮主体全套 1165 passed / 66 skipped / 2 warnings 属 `1425241`；`e53ebb5` 长名称补修仅有已登记定向 25 passed，不冒充新全套。

后续继续 RS05 候选构建和隔离验收，不发布、不打正式 tag，不自行推送或合并文档分支；RS06 与水泥开发不启动，Excel 正式流程延后。不得改真实数据库、已安装产品或旧 `UI测试版_b1346935`／`e70da765`／`ced969a3` 及其中数据。Frozen lock、公式、批准映射、支持范围与 Schema 不变。以下 2026-10-18～23 段落为已有业务与候选证据，具体通过项不跨版本继承。

**2026-10-18 当前正式业务映射：**Owner 已确认[GB29446 现行批准映射](standards/mappings/GB29446-2019/标准映射表_2026-10-18_已批准.md)为唯一正式业务映射版本，[标准入口](standards/mappings/GB29446-2019/README.md)记录原字节 SHA256。D01 将有效比较后超过 3 级上限的结果称为“未达3级”；D02 为本标准设 $E_d>0$、$m>0$ 的软件防误录边界，非标准明文。旧“超出3级”已在本轮源码展示中同步；不恢复企业建设属性合规填写或符合性主结论。映射正式不等于 RS05 完成或其他标准获正式支持。

**2026-10-23 新确认边界：**Owner 认可现有已验的选煤业务核算、判级及页面／Word表现，继续采用上述批准映射；[选煤入口](standards/mappings/GB29446-2019/README.md)记确认范围与未覆盖门禁。Owner 重申[水泥 V1.2 映射](standards/mappings/GB16780-2021/README.md)已批准冻结，但水泥软件 Stage B/C/D、旧规则差异及独立验收仍未完成，不能宣称水泥核算已正确支持。其他几十项旧规则按逐项映射重审；用户指出错误较多属于风险信息，未核具体项不预断为已证实错误。确认记录仍用[映射总索引](standards/mappings/INDEX.md)、各标准入口及既有决策／问题文件，不另建台账。审查修正后的结构化源码、定向测试与 `rc-b102e36` 构建通过；真实用户持久安装和隔离进程启动／关闭通过，GUI 三态视觉及选煤操作链仍待补验，见[RS05 执行报告](docs/governance/RS05_EXECUTION_REPORT.md)。

本轮 UI 与 Word 应共享映射术语及字段、单位、选项、说明和结果含义；未来 Excel 若启动亦如此，专业特殊命名须 Owner 明确特批。**本轮不生成或交付新版 Excel 工作簿**，保留既有 Adapter 与安全回归。新 Word 导出决定已通过 [Qingzhou-contracts PR #13](https://github.com/adgo07/Qingzhou-contracts/pull/13) 同步中央 ACTIVE 产品规格 A-12、验收清单与 UI 指南（merge `c5fc6d438c9200060649e47c016b9b48218de72c`），未修改 Frozen lock。

其他标准规则按**遗留待映射重审的工程基线**管理，不作为批准业务真值源，也不概括判定所有旧规则均错误。后续用户逐项批准映射，再走差异清单、设计、实现、独立 Golden、正式验收；支持状态仍仅中央五态，历史记录及规则快照不重算。

**标准包输入与上一轮 Candidate（尚非正式产品发布）：**[PIN](release/standard-packages/PIN.json) 指向签名包 `2026.10-published.5`，`package_id=gb29446-r3-from-2026.10-published.4`，132,966 B，SHA256 `9547e8214124cd76e999c2949dcdcf45738282a56cc0d725df08cea2a49fa2b5`；选煤规则修订 r3，48 项/765 条，包内无 `sources/*`。已对父 `.4` 核查仅替换选煤 r2→r3、其余 47 项定义与 corrections 逐字节不变，并用内置公钥验证 Ed25519；随包集合与交付清单一致。上一轮 Candidate 从干净源码 commit `025d8c5a1bdb63afd53c61df7c5435604259d314` 构建；PR #28 合并后新 Candidate 的独立构建与验收见下段，不能据旧实物称 0.2.0 已发布。下文 `.4` 和 r2 叙述是其时阶段证据。

已按 Owner 批准将 16 项原样 `draft` 候选迁入唯一可编辑机器定义源 `data/definitions/`，现共有 64 项。`data/delivery-scope.json` 显式选择随包 48 项（含历史项）、正式评价仅 `gb-29446-2019`；目录迁入不表示业务批准。`standards/development/scope-63/` 与 `scope-65/` 只读保留为历史快照，不是发布输入，也不能反向覆盖当前定义。旧规则确认表的只读校验和测试保留作历史证据；旧 `publish_confirmed_rules.py --apply` 与覆盖多目录的 promotion 写入口不作为现行发布方式。

**上一轮源码集成与 Candidate 交付续验：**[实施与验收记录](docs/governance/映射驱动单源规则与同源报告_V3_验收记录_20261018.md)记载本地 full suite 为 1110 passed、62 skipped、0 failed、1 warning；[交付补充验收记录](docs/governance/映射驱动单源规则与同源报告_V3_交付补充验收_20261018.md)记录 `025d8c5` Candidate Artifact 63/63、安装版与便携版实测、真实 Microsoft Word/WPS 四场景、同版本覆盖及卸载保留数据、可信旧 0.2.0 Candidate `.4`→`.5` 升级保留 r2 历史结果、构建源码 exact-head 三项 GitHub CI 通过。该次验收未执行 0.1.0→0.2.0 真实安装器覆盖；本次 RS05 收口已找回哈希吻合的历史安装器，旧载荷库级升级保真已证，旧 GUI 保存与两代安装器真实覆盖仍待验证；原生 Windows DPI／跨屏和 Windows 11 仍待环境证据。中央 ACTIVE 四文件已合并，业务 [PR #28](https://github.com/adgo07/ECQuota-Insight/pull/28) 已合并到 `main`（`8914d31da35ffb3e8f42cbea9a55a9075fea4d0e`），新 Candidate 独立结论见下段。RS05 仍 IN PROGRESS，Reference Standard Product Closure 仍 PARTIAL。

**合并后当前 Candidate 续验：**干净构建输入 `4e4349068bb56fa500d20cfab98ef6640e63605c` 生成 `rc-4e43490`；身份与 10 条文件哈希实算相符，冻结 EXE 自检 6/6、Artifact Gate 63/63、该构建源码三项 GitHub exact-head CI 均通过。新安装版 GUI 保存／重启读回及三份 DOCX 导出、临界与未达3级真实 Word/WPS 实开、便携 ZIP 中文路径 GUI 启停、可信旧 r2 数据克隆升至 `.5` 且历史 JSON 不变，详见[交付补充验收记录 §6](docs/governance/映射驱动单源规则与同源报告_V3_交付补充验收_20261018.md)。本次又验证可信正式 0.1.0 安装载荷的**库级**旧记录升级保真，真实旧 GUI 和两代安装器覆盖仍缺证，见 [RS05 本机收口结果](docs/governance/RS05_EXECUTION_REPORT.md)末节。上一段 `025d8c5` 是历史 Candidate 证据，不能替代当前构建身份；当前仍是未正式发布的 Candidate，RS05 = IN PROGRESS、产品闭环 = PARTIAL。

> `PARTIAL` **不等于“可发布”**；Windows 交付已有本机实测证据，仍缺上述环境覆盖与正式收口结论。

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
- 当前 `data/definitions/` 为 64 项（其中 16 项 `draft`），随包范围仍为 48 项；**当前软件正式评价范围只有 GB 29446—2019**。这 16 项候选未因目录迁入获得业务批准或正式支持；
- GB 29435-2025 为 `published/future`，实施日期 2027-01-01 前只能预览；
- 当前只有 Windows 桌面版；Web / Linux / 安卓 / 苹果 / 鸿蒙 与网络更新仅为架构方向；
- 普通页面不含企业属性、单一煤种工艺确认及合规主结论；GB 29446 专用页面已按批准映射 D01 同步显示“未达3级”，适用边界见[统一判定规范 §10](docs/统一判定规范.md)。

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

标准问题与Numeric治理：

- 当前标准问题统一以 `STANDARD_ISSUES_REGISTER.md` 为准；历史 ROUND6 是已修复的Numeric软件缺陷，原GB29446标准问题编号不再有效。
- RS04 Golden保留正式全值比较边界案例，依赖锁定的Numeric v1 / Profile / 判定规范，不再依赖旧标准问题条目。

**RS05 已修复（RS04 登记的 Release Gate）**：

- corrupted historical `result_json`：RS05 已按行隔离反序列化，单条损坏记录降级显示并记录 WARNING，
  不再中断“评价记录”页、首页或应用启动；detail 明确提示“记录损坏”。

**RS05 Blocker 历史处理记录**（其时 r2 / `.4`，当前包身份以上文 PIN 为准）：

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
- 当时未关闭（旧环境）：无 Windows 11 环境、单显示器，无法实测多 DPI 与跨屏拖动，原记录为 BLOCKED / PENDING-MANUAL。2026-10-27 已有 Win11 源码原生 150% 局部观察；最终候选、125%／跨屏仍待验，按第 4 节当前交接处理。

## 9. 下一步

- 当前阶段：RS05 — Product Simplification & Standard Library Pairing（IN PROGRESS）；RS06 保持 NOT STARTED；
- 普通用户只使用随软件配套的标准库，不再手动安装、导入、扫描或管理标准包；
- Excel Adapter / Canonical Input / 共用 Calculator / Decimal 安全链继续保留；Excel 正式用户流程暂缓开放；
- 设置页收敛、标准包普通入口移除、版本配套、Application readiness gate 与恢复后即时 reconciliation 已有本轮源码及 Candidate 证据；当前工作不重复实现这些完成项；
- 定向回归、RS04 Golden、Numeric/N01-A、literal full suite、Source Gate、Windows Candidate、Artifact Gate、自检及构建源码 exact-head CI 已按对应提交取得证据；后续仅在构建输入改变或实测发现缺陷时按影响复验；
- PR #33 已合并；纳入经审核文档后由干净 source SHA 重建最终候选，按[RS05 最新交付矩阵](docs/governance/RS05_EXECUTION_REPORT.md)核对实物门禁与隔离环境证据。`rc-4e43490`、`rc-f689658` 与 PR #32 的 `rc-b102e36` 均保留各自历史身份，不能代替当前 UI 最终候选。源码 Win11 原生 150% 局部观察不等于最终安装包、真实离线、125%／跨屏或两代安装器覆盖通过。不正式发布 v0.2.0，不开始 RS06。

Reference Standard Product Closure 仍为 PARTIAL。

**2026-10-21 历史验收准备包：**[当时的验收包记录](docs/governance/RS05_EXECUTION_REPORT.md#2026-10-21-验收准备包当时准备记录)和[库级升级小型证据摘要](docs/governance/evidence/RS05_20261020_legacy_upgrade_summary.json)保留原日期、资产身份与未测边界；后续实包状态以本报告较新日期补录和上方当前交接为准。准备包三份可审文本不代表二进制资产已跨机交付。

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
  「查看标准原文」，点击后请求浏览器打开**全国标准信息公共服务平台**上预先登记的官方页面
  （不进行运行时搜索或抓取）。未登记官方地址的标准，该入口禁用并提示
  「官方来源地址尚未登记」。
- 标准定义中仍保留标准编号、原文文件名与 SHA-256 等**追溯元数据**，但不再分发原文文件本身。
- 评价记录的时间按**操作系统本地时区**显示，精确到秒（数据库仍以 UTC 存储）。
