# 第二轮打包裁剪验证报告

日期：2026-10-06。任务：验证上一轮提出的五组内容是否可以从交付载荷移除。本轮只操作 `work/package-trim-validation-20261006/` 隔离副本；不修改正式打包配置、不替换现有 Candidate、不推送或合并。

## 1. 平台 / Contract 预检查

- 实际 origin：`https://github.com/adgo07/ECQuota-Insight.git`；分支 `feat/ecq-rs05-windows-v1-release`；执行时 HEAD `1ee4ad78ff0575cf97077fce32847bc7b7110a82`。
- 已执行仓库身份、分支、HEAD、状态和 fetch 检查；默认远端分支为 `main`，本地 `main...origin/main` 为 0 / 0。保留上一轮未提交的 spec、测试及执行报告，不覆盖这些改动。
- `platform-lock.json` 中央锁定 SHA：`ee5feb0cc34dbd99790500fadd0c4c932e202a20`；文件 SHA256 沿用未变更的 `3c1708fa1f619235310b31b9aadb5eed4ea6330c644af534c09050ae7fe67d4a`。
- 已读取 AGENTS、TASK_STATE、HANDOFF、参考标准开发路线、Standard Issues Register、lock 与相关打包/页面代码；中央当前 GUIDE_INDEX 路由的 PRODUCT_DELIVERY_POLICY 和 UI_DESIGN_GUIDELINES 已读取。
- 本任务不涉及中央公共 Contract。Architecture 2.1 与 Numeric v1 锁定不变；MUST 保持正式业务内核、签名、公钥、记录、Excel 和迁移；MUST NOT 修改计算规则、显示/比较语义、标准解释或锁定基线。
- 无 Contract 冲突，分类 N/A；不需要修改中央 Contract。现存 `ECQ-STD-GB29446-001` 不与本裁剪任务相关，状态与软件解释均不改变。
- 产品仍是 RS05 Release Candidate，不以本报告宣称正式发布或 RS05 完成。

## 2. 验证方法与证据边界

使用项目 `.venv` 的 Python 3.13.3 / PyInstaller 6.20.0 / PySide6 6.10.1，从上一轮 spec 派生仅用于测试的冻结入口。业务仍调用真实 `MainWindow`、`ApplicationFacade`、Calculator、标准包安装与数据库；没有写第二套业务算法。

启动环境清掉外部 Python / Qt / QML 路径变量，PATH 仅保留 Windows 系统目录。对四个核心 DLL 逐一检查实际加载位置必须位于被测副本，不能从开发环境补齐。除逐项 offscreen 测试外，还对基线/联合裁剪在 `windows` 平台插件下运行隐藏窗口测试；不把隐藏窗口的程序化操作称为人工视觉验收。

每组分别裁剪，再联合裁剪，保留软件 OpenGL。页面测试操作真实控件：两煤种的 12 个边界、k 自动产生且只读、中文输入、旧结果失效、无效工艺清空、官方原文地址路由、控件渲染、记录保存/详情/重新建立 context 后读取。原文入口截获 URL，不打开浏览器；输入法使用合成提交事件，不冒充真实 Windows 输入法或触屏实测。

另用未插桩的上一轮 `slim-dist` EXE 做联合裁剪后 `--self-check`，避免只证明测试入口可运行。

插桩载荷与原载荷均为 274 个文件；文件集合相同。差异只有 EXE 与 `base_library.zip`；后者的 154 个成员内容逐字节相同，仅归档元数据不同。所有其他运行库、插件、资源完全同源。原 EXE SHA256：`dd03e93a60e0185653871948297e6fa81879ef21d7dbd41f234bfe02c9a7f8cc`；最终探针 EXE SHA256：`cfff778e9a39ae15b63ed9a41d07d017e9a5ae2989b1cb1768e421ab3bff7421`。逐文件对比见 `probe-v4-original-comparison.json`。

### 验证工具本身的修正

早期试跑发现：探针未注入验签公钥，以及 `assert` 会被 spec 的 optimize=1 移除；这些早期结果作废。已改为正式公钥路径与显式异常门禁。

独立子 agent 又发现记录详情实际使用 `dialog.open()`，而非 `exec()`，最初详情检查未执行。最终修正为直接检查真实详情控件，并用必检名称集合/数量门禁防止漏检。中间 `matrix.json` 与 `matrix-r2.json` 均不是最终验收依据；以 `matrix-r3.json` / `gate-r3.json` 为准。

## 3. 实测结果

最终裁剪实验矩阵：**PASS（12/12 预期场景，0 项意外结果）**。这不是正式 Windows 发布验收 PASS。

| 实测类别 | 结果 |
|---|---|
| offscreen：基线、五组逐项裁剪、保留 OpenGL 的联合裁剪 | 7 组，每组完整必检集合 36/36 通过 |
| Windows 平台插件，隐藏主窗口/详情窗口：基线、联合裁剪 | 2 组，每组 36/36 通过 |
| 保留软件 OpenGL 的正对照 | 9/9 通过，实际加载随包软件 DLL |
| 删除软件 OpenGL 的负对照 | 退出 1，明确因软件 DLL 未加载失败；符合负对照预期，不是普通业务 regression |
| 未插桩原 EXE，联合裁剪 `--self-check` | 退出 0，6/6 通过 |

9 组 UI 测试共 324 项必检断言，记录详情在每组中确实执行；再加 OpenGL 正对照与原 EXE 自检，共 339 项正向检查通过。各组 UI 的 12 个边界逐例符合预先声明等级；常用 PNG/JPG/ICO 解码能力、中文翻译、四个 DLL 的包内加载路径均通过。PDF 组的 `supportedImageFormats` 只减少 `pdf`，其他格式仍在。

必检门禁校验名称集合与数量，不能因检查未执行而通过。最终结果文件：`gate-r3.json`、`matrix-r3.json`、`matrix-r3.log` 和 `run3/results/`；之前 r1/r2 不用于最终结论。

软件 OpenGL 对照已确认：保留 DLL 时，强制软件 OpenGL 会加载随包的 `opengl32sw.dll`；移除后该 DLL 不再加载。在本机，后者仍能创建 GL context，不能夸大为“所有渲染都失败”，也不能用它证明无显卡/旧驱动环境仍兼容。

源码全量回归没有本轮新结果：生产代码、正式 spec 与业务测试未再修改，上一轮实测是 1017 通过 / 66 跳过。本轮冻结裁剪矩阵与该源码回归是不同证据，不能混算。

## 4. 逐项删除结论

以下数值均针对解压载荷，不是压缩后的安装器。

| 项目 | 精确移除量 | 结论 |
|---|---:|---|
| 三个 Qt 核心 DLL + shiboken 平铺副本 | 4 文件 / 26,575,744 B / 25.34 MiB | 可作为正式裁剪候选，**只删重复副本**，保留 PySide6 / shiboken6 包目录中的正本和加载 hook。正式新 Candidate 仍需干净机门禁。 |
| Qt PDF 图像插件链 | 2 文件 / 5,568,448 B / 5.31 MiB | 当前产品可以移除。普通原文入口是官方网页，不使用 Qt PDF。裁剪后只失去 PDF 图像解码，常用图像格式保持。 |
| Qt 虚拟键盘 / QML / Quick 链 | 7 文件 / 13,538,336 B / 12.91 MiB | 条件裁剪候选。现有 Widgets 业务无依赖，但尚未做真实 Windows 中文输入法、触屏/辅助功能验证；不把合成输入事件当成这些验收。 |
| 非中文 Qt 翻译 | 90 文件 / 6,200,531 B / 5.91 MiB | 可按中文产品定位移除；保留 6 个中文文件，共 283,880 B。显式加载中文翻译已验证；不代表生产应用会自动加载翻译器。 |
| 软件 OpenGL | 1 文件 / 20,640,480 B / 19.68 MiB | **保留**。删除会失去随包的软件渲染器；暂无足以覆盖低配、旧驱动、远程桌面的证据。 |

核心副本的相对路径：`_internal/Qt6Core.dll`、`_internal/Qt6Gui.dll`、`_internal/Qt6Widgets.dll`、`_internal/shiboken6.abi3.dll`。

PDF 链：`_internal/PySide6/Qt6Pdf.dll`、`_internal/PySide6/plugins/imageformats/qpdf.dll`。

虚拟键盘链：`_internal/PySide6/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll`，以及 `_internal/PySide6/` 下的 `Qt6VirtualKeyboard.dll`、`Qt6Qml.dll`、`Qt6QmlMeta.dll`、`Qt6QmlModels.dll`、`Qt6QmlWorkerScript.dll`、`Qt6Quick.dll`。PE 导入表核实：虚拟键盘插件 → VirtualKeyboard → Qml/Quick；PDF 插件 → Qt6Pdf。

翻译只裁剪 `_internal/PySide6/translations/` 中不含 `_zh_` 的 `.qm` 文件，不按任意语言字符串跨目录删除。完整逐文件清单在最终矩阵 JSON 的 `excluded` 字段。

Qt 对软件 OpenGL 动态回退的说明见 [Qt 6.10 官方文档](https://doc.qt.io/qt-6.10/windows-graphics.html)。这里区分“本机构建试验通过”与“正式产品兼容性通过”，不承诺所有 Windows 环境都安全。

## 5. 联合裁剪体积实测

联合删除前四组，共 103 个文件；软件 OpenGL 保留。未插桩原 EXE 的实验载荷：

| 项目 | 第一轮瘦身版 | 第二轮联合实验版 | 进一步减少 |
|---|---:|---:|---:|
| 解压载荷 | 180,577,684 B / 172.21 MiB | 128,694,625 B / 122.73 MiB | 49.48 MiB / 28.73% |
| 文件数 | 274 | 171 | 103 |
| 便携 ZIP，同为 Optimal 压缩 | 79,446,917 B / 75.77 MiB | 57,410,513 B / 54.75 MiB | 21.02 MiB / 27.74% |

实验 ZIP SHA256：`07752b93abdea0b69d5cb3949caf9999dceddf23ffb3972b6a8e86a4f30c8ecc`。没有构建新安装器，不把 ZIP 缩减率套用到 Inno Setup。

**122.73 MiB / 54.75 MiB 是包含“条件候选虚拟键盘裁剪”的联合实验结果，不是已批准的正式发行体积。** 若暂不裁虚拟键盘链，仅其他三组可使解压载荷约 135.64 MiB；对应 ZIP 尚未单独构建，不给出伪实测值。

## 6. 下一步与交付状态

本轮不实施正式删除，只提供可追溯验证。建议正式修改分为：核心副本 + PDF + 非中文翻译；虚拟键盘链在真实中文输入法验证后决定；软件 OpenGL 保留。不得把 SDK 全部 DLL 删除、破坏正式发布物后继续沿用旧 hash 清单。

采用裁剪配置后，应从干净 source SHA 重建新 Candidate，重新生成身份/载荷清单/校验值，运行 Source Gate、Artifact Gate、自检、完整回归与安装/升级门禁。Windows 11、真实输入法、触屏/辅助功能、低配置及高 DPI 未验证部分仍应如实保留。

实验脚本、构建日志、逐项结果、原 EXE 自检和 ZIP 均位于 `work/package-trim-validation-20261006/`；该目录不属于正式发布物。已有下载 Candidate 与 `dist/release` 未改动，本轮没有删除用户数据。

实验 ZIP 属于上一轮本机 EXE 的条件联合裁剪副本，不包含正式 Candidate 身份与完整安装器验收，不能代替 PR #13 的原交付物。人工继续测试时必须使用隔离 `UEBENCH_DATA_DIR`，不要让实验 EXE 访问真实用户数据目录。

本轮最终仅新增本报告；上一轮两项代码/测试改动与报告保持原样。再次 `git diff --check` 无差异错误，未提交、推送或合并。
