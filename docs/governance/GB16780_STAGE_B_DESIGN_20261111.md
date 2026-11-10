# GB 16780—2021 水泥接入 Stage B 设计

日期：2026-11-11。状态：**Stage B 已由父Agent独立审查通过（设计提交55d09fa）；Stage C 分块实施中，尚未Stage D验收、未开放正式评价。**

本文件是 RS06 的专项设计，不是第二份总体路线。Owner 已批准启动水泥并跳过用户试用前置；不重复请求批准既定业务口径。唯一业务权威为 [V1.2 冻结映射](../../standards/mappings/GB16780-2021/标准映射表_V1.2_修订稿.md)，不修改、移动或重命名其正文。设计审查通过后进入 Stage C；Stage D 前不声明 SUPPORTED。

## 1. 平台 / Contract 预检查

| 项目 | 结果 |
|---|---|
| 实际仓库 / 起点 | 已核 origin=https://github.com/adgo07/ECQuota-Insight.git；fetch 后 origin/main=`298a966de8cec03f02daa646108911007c281aa3` |
| 隔离分支 | `codex/cement-integration-20261111`；独立工作树，不修改主工作树、旧包、真实数据或已安装产品 |
| platform-lock 文件 SHA256 | `3c1708fa1f619235310b31b9aadb5eed4ea6330c644af534c09050ae7fe67d4a` |
| Frozen 读取版本 | 中央 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`；Architecture 2.1、Numeric Contract v1、Profiles v1、Conformance Vector v1 |
| ACTIVE 读取版本 | 已核中央 origin=https://github.com/adgo07/Qingzhou-contracts.git；fetch 后 main=`829853a943c421e0b9864d84f3d94970d2ddf688`；GUIDE_INDEX 路由的标准开发指南、交付 Policy、UI v0.2、家族规格及验收清单 |
| Mapping 原字节 SHA256 | `43d75b9724d8105ca27f0b3eeadd41de7dce1f92fa26965306c69cad5c17575c` |
| MUST | 同一 Domain 业务链；Decimal28 / ROUND_HALF_EVEN；正式 full-value exact；数值无损入口；来源、规则、计算器版本及中间结果可追踪；历史快照只读 |
| MUST NOT | binary float 权威入口、隐式修约、默认 epsilon、显示值回流、ambient context 改正式结果、修改 Frozen lock、自动重算历史 |
| Standard Issue | 有：ECQ-STD-GB16780-001（内部决定 RESOLVED）、003（PROVISIONAL）；仍无官方勘误/组合公式解释 |
| 是否改变既有软件解释 | 采用已批准 V1.2 内部解释，修正旧实现差异；不新增业务解释，不冒称官方确认 |
| 冲突 / 分类 | 旧水泥计算与批准映射不符为本地业务实现差异（LOCAL DEFECT）；D-ECQ-002～006 保持 REGISTERED DEVIATION；未发现 CENTRAL CONTRACT GAP |
| 是否改中央 Contract | 否；Unit / Record / qzpack 仍 DRAFT，不以水泥任务宣称 adoption |

RS05 仍 IN PROGRESS、参考标准产品闭环仍 PARTIAL、0.2.0 未正式发布。既有 Win10、其他 DPI/跨屏、真实离线、IME、安装器及 Word/WPS 等未验环境事项保留原证据边界；新水泥验收不自动关闭它们。Excel 正式流程继续延期，不生成新工作簿。

## 2. 已核差异与处置

| 当前起点 | V1.2 要求 / 设计处置 |
|---|---|
| 水泥 r1 有 cement、clinker、cement-preparation 三个独立产品入口 | 一次评价覆盖生产模式与其全部适用指标；新 r2 使用单一 `cement-assessment` 产品，五项指标维持既有稳定 indicator ID；旧产品只存在于保存的 r1 快照，不自动映射重算 |
| 多项 DETAIL 为通用总能耗/等价产量 | 水泥专用 Domain calculator 落实式（2）～（9）、四扣除、余热、独立 P_sh/P_shx/P_s；不用通用能源表冒充原始燃料链 |
| 3级为 `(94+1.20(g-75))*K`，旧测试断言该式 | r2 改 `94*K+1.20(g-75)`，原独立业务期望取代旧算法测试；001/003 → 规则 → 测试完整追踪 |
| 全局输入校验失败导致所有指标不完整 | 水泥先按依赖图计算独立节点，错误只传播到依赖节点；表3可独立完成，缺压力不抹去实际值 |
| evaluate 计算后直接 save | Application 统一检查 DETAIL、适用指标集合、每线完整性及结果与请求一致性，未完整绝不调用 repository.save |
| Result 无生产线身份 | 增量可选行身份/角色字段，不改数据库表；一请求/一记录包含多线结果，无企业总等级 |
| report_view 只接受 GB29446，Word/详情固定选煤字段 | 按标准分派报告视图；新增水泥类型和渲染分支，保留选煤现有视图及两页签壳 |
| 仅选煤在 evaluation_support / delivery-scope 正式集合 | 开发和验收前保持不变；Stage D 证据闭合后才以最终受审提交开放水泥；其余46项不扩大 |
| 配套签名包仍含水泥 r1 | 最终阶段以当前可信 .5 签名父包仅替换水泥，重新签名；其他47项定义及无关corrections原字节不变；如需新增水泥corrections，只允许必要的水泥来源/解释变更并单列差异 |

不改 `scope-63` / `scope-65` 开发历史快照。`data/definitions/` 继续为唯一机器定义编辑源。

## 3. Canonical 与记录设计

### 3.1 请求

继续用 EvaluationRequest 外围：日期、standard_id、product_id、DETAIL、企业名称、周期、备注。增量增加默认空列表 `cement_lines`、`cement_shared_energy`；旧 JSON 缺字段正常读取，不做数据库 migration。其它标准拒绝误带水泥专用数据。水泥新 r2 要求 `product_id=cement-assessment`，旧 r1 请求不能经新入口冒充 V1.2。

每个 CementLineInput：稳定 `line_id`、可读 `line_name`、四态 `production_mode`、`inputs: dict[str, InputValue]`、`fuels: list[CementFuelInput]`。每个燃料含行标识、名称、`mass_kg`、`low_calorific_value_kj_per_kg`；所有权威数值以 lexical text/Decimal 规范化，拒绝 float/NaN/Infinity。可缺失值保留至依赖校验，不能由 Pydantic 全局必填提前牵连其他指标。

| Canonical key（每线） | 单位 / 条件 |
|---|---|
| site.altitude_m / site.pressure_pa | m / Pa；四项动态等级需海拔；严格>1500时压力>0，≤1500时K=1，不估气压 |
| clinker.production_t / cement.clinker_consumption_t / cement.production_t | P_sh / P_shx / P_s，t；各自独立，不推断相等 |
| fuel.standard_coal_heat_kj_per_kgce | Q_BM，kJ/kgce，>0；使用有依据的参数，不能静默用现存通用折标系数替代 |
| clinker.electricity_kwh / heat.generation_kwh / heat.own_use_kwh | w_sh / w_he / w_0，kW·h；非负，余热净量不能为负；无余热由用户明确填0，不因缺失猜0 |
| deduction.co_processing_fuel_tce / deduction.alternative_fuel_tce | tce，非负或空白 |
| deduction.co_processing_electricity_kwh / deduction.alternative_fuel_electricity_kwh | kW·h，非负或空白 |
| cement.clinker_percent | g，%，输入75表示75%；物理比例0～100，阈值用百分点，式8用g/100 |
| cement.grinding_packaging_kwh / cement.additives_preprocessing_kwh / cement.gypsum_preprocessing_kwh / cement.auxiliary_kwh | w_fm / w_m / w_g / w_fz，kW·h，非负 |
| cement.preparation_fuel_kgce / cement.preparation_electricity_kwh | e_h（kgce）/ w_sg（kW·h），非负 |

四扣除空白原样保留（None/未提供）；计算额外扣量取0，展示“未填（无需软件额外扣除）”，不同于用户明确输入0。界面统一 placeholder“若已扣除，则不填”，无新增确认框/涉及开关。原始量已净扣时不再填对应扣量；软件只验证可证明的负数、超额、重复行身份和单位冲突，不能凭数值自动认定同一来源重复扣除；同源、同期、同线边界说明可就近查看。

### 3.2 模式 / 适用矩阵

| 模式（稳定值） | E_s | E_sh | e_sh | W_sh | W_sg |
|---|---|---|---|---|---|
| 自产熟料并生产水泥（integrated） | 正式 | 正式 | 正式 | 正式 | 正式 |
| 部分外购熟料生产水泥（partial_purchase） | 正式 | 正式 | 正式 | 正式 | 正式 |
| 仅生产熟料（clinker_only） | 不适用 | 正式 | 正式 | 正式 | 不适用 |
| 全部外购熟料粉磨站（purchased_clinker_grinding） | 不适用（本轮不展示可选扩展参考） | 不适用 | 不适用 | 不适用 | 正式 |

纯外购式7的W_sh=0、式8的e_sh=0是映射保留的参考算法；本轮不展示非必要的扩展E_s参考等级，E_s输出NOT_APPLICABLE，仅表3进入正式完整性集合。四个窑扣除对该模式不适用，不能传入表3。若用户/API给不适用扣量非零，提示移除且阻止相应请求形成有歧义的正式记录；不以UI隐藏代替应用检查。W_s永远是中间量，不新增阈值或第六项等级。

### 3.3 多线与共用量

一次请求包含一条或多条线，每线可选其生产模式，独立输出五项状态；周期为请求级共享，不跨期。单线也使用同一结构，不保留第二套简化算法。

共用量录入使用有限、业务明确的目标：熟料燃料、熟料用电、水泥辅助用电、水泥制备工段用电。燃料仍为原始m_i/Q_i行；电量为kW·h。每个共用项记录唯一id、目标、明确参与线id列表；分摊分母由目标自动选择P_sh或P_s，按各参与线产量/合计产量分摊，不让用户自由选比例。分子与分母缺失/无效影响该共用项所有参与线的依赖指标，不影响无关指标。不能用P_shx代替产品产量；纯外购线不参加熟料目标。共用量只能在此录入一次，分摊后合入各线对应原始量；不向下游再次整体扣减。

计算顺序固定为 `shared_amount * (line_output / sum_outputs)`，均在Profile上下文。保存分摊原量、参与集合、分子/分母与每线全值；不修约到显示位数、不给最后一线强行补差。有限Decimal尾差不改各线正式结果，守恒审计与业务阈值比较分开。共享燃料先分摊实物量再进入同一燃料式；不引入无依据的通用折标捷径。

### 3.4 结果 / 历史版本

在 IndicatorResult 增量加入可选 `line_id`、`line_name`。`indicator_id`维持五项既有值；唯一性键为(line_id, indicator_id)。EvaluationResult.results 为按线顺序展开的条目，避免新建数据库或企业聚合等级。INCOMPLETE 对应无法判定；NOT_APPLICABLE 不计缺项；NOT_QUALIFIED（未达3级）是完整有效结果。

根结果保存 `calculator_version=gb16780-calculator-v1`、`numeric_behavior_version=gb16780-v1.2-full-value-v1`、r2及既有Numeric身份；每项trace含节点值/扣前扣后/来源。新规则corrections记录Mapping路径与SHA、001/003及2019参考属性；结果形成后按现有三件快照保存request/result/standard，不从Markdown运行时解析。

旧r1产品与旧数值按保存快照只读显示，明确未采用V1.2，不补造新中间量或新规则身份。新r2历史在当前库升级/计算器禁用时仍可查看及导出；只用所存快照。记录列表一行代表整次评价，详情按线分区；不拆成可部分保存的多条记录。

## 4. Rule / Calculator 与依赖

通用Engine仅在已确认标准身份及r2采用标识后分派 `domain/gb16780.py`，仍由其外层Profile context支配。保留其他标准原校验和DSL，不全局重写输入验证。水泥Calculator以有版本、纯Domain输入输出契约处理燃料/生产线/依赖；JSON保存五项阈值、名称、条件、正式及软件解释来源。阈值表达式仍由现有ExpressionEvaluator执行，不在UI/Word再写算法；复用现有grade能力（如须抽取，仅作等价私有工具提取并回归）。

固定顺序（与V1.2 §9～18一致）：

1. H = Σ(m_i×Q_i)，F = H/Q_BM（扣除总量审计），E_he = 0.1229×((w_he−w_0)/P_sh)。
2. e_fc = 1000×(两个tce合计)；e_sh,before=H/(Q_BM×P_sh)−E_he；e_sh=e_sh,before−e_fc/P_sh。
3. w_fc=两个kW·h合计；W_sh,before=w_sh/P_sh；W_sh=(w_sh−w_fc)/P_sh。
4. E_sh=e_sh+0.1229×W_sh；此后不再扣余热/四扣量。
5. w_s=w_fm+W_sh×P_shx+w_m+w_g+w_fz；W_s=w_s/P_s。
6. E_s=e_sh×(g/100)+e_h/P_s+0.1229×W_s（部分外购同样e_sh，绝非E_sh）；W_sg=w_sg/P_s。
7. K=1或1.179−0.211×(P_H/101325)；L1/L2只g修正，L3=94×K+1.20×(g−75)；熟料三项仅L3乘K，表3不修。

| 输出节点 | 缺失/错误传播来源 |
|---|---|
| e_sh | 燃料m/Q、Q_BM、P_sh、余热、燃料两扣除、对应共用分摊 |
| W_sh | w_sh、P_sh、电量两扣除、对应共用分摊 |
| E_sh | e_sh和W_sh |
| W_s | W_sh（纯外购常量0）、P_shx、P_s、四项水泥电量 |
| E_s | e_sh（纯外购常量0）、g、e_h、P_s、W_s |
| W_sg | w_sg、P_s、对应共用分摊；与窑扣除/海拔/压力无关 |
| 表1/表2等级 | 该指标实际值、海拔及必要压力；E_s还需g；缺压力保留实际值但grade INCOMPLETE |

负量、燃料超额、净煤耗/净电耗为负、净余热为负、零分母、无效单位阻断相关节点。仅以P_H>0及阈值顺序校验处理气压，不增加无来源“正常气压范围”；修正后阈值不有序则相关等级无法判定并解释，不夹紧K、不默默回退。燃料列表无行是缺失，不当作零燃料；明确零用量行可表示本期该燃料为0。

## 5. 应用层预览与保存

`preview`不写库；水泥只接受DETAIL（连预览也不允许使用DIRECT生成误导的批准链）。`evaluate`保留范围、配套库readiness及日期门禁，水泥再检查DETAIL及r2采用身份，计算一次后执行完整性策略：每线适用项集合必须与规则/模式匹配、无重复/漏项，actual和最终阈值有限、grade为1/2/3/未达3级；NOT_APPLICABLE仅允许在模式规定位置。

全部完整才调用一次现有repository.save并从evaluate正常返回；不完整时抛出专用 `IncompleteCementEvaluationError`，携带 `preview_result`，明确表示正式评价失败且未保存（无记录落库、无保存审计）。UI捕获该明确异常展示“部分预览，尚未生成记录”，关闭查看记录/导出动作；其他调用方收到失败而不会误认为保存成功。`preview`仍正常返回部分结果且永不保存。新建页不显示临时evaluation_id作为已保存id，不靠“结果有id”猜保存成功。既有evaluate成功返回EvaluationResult接口保留，非水泥调用语义不变。禁止先preview再evaluate导致两次权威计算/两次ID。

开发阶段先通过真实Domain/preview和使用受控测试仓库+测试中patch正式范围测试Application分支；生产范围常量、readiness不提供临时开关、环境变量或隐藏绕过。受控测试patch仅证明尚未开放的受测路径，不宣称已支持。候选包原生验收可在待合并的最终开放提交运行，通过前不得合并为正式支持；失败则返修并保持未验收状态，不能删除失败证据。

## 6. 页面、标准库与Word

复用当前AppShell、导航、字体/间距/滚动与记录页。新增独立 `ui/gb16780_form.py` 水泥表单，由main_window按标准分派；不复制整个MainWindow。顶部基本信息，随后生产线列表/当前线明细（模式、产量、燃料、熟料用电/余热/四扣除、水泥用量），可选共用系统分摊区，底部结果按线五项表。按模式隐藏无关输入并清理/校验不适用旧值；切模式、增删线或改输入立即作废旧结果和导出状态。所有Decimal用文本输入，保留原始精度及空白。

计算按钮“计算等级”，附近短说明“全部适用指标完整时自动生成记录”；部分结果明确显示缺项及未生成记录，完整则提供查看记录和“导出报告（Word）”。不新增手动保存/审批/确认步骤。不输出熟料总等级、企业建设属性、限定/准入符合性。完整结果表显示指标、实际值、等级、有效阈值，不适用项清楚标示。关键错误内联且可定位；背景说明以可点击/键盘打开的帮助收起，不把单位/缺项/保存影响藏入气泡。

标准库现有五列/三分区保留；映射确认与软件支持分开。r2待验收仍未开放，不因为标准随包、Mapping批准或Calculator可运行开放入口。正式范围变更须同时更新evaluation_support、delivery-scope、软件支持说明与真实标准库测试。

新增 `CementReportView`（按线、指标、输入、分摊、依据组成），`build_report_view`按标准分派，原GB29446 ReportView保持接口兼容。RecordDetailPage仍严格两页签：“基本信息与结果”按线结果；“输入数据与计算依据”显示原始明细、四扣除的未填/0、扣前后、W_s、K/g、分摊及必要解释。Word同源消费该视图，新水泥writer分支，绝不重新运行Calculator/读当前标准。

Word包括各线指标与等级、基准及有效阈值、统计边界、输入/四扣除、关键中间量及来源，001/003用“项目内部解释”说明，2019(C.1)/(C.3)列技术参考，不能标为2021附录；不将2019(C.7)作为计算依据。长表按行分页、重复表头、页码，真实渲染验证后才交付；旧r1若无法形成新报告则明确不支持V1.2报告，仍可历史只读查看。

## 7. 独立 Golden 候选与边界门禁

预期在实现前由下列手算确定；Stage C固化为人读说明+十进制JSON，不能导入生产Calculator/ExpressionEvaluator反造expected。独立验收可另用有理数/Decimal参考过程核算（与业务实现代码分离）。候选覆盖身份为V1.2+r2+项目Profile，正式冻结以Stage D实际审查证据为准。

| ID | 原始条件 / 独立推导 | 预期 |
|---|---|---|
| C01 四扣除与余热单次 | P_sh=1000；m=120000,Q_i=Q_BM=29307→F=120000；w_he=10000,w_0=1000→E_he=1.1061；两个tce=2/3→e_fc=5000；w_sh=60000，两kWh=1000/2000 | e_sh,before=118.8939；e_sh=113.8939；W_sh,before=60，净57；E_sh=113.8939+7.0053=120.8992；煤耗未达3级、电耗2级、能耗未达3级（K=1） |
| C02 部分外购 / P_sh≠P_shx | 延续C01，partial_purchase；P_s=2000，P_shx=1500；w_fm=30000,w_m=2000,w_g=1000,w_fz=2000；g=75,e_h=1000,w_sg=68000 | w_s=30000+57×1500+2000+1000+2000=120500；W_s=60.25；E_s=113.8939×0.75+0.5+0.1229×60.25=93.32515→3级；W_sg=34→3级。错误使用E_sh会得到98.579125，错误用P_sh会改变W_s |
| C03 双修正陷阱 | K=1.05,g=80的独立阈值例（K节点独立fixture）；另以实际P_H=60000验证端到端K公式 | L1=85.50，L2=92.75，L3=104.70，旧105.00不得复活；P_H=60000时K按1.179−12660/101325全值推导，不为凑1.05输入近似压力 |
| C04 正式边界 | 每项每个最终T，δ=0.0000001；用DETAIL原始量反解目标实际值；高海拔双修正也测 | T−δ/T归较低能耗等级，T+δ进入下一级或未达3级；显示同值不影响全值比较 |
| C05 海拔严格边界 | 1500、1500.0001；压力缺失/0/正值；表3完整 | 1500时K=1且不依赖压力；超过时缺压力仅四项等级不完整，实际值可显示，表3仍完成；整次不保存 |
| C06 四模式 | 完整integrated/partial、clinker_only、纯外购；纯外购仅P_s=1000,w_sg=29000 | 前两5正式；仅熟料3正式+2不适用；纯外购表3=29→2级可保存，E_s不适用不阻塞，窑扣除不进入表3 |
| C07 缺项依赖 | C02删燃料m；另删w_sh；另仅删w_sg；无关值保持 | 仅依赖节点失效，其余完整指标保持各自结果；任一适用指标缺项记录行数、save调用、保存审计均为0 |
| C08 空白 / 明确0 / 已净额 | 四扣除分别空白与明确0；用已扣后数据且空白 | 数值相同但原始状态不同；快照与Word保留未填含义，不能声称活动不存在；已扣后不再扣 |
| C09 多线分摊 | 两线P_sh=1000/3000，共用熟料电量8000；各自原始电量48000/144000 | 分摊2000/6000；两线W_sh均50；每线独立2级，不加企业总等级；再测不可整除比例和ambient context |
| C10 超额/非法 | 两tce合计超过F−E_he×P_sh、电扣大于w_sh、负值/非有限/float/错单位/零分母/重复线id | 拒绝或相关INCOMPLETE；不得保存；非相关完整项不牵连；不引入“合理气压上限”等无依据阻断 |
| C11 历史保真 | 保存r2后替换当前阈值/Calculator并禁用Engine，读历史、导出、重启 | request/result/snapshot原JSON及等级不变；旧r1不自动重算/改标V1.2；无新增审计写入 |
| C12 正式入口 | DIRECT经Application/Facade、缺适用项/伪造NOT_APPLICABLE、FUTURE、库错配 | DIRECT及正式前置失败不能save；不以GUI禁用充当门禁；未达3级完整请求反而可正常save |

回归顺序：水泥规则/依赖/Numeric/生命周期/报告/表单定向 → GB29446 Golden及Record/Word/Excel后台安全 → Frozen Numeric、N01-A、domain/import → 唯一必要全套pytest及CI → 签名包对账、Artifact Gate、自检 → 原生水泥/选煤最短链及候选包验证。完整pytest约40分钟，仅在最终相关改动稳定后跑一次，失败修复后按影响重跑。

原生Computer Use由唯一GPT-6-astra/medium操作者负责，设计/实现Agent不并行操作桌面。记录实际Windows、DPI、窗口与源码/候选包身份；无环境的项目保留OPEN，不以离屏测试冒充真实DPI/跨屏。Word导出需渲染逐页核验及可用办公软件实开证据，未实开版本如实列缺口。

## 8. 标准包与分段交付

建议三个逻辑提交/审查阶段（父Agent负责提交实际PR；未获Owner授权不合并，双方不发布/tag）：

1. **计算与算例**：`data/definitions/gb-16780-2021.json` r2、domain/models.py兼容字段、domain/gb16780.py、engine.py极小分派、独立Golden及tests/test_first_batch_rules.py旧期望修正。正式范围仍仅选煤。
2. **页面、记录、报告**：application/gb16780.py/服务失败异常与完整性策略、reporting分派、CementReportView、ui/gb16780_form.py、main_window接线、record_detail两页签、word_report分派及相应验证。复用facade/repository，必要API增量通过测试，不改数据库Schema。
3. **配套标准包与开放验收**：安全构建工具最小目标参数化、重建派生索引、签名包/PIN/配套身份、候选构建和验收，最终受审提交同时修改evaluation_support与delivery-scope支持集合并更新用户手册/治理当前入口。未通过前不把水泥宣称正式支持。

包以当前PIN `.5`为可信父；显式新package_id/data_version（必须排序更晚），签名仍Ed25519，no PDF/provenance-only。工具当前硬编码GB29446，改为显式受限目标参数，默认GB29446保持原行为；校验恰好一个水泥定义成员变化、其余47项定义逐字节一致；corrections仅允许必要水泥来源/解释变更，无关条目逐字节不变并单列差异。新定义与data单源规范序列化等价；安装/升级前后历史快照不变，配套readiness未被绕过。

基线验证沿用已记录的精确身份：PR #37 已合并298a966，现有选煤候选为0.2.0-rc-298a966（1236 passed / 66 skipped、Artifact Gate 63项、自检6项由父任务交接）；这些是基线证据，不作为新增水泥通过项，本轮不重复构建选煤包。

本轮只核文件存在性：PIN所记业务主工作树 `work/signing/development-private-key.pem` 不存在；尚未据此声称全机无密钥。后续由父Agent协调既有授权受控位置，私钥不复制到仓库、不输出内容、不从CI取用、不另造不可信签名。无法取得匹配现有公钥的私钥则最终签包/候选构建明确阻塞，其余实现及非签名验证继续；不能降级验签。

当前设计出口已由父Agent独立审查通过（55d09fa）：Canonical、模式矩阵、依赖、保存策略、多线记录、Golden、包策略均已明确；业务映射与标准解释无需Owner重复签署。Stage C后续各块由父Agent独立审查；Stage D前不扩大正式支持。Knowledge capture：本阶段无新增独立知识条目，专业解释继续引用冻结映射及现有Issue。

## 2026-11-11 有限发布阶段隔离修订

因既有签名私钥缺失且Stage D原生/Word待验，父Agent批准本次水泥的有限隔离：r2从2402f5c原字节复制至`standards/development/GB16780-2021/gb-16780-2021-r2-candidate.json`作为唯一未发布候选，生产data水泥恢复298a966配套r1原字节只读，显式测试/隔离夹具改读候选。此项仅调整发布阶段设计，不修改冻结映射、算法、解释、Numeric或其它标准单源原则；不是另建长期发布源，不放宽/跳过交付门禁。签名及正式验收齐备后一次性提升并移除候选，身份及条件见[阶段隔离记录](GB16780_UNPUBLISHED_CANDIDATE_20261111.md)。上文data为本轮实施编辑源的描述保留其设计/阶段历史，本节及AGENTS有限例外为当前执行方式。
