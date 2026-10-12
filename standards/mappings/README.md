# 标准映射表归档目录

状态：**工作资料（Documentation / Stage A）**。本目录不参与程序运行，不是发布规则源。

## 使用范围
- 每新增一个标准，先保存用户提供的原稿、标准来源及 SHA256，再进行 **Stage A 标准整理与独立核对**。
- 正式计算仍按 `标准原文 / 已批准的 Canonical → Rule → Calculator`，不可直接加载 Markdown 映射表决定判定结果。
- 具体业务映射归各自业务仓；中央 `Qingzhou-contracts` 只放开发流程与公共 Contract，不复制各标准技术原文。

## 每个标准建议文件结构
```text
standards/mappings/
├── README.md
└── GB16780-2021/
    ├── 标准映射表_用户原稿_V1_待复核.md
    ├── 标准映射表_V1.1_修订稿.md     # 上一已审核历史基线
    ├── 标准映射表_V1.2_修订稿.md     # Owner批准的现行冻结业务映射
    ├── 审核报告_20261011.md          # V1原稿审查证据
    └── DECISIONS_NEEDED.md         # 已确认解释与Stage B/C待办
```

**当前已由Owner批准冻结的现行水泥开发映射为 `标准映射表_V1.2_修订稿.md`；已根据2026-10-12用户决定改为2个tce＋2个kW·h分项扣除，并已逐式核对2019征求意见稿(C.1)/(C.3)及(C.7)与2021正式版的差异。V1.1保留作为上一已合并审核基线，旧两个tce扣综合能耗的口径已废止，不能再用于正式实现。V1.2的业务映射已冻结（MAPPING FROZEN），**Stage B的软件接入设计、Stage C实现及Stage D正式验收仍未完成**。后续计算、GUI、JSON、Excel及Golden不得擅自改变它。Owner批准的新版本才能替代；详见V1.2第0节。** 原稿仅供历史核对。目前仅进入映射/决策阶段，未同步修改正式JSON/计算程序，也未宣告可正式支持。

下一标准用同样的 `标准号-年份` 文件夹。一个标准涉及多个产品或工序时，仍按同一标准建目录，在 Mapping 内区分评价对象，避免按产品重复一套原文依据。

## 状态标识
- **DRAFT / MAPPING**：仍有歧义、缺项或未复核内容，不得据此更新正式计算规则。
- **REVIEWED**：条款/数值核对、Standard Issues 登记完成；**不**自动等于批准软件方案。
- **READY_FOR_IMPLEMENTATION**：待决事项按治理流程处理，Stage B 明确后才能进入实现。
- **SUPPORTED**：必须另有软件完整验收证据，不能仅凭 Mapping 宣布。

## 与现有目录的分工
| 目录 | 用途 |
|---|---|
| `standards/mappings/` | 标准原文到软件规则之间的可追溯人工映射、审查、待决事项 |
| `standards/development/scope-63/` | 开发标准定义/规则 JSON 快照，不用来存放未审定 Mapping |
| `data/definitions/` | 已发布标准定义，绝不由 Mapping 草稿自动覆盖 |
| `knowledge/` | 专业解释，不能代替 Standard / Rule |
| `STANDARD_ISSUES_REGISTER.md` | 标准**原文本身**的笔误、歧义和冲突固定台账；不把已修复的软件缺陷作为标准问题登记 |

依据：中央 `docs/governance/STANDARD_DEVELOPMENT_GUIDE_V0.1.md`（ACTIVE / EVOLVING）。

**注意：原始国家标准 PDF 依仓库已有来源管理流程独立保管，不直接在本目录提交原文 PDF。**

**台账执行约定（自2026-10-11起）**：每新增一个标准，Mapping中的原文疑义先检查仓库根目录 `STANDARD_ISSUES_REGISTER.md` 是否已有相同问题，再按稳定编号记录“原文事实/技术解释/用户软件决定/官方确认程度/当前实施状态/测试关联”。单纯软件设计取舍写在Mapping或决策文件，不强制登记标准问题，也不为填表制造编号。
