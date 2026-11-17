# 焦炭产品接入实施记录

日期：2026-11-17。承接设计提交 `d8ecc4f9f687de46612ade2b66e4c32d1951832f` 及 PR40。本文记录实施证据和独立验收入口，不是 Stage D 通过或正式发布声明。水泥已有实现保留，Stage D 暂缓。

## 平台 / Contract 预检查

- 实际仓库 origin 为 `https://github.com/adgo07/ECQuota-Insight.git`。主目录旧分支和未跟踪文件未修改；专属工作树从干净设计 HEAD 创建 `codex/coke-product-implementation-20261117`。
- 开工已执行 root/origin/branch/HEAD/status/fetch；首次 fetch 因沙箱写 FETCH_HEAD 被拒，通过正常权限申请后成功。默认分支 main，`main...origin/main=0/0`，均为 `1bf58cc1c2d190f3ebc3b5f37148633102623224`。
- Frozen 锁定 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`；相关 Architecture2.1、Numeric Contract/Profile/Conformance v1按该SHA读取。当前GUIDE_INDEX路由的标准开发、产品交付及UI v0.2/家族规格/验收清单已读取，不升级lock。
- MUST：独立Domain、Decimal28/HALF_EVEN、全值比较、来源/版本快照、历史不重算。MUST NOT：float恢复业务值、隐式ROUND6/epsilon、显示值回流、未定补0、生产r1冒充新链、替换公钥或伪造签名。
- D-ECQ-002～006继续REGISTERED DEVIATION；本轮未发现须修改中央Frozen的冲突，不需要中央Contract修改。
- 相关Standard Issue：001～005。001决定与003区间内插值保持，不改002部分外属、003表外、004混合熄焦、005气种对应；自动热值/焓折标引用尚待核验；这是取证缺口，尚无证据表明标准原文本身存在新增歧义，不另造问题编号。当前不改变既有式3/最高级别软件解释。

## 四块进度与真实边界

| 块 | 本轮落实 | 尚未完成的出口 |
|---|---|---|
| 1 已折标预览 | 家族壳中单页隔离预览、两炉型、中文文本输入、外属两项事实、混合煤气百分比转换、缺项/未定/不适用/结果过期、折叠依据；只调用preview_coke，不读规则库或存储 | 原生桌面矩阵按实际观察补录；普通正式入口仍关闭 |
| 2 原始能流 | 五分量归集、独立干全焦产量、总量/明细互斥、显式kg/t/tce/MWh/GJ换算、实测有效系数优先、附录A/B参考、104个精确蒸汽节点、氮气主副产品、重复物理流ID拒绝、零量显式声明 | 自动热值/热焓转换未实施（引用待核验）；未知气种不自动匹配；不同名称同一物理流仍需用户核查 |
| 3 记录与Word | 既有JSON列增加可选versioned载荷，未迁移数据库；Application配套身份/炉型/版本/hash检查；最高等级完整性；既有事务记录+审计；历史只读视图及Word复用现有报告载体/两页签 | 生产规则参数显式采用及一致性提升、整映射批准、匹配私钥签包/PIN尚缺；仅内存夹具证明存储能力，不代表普通页面已开放正式计算保存 |
| 4 验收/Windows | 定向、Numeric、完整回归、隔离DOCX样本及精确源码预览EXE构建分别记证 | 映射/签包/原生及Word实开、正式安装升级/Stage D仍待证；不宣布SUPPORTED |

生产 `data/definitions/gb-21342-2025.json`、签名包、PIN、公钥和正式范围未修改。未新增焦炭候选规则JSON或套用水泥特批。记录测试中的r2仅由内存克隆旧定义加采用标记，绝非批准或待发布的正式r2。执行参数仍只有既有Domain一个真值源；正式生产提升前仍须完成参数绑定审核。

新增可选载荷承载五量、全部判级条件、原始明细及有效系数来源、每级partial状态、输入摘要、Rule/Calculator/Numeric版本。旧记录无载荷走原只读路径。报告仅投影保存三快照，未调用当前计算器；不加入001解释或合规主结论。已知1级满足不强迫补齐L3；更高级未知不能因L3满足而保存。

## 提交与验证

| 源码 | 内容 / 结果 |
|---|---|
| `24cb9c65284435de5d787425339395e8cad2ff1f` | 前两块；新增产品11项通过；与已有焦炭核心/判级共415项通过 |
| `64a1e4a89b815b9d631974343050e46e8cf9d9eb` | 记录/报告适配；焦炭集成、分层和范围保护452 passed；Numeric工作流对应专项138 passed（首次开始于记录层工作区，后续提交记录身份） |
| `0441b1630436d5799fcb7990084972505377a345` | 隔离EXE构建入口与自检；小范围UI/报告补修15 passed；后续完整回归和构建结果见补录 |

测试使用仓库 `.venv/Scripts/python.exe`、`QT_QPA_PLATFORM=offscreen`、全新 `work/pytest-coke-*` 临时目录，未触碰真实用户库。首次literal full suite在收集阶段因缺少项目声明的python-docx中断（1 error），补齐python-docx1.2.0/lxml6.1.3后重跑，不将首轮记为通过。测试命令统一 `python -m pytest … -q -o addopts='' -p no:cacheprovider --basetemp=<新隔离目录>`。

Numeric专项执行：`tests/conformance/numeric/test_ecquota_numeric_v1.py`、`tests/pilots/numeric/test_qzc_n01_a.py`、`tests/test_gb29446.py`、`tests/test_engine.py`、`tests/test_excel.py`、`tests/test_ui.py`；与`.github/workflows/numeric-v1-adoption.yml`逐项核对。远端工作流只有对应精确HEAD运行后才能称CI通过。

## 独立验收入口

1. 源码预览：`python tools/coke_preview.py`，自动新建TEMP目录，关闭后清理；不能指定真实用户库。`--self-check`不启动GUI、不写记录。
2. 定向：`tests/test_coke_product.py`、`tests/test_coke_records.py`及既有`test_gb21342_core.py`/`test_gb21342_assessment.py`。独立预期继续引用设计中C04及Mapping C08，不从计算器反产Golden。
3. 隔离记录/Word：`python tools/coke_product_evidence.py --output-dir <不存在的新目录>`；仅该进程临时注入开发正式范围，退出恢复；不保存候选规则文件。样本明确为合成数据。
4. 隔离预览EXE：`python tools/build_coke_preview.py --source-commit <精确干净HEAD> --output <不存在的新目录>`；身份/EXE哈希/自检输出独立记录。不是正式安装包，不代表生产配套规则或完整交付通过。

干净64a1e4a已生成三份DOCX（111→1级且L3未定、113→3级、138→未达3级）及真实SQLite记录，`work/coke-evidence-64a1e4a/evidence.json`保留版本、快照hash和文件hash。技能render_docx.py尝试渲染均失败，原因LibreOffice soffice.exe未找到，常见安装位置亦不存在；尚未通过渲染/视觉QA，不将文件生成当排版通过或MS Word/WPS实开通过。

三条记录另经独立Python进程重开：将`coke_records.preview_coke`替换为必抛异常后仍全部读取并生成报告视图，级别/规则快照hash一致；证据`cross-process-readback.json`。未把该只读重开测试称为原生GUI或Word实开。

干净`0441b1630436d5799fcb7990084972505377a345`构建隔离预览EXE成功，SHA256=`028204a6123555c95f5fd7eb72d465286aa8ebd876ab205b937ae3ec88e77932`，自检exit0，1级/L3未定、1000kWh→122.9000kgce、记录数0均通过。身份与输出位于`work/coke-preview-0441b16/build-result.json`；EXE在其`portable/UEBench-Coke-Preview/`下。只验证无头入口，不代表原生GUI/安装器通过。

完整回归第二轮出现Excel跨进程读取失败，定位到共享虚拟环境editable安装指向主目录旧源码；旧模型拒绝cement/coke新字段。该错误环境执行已中止，不能记录通过。显式设置`PYTHONPATH=<当前工作树>/src`后同一跨进程测试1 passed；后续完整回归使用该配置重跑，未改全局虚拟环境源码绑定。额外焦炭/分层/源码交付定向50 passed。本机正确环境完整回归在本报告提交时仍运行，日志`work/coke-full-suite3.log`；不预写通过。最终精确HEAD结果在[草稿PR41门禁](https://github.com/adgo07/ECQuota-Insight/pull/41/checks)核对，交接消息给出最终状态，不将旧HEAD通过迁移到新HEAD。

原生Computer Use按Owner指定委派GPT-6 Astra低推理独立子Agent，父实施Agent未自行操作桌面。只允许新TEMP数据和当前隔离程序；实际观察另行补录，未观察项OPEN。

原生最终结果：仅在启动24cb9c6的源码预览后枚举到窗口`398852`，未取得截图或可访问性树。应用访问返回`Computer Use app approval timed out`，属于应用访问审批超时，不是自动安全审核拒绝；未进行任何表单输入或Word实开，全部原生矩阵OPEN。后续代码/EXE没有原生复验，不将该窗口枚举记为GUI通过。专属四个辅助进程已按精确PID和父子链核实后停止，未删除TEMP/旧数据。完整观察位于`work/coke-native-20261117/NATIVE_OBSERVATION.md`。

0441b16便携ZIP共337个载荷文件，85,015,482字节，SHA256=`fe37a0f1bbfc1497fc08d9fd9e41edc5c497895162cf2e39e11a23b860d4d449`，CRC通过；`payload-sha256.json`记录每个文件的大小/hash。该资产只对应0441b16，后续身份校验补强不冒充已进入该资产。

`ed161e0924b1f841f6af62689cff9a9b326e1b22`进一步核对记录的数值行为版本、标准信息、单位及专属输入副本，全部焦炭测试423 passed；随后缺项/非法载荷错误处理定向11 passed（含既有记录案例）。没有改变式3、阈值或Numeric行为版本的值。最终头提交的CI重新执行，旧头Numeric/N01-A成功仅属各自版本证据。

### 后续构建修复与全套执行边界

0441b16及baed566旧预览资产后经载荷审查发现误收集`icuuc.dll`/`icudt78.dll`，与现有`uebench-stage-d.spec`已记录的Poppler ICU78/Windows Qt符号冲突相同；旧自检只验证业务链，未覆盖Qt载入。因此这些资产标记为被替代，不作为可用GUI产物交付，旧exit0/CRC结论仅保留其原有范围。

构建修复`b2acf1aba5200e3b70ae1b92269e1ebd86daa4fe`仅在本次全新输出目录内核对目标路径后移除两个不兼容副本；不修改系统DLL或既有产物。`--self-check`增加离屏创建真实Qt表单，源码自检已返回`qt_form_created=true`、记录数0。后续替代EXE必须在新精确源码构建并通过该增强自检，以对应`build-result.json`/`portable-result.json`为准；离屏不冒充原生验收。

本机第三轮全套在执行期间HEAD有推进，收集时固定HEAD的两项构建身份测试如实失败；冻结HEAD后该两项单独复验2 passed，未修改测试规则。该混合HEAD本机全套不能记为精确提交通过；后续以固定检出的精确HEAD CI作为完整回归依据，最终计数与状态由PR41门禁及交接给出。其余本机失败/跳过仍以原日志完整保留，不用定向复验覆盖全套结论。

最后补齐原始能流预览的有效系数/来源明细及来源待补警告投影，未改变归集算术；新增界面案例验证旧总量111不会与1000kWh明细叠加，结果为122.9，并可在依据中核查表A.2/0.1229；实测系数改为0.2且未写来源时结果为200并直接提示来源待补。产品/记录定向23 passed。新增投影后的资产需重新按精确源码构建，不将7d5ae0f资产冒充更新后的界面。

2026-11-17再次在本机实际发现授权原文目录，重新核对焦炭PDF SHA256仍为`00fcc51c02c6d73d39bcab3103227fca2ee93841abce45d1576edaeba25595a0`，抽取并目视核验PDF8/9的§6.1.2与附录A，核对PDF13工质表及PDF14参考文献。确认实测优先、热焓折算及既有系数表；这些页面没有直接列出自动换算除数或完整引用算法。该目录未检出GB/T2589、GB/T12723原文；官方元数据和其他标准编制说明的引用不能代替本链完整取证，因此继续只接有效系数，自动热值/焓折标保持未实施。不修改映射原文，不制造新标准问题编号。原文/临时渲染图不提交、不分发。

百分比适配补充极端下溢边界：混合煤气时间百分比`1e-1000026`在除100时超出工作范围，明确显示中文换算错误、清空结果并恢复按钮，不当成0；该守卫不改变有效输入的换算或数值配置。

## 保留事项

整标准仍MAPPING、现行批准映射无；正式评价范围仍仅GB29446。签名私钥缺失不通过换公钥处理；正式规则/签包/PIN/交付须成套。水泥IMPLEMENTED / Stage D OPEN保留，RS05 IN PROGRESS，0.2.0未发布。本报告不授权合并、发布或tag。

Knowledge capture：无新增知识文章；引用核验缺口记于本报告，未将尚未核齐原文的取证问题冒充新增标准歧义。


## PR41 验收意见核实与最小返工（2026-11-17）

### 平台 / Contract 预检查

本次返工基线为 `116fd0c4b43bbcc2e2eb735a1ecaf55616d273de`，专属工作树 origin/branch/HEAD/status/fetch 均重新核对；`main=origin/main=1bf58cc1c2d190f3ebc3b5f37148633102623224`。锁定中央 SHA 仍为 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`，Architecture2.1、Numeric Contract/Profile/Conformance v1 不升级。已重读当前 GUIDE_INDEX 及其 UI v0.2、家族规格、验收清单路由。本次遵循历史快照不重算、版本相互绑定、全值 Decimal、中文业务依据；禁止隐式修约、恢复生产r1新链、扩大正式范围或签包。问题分类为本地产品衔接缺陷（LOCAL DEFECT），不需修改中央 Contract。相关 Standard Issue 001～005 保留；本次不改变式3、阈值、既有最高级别解释或任何未决问题决定。

| 意见 | 核实及实际处理 | 验证 / 保留边界 |
|---|---|---|
| M-1 | 确有桌面白名单和默认文件名遗漏；接入焦炭保存报告视图，复用现有两页签和真实 Word 按钮，默认文件名改为焦炭能耗对标报告 | 自动化调用 MainWindow.view_record、两页签投影、按钮点击、实际 DOCX 内容均验证；不开放普通正式评价或保存入口 |
| M-2 | 原分支确无调用覆盖；工具首条改为真实电力1000kWh×0.1229=122.9kgce、产量2t的 flows 记录，保留表A.2有效系数与来源，并走实际Application保存/读取/Word链 | 正例保存读回与报告；数量、系数、来源、分量总量、五量输入、flows版本篡改均拒绝。不是用书面降级移除既定能力 |
| L-1 | 未自动登记该气种为既有实现边界；“Issue005仅用字差异即可采用别名”并无批准依据，不能据此扩展系数匹配 | 页面直接说明驰/弛放气对应待确认，暂不自动提供表列系数，可用其他能源填写有效系数与来源；Issue005仍OPEN |
| L-2 | 展开依据确实显示内部字段及None；新增展示适配，输入与事实用中文，混合煤气比例不适用时明确显示不适用，布尔事实和比较结果分别显示是/否及满足/不满足 | 水分修正、挥发分插值、各级限额求和分别核对，保留具体算法与数值；后台原始trace及审计版本不删除 |
| L-3 | 焦炭统计期确实未投影到列表；按焦炭已存notes读取统计期，文件名同M-1修复 | 列表周期与保存请求一致；不重新解读历史统计期 |
| L-4 | 历史读校验确实依赖当前常量；历史采用固定、只追加的已知v1身份组合（payload/calculator/rule/numeric behavior/source）校验，并与envelope/输入摘要/Rule快照marker相互绑定 | 模拟全部当前版本升级后，关闭数据库再重开且禁用计算器仍可读；当前新写入仍严格绑定，未知版本组合及篡改均拒绝。历史不重算flows或业务结果；有效系数/来源读取保存值，能源名称仍由已知标识的展示字典投影，不作为计算来源 |
| L-5 | 精确节点语义正确但录入困难；提供A.3/A.4原表节点填入控件，自动填绝对压力和温度 | 两类表完整节点数、精确lexical值及删除前行后操作验证；填入后选择复位，手工改p/t不保留旧选中；Domain继续精确匹配，未新增插值/外推 |
| L-6 | 已有本机机器证据，不能判断为只有声明；本次重新计算旧116fd0c EXE/ZIP哈希、CRC并实际再跑增强自检，提交可审计摘要；TASK_STATE更新时间同步 | [旧资产摘要](evidence/GB21342_PREVIEW_116fd0c_SUMMARY.json)明确仅旧head、不含本次修复。335载荷文件/71,184,370字节，Qt离屏表单及记录数0；原生GUI、Word/WPS实开分页、正式安装升级及Stage D均OPEN |

最终返工源码焦炭四模块 **447 passed / 0 failed / 0 skipped**；父Agent独立执行产品/记录 **43 passed / 0 failed**。测试身份、文件摘要及JUnit摘要见[返工测试摘要](evidence/GB21342_PR41_REWORK_TEST_SUMMARY.json)。首轮新增节点用例中2项因Qt将tuple转换为QVariant list而断言失败，改为核对完整节点lexical值后通过；未放宽业务比较或Domain测试。额外Numeric及记录页回归在提交时仍运行，最终状态另补；本次精确提交的三项CI须推送后核对，不将旧head CI迁移为本次通过。

真实证据工具已在新隔离目录成功保存3条记录并生成3份DOCX（首条为电力flows，其余总量）；这只证明数据链和文件生成，不替代Word渲染或原生验收。现有EXE本轮不重建，后续展示修复只由源码测试证明，不能将旧EXE称为本次交付。PR保持草稿，不合并、不发布、不tag；生产data、PIN、公钥、锁定文件与正式支持集均不变，水泥Stage D继续暂缓。


## 265f215 修复后实物及报告验收续录

本轮按父设计顺序执行：先固定干净源码重建隔离预览，再生成当前链的合成记录/报告，委派指定 Astra 原生验收，最后才补证据文档。构建源码始终为 `265f215aeb4705695d7b72017fb5631014e33ad9`；本续录提交仅更新证据，不声称包绑定后续文档提交。

### 平台 / Contract 预检查

已实查专属工作树 root/origin/branch/HEAD/status/fetch；origin 为 ECQuota-Insight，分支 `codex/coke-product-implementation-20261117`，构建前干净；main 与 origin/main 均为 `1bf58cc1c2d190f3ebc3b5f37148633102623224`、差异0/0。fetch首次沙箱写拒，正常升级后成功。lock及中央Frozen SHA仍为 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`，Architecture2.1、Numeric Contract/Profile/Conformance v1按锁定SHA读取。中央本地clone实际origin已验证，ACTIVE文件通过 `origin/main`（`829853a943c421e0b9864d84f3d94970d2ddf688`）读取GUIDE_INDEX、UI v0.2/家族规格/验收清单及产品交付规则，未把其在途分支作为正式依据。MUST保持Decimal全值比较、历史快照不重算及版本追溯；MUST NOT隐式修约、显示值回流、改正式支持集或签包。未发现新公共冲突、不需中央Contract修改，D-ECQ-002～006保持已登记偏差；相关Standard Issue001～005保留，本轮不改变式3、等级解释或未决决定。

### 实测证据及边界

| 验证项 | 本次实际结果 |
|---|---|
| 全新隔离EXE | PASS：`work/coke-preview-265f215-native2/portable/UEBench-Coke-Preview/UEBench-Coke-Preview.exe`；12,228,493字节，SHA256 `082c036b0e9dac695e31db5517f29041f5ce06c8980c5604486454661dfe0355`。增强自检exit0、真实Qt离屏表单创建true、记录数0、1级/L3未定、1000kWh→122.9000kgce |
| ZIP与载荷 | PASS：`UEBench-Coke-Preview-265f215-portable.zip` 70,733,715字节，SHA256 `074b053f3851afd5bf260ffba01470b75d4f12580059d8dfd51ec79c368fec95`，CRC通过；335载荷文件共162,602,221字节，逐文件清单SHA256 `95960ff730a3190ab14303d1502641b7b0d027cea46d8d69e4ebd3bf9b5434d7`。与旧116fd0c资产分离，不复制旧证据 |
| 当前源码合成记录/Word | 数据链PASS：新目录 `work/coke-evidence-265f215-native2` 三条真实SQLite记录与三份DOCX；1000kWh×0.1229/2t=61.4500→1级（原sample_id111仅为稳定样本标签，不是该次实际能耗）；总量113→3级、138→未达3级；首条保留表A.2/有效系数来源 |
| 跨进程历史保真 | PASS：独立新Python进程禁用 `coke_records.preview_coke`，三条历史全部读回并构建报告视图，实际值/等级/Rule hash一致；读取前后三列request/result/rule原始JSON SHA256逐条相同，见 `cross-process-readback.json` |
| 原生EXE/源码历史/Office | OPEN：指定GPT-6 Astra低推理Agent初始化后，两次 `sky.list_apps()`（间隔2秒）均立即返回 `Computer Use helper already has an active request`。未得到窗口/截图/树、未启动应用或输入；不是旧轮审批timeout，也不是自动安全审核拒绝。未终止未知helper或绕过占用。新EXE交互矩阵、源码MainWindow两页签及真实Word按钮、三份DOCX的Word/WPS表格分页上下标/截断检查全部未观察，不记PASS |
| DOCX渲染 | OPEN：使用documents技能和实际解析的bundled runtime运行 `render_docx.py`，报 `LibreOffice soffice.exe was not found on PATH`；未生成页图，不能交付视觉验收通过。未安装软件或借用用户桌面LibreOffice |
| 精确源码CI | 265f215 Numeric v1 run44110927512与N01-A run44110927701均success；PR Gate run44110927544的compile/source gate均success，strict literal full suite仍in_progress，尚无完整套件通过结论。不能把此状态平移至后续文档提交 |

[可审计摘要](evidence/GB21342_265f215_DELIVERY_ACCEPTANCE_SUMMARY.json)包含构建身份、文件hash、记录/DOCX摘要、原始JSON前后hash及CI快照；完整本机载荷清单、自检输出、原生观察继续保留在各专属目录。父Agent已独立重新计算EXE/ZIP hash并核对身份/增强自检。当前无新增生产代码，因此不无改动重复已完成回归；完整回归仍按精确head CI实际结果补录。

本轮未改变生产data、PIN、公钥、lock或正式支持集；焦炭整体仍MAPPING、正式仅选煤，水泥Stage D暂缓。原生/报告视觉、生产规则参数采用/签包、整映射批准与正式安装升级/Stage D仍OPEN。PR41保持草稿，不合并、不发布、不tag。

### 构建源码CI最终核实

上节“strict literal full suite仍in_progress”为提交时历史快照。后续实际重新查询确认：构建源码 `265f215aeb4705695d7b72017fb5631014e33ad9` 的 PR Gate `44110927544`、Numeric v1 `44110927512`、N01-A `44110927701` 均已 completed/success；job `134135978175` 全部步骤（含严格单次 literal full suite 与 summary）均 completed/success，父Agent亦独立核实。未将此结论套用到后续纯文档head；文档提交的CI另按精确SHA跟踪。包仍绑定干净265f215，不因纯证据文档更新重建。

本轮续派同一Astra低推理Agent，一次 `list_apps` 探测成功并发现已安装Word；随后应用操作尚未取得明确结果或可审截图。该枚举恢复不能视为EXE、历史页或Word原生通过，当前矩阵仍OPEN。未重复在途请求、终止未知helper或自动安装Office；可独立同步的CI/构建/记录证据先行提交，后续原生实际结果另按观察补录。

## 2026-11-18 完整功能实施续录

### 平台 / Contract 预检查

本轮源起点`f6e60239cfc2a5a2acfe68cc7756eecbe8f22cc7`，实际origin/root/branch/head/status/fetch均核实；main仍`1bf58cc1c2d190f3ebc3b5f37148633102623224`。中央lock为`ee5feb0cc34dbd99790500fadd0c4c932e202a20`，Architecture2.1与Numeric Contract/Profile/Conformance v1不变。按当前GUIDE_INDEX重读标准开发、交付及UI家族规格/指南v0.2/清单；遵守Decimal28/HALF_EVEN、全值比较、无损输入、参数快照与历史不重算，禁止隐式修约、显示回流、float恢复与UI另算。已登记偏差不在本轮关闭，无新增CENTRAL CONTRACT GAP或中央修改需求。Issue001～005相关；沿用已确认最高级别与表内线性，其他未规定情形不补造算法。水泥正式验收继续暂缓。

### 实施结果与当前验收边界

| 能力 | 已实施内容 | 当前证据 |
|---|---|---|
| 主应用完整链 | 焦炭专属Form接入MainWindow选择、炉型同步、五量/原始明细互斥、对象/统计期、一次evaluate及事务保存；partial/不适用保留预览；修改过期、防重复、保存失败可重试；真实历史两页签及Word动作 | 最终主应用/产品/记录定向54通过；真实审计写入失败回滚与重试、readiness负例均覆盖 |
| 规则绑定 | 专属可选参数载荷、严格版本及内容核验；内核实际消费参数；新记录v2保存参数hash；r1/只加marker/改值/错源拒绝 | 规则/记录/内核443通过；新增字段None不序列化，保留旧快照形状 |
| 热值及热焓 | 按核验原文收到基低位热值或蒸汽热焓÷29307.6；与实测有效系数互斥；维度/能源类别校验；干煤干焦/附录参考系数不被重算覆盖 | 三模块58通过；最后增强禁实际计算入口及修改当前展示字典后历史报告保真，flows/product32通过 |
| 历史保真 | 已知v1/v2身份独立于当前写入版本；保存参数/来源供只读报告；未来展示字典不能改变v2保存能源名称 | 真实265f215合成旧库三条v1，sqlite mode=ro、五个计算入口禁用，原三JSON不变；工具`tools/check_coke_legacy_readback.py`可重跑 |
| 隔离完整应用 | `tools/coke_application.py`，TEMP专属标记目录可重开；真实签包对账及readiness，内存候选从已装r1生成，不改正式支持集 | 源码主应用保存/重开hash、记录数及审计数保真；无条件跳readiness不作为验收 |
| 签包准备 | 新增显式焦炭target、严格参数/替代链/既有信任根检查及不读钥不写包dry-run | 焦炭10项及既有工具29项通过，最终组合65通过；真实父包dry-run为48项/765规则，仅焦炭替换，47定义与corrections保留原字节 |
| Windows实物 | 新增`tools/build_coke_application.py`，精确干净提交、完整主应用EXE/ZIP、自检和跨进程重开、载荷hash | 本续录提交时尚待实际构建；原生源码与Word观察进行中，不冒称通过 |

上述测试组有重叠，不相加。父独立首轮规则/记录/主应用49通过；Numeric工作流对应专项及记录177通过。当前literal full suite正在运行，最终结果另补；本次提交的精确CI也须另核。原生前一轮明确返回`Computer Use app approval timed out`，无窗口/截图，已结束；不能用枚举恢复替代原生通过。

### 已消除的历史外部缺口与待确认项

本机现有GB/T2589—2020与GB/T12723—2024原文，已计算SHA并实际目视关键页，父独立复核；引用链、29307.6基准及与附录系数的区别写入[V1.1审核稿](../../standards/mappings/GB21342-2025/标准映射表_V1.1_审核稿.md)§5.7。该稿§7集中D01～D05边界，已提交Owner确认，当前尚未记批准。

通过既有签名工具仅派生公钥比对，已确认本机既有私钥匹配软件信任根；不输出秘密、不更换公钥。旧“缺签钥/缺引用原文”是历史取证状态，不能继续作为本轮硬阻断。当前只完成dry-run，尚未签正式焦炭包或提升生产定义/PIN。正式支持须按批准映射、独立验收和配套交付实证推进；本段不宣称SUPPORTED、正式发布或水泥验收通过。


## 2026-11-18 最终完整主应用开发包与独立验收补录

### 平台 / Contract 预检查

构建源码为干净 `f4aea0ba091e93e7a1bc12822d30d3e8419d3c5e`，origin仍为ECQuota-Insight、专属分支未切换；构建前重新确认HEAD/status，构建期间未混入后续文档。中央锁定SHA仍为 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`，Architecture2.1及Numeric Contract/Profile/Conformance v1不升级。沿本轮已读取的中央ACTIVE标准开发/交付/UI v0.2路由，MUST保持Decimal全值比较、参数/输入/结果快照互相绑定、历史不重算；MUST NOT隐式修约、epsilon、float恢复、显示值回流、替换公钥或伪造签名。验收发现的产品衔接/展示问题按LOCAL DEFECT修复，无新增Frozen冲突或中央修改需求；D-ECQ-002～006保留。相关Standard Issue001～005，不改变既有最高级别解释或擅自处理未规定情形。

### 独立检查发现及收口

- 真实主应用已接焦炭专属Form、对象/统计期、炉型/产品同步、五量与能流互斥，一次Application.evaluate完整结果及审计同事务保存；最高等级已确定时不强迫低等级未知补齐。partial/不适用只显示预览；输入变更使旧结果失效、重复信号不重复保存。历史列表、两页签及Word沿保存快照链读取。
- 本轮开发入口显式启用真实标准库readiness，先核对既有签包，再从其r1生成内存参数化候选；只在专用TEMP标记目录工作并支持重开，不把开发作用域写回正式支持集，也不新建长期候选JSON。未对账负例仍阻断。完整热值/焓、参数化规则及v2记录由同一Domain执行，v1历史保留只读兼容。
- 1280×800和960×600实际Qt offscreen显示/滚动/抓图共22张代表图，覆盖五量、条件、明细左右、计算、结果、记录列表和两页签。计算、查看记录和Word共8次位置核对均可完整滚入viewport。父独立目视发现开发scope标签误写正式支持、禁用热值单位占位裁尾及焦炭来源未登记；`18722bd`统一复用development-aware标签、缩短为“选择单位”、登记已重新核对编号/名称/现行/发布/实施日期的固定官方页面。两张960×600补图经父复查通过。表格14列需自身横向滚动，长待定原因可换行；这些观察均为离屏，不当作原生交互通过。
- 随后父独立覆盖审查发现保存失败时清空预览不符合设计；`f4aea0b`增加焦炭专用保存异常携带已算结果，UI保留预览及有效系数/来源，明确尚未生成记录，恢复重试且历史/Word按钮禁用。实际审计失败事务回滚与重试只生成一条记录，异常处理不再次调用计算器，也不显示保存成功；用户重试仍执行正常计算保存流程。此前`f1bbd61`及`18722bd`资产保留各自历史身份，不冒充该最终修复。

### 最终开发资产及机器检查

| 项目 | 实际结果 |
|---|---|
| 源码身份 | `f4aea0ba091e93e7a1bc12822d30d3e8419d3c5e`，source_dirty=false；完整主应用开发验收包，不是正式发布 |
| EXE | `work/coke-application-f4aea0b/portable/UEBench-Coke-Application/UEBench-Coke-Application.exe`；12,252,624字节；SHA256 `78bb83e9f4a4e43f36ba697009e10bf9a296e774ce11d1da484fe57409a98699` |
| ZIP | `UEBench-Coke-Application-f4aea0b.zip`；70,887,600字节；SHA256 `6c83816aa27d243812a5e1f7a263df266f39b03bfd0e7fdd6a2fa260d74655ee`；CRC PASS |
| 载荷 | 337个文件，逐文件大小/hash全部独立重算；载荷清单SHA256 `c6fc646d962a0388651e467038019e8360f49b8f2f898f4793756c59818201c4`；内置既有签包与生产配套原字节相同，不含新的正式焦炭签包 |
| 实际运行依赖 | Pydantic2.13.4、PySide6 6.10.1、PyInstaller6.20.0、python-docx1.2.0；最低Pydantic声明已在6e85f3c补齐并包含于最终源码 |
| 已构建EXE自检 | exit0；真实MainWindow dispatch、readiness=true、最高等级1级、保存1条及审计52条；DOCX实际生成；离屏Qt表单可创建 |
| 独立EXE进程重开 | exit0；request/result/rule三列原始JSON SHA256逐一不变，记录/审计数仍1/52，新增记录0，保存报告可读；不重算历史 |

以上资产已由父Agent独立复算EXE/ZIP哈希。完整机器摘要见[最终开发包摘要](evidence/GB21342_COMPLETE_APPLICATION_DELIVERY_20261118.json)；本机完整build-result、逐文件清单及独立校验保留在`work/coke-application-f4aea0b/`。桌面启动使用同目录“启动焦炭开发验收.cmd”或EXE加`--data-dir <独立TEMP子目录>`；不得使用正式用户目录。启动到真实主应用，开发标识直接可见；关闭保留同一标记TEMP库，重开可查历史。

### 验证状态与未决边界

视觉修复受影响定向69 passed、保存失败预览修复定向56 passed；分组有重叠，不相加。首轮主应用保存载荷展示遗漏property字段、readiness负例被tests/conftest默认关闭及清理日志句柄的问题均曾真实失败，已补显式适配、严格readiness=True与日志关闭后重跑通过，未放宽断言。完整源码回归仍按本机原日志/远端精确SHA终局核对。

2026-11-18 00:36:36（UTC+8）重新核对精确f4的[Numeric v1 44127187683](https://github.com/adgo07/ECQuota-Insight/actions/runs/44127187683)与[N01-A 44127187637](https://github.com/adgo07/ECQuota-Insight/actions/runs/44127187637)均completed/success；[PR Gate 44127187764](https://github.com/adgo07/ECQuota-Insight/actions/runs/44127187764)仍in_progress。此前启动的本机literal full suite仍运行、尚无终局；期间HEAD推进，不将其冒称f4精确全套通过。后续CI终局另补，当前不提前宣布全套通过。

原生及Word视觉仍OPEN：本轮统一Computer Use inventory仅见Codex/Explorer、未见焦炭；Word isRunning=false。此前903.2s Word请求由父中断后返回aborted，不是超时或自动审核拒绝。没有取得本最终EXE的真实表单操作、Word/WPS实开/分页证据；不以离屏截图、DOCX生成或机器自检替代。正式安装/升级/卸载、整标准Stage D仍OPEN。引用原文和匹配既有公钥的私钥已核实具备，不沿用旧“缺失”阻断；V1.1映射审核稿尚未收到Owner批准，未正式签焦炭包或改PIN/生产data/正式支持集。整体仍MAPPING、正式评价仍仅GB29446；水泥Stage D暂缓，PR41保持草稿，不合并、不发布、不tag。
