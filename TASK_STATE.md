# TASK_STATE

更新时间：2026-09-28

## 当前任务

`QZC-A01 — 接入 Qingzhou-contracts 公共治理`

工作分支：

```text
chore/qingzhou-contracts-adoption
```

基线业务仓 main：

```text
d857f70acbc476f30decc2e0bd367d692a1447d1
```

## Qingzhou Contracts 锁定基线

公共仓库：

```text
https://github.com/adgo07/Qingzhou-contracts.git
```

当前无正式 release/tag，采用：

```text
baseline: pre-release / bootstrap
commit: 0cd74d783fa23add6dc881b408a8c8ba8503f8e8
architecture: 2.1 FROZEN
contracts: draft-v1 / DRAFT / NOT YET RELEASED
```

本仓库不会自动跟随中央 `main`。

## 当前接入状态

已建立/计划在本分支建立：

- `PLATFORM_BASELINE.md`
- `platform-lock.json`
- `AGENTS.md` 上位治理关系
- `docs/governance/PLATFORM_ADOPTION_REPORT.md`
- HANDOFF 最小同步

本任务不修改业务算法、Canonical 标准数据、UI、数据库 schema/migration、标准包实现或公共 Contract。

## 已知 BLOCKED 点

### QZC-A01-B01 — Numeric Governance Conflict

本仓当前 `docs/统一判定规范.md` 要求全部数值边界比较先 `ROUND(value, 6)`；Qingzhou Architecture V2.1 FROZEN 要求默认 full-value comparison，并禁止无标准依据的 implicit rounding。

本任务只记录，不修复。

因此：

> 治理接入文件可以建立，但在该冲突解决前，不得把 ECQuota 描述为已完全符合 Qingzhou Numeric / Architecture V2.1。

## 后续

- 完成 Adoption Report；
- 最小同步 HANDOFF；
- 核对最终 diff 仅包含治理文件；
- 不自动合并 main；
- 数值冲突由独立后续任务处理。
