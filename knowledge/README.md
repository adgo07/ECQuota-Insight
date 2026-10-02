# knowledge/ — 能耗限额专业知识沉淀

本目录保存**可长期复用**的能耗限额专业知识。它不是 Calculator 的真值源，也不是规则正文。

## 定位

- 本目录只存放**面向人的专业解释**，不存放业务真值；
- 业务真值链路是：标准原文 / Canonical → Rule → Calculator → Result；
- 知识解释链路是：标准 / Standard Issue / Rule → Knowledge explanation → 用户；
- **两条链路不得混用**：不得把本目录的 Markdown 当作 Calculator 的权威数据源或规则源，**不得在运行时解析 Markdown 决定业务结果**。

## 规则

1. 本目录保存可长期复用的专业知识；
2. 新条目默认状态为 **`DRAFT`**；
3. **不强制**每个任务生成知识条目；没有值得沉淀的内容时允许不产出；
4. 知识不是 Calculator 的真值源；
5. **标准原文事实 / 官方资料 / 专业解释 / 工程实践建议必须区分**，不得把技术判断写成标准明文，也不得把工程经验写成强制标准要求；
6. 具体治理规则见中央 `Qingzhou-contracts` 的 `docs/governance/STANDARD_DEVELOPMENT_GUIDE_V0.1.md`。

## 最小条目字段

当前只要求：

- 标题；
- 状态（`DRAFT` / `REVIEWED` / `PUBLISHED` / `RETIRED`）；
- 类型；
- 适用标准；
- 来源；
- 正文；
- 关联 Standard Issue（如有）。

## 当前明确不做

- 不建立复杂 Schema；
- 不建立知识数据库 / SQLite 知识库；
- 不建立向量数据库；
- 不建立 RAG 或 AI Chat；
- 不建立知识中心 UI；
- 不为了数量批量编造知识文章。

## 允许的知识范围（示例）

- 能耗限额专业概念解释；
- 参数和数据如何取得；
- 计算和判定解释；
- 标准理解和争议；
- 工程实际操作建议；
- 常见问题与典型错误；
- 软件字段如何理解；
- 现场资料通常在哪里取得。

## 关联本仓文件

- 标准问题与解释台账：`STANDARD_ISSUES_REGISTER.md`（保持独立，不合并进本目录）；
- 判定口径：`docs/统一判定规范.md`；
- Numeric adoption 证据：`docs/governance/NUMERIC_V1_ADOPTION_REPORT.md`。
