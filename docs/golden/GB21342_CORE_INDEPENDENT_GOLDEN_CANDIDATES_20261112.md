# GB 21342—2025 首块独立 Golden 候选

日期：2026-11-12。编制角色：独立原文核验与验收线。状态：设计阶段可审候选，不是已执行生产实现测试，不是Stage D通过。

## 平台 / Contract 预检查

业务设计基线`7127673c76d5b4d99d920c345688344413c16c4a`；PR23原映射核验提交`18dd79af74476372e8b6b337df119ce04d9d9198`。合并后的业务SHA由实施报告补充。`platform-lock.json`锁定中央`ee5feb0cc34dbd99790500fadd0c4c932e202a20`；Numeric Contract/Profile/Conformance v1保持原基线，采用`ECQUOTA_DECIMAL_FULL_VALUE_V1`：Decimal、28位有效工作精度、ROUND_HALF_EVEN。禁止默认ROUND6、epsilon、float恢复、显示值回流、调用者ambient context改变权威结果。

本块无须中央Contract修改，无CENTRAL CONTRACT GAP；Unit仍DRAFT。Issue002相关部分外属/未知分支保留未定，不解释为0或13。其余Issue001/003/004/005不影响本块已折标五分量算术。未修改既有生产解释，不改变正式支持门禁。

## 来源与预期独立性

原文`标准原文/08.GB 21342-2025焦炭单位产品能源消耗限额.pdf`，SHA256`00fcc51c02c6d73d39bcab3103227fca2ee93841abce45d1576edaeba25595a0`。§6.2式(3)，印刷4/PDF8：

`net = raw + processing - coke - chemicals - heat`（五项全部kgce）

`actual = net / dry_coke_output`（干全焦t；结果kgce/t）

§6.1.1同页：煤气净化与废水处理两项完整外属且能耗未计入时，计算结果增加26kgce/t，不能加在限额上。

以下预期由原式加减、整数分数和十进制长除法独立得到，没有调用拟实现`gb21342`模块、Engine或现有规则生成。循环小数先由分数1/3、2/3长除，按第29位判定28位ROUND_HALF_EVEN；再按已声明顺序对actual加26。Python标准库Decimal仅用于复核已写预期数字，不是业务实现oracle。

`N/T/U`是本候选语义简写，不要求成为生产enum值：N=明确不触发；T=两项完整外属且均未计入；U=仅一项、部分计入或未知。父Agent已明确本首块软件决定：有限负分量保留算术并给中文口径核查warning，负结果同理；P>0。该决定不宣称标准允许任意负实物流，原文也未明定负账冲回处理。不要以五量非负断言替代此决定。

## 数值Golden候选

五量顺序固定`[raw, processing, coke, chemicals, heat]`，全部为十进制文本；输入P为t。

| 编号 | 五量kgce | P | 状态 | net kgce | actual kgce/t | adjustment | evaluation kgce/t | 独立推导/语义 |
|---|---|---|---|---|---|---|---|---|
| G01 | 100000,20000,80000,20000,5000 | 100 | N | 15000 | 150 | 0 | 150 | C04，120000−105000=15000 |
| G02 | 同G01 | 100 | T | 15000 | 150 | 26 | 176 | 完整触发；26是单位结果上的加数 |
| G03 | 同G01 | 100 | U | 15000 | 150 | null | null | Issue002未定；actual不丢失，不补0/13/26 |
| G04 | 100,20,80,30,10 | 5 | N | 0 | 0 | 0 | 0 | 真实五量可含0，净零不是缺失 |
| G05 | 100,20,80,30,10 | 5 | T | 0 | 0 | 26 | 26 | 不因actual=0跳过26 |
| G06 | 100,20,100,30,10 | 4 | N | -20 | -5 | 0 | -5 | 不截零；中文结果口径warning |
| G07 | 同G06 | 4 | T | -20 | -5 | 26 | 21 | 负actual仍按原式加26 |
| G08 | 1,0,0,0,0 | 3 | N | 1 | 0.3333333333333333333333333333 | 0 | 同actual | 1/3，28位；不得ROUND6 |
| G09 | 1,0,0,0,0 | 3 | T | 1 | 0.3333333333333333333333333333 | 26 | 26.33333333333333333333333333 | 加26后共28位有效数字 |
| G10 | 2,0,0,0,0 | 3 | T | 2 | 0.6666666666666666666666666667 | 26 | 26.66666666666666666666666667 | 2/3第29位6，向上取末位7 |
| G11 | 0.0000001,0,0,0,0 | 1 | N | 0.0000001 | 0.0000001 | 0 | 0.0000001 | 非零长尾，显示精度不能变为0 |
| G12 | 5E+400,3E+400,2E+400,1E+400,1E+400 | 2E+399 | T | 4E+400 | 20 | 26 | 46 | 有限Decimal，超出float范围仍应可算；不经float |
| G13 | 10,-2,3,0,0 | 1 | N | 5 | 5 | 0 | 5 | 父决定的负分量策略；中文输入口径warning |
| G14 | 1,0,0,0,0 | 1 | N | 1 | 1 | 0 | 1 | 名为kgce的数值1只表示1kgce，不猜测为1tce或乘1000 |
| G15 | 0,0,0,0,0 | 1 | U | 0 | 0 | null | null | 不能因actual为0就宣称无需26分支判断 |

Decimal值按数值等价验收；不强制`20`与`2E+1`的字符串样式，不强制正/负零格式。warnings按语义和中文可读性验收，不绑定未批准的完整文案。G06/G07是结果为负warning，G13是输入负分量warning；G13结果正数也不能抹掉输入核查提示。

## 非数值/拒绝候选

| 编号 | 输入变化 | 预期 | 理由/边界 |
|---|---|---|---|
| V01 | 任意必需五量缺失、None；P缺失、None | 明确输入错误，无完整结果 | 缺失不等于0；逐个字段参数化 |
| V02 | P=0、-1 | 明确输入错误 | 不能除零或以负产量评价；本设计P>0 |
| V03 | 任意数值字段为Python float或bool | 在转Decimal之前拒绝 | 包括0.0、True、False；逐字段检查 |
| V04 | 任意数值字段NaN、sNaN、Infinity、-Infinity | 拒绝非有限数 | 同时覆盖文本及Decimal对象 |
| V05 | 空文本、空白、非法十进制；不支持对象类型 | 可读输入错误 | 不输出伪完整数值 |
| V06 | 外属状态缺失或非法enum | 明确输入错误 | 不静默按N处理；合法U则按G03/G15处理 |
| V07 | 在kgce数值字段传`{value:1,unit:tce}`、`1 tce`或错误字段`raw_coal_energy_tce` | 固定单位API拒绝；不吞掉单位或猜测换算 | 若没有自由单位参数，不为此新增单位编辑器；测试仅覆盖实际公开入口，不发明无入口参数 |
| V08 | 数据有效但算术结果超出已声明工作范围 | 明确计算错误；无Infinity结果 | 该组须依据最终Profile实际Emax/Emin构造，不能把G12误判溢出 |

精确整数和Decimal输入另作与同值十进制文本等价性测试。对于用户已经传入的Decimal，不能可靠追查其先前是否由float构造；禁止的是本模块把float恢复为权威Decimal，不声称解决不可见的数据来源问题。

## Context及trace独立验收

- G08/G10/G12在调用者prec=6、ROUND_DOWN/ROUND_UP、较小Emax/Emin、Inexact/Rounded/Overflow陷阱开启等情况下，权威结果与标准context一致；外部context配置和已有flags不得被污染。先确认Profile明确的指数范围及陷阱政策，再写精确断言，不能只改prec/rounding后继承其他ambient属性。
- trace逐项记录全部五量、kgce单位、干全焦t、净值加减链、actual除法、26/0/未定分支及Issue002引用。不得用显示后的actual再加26。
- U保留net/actual，adjustment/evaluation为null并明确UNDETERMINED，不能产生完整判级或正式record。本块不产生等级/限额/准入结果。
- 输出含numeric_contract_version/profile_id、calculator id/version、局部rule_revision、必要numeric_behavior_version和原文来源。不能把局部版本写成生产r1已经替换。
- G01等适当复制为调用间隔离检验：计算T后再计算N/U，26或warning不得串入其他结果。

本候选供父Agent审阅后用于首块实现独立验收；不提前改变整标准MAPPING状态或正式评价范围。
