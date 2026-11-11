# PR36/38整合实施

## 当前状态（覆盖下方阶段历史）

截至cbc85192137df5a669e602f58a2e7ac2c201775b，整合源码已完成：r3身份、两版r2历史只读兼容、完整保存事实报告、Excel早拒绝、精确辅助来源、源码ZIP自包含与两spec真实解包输入验证、TEMP独立开发入口、严格计算保存及无写入读回。下方“阶段1尚未完成”仅记录当时进度，不代表当前缺口。父已独立审核最终代码通过；尚未构建开发EXE、未完成该新EXE原生/Word验收，也未取得正式水泥签名包，不合并、不发布、不开放正式水泥支持。

测试身份分开记录：cc8a5202cb13b480f282ed4fd371517749e8a18a启动的受影响全组332 passed（work/consolidation-affected-final.xml）；cbc8519相对cc8仅构建时间字段对齐及历史燃料来源说明，cbc历史14 passed（work/consolidation-cbc-history.xml）；a2311bf工作树附带revision并集/source gate测试修正的44 passed（work/consolidation-targeted17.xml），该修正已纳入cc8。父对cbc独立复验stage_d/history/sourcezip/release_source共40 passed（父工作树parent-final.xml）。不将这些分组冒称最终源码完整全套；完整精确远端CI仍由父协调。full1已中断，不作为结果。

## 阶段1历史记录

平台 / Contract 预检查：起点8ec5e998ff5e5e4d4a4009ad14ef332c5add0dba；platform-lock仍锁定ee5feb0cc34dbd99790500fadd0c4c932e202a20。遵守Numeric Decimal28/HALF_EVEN全值比较，不修改中央Contract、冻结V1.2映射及Issue001/003内部解释。本轮为工程保护和身份修正，不改变业务公式。

整合采用PR38多线唯一写入模型，候选revision=3；两个旧r2结构不同，不能复用身份。PR38原候选原字节保存在tests/fixtures/gb16780/pr38-r2-unpublished.json，SHA256仍为1e9db2b766c4ce84c0e21d6c899481b86c0e009749f6f63de068544a1211cfa2。生产r1/PIN/.5、其他47项、公钥保持原样。历史原始快照只读兼容尚待实现，不以r3自动升级旧记录。

阶段1：Excel在load后、Workbook构造前检查request/result/standard三身份拒绝水泥；严格验包承接精确2019来源白名单，限定r3和四指标，按PR38实际辅助来源文字适配，要求2021主来源不缺失。Word同源视图补保存输入g−75百分点差。源码ZIP包含release/standard-packages和必需.gitattributes，不规范化已有签名包或定义字节。

定向验证：work/consolidation-targeted3.log，184项通过（核心、应用、候选隔离、源码ZIP、真实临时测试签名包来源正反例）；私钥仅合成测试即时生成，不替换产品信任根。初次默认TEMP权限错误已改工作区隔离TEMP；随后发现新旧引用字符串不同并按实际新候选修复。

未完成：历史快照读取投影；可运行隔离候选入口与真实新签包/EXE；源码ZIP解包构建输入验证；升级并集验收；完整回归。尚未推送、合并、发布或开放正式支持。


## 后续阶段与当前边界

1a353c1：g−75显示也使用局部Decimal28/HALF_EVEN；三身份Excel拒绝回归证明Workbook零构造/审计零调用/原文件不变；源码ZIP实际解包执行spec桩，核对真实entry/data/runtime_hook存在。41项通过，work/consolidation-targeted5.log。

78cc8e3/a054db5：四模式真实三JSON合成存档由未修改PR36 51771ef源码生成，provenance随fixture。历史原JSON哈希校验，模型字段若被改则拒绝借用原哈希；标准库旧15nodes可读取但不进入新计算器。SQLite get/query_page/Word导出、保存拒绝、原JSON不变及损坏隔离定向通过。旧r2与新r3不互相冒认。

22b32ac：新增独立run_stage_d_cement.py/uebench-stage-d.spec，复用正常上下文、正常主窗口与唯一计算器；独立入口只允许本进程TEMP内新空/标记目录，进程内ContextVar启用开发评价，正常SUPPORTED集合仍仅选煤。界面标题标开发验收、非正式发布；拒绝formal-release参数。固定可信煤包与明确r3开发注入不冒认正式水泥签名包。源码隔离自检实际成功，work/consolidation-dev-selfcheck.log；最终EXE尚未构建和复验。

父独立核验旧.5和.6均可用当前公钥验签；.6包内与PR36源码definition经旧只读模型默认序列化后完全相等，原JSON顶层差别不是已证明业务差别。并不因此让旧模型进入新模型计算。

只读签名位置盘点：当前PIN记载work/signing/development-private-key.pem不存在，work/signing目录不存在；历史构建/治理记录指向同一路径（另有历史G盘存档，不推定为当前受控位置）。未输出密钥、未替换公钥，也未据此声称全机无key。正式水泥签包仍须取得匹配现有公钥的授权私钥，独立开发EXE可继续。


真实旧库启动实测：从51771ef未修改源码安装真实签名.6，再以其真实EvaluationService创建合成r2记录；新源码默认create_context/readiness/reconcile显示NO_DOWNGRADE/INSTALLED_NEWER，保留旧.6（不降至.5），48项标准可列出、历史列表1项、get保留原哈希1bc58b423325d56e1763ca088144484f4fa2cf55593a249ae3cbda58d019ca77、只读报告5指标。原始日志work/consolidation-pr36-original-install.log及consolidation-pr36-new-startup.log。首次旧进程单独install后未对账的readiness阻断，经旧正常reconcile后成功，未绕过默认readiness。

开发自检补强：真实PIN身份与r3开发对象分开记录；只读readback使用sqlite mode=ro，不创建上下文、不对账/安装、不重写marker。自检独立预期表3=29/2级，另四项不适用，并记录三JSON原哈希、记录数、审计数；源码独立两进程smoke3/readback3成功。构建输出仅允许新空目录，不覆盖旧产物。完整full1启动后按父验收安排中断，不作为测试结果；改跑受影响全组/Numeric/选煤生命周期，最终精确HEAD完整CI仍待父协调。


受影响组实际结果：work/consolidation-affected1.xml，330 passed、0失败、0跳过（83.285秒），涵盖水泥核心/UI/应用/来源/历史/隔离、损坏记录/列表、选煤生命周期、Numeric正式及N01A。该轮运行过程中开发readback继续补强，不将结果冒认为最终提交的全套；开发补强另有5项定向通过。额外发布源码/正式工作流/支持门禁/历史组先43通过1失败（新增必需构建入口未同步旧源码门禁测试），精确同步测试后work/consolidation-targeted17.xml为44 passed。旧/新水泥标准库身份并集断言明确覆盖(r2,r3)，最新选择r3，不删除旧定义。完整CI、开发EXE实际构建和真包复验仍待父验收；正式水泥签包/Stage D/正式支持保持OPEN。
