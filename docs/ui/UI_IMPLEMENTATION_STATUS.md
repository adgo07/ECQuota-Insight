# UI 实施状态与第二阶段交接

日期：2026-10-27。状态：**PR #33 第二轮用户反馈已作本地实现与一次最终完整回归；证据归档完成，等待设计会话独立复验，暂不推送。** 当前结论及未收口项见第 11 节；此前章节为历史证据。

## 1 分支、基线与平台 / Contract 预检查

| 项目 | 记录 |
|---|---|
| 仓库 | `https://github.com/adgo07/ECQuota-Insight.git`，实际工作树 `D:\project\能耗限额\ECQuota-Insight` |
| 分支 | `ui/phase1-qingzhou`，普通开发分支 |
| 开工源码 | `cdc89c12b0b7ea6791568838fbb382cb76842002`；实际 fetch 后与 `origin/main` 相同 |
| 当前实现提交 | **`afe001e4ba5a6f8e396acad88dd1ca353ff44deb`**（第二阶段）；第一阶段复验基线 `746d221cba9b31f6e6fe0d13d83311093c24f040`；本状态文件另作纯交接提交，最终 HEAD 用 `git log -1` 查询 |
| 中央 ACTIVE UI | `a389ac1de63c4f331f3b04e5e7b7a17ef02ed111`；已读 GUIDE_INDEX、产品家族规格、指南 v0.2、验收清单；另核当前 main 的 GUIDE_INDEX blob 相同 |
| Frozen lock | `platform-lock.json` 保持 `ee5feb0cc34dbd99790500fadd0c4c932e202a20` |
| 相关 Frozen | Architecture V2.1、Numeric Contract v1、Numeric Profiles v1、Numeric Conformance v1，均不变 |
| MUST / MUST NOT | Presentation 继续使用既有 Application；只对选煤开放；保留 Decimal 全值比较、历史请求/结果/规则快照、自动保存与选煤 Word；不改公式、系数、阈值、支持注册表、Schema、lock 或专业解释 |
| 公共语义 | 本任务不涉及中央公共 Contract 的语义修改，不需要中央 Contract 修改 |
| 差异与冲突 | 单页及自动保存为 ALLOWED PROJECT DIFFERENCE；D-ECQ-002～006 仍为 REGISTERED DEVIATION；未发现新增 CENTRAL CONTRACT GAP |
| Standard Issue | 无与本轮选煤 UI 直接相关的现行问题；水泥 ECQ-STD-GB16780-001、003 不变，不启动水泥接入 |
| 软件解释 | 保留 D01“未达3级”、D02；D02 提示补明“软件防误录校验”，不称为标准明文 |

原有未提交的任务书、设计 MD/HTML 和原始 LOGO 均保留并纳入实现提交，没有清理或覆盖设计正文。未接触旁边旧源码、安装版或用户真实数据库。未推送、创建 PR、合并、构建 Candidate 或发布。RS05 仍 IN PROGRESS，产品闭环仍 PARTIAL。

## 2 第一阶段结果与改动文件

- `src/uebench/ui/design_tokens.py`：本仓轻量视觉参数与公共 QSS，浅蓝侧栏、主次按钮、中文字体、表格与焦点状态。
- `src/uebench/ui/responsive_fields.py`：重排已有控件，宽窗两列、窄窗单列；保留控件对象、输入和信号，避免重建输入框。
- `src/uebench/ui/main_window.py`：命名页面映射；无侧栏首页、五项任务卡、独立设置、禁用导入/系数库；业务壳持续显示；真实最近六条记录及空/失败/重试反馈。
- 同一主窗口：标准固定五列、唯一标准状态筛选，包含历史目录；编号/名称点击与 Enter/双击进入同一独立详情；返回不重建列表，保留检索、筛选、选中和滚动；详情连续“基本信息、适用范围、标准要求”三分区，三态支持保护保持。
- 同一主窗口：选煤只读标准、企业类型单选（绑定原稳定值）、完整周期候选、自定义周期、联动工艺与只读 k；宽窄窗表单；就近错误及定位、防重复提交；正式服务计算和自动保存；共享 ReportView 结果、查看记录和 Word 连线；结果失效后取消旧导出关联；已保存但展示失败保留记录入口。
- `src/uebench/resources/branding/`、`icons/`：原始 PNG、七项同源 SVG 与来源登记。PNG 复制前后 SHA256 相同；图标原路径静态复制，运行时按浅色背景投影描边，不产生跨仓运行依赖。现有 PyInstaller 资源目录收集可涵盖这些文件，本轮未构建验证安装载荷。
- `tests/test_ui_phase1.py`：10 项样板行为检查；已有 `test_ui`、`test_ui_release_scope`、选煤 validation/lifecycle/reference、build identity、corrupted records、M3 performance 测试只按已批准结构/文案和命名导航更新，业务保护断言保留。
- `tools/capture_ui_phase1.py`：可复现的离屏截图及临时隔离数据原生交互预览；`.gitignore` 排除本地 `.venv-ui/`。
- `docs/ui/`：原有设计资产、十张真实 Qt 截图、截图环境清单、本唯一状态文件。

结果服务仍为现有正式服务，没有 Widget 内第二套算法。首页只读取有界最近六条保存记录；完整记录查询仍留第二阶段。修复了重构时发现的两处实际连线问题：记录刷新残留旧页索引；规则不兼容时新版工艺块没有隐藏。另保留多信号联动后的“数据已修改”状态，避免随后信号将其覆盖。

## 3 初次阶段测试命令、结果与限制（保留历史）

运行环境：Windows，本项目隔离环境 `.venv-ui`，当前可用 Python **3.12.14**、PySide6 **6.10.1**。项目正式支持要求 Python **3.13**，未降低 `pyproject.toml` 的要求或修改版本断言；其余依赖按项目声明范围安装，并非正式锁定 3.13 构建环境。

以下命令均在上述工作树执行，Python 前缀为 `& .\.venv-ui\Scripts\python.exe`。

| 检查 | 实际命令 / 结果 |
|---|---|
| 静态编译 | `-m compileall -q src tests tools`，通过 |
| 发布源码门禁 | `-m pytest tests/test_release_version_consistency.py tests/test_release_source.py tests/test_candidate_identity.py tests/test_build_info_provenance.py -ra --tb=short`，**164 passed** |
| 一次 literal full suite | `-m pytest -ra --tb=short`，迭代中执行，**1115 passed / 66 skipped / 16 failed / 1 warning**；不能写成完整回归通过 |
| 完整回归失败归因 | 10 项 UI 失效文案/结构及不兼容控件问题，已修复并在下列最终定向组复验；5 项子进程因仅 pytest 配置了源码路径而无法 import，设置 `PYTHONPATH` 后复验通过；1 项 `test_self_check::test_report_version_matches_package_and_pyproject` 要求 Python 3.13，本机仍为 3.12，保留环境限制 |
| 最终定向回归 | 下方完整命令，**253 passed**，含上述 10 项 UI 与 5 项子进程失败的复验 |
| 最终样板补验 | `-m pytest tests/test_ui_phase1.py -ra --tb=short`，**10 passed**（包括随后补充的历史目录筛选；与上组有重叠，不相加宣称总数） |
| 截图重现 | `tools/capture_ui_phase1.py`，成功，十图及环境清单；计算一次生成一条临时记录，结果 6.64 kW·h/t、2级 |
| Git 检查 | `git diff --check`、暂存区 `git diff --cached --check` 通过 |
| 远端 CI | 未推送，未触发本阶段 exact-head GitHub CI；不沿用旧 Candidate 的 CI 或安装证据 |

最终定向命令（先设置 `$env:PYTHONPATH=(Join-Path $PWD 'src')`，保证子进程同样能导入源码）：

```powershell
& .\.venv-ui\Scripts\python.exe -m pytest tests/test_ui_phase1.py tests/test_ui.py tests/test_ui_release_scope.py tests/test_gb29446_ui_validation.py tests/test_gb29446_record_lifecycle.py tests/test_gb29446_word_report.py tests/test_build_identity.py tests/test_corrupted_records.py tests/test_rs05_m3_performance_cleanup.py tests/test_gb29446_reference_slice.py tests/test_gb29446_rule_compatibility.py tests/test_evaluation_scope_enforcement.py::test_refusal_happens_in_a_process_that_never_loaded_qt tests/test_gb29446_excel_adapter.py::test_excel_record_lifecycle_survives_restart tests/test_retired_batch_writers.py -ra --tb=short
```

本地日志位于 `D:\project\能耗限额\ECQuota-Insight\work\`：`phase1-source-gate.log`、`phase1-full-suite.log`、`phase1-final-targeted.log`、`phase1-sample-final.log`、`phase1-capture.log`。日志不入库。首次 full suite 的跳过项包括未提供 Candidate、旧归档不可用及符号链接环境；warning 为既有重复 ZIP 成员测试。修复后未再次执行全部套件，不把定向复验推断成最终完整回归通过。

## 4 截图与隔离启动

**均为真实 PySide6 控件的 offscreen 截图**，devicePixelRatio=1.0，尺寸为窗口逻辑像素。由随软件配套的签名标准包建立临时隔离数据库；输入来自批准映射示例，仅用于截图，不写入生产 UI 默认值。临时数据在关闭后删除，未使用用户数据库。它们只用于布局讨论，不是原生 Windows DPI、输入法或安装版验收。

| 页面 | 绝对路径 |
|---|---|
| 首页空状态 | `D:\project\能耗限额\ECQuota-Insight\docs\ui\screenshots\phase1\home-1440.png` |
| 首页真实保存记录 | `D:\project\能耗限额\ECQuota-Insight\docs\ui\screenshots\phase1\home-record-1180.png` |
| 标准列表 | `D:\project\能耗限额\ECQuota-Insight\docs\ui\screenshots\phase1\standards-1440.png` |
| 选煤详情 | `D:\project\能耗限额\ECQuota-Insight\docs\ui\screenshots\phase1\detail-coal-1440.png` |
| 水泥详情 | `D:\project\能耗限额\ECQuota-Insight\docs\ui\screenshots\phase1\detail-cement-1440.png` |
| 未确认标准详情 | `D:\project\能耗限额\ECQuota-Insight\docs\ui\screenshots\phase1\detail-other-1440.png` |
| 选煤录入宽窗 | `D:\project\能耗限额\ECQuota-Insight\docs\ui\screenshots\phase1\form-1440.png` |
| 选煤结果宽窗 | `D:\project\能耗限额\ECQuota-Insight\docs\ui\screenshots\phase1\result-1440.png` |
| 选煤录入窄窗 | `D:\project\能耗限额\ECQuota-Insight\docs\ui\screenshots\phase1\form-1180.png` |
| 选煤结果窄窗 | `D:\project\能耗限额\ECQuota-Insight\docs\ui\screenshots\phase1\result-1180.png` |

详细环境：同目录 `capture-environment.json`。原生临时隔离窗口的可复现启动方式（关闭即退出并清理临时数据）：

```powershell
Set-Location -LiteralPath 'D:\project\能耗限额\ECQuota-Insight'
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
& .\.venv-ui\Scripts\python.exe tools/capture_ui_phase1.py --interactive
```

自动重现离屏截图：`& .\.venv-ui\Scripts\python.exe tools/capture_ui_phase1.py`。工具使用临时数据；默认输出本阶段截图目录，可用 `--output work/review-captures` 将复验截图放在忽略目录。

## 5 检查点与剩余工作

本轮到此停止，等待原设计会话检查第一阶段样板及提出具体返修，不自动开始第二阶段，不替代设计会话最终验收。

- 第二阶段：记录全库搜索/count/稳定分页、独立只读两页签详情、移除普通 UI 重新评价入口、设置及剩余异常/上下文适配。当前记录列表和详情仍沿用旧能力，不能据此宣称 A-10/A-11 已全部完成。
- 环境：正式 Python 3.13 下的最终完整回归与 exact-head CI 尚未执行；没有构建本阶段安装版或 Candidate。
- 原生 Windows 125%/150% DPI、跨屏、真实中文输入法预编辑与原生下拉弹层未实测；离屏图与 QTest 点击不替代这些证据。
- 长标准详情标题支持换行，宽表在自身区域横滚；1180×760 时表单为单列并滚动访问底部动作，未缩小字体强塞。

原设计会话可直接读取本文件、实现提交与截图，无需主动回传消息。后续在同一开发分支继续。

## 6 第一阶段首轮设计返修（历史交接）

返修输入：原设计会话对 `cb43242` 的独立检查及五项具体意见。当前实现提交为 **`379bd9066b8cde34c12101c9fd936fec85628592`**。仍在 `ui/phase1-qingzhou`；本轮没有改动 Application / Domain、数据定义、数据库 Schema、支持注册表或 lock，没有启动第二阶段。

| 返修项 | 实际处理与证据 |
|---|---|
| 保存后的主要动作 | 保存成功或已保存但展示失败后，“查看对标记录”为结果区唯一主要动作；原计算按钮变为次操作“重新计算并生成新记录”。修改输入后恢复主要操作“计算并判级”，清空当前记录关联并禁用旧查看/导出；保留“重新计算将生成新记录”。`finally` 改为按当前真实状态同步操作，不再无条件恢复初始状态 |
| 单一正式标准摘要 | 完整标准编号/名称紧靠页标题显示为可选择复制的只读文本；旧 combo 隐藏为兼容模型，不再展示禁用下拉箭头。摘要来自当前实际标准；无可用标准时显示真实缺失状态，原注册表、日期、官方来源与就绪保护不变 |
| 首页任务卡与最近对标 | 新增本仓轻量 `task_card.py`，标题和说明独立布局，重点卡使用原几何图标的白色描边；键盘点击、禁用及中文无障碍名称仍保留。无记录时隐藏空网格，以紧凑空状态和“新建对标”按钮呈现；有记录时显示真实最近六条，表高随行数变化，操作列固定为紧凑宽度。失败提示独立于空状态，保留重试 |
| 表单与结果层级 | 企业类型单选靠左相邻成组；k 保留原只读字段和信号，但改为紧凑无边框数值展示，完整来源仍可见。结果保留一个主要白色面板、两项核心值及完整计算/判级依据，移除嵌套卡片背景边框与重复标题。统计范围和窄窗滚动访问保持 |
| 小限额表与依据 | 标准详情阈值表单独关闭末列拉伸，六列均衡分配、表高按实际行数；“标准要求”补显现有可信定义中第3.1条表1、第3.2条表2的等级依据，继续复用已有依据展示函数。未支持标准不展示旧限值或伪造依据 |

新增有意义的状态转换验证分别覆盖正常展示与展示失败两条路径：一次计算只调用一次正式服务、生成一条记录；点击查看只打开保存记录，不再次计算；修改输入使旧关联失效；再次主动计算才生成第二条新记录。另检查空/失败状态分离、隐藏选择器后的真实标准摘要及支持/未支持详情的依据保护。

本轮测试均使用项目 `.venv-ui`，Python 3.12.14 / PySide6 6.10.1。工作目录仍为本仓根；先设 `$env:PYTHONPATH=(Join-Path $PWD 'src')`。使用工作区独立 `--basetemp` 和 `-p no:cacheprovider`，避免系统临时目录/cache 权限影响。

```powershell
& .\.venv-ui\Scripts\python.exe -m pytest tests/test_ui_phase1.py tests/test_gb29446_ui_validation.py tests/test_gb29446_record_lifecycle.py tests/test_ui_release_scope.py tests/test_ui.py tests/test_gb29446_reference_slice.py tests/test_gb29446_rule_compatibility.py tests/test_gb29446_word_report.py -ra --tb=short -p no:cacheprovider --basetemp work/revision1-affected-tests
# 196 passed in 84.66s

& .\.venv-ui\Scripts\python.exe -m pytest tests/test_ui_phase1.py tests/test_build_identity.py tests/test_rs05_m3_performance_cleanup.py -ra --tb=short -p no:cacheprovider --basetemp work/revision1-final-checks
# 48 passed in 6.97s；与上组重叠，不相加宣称总数

& .\.venv-ui\Scripts\python.exe tools/capture_ui_phase1.py
& .\.venv-ui\Scripts\python.exe -m compileall -q src tests tools
git diff --check
# 截图重现、编译与补丁格式检查均通过
```

日志在 `D:\project\能耗限额\ECQuota-Insight\work\revision1-affected.log`、`revision1-final.log`、`revision1-capture.log`。没有重复运行无关整库测试，没有改动正式 Python 3.13 版本断言。

第 4 节同名十张截图已由最终返修代码重新生成；七张有内容变化，首页空/有记录、宽窄窗表单/结果、选煤详情均已查看核对。仍是 **offscreen、devicePixelRatio=1.0、隔离临时数据**，环境清单及绝对路径同第 4 节。示例计算仍一次保存、6.64 kW·h/t、2级。任务卡曾在中间截图暴露通用按钮样式压缩高度，已调整任务卡角色高度并重现，当前交付截图不含该中间错误。

本轮等待原设计会话复验；不推送、不建 PR、不进入记录/设置重构。Python 3.13 完整回归、exact-head CI、原生 125%/150% DPI、跨屏、真实输入法与原生弹层仍未验证，不能由本次定向测试和离屏图推断通过。最小窗口仍为 1180×760，更窄有效空间及原生缩放兼容按后续阶段实际检查。


## 7 第二阶段当前交接（2026-10-27）

### 7.1 授权顺序及范围

原设计会话已独立通过第一阶段并授权实施第二阶段。最新顺序为：第二阶段完成 → 原设计会话独立检查和必要返修 → 原设计会话明确允许后推送 GitHub、创建一个 PR → 用户独立最终验收。本次停在第二步之前，不推送、不建 PR、不合并、不构建或发布 Candidate。此文是唯一实施状态文件，未回写已批准设计 MD/HTML。

实现提交为 `afe001e4ba5a6f8e396acad88dd1ca353ff44deb`，分支 `ui/phase1-qingzhou`。正式评价范围、D01/D02、自动保存、历史快照、选煤 Word 保留；未修改公式、系数、阈值、支持注册表、Schema、迁移或 platform-lock.json。

### 7.2 已完成行为与查询边界

- 记录页七列：企业名称、统计期、标准、核心结果、结果状态、评价时间、操作；全库搜索、状态筛选、真实总数与分页，刷新/重试、查看、默认取消的删除确认。搜索输入框保留，200 ms 延迟提交；筛选切换重置页码，末页删除自动回退，刷新/返回保留可用选中和滚动位置。
- `application/record_query.py` 定义小型只读分页投影；`infrastructure/repositories.py::query_page` 在同一 SQLite 读事务内做计数和取页，按时间及记录 ID 双重稳定降序排列。每页 20 条，服务边界最多 100 条；全库条件查询不再受最近 200 条限制。文字查询转义 `%`、`_`，条件绑定参数。状态筛选按保存结果生成，不调用当前规则或计算器。
- 计数/筛选可能线性扫描保存的请求和结果，时间 O(N)，不是索引级检索承诺。SQLite UDF 一次处理一行，返回小摘要；列表返回页大小有界，内存为单行载荷加当前页，未批量加载全部历史对象。列表不读取 `rule_snapshot_json`；请求/结果损坏标为“记录损坏”，打开详情时再校验全部三类快照并隔离失败。没有另建镜像表、索引或迁移。
- 统计期只读保存请求中的已知周期信息，旧记录缺失显示“未记录”。多指标旧记录显示“分项结果”和首项标识，不合成总等级。`未达3级`、无法判定及损坏态明确区分。
- `ui/record_detail.py` 为独立只读页面，严格两页签“基本信息与结果”“输入数据与计算依据”；由记录 ID 直接打开，首页入口也能打开超过 200 条的旧记录。复用保存快照和已有 ReportView，展示核心值、单位、上下标、限值与依据；不重新评价，不展示原始 JSON/技术指纹。旧记录兼容提示及数据不完整提示保留。
- Word 按实际已有导出能力启用，不能导出时显示真实原因；导出对应当前记录 ID，不新增评价。标准来源无已注册入口时禁用并解释原因，不伪造链接。
- 设置页白色分组、可复制路径、可滚动布局，“高级”默认折叠；备份和恢复继续原保护逻辑，恢复确认默认取消。导入和系数库仍可见禁用。
- 首页任务卡随宽度重排并可滚动；原生启动尺寸按当前屏幕可用工作区限制。通常最小尺寸 900×600，可用工作区更小时按屏幕收缩；1440×900 与 900×600 补充截图见下。修复独立详情/设置页面背景重绘导致透出首页的问题。

主要文件：`application/facade.py`、`services.py`、`record_query.py`；`infrastructure/repositories.py`；`ui/main_window.py`、`record_detail.py`、`settings_page.py`、`task_card.py`；`tools/capture_ui_phase2.py`；新增 `tests/test_record_query_ui.py`。既有 UI/lifecycle/corrupted/performance 测试按新页面和分页结构调整，业务保护断言保留。

### 7.3 最终代码测试证据

工作目录 `D:\project\能耗限额\ECQuota-Insight`，Python **3.13.17** / PySide6 **6.10.1**，依赖按 `requirements.lock` 安装，项目以 editable 安装；未降低 Python 版本要求。运行时、虚拟环境位于忽略的 `work/python-runtimes`、`work/venv313`。

环境安装工具曾额外生成用户级 `python3.13.exe` 启动入口及 Astral 的 CPython3.13.17 注册项。交接前检查二者确实指向本项目 `work/python-runtimes`，已精确移除该入口和该版本注册项；空 Astral 父键一并清理。复核任务入口/版本注册项均不存在、原有 PythonCore/3.11 保留，项目隔离 Python 仍可运行。未修改系统显示设置、PATH 或原有 Python 安装。后续若重装，应明确使用 uv 的 `--no-bin --no-registry`。

以下是最终实际命令（PowerShell）：

```powershell
& .\work\venv313\Scripts\python.exe -m pytest -ra --tb=short -p no:cacheprovider --basetemp work/phase2-final-full
# 1142 passed, 66 skipped, 2 warnings in 357.43s

& .\work\venv313\Scripts\python.exe -m pytest tests/test_release_version_consistency.py tests/test_release_source.py tests/test_candidate_identity.py tests/test_build_info_provenance.py -ra --tb=short -p no:cacheprovider --basetemp work/phase2-source-gate
# 167 passed

& .\work\venv313\Scripts\python.exe tools/qzc_n01_a_excel_ingress_probe.py
# 20 checks, 0 failed

& .\work\venv313\Scripts\python.exe -m compileall -q src tests tools
git diff --check
# 通过
```

新增五项分页/历史 UI 测试覆盖 225 条记录、超过 200 条的最早记录、字面通配符、统计期搜索、真实筛选计数、同时间稳定顺序、末页回退、损坏与失败重试、列表不读取规则快照、严格两页签、按 ID 直达、旧快照不变、禁用当前规则/计算器后仍可查看和 Word 导出、数据不完整的真实不可导出原因。最终完整回归已包含这些测试，以及既有数值与架构保护。

66 项跳过包括未提供 Candidate 安装产物、旧归档不可用及符号链接环境；两个 warning 为既有重复 ZIP 成员安全样例和 Windows junction 安全样例子进程输出线程的解码警告，未隐藏或改成通过。完整回归 0 失败，不能据此认定跳过的安装产物检查通过。未推送，远端本提交 CI 尚未运行。

本地忽略日志目录 `D:\project\能耗限额\ECQuota-Insight\work`：`phase2-final-full.log`、`phase2-source-gate.log`、`phase2-ingress-probe.log`、`phase2-word-query-final.log`（28 passed，与全量重叠）、`phase2-capture-final.log`。第 3、6 节 Python 3.12 环境限制为历史事实，当前已补齐正式 Python 3.13 本地完整回归。

### 7.4 截图与原生检查

截图根目录绝对路径：`D:\project\能耗限额\ECQuota-Insight\docs\ui\screenshots\phase2`。

| 场景 | 根目录内文件 |
|---|---|
| 宽窗记录 / 末页 | `records-1440.png`、`records-last-page-1440.png` |
| 只读详情两页签 | `record-result-1440.png`、`record-inputs-1440.png` |
| 设置默认 / 高级展开 | `settings-1440.png`、`settings-advanced-1440.png` |
| 900×600 补充 | `records-900.png`、`record-900.png`、`settings-900.png`、`home-900.png` |
| 原生 Windows 150% | `native150/home.jpg`、`records.jpg`、`records-search.jpg`、`record-result.jpg`、`record-inputs.jpg`、`settings.jpg`、`settings-advanced.jpg`、`form.jpg`、`form-bottom.jpg`（均在 native150 子目录） |
| 环境与限制 | `capture-environment.json`、`native-environment.json`、`native150/observation.json` |

离屏图由真实 Qt 控件、225 条临时隔离保存快照生成；1440×900 与 900×600，DPR 1.0，不作为原生 DPI 通过证据。最终图已检查。

另用 Computer Use 在原生 Windows 窗口检查并保存证据：系统实际 DPI **144 / 150%**、QScreen DPR 1.5，逻辑屏幕 1280×720、可用工作区 1280×672，实际客户区 **1256×624**，没有 QT 缩放环境覆盖。已操作首页/业务切换、225 条记录中文“最早”搜索返回一条、独立详情两页签、设置高级折叠展开、表单长名称/单位/焦点与底部计算按钮滚动可达。截图可能经过工具逻辑像素缩放，非像素比对或完整 DPI 验收。

明确限制：中文输入通过工具 Unicode 注入，真实输入法预编辑未测；125%、跨屏、安装版未测；工艺下拉打开后工具报告 `no monitor found` / owned popup 目标不匹配，已安全关闭，不宣称下拉视觉或选项提交通过。原生未执行计算、Word 或恢复；其行为由上述自动测试覆盖。`native_dpi_acceptance` 继续明确为 false。

隔离预览（225 条测试记录，临时数据随关闭清理，不连接用户数据库）：

```powershell
& .\work\venv313\Scripts\python.exe tools/capture_ui_phase2.py --interactive
# 原生窗口；不要设置 QT_QPA_PLATFORM=offscreen 或缩放覆盖

& .\work\venv313\Scripts\python.exe tools/capture_ui_phase2.py
# 离屏重现截图，会更新 phase2 同名证据；可用 --output work/phase2-local-preview 改为本地输出
```

### 7.5 交接结论

第二阶段本地实现及已列明测试完成，等待原设计会话独立检查；不等同于用户最终验收。下一步先审查、返修，再由原设计会话明确授权推送和一个 PR。当前无 PR、未合并、未发布，产品路线状态不在本次擅自升级。


## 8 设计会话独立复核与 PR 交付（2026-10-27）

原设计会话对 **`029945151368c22fc7a2aa4624d2103ef6058f20`** 独立检查通过，明确允许依据用户授权推送当前开发分支，并创建一个以 main 为目标、覆盖完整两阶段 UI 工作的中文草稿 PR。本结论是设计/代码复核，**不代替用户独立最终验收**。本节仅更新交付记录，未改生产代码。

设计会话实际检查：分页投影及仓储 SQL、独立只读两页签、按 ID 打开与 Word 连线、设置及窗口适配；确认无公式、数值语义、Schema 和支持范围改变。检查 225 条全库计数、超过 200 条可达、稳定排序、通配符、损坏行、末页删除及上下文保护，以及禁用计算器/当前规则后历史查看与导出的测试。另检查宽窄真实 Qt、原生 150% 截图与环境说明，保留原生下拉、真实输入法预编辑、125%/跨屏和安装产物未验证限制。查询 O(N) 及单行载荷加页大小内存边界继续如实保留。

设计会话独立执行命令（本仓根目录）：

```powershell
& .\work\venv313\Scripts\python.exe -m pytest tests/test_record_query_ui.py tests/test_gb29446_word_report.py tests/test_ui_phase1.py -ra --tb=short -p no:cacheprovider --basetemp D:/project/能耗限额/.ui-design-work/review-phase2-1657
# 32 passed in 8.23s，退出 0
```

证据区分：设计会话读取了第 7 节完整回归日志（1142 passed / 66 skipped / 2 warnings），但没有重复执行全套；源码门禁 167 项及入口探针 20 项也是实施会话执行证据，不标为设计会话重跑。

交付前实际核对：origin 为 `https://github.com/adgo07/ECQuota-Insight.git`，分支 `ui/phase1-qingzhou`，工作区干净；fetch 后 `origin/main` 仍为 **`cdc89c12b0b7ea6791568838fbb382cb76842002`**，即本轮开工基线，无新增 main 变更需协调。提交本交付文档后，仅正常推送当前开发分支，不强推、不改 main。PR URL、最终精确 head 与该 head 的 CI 结果以本执行会话交付报告及所挂 PR 为准，避免为了回写动态 CI 状态反复改变已验提交。

平台 / Contract 预检查复用第 1 节真实基线：Frozen lock `ee5feb0cc34dbd99790500fadd0c4c932e202a20`，ACTIVE UI 检查基线 `a389ac1de63c4f331f3b04e5e7b7a17ef02ed111`；本次仅文档和 PR 交付，不升级 lock、不改公共语义、软件解释或标准支持状态。现有 PR Gate、Numeric v1 与 N01-A 适用 CI 由 PR 自然触发，未要求发布或 Candidate workflow。等待原设计会话核实 PR/CI 后交用户验收；不合并、不发布、不覆盖安装产品或用户数据。


## 9 PR #33 独立验收后的本地返修（2026-10-27）

输入为用户两份独立验收意见，以及设计会话在 `ced969a3d50581f95320bcd61ddbbad6f7f74d88` 的代码与真实 QTest 点击复现确认。沿用现有分支和唯一状态文件，不回写“用户验收通过”。按设计会话确认范围处理六项，暂不推送、更新 PR 或构建可试用包；先交设计会话复验。

**平台 / Contract 预检查：** 本地确认 origin 为 `https://github.com/adgo07/ECQuota-Insight.git`，分支 `ui/phase1-qingzhou`，开工 HEAD `ced969a3d50581f95320bcd61ddbbad6f7f74d88`，工作区干净；fetch 后 main 仍为 `cdc89c12b0b7ea6791568838fbb382cb76842002`。重读现行中央 GUIDE_INDEX 及路由的家族规格、指南 v0.2、验收清单，文件 blob 分别为 `658b3df9569e2956ff7b9060dab0d1bd0fa2bd58`、`0efede55f8b2e7856df778a61f0308fa621226b7`、`532c0edd2ee2349620c77472f8e9227440b29722`、`71c4712a0bdb6ba3bd4153f99eccd031c8dbf134`。Frozen lock 仍为 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`；Architecture 2.1、Numeric Contract/Profile/Conformance v1 不变。MUST 保留 Decimal 全值判定、历史快照和正式选煤范围；MUST NOT 修改 Calculator、数值、批准映射、Schema、支持状态及软件解释。无新增公共 Contract 冲突或相关 Standard Issue，不需中央修改，本任务不涉及中央公共 Contract。

最终实现提交 **`93c46e8cfbc4a62ca07bb3b7e2bf791c74703834`**，前置修复提交 `27c81549f25f5f5e55803d9cbcedbda53b6b2f9d`；后续仅本节与截图证据。改动如下：

| 验收项 | 修复与保护 |
|---|---|
| 保存状态 | `record_query.py` 移除把 INCOMPLETE/NOT_APPLICABLE 改为无法判定的覆盖，沿用既有“不完整”“不适用”；筛选补齐，两种保存状态的列表、计数、筛选和详情一致。空结果仍无法判定，多分项策略不变 |
| 结果定位 | 正常成功后排队按结果标题定位滚动条，使标题与首屏核心值可见；不对整个高结果块做 ensureWidgetVisible。1440×900 / 900×600 验证一次成功只保存一条，失败仍定位输入错误，修改输入仍失效旧结果。保留成功弹窗 |
| 侧栏返回 | 补 itemClicked 处理仅在当前页面不是目标父列表时导航，保留 currentRowChanged 键盘逻辑。真实 QTest.mouseClick 覆盖记录/标准详情重复点击、上下文、普通切页单次导航及禁用项 |
| 企业名标题 | RecordDetailPage.title 明确 PlainText，`A<b>x</b>B & 特殊企业` 原样显示；保存快照逐字节模型序列化前后相同，禁止计算器和当前规则读取后仍可查询与查看 |
| 表格宽度/行高 | 新轻量 `ui/record_table.py` 对企业、标准列弹性分配，操作列至少 88；1440 无横滚，900 保留横滚。长中文按实际列宽测量完整文字高度，行高随内容增长，避免默认 Qt 末行省略；真实图和尺寸断言复核 |
| 证据格式 | native150 九张既有 JPEG 仅改名 .jpg，无重编码，SHA256 不变。原生环境清单 `docs/ui/screenshots/phase2/native-environment.json` 已登记九张的真实路径、JPEG 格式、既有尺寸及哈希，observation 同步；保留历史采集环境，不冒充返修图 |

维护性清理仅去掉两处与 GRADE_LABELS 重复的 NOT_QUALIFIED 赋值（冗余赋值，不称不可达代码），用命名 grade_basis 替代历史详情 basic[:5]/basic[7:]，标准详情标题在创建时持有明确引用。未开展第二标准扩展、高级区美化或成功弹窗策略调整。未接触用户数据库、已安装产品或 `UI测试版_ced969a3` 数据。

**测试与日志：** Python 3.13.17 / PySide6 6.10.1，仍使用本项目 `work/venv313`。相关定向组 78 passed（`work/pr33-rework-affected.log`）；长文本高度最终修正后记录查询与第一阶段 UI 23 passed（`work/pr33-rework-final-targeted.log`）；源码门禁 168 passed（`work/pr33-rework-source.log`，此前 167 随新增 UI 模块增加一项源码检查）；编译和 diff 格式检查通过。以上组有重叠，不相加。

最终完整回归命令：

```powershell
& .\work\venv313\Scripts\python.exe -m pytest -ra --tb=short -p no:cacheprovider --basetemp work/pr33-rework-final-full
# 1149 passed, 66 skipped, 2 warnings in 303.66s (0:05:03)
```

最终完整回归 0 失败；66 项跳过仍含未提供 Candidate、旧归档及符号链接环境，两个 warning 仍为重复 ZIP 成员样例与 Windows junction 样例输出线程解码警告，未隐藏。日志 `work/pr33-rework-final-full.log`。前一完整运行 `work/pr33-rework-full.log` 在长文本截图暴露 Qt 默认行高仍省略末行后主动中止，未列为通过；补修、定向复验后才执行上述最终一次完整回归。新增六个有效测试实例覆盖两种保存异常状态、真实侧栏点击、表格宽窄/长文本及两尺寸结果定位；不删保护断言、不改版本要求。当前未推送，旧 head 三项远端 CI 通过不作为本返修提交 CI 证据；复验授权后更新同一 PR 才触发现有 PR Gate/Numeric v1/N01-A，仍不触发发布或 Candidate。

**返修截图：** 绝对目录 `D:\project\能耗限额\ECQuota-Insight\docs\ui\screenshots\pr33-rework`，均为真实 Qt offscreen / DPR 1.0 / Python 3.13.17 的隔离数据。`capture-environment.json` 标记源码精确 head `93c46e8cfbc4a62ca07bb3b7e2bf791c74703834`；source_dirty=true 如实保留，待提交为状态文档与图片证据，源码/测试/工具与该提交一致。225 初始示例，加两次独立成功计算及两种异常保存示例，最终 229 条，不是用户数据。

- `success-result-1440.png`、`success-result-900.png`：成功后实际滚动位置，标题/单耗/等级可见。
- `records-1440.png`、`records-900.png`：参考宽窗直接使用操作列、窄窗表内横滚；`records-long-names-1440.png` 专用长名称隔离样例，完整换行和增高行可见，fixture 说明登记在清单。
- `incomplete-list-1440.png`、`incomplete-detail-1440.png`、`not-applicable-list-1440.png`、`not-applicable-detail-1440.png`：状态区分、详情一致及带尖括号/&的原文标题。另保留同工具生成的详情/设置等补充图，均有清单。

这些是新返修版布局证据，已目视检查代表图；`phase2/native150/*.jpg` 是旧交付历史原生图，不是本轮修复后证据。真实输入法预编辑、原生下拉弹层、125%/跨屏及安装版仍未验证，本轮未重做原生 150% 检查，不由离屏图推断通过。PR 当前链接固定旧 head，因此仍保留其原有有效 .png 路径；待复验后推送时同步换为新 head 的 .jpg 和返修截图链接，避免当前生成不存在的远端链接。

本轮等待设计会话独立复验；未推送、未合并、未发布，尚非用户最终验收通过。


## 10 返修独立复验与交付授权（2026-10-27）

设计会话在精确 HEAD `189f31a73078d4eb7cf18e3511f32d4304fd663c` 独立复验通过：逐项审查生产 diff、导航双信号去重、结果定位、状态/纯文本和 RecordTable；查看宽窗长文本、900 成功结果、不适用详情真实 Qt 图；逐字节验证九张 JPEG 与 ced969a3 原图及清单哈希相同。独立运行 Python 3.13 的 `tests/test_record_query_ui.py tests/test_ui_phase1.py tests/test_gb29446_word_report.py -ra --tb=short -p no:cacheprovider --basetemp D:/project/能耗限额/.ui-design-work/pr33-review-fixed-0347`，38 项全通过（9+14+15）。设计会话读取实施会话最终日志确认 1149 passed / 66 skipped / 2 warnings / 0 failed，未把该全套记为其重复执行。原生及安装环境限制保留，不改变业务语义或支持范围。

依据用户授权，允许正常推送原分支、更新同一草稿 PR #33、核对新精确 head 的三项适用 CI，并在 `D:\project\能耗限额\UI测试版_<最终SHA前8位>` 制作本地便携 UI 试用包。保留旧包及其数据库；新包仅通过隔离数据目录与 TEMP/TMP 的 cmd 启动，空白用户测试数据，自检另用隔离目录。沿用 tracked spec 和合法构建身份工具，不制作安装器、不声明完整 Candidate 验收、不合并发布。包、ZIP/清单/自检和本提交 CI 的动态交付证据在会话最终报告及 PR 中记录，不为回填构建后信息再次改变构建源码 SHA。平台预检查沿用第 9 节，本次仅文档提交与授权交付。


## 11 第二轮用户实测反馈与紧凑列表返修（2026-10-27）

**当前边界：** 实现提交 `142524169fa0e53dc8844f28de73652f2e06575c`；本节及截图另作证据提交，生产代码/测试/工具未再修改。暂不推送、不更新 PR、不构建下一便携测试包、不合并发布；等待设计会话独立复验。用户最新允许适度缩小两张列表文字及留白，优先默认窗口全列可见和普通行单行；不全局缩小字号，不强求任意长名称单行。

**平台 / Contract 预检查：** 本轮确认本仓 origin 为 `https://github.com/adgo07/ECQuota-Insight.git`，原分支 `ui/phase1-qingzhou`，开工 HEAD `e70da765a63047a413a6076197cc1e8d4df507d2`，工作区干净；fetch 后 main 仍 `cdc89c12b0b7ea6791568838fbb382cb76842002`。重读当前中央 GUIDE_INDEX、家族规格、UI 指南 v0.2、清单，四文件 blob 与第 9 节一致；Frozen lock 仍 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`。Architecture 2.1、Numeric Contract/Profile/Conformance v1 不变；MUST 保留 Decimal 全值判定、保存快照、D01/D02 与仅选煤正式范围，MUST NOT 改 Calculator、映射、数值、Schema、支持状态或软件解释。无新增相关 Standard Issue、公共 Contract 冲突或中央修改需要；本任务不涉及中央公共 Contract。

先实际查看用户三张截图：标准库右侧截断、炼焦煤选中圆点消失、设置标题压在边框上。实现与验证如下：

| 项目 | 本地处理及实际边界 |
|---|---|
| 默认窗口列表 | 标准五列及记录七列均按 viewport 响应分配。仅这两张表正文/表头采用 13px、较紧单元格/按钮留白，其他页面仍 14px。1180、1256、1440 的正常记录日期、标准、统计期和状态尽量完整单行，全部列/操作可见；900 保留自身横滚，不藏列或强制移出屏幕。长名称按需换行增高，工具提示保留原文 |
| 原文打开 | 只从已登记官方 https 注册表取地址；捕获 openUrl false/异常。请求后弹窗明确“无法确认浏览器是否已显示网页”，地址只读可复制，始终有“复制官方地址”。不改默认浏览器或权限，不访问本地 PDF，不虚称网页已打开 |
| 冻结浏览器环境 | 仅 frozen Windows 的外部打开调用期间临时清除 DLL 搜索覆盖、过滤本 bundle 的 PATH 段，finally 精确恢复原值。依据 [PyInstaller 6.20 官方说明](https://pyinstaller.org/en/v6.20.0/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application)，属于最小可逆处理，不认定它已证明用户权限弹窗的根因 |
| 录入滚轮 | 工艺与统计期采用 WheelSafeComboBox。收起时真实 QWheelEvent 转交所在页面滚动，聚焦/未聚焦均不改选项、k 或旧结果；弹层选择与键盘保留。未扩展无关筛选控件 |
| 设置卡片 | 移除标题画在边线上的 QGroupBox，改为卡片内独立标题与内容布局；长路径可选中复制并换行，高级展开仍可滚动。备份/恢复及诊断信号和保护不变 |
| 单选标记 | 明确提供选中/未选中/禁用 SVG 指示器、焦点边框；文字点击及键盘正确互斥并同步真实煤种。离屏像素检查与原生截图均看见圆环/圆点；原生实测炼焦煤→动力煤→炼焦煤 |

**仍需设计复验的长文本细节：** `records-long-1256.png` 中特别长的企业名已多行增高，但末行仍出现省略号；完整原文保留在工具提示，状态/日期/操作完整。1180 同类样例未出现该末行省略。本轮不宣称任意长度名称均完整无省略；这个细节作为未收口项明确交设计会话，未在证据收尾阶段改动已跑全量的实现。

**测试：** Python 3.13.17 / PySide6 6.10.1。本轮相关组 78 passed（`work/pr33-r2-affected.log`，紧凑字号最终调整之前）；最终紧凑表格与记录组 22 passed（`work/pr33-r2-compact2.log`）。新增第二轮 13 个测试实例，含四种窗口尺寸、普通行单行度量、上下文保留、聚焦/未聚焦真实滚轮和页面滚动、键盘/弹层鼠标选择、卡片标题位置、官方请求 true/false/异常及复制、单选真实点击/键盘与蓝色像素、冻结 DLL/PATH 正常及异常时恢复。各组重叠不相加。

最终一次 Python 3.13 完整回归在上述实现提交后执行，后续仅等待原 session 结束并读取日志，没有重跑：

```powershell
& .\work\venv313\Scripts\python.exe -m pytest -ra --tb=short -p no:cacheprovider --basetemp work/pr33-r2-final-full
# 1165 passed, 66 skipped, 2 warnings in 342.36s (0:05:42)，退出0
```

日志 `D:\project\能耗限额\ECQuota-Insight\work\pr33-r2-final-full.log`。66 跳过仍包含未提供 Candidate 产物、旧归档不可用及符号链接环境；两个 warning 为 junction 样例输出线程解码警告与重复 ZIP 成员样例，未抑制。完整回归含源码门禁和既有业务保护；未修改相关三项 CI workflow，不手动触发 Candidate/发布。未推送，因此旧 head CI 不作为 `1425241` 的 CI 通过证据。

**实际窗口与截图：** 根目录 `D:\project\能耗限额\ECQuota-Insight\docs\ui\screenshots\pr33-round2`。离屏清单 `capture-environment.json` 记录干净源码精确 head `142524169fa0e53dc8844f28de73652f2e06575c`、DPR1.0、1256×624 / 1180×760 / 1440×900 / 900×600。标准库来自真实随包48项，记录来自225条临时保存样例，长名称另外保存一条，非用户数据库。代表图：`standards-1256.png`、`standards-1180.png`、`records-1256.png`、`records-1180.png`、`records-long-1256.png`、`records-long-1180.png`、三张 `radio-*-1256.png`、`settings-1256.png` 和 `settings-advanced-1256.png`。

原生 `native150/` 十张 JPEG 及 `observation.json`：实际 GetDpiForWindow=144、QScreen DPR1.5，逻辑屏幕1280×720/可用1280×672，默认客户区 **1256×624**，无 Qt 缩放环境覆盖。已检查紧凑标准/记录全列、普通记录单行、三次煤种切换圆点、聚焦工艺滚轮保持跳汰/k1.26而页面滚动、键盘Down有效、设置与高级标题。原生图在提交前 e70da765 的脏工作树采集，对应本轮随后提交1425241的实现；表格图已由最终13px紧凑版覆盖，其余单选/设置/滚轮组件后续未改。归档清单记录图像格式/尺寸/SHA256和源文件归档哈希，不冒充从干净1425241重新启动采集。Computer Use图像可能被工具按逻辑像素缩放，不作像素比对或完整DPI验收。本人创建的业务测试窗口已关闭。

**真实冻结 EXE 原文链路及停止限制：** 默认 https 关联只读检查为 `MSEdgeHTM`，命令指向系统安装的 msedge.exe。在 work 内构建仅浏览器调用的诊断 EXE，共用本轮生产 helper、QDesktopServices 及 tracked spec 的运行时hook/DLL筛选，不是下一版UI试用包。最初简化探针缺少对应DLL处理，QtWidgets导入失败，未执行浏览器请求；等同产品运行时的诊断成功启动后，真实点击已登记官方地址，日志确认 frozen=true、系统请求返回true、调用期间 DLL覆盖清空及bundle PATH段移除、调用后 DLL/PATH 完整恢复。随后窗口清单出现“国家标准 - 全国标准信息公共服务平台 - 个人 - Microsoft Edge”标题；**这仅为窗口标题证据，不等于实际页面呈现已核验。**

尝试观察浏览器时，Computer Use 因无法可靠识别当前浏览器URL而自动停止；未绕过、未再次尝试浏览器视觉操作、未批准任何权限提示。用户原先描述的权限弹窗未在本轮确认复现，根因仍未确定。只提交不含完整用户PATH的摘要 `browser-request-observation.json`；完整本地诊断日志 `work/pr33-r2-browser-probe.json` 保留。后续非UI进程检查未发现该诊断EXE仍在运行，没有操作用户浏览器/旧程序来清理。

**未验证及上一包状态：** 原生1180/1440/900逐尺寸调整、真实输入法预编辑、125%/跨屏、当前实现的新便携包与安装器仍未验证；本轮原生展开弹层未重测，QTest弹层鼠标/键盘已通过。浏览器实际页面视觉核验仍 OPEN。上一版 `UI测试版_e70da765` 的6项EXE自检已由设计会话通过、退出0；326文件哈希一致，设计会话更新后的ZIP SHA256为 `bffd9a572da4fba56ae73fc3468e6e54661dee92c19a5c7c156d27f23c49403e`，不恢复本执行会话早先的失败/旧ZIP结论。全部旧测试包和数据保持原状。

本轮仅交本地实现、完整回归与真实证据供设计会话独立复验；长名称细节及浏览器视觉边界如上，不写用户最终验收通过。
