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
