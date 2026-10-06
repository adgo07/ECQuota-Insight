# Windows 程序包第一轮瘦身执行报告

日期：2026-10-06。范围：ECQuota-Insight 原项目目录中的打包配置与门禁测试；不改业务规则，不替换已有 Candidate，不推送或合并 PR。

## 1. 平台 / Contract 预检查

- 已实际确认工作树、origin、分支、HEAD、状态，并执行 `git fetch origin`。
- origin：`https://github.com/adgo07/ECQuota-Insight.git`；分支：`feat/ecq-rs05-windows-v1-release`。
- 修改前业务仓 SHA：`1ee4ad78ff0575cf97077fce32847bc7b7110a82`；工作区干净；`main` 与 `origin/main` 的左右差异均为 0。
- `platform-lock.json` 锁定中央 SHA：`ee5feb0cc34dbd99790500fadd0c4c932e202a20`；本地 lock 文件 SHA256：`3c1708fa1f619235310b31b9aadb5eed4ea6330c644af534c09050ae7fe67d4a`。
- 已读取 AGENTS、TASK_STATE、HANDOFF、参考标准开发路线、Standard Issues Register、platform-lock，以及直接相关打包代码；中央 GUIDE_INDEX 路由的交付政策亦已读取。
- 本任务不涉及中央公共 Contract。既有 Architecture 2.1 与 Numeric v1 锁定不变；MUST 保留正式计算、签名验证、离线运行、迁移与追溯能力；MUST NOT 改数值口径、把显示值用于判级、改锁定基线或借瘦身删除审计能力。
- 未发现与已采用 Frozen Contract 的冲突，不需要中央 Contract 修改，不新增冲突分类。
- 当前有 `ECQ-STD-GB29446-001`（PROVISIONAL），但本任务不涉及其标准解释或计算决定。不改变既有软件解释。
- 当前仍为 RS05 Release Candidate；本报告不宣布 RS05 完成或正式发布。

## 2. 清理决定与实际修改

问题不是公式复杂，而是打包配置把整个 PySide6 安装目录的 DLL 手工平铺进程序；Qt 自动 hook 又收集实际依赖，形成无关模块与重复副本。

`uebench.spec`：取消 `PySide6/*.dll` 全量手工复制，只保留现有 Windows 加载兼容副本 `Qt6Core.dll`、`Qt6Gui.dll`、`Qt6Widgets.dll` 和 `shiboken6.abi3.dll`；自动依赖与插件收集保持开启。保留 ICU 排除规则，并显式排除当前业务不用的 QtWebEngine / QtWebView。

`tests/test_release_source.py`：新增执行真实 spec 输入装配的门禁，防止额外安装 Designer、Quick、Qml、Pdf、Multimedia、3D、avcodec、WebEngine 后再次被整批手工复制。

实际新载荷减少 187 个相对路径文件。包括无关 Designer、Multimedia/编解码、Quick3D 等模块，以及原来平铺的 PDF、QML、Quick、软件 OpenGL 等副本。注意：自动 hook 判定需要的 PDF、QML、Quick、软件 OpenGL 正本仍在，不能把“取消平铺副本”理解成彻底移除了这些能力。

未删除源代码、标准库、原文、Excel、迁移、数据库、签名校验、测试或历史证据；未改运行时加载 hook。已有下载目录、正式 dist/release 和旧 Candidate 不做就地删 DLL 操作。此次“删除”发生在后续构建输入及新构建载荷中，原发布物不变，配置可经 Git 恢复。

两位 `gpt-6-luna / max` 子 agent 分别只读核对 Qt 使用与剩余依赖；修改、实测和结论由主 agent 完成。

## 3. 同环境实际构建对比

均用项目 `.venv`：Python 3.13.3、PyInstaller 6.20.0、PySide6 6.10.1；同一 spec 构建方法、同一压缩方法，不使用全局 Python。基线先构建，再应用配置修改构建瘦身版。所有实验输出在 `work/package-slimming-20261006/`，不覆盖原发布物。

| 项目 | 修改前 | 修改后 | 实际减少 |
|---|---:|---:|---:|
| 解压后载荷 | 371,926,580 B / 354.70 MiB | 180,577,684 B / 172.21 MiB | 182.48 MiB / 51.45% |
| 文件数 | 461 | 274 | 187 |
| 便携 ZIP（Optimal） | 161,078,481 B / 153.62 MiB | 79,446,917 B / 75.77 MiB | 77.85 MiB / 50.68% |
| 构建耗时（单次） | 138.73 秒 | 65.49 秒 | 非性能基准，仅记录本次实测 |

载荷清单哈希：基线 `cabc87bcdb8a4e25fa4c940f8e5ddbde4883599908b1523e0f8334cf7448f3af`；瘦身版 `ee0dc8f661ce1225c58e4f55c37a5df52a75e5c4efc93339d72fd52b988a2fc1`。

便携 ZIP SHA256：基线 `fa6afe4830c36222b18162d38826ec6549cfdb0d625a570779631930d84ba95d`；瘦身版 `8a9cb8d24ee9428339e949aee4342896b904b6129392518db9effd5eb9ff7b77`。对比构建、ZIP 和测试证据暂留，因此实验目录约 0.91 GiB；项目目录总占用并未减少，此处收益指交付载荷。验收后可单独清理实验缓存，本次未删除证据。

用户下载的旧 Candidate 为 CI Python 3.13.15 环境，解压约 354.48 MiB、便携 ZIP 153.57 MiB；不能把它与本机重构建的差异都归因于本次修改。上表才是受控前后对比。

本次没有构建新 Inno Setup 安装器。旧安装器约 101.73 MiB；其 `lzma2/ultra64`、solid 压缩已较强，不能直接按 51% 推算安装器结果。正式安装器体积必须在下一次完整 Candidate 构建中实测。

## 4. 验证结果与限制

- Source Gate / 版本一致性：80 通过，0 失败（18.25 秒）。
- 新冻结 EXE `--self-check`：退出码 0，6/6 通过：构建信息、标准包验签、数据库初始化、Golden 回放、记录往返、Excel 导入链路。Golden 回放为自检内置的 3 个代表案例，不冒充全部 Golden Case 或人工 Excel 实机重算。
- 内置 `.4` 标准包 SHA256 保持 `023d5caf81dd6ba1ce41a5b5d8a59676db20dd98db510b6c4329600aa47e77ff`，规则与计算实现未改。
- 全量测试：**1017 通过、0 失败、0 错误、66 跳过**，共收集 1083 项，退出码 0，耗时 1279.18 秒（21 分 19 秒）。JUnit 报告独立核对计数一致。65 项因未设置 `UEBENCH_ARTIFACT_DIR`、未声明完整新 Candidate 而跳过；1 项因环境不能创建目录符号链接而跳过。1 条警告来自重复 ZIP 成员的拒绝测试夹具，不是新增业务失败。
- 启动诊断：隔离数据目录中运行进程未提前退出、Responding=True；真实加载 QtCore/Gui/Widgets，完成数据库迁移和标准包安装。20 秒内未取得主窗口句柄/标题，因此只算启动链路诊断，**不能认定真实页面烟测通过**。仅关闭本次启动的测试进程。
- `git diff --check` 通过；LF/CRLF 提示不是差异错误。
- 两次构建均有相同的可选 hidden import 提示（tzdata、pysqlite2、MySQLdb）；没有本次裁剪新增的构建告警。

这只是瘦身配置验证，不是重新完成发布验收。尚需正式 Candidate 流程、安装/卸载/升级、窗口页面操作、低配置/无独显兼容等检查；新的实验 EXE 不得冒充源 SHA 干净且完整签名清单对应的正式 Candidate。

证据：`baseline-build.log`、`slim-build.log`、两份 `*-payload.json`、两份 `*-portable.zip`、`source-tests.xml`、`full-tests.log/xml`、`self-check.json`、`gui-smoke-data/logs/uebench.log`，均位于上述实验目录。

主要复现命令（PowerShell，项目根目录；输出目录应另取新名称，勿覆盖已有证据）：

```powershell
.venv/Scripts/python.exe -m PyInstaller --noconfirm --distpath work/package-slimming-20261006/slim-dist --workpath work/package-slimming-20261006/slim-build uebench.spec
.venv/Scripts/python.exe -m pytest -o addopts='' -q -p no:cacheprovider tests/test_release_source.py tests/test_release_version_consistency.py --basetemp work/package-slimming-20261006/pytest-source --junitxml=work/package-slimming-20261006/source-tests.xml
.venv/Scripts/python.exe -m pytest -o addopts='' -q -p no:cacheprovider --basetemp work/package-slimming-20261006/pytest-full --junitxml=work/package-slimming-20261006/full-tests.xml
work/package-slimming-20261006/slim-dist/UEBench/UEBench.exe --self-check --data-dir work/package-slimming-20261006/self-check-data --output work/package-slimming-20261006/self-check.json
```

## 5. 剩余体积与进一步建议

以下预估均针对 **172.21 MiB 解压载荷**，不是安装器或 ZIP 的压缩后大小，不把未经测试的依赖当作垃圾。

| 优先级 / 项目 | 当前占用或最大可省 | 建议及前提 |
|---|---:|---|
| 下一步：四个加载兼容副本去重 | 约 25.34 MiB | 主 DLL 实测从包目录加载，但这不证明平铺副本在所有 Windows 环境都无用。单独验证加载路径、首次启动、干净机和安装器，再决定；通过后解压约 146.87 MiB。 |
| 可研究：Qt PDF 图像插件链 | 约 5.31 MiB | `qpdf.dll` 与 Qt6Pdf；原文由系统查看器打开不代表图像插件从无依赖。确认资源/预览不依赖 PDF 图像格式后再删，并回归原文入口和图片加载。 |
| 可研究：虚拟键盘 / QML / Quick 链 | 相关 DLL 约 12.46 MiB | 当前源码未直接使用不等于 hook 依赖不存在。先定位插件依赖链，验证输入法、文本输入、辅助功能，再裁剪；与其他插件节省可能重叠，不能简单相加。 |
| 小收益：Qt 多语言翻译 | 96 个文件共 6.18 MiB | 中文优先可做语言白名单，但标准对话框、语言回退需实测；不承诺全额可省。 |
| 暂不删：软件 OpenGL | 19.68 MiB | 无独显/旧驱动/远程桌面可能依赖；收益可观但兼容风险较高，须有对应机器证据。 |
| 不建议：重写 UI 或删除业务依赖 | 无安全直接收益承诺 | Python/Qt 是独立运行成本；cryptography 用于验签、openpyxl 用于 Excel、SQLAlchemy/Alembic 用于数据库与迁移、pydantic 用于校验，均有实际用途。不要用削减正式能力换体积。 |

不同名字或相同名字但不同哈希的 OpenSSL / MSVC 库不得按文件名强行去重。开发依赖与运行依赖拆分有利于 CI 管理，但不等于 PyInstaller 会把每个已安装依赖打进程序，不能承诺因此再明显缩小。

已通过新载荷实际 PE 导入表核实：`qtvirtualkeyboardplugin.dll → Qt6VirtualKeyboard.dll → Qt6Qml.dll / Qt6Quick.dll`；`qpdf.dll → Qt6Pdf.dll`。因此这些剩余项确有插件依赖来源，不是凭文件名判定的无用文件。本轮保持不动。

最终工作区仅三项修改：`uebench.spec`、`tests/test_release_source.py`、本报告。尚未提交、推送或合并；不覆盖 PR #13 的已有交付物。全量测试完成后只补录报告，再次做差异检查，不重复把文档更新冒充新一次测试。

当前结论：第一轮已把可确认的过量手工复制清掉，便携 ZIP 实测约 76 MiB；对可离线独立运行的 Python + Qt 桌面软件，剩余体积主要是运行基础设施，不是选煤公式本身。建议先验收这一轮，再以“核心 DLL 去重”为第二轮独立小改动，不一次性叠加高风险裁剪。
