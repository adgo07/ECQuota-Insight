# GB 21342—2025 首块独立只读验收记录

日期：2026-11-12。验收范围：纯Domain式（3）及明确26分支；不是整标准Stage D，不开放正式评价。

## 平台 / Contract 预检查

受验工作树`work/coke-core-20261112`，起始业务基线PR23合并SHA`ea28ca46fdff826e92f2a907f8faf4e9726f435b`；本记录验收时改动尚未提交，以实际文件SHA256固定实现：

`src/uebench/domain/gb21342.py`：`5B7B09602E84A19632131BDA551A4EDB76BD6BB9224D1F0CFA96E9147E042B5C`。

中央Frozen锁定`ee5feb0cc34dbd99790500fadd0c4c932e202a20`，Numeric Contract/Profile/Conformance v1维持基线，Decimal28/ROUND_HALF_EVEN、正式全值比较、无默认ROUND6/epsilon、无float恢复、显示不回流、context独立；Unit仍DRAFT，不修改lock或公共Contract。未发现CENTRAL CONTRACT GAP。

相关Standard Issue为ECQ-STD-GB21342-002：部分外属/未知保留actual，adjustment/evaluation未定，无擅自0/13/26分配；001/003/004/005不在本首块处理。有限负分量/负结果保留算术并中文警示、P>0系父确认的本块软件策略，不冒充标准允许任意负实物流。本能力独立未发布，不改变生产r1、正式支持范围或历史结果。

## 独立方法与已执行结果

先于实现编制的15项Golden来自原文式（3）及§6.1.1、整数分数/十进制长除和显式28位工作语义，没有从实现反生成预期。原文SHA为`00fcc51c02c6d73d39bcab3103227fca2ee93841abce45d1576edaeba25595a0`，印刷4/PDF8。

独立读取实际实现、公开API及trace，再用独立探针执行：

- `probe.py`，103/103 PASS。包括15Golden、逐字段float/bool/nonfinite/错误单位拒绝、每个有限负分量接受与警示、真实underflow拒绝、28位循环小数及加26再舍入、1E400有限大数、caller全部traps/flags配置隔离、精确最小subnormal保留。
- `edge_probe.py`，3/3 PASS。错误文本解析不污染caller InvalidOperation flag；极小exponent正/负真零得到实际值0，原输入trace保留，不误判underflow。
- 独立执行零商补充6例：五能量全0、P分别1E1000027和1E-1000027，各跑N/T/U三状态，actual均0，evaluation分别0/26/None；P仍必须有限且>0。
- pytest独立执行`tests/test_gb21342_core.py`与`tests/conformance/numeric/test_ecquota_numeric_v1.py`，151+20=171 passed，exit0，1.32s。命令使用主checkout `.venv/Scripts/python.exe -m pytest ... -o addopts='' -p no:cacheprovider`，cwd为受验工作树；Python3.13.3/pytest8.4.2。

证据在本记录同目录：`probe.py`、`report_final.json`、`edge_probe.py`、`edge_final.json`；失败时的`edge_before.json`和修复中间版保留追溯身份，不替代最终结果。原PDF/渲染图未复制进代码或交付物。

## 发现、修复与复验

1. 最初无效十进制文本在局部context之外解析，能污染caller InvalidOperation flag。实施改为显式局部context解析；同一独立探针复验关闭。
2. 最初极小exponent真零被Clamped trap误拒。实施将算术零归一，trace保留输入值；正/负零独立复验关闭。
3. 同类零商在极大/极小有限正P下误触Clamped。父确认net为零直接actual0；独立6例复验关闭。非零真正underflow仍报中文计算范围错误，未无声变0。

初次pytest默认命令曾显示145全点完成但进程未退出，验收线已中止该自有进程，不计为通过证据；后续显式禁用cache、清空addopts的最终171项命令正常exit0。未改变机器权限、终止其他会话或改实现文件。

## 结论

在上述最终实现文件hash及限定范围内，无剩余阻塞缺陷。五量加减、干全焦分母、完整26调整、部分保留actual、有限负量警示、输入/单位边界、Decimal工作语义、trace及版本源引用满足首块设计。可供父审核首块代码与PR；本记录不批准合并，不替代full suite、N01-A或其他交付门禁，不代表整标准IMPLEMENTED/SUPPORTED或Stage D验收通过。
