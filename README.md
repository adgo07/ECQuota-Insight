# 单位产品能耗对标软件

## 最新源码状态（2026-09-27）

仓库：<https://github.com/adgo07/ECQuota-Insight>。

- Phase 0“GB 29446 Golden Case 冻结与基线闭环”在独立分支 phase0-gb29446-golden-case 上实施，基于主线 d857f70acbc476f30decc2e0bd367d692a1447d1。当前分支工作尚未合并或正式发布；以 docs/GB29446_GOLDEN_CASE.md 和最新验收记录为准。
- GB 29446—2019 唯一业务公式为 e_d = E_d × k / m；两侧按 ROUND(..., 6) 判级；超过三级限额统一显示“未达标”。12 个附录A系数和两个煤种的等级边界以 canonical JSON 与 Golden fixture 锁定。
- 选煤专用表单采集核算周期、煤种、工艺、E_d、m、可选企业名称和备注；k 从正式规则只读匹配。计算和判级均由 Engine 返回。
- 正式 dist/release 保持未改动。Excel 与便携程序 Candidate 仅保存在忽略的 work/ 隔离目录，现有 Excel parity 和 Candidate 哈希见 Golden Case 文档；Microsoft Excel/Qt 桌面烟测仍受桌面自动化授权阻断。
- 其他标准保留现有范围和发布状态，不代表已经完成现场验收。

仓库只上传源码、规则、测试和说明，不上传本机私钥、数据库、标准原文或构建缓存。启动及测试前提见 [仓库使用说明](docs/仓库使用说明.md)。下文交付状态及数量保留历史背景。

仓库只上传源码、规则、测试和说明，不上传本机私钥、数据库、标准原文或构建缓存。启动及测试前提见 [仓库使用说明](docs/仓库使用说明.md)。下文交付状态及数量保留历史背景。

Windows 10/11 x64 单机离线应用。软件依据已发布的强制性能耗限额标准，计算或接收单位产品能耗实际值，并逐指标判定 1 级、2 级、3 级或未达标。

## 开发启动

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m uebench.main
```

## 设计原则

所有标准后续开发和完善须遵循 [统一判定规范](docs/统一判定规范.md)。GB 29446 Phase 0 的范围、样例和交付状态见 [Golden Case 基线说明](docs/GB29446_GOLDEN_CASE.md)。

- 标准原文及修改单优先于目录和汇编。
- 所有数值使用 `Decimal`，规则不执行任意 Python 代码。
- 每个指标单独判级，不生成总体等级。
- 已完成评价保存规则快照，标准更新不改写历史结果。
- 运行时不依赖原始资料盘符。

## 当前交付状态

- 正式范围为用户确认的 47 项强制性标准，共 753 条当前指标。GB 29435-2025 的51条规则已于2026-09-09由王玮明确批准转正；其中7条原文存在缺级或非单调限额，已保留警告并禁止静默修正。GB 29447-2022 已由 GB 29447-2026 替代，并新增 GB 47834-2026、GB 47835-2026。
- 当前正式标准包为 `initial-standard-package-published.uebench`。候选包仅用于留档，不应再用于正式判定。
- 当前开发基线为 `standards/development/scope-63`，共63项标准定义，其中47项已发布、16项仍为草案；`standards/development/scope-65` 仅作历史对照，禁止作为发布入口。草案须完成原文复核和确认表确认后才能发布。
- 运行 `python tools/publish_confirmed_rules.py --help` 查看确认表发布命令；未加 `--apply` 时只校验不修改。
- 对隔离草案先运行 `python tools/review_confirmed_rules.py --help`；只有确认表完整后才能将 draft 提升为 reviewed，再生成标准包。
- Windows 用户可双击交付目录中的 `验收助手.cmd`，先完成文件完整性检查；它不会修改规则或数据库。
- 详细操作见 [`docs/用户手册.md`](docs/用户手册.md) 和 [`docs/验收记录.md`](docs/验收记录.md)。
