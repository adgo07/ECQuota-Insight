# GB 21342—2025 Stage D 验收记录

记录日期 2026-11-18。候选普通对标覆盖选煤与焦炭。已通过 Windows 原生 Qt 桌面、Microsoft Word 实开及 Windows 独立安装升级专项验收。候选已实施，正式构建与严格全量结果尚待核实。同一运行源码的正式构建与严格全量通过、PR #41 合并后，焦炭支持状态生效为 **SUPPORTED**。0.2.0 尚未发布，水泥正式验收继续暂缓。见 [PR #41](https://github.com/adgo07/ECQuota-Insight/pull/41)。

## 核对的源码身份

- 原生窗口和 Word 证据对应运行源码 `cae84828f9d6fa8cae8f5d8298d6012a88534467`。
- 独立 Windows 安装器对应精确源码 `8ea5a166cbc8dfc85a5585b0c0020385cecf1ef6`。两提交之间的改动在验收流程、测试和治理文档，`src/`、`data/`、`release/` 和 `pyproject.toml` 逐路径核对一致。实际安装器及 EXE 身份见下文。

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
| 实屏截取 | 表单、结果及历史两个页签均从 Windows 前景窗口裁切，客户区抽样像素与 Qt 窗口抓取一致率均为 1.0，四图已逐张目视复核。该项为源码窗口自动化，安装实物的环境和检查点另见下文。 |
| 普通应用样例 | 使用正式签包对账，通过普通应用服务计算并保存下表四例。应用级升包烟测从 `2026.10-published.5` 升至现行包，生成升级备份，既有选煤请求、结果与规则快照逐字节一致，焦炭 r2 可继续形成新记录。 |
| Microsoft Word | Microsoft Word 16.0 Build 16.0.20326 逐份只读打开、实际复排并导出 PDF。三个短样本各 1 页，实测能流样本 2 页，共 5 页逐页目视复核。能流样本第 1 页包含能流输入及换算，第 2 页包含完整计算与三级判级依据。五页均无裁切、重叠、缺字、孤立标题或等级列表夹断。 |
| 源码定向回归 | 形成 `cae8482` 的变更内容通过 126 项定向测试，耗时 272.93 秒。范围涵盖焦炭应用、保存记录、能流折标、选煤和水泥报告、正式范围及桌面回归。后续测试修复 `f8bb608` 的选煤校验、焦炭普通应用和评价范围三文件通过 53 项。 |

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

## Windows 独立安装升级专项

运行 `44320245761` 的 `installer-diagnostics` 作业 `134856968027` 在 Windows Server 2025（10.0.26100）完成，结论为 success。依赖安装、诊断包构建、隔离安装升级及证据上传均通过。构建含冻结自检 6 项及 Artifact Gate 63 项。该作业以诊断模式构建并仅上传验收证据，正式交付和严格全量由正式流程执行。见 [运行 44320245761](https://github.com/adgo07/ECQuota-Insight/actions/runs/44320245761/job/134856968027)。

依据历史源码 `a83a838a01ca48dd8e8afdf061a7402aef1e7a0c` 重建 0.1.0 安装器，使用实际历史签名包，两个工作簿采用布局占位。隔离账号先安装旧版，原生启动并保存样例记录，再使用 8ea 候选安装器沿同一 AppId 和位置覆盖。清理旧 `_internal`，新程序及焦炭签包哈希均匹配。首次启动、重开、同版重装和卸载后数据保留均通过。旧记录 ID、请求、结果、规则快照及删除标记逐项一致，焦炭 r1 和 r2 同在。卸载移除程序与注册，四份安装或卸载日志均成功。

| 证据 | SHA256 |
|---|---|
| 重建的 0.1.0 安装器 | `f87abb88cb2568acd56ea87be58e5352b1694d6972537387a07e7a83ab8d4371` |
| `8ea5a16` 独立诊断安装器 | `dd9f0c65dd0a1aefde6c661a7bf4d810834a24f211d0f760bcba7cb7497c8e3c` |
| `8ea5a16` 诊断包 EXE | `6c12924299fd390fb8e027eb5b0ceb42cab36ab1cecb5ebabdbc60ab10fd5ebf` |
| 下载并独立复核的证据 ZIP | `4ebac31a30b8d33002dcb17aa7f9524c5da0e65ae54bd6e3d0ef0683eed05c5f` |

证据工件 `UEBench-Installer-Diagnostics-8ea5a166cbc8dfc85a5585b0c0020385cecf1ef6` 包含机器摘要、安装及卸载日志。见 [Windows 独立安装验收证据](https://github.com/adgo07/ECQuota-Insight/actions/runs/44320245761/artifacts/14433849504)。

## 待核实的交付门禁

| 项目 | 状态 | 收证要求 |
|---|---|---|
| 正式 Windows 候选构建 | 待核实 | 核对 [正式运行 44320265653](https://github.com/adgo07/ECQuota-Insight/actions/runs/44320265653) 的结论，并登记交付 EXE、安装包及配套包身份。 |
| 严格全量及适用 CI | 待核实 | 核对与正式运行源码及最终文档 HEAD 对应的严格全量结果。 |
| PR #41 合并 | 待办理 | 上述门禁通过后按 Owner 授权合并，焦炭支持状态生效为 SUPPORTED。 |

在本记录续录正式门禁证据和结论。历史阶段详见 [Stage C 实施记录](GB21342_PRODUCT_IMPLEMENTATION_20261117.md)。
