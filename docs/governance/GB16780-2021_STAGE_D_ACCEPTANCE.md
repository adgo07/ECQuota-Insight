# GB 16780—2021 Stage D 候选与验收记录

日期：2026-10-29。状态：**验收进行中；IMPLEMENTED，尚未SUPPORTED，未发布**。

## 平台 / Contract 预检查

- 业务仓已实际核为`https://github.com/adgo07/ECQuota-Insight.git`，独立clone分支`codex/gb16780-v12-stage-c`，本轮起点`b52eea62fb5c50c948596f4e1000b1b13e873a85`；已fetch，默认main，`origin/main=b538ac6729d39eafbb6903d1ecfbb1cd94a26d1e`。实际构建提交及资产哈希另记，不能用文档提交冒充被测源码。
- `platform-lock.json`锁中央`ee5feb0cc34dbd99790500fadd0c4c932e202a20`，Architecture2.1、Numeric Contract/Profile/Conformance v1 Frozen；Decimal28、ROUND_HALF_EVEN、全值比较，不引入隐式修约/epsilon，不让显示值回流比较，不重算历史。
- 中央origin已实际核证并fetch；当前已合并`main@a389ac1de63c4f331f3b04e5e7b7a17ef02ed111`，按其GUIDE_INDEX读取标准开发、产品交付、UI指南v0.2/产品规格/适用验收清单；不升级Frozen锁。
- Standard Issue：是，`ECQ-STD-GB16780-001`与`003`；沿用冻结V1.2及批准软件解释，不新增或改写业务解释。当前未发现需要中央Contract修改的事实；既有REGISTERED DEVIATION保持。本任务不修改中央公共Contract。

## 候选专用激活

Owner授权继续Stage D；[Stage B §9.2](../GB16780-2021_StageB_软件接入设计.md)允许独立、可审候选激活。`run_stage_d_cement.py`是本分支spec显式采用的候选入口；正常`run_uebench.py`、正式registry及`data/delivery-scope.json`仍仅选煤。候选将同一个实例scope传入真实Application和原MainWindow，复用初始化、签包对账、Calculator、保存与Word；不使用隐藏环境开关、不另造算法。

候选必须显式`--data-dir`，resolve/junction解析及Windows大小写规范化后拒默认用户目录及其祖先/后代，拒已配置且有数据的用户目录，拒非空未标识目录。候选标记绑定实际resolved目录。运行时`candidate-runtime.json`记录精确构建身份、规则包及实际隔离目录；标题与水泥支持说明明确“Stage D验收候选，尚未正式支持”。同一隔离目录允许重启读回，不允许把现有真实用户数据直接交给候选。

版本仍为未发布的`0.2.0`开发版本；资产用`rc-<cleanSHA前7位>`及内嵌完整SHA区分。配套`.6`/水泥r2，旧0.2.0解析器不兼容，不能单独向旧安装版导入`.6`。`-FormalRelease`拒绝此候选spec。现有安装器沿用产品AppId，**只构建不执行**；安装/升级/卸载仍待安全环境验收。Excel新版工作簿不在本轮范围。RS05仍IN PROGRESS、产品PARTIAL、RS06未完成。

## 独立输入与预期矩阵

以下由独立验收者依据冻结V1.2与Stage B手算复核，**不是从Calculator输出回填**。Numeric均按全值。统计期填“2025年”，生产线“A”，同一期同线；基础A海拔1500m，Q_BM/燃料热值均29307.6kJ/kgce（燃料热值单位kJ/kg）。

| A原始字段 | 数值/单位 |
|---|---|
| 生产模式 | 自产熟料并生产水泥 |
| 自产熟料产量；水泥产量；本期水泥耗用熟料 | 1000t；1000t；750t |
| 熟料配比 | 75%（输入75） |
| 燃煤量；低位热值 | 100000kg；29307.6kJ/kg |
| 余热发电量；余热自用电量 | 12000；2000kW·h（净10000） |
| 熟料生产电量 | 50000kW·h |
| 协同处置燃料；替代燃料扣除 | 各1tce |
| 协同处置用电；替代燃料用电扣除 | 各1000kW·h |
| 水泥粉磨包装；混合材制备；石膏制备；辅助电量 | 20000；1000；1000；2000kW·h |
| 水泥制备燃料；制备工段电量 | 1000kgce；23000kW·h |

| 情形 | 独立预期及保存边界 |
|---|---|
| 自产A | e_sh=96.771/2级；W_sh=48/1级；E_sh=102.6702/2级；W_s=60中间量；E_s=80.95225/2级；W_sg=23/1级；五项完整可保存/Word |
| 部分外购A | 同五实际值/等级；式8必须用e_sh，错用E_sh会得85.37665，应为80.95225 |
| 仅熟料 | 只保留熟料链：煤96.771/2级、电48/1级、综合102.6702/2级；水泥及工段不适用，三项完整可保存 |
| 全外购粉磨 | 只填P_s=1000t/w_sg=23000kW·h，工段23/1级，其余不适用；一项完整可保存 |
| B：A只删w_sg | 其余四项完整，工段不完整；只部分预览；Application拒正式保存，Word不可用 |
| A双修正 | 海拔1600m、P_H=81060Pa、g=80；K=1.0102；水泥阈85.50/92.75/100.9588（错顺序101.0200），实际85.7908/2级；熟料3级综合118.1934、煤110.1118、电61.6222；工段34不变 |
| A四扣除均空白 | 煤98.771/2级、电50/2级、熟料综合104.916/2级、W_s=61.5、水泥综合82.6366/2级、工段23/1级；显式0同数值但原输入空白状态必须可区分 |

45点边界：每个三级上限T取T−0.01/T/T+0.01，用原始量产生指标，不直接填单位能耗。K=1、g=75、P_sh/P_s=1000t、余热/扣除均零；煤与熟料综合分别以燃料kg=1000x、电量0产生x，熟料电以w_sh=1000x、燃料0产生x；水泥综合以e_h=1000x、其他燃料与水泥电项0产生x；工段以w_sg=1000x产生x。阈依次煤94/100/109、熟料综合100/107/117、熟料电48/57/61、水泥综合80/87/94、工段26/29/34。按≤比较及“未达3级”共同软件标签验收。

## 本轮证据

以下保留各执行阶段真实结果；最终实包结论见下方rc-a89b2c1节。原生视觉、实际Office排版和安装均不能据源码或程序化证据宣布通过，不跨版本套用旧选煤Candidate结论。

候选激活首轮定向66项，65通过、1项新测试因错误导入另一测试模块失败（测试辅助导入错误，未触发业务断言）。修为本测试自带原始DETAIL请求后，新6项全部通过、0skip（15.193秒），含真实Application签包对账/水泥保存、UI导航、默认入口拒绝以及本机真实Windows junction拒绝。其他61项默认范围、水泥展示、架构与Source Gate在首轮通过。证据为隔离clone的`tmp/staged-targeted-1.log/xml`与`tmp/staged-targeted-2.log/xml`。未因入口修改重跑无关本地全套；原Stage C精确head的远端CI与本轮新head的CI分开记录。

版本一致性、开发清单（64源/16草稿）与签包范围校验（48随包/1正式）通过。已真实调用build_candidate.ps1的FormalRelease路径，按预期在构建前拒绝专用候选入口；未创建正式产物。构建复用现有流程并跳过重复全套，保留冻结EXE自检与Artifact Gate；干净SHA与实物结果后续补录。

## 候选专用程序化验收工具

`--acceptance-smoke`仅由候选入口提供。每次在已标识验收目录下新建UUID子目录，不覆盖已有GUI或上次验收记录；用真实签包对账、Application、Calculator、Repository与Word接口运行独立A四模式及双修正5条完整记录。预期常量来自上方独立复核。部分预览必须拒正式保存和Word。Word从已保存快照生成，程序检查标准身份、适用指标及必要海拔说明，不替代分页/视觉验收。

首进程记录输入、结果、规则三份原JSON各自SHA256，再结束其数据库连接。第二独立同入口进程`--acceptance-readback`使用SQLite`mode=ro`/`query_only`只读重开，逐字节核hash，并以保存模型投影报告；不构造Calculator、不进行标准包对账、不重算。验收检查全部显式异常，不依赖会被PyInstaller optimize=1删除的assert。输出`acceptance-smoke.json`与`smoke-readback.json`保留进程身份、实包身份、5条记录、Word路径/哈希和“视觉未验/安装未验”。

源码探针已真实通过：`tmp/staged-source-smoke/smoke-f1e5b59bf0d145b3be9996e9b0228599/acceptance-smoke.json`，首进程5708、独立只读进程19864，5记录/5 Word/部分预览拒绝通过；`frozen=false`且源码未嵌入build identity，不计作冻结EXE证据。冻结实包仍须另跑同探针，记录精确干净提交。

新增探针后最终定向14项全部通过，0失败/0错误/0skip，16.800秒：`tmp/staged-smoke-final.log/xml`。其中只读探针对故意改变的输入JSON拒绝并保持数据库原字节；`python -O`下失败守卫仍执行；真实Windows junction拒绝通过。旧61项定向和本轮14项各按实际执行记录，不冒称本地完整回归重跑。

独立只读复审确认当前候选隔离、默认选煤范围、Application/UI同实例许可、FormalRelease拒绝、smoke独立常量及只读快照关联链无阻断项；该审查没有运行测试，不作自动或原生通过证据。候选代码将按此状态锁定干净构建提交。


## rc-a89b2c1实际构建与冻结实包验证

干净构建源码为`a89b2c166214451bf6f6692099548979a4953483`、`source_dirty=false`；版本`0.2.0`开发候选，候选`rc-a89b2c1`，本轮不发布。按既有`build_candidate.ps1 -SkipTests`执行，未跳过版本/清单/来源门禁、冻结EXE自检或Artifact Gate；构建exit0。Inno编译成功（64.500秒），**安装器没有执行**。

配套包`.6`/水泥r2，package_id=`gb16780-r2-from-2026.10-published.5`，SHA256`d5ff370d3728ad3dda2589ed72bc9c693425208084ed96d45ad1d036c91afa51`。payload339文件、162835047字节，树SHA256`5895f61c747ae56e95f7f34f38f88d24679d0f8586b12f59ba9eb169898f0a64`。EXE既有冻结自检6/6，Artifact Gate63/63均通过；它们不是水泥原生界面通过的替代证据。

| 实物（本次隔离clone相对路径） | 字节 | SHA256 |
|---|---:|---|
| `dist/UEBench/UEBench.exe` | 12071870 | `7dccbabdeb839aef1d8ea35552e528c471b3f8f3040afe8b0e4a7bae7f2c61b5` |
| `dist/candidate-0.2.0/UEBench-0.2.0-rc-a89b2c1-win-x64.zip` | 72626664 | `66a4b8d5ee20745414de8c61b18fc4aa1100e2b8d778bc5a69ae5a12a1fcf7ee` |
| `dist/candidate-0.2.0/UEBench-Setup-0.2.0-rc-a89b2c1-x64.exe` | 49679197 | `8be190b243610d4dba4202b276a2c68d51d59c01aaeff2eceeed4bb7e9dbac14` |
| `dist/candidate-0.2.0/UEBench-source-0.2.0-rc-a89b2c1.zip` | 9595960 | `40d925f338d600006ededef2438d3ae94dd3b2b186877230d22f60cde9fe8aca` |

对**实际便携ZIP重新解包出的EXE**运行`--data-dir <新验收根> --acceptance-smoke`，exit0，`frozen=true`，嵌入源码/候选/.6身份均相符：四模式与双修正5记录/5 Word、部分预览拒存/拒Word通过；第二独立同EXE进程23636→13048以SQLite只读重开三份原JSON、规则关联hash及保存快照投影全部通过，不重算。原始输出在本次clone的`tmp/staged-frozen-smoke-rc-a89b2c1/smoke-f8002de0b9514960bdd0764b360909b4/`，含5份`水泥-*.docx`。Word标准标题/适用指标/海拔必要说明程序检查通过；**分页和真实Office视觉仍未验**。

可审证据：[构建身份与资产](evidence/GB16780_STAGE_D_rc-a89b2c1_artifacts.json)、[冻结自检](evidence/GB16780_STAGE_D_rc-a89b2c1_self_check.json)、[冻结水泥smoke](evidence/GB16780_STAGE_D_rc-a89b2c1_frozen_smoke.json)。构建日志为本次clone的`tmp/staged-build.log`；这些本地路径仅用于追溯当次环境，不是跨机器固定入口。

原生启动方式：从本候选便携payload运行`UEBench.exe --data-dir <新的空验收目录>`；标题明确“水泥Stage D验收候选 · rc-a89b2c1”。不直接双击同AppId安装器，不把旧安装版与新`.6`分开混用。本节为a89b2c1的实物证据；后续仅补报告的提交不自动变成构建输入，不需因治理补录重打包。


## 原生目标尝试与当前出口

指定Astra验收者已用独立目录启动本次候选EXE，进程PID25296；工具无法枚举对应应用窗口，未取得可验证的窗口句柄，未完成视觉/交互验收。候选进程按Owner交接保留供用户查看，不将“进程存在”记为四模式UI链通过。此前Word截图capture超时及点击geometry不可用；不据工具失败断言没有Office，也不把程序化DOCX检查当作Word分页通过。

当前分别为：**候选构建/Artifact Gate/冻结基础自检/冻结水泥计算-保存-只读快照-Word生成PASS；原生UI交互/Word视觉与分页/安装升级卸载待验。**安装器仅构建，未运行，未覆盖用户安装或真实数据。Stage D未完成，水泥仍IMPLEMENTED，尚未SUPPORTED；RS05 IN PROGRESS、产品PARTIAL、0.2.0未发布，Excel新工作簿延期。PR36保持草稿，不自动合并/发布。


候选源码a89b2c1远端CI查询时：[Numeric v1](https://github.com/adgo07/ECQuota-Insight/actions/runs/40858839532)与[N01-A](https://github.com/adgo07/ECQuota-Insight/actions/runs/40858839519)已success；[Pull Request Gate](https://github.com/adgo07/ECQuota-Insight/actions/runs/40858839552)仍in_progress，不记成全套成功。后续仅文档/evidence补录的head与该构建源码分开识别；新head若CI仍运行按真实状态交接，不为等待重复跑本地完整套件。最后文档卫生6项通过，`tmp/staged-doc-final.xml`；本次未改打包输入或重建实物。
