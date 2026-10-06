# 核心 DLL 重复副本移除执行报告

日期：2026-10-06。范围：仅移除核心 DLL 手工平铺重复副本；其他裁剪建议不实施。

## 1. 平台 / Contract 预检查

| 项目 | 结果 |
|---|---|
| 仓库身份 | `origin=https://github.com/adgo07/ECQuota-Insight.git`，实际根目录、分支、HEAD、状态已检查，已 fetch |
| 分支 / 当前业务仓 SHA | `feat/ecq-rs05-windows-v1-release` / `1ee4ad78ff0575cf97077fce32847bc7b7110a82`；工作区含上一轮未提交修改，本轮继续修改既有打包配置 |
| 默认分支 | `origin/HEAD=origin/main`；本地 main 与 origin/main 左右差异 `0/0` |
| platform-lock.json SHA256 | `3c1708fa1f619235310b31b9aadb5eed4ea6330c644af534c09050ae7fe67d4a` |
| 中央锁定 SHA | `ee5feb0cc34dbd99790500fadd0c4c932e202a20`，未修改 |
| 本任务相关 Frozen Contract | 本任务不涉及中央公共 Contract。Architecture 2.1、Numeric v1 等既有锁定语义保持不变 |
| 适用 MUST | 保留核心 DLL 正本与运行时加载能力；Windows-first；如实区分本地验证包与正式 Candidate；中文报告 |
| 适用 MUST NOT | 不改 Calculator / Decimal 正式比较 / 标准解释 / 数据库；不顺手裁剪其他组件；不将 dirty 工作区构建冒充正式 Candidate |
| 适用中央 ACTIVE 指南 | 已读取当前合并 GUIDE_INDEX、PRODUCT_DELIVERY_POLICY_V1、UI_DESIGN_GUIDELINES_V0.1；未升级 Frozen 基线 |
| 是否发现公共冲突 / 分类 | 否 / N/A |
| 是否需要中央 Contract 修改 | 否 |
| 是否存在与本任务相关 Standard Issue | 否；已读取台账，`ECQ-STD-GB29446-001` 仍 PROVISIONAL，与 DLL 去重无关 |
| 是否改变既有软件解释 | 否 |

## 2. 实际实施

`uebench.spec` 的手工 `binaries` 改为空列表，不再平铺收集下列四个副本：

| 移除的载荷路径 | 保留的正本路径 |
|---|---|
| `_internal/Qt6Core.dll` | `_internal/PySide6/Qt6Core.dll` |
| `_internal/Qt6Gui.dll` | `_internal/PySide6/Qt6Gui.dll` |
| `_internal/Qt6Widgets.dll` | `_internal/PySide6/Qt6Widgets.dll` |
| `_internal/shiboken6.abi3.dll` | `_internal/shiboken6/shiboken6.abi3.dll` |

PyInstaller 自动 Qt/shiboken hook 保持原样；`packaging/pyi_rth_uebench.py` 保持原样。
PDF 插件、非中文翻译、虚拟键盘、QML/Quick、软件 OpenGL 均未裁剪。
已有 ICU / WebEngine 过滤为之前配置，不属于本轮新增。

更新 Source Gate：执行真实 spec 的 Analysis 前装配，放置核心、额外 Qt 与 shiboken 占位文件，断言不会生成任何上述手工平铺副本。

重新从源码构建，不在旧发布目录直接删 DLL。因此不会产生与旧 payload manifest / hash 不一致的伪 Candidate。
原下载 Candidate、`dist/release` 与上一轮验证基线未覆盖；用户数据未触碰。

## 3. 实测结果

构建环境：项目 `.venv`，Python 3.13.3、PySide6 6.10.1、PyInstaller 6.20.0。

| 指标 | 上一轮瘦身基线 | 本轮仅核心 DLL 去重 |
|---|---:|---:|
| 载荷文件数 | 274 | 270 |
| 解压字节数 | 180,577,684 | 154,001,940 |
| 解压体积（MiB） | 172.21 | 146.87 |

净减少 **26,575,744 B = 25.34 MiB**。文件集合实测恰好少上述四项，无额外新增/删除。
全部其余 DLL、插件、翻译、资源与基线逐字节相同。
EXE 因重新构建发生变化；`base_library.zip` 元数据变化，但内部全部 154 个成员内容哈希相同。

本地验证 ZIP：`work/core-dll-dedup-20261006/UEBench-core-dll-dedup-local-test.zip`，
66,268,294 B = **63.20 MiB**，使用 Python zipfile Deflate level 6。
与前次 ZIP 压缩工具/参数不同，不把两者的 ZIP 差值全归因于 DLL 去重。
没有重建 Inno Setup 安装程序，不对安装程序减少量作实测声明。

## 4. 验证与限制

- 发布源码门禁：**153 passed**（`source-gate-r3.log`、`source-gate.xml`）。
- 新构建原 EXE 自检：**6/6**，隔离数据目录，exit 0。
- 新配置构建的插桩验证 EXE：offscreen **36/36**、Windows 原生平台隐藏窗口 **36/36**，exit 0。
- 两煤种 12 个等级边界、k 只读、输入变化旧结果失效、无效工艺清空、中文文本、合成输入法提交、记录保存与真实详情页、记录读取恢复、官方来源路由、Widget 渲染、图像格式与中文翻译均验证。
- 四个已加载 DLL 路径均实际定位到新包的 PySide6/shiboken6 正本目录，未借用开发机 Qt。
- 测试子进程移除外部 Qt/Python 环境变量，PATH 只保留 Windows 系统路径；数据均在 work 隔离目录。
- 插桩载荷和原 EXE 载荷文件集合相同；仅 EXE 与 base_library.zip 容器不同，其他文件逐字节相同；该 ZIP 内部内容也相同。
- 仓库全量测试：**1,017 passed、66 skipped、0 failed、0 errors**，exit 0；独立 collection 为 1,083 项，完整进度标记计数同为 1,083，二者一致。
- 全量命令：`.venv/Scripts/python.exe -m pytest -q -ra -p no:cacheprovider --basetemp work/core-dll-dedup-20261006/pytest-full-r2`。
- 跳过原因：65 项 Artifact Gate 未声明正式 Candidate（`UEBENCH_ARTIFACT_DIR` 未设置）；1 项目录符号链接测试缺少系统权限。跳过不算通过，没有声称正式 Candidate Artifact Gate 已通过。
- 1 个 warning 来自刻意构造 ZIP 重复成员的安全测试 fixture，不是本轮新增运行故障。
- 最终 `git diff --check` 通过；未新增其他组件裁剪、未改业务源文件。

首次门禁因历史 `%TEMP%/pytest-of-WANGWEI` 访问被拒绝产生 fixture ERROR；首次全量测试随之停止。
随后使用新的仓库 work 临时目录重跑；不修改断言，不清除旧临时目录。

上述为自动程序化验证，**不是人工可见页面验收**；没有实测真实 Windows 中文输入法、Win11、多 DPI/跨屏。
RS05 保持 `IN PROGRESS / RELEASE CANDIDATE`，不据此宣布整个正式发布完成。

## 5. 交付与恢复

- 打包配置已落实，后续正常构建不再生成四个重复副本。
- 本地验证 EXE：`work/core-dll-dedup-20261006/dist/UEBench/UEBench.exe`。
- 本地验证 ZIP 不含完整 Candidate 交付元数据/安装程序；**不是正式发布包**。
- 新包来自 dirty 工作区，未提交、未推送、未合并；正式 Candidate 应在干净 exact-head 提交构建，重新产生清单、hash、身份与 Artifact Gate 证据。
- 上一轮构建基线和原发布物完整保留；无需从回收站恢复。若需回退本轮变更，仅恢复原四项手工 binaries 配置并重建，不回退用户其他改动。

详细证据：`work/core-dll-dedup-20261006/verification.json`、`verification.log`、`self-check.json`、
`probe-offscreen.json`、`probe-windows.json`、`build.log`、`probe-build.log`、`full-suite-r2.log`。

## 6. 用户授权提交与 GitHub 重建

上述“未提交、未推送”是本地验证结束时状态。随后用户明确授权将本次变动提交 GitHub，供重新下载尝试。
提交范围为当前 `uebench.spec`、`tests/test_release_source.py` 与三份 2026-10-06 打包报告，
包含此前已完成的过量手工收集取消与本轮四个核心副本去重；不包含 PDF、翻译、虚拟键盘、OpenGL 的进一步裁剪。
沿用未合并 PR #13 的分支，不合并 main、不创建正式 Release、不提交实验 ZIP 或用户数据库。
新的 exact-head CI、Candidate 身份与可下载资产，以 GitHub 当前 PR / Actions 实际结果为准；
本地 dirty 验证包不能替代该新 Candidate。
