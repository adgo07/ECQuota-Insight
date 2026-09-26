# UEBench 能耗对标软件交接说明

> 2026-09-26：已合入独立验收PASS的GB29446新建页面源码，完整测试303项通过；新版EXE/安装包及公式Excel尚未同步验收。最新使用与测试前提见 docs/仓库使用说明.md。下文发布状态与旧数字为历史基线。

> 新增必读规范：docs/统一判定规范.md。数值边界先ROUND(...,6)再比较；最低要求未满足统一输出未达标；企业属性填写与否均不得阻碍或改变指标等级。现有软件和GB29446 Excel整改为待修改，旧测试通过不代表符合新规范。

> 本文件面向一个完全不了解此前对话的新 Codex 会话。开始任何修改前，先阅读本文件，再按“必读文档”顺序阅读项目文件。不要把历史验收记录中的旧数字当成当前状态。

## 0. 项目位置与当前基线

- 项目根目录：G:/Python Project/能耗限额
- 当前产品名称：单位产品能耗对标软件（UEBench）
- 最近一次已完成的功能提交：a83a838 发布GB29435并实现动态标准选择
- 之前与本轮相关的提交还包括：1b0faa5 修复实测反馈并优化桌面打包界面、8bda4c2 增加待确认标准只读目录。
- dist/、work/ 主要是构建和验收产物，通常由 Git 忽略；源代码、规则和文档才是继续开发的主要依据。
- 本文件生成后，第一步仍必须重新运行 git status --short，确认是否有用户的新改动；不得覆盖未提交的用户改动。

## 1. 当前项目目标

建设一个面向中文用户的单位产品能耗对标软件：

1. 首版为 Windows 10/11 x64、单机、离线、单用户、无登录、无遥测。
2. 权威范围以“现有强制性能耗限额标准目录”和“现行强制文本”为主；汇编只作为录入线索。行业标准、推荐性标准、标杆/基准水平不能自动进入规则库。
3. 评价时默认按电脑真实日期选择当前正在生效的标准；允许手动查看旧标准和未实施新标准，但必须有明显提示。未来标准在实施日前不能形成正式评价。
4. 支持直接录入单位产品能耗，或录入能源、产量、折算和分摊明细后计算实际值。
5. 每个指标单独输出 1 级、2 级、3 级、未达标、不完整或不适用；不生成产品/项目总体等级。
6. 标准规则使用版本化 JSON 和签名 .uebench 离线包；已发布规则不能由用户在软件内直接修改。
7. 架构保留未来增加 Web、Linux、安卓、苹果、鸿蒙和 NAS/低成本网络更新的可能，但当前不要为了这些平台破坏 Windows 首版的稳定性。

## 2. 必读文档与阅读顺序

### 2.1 先读交接和当前交付

1. HANDOFF.md（本文件）
2. README.md：当前范围、开发基线和常用命令
3. docs/交付清单.md：当前交付物、规则数量和发布包说明
4. docs/验收记录.md：按时间排列的验收事实；旧章节是历史记录，最后一个相关章节才代表当前收尾结果
5. docs/用户手册.md：用户界面和评价流程
6. docs/安装发布说明.md：安装包、便携版、标准包和验收步骤
7. docs/非程序员验收与AI开发教程.md：给非程序员使用和验证软件的说明

### 2.2 需要理解规则和范围时再读

- data/catalog.json：正式目录元数据；当前正式范围是 47 项
- data/scope-44.json：名称虽沿用历史文件名，但现在是正式的 47 项范围清单，不要擅自重命名
- data/definitions/：正式规则定义
- standards/development/scope-63/：开发基线，共 63 项定义，其中一部分仍是草案
- standards/development/library-index.json：开发库索引
- work/next-scope-63/GB 29435-2025标准规则专项复核表.xlsx：稀土标准专项确认表
- dist/release/统一标准规则确认表.xlsx：正式范围统一确认表

### 2.3 需要改代码时读

- src/uebench/domain/：领域模型、规则和计算逻辑；不得依赖 PySide6、SQLite 或 Excel
- src/uebench/application/：应用服务和用例
- src/uebench/infrastructure/：SQLite、文件、Excel、标准包、签名和日志
- src/uebench/ui/main_window.py：Windows Qt 界面；界面只能调用应用层
- tests/：修改代码必须同步增加/调整测试
- pyproject.toml、packaging/installer.iss：依赖和安装构建配置
- scripts/build_release.ps1、scripts/sync_release.ps1：冻结版、安装程序、便携包和 dist/release 同步流程

## 3. 已经完成的工作

### 3.1 规则和标准库

- 正式标准包当前包含：47 项当前标准、1 项历史标准；共 765 条规则，其中当前规则 753 条、历史规则 12 条。
- 统一确认表当前 753 条规则均为“同意发布”。
- GB 29435-2025《稀土冶炼企业单位产品能源消耗限额》已转为 published，共 51 个产品/指标规则。
- GB 29435-2025 的生命周期为 future，实施日期是 2027-01-01。因此“转正”已经完成，但在实施日前只能预览，不能保存正式评价。
- GB 29435-2025 已由原文 PDF 建立 SHA-256 追踪，规则中保留来源页码、条款/表号字段；专项复核表记录王玮于 2026-09-09 的确认。
- 已处理标准替代关系：GB 29447-2022 被 GB 29447-2026 替代；GB 29141-2012、GB 29437-2012、GB 29441-2012 被 GB 29141-2024 替代的处理已写入目录/历史规则逻辑。
- 7 条其他标准中“原文缺级或非单调”的情况被显式保留，禁止猜测补值或静默修正。

### 3.2 界面和规则驱动选择

- 新建评价的标准栏已压缩为一行：标准可输入/可筛选下拉、版本选择、状态提示、查看原文。
- 软件按真实日期默认选择当前生效版本；旧版和未来版可以手动查看，并显示提示。
- 规则模型新增 selection_schema（标准声明选择层级）和 selection_values（产品层级值）。
- GB 29435-2025 已实现“产品类别 → 产品规格/工序”的动态级联。
- 没有声明层级的旧规则自动使用单级“产品/工序”兼容模式。
- 适用条件和修正参数从规则数据动态生成；特殊修正算法不能硬编码到 UI。
- 评价日期和项目名称在界面隐藏，日期仍由程序自动记录；录入模式改为操作区按钮。
- 安装器、主要弹窗和评价流程已中文化；桌面图标使用 packaging/uebench.ico。
- 程序不使用 Qt WebEngine 打开 PDF，标准原文通过系统默认 PDF 程序打开，因此冻结包中不应重新加入 Qt6WebEngine*.dll、Qt6WebView*.dll 或不兼容的 Poppler ICU DLL。

### 3.3 构建、测试和验收

- PyInstaller 冻结版和 Inno Setup 安装程序已重新构建。
- 最新发布目录审计为 valid=true。
- 全量 pytest 最近一次结果为 237 项通过；有 1 条与重复 ZIP 成员测试有关的预期警告，不是功能失败。
- check_published_rules.py：753 条当前规则，incomplete=[]，boundary_errors=[]。
- verify_scope.py：47 项标准、753 条指标、原文哈希检查通过，valid=true。
- 已完成便携版隔离启动、安装程序隔离安装/启动/卸载测试：程序能创建 SQLite、日志和标准包，卸载后程序文件移除。
- 最近一次完成提交后，Git 工作区曾验证为干净；新会话仍需自行复核。

## 4. 现在进行到哪里

当前处于“GB 29435-2025 转正、动态标准/产品选择和 Windows 发布包完成后的交接阶段”。不是在等待一个未完成的代码修复。

当前可交付物位于：

- 安装程序：dist/release/UEBench-Setup-0.1.0-x64.exe
- 便携版：dist/release/UEBench-0.1.0-win-x64.zip
- 正式标准包：dist/release/initial-standard-package-published.uebench
- 统一确认表：dist/release/统一标准规则确认表.xlsx
- 范围报告：dist/release/scope-47-report.json
- 发布审计：dist/release/release-audit-unified.json
- 哈希清单：dist/release/SHA256SUMS.txt
- 源码交付包：dist/release/UEBench-source-0.1.0.zip

重要状态判断：

- 47 项正式范围已发布；开发基线的 63 项中仍有 16 项是草案，不得误称为 63 项全部可正式评价。
- GB 29435-2025 是“已发布但尚未实施”，不是“待确认”；当前日期早于 2027-01-01 时，正式评价阻止逻辑必须保留。
- data/scope-44.json 文件名中的“44”是历史遗留名称，不表示当前只有 44 项。

## 5. 当前问题和阻塞

### 5.1 没有已知的当前代码阻塞

上一次收尾时，发布审计、规则检查、范围校验、全量测试和隔离安装均通过。因此不要为了“找问题”随意重写已发布规则或安装流程。

### 5.2 仍然存在的业务/产品限制

1. 标准覆盖未完成：开发基线还有 16 项草案，必须逐项完成原文提取、专项确认表、边界测试和发布，不能批量跳过复核。
2. 未来标准限制：GB 29435-2025 在 2027-01-01 前只能预览；这是业务规则，不是 bug。
3. 原文缺级记录：已有 7 条原文事实被保留为空/警告，后续只能依据标准修改单或人工确认处理，不能自动猜值。
4. 跨平台尚未交付：当前只有 Windows 桌面版；Web、Linux、安卓、苹果、鸿蒙和网络更新只是架构方向。
5. 网络更新尚未实施：标准包目前通过本地 .uebench 文件安装；NAS/低成本网络分发需要另立设计、签名、版本回滚和权限方案。
6. GB 29435 的复核性质：当前发布依据是王玮明确批准/确认的专项表；不要在新文档中声称已经有另一名独立复核人。

### 5.3 如果重新验收失败，优先排查

- 是否误用了旧的 candidate 包，而不是 initial-standard-package-published.uebench。
- 是否从旧解压目录启动，目录中残留了 Qt6WebEngine 或 ICU DLL。
- 是否在 SQLite 初始化完成前就查询数据库；启动后至少等待 8～15 秒再查。
- 是否把未来标准的 published 状态误当成“今天可以正式评价”；还要检查 lifecycle_status 和 effective_date。

## 6. 下一步应该做什么

### 6.1 新会话接手后的第一轮操作

在项目根目录运行：

    Get-Location
    git status --short
    git log -8 --oneline --decorate
    Get-Content ./HANDOFF.md -Encoding UTF8

然后按顺序阅读 README.md、docs/交付清单.md、docs/验收记录.md，确认交付目录是否存在。

### 6.2 快速验证当前发布物

项目使用的 Python 虚拟环境是 .venv：

    $py = './.venv/Scripts/python.exe'
    & $py tools/audit_release.py dist/release
    & $py tools/check_published_rules.py --data-dir data/definitions --scope data/scope-44.json
    & $py tools/verify_scope.py --data-dir data --source-dir 'G:/标准  规范/02_能耗限额_终端产品/单位产品限额/现行强制文本' --scope-file data/scope-44.json --output work/verification/formal-scope-47-20260909.json
    Get-Content ./dist/release/SHA256SUMS.txt

如果实际电脑的 G 盘目录不同，先用 Get-ChildItem 'G:/标准  规范' 找到真实目录，不要修改代码中的规则来源哈希。

### 6.3 运行全量测试

每次功能改动后使用新的临时目录：

    $base = 'work/pytest-handoff-YYYYMMDD'
    & ./.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp $base

测试可能需要几分钟；不要在测试尚未结束时把“没有马上输出”当作失败。也可以先用以下命令确认收集数量：

    & ./.venv/Scripts/python.exe -m pytest --collect-only -q -p no:cacheprovider

### 6.4 重新构建发布物（只有代码/规则确实变更时）

    powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/build_release.ps1 -SkipTests
    powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/sync_release.ps1
    & ./.venv/Scripts/python.exe tools/audit_release.py dist/release

构建后还要检查：

- dist/UEBench/UEBench.exe 可以启动；
- 冻结目录没有 Qt6WebEngine*.dll、Qt6WebView*.dll、icuuc.dll、icudt78.dll；
- dist/release/SHA256SUMS.txt 与实际文件一致；
- 安装程序和便携 ZIP 都用新的隔离目录进行启动/卸载测试。

### 6.5 继续录入剩余标准

必须按目录顺序逐项处理剩余 16 项草案：

1. 原文和修改单提取；
2. 建立产品/工序、指标、单位、等级限额、条件和公式；
3. 生成专项确认表；
4. 另一轮逐项对照页码/条款/表号；
5. 边界和条件分支测试；
6. 用户确认后才从 draft/reviewed 进入 published；
7. 重新生成标准包、回归测试并更新验收记录。

不要因为 GB 29435 已经转正就把剩余草案批量标成发布。

## 7. 已经踩过的坑（不要重复）

1. 安装器 /DIR 路径必须带引号：路径含空格时，PowerShell Start-Process 需要类似 /DIR="G:/Python Project/能耗限额/work/installed-test"。未加引号会变成 /DIR= G:/...，Inno Setup 会忽略目标路径并安装到默认目录。
2. 安装启动后要等待数据库初始化：8～15 秒内直接查询可能得到空库或缺表；不要把启动竞态误判为安装失败。
3. 数据库字段不要猜：标准表使用 status、lifecycle_status、effective_date，不是 publication_status 列。规则 JSON 中才使用 publication_status。
4. 验证脚本参数不能混用：
   - audit_release.py 用法是 python tools/audit_release.py dist/release，没有 --release-dir；
   - verify_scope.py 需要 --data-dir、--source-dir、--scope-file，不要套用其他脚本的参数名。
5. 原文路径曾写错：当前机器实际目录是 G:/标准  规范/02_能耗限额_终端产品/单位产品限额/现行强制文本，不是把目录拆成 02/_能耗限额/_终端产品 的写法。
6. 不要使用旧候选标准包：initial-standard-package-0.1.0.uebench、initial-standard-package-44-candidate.uebench、initial-standard-package-46-candidate.uebench 和“首批6项”文件不能作为当前全量正式包。
7. 不要把 published 和“已实施”混为一谈：GB 29435-2025 是 published/future，必须同时检查实施日期。
8. 不要直接改正式 JSON 中的限额：标准更新必须经过原文/修改单、确认表、测试、发布包和审计；不能口头改一行数值。
9. 不要为打开 PDF 重新引入 Qt WebEngine：当前用系统默认 PDF 程序打开原文；重新收集 WebEngine 会造成安装包变大，并可能重现 Qt/ICU DLL 冲突。
10. 不要把两个同名产品简单合并：同一“产品/工序”可能对应不同指标，例如硫磺的综合能耗和吨酸电耗；最终显示和规则 ID 必须保留指标区分。
11. 不要把界面写死成两级：只有规则包声明了多级选择才生成多级控件；旧规则必须保留单级兼容。
12. 不要使用 Python eval 执行规则包：公式必须使用受控的规则节点和 Decimal 计算。
13. 不要把 dist 里的生成文件当源代码修改：源代码在 src/、规则在 data/和 standards/development/、构建由脚本生成；修改后重新构建和同步。
14. Git 换行提示不是错误：git diff --check 无输出才表示没有空白错误；LF/CRLF warning 可以记录但不要因此重写全部文件。

## 8. 关键文件、命令和注意事项速查

### 8.1 关键代码文件

| 文件 | 作用 |
|---|---|
| src/uebench/domain/models.py | 标准、产品、指标、选择层级和结果模型 |
| src/uebench/ui/main_window.py | 主窗口、标准一行选择、动态产品级联 |
| data/definitions/gb-29435-2025.json | GB 29435-2025 正式规则 |
| tools/promote_gb29435_2025.py | 稀土标准可审计转正工具；重新执行前先看 --help 和当前确认表 |
| tools/refine_gb29435_2025_rule.py | 稀土标准规则生成/精化工具 |
| tools/check_published_rules.py | 当前规则完整性、边界和直接录入烟测 |
| tools/verify_scope.py | 目录、定义、原文和 SHA-256 范围校验 |
| tools/audit_release.py | 发布目录哈希、包内容和确认表审计 |
| scripts/build_release.ps1 | PyInstaller + Inno Setup 构建 |
| scripts/sync_release.ps1 | 将程序、标准包、确认表、模板和文档同步到 dist/release |

### 8.2 规则更新硬门槛

- 只允许 published 规则参加正式计算。
- 标准包安装前自动备份，签名/哈希/版本冲突必须校验，失败要回滚。
- 历史评价保存规则快照；更新标准包不能悄悄改变历史结果。
- 评价结果要保留计算轨迹和原文来源，不要只保存最后一个等级。
- 所有数值计算使用 Decimal，不能引入二进制浮点参与限额边界比较。

### 8.3 当前交付哈希

以 dist/release/SHA256SUMS.txt 为准。上一次收尾核验的关键值为：

    UEBench-0.1.0-win-x64.zip       424af9e445264702b5b43f36c0f8346dad0855b9dd88d80028f5d50780d785b4
    UEBench-Setup-0.1.0-x64.exe     234bb4b00c3ca3ea3d992b5ed3f5e3ee2ef9f01343680ee96819a98ae248a911
    UEBench-source-0.1.0.zip        3359dfc171a837e4087e7b9ad50d9f6335156e3e5732706a2de71ee82b0f929b
    initial-standard-package-published.uebench
                                      4f025b8a45f03fc5539b2d5eb76bdf6c3d127b863e7485b46fbb100b6f221727

如果这些文件后来重新构建，哈希必然变化；不要在 HANDOFF 中坚持旧哈希，应以新的 SHA256SUMS.txt 和 release-audit-unified.json 为准。

## 9. 给下一位 Codex 的工作原则

1. 先读文档、查状态、跑审计，再改代码。
2. 任何标准规则变更都要同时更新来源、确认表、测试、包和验收记录。
3. 用户已经确认的业务口径是基线；如果要改变判级、实施日期、范围或数据来源，先形成变更说明，不要在代码里默默改变。
4. 遇到信息缺失时返回“不完整”或阻塞人工确认，不猜测限额、单位或修正系数。
5. 完成修改后必须给出：改动文件、测试命令/结果、构建产物路径、审计结果和剩余风险。
