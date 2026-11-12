# GB 21342—2025 接入设计与判级预览边界

日期：2026-11-12。当前范围为用户授权的完整纯业务判级预览链；首块式3能力继续复用。001最高级别已确认，003区间内相邻线性为本轮明确采用的软件算法；其余未决范围不新增解释。不是第二份总体产品路线。001解释只记内部资料，不进入UI、Word或外部导出。

## 平台 / Contract 预检查

业务基线：`origin/main@7127673c76d5b4d99d920c345688344413c16c4a`。PR23合并后开发SHA、映射版本/hash在实施时补记。共享cwd实际不是main，已改用显式`git show origin/main:<path>`重新读取现行TASK/路线/台账/lock/HANDOFF和代码，未按旧工作区状态设计。

实施基线：PR23已合并`ea28ca46fdff826e92f2a907f8faf4e9726f435b`，独立分支`codex/coke-core-20261112`。映射V1.0草稿SHA256为`5efedc65f048205da5cc4655b81bff01f27d8cee37cdc8664f4658f1a15a748b`；本轮局部依据为已核验式3、明确26条件、表1/表2，以及001最高级别软件决定、区间相邻线性算法选择，不表示整映射批准。历史[首块实施记录](GB21342_STAGE_C_CORE_REPORT_20261112.md)与当前[判级实施记录](GB21342_STAGE_C_ASSESSMENT_REPORT_20261112.md)分别承接范围。

Frozen基线：`platform-lock.json`锁定中央`ee5feb0cc34dbd99790500fadd0c4c932e202a20`，Architecture2.1、Numeric Contract/Profile/Conformance v1已按此读取。ACTIVE依据：中央`origin/main@829853a943c421e0b9864d84f3d94970d2ddf688`的GUIDE_INDEX、标准开发指南、产品交付规则、UI家族规格/指南v0.2/验收清单。

MUST：Domain独立于UI/SQLite/Excel；版本化输入输出、trace；Decimal/28位/ROUND_HALF_EVEN，全值精确比较，上下文独立，显示仅用于展示，历史快照不重算。MUST NOT：默认ROUND6/epsilon、float恢复真值、未决解释冒充标准明文、运行时解析Markdown。Unit/Record/qzpack仍DRAFT，D-ECQ-002～006继续REGISTERED DEVIATION。

相关Issue：`ECQ-STD-GB21342-001`～`005`；001已按Owner软件决定记PROVISIONAL，002～005仍OPEN（003仅区间内插值算法本轮采用）。本地通用明细公式不能表达式3；本轮已接完整独立判级预览，不替换生产r1。非单调限额不能套水泥顺序校验。无须修改中央Frozen Contract或lock；标准原文不变。

正式范围仍仅GB29446；RS06已有水泥Stage C，RS05仍IN PROGRESS。不改水泥冻结映射/实现/候选，不改生产data/PIN/数据库/安装包。

## 现状与差异

| 对象 | 当前事实 | 接入方向 |
|---|---|---|
| Mapping | PR23覆盖式1～3、表1/2、附录A/B；001软件决定已确认，002～005仍OPEN | 事实核验合并与软件解释采用分开，整体映射未全面批准 |
| 机器规则 | data/definitions焦炭r1已有分类/修正；通用总标准煤÷折合产量并非五分量式3 | 首块不需机器规则文件；后续候选隔离方式待与唯一data源/打包策略协调，不套用水泥特批；scope-63/65只读历史 |
| Engine | `_grade()`按1/2/3首命中，完整已知阈值下符合最高级别策略 | 本轮独立链采用同一优先级并处理未知高等级，复用Grade，不改公共Engine |
| 模型/保存 | IndicatorResult只有grade及compliance；正式evaluate有范围门禁 | 后续采用最高级别，不增加限定/准入合规主结论；完整性及保存另行接入 |
| 水泥先例 | 专用calculator已有dispatch；水泥完整性要求L1≤L2≤L3 | 可以复用分层方法，不能复制顺序断言 |

元数据真实差异：焦炭2025版替代2013版，但生产r1的`supersedes`为空。修复须与标准包版本、签名、PIN成套，当前签名私钥缺失未解；本首块不改生产data，不称该项已修复。后续真实配套规则修订时表达正确元数据，并完成配套签名与交付验收；不默认另建第二可编辑机器JSON。

## 历史首块范围：原文明细式3与明确26分支

用户已授权开始开发。首块仅做纯Domain独立能力，不接Engine/Facade/UI/Record/报告/Excel，不改变正式评价范围。建议文件`src/uebench/domain/gb21342.py`及`tests/test_gb21342_core.py`。

Canonical是专属不可变输入，数值接受十进制文本/Decimal/精确整数，拒绝float/bool/非有限数。模型不能在验证前把float转Decimal，也不能仅依赖类型注解保证dataclass传参类型。

| 字段候选 | 单位 | 要求 |
|---|---|---|
| raw_coal_energy_kgce | kgce | e_yl原料煤有效能量 |
| processing_energy_kgce | kgce | e_jg加工能量 |
| coke_energy_kgce | kgce | e_jt干全焦携带能量 |
| chemical_products_energy_kgce | kgce | e_jf净化回收化产品能量 |
| recovered_heat_energy_kgce | kgce | e_yr回收有效能量 |
| dry_coke_output_t | t | p_JT干全焦，>0 |
| external_services_status | enum | 明确不触发/两项全外属且未计入/部分或未知 |

五能量项不能缺项默认为0，真实0可输入。原文未明确规定分量非负，本首块有限负分量保持原样执行算术并给中文统计口径核查warning；这是软件数据合理性提示决定，不宣称标准允许任意负实物流，也不称标准强制非负，不新增Standard Issue。净结果为负同样保留并提示核查，不截零。产量P>0为有效单位产量必要边界。单位固定即可，本块不提供自由单位编辑器；若支持tce须在明示单位边界×1000，不能隐式猜测。

Profile入口默认明确绑定项目`ECQUOTA_DECIMAL_FULL_VALUE_V1`。若函数接受显式Profile参数，必须在函数入口核对其已支持身份/配置，计算及trace使用同一个传入有效Profile；不支持的Profile须明确拒绝，不能悄悄使用调用方ambient或helper自造默认。首块不声称已支持任意Profile。

已实施工作范围：Context完整明示prec=28、ROUND_HALF_EVEN、Emin=-999999、Emax=999999、capitals=1、clamp=0、flags清空；traps为InvalidOperation/DivisionByZero/Overflow/Underflow/Clamped。该范围是本局部Calculator的版本化算术范围，不是业务数量上限或额外业务修约；正常Inexact/Rounded（如1/3）按Profile工作舍入继续，不作为错误。指数范围错误明确报错，不能把有限非零下溢成可信0；不依赖decimal.DefaultContext或调用者context，不修改公共Numeric。

解析也隔离Context；真正零仅在算术侧规范为精确0，输入trace仍保留原Decimal。净量精确零且P有限正时，商精确为0，不因零或P的lexical exponent误触发Clamped；非零下溢仍明确错误。

在有效Profile自己的localcontext内按原式顺序计算：

`net = e_yl + e_jg - e_jt - e_jf - e_yr`

`actual = net / dry_coke_output_t`

明确均不外属或已计入：adjustment=0、evaluation=actual。煤气净化和废水处理两项完整外属且能耗均未计入：adjustment=26、evaluation=actual+26。仅一项/部分计入/未知：保留actual，adjustment=None、evaluation=None、adjustment_status=UNDETERMINED并引用Issue002，不能分摊13或返回伪完整值。

外属enum是Domain最小语义承载，不要求未来UI增加技术确认框；Adapter应从实际业务事实映射。首块不判断企业等级、适用性、限额或准入。

专属结果保存net/actual/adjustment/evaluation/status/warnings/trace、源引用、calculator_id/version、局部rule_revision、numeric_contract_version/profile_id/behavior_version。局部规则版本不得暗示生产r1已替换；不创建正式record id。trace列出输入及单位、加减净量、除法、26触发或未定原因，全部使用有效Profile。不用显示值回流。有限值计算若超出Decimal工作范围，明确报计算错误，不泄露Infinity。

来源：§6.1.1、§6.2式3，PDF8，源SHA `00fcc51c02c6d73d39bcab3103227fca2ee93841abce45d1576edaeba25595a0`；最终定位跟随PR23核验稿。不因非计算必需的追溯信息不足阻断结果。

## 当前完整判级预览链设计

本轮基线`47d50b51a992a04cf167fb60f0b6de632877771a`。公开输入为`CokeAssessmentInput`：必须提供已验证的`energy:CokeEnergyInput`；炉型、燃料、Vd/Mt、炉龄、熄焦、混煤时间比例及常规焦炉事实可为None，显式非法值与缺失区分。即使适用事实False/None，该API仍要求有效energy以便保留独立能耗参考，不扩展可选energy接口。

`assess_coke`复用式3/明确26后计算两炉型修正阈值，返回`CokeAssessmentResult`（energy、逐级base/corrections/threshold/matched/undetermined_reasons、现有Grade、完整trace、局部版本及来源）。常规焦炉事实默认None则INCOMPLETE，False为NOT_APPLICABLE，True才可判等级；不要求新增UI确认框，后续Adapter应从可靠业务事实推导。Application `preview_coke`与`ApplicationFacade.preview_coke`薄委托均只读，不调用legacy r1或存储，不改正式evaluate门禁；本轮不做GUI、台账能源折标、正式记录或包发布。

Canonical按同一统计期及单焦炉类型组织，保持现有顶装/捣固产品ID。不同炉型/炉龄/分期聚合不得直接平均，先证明能量和产量不重复，再设计分段合并。

输入仅保留实际计算/适用性不能自动确定的事实：常规焦炉、焦炉类型、报告期、五能量项与干全焦产量、加热燃料（仅混合煤气要时间比例r）、Vd/Mt、熄焦方式、1/3级用炉龄。不新增企业建设属性或项目属性字段；软件不据此筛掉等级，不输出限定值/准入值合规主结论。标准原文的企业用途条件原样保留在Mapping，不由本软件决定改写。

原始台账下一层按数量×有效系数分别汇总五项，保留实测优先、参考后备：干洗精煤/干全焦按附录A；其他能源优先实测热值，蒸汽记录绝对压力/温度/热焓或明确系数来源；工质实测优先，其次附录B。氮气主/副产品不可混用。非表列蒸汽不自动二维外推；可接受合法实测焓/系数。来源不足原则Warning。气种同名不意味着流量可重复扣除。

直接单位值入口若有真实需求，须明确是式3未调整还是已加26，自动防双加；首块不做双入口。普通字段中文，机器key只在后台。

阈值：L1=B1+F+V+M+A，L2=B2+F+V+M，L3=B3+F+V+M+Q+A。B顶装110/110/135、捣固115/115/140；F为8r/12r且r是使用时间；M为3.67(Mt−10)/3.71(Mt−10.5)；Q湿熄46.46只用于3级；A≤15为0、(15,25]为2.50、>25为5.50，只用于1/3级。其他燃料不得假扮混合煤气。

Owner于2026-11-12明确的软件判级：分别按各级原有阈值进行`E_eval<=Lk`比较，不对阈值排序、截取或强制单调；在满足级别中取数字最小者（1级最高）。满足1级不推定同时满足2级。已知1级满足即最终1级，无须补齐低级阈值；1级确定不满足、2级满足即最终2级，3级未知不阻断。已知3级满足而1或2仍未知则无法确认最高等级，保留未定。评价值及三阈值完整且均不满足才为“未达3级”。非常规焦炉仍为不适用；其他数据/解释不足只保留已确定部分（混合干湿可保留已知L1/L2，表外Vd仍可保留actual）。本软件最高级别策略不代表标准解读；该解释只在内部说明保存，不带入UI/Word/外部导出。

## 已确认软件决定与其余待决候选

| Issue | 推荐候选 | 精确边界与待决 |
|---|---|---|
| 001非单调 | Owner已确认不区分现有企业/新建项目，按能达到最高级别，001为PROVISIONAL | 不新增企业字段或限定/准入合规主结论；逐级阈值不排序、满足取1→2→3最先者；本轮判级预览已采用；解释仅内部保存 |
| 002部分外属 | 两项全外属未计入+26，明确均已计入/不外属0，部分未定 | 部分加26/13分摊/比例均无直接依据；Owner决定前不算该adjustment |
| 003表外Vd | 区间内相邻线性本轮明确采用，节点精确；区间外V未定仍保留actual | 线性是本软件算法选择，标准仅允许插值，非唯一标准解读；003表外问题仍OPEN，不外推/夹取或宣称全标准不适用 |
| 004干湿并存 | 可可靠分段则分段评价；单混合期L3修正未定 | 比例加46.46须决定时间/产量权重，不能自选；L1/L2仍可确定 |
| 005驰/弛放气 | 保留两处原文用字和Issue；有气种证据再别名关联 | 不能只凭字形就等同并套0.3216；首块已折标五分量不涉及这一对象 |

001为Owner软件决定；003区间相邻线性已作为本轮常规算法选择记录采用，不再等待泛审批。002部分外属、003表外、004混合干湿、005气种术语仍OPEN。其他/未知燃料F未定不默认0；这些未知只影响所依赖子项。

原先“按评价对象给限定/准入主结论”的技术推荐未获采用，已由上述Owner决定覆盖。标准非单调事实不据此判错，原文与软件策略明确分开；不以内部工程推断包装为官方解释。

## Application、Record与UI

后续单一normalize→Calculator→结果路径，准确adoption标识/hash消费配套规则；是否采用隔离候选及其位置是待确定方案，须与唯一data源、打包策略协调，水泥特批不是焦炭自动授权。正式支持门禁保持；预览不把legacy r1计算冒充新实现。记录保存原始输入/系数来源、统计期、Mapping/Rule/Calculator/Numeric版本、每子项终态与规则快照；历史不重算。结果字段落位先明确向后兼容，不为首块迁移数据库。未定adjustment不形成伪完整正式记录；actual可以预览。报告只用记录快照。

未来Windows沿现有家族壳、五类功能单页业务分区：实际能耗与最终级别，不新增企业属性字段，不输出限定/准入合规主结论，不向UI/Word/导出加入本内部解释文字；未定/未开放/结果过期直接可见。记录两页签不新增审计页。标准库五列/详情三区，映射确认与软件支持分别表达；未StageD不得开放。官方地址固定登记并核验，不运行时搜索。Excel本轮不做，未来仅文本Decimal Adapter共用Domain，无第二套算法。

## 验证与Golden候选

独立首块C04：五量100000/20000/80000/20000/5000kgce，P100t，net15000，actual150；完整外属未计入evaluation176；不触发150；部分/未知actual150且evaluation=None。另测扣除大于输入的负actual、净0、真实0≠缺失、P零/负、每项缺失、float/bool/NaN/Inf、算术溢出、非法外属状态、长尾小数无quantize、caller低精度/不同rounding/traps不影响。测试须执行有效Profile且不悄悄退回默认。明确类型模型错误与中文计算错误。

完整评价后续：两焦炉所有节点/区间、r0/1、Mt基准±、炉龄15/15+δ/25/25+δ、所有T−0.0000001/T/T+0.0000001、每级修正矩阵、最高级别策略且无企业字段、未定局部保留、tce×1000陷阱、能源双扣、氮气主副产品、所有蒸汽精确节点和绝对压力、实测优先。

非单调手算：顶装r0.5/Vd24.5/Mt11/湿熄/20年，L1=126.57、L2=124.07、L3=198.03；E125通过L1不通过L2，按已确认软件策略最终1级，见[本轮独立Golden](../golden/GB21342_ASSESSMENT_GOLDEN_CANDIDATES_20261112.md)。完整物理工况B1=B2、F/V/M共用、A≥0，故L1≥L2；最终2级在真实完整工况不可达，是原表与软件策略自然结果，不改标准或阈值制造2级。

### 001判级验收案例（内部）

| 案例 | E_eval | L1/L2/L3 | 独立逐级结果 | 最终软件级别 |
|---|---|---|---|---|
| 非单调基准顶装/20年 | 111 | 112.5/110/137.5 | 真/假/真 | 1级 |
| 同组等号 | 110 | 112.5/110/137.5 | 真/真/真 | 1级 |
| 仅较低级满足（通用算法合成阈值，不冒充焦炭明文工况） | 105 | 100/110/135 | 假/真/真 | 2级 |
| 非单调组较高实际值 | 113 | 112.5/110/137.5 | 假/假/真 | 3级 |
| 全部不满足 | 138 | 112.5/110/137.5 | 假/假/假 | 未达3级 |
| 必要阈值未定 | 111 | 未定/110/137.5 | 未定/假/真 | 不生成完整最终等级 |
| 已知最高级满足、低级未知 | 111 | 112.5/未定/未定 | 真/未定/未定 | 1级，无须补齐低级阈值 |
| 高一级确定不满足、2级满足、3级未知（通用算法合成） | 105 | 100/110/未定 | 假/真/未定 | 2级，无须补齐3级 |

上述案例没有企业/项目属性输入，内部解释不进入运行结果文案。通用Engine `_grade()`的1→2→3优先级保持，但其跳过未知阈值不足以处理本链。现`assess_coke`采用短的局部partial-aware选择，复用现有Grade枚举：遇到首个满足项之前的未知即INCOMPLETE，已过高等级无须补低等级；不是新增公共等级模型。原`calculate_energy`仍只返回actual/adjustment，不破坏首块API。

trace保存五能量及产量、八项评价输入（含原始正规化Decimal值和单位）、每个修正/未定原因、各级阈值及逐级比较、最终级别。调整未定及适用事实未知也进入每级undetermined_reasons，003/004来源可从技术trace追踪；不把001内部解释加入UI/Word/导出。L3算术顺序明确为B+F+V+M+Q+A，全部使用首块已完整声明的Profile/Context；显示不回流。

判级预览测试、Frozen v1向量真实执行、原N01-A、Numeric/domain/import及full suite、numeric-v1-adoption workflow按AGENTS核对；已有失败单独记录不能顺改无关逻辑掩盖。本轮完成只写“完整纯业务判级预览已实现并验证”，不表示GUI、明细台账折标、正式记录、Stage D或整标准SUPPORTED；整体映射仍MAPPING，不宣称RS05完成或发布。
