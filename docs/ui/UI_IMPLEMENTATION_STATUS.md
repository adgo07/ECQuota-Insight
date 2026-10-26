# UI 实施状态与第一阶段交接

日期：2026-10-26。状态：**第一阶段实现完成，等待原设计会话检查；未开始第二阶段，未作最终验收。**

## 1 分支、基线与平台 / Contract 预检查

| 项目 | 记录 |
|---|---|
| 仓库 | `https://github.com/adgo07/ECQuota-Insight.git`，实际工作树 `D:\project\能耗限额\ECQuota-Insight` |
| 分支 | `ui/phase1-qingzhou`，普通开发分支 |
| 开工源码 | `cdc89c12b0b7ea6791568838fbb382cb76842002`；实际 fetch 后与 `origin/main` 相同 |
| 当前实现提交 | `94aa8c7f014660422017a7c6b6b3e47d70a83ac6`；本状态文件另作纯交接提交，分支最终 HEAD 用 `git log -1` 查询 |
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

## 3 测试命令、结果与限制

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
