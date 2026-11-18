# GB 21342—2025 Stage D 验收记录

记录日期 2026-11-18。验收对象为 [PR #41](https://github.com/adgo07/ECQuota-Insight/pull/41) 的候选运行源码 `cae84828f9d6fa8cae8f5d8298d6012a88534467`，包含普通标准切换修复和焦炭 Word 分页修复。焦炭当前状态为 **IMPLEMENTED，Stage D OPEN**。候选普通对标支持选煤与焦炭。精确候选的安装升级与严格全量结果待核实，完成后再按 Owner 授权办理合并。0.2.0 尚未发布，水泥正式验收继续暂缓。

## 平台与 Contract 预检查

- 仓库 `origin` 指向 `adgo07/ECQuota-Insight`。核对候选源码、当前分支与工作区后同步远端，`main` 与 `origin/main` 一致。中央锁定 SHA 为 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`。见 [platform-lock.json](../../platform-lock.json)。
- 相关 Frozen 基线为 Architecture 2.1、Numeric Contract v1、Numeric Profiles v1 和 Numeric Conformance Vector v1。正式链遵循 `ECQUOTA_DECIMAL_FULL_VALUE_V1` 的 Decimal 全值精确比较，保持规则、计算器、数值配置与保存快照可追溯。禁止隐式修约、显示值回流判级，以及因版本变更重算历史记录。
- 两项验收发现归类为 `LOCAL DEFECT`。标准下拉继承单标准页面的禁用状态，现按可选标准数量启用。焦炭短报告存在孤尾页，现调整焦炭表格段距、移除表后空段，并保持计算与判级依据段落连续。沿用现行 Frozen 基线，无需中央 Contract 修改。
- 相关 Standard Issue 为 **是**，编号 `ECQ-STD-GB21342-001` 至 `ECQ-STD-GB21342-005`。2026-11-18 Owner 批准现行映射 V1.1 及 D01—D05 软件处理决定。本次验收沿用这些决定，未新增或改变标准解释。疑义状态以独立台账为准。见 [现行批准映射](../../standards/mappings/GB21342-2025/标准映射表_V1.1_审核稿.md)和[标准问题台账](../../STANDARD_ISSUES_REGISTER.md)。

## 已核实的结果

| 项目 | 证据与结果 |
|---|---|
| 正式签包与同源 | `2026.11-published.1`，包 ID `gb21342-r2-from-2026.10-published.5`，SHA256 `f649e085941b41e3c942c37038ab41d582797cf0473d49a26c860b1b9d609b2f`。使用产品现有 Ed25519 公钥验签通过，PIN、包清单与 48 项机器定义逐项相符。焦炭由 r1 更新为 r2，其余 47 项定义和更正清单逐字节一致。仍为 765 条规则，原文成员为 0。见 [PIN](../../release/standard-packages/PIN.json)。 |
| 真实 Windows Qt 桌面 | 精确 `cae8482`，以 `windows` 平台插件启动普通主窗口，Windows 窗口句柄可见，Qt 窗口已暴露且位于前景。QTest 使用鼠标和键盘从默认选煤切换焦炭，填写顶装焦炉场景，点击计算并保存。结果为 111 kgce/t、1 级，保存恰好一条 r2 记录。继续点击历史结果、输入与依据页签及导出按钮，操作真实 Qt 文件保存和导出完成对话框。抽样结果与保存快照及导出报告一致。 |
| 实屏截取 | 表单、结果及历史两个页签均从 Windows 前景窗口裁切，客户区抽样像素与 Qt 窗口抓取一致率均为 1.0，四图已逐张目视复核。该项为源码窗口自动化，安装实物检查另见待核实项。 |
| 普通应用样例 | 使用正式签包对账，通过普通应用服务计算并保存下表四例。应用级升包烟测从 `2026.10-published.5` 升至现行包，生成升级备份，既有选煤请求、结果与规则快照逐字节一致，焦炭 r2 可继续形成新记录。 |
| Microsoft Word | Microsoft Word 16.0 Build 16.0.20326 逐份只读打开、实际复排并导出 PDF。三个短样本各 1 页，实测能流样本 2 页，共 5 页逐页目视复核。能流样本第 1 页包含能流输入及换算，第 2 页包含完整计算与三级判级依据。五页均无裁切、重叠、缺字、孤立标题或等级列表夹断。 |
| 源码定向回归 | 形成 `cae8482` 的变更内容通过 126 项定向测试，耗时 272.93 秒。范围涵盖焦炭应用、保存记录、能流折标、选煤和水泥报告、正式范围及桌面回归。 |

### 普通应用样例与 Word 实开对应

| 样本 | 已保存结果 | Word 实排页数 | 原 DOCX SHA256 |
|---|---|---|---|
| `level-1.docx`，顶装焦炉 | 111 kgce/t，1 级 | 1 | `cc9b92e9a2f1c8cc2f9368717dab1dd50f130ecbf0643a50b4246617797ca742` |
| `level-3.docx`，捣固焦炉 | 130 kgce/t，3 级 | 1 | `b25b1b9f3bebb2de1ff0c61144d2d4c31996eb7a52efadadbfe3cdc8b8652133` |
| `exceeds-level-3.docx`，顶装焦炉 | 140 kgce/t，未达 3 级 | 1 | `a8fee6e85500501b2b282007bd441f615bd61d5e85ab561108bcb95a7e057702` |
| `measured-flows.docx`，天然气实测收到基低位热值、蒸汽实测热焓 | 100.00 kgce/t，1 级 | 2 | `fcfde957bfb3e84bbef48aa0c7726fffe0142ae564e2e2db02f792cfcca2b323` |

### 实屏与导出证据索引

运行过程文件可随 PR #41 提交外部验收证据。机器生成的原始环境路径、隔离数据库和进程信息保留在执行现场。

| 材料 | SHA256 |
|---|---|
| `01-form-screen-crop.png` | `56d401585c3245a23f8302dece5abda10268a970667c4dd66209554be5600ac1` |
| `02-result-screen-crop.png` | `51bd16860c019a2a3cdf953944e8a89783f4871c4b93aba665fa9eaad378cc17` |
| `03-history-result-screen-crop.png` | `cd803ca0612a0411dc0024ae1cd9168ca1ddad79697eb517398c071d86539459` |
| `04-history-inputs-screen-crop.png` | `c193ad7bdd392695b2374b1cb65fa676116641c30b8400b0e40edb23184d6a86` |
| `coke-native-export.docx` | `55d527700e686a5c7d35a9af1138231666566f6b597f9b13fea2c89a71057ef3` |

## 待核实的门禁

| 项目 | 状态 | 收证要求 |
|---|---|---|
| 精确候选 Windows 实物 | 待核实 | 以运行源码 `cae8482` 生成的候选实物为准，登记 EXE 与安装包身份、安装和覆盖升级结果，核对配套包及安装后启动。 |
| 精确候选全量回归 | 待核实 | 登记与候选运行源码对应的严格全量及适用 CI 门禁。历史开发包和跨提交诊断只作历史记录。 |

待两项门禁核实后在本记录续录证据及结论。历史阶段详见 [Stage C 实施记录](GB21342_PRODUCT_IMPLEMENTATION_20261117.md)。
