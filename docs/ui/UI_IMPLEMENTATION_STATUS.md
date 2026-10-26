# UI 实施状态与第一阶段交接

日期：2026-10-26。状态：**第一阶段首轮返修完成，等待原设计会话复验；未开始第二阶段，未作最终验收。** 最新证据见第 6 节。

## 1 分支、基线与平台 / Contract 预检查

| 项目 | 记录 |
|---|---|
| 仓库 | `https://github.com/adgo07/ECQuota-Insight.git`，实际工作树 `D:\project\能耗限额\ECQuota-Insight` |
| 分支 | `ui/phase1-qingzhou`，普通开发分支 |
| 开工源码 | `cdc89c12b0b7ea6791568838fbb382cb76842002`；实际 fetch 后与 `origin/main` 相同 |
| 当前实现提交 | `379bd9066b8cde34c12101c9fd936fec85628592`（首轮返修）；初次实现 `94aa8c7f014660422017a7c6b6b3e47d70a83ac6`，首次交接 `cb432425931b9b984732dfd505d3bbe9f9032529`；本状态文件另作纯交接提交，分支最终 HEAD 用 `git log -1` 查询 |
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

## 6 第一阶段首轮设计返修（当前交接）

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
