# GB 21342—2025 首块核心实施记录

日期：2026-11-12。式3核心源码已实现，产品未接入；整体MAPPING，未正式支持，不合并本开发PR、不发布。

## 平台 / Contract 预检查

业务基线`ea28ca46fdff826e92f2a907f8faf4e9726f435b`（PR23合并），分支`codex/coke-core-20261112`；最终源码身份以本PR实际head为准。`platform-lock.json`锁中央`ee5feb0cc34dbd99790500fadd0c4c932e202a20`，Architecture2.1与Numeric Contract/Profile/Conformance v1不变；ACTIVE指南及设计读取见[首块设计](GB21342_STAGE_B_DESIGN_20261112.md)。

MUST：纯Domain、严格Decimal、28位ROUND_HALF_EVEN工作精度、全值、不受ambient影响、版本及来源trace。MUST NOT：float恢复、默认ROUND6/epsilon、显示回流、历史重算。Unit/Record/qzpack仍DRAFT；已登记偏差不关闭。无CENTRAL CONTRACT GAP，无须中央修改。相关Issue001已按Owner软件决定记PROVISIONAL、002～005仍OPEN；本块仅002部分外属保持未定。不修改既有生产解释；新增局部未发布算术能力，未替换生产r1。

## 实施范围

用户已授权PR23核实修复合并后开始软件开发。原文式3与完整外属且未计入的26条件已由独立原文复核及父Agent审查，形成本首块的局部事实采用依据；整体映射与争议未完整批准/冻结不等于已核验事实不能局部开发，002～005不因该局部事实采用而获批准；001后续Owner软件决定单独记录于台账。

`src/uebench/domain/gb21342.py`提供不可变`CokeEnergyInput`、`calculate_energy`与专属结果/trace。五量固定kgce、干全焦固定t；严格拒float/bool/非有限数/缺失。五量有限负值按软件入口策略保留并提示核查，不冒充标准许可；产量必须>0。式3保留负actual，不截零。

明确不触发时adjustment0，明确两项全部外属且能耗均未计入时26，部分/未知时actual保留且adjustment/evaluation=None、UNDETERMINED及Issue002。输入、运算、分支、单位、原文源hash与局部规则/Calculator/Numeric身份完整返回；不生成正式record id。

仅支持项目现有Profile且保存有效配置。局部Context完整明示Emin=-999999/Emax=999999、prec28、ROUND_HALF_EVEN、capitals1/clamp0/空flags，InvalidOperation/DivisionByZero/Overflow/Underflow/Clamped traps。正常Inexact/Rounded为工作舍入，不是业务修约；不受DefaultContext或调用者traps/flags/指数范围影响；算术超范围明确错误。

未修改生产data/PIN/签名包、共有Engine/Facade/Schema、其他标准、GUI/Record/Excel。焦炭supersedes遗漏仍为后续配套规则修订待办，签名私钥缺失未解，不能为该元数据单改data破坏PIN一致性。整体映射仍未全面批准；001已获Owner明确软件决定，后续判级不分企业/项目，采用所能达到最高级别，内部解释不进入UI/Word/外部导出。其余002～005未扩展批准。

## 验证

- 焦炭独立15个数值Golden与8类拒绝/边界设计已执行于`tests/test_gb21342_core.py`。初轮145 passed（0.59s）；独立审查后补输入解析flags隔离、极端指数真零及零商边界，最终151项与源码门禁187项组合共338 passed（25.19s）。预期见[独立手算候选](../golden/GB21342_CORE_INDEPENDENT_GOLDEN_CANDIDATES_20261112.md)，不由实现反推。
- Frozen Numeric v1可执行向量、原N01-A、GB29446、Engine、Excel、UI专项组合：138 passed（本地19.71s）。命令为`python -m pytest tests/conformance/numeric/test_ecquota_numeric_v1.py tests/pilots/numeric/test_qzc_n01_a.py tests/test_gb29446.py tests/test_engine.py tests/test_excel.py tests/test_ui.py -q -ra -p no:cacheprovider -o addopts=''`。
- 测试通过独立工作树`PYTHONPATH=src`，未使用已安装旧源码计算焦炭。Python来自既有测试虚拟环境；未操作真实用户数据。
- `compileall -q src tests tools`通过。源码门禁前两次setup产生43项环境错误，分别为系统pytest临时目录权限与工作树work父目录尚未创建；建立work并指定新`--basetemp work/pytest-core-source-fixed`后上述338项全部通过，没有修改业务代码掩盖环境错误。
- [独立源码/Golden验收](GB21342_CORE_INDEPENDENT_ACCEPTANCE_20261112.md)已通过：103原始探针、3项初轮边界、6个零商案例均PASS；独立核心151＋Frozen Conformance20合计171 passed（1.32s），三项发现全部关闭，无剩余首块阻塞。验收代码SHA256为`5b7b09602e84a19632131bda551a4edb76bd6bb9224d1f0cfa96e9147e042b5c`。此为首块验收，不是整标准Stage D。
- literal full suite由新PR的Pull Request Gate严格单次执行，Numeric workflow另跑。CI未完成前本记录不写full PASS。
- 父Agent另以未复用实现预期的探针独立验证：97+3−50−10−5=35kgce，P7t，actual5，完整外属evaluation31，部分actual5且evaluation=None，通过。

独立审查修复：十进制非法lexical解析也在完整局部Context中执行，不污染调用者InvalidOperation flags；真零分量只在算术使用时归一精确0，原始Decimal exponent仍保留于trace；net精确0且P已验证有限正时商直接精确0，避免零商因极端P指数被Clamped误拒。非零下溢继续拒绝，不提升Profile精度或改变非零算术范围。

下一块按已确认最高级别策略接入判级，仍须解决阈值所依赖的必要输入及其余未定事项；本块算术结果尚不能生成最终等级。本块不满足整标准Stage B/C/D出口，不改变正式范围或RS05状态。

## 2026-11-12 Owner明确001软件决定后的同步

更新基线为PR40的`570f9bd09ba6e94a052f780e92019d1c953858d2`。Owner明确：软件不分现有企业/新建项目，按能达到最高级别判定；属于软件内部策略，不代表标准解读，解释不进入UI/Word/外部导出。台账001改PROVISIONAL，原文事实保持；002～005仍OPEN，整体映射仍未全面批准。Stage B删除企业属性输入及限定/准入合规主结论，内部后续判级验收表加入非单调与局部未知案例。

本次仅内部文档变更。已核对调用链：首块`calculate_energy`不调用等级算法，也没有grade输出；通用`EvaluationEngine._grade`已按1→2→3返回首个满足级别。因此不凭空新增未接入helper，不改生产算法/规则/Schema/UI/报告或冻结Mapping。后续接入需补未知高等级是否妨碍确定最高等级的完整性判断：已知1级通过无需补低级阈值；1级不通过且2级通过无需补3级；高等级未知则不能把已知较低级伪装成最高。

父Agent对既有通用算法的5个独立探针通过：112.5/110/137.5这一组，E111→1、110→1、113→3、138→未达3；通用合成100/110/135，E105→2。后者不是焦炭标准明文工况。这些只验证既有优先级，未宣称首块焦炭完整判级已接入。文档差异检查及内部决定一致性核对执行；既有首块测试证据保持对应源码身份，未为文档变更重复本地full suite，新PR CI按最终head执行。
