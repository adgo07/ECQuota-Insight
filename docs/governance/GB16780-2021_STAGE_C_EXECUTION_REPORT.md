# GB 16780—2021 Stage C 实施记录

日期：2026-10-29。状态：**Stage C源码IMPLEMENTED；自动验证如下；未完成Stage D，不宣称SUPPORTED，未发布**。

## 1. 平台 / Contract 预检查

| 检查 | 结果 |
|---|---|
| 业务仓及实施基线 | origin=https://github.com/adgo07/ECQuota-Insight.git；独立checkout，已fetch并快进至main `b538ac6729d39eafbb6903d1ecfbb1cd94a26d1e`，远端默认main |
| Frozen锁 | platform-lock.json仍为中央 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`，未升级 |
| 相关Frozen | Architecture2.1；Numeric Contract、Profiles、Conformance v1；Unit/Record/qzpack仍DRAFT |
| MUST | Decimal28、ROUND_HALF_EVEN、全值比较、声明Profile并独立于ambient；结果保留Numeric/Calculator/Rule身份；历史记录不重算 |
| MUST NOT | 不引入float权威值、全局epsilon、隐式业务修约、显示值回流；不改冻结V1.2、不把ACTIVE指南当Frozen |
| ACTIVE读取 | 已核中央origin，按origin/main@a389ac1的GUIDE_INDEX路由读取标准开发指南、交付规则、UI指南v0.2、产品规格及适用验收清单；Frozen另按locked SHA读取 |
| Standard Issue | 是：ECQ-STD-GB16780-001与003；内部解释按冻结V1.2，不声称官方勘误 |
| 冲突分类与中央修改 | 当前未发现需变更中央Contract的事实；本轮不修改中央公共Contract，既有registered deviations保持 |
| 软件解释是否变更 | 采用已批准V1.2修复旧工程规则差异；不新增标准解释，额外防误录边界明确标识 |

Owner已批准[Stage B设计](../GB16780-2021_StageB_软件接入设计.md)及其§9修正并授权Stage C。生产正式支持仍仅选煤；水泥在测试实例注入许可。RS05=IN PROGRESS、产品闭环PARTIAL；Excel新工作簿延期。

## 2. 参数来源核证

- 水泥2021原文SHA256 `c50768dbca219aeee201a2ef9a79093a2b8e1d384560b31de045aa2cef843a5c`，PDF3/正文1页§2：GB/T2589不注日期，适用最新版本含修改单。已提取文本并视觉复核原页；未改原文。
- [国标官方登记](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=53D1440B68E6D50B8BA0CCAB619B6B3E)确认GB/T2589—2020现行、2021-04-01实施，故不沿用旧2008版29307。
- [发改委官方技术文件](https://www.ndrc.gov.cn/yjzxDownload/20220726fj6.pdf)实际47/正文45页明确援引GB/T2589—2020的29307.6 kJ/kgce，已文本与页图复核；下载文件SHA256 `2c5db9a3f87c16318b630e9fac22ac0fa3783b1021e499b54cd93a2def800220`。它是官方技术引用证据，并非GB/T2589标准原PDF。Rule/快照固化依据，不让用户逐次填写来源。

## 3. 实施与验证

实现、定向测试、Numeric/N01-A与完整回归的真实结果见下文；不把旧选煤Candidate的证据平移到水泥。未构建新EXE或安装包。

Stage D若需要原生实包，将在功能分支另建最小可审candidate-only激活提交，锁定干净源码SHA和包身份，不使用生产隐藏环境开关；完成实测后由设计负责人审是否保留激活变更。不自动合并或发布。

## 4. DSL能力及r1差异核对

| 项 | 已实施设计 |
|---|---|
| 既有DSL | sum/add/subtract/multiply/divide/per_unit表达式（2）～（9）及单位转换；piecewise表达海拔条件；ThresholdSet与Condition表达五指标阈值与四模式。固定公式及阈值仅存JSON，不重写公共Engine算术 |
| 最小扩展 | 可选计算节点及cement_details；Python负责合法图/拓扑、动态燃料明细组装、同产品分摊审计、局部依赖错误、结果封装及保存控制。旧模型无这些字段时保持序列化形状 |
| 对象 | r1的三个分离product及DIRECT/per_unit泛化改为单线cement对象和四生产模式；原五个indicator稳定ID保留 |
| 双修正 | r1的(94+配比修正)K改为已批准94K+配比修正；g/100只用于实际能耗公式，阈值仍用g−75 |
| 原始明细 | 动态燃料量/低位热值；P_sh与P_shx独立；余热源扣；两tce乘1000与两kW·h源扣一次；Q_BM参数来源随节点trace保存 |
| 结果 | 五指标独立，W_s只作中间量，无总等级或企业属性符合性；局部缺失可预览，全部适用项完整后Application才保存 |
| 分摊 | 同产品原量、参与线产量、公式、分母、派生量及Decimal28残差保留，不隐式末线补差；普通残差不阻保存，结构/统计边界错阻正式保存 |
| 历史保护 | r1历史snapshot只读、不重算；默认生产范围不扩大，水泥正式路径仅测试实例注入 |

上述为实现差异核对，不把代码存在等同于Stage D通过；最终测试与原生候选证据另记。

## 5. 当前随包与源码身份（尚非水泥Candidate）

实施前已核当时PIN包 `2026.10-published.5`、package_id `gb29446-r3-from-2026.10-published.4`：文件SHA256 `9547e8214124cd76e999c2949dcdcf45738282a56cc0d725df08cea2a49fa2b5`与当时PIN相符；只读取随产品公钥完成Ed25519 manifest验签，通过；包内sources成员为0。该包内水泥仍为r1，定义成员SHA256 `a318add38b0e8650414f1ac332bd0f976f367f14f6c7d054c5ab89c31a2d7ecf`。

上述.5是实施前父包，已留作只读历史夹具。本轮按既有Ed25519流程同步为 `2026.10-published.6`（`gb16780-r2-from-2026.10-published.5`），大小134262字节，SHA256 `d5ff370d3728ad3dda2589ed72bc9c693425208084ed96d45ad1d036c91afa51`。随产品公钥验签、manifest全成员hash/size及源定义一致性均通过：48项标准、765条规则、0个sources；仅水泥定义r1→r2，其他47定义及corrections共48个内容成员逐字节不变；manifest和signature随之变化。同步catalog仅水泥revision及library-index对应源hash。私钥未复制入仓。

这是源码配套规则库同步；未完成candidate-only激活或构建水泥EXE/安装包，不能称作水泥Stage D实包验收；普通生产白名单仍仅选煤。

## 6. 验证环境

最初根目录venv仅确认pytest8.4.2可启动，后续UI定向因缺项目声明依赖python-docx而收集失败；这不是业务断言失败，不能当测试通过。未向根venv补装。随后获授权在本独立clone的 `.venv` 创建Python3.13.3隔离环境，按 `requirements.lock` 安装完整锁定依赖成功；以下受影响测试与完整回归均使用该环境及显式clone/src路径，不把旧环境数目当最终汇总。

## 7. 本轮原生验收限制与下一阶段

指定Astra low验收者仅完成computer-use应用/窗口清单读取，确认设备已安装Microsoft Word。尝试取得Explorer与Word应用控制时，各一次返回“Computer Use app approval timed out”（每次约300秒）；未向应用发送输入、未启动source harness、未打开Word样例，也未生成原生截图。此为工具应用批准超时，不能写成软件验收失败、没有Office或原生通过。四模式实际界面、保存后重启读取、Word分页/排版均保持待验；本轮不重复申请应用控制。

本轮执行范围优先Stage C源实现、自动验证和可审PR，不要求立即交EXE/安装包。含r2的规则库已作为必要派生产物同步；candidate-only激活、EXE/安装包构建及Stage D另在下一阶段取得独立证据后审查；当前不执行激活，不自动merge/release，不扩大主线正式评价范围。

## 8. 自动验证证据（当前工作树）

独立clone `.venv/Scripts/python.exe`，Python3.13.3、pytest8.4.2、python-docx1.2.0、PySide6 6.10.1，均按requirements.lock安装exit0；显式 `PYTHONPATH=<clone>/src` 后打印的 `uebench.__file__`确认为本clone源码。Qt使用offscreen，临时数据隔离到clone/tmp。根venv未改。

统一最终定向已exit0：**141 tests，0 failures、0 errors、0 skips，290.803s**（XML计数）。模块为 `test_gb16780_v12`、`test_gb16780_presentation`、选煤Word、UI family baseline、Engine、Excel、Frozen Numeric v1 Conformance与N01-A migration evidence。原始日志/XML：`tmp/stagec-verification/targeted.log`、`targeted.xml`。

随后执行一次literal full suite（compileall成功；`pytest -vv -ra -p no:cacheprovider --basetemp tmp/stagec-verification/full --junitxml tmp/stagec-verification/full.xml`）：**1341项，1272 passed、7 failed、62 skipped、0 errors、0 xfail，7296.69s**。61项skip因未设置Candidate产物目录、1项因Windows不能创建目录符号链接，无其他skip。完整证据保留full.log/full.xml。这是修正前完整结果，修后仅运行受影响项，不声称本地最终树完整重跑通过。

独立只读审查者已核r2公式/阈值/四模式、局部依赖、输入守卫、分摊边界、Application保存、默认范围及历史serializer兼容，当前静态结论为no-blocker；其未运行full suite，不能把该静态审查写成自动或原生验收通过。另核V1.2冻结映射Git-clean且未改内容，g仅0..100物理范围，P_H无虚构max、由协调器要求>0，有效阈值顺序校验已实施。

### 首轮完整回归发现的适配缺口

首轮以下7项失败均保留原始full.log/XML。不以141定向通过替代全套，也不将修后定向写成修后重跑完整回归：

| 失败用例 | 分类及最小处置 |
|---|---|
| all_scope::every_scope_standard_has_at_least_one_source_backed_rule | 旧来源断言假定全部reference均为本标准；水泥r2合法2019技术参考触发。仅水泥精确校验已核file/hash/page/C1/C3/非现行标记，仍要求2021正式主来源覆盖；其他标准严格断言保留 |
| all_scope::every_published_indicator_runs_in_direct_entry_smoke | 旧通用smoke假定所有标准允许DIRECT；按批准Q4为水泥新增DETAIL真实原始数据smoke/边界，不跳过水泥、不恢复DIRECT |
| delivery_scope::current_signed_package_matches_explicit_bundled_scope | 源r2与现行签包r1不一致；保持门禁，依既有流程只替换水泥定义、重签标准库派生产物，正式支持不扩张 |
| delivery_scope::sixteen_drafts_do_not_enter_bundled_or_formal_scope | 同上，一致性检查在64源/48随包/16草稿场景同样发现水泥差异 |
| first_batch::every_first_batch_indicator_has_sources_and_boundary_grading[GB16780] | 旧DIRECT测试入口不适用；改水泥DETAIL五指标逐级T−0.01/T/T+0.01原始量真实推导，其他5标准原路径保留 |
| first_batch::representative_corrections_and_missing_level_are_exact | 水泥旧DIRECT及旧双修正假设；改DETAIL并按批准94K+1.20(g−75)独立期待，另明确DIRECT拒绝 |
| gb29446_record_lifecycle::two_real_processes_restore_ui_then_create_b_without_drifting_a | 首个seed子进程120秒TimeoutExpired，尚未打印RS02 payload；按原timeout单项复现并定位，不预判为环境、不增timeout |

第7项以同一隔离venv、原测试/生产代码及原120秒限制单独复跑，**1 passed in35.71s**，证据为lifecycle-repro.log/xml。未发现可复现业务断言失败，也未定位首轮超时根因，因此保留首轮失败记录，不将其归为已证明的环境故障。

签名修复按本轮实施授权执行，属于本轮源码变更必要的派生产物一致性，不是水泥正式支持或EXE Candidate放行。实际父/新包均48项、765条，水泥r1/r2均5指标。

完整回归最慢项（XML单项秒数）：旧规则不兼容提示134.422、跨进程生命周期120.370（超时失败）、保存数据损坏探测115.931、UI实际尺寸size3 83.353、size0 79.076；本轮未改性能或放宽测试超时。

### 规则库切换后的真实生产门禁缺口

切换.6后首次受影响定向收集130项，结果**115 passed、6 failed、9 errors，180.04s**（fixed.log/xml）。新失败/fixture error均源于应用层标准包校验仍要求所有引用与主标准号/file/hash完全一致，拒绝水泥已批准的2019技术辅助依据；因此真实安装、r1历史装新包、scope与自检被连带阻断。未通过测试绕过该门禁，也未回退源/随包一致性要求。按本轮实施授权作最小生产修复：集中验证批准辅助来源，限定水泥r2及精确身份，每指标仍必须有2021正式主来源，其他标准原严格约束不变；伪造hash/路径/条款、缺主源、其他标准借用辅助来源均须拒绝。修复后证据另列，不覆盖此失败记录。

分类为**LOCAL DEFECT**，无需中央Contract修改。`packages.py`集中来源校验函数保留其他标准的三字段严格匹配；水泥r2还锁定正式标准号、年份、主文件/hash及四个允许辅助的指标ID，2019辅助的标准标记、文件/hash、页、条款、table=None、note逐字段匹配且拒重复，粉磨指标不接受该辅助。没有新增模型字段、改变规则包字节或改写历史snapshot。独立审查者再次只读复核这两文件及13项真实签包场景，结论no-blocker；该结论不代替测试执行。

### 最终受影响验证

最终统一定向：**177 passed in282.33s，0 failures、0 errors、0 skips、0 xfail，exit0**；证据 `tmp/stagec-verification/final-affected.log`、`final-affected.xml`。包括水泥V1.2原始输入及真实已签r1历史快照、11项展示/Word投影、45个DETAIL阈值边界、双修正/DIRECT拒绝、全范围规则smoke与精确来源、delivery_scope、参数化包工具、.4→.5历史/.5→.6最小差异、release source真实验签安装、正式范围拒绝/零写入、选煤自检Golden、13项辅助来源正/负场景、既有包安全测试和文档卫生。原首轮7项在上述受影响复验及选煤生命周期原样单项复跑中通过；不宣称本地修后完整套件重跑。

源码状态为`IMPLEMENTED`，不扩正式白名单；Stage D原生、完整软件候选、安装/升级及Excel新工作簿仍待后续批准范围和证据。PR保持草稿，远端CI以该PR精确head为准，不能将旧head或旧Candidate证据计入本轮。

### 规则包与旧解析器兼容边界

只读提取实施父基线 `b538ac6729d39eafbb6903d1ecfbb1cd94a26d1e` 的旧models，在独立临时模块解析r2定义，明确复现 `cement_calculation_nodes: extra_forbidden`。这是旧源码schema不兼容的证据，**不是旧EXE实测**。因此.6只作本轮源码配套派生产物，不得单独导入旧安装版或称为兼容旧0.2.0 Candidate的发布物。

`minimum_app_version=0.2.0`沿用本仓当前仍未发布的开发版本；该字段无法区分历代同版本Candidate，不能据此证明兼容。后续交付须配套含r2解析模型的完整软件，并在正式发布时锁真实版本和候选身份；本轮不虚构0.2.1/release、不升级用户安装。
