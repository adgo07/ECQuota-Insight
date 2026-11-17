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

## 保留事项

整标准仍MAPPING、现行批准映射无；正式评价范围仍仅GB29446。签名私钥缺失不通过换公钥处理；正式规则/签包/PIN/交付须成套。水泥IMPLEMENTED / Stage D OPEN保留，RS05 IN PROGRESS，0.2.0未发布。本报告不授权合并、发布或tag。

Knowledge capture：无新增知识文章；引用核验缺口记于本报告，未将尚未核齐原文的取证问题冒充新增标准歧义。
