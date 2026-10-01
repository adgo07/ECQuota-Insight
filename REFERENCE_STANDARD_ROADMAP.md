# ECQuota 参考标准开发路线

状态：**CURRENT INVENTORY / GOVERNANCE ROADMAP**
盘点日期：2026-10-01
盘点基线：`main@c2dea39bd609c89a6c29cc526e29680b556e6be6`
参考标准：`GB 29446—2019 选煤电力消耗限额`

> 本文件只记录当前真实能力与后续交付顺序，不修改 Calculator、标准规则、Numeric Profile、数据库、Excel 实现或 Windows 打包产物。

## 1. 平台 / Contract 预检查

| 项目 | 结果 |
|---|---|
| 当前业务仓 SHA | `c2dea39bd609c89a6c29cc526e29680b556e6be6` |
| `platform-lock.json` | 当前锁定中央 `ee5feb0cc34dbd99790500fadd0c4c932e202a20` |
| 中央 Contract | Architecture V2.1 FROZEN；Numeric Contract v1 / Numeric Profiles v1 / Numeric Conformance Vector v1 FROZEN；Unit/Module/Record/qzpack 仍 DRAFT |
| 本路线相关 Frozen Contract | Architecture V2.1；Numeric Contract v1 |
| 适用 MUST | 权威计算遵守 Numeric Profile；默认 full-value exact；无隐式 ROUND6；Windows-first；Excel 后续共用同一业务内核 |
| 适用 MUST NOT | 不自动跟随中央 `main`；不把 Excel 另做一套算法；不因本盘点修改 Frozen Contract |
| 是否发现中央 Contract 冲突 | 否 |
| 已知 OPEN | lossless XLSX numeric-cell 公共方案仍 OPEN |
| 是否需要修改中央 Contract | 否；本任务只记录现状 |

中央产品交付治理文件：`Qingzhou-contracts/docs/governance/PRODUCT_DELIVERY_POLICY_V1.md`。该文件属于产品交付治理，不改变本仓 `platform-lock.json` 的 Frozen Contract 锁定 SHA。

## 2. 状态定义

| 状态 | 中文解释 |
|---|---|
| `DONE` | 已完成，并有当前可核对证据 |
| `PARTIAL` | 部分完成；仍缺少参考标准完整交付所需事项 |
| `NOT STARTED` | 尚未按本路线开始 |
| `BLOCKED` | 被明确外部或治理条件阻塞 |

## 3. 参考标准现状盘点

| 项目 | 状态 | 证据与说明 |
|---|---|---|
| 标准库 | `DONE` | `data/definitions/gb-29446-2019.json` 已存在于正式定义；`data/catalog.json`、标准生命周期/来源能力和对应规则测试均已存在。 |
| 新建评价 | `DONE` | `HANDOFF.md` 明确记录 GB29446 新建页面源码已通过独立验收并合入；`src/uebench/ui/main_window.py` 与 `tests/test_gb29446.py` 提供实现/测试证据。 |
| 输入 | `DONE` | GB29446 页面、Application/Domain 输入模型及 `tests/test_gb29446.py` 已覆盖该标准输入和业务路径；当前 Numeric v1 要求正式数值使用 Decimal 权威语义。 |
| 校验 | `DONE` | Domain Engine、GB29446 专项测试、Numeric v1 Conformance 已覆盖正式边界与非法数值入口；无依据 ROUND6 已移除。 |
| Calculator | `DONE` | `src/uebench/domain/engine.py`、`tests/test_gb29446.py`、N01-A Pilot 和 Numeric v1 adoption 共同证明正式判定链可执行。 |
| 等级 | `DONE` | N01-A 已执行 exact T−δ/T/T+δ 边界并验证 full-value exact 等级语义；当前正式结果不再依赖默认 ROUND6。 |
| 结果解释 | `PARTIAL` | 软件已有结果展示、标准来源和用户说明能力；但按本治理规则尚缺“GB29446 最新参考标准完整产品闭环”的一次集中正式验收，尤其要把计算依据/标准依据/来源作为独立交付项确认。当前不影响 Calculator 正确性，但影响 Reference Standard 全流程宣布 DONE。 |
| 正式记录 | `PARTIAL` | 仓库已有数据库、Repository、`tests/test_persistence.py` 等持久化能力；但现有证据未把“GB29446 最新页面 → 正式保存”作为本次 Reference Standard 闭环重新做端到端验收，因此暂不标 DONE。 |
| 历史记录 | `PARTIAL` | 当前 UI/持久化基础和历史功能存在；尚缺本路线要求的“保存 GB29446 → 关闭/重新进入 → 查看并正确恢复结果”的明确最新 E2E 证据。 |
| Windows | `PARTIAL` | Windows x64 是现产品平台，已有 PyInstaller/Inno Setup 构建、隔离安装/启动/卸载历史证据；但 `HANDOFF.md` 明确记录 GB29446 新页面源码合入后**新版 EXE/安装包尚未同步验收**。因此最新参考标准 Windows 交付不能标 DONE。 |
| Excel | `PARTIAL` | `src/uebench/infrastructure/excel.py`、`tests/test_excel.py` 已有成熟 Excel 基础；Numeric v1 adoption 已规定 authoritative XLSX numeric cell 若被 openpyxl 物化为 `float` 则拒绝、正式数值列采用文本十进制。缺口：最新版 GB29446 公式 Excel/完整 GUI↔Excel 同输入同结果闭环尚未同步验收；中央统一 lossless XLSX scheme 仍 OPEN。 |
| Conformance | `DONE` | `tests/conformance/numeric/`、N01-A vectors/tests、Numeric v1 adoption workflow 已建立并通过；GB29446 exact boundary、display separation、legacy-vs-current 均有证据。 |
| Golden Case | `PARTIAL` | N01-A 有强边界/迁移向量作为数值证据，但当前仓库未见与 EquipEffi 类似的“具名审批、覆盖完整用户业务流程”的 GB29446 正式 Golden Case 资产。缺口不影响已有 Numeric Conformance，但影响 Reference Standard 产品级 Golden Gate。 |
| 打包 | `PARTIAL` | `uebench.spec`、`packaging/installer.iss`、`scripts/build_release.ps1` 等正式打包链存在；旧发布包曾完成安装/便携测试。由于最新 GB29446 页面后的 EXE/安装包未同步验收，当前参考标准打包状态为 PARTIAL。 |
| 下一标准准备状态 | `NOT STARTED` | 仓库已有其他标准资产继续维护，但依据新治理规则，不把“继续新增标准”作为当前主任务。应先关闭 GB29446 的结果解释、记录/历史 E2E、Windows 最新包、Excel 与 Golden Case 缺口，再明确选择第二个架构验证标准。 |

## 4. 当前结论

GB 29446—2019 的 **业务计算和 Numeric 正确性已较成熟**，目前主要缺口不在重写 Calculator，而在产品交付闭环：

```text
结果解释正式验收
+ 正式记录/历史恢复 E2E
+ 最新 Windows EXE/安装包同步验收
+ 参考标准 Excel 完整闭环
+ 产品级 Golden Case
```

因此当前 Reference Standard 总体状态：

`PARTIAL`

这不是中央 Contract 阻塞，也不授权本治理任务顺手实现上述缺口。

## 5. 后续任务顺序

后续应拆成独立任务并分别验收：

1. GB29446 软件核心纵向闭环最终验收；
2. 最新 Windows 构建/安装/启动/中文路径/高 DPI/关闭与异常输入验收；
3. GB29446 Excel 导入/必要导出闭环，证明 GUI 与 Excel 调用相同业务内核并产生相同业务结果；
4. 建立/批准产品级 Golden Case；
5. Reference Standard Gate PASS 后，再选择第二个标准用于扩展架构验证。

不得在本路线图任务中自动进入上述实现。
