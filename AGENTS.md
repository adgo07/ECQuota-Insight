# AGENTS.md — ECQuota-Insight

本文件补充当前仓库的执行治理，不覆盖既有 `HANDOFF.md`、README、标准原文、用户已确认业务口径和其他有效项目结论。

## 1. 项目定位

本仓库是青舟工业能源软件体系中的单位产品能耗限额评价业务仓库。

永久 Module ID：

```text
qz.energy_quota
```

当前仍独立开发、独立安装、独立升级、独立离线运行。

## 2. Qingzhou Contracts 上位治理

本项目受 `Qingzhou-contracts` 公共架构与 Contract 治理约束。

公共规范权威仓库：

`https://github.com/adgo07/Qingzhou-contracts.git`

当前批准基线必须以本仓库以下文件为准：

- `PLATFORM_BASELINE.md`
- `platform-lock.json`

当前是 **pre-release / bootstrap baseline**。中央仓尚无正式 Contract release/tag，因此本项目锁定的是已经合并批准的精确 commit SHA；不得虚构 release/tag。

## 3. 版本锁定规则

1. 不得实时采用或运行时依赖 `Qingzhou-contracts/main` 最新内容；
2. 中央仓后续 commit 默认不会自动对本项目生效；
3. 只有显式升级 `PLATFORM_BASELINE.md` 与 `platform-lock.json` 后，新公共 Contract 才进入本项目基线；
4. 有正式 release/tag 后，应锁定 release/tag + 对应精确 commit SHA；
5. 升级公共 Contract 后必须运行适用的公共 Conformance 和本项目完整回归；
6. DRAFT Contract 必须明确标识为 DRAFT，不得描述成 FROZEN 或正式稳定 Contract。

## 4. 权威边界

- 标准原文、正式修改单和更具体的法定/标准专属要求不得被通用公共 Contract 覆盖；
- Qingzhou Architecture FROZEN 约束长期公共边界；
- 已发布 Contract/Schema 在本项目显式升级后约束对应公共语义；
- 当前 DRAFT Contract 只作为锁定 bootstrap baseline 的试点参考；
- 普通业务问题、产品 Bug、单标准专属公式、专属 UI、产品内部实现继续在本仓解决；
- 公共 Contract 不得覆盖当前业务模块合法自治范围。

如本仓现有治理与上位 FROZEN 规范存在冲突：

> 不得偷偷改掉现有治理或业务行为。先在 `PLATFORM_BASELINE.md` / `docs/governance/PLATFORM_ADOPTION_REPORT.md` 记录偏差，再通过独立任务处理。

## 5. 公共 Contract 缺口与 RFC Candidate

如果问题同时影响三个产品、多平台公共语义或以下公共能力：

- Numeric / Unit；
- Module / Capability；
- Canonical / qzpack；
- Workspace / Attempt / Record / Result；
- Conformance；
- 公共版本兼容与迁移；

不得在本项目永久私自定义一套同名不同义的公共规则。

应：

1. 记录 RFC candidate；
2. 写明当前产品真实案例、影响 Contract 和兼容性；
3. 由总负责人决定是否提交 `Qingzhou-contracts` RFC/ADR；
4. 本仓仅允许明确、可逆、不会冒充公共规范的局部试验。

本项目不得直接修改 Qingzhou-contracts 正式 Contract，除非任务明确切换到公共仓治理流程。

## 6. 当前已知上位偏差

当前至少存在以下已记录偏差：

- 本仓 `docs/统一判定规范.md` 的全局 ROUND6 比较规则，与 Qingzhou Architecture V2.1 FROZEN 的默认 full-value comparison / 禁止 implicit rounding 原则存在硬冲突；
- Module/Capability Manifest 尚未正式实施；
- Workspace/Attempt/Record/Result 公共外围仅部分具备；
- 现有 `.uebench` 包不是正式 qzpack v1；
- Unit Contract 与平台无关 Conformance Vectors 尚未正式实施。

详见：

- `PLATFORM_BASELINE.md`
- `docs/governance/PLATFORM_ADOPTION_REPORT.md`

未经独立任务批准，不得在普通业务修改中顺手解决这些偏差。

## 7. 当前接入不要求业务重构

QZC-A01 以及后续普通 Contract baseline 升级任务不得默认要求：

- 修改业务公式；
- 修改 Canonical 标准数据；
- 修改 evaluator/calculator；
- 重写业务 UI；
- 迁移数据库；
- 抽公共 Python package；
- 合并三个仓库；
- 启动 Suite；
- 开始 Android/HarmonyOS/iOS；
- 将所有算法 DSL 化；
- 全量 qzpack 化；
- 为统一架构重写成熟 UI。

## 8. 当前仓执行原则

开始任务前至少检查：

1. `AGENTS.md`
2. `PLATFORM_BASELINE.md`
3. `platform-lock.json`
4. `HANDOFF.md`
5. 与任务相关的本仓业务规范

如任务涉及公共 Contract，再读取锁定 SHA 对应的 Qingzhou-contracts 文件，不得直接按中央仓当前最新 `main` 猜测规则。
