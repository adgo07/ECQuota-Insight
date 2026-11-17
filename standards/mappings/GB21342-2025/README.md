# GB 21342—2025 焦炭映射入口

- 程序标准ID：`gb-21342-2025`；包含顶装、捣固两种常规焦炉。
- **现行批准映射：无。** 当前工作稿：[标准映射表V1.0草稿](标准映射表_V1.0_草稿.md)，2026-10-13编制；2026-11-12独立核验表A.3/A.4逐行配对及公式实现差异，尚未完成全部专业审核或映射批准。
- [原文及交付核验记录](核验记录_20261013.md)；[唯一标准问题台账](../../../STANDARD_ISSUES_REGISTER.md)中的ECQ-STD-GB21342-001—005。
- 标准现行，2026-05-01实施，全部替代GB 21342—2013；原文来源及SHA见映射§2，PDF不提交、不分发。
- PR #23仅作Stage A映射整理（MAPPING）；已有JSON不代表正式支持，PR #23未实施或验收焦炭Stage B/C/D，正式评价仍仅GB29446。2026-11-12 Owner已授权PR #23核实修复合并后继续焦炭开发；当前水泥为IMPLEMENTED、Stage D未闭合，RS05/RS06以当前TASK_STATE为准。
- [映射总索引](../INDEX.md) · [目录规范](../README.md) · [当前任务](../../../TASK_STATE.md)。

## 2026-11-12 授权后的首块实施

PR23已合并；Owner授权继续开发下，按经独立核验的原文式（3）与完整外属且未计入时的26调整实现独立Domain核心。见[首块设计](../../../docs/governance/GB21342_STAGE_B_DESIGN_20261112.md)、[实施记录](../../../docs/governance/GB21342_STAGE_C_CORE_REPORT_20261112.md)、[独立Golden候选](../../../docs/golden/GB21342_CORE_INDEPENDENT_GOLDEN_CANDIDATES_20261112.md)。本块不接GUI、正式记录或标准包；部分/未知调整未定。整体仍MAPPING，无现行批准映射，001按Owner明确的软件最高级别决定记PROVISIONAL，002～005仍OPEN，未纳入正式支持；代码首块完成不等于整标准IMPLEMENTED或Stage D通过。

Mapping草稿§7及PR23核验记录的001 OPEN保留当时身份；2026-11-12后续内部软件决定以[唯一台账001](../../../STANDARD_ISSUES_REGISTER.md#ecq-std-gb21342-001--炉龄修正后1级与2级限额非单调的等级表达)及[当前设计](../../../docs/governance/GB21342_STAGE_B_DESIGN_20261112.md)为准。只同步软件内部决定，不改标准原文事实、历史核验结论或整映射批准状态，解释不进入产品界面或导出。

## 当前完整业务判级预览（2026-11-12续更）

已实现两炉型已折标明细能耗/26、各级修正阈值及最高级别/未定子项，并提供Application与Facade只读preview_coke；见[本轮实施记录](../../../docs/governance/GB21342_STAGE_C_ASSESSMENT_REPORT_20261112.md)。001软件决定已采用，003区间相邻线性是本轮软件算法选择；表外等其余未决保留。整体仍MAPPING，无整映射全面批准，不代表GUI/能源台账折标/正式记录或Stage D完成，正式范围/PIN/生产规则不变。
