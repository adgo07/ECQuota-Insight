# 单位产品能耗限额评价软件（ECQuota / `uebench`）

仓库：<https://github.com/adgo07/ECQuota-Insight>（Module ID `qz.energy_quota`）

## 当前产品目标

> **下一正式版必须完整支持 GB 29446—2019《选煤电力消耗限额》。**

| 项目 | 值 |
|---|---|
| Reference Standard | `GB 29446—2019 选煤电力消耗限额` |
| 总体开发路线 | [`参考标准开发路线.md`](参考标准开发路线.md)（唯一路线入口） |
| 当前任务 | [`TASK_STATE.md`](TASK_STATE.md) |
| 当前交接 | [`HANDOFF.md`](HANDOFF.md) |
| 治理基线 | [`PLATFORM_BASELINE.md`](PLATFORM_BASELINE.md)、[`platform-lock.json`](platform-lock.json) |

## 当前开发源码 / Current Development Source

- 以执行时实际 `main` SHA 为准；不要凭文档记忆 SHA。
- 当前正在开发下一正式版，目标是完整支持 GB 29446。
- 普通用户无需管理标准包；标准库随完整软件版本配套更新。Excel Adapter 技术能力保留，Excel 正式用户流程暂缓开放。
- **RS05 当前阶段为 Product Simplification & Standard Library Pairing（IN PROGRESS）；不把旧 EXE / 安装包冒充为当前源码 Candidate，也不据此发布 0.2.0。**

### 上一正式发布物 / Previous Release

- `UEBench 0.1.0`
- standard package `2026.09-published.2`

> 这是历史已发布版本，**不代表当前 main 源码**。其构建时间早于当前 GB 29446 与 Numeric v1 源码变更，因此不能用于验证当前源码行为。
> 交付物清单与历史哈希见 [`docs/交付清单.md`](docs/交付清单.md)、[`docs/安装发布说明.md`](docs/安装发布说明.md) 与 [`docs/验收记录.md`](docs/验收记录.md)（历史验收台账）。

## 开发启动

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m uebench.main
```

启动及测试前提见 [仓库使用说明](docs/仓库使用说明.md)。

## 当前 Numeric 规则

- 正式语义为 **Decimal full-value exact comparison**，不执行全局 ROUND6；显示精度不参与判级。
- 项目 Numeric Profile：`ECQUOTA_DECIMAL_FULL_VALUE_V1`。
- **历史口径（已废止）**：早期版本对等级边界两侧执行 `ROUND(value, 6)` + `ROUND_HALF_UP`。该无依据全局 ROUND6 已由 Numeric Contract v1 Full Adoption 移除（`D-ECQ-001` 已关闭）；仅在标准原文或正式 Rule 显式要求修约时才允许 explicit rounding。
- 当前权威来源：[`platform-lock.json`](platform-lock.json)（locked SHA）、[`docs/统一判定规范.md`](docs/统一判定规范.md)、[`docs/governance/NUMERIC_V1_ADOPTION_REPORT.md`](docs/governance/NUMERIC_V1_ADOPTION_REPORT.md)。

## 设计原则

所有标准后续开发和完善须遵循 [统一判定规范](docs/统一判定规范.md)。

- 标准原文及修改单优先于目录和汇编。
- 所有数值使用 `Decimal`，规则不执行任意 Python 代码。
- 每个指标单独判级，不生成总体等级。
- 已完成评价保存规则快照，标准更新不改写历史结果。
- 运行时不依赖原始资料盘符。

## 当前交付范围

- 正式范围为用户确认的 47 项强制性标准，共 753 条当前指标；开发基线 `standards/development/scope-63` 共 63 项，其中 16 项仍为草案。
- GB 29435-2025 的 51 条规则已成为 `published`，但生命周期为 `future`，实施日期 2027-01-01 前只能预览。
- 其中 7 条原文存在缺级或非单调限额，已保留警告并禁止静默修正。
- GB 29447-2022 已由 GB 29447-2026 替代，并新增 GB 47834-2026、GB 47835-2026。
- 当前开发基线为 `standards/development/scope-63`；`standards/development/scope-65` 仅作历史对照，禁止作为发布入口。

## 常用命令

- 规则确认与发布：`python tools/publish_confirmed_rules.py --help`（未加 `--apply` 时只校验不修改）。
- 隔离草案复核：`python tools/review_confirmed_rules.py --help`。
- 运行测试：`python -m pytest -q -p no:cacheprovider --basetemp <可写临时目录>`。

## 阅读顺序

1. `AGENTS.md`（执行治理）
2. `TASK_STATE.md`（当前任务）
3. `参考标准开发路线.md`（当前路线）
4. `STANDARD_ISSUES_REGISTER.md`（标准问题）
5. `platform-lock.json`（治理基线）
6. 当前任务直接相关的代码 / 测试

Numeric 任务再读 `docs/统一判定规范.md`。历史资料（`docs/history/`、`docs/audits/`、`docs/验收记录.md`）按需读取，**不属于默认必读**。
