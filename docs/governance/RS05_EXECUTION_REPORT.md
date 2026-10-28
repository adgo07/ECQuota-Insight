# ECQ-RS05 执行报告 — Windows V1 Release Candidate

> **2026-10-28 最新补录：** `rc-69562ee` 的 12 项原生短定向复验及设计独立复核通过，两项 P3 在此范围关闭；实际构建源码仍为 `69562eed5d072b9a1a1a77ab6a71f63ea0196788`。本次仅治理补录，不重打包；最新证据与剩余环境条件见本文末节。下方 10-27“新包待构建／待复验”为历史状态。PR #34 仍为未合并草稿，RS05 IN PROGRESS、产品 PARTIAL、0.2.0 未发布。

> **当前交付状态更新（2026-10-27）：** PR #33 已合并到 main `77665b87c9f1ff77c24d26fa5ffbd057c1d12cee`；`rc-3bfbbeb` 已有 Win11 原生 150% 实包业务链证据，两处提示问题已在 `96aa3cb` 源码修复，新包待构建及原生复验。下文早期“无 Win11 环境”、旧候选的 PASS／BLOCKED 和“未合并”等均只描述各自日期及版本，不能直接作为当前环境或最终候选结论。最新状态、缺口和证据边界见本文末节“2026-10-27 rc-3bfbbeb 实包结果与提示修复衔接”。RS05 仍 IN PROGRESS，0.2.0 尚未正式发布。

状态：**`RS05 = IN PROGRESS / RELEASE CANDIDATE`**
目标版本：**`UEBench 0.2.0`**
本报告不宣布 `RS05 = DONE`，也不宣布 `UEBench 0.2.0 = RELEASED`。

---

## 1. 基线与仓库身份

| 项目 | 值 |
|---|---|
| 仓库 | `https://github.com/adgo07/ECQuota-Insight.git`（`git remote get-url origin` 实测一致） |
| Base 分支 | `main` |
| Base SHA | `fb91ccc6f85791bcaf9751c5681cc00c5a0ed213` |
| 执行前核实 | `git fetch origin --prune` 得 `810c0c7..fb91ccc`；`origin/main` = `fb91ccc6f85791bcaf9751c5681cc00c5a0ed213`，**与任务书给定 Base 完全一致** |
| 执行分支 | `feat/ecq-rs05-windows-v1-release` |

Base 上 RS04（PR #12）已合入，因此本阶段的起点包含 `GB29446 Product Golden = ADOPTED (v1)`。

---

## 2. 平台 / Contract 预检查

| 项目 | 结果 |
|---|---|
| `platform-lock.json` | 锁定中央 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`（`auto_follow_main: false`），**未修改** |
| 中央 Frozen（locked SHA） | Architecture V2.1；Numeric Contract v1；Numeric Profiles v1；Numeric Conformance Vector v1 |
| 中央 ACTIVE Guide | 按 `docs/GUIDE_INDEX.md` 路由读取当前正式合并版本（含 Product Delivery Policy v1、UI Guidelines v0.1） |
| 本任务相关 Frozen Contract | Architecture V2.1；Numeric Contract v1（full-value exact、禁止显示值回流与隐式修约） |
| 适用 MUST | 正式产物可追溯；标准包签名必须校验；不得用实现代码反向生成权威期望；历史结果不得重算 |
| 适用 MUST NOT | 不自动跟随中央 `main`；不得把 DRAFT 当已发布 Contract；不得用“确认表”替代正式验证 |
| 是否发现冲突 | 曾发现 1 项本仓 `LOCAL DEFECT` 级治理不一致（固定标准包内 GB29446 定义落后）；已在方案 B 下关闭（见 §5.2A），**不需要修改中央 Contract** |
| 是否需要修改中央 Contract | **否** |
| 相关 Standard Issue | `ECQ-STD-GB29446-001`，**仍为 `PROVISIONAL`**，本阶段**未关闭**、**未**写成官方解释 |
| 本任务是否改变既有软件解释 | **否**（未改 Calculator、Numeric、阈值、标准解释） |
| `D-ECQ-006` | 仍 **OPEN**；本阶段未声称中央 lossless XLSX 公共方案已冻结 |

---

## 3. 已确定的发布决定（按任务书）

| 决定 | 落实 |
|---|---|
| 新版本 `0.2.0` | `pyproject.toml [project] version = "0.2.0"` |
| `pyproject.toml` 为唯一产品版本源 | 见 §4；有版本一致性 Gate |
| Authenticode：`UNSIGNED` | `release-build-info.json` 声明 `authenticode_signed=false` / `unsigned_reason=no_signing_certificate` |
| 最终发布位置：公开 GitHub Release | 本阶段**不**发布；只做 Candidate |
| `D-ECQ-006` 继续 OPEN | 未触碰 |
| `Reference Standard Product Closure` 继续 `PARTIAL` | 见 §9 |
| 不开始 RS06 | 未开始 |

---

## 4. 单一版本源

**权威**：`pyproject.toml` 的 `[project] version`（现 `0.2.0`）。

**生成器**：`tools/release_version.py`

- `--print` / `--names` / `--generate` / `--check`；
- 派生文件（由 `--generate` 写出，`--check` 校验）：
  - `src/uebench/_version.py`（运行时 `__version__`，`src/uebench/__init__.py` 改为从它导入）
  - `packaging/version_info.txt`（PyInstaller 版本资源，**数字元组与字符串两种写法同时生成**）
  - `packaging/version.iss`（Inno Setup 的 `MyAppVersion`）
- `packaging/installer.iss` 改为 `#include "version.iss"`，**不再手写版本号**；
- 产物文件名由 `artifact_names(version)` 统一给出，`tools/audit_release.py`、
  `tools/build_source_zip.py`、`scripts/sync_release.ps1`、`scripts/验收助手.ps1`
  全部改为**读取**而非硬编码；
- `scripts/build_release.ps1` 与 `scripts/sync_release.ps1` 在开工前执行
  `tools/release_version.py --check`，不一致即中止构建。

**版本一致性 Gate**：`tests/test_release_version_consistency.py`（见 §7）。

**刻意不合并的相邻版本域**（不是产品版本，不应跟随 0.2.0）：
`RULE_ENGINE_VERSION`、`NUMERIC_CONTRACT_VERSION`、`TEMPLATE_VERSION`、
`GB29446_EXCEL_TEMPLATE_VERSION`，以及标准包 `minimum_app_version` 默认值
（含义是“标准包要求的最低软件版本”，与产品版本是两个概念）。

---

## 5. 实现内容

### 5.1 统一标准规则确认表 → `LEGACY_REFERENCE_ONLY`

`统一标准规则确认表.xlsx` 已降级，且**不再**：

- 作为 0.2.0 发布正确性依据；
- 作为正式标准包正确性依据；
- 作为 `audit_release` 的 PASS 条件（`tools/audit_release.py` 现在把它单列为
  `legacy_reference_only`，只做信息性报告，**不产生 error**）；
- 作为 installer 必需内容（`packaging/installer.iss` 已删除该 `[Files]` 行）；
- 其“同意发布”**不**代表其余 46 个标准均已正式验证。

RS05 的正式正确性声明**只针对已完成 Product Golden 的 GB 29446—2019**。

### 5.2 正式标准包固定为版本化 release input

- 只读来源：`dist/standard-packages/initial-standard-package-published.uebench`
  （原资产**未修改、未重建**，复制后 SHA256 一致）；
- 固定位置：`release/standard-packages/initial-standard-package-published.uebench`；
- 固定记录：`release/standard-packages/PIN.json`；
- `uebench.spec` 改为从固定位置打包，使 **clean checkout 也可构建**。

实测（独立核实，非引用文档）：

| 项目 | 值 |
|---|---|
| size | `21320540` |
| SHA256 | `4f025b8a45f03fc5539b2d5eb76bdf6c3d127b863e7485b46fbb100b6f221727` |
| data_version | `2026.09-published.2` |
| package_id | `initial-47-current-plus-history-published-20260909` |
| package_mode | `full` |
| standard_count / rule_count | `48` / `765` |
| issued_at | `2026-09-09T01:41:17.924310Z` |
| 签名 | `signature.ed25519`；用 `src/uebench/resources/update_public_key.pem` 经
  `context.application.install_package()` 在隔离数据目录**实际安装成功**，签名校验通过 |

### 5.3 升级前自动备份

见 §6.1。

### 5.4 Installer 覆盖安装清理

`packaging/installer.iss` 新增 `[InstallDelete]`：

```ini
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\{#MyAppExeName}"
Type: filesandordirs; Name: "{app}\文档"
Type: filesandordirs; Name: "{app}\模板"
```

原因：`DefaultDirName={autopf}\UEBench` 不带版本，且所有 `[Files]` 都是
`ignoreversion`，因此旧版本留下的文件（尤其是整个 `_internal`，其中含
`_internal\migrations`）不会被覆盖删除。**陈旧的 `_internal\migrations` 会让新
可执行文件用旧迁移脚本建库**，比外观不一致严重得多。

范围严格限定在 `{app}`；**不引用** `%LOCALAPPDATA%\UEBench`，因此升级与卸载都
不会删除用户数据（见 §5.6）。

### 5.5 单条损坏历史记录

见 §6.2。

### 5.6 用户数据与卸载

- 数据目录 `%LOCALAPPDATA%\UEBench\`（`uebench.sqlite3` + `-wal` / `-shm`、
  `standards\`、`backups\`、`logs\`、`imports\`）；
- installer 不写、不删该目录；
- 卸载只删除 Inno 记录在 `{app}` 下的文件，用户数据保留；
- 安装 → 建记录 → 卸载 → 数据仍在 → 重装 → 记录恢复（验证见 §7）。

### 5.7 同源 payload 清单

- `tools/build_payload_manifest.py` 对 `dist/UEBench` 逐文件记录
  `path` / `size` / `sha256`，并生成 `payload_tree_sha256`
  （对排序后的 `"{sha256}  {size}  {path}\n"` 取 SHA256）；
- portable ZIP 与 installer **同源于同一次 `dist/UEBench`**；
- `tools/audit_release.py` 从交付目录的 portable ZIP **重新推导**同样的三元组并与清单
  逐项比对，从而证明 ZIP 确实是被审计载荷树的忠实副本。

已用独立实验验证该机制：干净树 `matches_zip=True`（418 个文件、tree hash 相等）；
对其中一个文件注入 1 字节篡改后 `matches_zip=False`，报
“便携包文件与 payload 清单哈希/大小不一致：['UEBench.exe']”。

### 5.8 Excel 正式交付模板（无头、确定性）

- `tools/build_release_templates.py` 通过**真实** `ApplicationFacade` /
  `WorkbookTemplateService` 在隔离数据目录无头生成，**不需要人工打开 GUI 另存**；
- 生成后做确定性归一化（固定 ZIP 成员时间戳、固定 `docProps/core.xml` 日期），
  因此可字节复现；
- `--check-determinism` 生成两次并断言字节一致 —— **实测通过**；
- 交付：`GB29446选煤电力消耗限额导入模板.xlsx`（必需）；
- 确认表**不**随普通用户 release 交付。

### 5.9 Source Gate / Artifact Gate 分离

- 旧 `tests/test_frozen_release.py` 是**唯一**依赖 `dist/` 的测试，且在干净 checkout 上
  **必然硬失败**（第 12 行 `assert archive.exists()`），两个 workflow 因此不得不
  `--deselect` 它、并另写步骤去“证明它在 base 上也失败”。这被 RS03/RS04 记为
  historical release asset failure 并留给 RS05。
- RS05 将其拆分为：
  - **Source Gate** `tests/test_release_source.py`：只断言源码/config 可证明的事情；
    没有产物时明确 `SKIP + reason`；
  - **Artifact Gate** `tests/test_release_artifacts.py`：仅在显式声明产物目录
    （`UEBENCH_ARTIFACT_DIR`）时启用；一旦声明，产物缺失**必须 FAIL**。
- 两个既有 workflow 的 `--deselect` 与“证明 base 失败”步骤在同一次改动中移除。

### 5.10 打包后自检入口

见 §6.4。

### 5.11 独立的 Windows Release Candidate workflow

见 §8。

---

### 5.2A 方案 B：只替换 GB29446 定义的新正式标准包（已批准并执行）

项目负责人批准**方案 B**，约束为：不得依据 `统一标准规则确认表.xlsx` 重建全部规则；
以已签名 `2026.09-published.2` 为**父基线**，只把经 RS04 验证的 GB29446 由 r1 替换为当前 r2；
其余标准内容必须保持不变；生成并本地签名新的**完整**正式标准包，设新 `data_version`。

执行方式：`tools/build_gb29446_package_revision.py`

- **不**经过 `StandardPackageBuilder.build()`。该方法会把每个定义重新过一遍当前 pydantic
  模型再序列化，可能静默改变其余 46 项标准的字节；本工具改为**逐个成员从父包原样复制**，
  只替换 GB29446 定义成员，然后重新签名 manifest。
- 全程**未读取也未使用**确认表，未从该表重建任何规则。

结果（父包 `4f025b8a…1727` → 新包 `14db53be…32b0`）：

| 项目 | 值 |
|---|---|
| 新 `data_version` | `2026.10-published.3` |
| 新 `package_id` | `gb29446-r2-from-2026.09-published.2` |
| `package_mode` | `full` |
| `standard_count` / `rule_count` | `48` / `765`（均未变） |
| 移除成员 | `definitions/gb-29446-2019-2019.json`（旧 r1） |
| 新增成员 | `definitions/gb-29446-2019-2019-r2.json`（新 r2） |
| **`changed_members`** | **`[]`（空）** |
| 逐字节未变成员数 | 96 |
| `minimum_app_version` | `0.1.0` → `0.2.0`（见下） |

独立验证（不是自述，均为实测）：

1. **同源校验**：除上述一个定义成员外，父包与候选包每个成员逐字节一致（`changed_members` 为空）。
2. **签名校验**：用 `update_public_key.pem` 经 `install_package()` 在隔离数据目录安装成功。
3. **安装后逐项对比**：新包安装出的 48 项标准中，除 GB29446 外其余 **47 项与父包定义逐字节一致（差异数 0）**。
4. **GB29446 安装后 `rule_revision = 2`** 且 `selection_schema` 含 `coal_type`。
5. **RS04 Product Golden 对已安装新标准包回放：15 例全部通过**（含 `5.0000004 → 2级` 的 full-value trap），
   且 Applicability Gate 由原来的 `2 vs 1 FAIL` 变为 **PASS**。

两项需要明示的判断（非标准内容，属清单元数据）：

- **`minimum_app_version` 由 `0.1.0` 提升为 `0.2.0`**：新 GB29446 r2 使用只有 r2 才引入的
  煤种选择 schema 与专属模板，0.1.0 应用无法正确处理；提升该下限可阻止旧应用安装不兼容的标准包。
  这是除 GB29446 定义外**唯一有意偏离**父基线的字段，已记录在 `PIN.json` 的 `notes`。
- **`parent_package_id` 无法写入完整包 manifest**：`PackageManifest.validate_lineage` 规定
  `package_mode == "full"` 时该字段必须为 `None`，因此父基线关系记录在
  `release/standard-packages/PIN.json` 的 `parent_baseline` 中。

父基线未被修改，完整保留为
`release/standard-packages/initial-standard-package-2026.09-published.2.uebench`
（SHA256 `4f025b8a…1727`），供逐字节复核。

### 5.12 Windows 验收工具不得由显示器数量推断 PASS（已修正）

原 `tools/windows_acceptance_evidence.ps1` 在检测到 `screen_count >= 2` 时直接判
「多显示器拖动窗口 = PASS」，这属于**由环境推断结论**，不是实测。已改为：

- 有 2 个及以上显示器且**未**提供实测声明 → `PENDING-MANUAL`，并明确写出
  “本工具不因显示器数量判定通过”；
- 仅在操作者显式传入 `-CrossMonitorDragVerified [-CrossMonitorDragNote <说明>]`
  时才记 `PASS`，并注明该结论来自操作者实测声明；
- 不足 2 个显示器 → `BLOCKED`。

本机 1 显示器实测输出仍为 `BLOCKED`，未出现任何自动 `PASS`。
---

## 6. 逐项结果

### 6.1 升级前自动备份

（由 RS05 独立工作流实现，结果见 §7 测试记录。）

### 6.2 单条损坏历史记录

（同上。）

### 6.3 0.1.0 → 0.2.0 升级

真实 0.1.0 资产（只读取证，未修改）：

| 文件 | size | SHA256 |
|---|---|---|
| `dist/release/UEBench-0.1.0-win-x64.zip` | 176480046 | `424af9e445264702b5b43f36c0f8346dad0855b9dd88d80028f5d50780d785b4` |
| `dist/installer/UEBench-Setup-0.1.0-x64.exe` | 127023093 | `234bb4b00c3ca3ea3d992b5ed3f5e3ee2ef9f01343680ee96819a98ae248a911` |
| `dist/UEBench-0.1.0-win-x64.zip` | 342077067 | `5fdae95b62f9550fafdd68cae2406a8aba78cb1f4a802f234f79e9298201d30a` |
| `dist/UEBench-source-0.1.0.zip` | 409695 | `b32ea38c6944d3079a4b6617022b5b6e4562d70401bbd95f724cd9d6c437c48d` |
| `dist/standard-packages/initial-standard-package-0.1.0.uebench` | 26539314 | `481160bcaf5a064c7ac661829816fbdec4212cee447107741748cc822a8b1384` |

**交叉印证**：前两项 SHA256 与仓库历史记录
`docs/history/legacy/HANDOFF_LEGACY_2026-09.md:280-281` 中登记的
`424af9e4…` / `234bb4b0…` **完全一致**，说明本机 `dist/release` 确为该历史正式交付物，
不是重新构建的替代品。

只承诺 `0.1.0 → 0.2.0`。合成 fixture 的构造与验证结果见 §7。

### 6.4 Candidate self-check

契约（详见 `--self-check` 帮助与实现文档）：

```text
UEBench.exe --self-check --output <json> --data-dir <isolated dir>
```

- 不依赖系统 Python；不启动普通 GUI；不使用第二套计算算法；
  调用真实 Application / Domain / Repository；使用同一 RS04 Golden；isolated 数据目录；
  有明确 exit code。结果见 §7。

---

## 7. 测试记录

全部结果来自最终源码（本报告所述 final head）实际运行，basetemp 使用 `$env:TEMP`
（仓库 `work\` 目录存在 ACL 怪癖，会使 SQLite 写入慢约 200 倍）。

### 7.1 literal full suite

```text
python -m pytest -q -ra -p no:cacheprovider --basetemp <TEMP>
tests = 736   passed = 687   failures = 0   errors = 0   skipped = 49   exit = 0
```

`skipped = 49` 包含 4 个既有 strict XFAIL（N01-A legacy ROUND6 证据）与 45 个
**按设计跳过**的项（Artifact Gate 未声明产物目录时的精确 SKIP、以及需要 git 跟踪
固定输入的用例）。**无 failed、无 error。**

### 7.2 新增 Gate 与测试

| 文件 | 结果 |
|---|---|
| `tests/test_release_version_consistency.py` | **57 passed** |
| `tests/test_release_source.py` | **16 passed** |
| `tests/test_release_artifacts.py`（未声明产物目录） | 36 collected：11 passed + 25 SKIP（精确理由） |
| `tests/test_release_artifacts.py`（`UEBENCH_ARTIFACT_DIR=dist\release`） | **58 passed, 0 failed, 0 skipped** |
| `tests/test_migration_backup.py` | **7 passed** |
| `tests/test_corrupted_records.py` | **17 passed** |
| `tests/test_self_check.py` | **13 passed** |
| `tests/test_upgrade_0_1_0_to_0_2_0.py` | **9 passed** |
| `tests/test_document_hygiene.py` | 2 passed（阶段状态词表已扩展为包含 `IN PROGRESS / RELEASE CANDIDATE`） |

Artifact Gate 不只是“绿”：独立工作流在真实合成 Candidate 上运行得 58 passed，并对
10 种注入（ICU 注入、篡改 manifest、伪造 installer、坏模板、虚假签名声明、
helper 硬编码旧版本、篡改产物内容、篡改 SHA256SUMS 行、缺产物、空目录/缺目录）
逐一验证**均被检出**，未检出的注入为 **0**。

### 7.3 既有 Gate 未回归

RS01 / RS02 / RS03 / RS04 Product Golden / Numeric v1 / N01-A / Generic Excel /
Architecture / Document hygiene 全部在 literal full suite 内通过。
`test_gb29446_product_golden.py`（Gate A–D）保持通过；`test_gb29446.py` 的 4 个
legacy XFAIL 仍为 XFAIL（未被 deselect，也未被改成通过）。

### 7.4 打包后可执行自检（冻结 EXE）

```text
dist\UEBench\UEBench.exe --self-check --data-dir <isolated> --output <json>
exit code = 0
```

| 检查 | 结果 |
|---|---|
| `build_info` | passed（product_version `0.2.0`，`qt_imported=false`） |
| `standard_package` | passed（Ed25519 校验通过，48 项标准，`2026.10-published.3`） |
| `database` | passed（schema 初始化到 head） |
| `golden_replay` | **passed** |
| `record_roundtrip` | **passed** |
| `excel_import_chain` | **passed** |

`overall_status = passed`，`failed_checks = []`，`warnings = []`。

> **对照记录**：在方案 B 之前，同一冻结 EXE 自检为 `exit code = 1`，`golden_replay`
> 报「已安装 GB 29446 规则版本为 r1，RS04 Product Golden 要求 r2」，
> `excel_import_chain` 报「评价数据!B6 标准中不存在煤种：炼焦煤」，
> `record_roundtrip` 因无记录而失败。这曾是该阶段唯一的实质 Blocker；
> 换成只替换 GB29446 定义的新签名标准包后全部通过，
> 说明失败根因确实是标准包内容而非软件。
### 7.5 未完成 / 无法验证

- **未用真实 0.1.0 安装包在真实用户数据目录上执行升级**；升级验证使用合成 fixture
  （见 §6.3），只承诺 `0.1.0 → 0.2.0`。
- **未枚举 installer 内部载荷**：本机无 `innounp`/7-Zip，无法列出
  `UEBench-Setup-0.2.0-x64.exe` 内嵌的 `migrations/versions`；installer 的验证依赖
  ISCC 编译日志 + 安装目录与 `payload-manifest.json` 的一致性检查（后者需实机安装）。
- **`scripts/build_candidate.ps1` 未经完整端到端运行**（该工作流自身报告：仅通过
  语法与参数传递冒烟测试）；正式链路是通过 `scripts/build_release.ps1` +
  `scripts/sync_release.ps1` 实际跑通的（见 §7.6）。
---

## 8. CI

（待本轮 push 后由 GitHub Actions 运行结果填写；本文件在 push 前不加猜测值。）

Candidate 构件由 `windows-release-candidate.yml` 在 `windows-latest` 上构建并作为
workflow artifact 上传；该 workflow 的版本与产物名全部取自
`tools/release_version.py`，不含任何版本字面量。
---

## 9. Windows 验收证据

以 `tools/windows_acceptance_evidence.ps1` 记录（只记录事实，不伪造 PASS）。

本机实测环境：

| 项目 | 值 |
|---|---|
| OS | Microsoft Windows 10 专业版 |
| Version / Build | `10.0.19045` / **19045** |
| 架构 | 64 位 |
| Locale | `zh-CN`（UI `zh-CN`） |
| 账户 | `DESKTOP-35VQUAK\WANGWEI`，**非管理员（standard）** |
| PowerShell | `7.6.6` |
| 显示器 | **1 个**（2560×1440，primary） |
| Session | `Console` |

结论：

| 验收项 | 结论 | 依据 |
|---|---|---|
| Windows 10 实机 | **PASS** | Build 19045 |
| Windows 11 实机 | **BLOCKED** | 本机无 Windows 11 环境，**不伪造 PASS** |
| 标准（非管理员）账户 | **PASS** | `is_administrator=false` |
| 多显示器之间拖动窗口 | **BLOCKED** | 仅 1 个显示器 |
| DPI 100/125/150/175/200 五档实测 | **BLOCKED** | 单显示器环境无法逐一实测并跨屏拖动 |
| 离线运行 | `OBSERVED-ONLINE` | 采集时本机可连通外网；离线断言需在断网验收机复测 |

> **本节结论：Windows 正式交付证据尚未建立。**
> 此为当时阶段结论；后续本机已取得的 Windows Candidate 证据及尚缺环境门禁，见[2026-10-20 本机执行结果](#2026-10-20-本机执行结果与上述计划分列)。
> Win11 与多 DPI / 跨屏拖动两项如实记为 `BLOCKED`，需在具备相应环境的验收机上补做。

---

## 9A. 执行过程中的问题、修复与事件（如实记录）

### 9A.1 由 literal full suite 捕获的真实回归（已修复）

`tools/release_version.py` 被引入后，`tools/build_source_zip.py`、
`tools/audit_release.py`、`tools/build_payload_manifest.py`、
`tools/write_build_info.py`、`tools/build_release_templates.py` 使用了
`from release_version import ...`。这在**脚本方式**下可行（`tools/` 为 `sys.path[0]`），
但测试以 `tools.build_source_zip` 方式导入时 `ModuleNotFoundError`，
导致 `tests/test_source_zip.py` **collection error**、整个 full suite exit 2。

- 发现方式：literal full suite（`exit=2`，`ERROR tests/test_source_zip.py`）。
- 修复：五个工具改为双模导入（`try: from release_version import ... except ModuleNotFoundError: from tools.release_version import ...`），并用两种导入方式各自实测。
- 复验：`pytest tests/test_source_zip.py tests/test_release_source.py` 通过；full suite 恢复 green。

### 9A.2 阶段状态词表扩展（`test_document_hygiene.py`）

该测试原本只承认 `DONE | NOT STARTED | PARTIAL | BLOCKED`。RS05 任务书要求本阶段
只能写 `RS05 = IN PROGRESS / RELEASE CANDIDATE`，该措辞对原有词表不可表达，导致
三份稳定文档的阶段状态校验失败。处理：把 `IN PROGRESS / RELEASE CANDIDATE` 加入
词表（单一常量 `_STATE`），**保留**跨文档一致性断言这一核心价值；同时移除稳定文档中
该测试明令禁止的措辞（`等待独立验收` / `等待合并` / `不合并 PR`）。

### 9A.3 并发构建竞争（已定位）

第一次最终构建在 PyInstaller COLLECT 阶段以
`OSError: [WinError 145] 目录不是空的。: dist\UEBench\_internal\PySide6` 失败。
根因不是环境 ACL，而是**两个构建同时作用于同一个 `dist\UEBench`**：另一个工作流在
冒烟测试 `scripts/build_candidate.ps1` 时删除并重建了 `dist\UEBench`。
修复：改为串行执行，并在构建前用带重试的健壮清理；第二次构建 exit 0。

### 9A.4 历史 0.1.0 资产被改写（已记录，影响有限）

一个工作流在探针迭代中向 `dist\release\UEBench-0.1.0-win-x64.zip` **追加**了一个测试
条目，改写了该文件；随后它从 `work/migration-backup-20260830/dist-release/` 的同名副本
恢复，但**恢复得到的是同一 0.1.0 便携版的 2026-08-29 构建，不是被改写前的字节级原件**，
因此 `dist/release/SHA256SUMS.txt` 中该行不再匹配。

影响评估（已实测）：

- `dist/` 是 **git-ignored 且未跟踪**，**没有任何已提交产物受影响**；RS05 的 0.2.0 交付物无关；
- 用于报告与夹具 provenance 的 0.1.0 证据中，**稳定且未受影响**的有：
  `dist/UEBench-0.1.0-win-x64.zip` = `5fdae95b…1d30a`（342,077,067 B）、
  `dist/installer/UEBench-Setup-0.1.0-x64.exe` = `234bb4b0…a911`（127,023,093 B）、
  `dist/standard-packages/initial-standard-package-0.1.0.uebench` = `481160bc…1384`、
  `dist/standard-packages/initial-standard-package-published.uebench` = `4f025b8a…1727`；
- 被改写的那个文件的原哈希 `424af9e4…d785b4` **完好保存在 git 跟踪的历史文档**
  `docs/history/legacy/HANDOFF_LEGACY_2026-09.md:280`，且同文件第 281 行的安装程序哈希
  `234bb4b0…a911` 与本机现存 `dist/installer/UEBench-Setup-0.1.0-x64.exe` **完全一致**，
  因此历史事实仍有权威佐证；
- `scripts/sync_release.ps1` 会在组装时清理 `UEBench-*-win-x64.zip` 等旧命名，
  该文件不出现在 0.2.0 交付目录中。

**教训**：探针不得对仓库内既有资产做写操作。后续任何探针必须使用 scratch 副本。

### 9A.5 载荷中夹带 `migrations/**/__pycache__/*.pyc`（未修复，非阻塞）

ISCC 编译日志显示 `dist\UEBench\_internal\migrations\versions\__pycache__\*.pyc`
被一并打包。功能上无害（同目录的 `.py` 源码存在且更新时会优先），且 §5.4 的
`[InstallDelete]` 已消除跨版本陈旧风险；但作为发布卫生问题应当清理。
精确定位：`uebench.spec` 的 `datas` 以目录方式整体复制 `migrations`，未过滤
`__pycache__`。**本阶段未修复**（会要求再次完整重建），如实记录供后续收口。
---

### 9A.6 CI 失败根因：发布工具的 cp1252 控制台（已修复）

首次推送后 `Windows Release Candidate` workflow 在
**"Read the authoritative version and artifact names"** 步骤失败
（run 37144561418）：

```text
File "tools\release_version.py", line 200, in main
    print(f"版本一致性校验通过：{version}")
UnicodeEncodeError: 'charmap' codec can't encode characters in position 0-9
```

根因与前两次完全相同：GitHub Windows runner 的控制台是 **cp1252**，
`print()` 中文即崩溃。这是本项目第三次被同一模式击中（RS03 ingress probe、
RS04 lifecycle probe、本次发布工具）。

修复：`tools/release_version.py` 新增 `ensure_utf8_console()`，
在 stdout/stderr 支持 `reconfigure` 且当前编码非 UTF-8 时改为
`utf-8 + backslashreplace`；六个发布工具（`release_version` /
`audit_release` / `write_build_info` / `build_payload_manifest` /
`build_release_templates` / `build_legacy_0_1_0_fixture`）的 `main()` 开头调用它。
该函数对 pytest 捕获对象与已 UTF-8 的流是**无操作**，因此不会干扰测试捕获。

新增持续回归：`tests/test_release_tools_console.py`（11 passed），
以**真实子进程 + `PYTHONIOENCODING=cp1252`** 运行各工具，
确保未来新增工具若忘记调用会在本地失败，而不是在发布 workflow 里失败。

### 9A.7 Artifact Gate 检出执行者自己造成的发布目录不一致

在执行 cp1252 验证时，我直接以 `--output` 覆盖了 `dist\release\` 内的
`release-build-info.json` 等文件，而 `SHA256SUMS.txt` 未同步重算，
Artifact Gate 随即报出：

```text
FAILED tests/test_release_artifacts.py::test_sha256sums_hash_matches_recomputed[source]
FAILED tests/test_release_artifacts.py::test_audit_release_reports_valid
```

重新运行 `scripts/sync_release.ps1` 后恢复一致（Artifact Gate 58 passed）。
**这说明 Artifact Gate 确实能抓住发布目录被后续动作改坏的情形**，不是形式化绿灯。

同时把 `sync_release.ps1` 的旧产物清理从静默 `-ErrorAction SilentlyContinue`
改为 try/catch + `Write-Warning`：此前它在文件被占用时会打印“已清理”但实际未删除，
属于会误导验收的日志。
---

### 9A.8 Source Gate 曾破坏已构建的 Candidate 产物（已修复）

`tests/test_release_source.py::test_source_zip_default_output_name_is_version_derived`
用 `monkeypatch.chdir(ROOT)` 把工作目录切到仓库根，然后让替身函数向**相对**默认路径
`dist/release/UEBench-source-<版本>.zip` 写入 `b"placeholder"`，
用于让 `main()` 末尾的 `output.stat()` 能取到大小。

后果：只要已经构建过 Candidate，再跑一次 Source Gate 就会把真实的源码包**覆盖成
11 字节的 `placeholder`**。本次执行中实际发生——`dist/release/UEBench-source-0.2.0.zip`
由 1,419,535 字节变成 11 字节，随后由 `scripts/sync_release.ps1` 重新组装修复。
（该缺陷不影响 CI 的 Artifact Gate：CI 上 Source Gate 在构建之前运行，且产物审计针对
`dist/candidate`；但它会污染 `dist/release`，并且会破坏开发机上的候选产物。）

修复：把该测试的 `chdir` 目标由仓库根改为 `tmp_path`（并补上 `tmp_path` fixture），
使相对默认路径落在一次性目录内；断言未削弱（仍要求默认输出名由版本推导且含当前版本）。

验证：运行该测试后 `dist/release/UEBench-source-0.2.0.zip` 的字节数与 SHA256 **不变**；
`tests/test_release_source.py` 16 passed；全量套件运行后该文件同样保持完好。
另已 grep 确认 `tests/` 中不再有指向仓库根的 `chdir`。
---

## 11. Runtime Standard Package Reconciliation & Candidate Identity Closure

本节记录在本分支 `cdbd359` 之上追加的一轮工作，关闭两个 blocker：

1. 软件升级后旧用户数据目录的标准规则不会自动升到当前 bundled package；
2. 不同内容的 Candidate 可以拥有相同文件名与版本资源，人工测试无法可靠区分。

### 11.1 启动期标准包对账（替代一次性初始化）

原 `install_bundled_package()` 只要标准库非空就整体跳过，因此老用户数据库的规则
永远停在旧包。现改为**每次正常启动都执行确定性对账**：

| 情形 | 判定 | 动作 |
|---|---|---|
| A 从未安装过标准包 | 标准库为空 | `INSTALL` 安装内置包 |
| B 内置包与已安装包完全相同 | 同 `package_id` **且** 同 `package_sha256` | `NOOP`（不重复备份、不重复安装、不写审计） |
| C 已安装严格旧于内置 | `_data_version_key` 比较 | `UPGRADE` 安全升级 |
| D 已安装严格新于内置 | 同上 | `NO_DOWNGRADE` 不降级 |
| E 同版本但身份/内容冲突，或任一侧版本无法排序 | — | `CONFLICT` 不覆盖并显式上报 |
| F 内置包验签/清单/文件校验失败 | — | `INVALID` 不安装，存量数据不动 |

实现与约束：

- **没有第二套版本算法**：排序复用既有 `uebench.infrastructure.packages._data_version_key`。
  application 层受架构门禁约束不得导入 infrastructure，故由组合根
  （`main.reconcile_standard_package`）把该实现注入 `PackageReconciliationService`，
  测试注入同一份实现，语义不会分叉。
- **内置包发现是确定性的**：多个候选时按 `data_version` 取最高者，
  而非文件名字典序最后者；无法解析版本的候选不会胜出。
- `preview()` 同时包含**包自身完整性**错误与**依赖当前数据库状态**的安装闸门错误
  （如「该标准包已安装」「禁止降级」）。对账必须区分二者，否则 B/D 会被误判为 F。
  实现把它们分成 `errors`（完整性 → INVALID）与 `install_blockers`（安装闸门 →
  交给决策表处理）。
- **内容冲突不得被当作无害闸门**：`标准版本已存在：…如需变更必须递增标准包/规则版本`
  表示已安装的同 `(standard_id, version, rule_revision)` 行内容不同，属 §三 E 的
  "内容冲突" → `CONFLICT` / `installed-content-conflict`，且**不得**调用 `install()`。
- 决策函数 `decide(installed, bundled, *, data_version_key)` 是纯函数，不访问数据库与
  文件系统，预期情形从不抛异常；结果类型 `ReconciliationOutcome` 可序列化，
  含 `action` / `reason` / 中文 `message` / `executed` / 前后身份 / `backup_path` /
  `standards_installed` / `errors`，并有 `summary()` 供日志与诊断视图复用。
- 桌面启动路径对账失败**只记日志、不阻断界面启动**（对账未成功时也不会对外宣称"已更新"）。

### 11.2 升级数据安全

- 升级前使用**现有**安全备份能力：`StandardPackageService.install` 先经
  `BackupService`（SQLite 在线备份 API，不直接复制活动 WAL）生成
  `pre-package-<时间>.uebackup`；
- 定义写入在**单个数据库会话**内完成，异常时回滚并删除已复制的包目录，
  **不留半升级状态**；
- 历史评价记录及其 `rule_snapshot_json` **不被新规则重算**；
- 未提交任何真实用户数据库；回归全部由已知旧正式包与确定性 fixture 构造。

### 11.3 GB29446 规则不兼容 fail-fast

`gb29446_rule_is_compatible(definition)`：当定义缺少 `coal_type` 选择层级、
或某产品没有非空 `selection_values.coal_type`、或选煤电力单耗指标没有可用
`process_factor` 查表行时判定为不兼容。此时：

- 显示中文「标准规则数据不完整或版本不兼容，请更新标准数据后再评价。」；
- 隐藏并禁用煤种 / 选煤工艺 / 折算系数控件，禁用计算按钮；
- **禁止正式计算与 Excel 导入评价**（在进入 `application.evaluate` 之前返回，
  不产生记录）；
- **不再用 `product.name` 冒充煤种**，也不再给出看似正常但空的工艺下拉框。

正常 r2 路径业务语义与 Golden 完全不变（未触碰 domain engine、数值、阈值与 Golden）。

### 11.4 Candidate 身份与构建溯源

产品版本仍为 **0.2.0**（不因 Candidate 迭代改名），但资产必须唯一可区分：

```text
UEBench-0.2.0-rc-<short7>-win-x64.zip
UEBench-Setup-0.2.0-rc-<short7>-x64.exe
UEBench-source-0.2.0-rc-<short7>.zip
```

- `<short7>` 由构建时的 `git rev-parse HEAD` 推导；CI artifact 名同样携带身份；
- 正式 release cut 才回到不带后缀的名字；
- `packaging/installer.iss` 经 `#ifndef MyAppCandidateSuffix` + ISCC `/D` 注入后缀，
  且不再含任何版本字面量；`version.iss` / `_version.py` / `version_info.txt`
  仍与提交无关（`--check` 通过，`--generate` 结果与提交前逐字节一致）。

`release-build-info.json` 增加必需字段：`product_version`、`candidate_id`、
`source_commit`（完整 40 位）、`source_dirty`、`standard_package_id`、
`standard_data_version`、`standard_package_sha256`、`payload_tree_sha256`、
`build_time_utc`。正式 Candidate 要求 `source_dirty = false`：三个构建脚本默认
拒绝 dirty 工作树，`audit_release` 断言 `source_dirty is false` 且
`payload_tree_sha256` 与 payload manifest 一致，CI 新增步骤断言
`source_commit` 与 workflow exact head 完全一致。

**一处必须解决的循环**：`release-build-info.json` 含 `payload_tree_sha256`，
描述整个应用载荷，因此**不可能**同时位于它所描述的载荷之内。处理方式：载荷内改嵌
**子集** `_internal/uebench/resources/build-identity.json`（同样的身份字段，
**不含** `payload_tree_sha256`），在 PyInstaller 之后、`build_payload_manifest.py`
之前写入，从而它本身也被同源载荷清单覆盖与校验。

### 11.5 应用内诊断信息

菜单「帮助 → 关于 / 诊断信息…」只读展示并可一键复制：产品版本、Candidate 身份、
源码提交（完整 40 位）、`source_dirty`、构建时间、内置/已安装标准包
`package_id` + `data_version` + SHA256、当前 GB29446 `rule_revision`、
数据库 schema 版本（实读 Alembic 版本，不硬编码）、当前数据目录，
以及**最近一次标准包对账**（动作 / 原因 / 中文说明 / 前后身份 / 备份路径）。
不读取也不输出任何私钥材料。当对账未达期望状态时，状态栏给出可关闭的非模态中文提示
（不阻断启动，不改变页面布局）。

### 11.6 单一 ACTIVE Candidate

- 归档前先记录 SHA256 证据，再移动：`dist/candidate` →
  `dist/archive/SUPERSEDED-candidate-2026-10-04-before-identity`，
  并写出 `dist/archive/SUPERSEDED-INVENTORY.json`（**不删除历史证据**）；
- 构建脚本在组装前**清空**目标交付目录（锁文件即硬失败，不再
  `-ErrorAction SilentlyContinue`），避免旧载荷混入；
- 成功后写 `ACTIVE-CANDIDATE.json`，其 `payload_tree_sha256` **读自** payload manifest，
  因此不可能与 manifest 不一致；该标记在 audit 失败时会被撤销。

### 11.7 本轮 Gate

新增/加强的真实 Gate（命令与结果见 PR 描述与本轮完成报告）：

1. Clean First-run Gate（空数据目录 → 内置包 → GB29446 r2 可评价）；
2. Legacy Upgrade Gate（published r1 数据目录 → 自动升级到 bundled r2）；
3. Already-current NO-OP Gate（第二次启动不重复备份、不重复安装）；
4. No-downgrade Gate；
5. Same-version / content-conflict Gate（不覆盖、不抛异常、向用户暴露）；
6. Upgrade failure / backup safety；
7. 历史评价与 rule snapshot 不被新规则改写；
8. GB29446 incompatible-rule fail-fast；
9. Candidate Identity Gate；
10. Build Info Provenance Gate（含 `source_commit` 与 exact head 一致性）；
11. **bundled package → 启动/安装 → Application/Domain → GB29446** 的真实产品链
    （冻结 EXE `--self-check` 与运行期取证脚本均走该链路，而不是直接安装
    `data/definitions` 后测试）；
12. packaged EXE self-check。

---

### 11.8 人工验收发现的两个真实缺陷（本轮修复）

人工验收 packaged Candidate 时发现「计算并判级」完全无反应。定位到**两个独立真实缺陷**：

**缺陷 A：按钮槽函数被 PySide6 传入的 bool 打崩，且异常被静默吞掉。**

```python
calculate.clicked.connect(self.calculate_evaluation)          # clicked(bool checked)
def calculate_evaluation(self, request: EvaluationRequest | None = None)
```

`QPushButton.clicked` 会把 `checked: bool` 作为**第一个位置参数**传入；而
`calculate_evaluation` 的首参是**可选**的 `EvaluationRequest`，于是 Qt 把 `False`
当成 request 传了进来，`request.standard_id` 抛 `AttributeError`。该异常发生在方法
自身 `try` **之前**，被 PySide6 吞掉，因此用户看到的是"点了完全没反应"——
没有结果、没有对话框、没有评价记录。

为什么既有测试没抓到：既有测试都**直接调用方法**（`window.calculate_evaluation()`），
而 `request is None` 时才走正常分支；只有**经信号触发**才会暴露。这正是"必须真实经过
产品链"的意义。我的运行期取证脚本同样直接调 facade，也没覆盖它。

修复：
- `calculate_evaluation(self, request=None, checked=False)`，`isinstance(request, bool)`
  时视为"无请求"；
- 接线改为无参 lambda，从源头避免 bool 落入 request；
- 增加**兜底**：`_calculate_evaluation` 外包一层 `try/except`，任何未预期异常都记录日志
  并弹出可见提示，**槽函数永不静默失败**（这类"静默无反应"本身就是缺陷）。

**缺陷 B：标准库取到了被取代的旧修订。**

`ApplicationFacade.list_library_standards` 用 `by_id = {item.id: item}` 折叠已安装修订，
保留的是仓库返回的**最后一条**；而仓库按 `desc(rule_revision)` 排序，于是**最旧**的修订胜出。
后果：标准库页显示 GB 29446 `rule_revision 1`（而非包内的 r2），
诊断信息也报 `rule_revision: 1`，与"已安装包 = 2026.10-published.3"自相矛盾。

修复：改为按 `(effective_date, rule_revision, version)` 显式取**最新**修订，
不再依赖行顺序；`list_all_standards()` 仍返回全部历史行（49 行 = 48 标准 + GB29446 r1 历史行）。

> 说明：标准库按"每个标准一条"展示，因此升级后条目数仍是 **48**（不是 49）；
> 数据库内标准行数为 **49**。两者含义不同，已在文档中澄清。

**一个曾被我误判的方向（如实记录）**：我最初的复现脚本驱动的是通用评价页的选择器，
而不是 GB 29446 专用页的 `gb29446_coal_type`，导致状态不一致并报出
「选煤工艺类型 不在允许选项中」。改用页面真实控件后确认：
动力煤 + 干法选煤**是合法组合**（干法选煤在动力煤的 `choices` 与附录A k 表中，
k=1.04），`E_d=1000, m=200 → e_d=5.2 → 超出3级`，正常出结果并保存记录。
引擎按所选 product 作用域解析输入定义（`engine.py:313`），**不存在**该缺陷。

**新增 Gate**：`tests/test_gb29446_evaluate_wiring.py`（9 项）——
经**真实按钮信号**点击并断言"生成评价记录"、Bool 首参不得被当作请求、
槽函数抛异常必须可见、标准库必须返回最新修订且每个标准一条、
诊断信息的 `rule_revision` 必须与当前生效定义一致。
（该文件的测试对全部消息框做 autouse 拦截，否则模态框会挂住无头测试。）

---

### 11.9 发布溯源缺陷：身份声明未与真实来源闭合（已修复）

验收者报告的 blocker：Candidate 的字段齐全、哈希自洽、本次 CI 成功，
但**身份并未与真实 source_commit 绑定**。两个独立缺口：

**缺口 A：显式提交可以覆盖真实 HEAD。**
`scripts/build_candidate.ps1` 的 `Resolve-SourceCommit` 与
`tools/write_build_info.py` 的 `commit = args.source_commit or source_commit()`
都让显式值**直接胜出**。独立实测：在当前干净 HEAD 下传入旧 Base SHA，
`--require-clean` 仍然成功生成 `rc-fb91ccc` 身份并声明 `source_dirty=false`
（因为"脏"是按真实工作树测量的）。

修复：显式提交**只能确认** HEAD，不能替换它。不一致即拒绝（生成器 exit 2；
三个构建脚本 throw）。`write_build_info.verified_source_commit()` 是唯一实现。

**缺口 B：审计与 Artifact Gate 不做三方交叉核对。**
`audit_release.py` 校验了字段齐备与文档内部自洽，却从未比较身份的**三个声明处**：

1. 外部 `release-build-info.json`（与 ACTIVE 标记）；
2. 交付**文件名**里的 `rc-<short7>` 前缀；
3. **便携载荷内部**的 `_internal/uebench/resources/build-identity.json`。

因此只改外部文档（并同步刷新校验和）即可通过全部 Gate，而候选实际仍携带旧提交的字节。
独立负例：仅把外部 `source_commit` 改成旧 Base、同步校验和、保留 `rc-88b6f05`
与包内当前 Head → 原为 `valid=true`。

修复：新增 `_audit_identity_binding()`，要求三者一致，并且：

- 候选包的便携包内**必须**存在内嵌身份（否则外部声明可被单独改写而不被发现）；
- 内嵌身份须与外部文档在 `product_version` / `candidate_id` / `source_commit` /
  `source_dirty` / `standard_package_id` / `standard_data_version` /
  `standard_package_sha256` 上逐字段一致；
- 内嵌身份**不得**含 `payload_tree_sha256`（它描述整个载荷，不可能同时位于该载荷内）；
- 产物名必须携带 `-rc-<前缀>`，且前缀等于 `source_commit` 的前 7 位；
- ACTIVE 标记须与外部文档在 `candidate_id` / `source_commit` / `payload_tree_sha256` 上一致；
- **正式发布目录**（`candidate_id` 为 `null`）反过来要求文件名**不带**候选标识，且不做内嵌核对。

由于 (3) 位于被 `payload_tree_sha256` 钉住的载荷之内、而该摘要又被 `SHA256SUMS.txt` 钉住，
三者一致即形成闭合链条。**字段齐全 + 哈希一致 + CI 绿，本身不足以证明绑定；绑定必须被断言。**

**修复后实测（负例脚本，`dist/release` 的临时副本）：**

| 场景 | valid |
|---|---|
| 未改动的副本（对照） | `True` |
| 负例 1：仅外部 `source_commit` 改成旧 Base（文件名与包内身份保持当前 Head） | **`False`**（报出文件名前缀不符、包内 `source_commit` 不符、ACTIVE 不符共 5 条） |
| 负例 2：外部与文件名都改成旧 Base（包内身份仍为当前 Head） | **`False`** |

**新增 Gate**：`tests/test_identity_binding.py`（19 项）——显式提交必须等于 HEAD
（含 CLI 负例、格式负例）、不得写出任何文件；外部↔文件名前缀↔包内身份三方一致的
正例与逐字段负例（对 7 个内嵌字段参数化）、缺失内嵌身份、内嵌身份误含
`payload_tree_sha256`、ACTIVE 标记不一致、以及三个构建脚本不得再"原样采用"显式提交。

### 11.10 报告计数口径更正

此前把 **strict XFAIL 计入 skipped**，分类不准确。pytest 自己的汇总口径为
**`failed` / `passed` / `skipped` / `xfailed` 分开统计**；JUnit XML 会把 xfail 编码为
一个 `skipped` 元素，因此按 XML 统计会得到 65，而按 pytest 汇总应为
**61 skipped + 4 xfailed**。本报告此后统一采用 pytest 口径，并在需要时同时给出 XML 口径。

---

## 10. 状态

```text
RS01 = DONE    RS02 = DONE    RS03 = DONE    RS04 = DONE
RS05 = IN PROGRESS / RELEASE CANDIDATE

Reference Standard Product Closure = PARTIAL
D-ECQ-006 = OPEN
ECQ-STD-GB29446-001 = PROVISIONAL

RS06 = NOT STARTED
```

**本阶段不得写 `RS05 = DONE` 或 `UEBench 0.2.0 = RELEASED`。**
只有独立验收 + merge + final release cut 之后才能宣布 `DONE`。

### 10.1 Blocker 状态（截至 §11 这一轮）

已关闭：

- **内置标准包 GB29446 落后**（原 Blocker 1）：按批准的方案 B，以已签名
  `2026.09-published.2` 为父基线，只替换 GB29446 定义（r1 → r2），其余标准逐字节不变，
  重新签名生成 `2026.10-published.3`（见 §5.2A）。
- **升级后旧用户数据目录规则不自动更新**：改为启动期标准包对账（见 §11.1）；真实
  published r1 数据目录实测 `upgrade` 到 bundled r2，第二次启动 `noop` 且不重复备份。
- **不同内容 Candidate 同名不可区分**：Candidate 资产名与 CI artifact 名携带
  `-rc-<short7>`，并由 build-info / ACTIVE 标记记录完整 `source_commit`（见 §11.4）。

仍未关闭（由环境决定，如实记录）：

- **Windows 验收证据不完整**：本机仅 Windows 10 Build 19045、单显示器，
  缺 Windows 11 实机、多显示器跨屏拖动与 DPI 100/125/150/175/200 实测；
  离线运行只观测到 `OBSERVED-ONLINE`。取证工具不再由显示器数量推断通过
  （≥2 显示器且无实测声明记为 `PENDING-MANUAL`）。

由本轮发现、记录但不扩展实现（按任务书 §十二）：

- 旧的 `reviewed` 阶段标准库与当前正式包存在**同标准版本不同内容**时，对账判定为
  `conflict` 并明确提示、不覆盖；该行为已有回归覆盖。这类库需管理员确认后迁移，
  产品不自动改写标准内容。

## Phase 7 收口进度（进行中，未验收）

> 本节为**追加**记录，不改写上文历史。上文关于 `2026.10-published.3` 的叙述是其时事实；
> 自本轮起，**当前正式标准包已变更为不含标准 PDF 的 `2026.10-published.4`**。

### 新正式标准包（去 PDF，provenance-only）

| 项目 | 值 |
|---|---|
| `package_id` | `gb29446-r2-provenance-only-from-2026.10-published.3` |
| `data_version` | `2026.10-published.4`（排序晚于 `.3`） |
| `minimum_app_version` | `0.2.0` |
| size / SHA256 | 132,837 B / `023d5caf81dd6ba1ce41a5b5d8a59676db20dd98db510b6c4329600aa47e77ff` |
| 标准 / 规则 | 48 / 765（业务内容不变） |
| 成员 | 48 × `definitions/*.json` + `corrections.json` + manifest + signature；**0** 个 `sources/*`、**0** 个 PDF |

- 去 PDF 方式：manifest 新增自描述字段 `source_policy ∈ {"embedded","provenance-only"}`，
  **默认 `embedded`** —— 因此所有历史/归档包仍按原语义校验，legacy 读取兼容未被破坏。
- 定义 provenance（`source_file` / `source_sha256` / `source_references`）**保留**，
  仅不再分发原文文件；`install()` 因而不再把 PDF 写入用户数据目录。
- 逐字节证据（对归档基线以 `--verify-only` 复核）：
  `removed_source_count=48, added=[], changed=[], unchanged_member_count=49` ——
  48 个定义与 `corrections.json` 逐字节一致，仅 `manifest.json` / `signature.ed25519` 变化。
- 旧 `2026.10-published.3` 已按既有规则归档为 SUPERSEDED / REFERENCE ONLY。
- 新增 Gate：`tools/audit_release.py` 的 `no_standard_pdf` 一节 + Artifact Gate 四项
  （发布目录 / 标准包 / 便携 ZIP / payload 清单均不得出现标准 PDF 或 `sources/*`）。

### 支持范围 / 官方来源 / 时间显示（基础模块已完成）

- `application/evaluation_support.py`：单一软件评价支持范围 = `{"gb-29446-2019"}`，
  **不读 `publication_status`**（有 AST 守卫测试）。
- `application/official_sources.py`：仅固定常量，**一个已核实**官方地址
  `https://std.samr.gov.cn/gb/search/gbDetailed?id=9A0A4FA998CDD4A5E05397BE0A0AD02D`
  （两次独立抓取 HTTP 200、内容与本仓标准快照逐项吻合）；其余标准一律未登记。
- `ui/presentation.py`：`naive → UTC → 系统本地时区`，显示 `YYYY-MM-DD HH:MM:SS`、无微秒。

### 尚未完成（因此本轮不构成完成报告）

UI 收口（标准库信息结构 / 新建评价页 / 时间显示接入 / 声明原文入口）、
release 文档中"当前包为 .3 / 48 项标准"表述的统一更新、重建 Candidate、
Source/Artifact Gate + RS04 Golden + self-check + Numeric v1 + N01-A + Generic Excel +
legacy upgrade + literal full suite、exact-head CI、本机 Win10 最短真实产品链人工验证。
**注意**：`dist/release` 仍是用旧包构建的 Candidate，新增"无 PDF"断言对它必然失败，
必须重建后才转绿（不得以删断言或 skip 掩盖）。

## Phase 7 独立验收结论：FAIL —— 三项 blocker 与修复（进行中）

> 本节为**追加**记录。它更正上文与前一份完成报告的过强表述，并记录独立验收的实际结论。

### 独立验收结论

- 验收坐标：Base `fb91ccc6f85791bcaf9751c5681cc00c5a0ed213` → Head `4320980645256d446033a8213000b9bea5625599`（15 提交、79 文件）。
- 结论：**Phase 7 整体未通过**；不允许 merge PR #13，也不允许该 Candidate 放行进入 Win10/Win11 人工发布验收。
- 已成立并与之相符的证据：全量 `918 passed / 65 skipped / 4 xfailed`、真实 Candidate Artifact Gate `66 passed`、
  冻结 EXE self-check `exit 0`、reconciliation/package/Golden/Numeric 计数、Candidate 身份旧缺陷已关闭。
- CI 三个 workflow 在 final-head 均为 success，但**不能替代** Win11/多显示器/DPI/断网人工验收。

### 更正两处过强表述

1. **"正式评价范围已收口"不完整**：收口此前只做在 UI 层。`Application` 正式链路
   （`EvaluationService.evaluate()`）当时**未**检查支持范围注册表，范围外标准（如 `gb-16780-2021`）
   仍能形成正式评价记录。因此"只有 GB29446 可正式评价"当时**不覆盖正式 Application 调用链**。
2. **"用户数据目录无标准 PDF"不完整**：新包/便携 ZIP/源码 ZIP 确实无 PDF，但
   `install()` 仍会把含 `sources` 的**旧包**的原文写入用户数据目录，因此旧库升级后
   48 份 PDF 仍在，并被复制进升级前备份。新包无 PDF **不能**证明用户数据生命周期满足要求。

### 三项 blocker 与修复

| # | blocker | 修复 |
|---|---|---|
| 1 | 正式评价范围仅在 UI 收口 | `EvaluationService.evaluate()` 在**解析/计算/保存之前**用 `request.standard_id` 直接判范围，范围外抛 `ValueError`（文案取自注册表）且**不写任何记录**；`preview()` 显式保留为对所有标准开放并写入 docstring |
| 2 | 安装仍把标准原文写入用户数据目录 | `install()` 对任何包都不再复制 `source` 成员（`preview()` 的 `sources/*` 哈希校验**保持**）；并在**创建升级前备份之前**清理旧版本在产品管理目录下遗留的 `standards/<pkg>/sources`（严格限定于该路径），记日志 + 审计动作 `STANDARD_PACKAGE_LEGACY_SOURCES_REMOVED`，清理量经 `removed_source_directory_count` / `removed_source_file_count` 如实上报 |
| 3 | 安全备份可被静默覆盖 | 备份名改为亚秒精度 `%Y%m%d-%H%M%S-%f` **并加冲突守卫**（同名则追加 `-1/-2/…`），**绝不覆盖**既有备份；保留 `pre-package-*.uebackup` 前缀以兼容既有 glob；测试中的 `time.sleep(1.05)` 规避已移除，改为真实回归 |

### 修复的独立复现证据（以真实当前标准包 + 隔离 SQLite + 归档旧包副本）

下列“仅可预览”是 Phase 7 当时异常提示的原样证据，证明范围外调用不能保存正式评价；`preview()` 是不落库的底层能力，不表示当前普通界面开放其他标准的预览入口。现行用户可见范围以当前源码、用户手册与本报告末尾的阶段结果为准。

```text
Blocker 1  gb-16780-2021 registry=False
           evaluate() -> ValueError「尚未纳入正式评价范围：该标准不能形成正式评价记录，仅可预览。」
           评价记录 0 -> 0；DB 中 gb-16780-2021 评价行 rows=0
           preview() 对范围外标准仍可用且不落记录
           GB29446 正式评价仍可用并落记录（LEVEL_1）
Blocker 2  安装含 sources 的旧包后用户数据目录 PDF = 0
           人为构造旧版遗留 PDF=3 -> 再次安装后 PDF=0（removed_dirs=1 removed_files=3）
           升级前备份逐成员清点：members=3 pdf=0 / members=4 pdf=0  -> 备份亦不含 PDF
Blocker 3  连续两次安装（无 sleep）备份路径不同：
           pre-package-20261005-111819-684675.uebackup
           pre-package-20261005-111821-081210.uebackup
           两个备份都存在，第一个未被覆盖（sha256 不变）
```

### 待完成

新增 Gate 的完整回归、**重建 final Candidate**、Source/Artifact Gate + RS04 Golden + self-check +
Numeric v1 + N01-A + Generic Excel + legacy upgrade、**exact-head CI**、本机 Win10 最短真实产品链复验、
以及修复报告（Base → 新 final Head 为独立验收对象）。

状态保持不变：`RS05 = IN PROGRESS / RELEASE CANDIDATE`、`UEBench 0.2.0 = NOT RELEASED`、
`Reference Standard Product Closure = PARTIAL`、`D-ECQ-006 = OPEN`、
`ECQ-STD-GB29446-001 = PROVISIONAL`、`RS06 = NOT STARTED`。

## 三项 blocker 修复完成（本轮）

> 追加记录，取代上文"待完成"。**独立验收对象仍为 Base `fb91ccc6f85791bcaf9751c5681cc00c5a0ed213` → 本 head。**

- final Head：`c380e15215b19a77ed5c3d4f052034df3ea55a70`（本轮 1 个提交，Phase 7 整体 16 个提交）

| # | blocker | 修复 | 验证 |
|---|---|---|---|
| 1 | 正式评价范围只在 UI 收口 | `EvaluationService.evaluate()` 在**解析/计算/保存之前**用 `request.standard_id` 判范围（换 `selection_mode` 绕不过），范围外抛 `ValueError` 且**不写任何记录**；`preview()` 显式保留为对所有标准开放并写入 docstring | 独立复现：`gb-16780-2021` 拒绝、记录 `0→0`、DB `rows=0`、`preview()` 仍算出 LEVEL_1 且不落记录、GB29446 仍落记录；新增门禁测试 11 项（含不导入 Qt/无 MainWindow 直调、`ast` 守卫、子进程从未加载 PySide6、穷举 >40 个范围外标准） |
| 2 | 安装仍把标准原文写入用户数据目录 | 暂存循环改为**仅 `correction`**（`sources/*` 只留在压缩包内，`preview()` 逐文件哈希校验不变）；并在**取升级前备份之前**清理旧版遗留的 `standards/<pkg>/sources`（严格限定、junction/符号链接防护、不动用户文档），记 WARNING + 审计行 `STANDARD_PACKAGE_LEGACY_SOURCES_REMOVED` + 计数上报 | 独立复现：装含 sources 旧包后用户目录 PDF **0**；人为注入 3 份遗留 PDF → 再装后 **0**（`removed_dirs=1 removed_files=3`）；**两个 `.uebackup` 逐成员清点 `pdf=0`**；真实 Candidate EXE 自检后用户数据目录 PDF **0** |
| 3 | 安全备份可被静默覆盖 | `_backup_path()` 改 `%Y%m%d-%H%M%S-%f`（微秒）+ 显式碰撞守卫 `-1/-2…`，**绝不覆盖**；前缀与备份机制（sqlite3 在线备份）不变；测试中 `time.sleep(1.05)` 规避已移除 | 独立复现：连续两次安装（无 sleep）备份路径不同、两个都在、**第一个未被覆盖**（sha256 不变）；新增 `tests/test_package_install_safety.py` 10 项（含碰撞回归、同秒 200 个名字唯一、守卫绝不返回已存在路径） |

**同时消除"失败断言退化为无限挂起"这一类风险**（此前多次全量跑不出失败清单的真因：门禁上线后某 UI 测试触发**真模态 `QMessageBox.critical`**）：`test_ui.py` 增加 autouse 对话框中和 fixture（函数体内重新 patch 仍生效），门禁测试子进程改为写普通文件 + `timeout=600`。

### 回归结果（pytest 口径）

```text
literal full suite: 939 passed / 65 skipped / 4 xfailed，exit 0
  junit G:\tmp\p7-full.xml: tests=1008 fail=0 err=0 skipped=69（65 真实 skip + 4 xfail）
  65 个 skip 全部为既有"未声明已构建 Candidate（UEBENCH_ARTIFACT_DIR 未设）"一类
Artifact Gate（真实 rc-c380e15）: 66 passed, exit 0
audit_release: valid=True, errors=[]；no_standard_pdf 各计数全 0
冻结 EXE --self-check: exit 0（6/6，含 GB29446 Golden 回放 / 记录往返 / Excel 链路）
exact-head CI（c380e15）: Windows Release Candidate / Numeric v1 / N01-A 全 success
```
未删除、未 skip、未 xfail、未 deselect 任何测试；未放宽任何断言；GB29446 数学/阈值/Numeric/Golden 未改动。

### 产物（rc-c380e15）

| 文件 | size |
|---|---|
| `UEBench-0.2.0-rc-c380e15-win-x64.zip` | 157,065,836 |
| `UEBench-Setup-0.2.0-rc-c380e15-x64.exe` | 104,807,403 |
| `UEBench-source-0.2.0-rc-c380e15.zip` | 1,595,271 |
| `initial-standard-package-published.uebench` | 132,837（0 sources / 0 PDF / provenance-only / 2026.10-published.4） |

### 仍未进行（按本轮要求）

Win11 实机、多显示器跨屏拖动、DPI、断网与安装后载荷人工核对，留待最终人工发布验收。**未 merge、未发布。**

状态保持不变：`RS05 = IN PROGRESS / RELEASE CANDIDATE`、`UEBench 0.2.0 = NOT RELEASED`、
`Reference Standard Product Closure = PARTIAL`、`D-ECQ-006 = OPEN`、
`ECQ-STD-GB29446-001 = PROVISIONAL`、`RS06 = NOT STARTED`。

## Phase 7 Final Simplification（本轮）—— 语义收敛与简化

> 追加记录。**本节取代上文关于 fail-closed 清理与"整目录备份"的描述**；独立验收对象仍为 Base `fb91ccc6…` → 本轮 final Head。

### §二 Backup 语义收敛：安全备份只负责用户业务数据

新增 `BackupScope`：

- `USER_DATA`（默认，`BackupService.create`）→ **只写数据库快照**；预迁移（`database.py`）、预安装（`packages.py`）、预恢复（`restore`）**全部使用该默认值** —— **未做任何启动顺序调整**（迁移仍在 package reconciliation 之前）。
- `FULL_ENVIRONMENT`（`create_full_environment`）→ 额外打包 `APPLICATION_DATA_ROOTS = ("standards","imports","logs")`。
- **实测**（真实内置包 + 3 份 legacy PDF + imports + logs 的活目录）：安全备份 = **2 个成员 `{manifest.json, uebackup.sqlite3}`**（112,662 B、`scope=user-data`、**0 PDF、0 `standards/` 成员**）；同一目录走完整环境备份 = 8 成员 / 115,088 B（即旧单一机制每次都复制进备份的内容）。
- 清单自描述 `scope` 且 `validate()` **拒绝**"自称 user-data 却列有应用数据成员"的归档；`restore` 只合并归档真正拥有的内容（**取消了破坏性的 `rmtree(standards)`**），因此安全备份**永不删除活的**可重建数据；历史 `.uebackup` 逐字节不变。
- **面向用户的"完整备份"仍然存在**（UI「创建备份」→ `ApplicationFacade.create_backup` → `create_full_environment`），与内部安全备份是**两套语义**。

### §三 Legacy PDF 清理改为 **warn-only**（**反转**上一轮的 fail-closed）

- 成功：仍记日志 + 成功审计 `STANDARD_PACKAGE_LEGACY_SOURCES_REMOVED`，计数为**重扫验证后**的真实结果。
- 失败（占用/权限/任何异常）：**只记一条中文 WARNING 并继续** —— **不阻塞启动、对账、安装、正式评价与保存**，**不写成功审计**，返回计数只包含**已验证删除**的部分，下次启动自动重试。
- `reconcile()` 额外包裹端口调用，任何异常都只 WARNING 后继续决策表。
- Windows 真实占用实测：安装完成、规则落盘、GB29446 正式评价与保存正常、随后对账 NOOP 不抛异常、无成功审计、被锁 PDF 逐字节不变、未被锁的平铺 PDF **确实被删**；释放句柄后下次清理成功且审计计数 == 返回计数。

### §五 发现并修复一个真实缺陷（此前会写入垃圾记录）

审查确认：**标准明确要求的必填量缺失时不阻塞** —— `E_d` / `m` **留空**或**为 0 / 负数**时，引擎报 `MissingInputError` / `EvaluationValidationError`，结果 `INCOMPLETE`，**但记录仍然被保存**（`m=0` 即分母为 0）。现改为在**构造 `EvaluationRequest` 之前**于 UI 采集层拒绝：空值「…不能为空。」、非数字/非有限（复用领域 `parse_decimal`）、`<= 0`「…必须大于 0。」→ 提示 + 页面结果卡 + **不保存任何记录**；其他有限小数**原样透传**（Numeric 全值语义不变）。**未新增任何字段或复选框**（用 `findChildren(QCheckBox) == []` 断言）。新增 `tests/test_gb29446_ui_validation.py`（20 项）。

### §七 历史包袱清理（执行记录见 `RS05_LEGACY_DEPENDENCY_AUDIT.md` §10）

- **删除**：`tools/build_initial_package.py`、`tools/build_release_workbooks.mjs`、`tools/build_unified_merge_report.mjs`（均零引用，后两者 `import` 一个本仓不存在的模块、任何机器都跑不起来）。
- **删除** `tests/conftest.py` 的 xfail-strict 钩子及其唯一标记的 2 个用例（6 个参数实例）—— 它们断言的是**已废止**的比较前 ROUND6 契约，同一职责由 `pilots/numeric` 边界向量、`conformance/numeric` 与 GB29446 Golden 的 full-value trap **更强**地承担；**全量套件的 xfail 计数由 4 降为 0**。
- **改造**：`tools/windows_runtime_evidence.py` 去掉硬编码 `G:\`（改 `--root`/`UEBENCH_EVIDENCE_ROOT`）并**惰性化归档访问**（新增 `--part {a,b,both}`，Part A 可无归档运行）；`tests/test_evaluation_support.py` 改指运行期真值源 `data/definitions` 并把断言收紧为 `== 48`。
- **保留**：`standards/development/scope-65` 仍为 REFERENCE_ONLY（8 处活引用、其中 5 处是正向不变量断言；先移出会静默删覆盖），移除顺序已记入审计 §10。

### 仍未执行 / 待裁定

- 其余 8 个 `tools/build_gb*_review.mjs` 仍 `import @oai/artifact-tool`（本仓无该依赖），**任何机器都无法运行**；建议删除或改指受支持生成器。
- 自定义核算周期留空仍阻塞；`E_d = 0` 在 UI 阻塞（与领域守卫一致）。

状态保持不变：`RS05 = IN PROGRESS / RELEASE CANDIDATE`、`UEBench 0.2.0 = NOT RELEASED`、
`Reference Standard Product Closure = PARTIAL`、`D-ECQ-006 = OPEN`、
`ECQ-STD-GB29446-001 = PROVISIONAL`、`RS06 = NOT STARTED`。

## 2026-10-20 RS05 交付收口计划（当前；以下先记计划，不预写验收结果）

本节承接[当前任务](../../TASK_STATE.md)、[唯一总体路线](../../参考标准开发路线.md)和[选煤映射驱动交付补充验收 §6](映射驱动单源规则与同源报告_V3_交付补充验收_20261018.md)。上文各 Phase／当时结论保留为历史执行证据；本节负责本次剩余交付门禁，不新建总体路线，也不改写已批准的选煤映射。计划执行与最终结果必须分开记录；只有取得对应实物证据才能将下表的 `PENDING` 改为通过。

### 平台 / Contract 预检查

| 项目 | 2026-10-20 本次计划依据 |
|---|---|
| 业务仓身份与 SHA | `origin=https://github.com/adgo07/ECQuota-Insight.git`；本计划从 `origin/main@08c6b8ec83d49e5baa864fdf378ab6f0f97369d4` 开始。当前已验 Candidate `rc-4e43490` 的构建源码是独立的干净提交 `4e4349068bb56fa500d20cfab98ef6640e63605c`；本轮治理文档提交不得冒充其构建身份 |
| 中央锁定与适用文件 | `platform-lock.json` 锁 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`，`auto_follow_main=false`；相关 Frozen 为 Architecture 2.1、Numeric Contract v1、Numeric Profiles v1、Numeric Conformance Vector v1。中央 `docs/GUIDE_INDEX.md` 当前已合并 `main@c5fc6d438c9200060649e47c016b9b48218de72c` 路由 ACTIVE `PRODUCT_DELIVERY_POLICY_V1.md`，不按锁定 SHA 读取 ACTIVE 指南 |
| 适用 MUST / MUST NOT | 保持 Decimal full-value exact 正式比较、规则／包签名及历史评价与快照不重算；Windows 正式验收按中央交付 Policy §5 覆盖 Win10/11 基本兼容与主要页面高 DPI 可用。不得把显示值回流正式比较、把旧 Candidate 说成新源码、把未测环境写为 PASS、自动升级 Frozen 或以 UI／Excel 新造业务规则 |
| 冲突分类与中央修改 | 当前未发现新增 Frozen 冲突或 `CENTRAL CONTRACT GAP`；D-ECQ-002～006 仍为 `REGISTERED DEVIATION`。本任务不修改中央 Contract、ACTIVE 指南或本仓锁定 SHA；若实测暴露公共语义缺口，先按治理分类上报 |
| Standard Issue / 软件解释 | 当前标准问题台账无 GB 29446 现行登记项；旧 ROUND6 编号是历史软件问题，不恢复为 `PROVISIONAL`。本任务只补交付证据，不改变选煤批准映射 D01/D02、规则阈值、公式、Numeric Profile 或历史结果 |

### 已有证据与复用边界

`rc-4e43490` 已通过构建身份与 10 条交付文件哈希核验、冻结 EXE 自检 6/6、Candidate Artifact Gate 63/63、构建源码三项 exact-head GitHub CI；Win10 安装版保存／重启读回、临界与未达3级 DOCX 经真实 Microsoft Word 与 WPS 打开、中文路径便携版 GUI 启停、可信旧 0.2.0 Candidate `.4`→`.5` 保留历史 r2 结果均已记录在上述[交付补充验收](映射驱动单源规则与同源报告_V3_交付补充验收_20261018.md)。本次不为补文档或外部环境实测重建相同源码／资源，也不重复完整人工 Word/WPS 矩阵；如生产代码、锁依赖、标准包、构建脚本或随包资源发生变化，再按影响重建 Candidate 并复验相应门禁。

### 并行任务、验收口径与依赖

| 任务／责任 | 要取得的证据和通过条件 | 依赖、风险与当前状态 |
|---|---|---|
| A：现行治理与最终审查（治理负责人） | 清理 `TASK_STATE.md`、`HANDOFF.md`、唯一总体路线中仍把已建 Windows Candidate、便携 ZIP、修复过的历史记录或已通过门禁写作未完成的**现行**句子；保留明确标注的历史阶段事实。汇总 B/C 的原始证据、测试范围、失败与环境限制，出具 RS05 独立验收结论供 Owner 审查 | 不改批准映射正文、水泥结论、Frozen 锁、Excel 工作簿；本计划只记 `PENDING`，不因文档更新宣布 RS05 DONE |
| B：上一正式版升级（升级验收负责人） | 已定位历史 `UEBench 0.1.0` 安装器，其 SHA256 `234bb4b00c3ca3ea3d992b5ed3f5e3ee2ef9f01343680ee96819a98ae248a911` 与正式历史记录一致。下一步在不覆盖现有安装／HKCU 的前提下，分层核旧载荷与版本来源、隔离旧数据升级及原始 request/result/snapshot 哈希；仅具备真正隔离安装条件时，才执行旧安装器→新安装器同路径覆盖、启动、数据保留和卸载保护。失败须保留日志、原库及复现步骤 | `docs/安装与发布说明-0.2.0.md` §5 明确承诺此升级；旧 `.4`→`.5` 及可信旧 payload 数据升级均不能冒充 0.1 安装器真实覆盖。旧安装器固定 AppId／默认目录，当前不运行可能触碰现有注册项的覆盖；若无安全环境则真实安装器覆盖标 `BLOCKED`，交 Owner 裁定承诺与放行。当前资产哈希已核，升级结果 `PENDING` |
| C：Win11／原生 DPI／跨屏与离线（桌面验收负责人） | 用现有 `rc-4e43490` 的安装包和便携包，在可核 OS 与显示器身份的 Win11 环境测基本启动／关闭、中文路径与企业名、选煤最短保存／读回／Word；以 Windows **系统 DPI**（非 Qt 模拟缩放）核主要页面可用、长内容及关键按钮可达，记录实际档位与截图；有双屏条件时检查跨屏拖动和窗口恢复；物理断网或等效可审计隔离下核启动、标准库、评价／历史记录和本地 Word 导出不依赖网络 | 中央交付 Policy §5 要求 Win10/11 基本兼容及高 DPI 主要页面可用；本仓旧 RS05 报告把跨屏／多档 DPI 与断网列为缺证。Win10、Qt 模拟缩放、Windows runner CI 不能冒充 Win11／原生 DPI／断网实测。设备不可得如实 `BLOCKED`，不得自动豁免。当前 `PENDING` |

任务 B 与 C 可并行，均只在隔离数据目录操作并保留旧 Candidate 与原用户目录；A 在两者进行时可修正文档导航，最后依赖 B/C 实测对照验收。发现代码缺陷先保全证据并报主代理审查，按本任务授权处理必要的最小修复；涉及业务语义或支持范围变更再由 Owner 决定。如修复改变构建输入，重建并补受影响回归及实物验证。本机原始证据只放隔离工作树或经授权的 G 原仓 `work/rs05-closure-20261020/` 忽略目录，不纳入源码提交，也不触碰 G 仓跟踪文件或真实用户数据；正式报告记录证据身份和可审查的摘要。

### 剩余门禁矩阵（计划状态，待填实测结果）

| 项目 | 依据与放行性质 | 目前证据／下一步 |
|---|---|---|
| Win11 基本兼容 | 中央 ACTIVE `PRODUCT_DELIVERY_POLICY_V1.md` §5 的正式 Windows 交付最低范围；本任务无权自行豁免 | `BLOCKED`（待人工补验）。本机实测 Win10 19045.6466；当前无可用 Win11／VM／Sandbox。Windows CI runner 不等于 Win11 桌面人工验收；需可核身份的 Win11 设备，或由 Owner 处理无法取得设备造成的发布阻断 |
| 原生系统高 DPI 下主要页面可用 | 同一中央 Policy §5 的正式交付要求 | `PENDING-MANUAL`。本机当前单屏原生 96 DPI（100%）；已有 Qt 模拟缩放仅证明模拟场景。需 Windows 系统高 DPI 实测，保留档位、页面与按钮可达证据 |
| 多显示器跨屏与窗口恢复 | 本仓 RS05 历史验收 §8 登记的 `BLOCKED` 项；中央 §5 未单列为独立最低条件 | `PENDING-MANUAL`。本机仅 2560×1440 单屏，双屏设备可得时实测；不可得时保留缺证并由 Owner 明确处置，不写作 PASS |
| 0.1.0→0.2.0 用户数据与安装升级 | `docs/安装与发布说明-0.2.0.md` §5 的用户承诺；历史 `.4`→`.5` 升级不是该承诺的验证 | `PARTIAL`。历史正式安装器 SHA 已核；其内旧版业务模块生成记录、真实新 EXE 对旧库克隆升级且历史五字段保真，详见下节。旧 GUI 保存与两代安装器同路径覆盖未完成，不能按用户承诺判整项通过；固定 AppId／HKCU 需安全环境，真实覆盖保持 `PENDING-MANUAL` 并交 Owner 处置 |
| 离线最短业务链 | 本仓独立离线运行承诺和历史 RS05 §8 `OBSERVED-ONLINE` 缺证 | `BLOCKED`。本机 Domain／Private／Public 防火墙 profile 均 Disabled，执行账户无管理员令牌，临时仅针对测试 EXE 的出站规则无法构成可信隔离；未创建规则、未改系统设置、未跑离线 GUI。须物理断网或其他可审计隔离环境复验启动、库、保存／读回和本地 Word；静态未见直接网络调用不等于通过 |
| Authenticode | RS05 已记录 `UNSIGNED` 决定；中央 §5 未要求必须具备代码签名 | 当前 `UNSIGNED` 已披露，非无条件硬门禁。若目标企业安全策略要求签名，则由 Owner 确认证书、渠道和正式交付条件；标准包 Ed25519 签名不能替代 EXE 签名 |

本机环境与离线探针原始记录在隔离工作树 `work/rs05-closure-20261020/environment/README.md`（本机忽略目录，非跨机器固定入口）；该记录只确认环境边界，不代替桌面功能通过证据。上述 `PENDING-MANUAL`／`BLOCKED` 状态仍需后续实测或 Owner 明确处置，不能因计划入库转成 PASS。

**2026-10-20 Owner 范围决定：**目前没有可用的 Win11／多屏环境，先完成本机可做的资产、升级及治理工作。此决定仅限定本阶段执行范围，不豁免 Win11／原生系统高 DPI／跨屏验收，不授权将 RS05 标为 DONE，也不应反复要求 Owner 提供现时不存在的设备。缺失环境证据保持在后续收口清单中。

### 放行边界与需 Owner 裁定事项

中央交付 Policy §5 的 Win11 基本兼容与高 DPI 可用不能由本任务自行取消；跨屏是本仓既有待验项，也必须以实际证据或 Owner 明确决定处置，不写成已测。0.1.0 安装器虽已找到且哈希吻合，真实安装器覆盖仍取决于安全隔离条件；若不能实测，须由 Owner 决定用户文档升级承诺的风险处置。当前 `Authenticode=UNSIGNED` 是既有交付决定，安装包／EXE 必须如实声明，`.uebench` 的 Ed25519 内容签名不能替代代码签名；若目标企业环境要求 Authenticode，另由 Owner 决定证书与交付渠道，不把签名凭空设为已完成门禁。最终由 Owner 在证据和残余风险清单上决定 RS05 是否收口；在此之前维持 `RS05=IN PROGRESS`、`Reference Standard Product Closure=PARTIAL`、`0.2.0=NOT RELEASED`、`RS06=NOT STARTED`。Excel 正式工作簿继续暂缓，水泥不在本任务启动。

正式发布是后续独立动作：`windows-formal-release.yml` 要求已发布且非 prerelease 的 GitHub Release、与产品版本严格相符的 tag、tag commit 属于 `main` 历史、干净源码，并重新构建、运行完整门禁后上传正式资产。RS05 证据闭合与 Owner 审查在前，不把 `rc-4e43490` 文件改名视作正式发布，也不在本计划阶段建 tag 或发布 Release。

### 2026-10-20 本机执行结果（与上述计划分列）

**旧版来源与数据兼容，部分通过。**从历史正式 `UEBench-Setup-0.1.0-x64.exe` 复算 127,023,093 B、SHA256 `234bb4b00c3ca3ea3d992b5ed3f5e3ee2ef9f01343680ee96819a98ae248a911`，与历史登记一致；独立提取工具对安装器测试及提取均 exit 0，得到旧版 EXE（SHA256 `cf4c9da1e65d635d174a68c4783ea3703caaf8f3b11598637e40a67a75251218`）。该真实旧 EXE 在双隔离目录初始化数据库 revision `0003`、48 项标准、0 条评价。由于交互桌面自动化未能可靠进入旧 GUI，随后使用**该 EXE 内 PYZ 提取的旧版业务模块**在旧库副本建立 1 条 GB29446 r1 记录 `a60474e1-4856-4022-95b6-f38370374f45`，实际值 `7.0 kW·h/t`、结果 `LEVEL_2`；这不是本轮源码重造的业务结果，也不是旧 GUI 人工保存。

将这份旧库再克隆到独立数据目录，用 `rc-4e43490` 便携 ZIP 中的真实 EXE（SHA256 `9b11064deb403096723e9293e889b1af156c960d8d60eeb7c081238e73af28fa`）执行自检，exit 0、6/6 通过；其中 `excel_import_chain` 是既有后台安全链自检，不表示交付 Excel 工作簿。逐项比较旧记录的 `evaluation_id`、`request_json`、`result_json`、`rule_snapshot_json`、`deleted_at` 均相同；三个 JSON 的升级前后 SHA256 分别为 `a033c4f77f2bf282bdfd5d42eed974a4e0df4d27a10fc0ae34eda8d970846ce7`、`318deb80a8624bc522a5e5bf7ec7d8208b81514381f0bf6119fafe096dda56b5`、`38e76c7faaee3f3c0ec610d4e6266cb053f43dbe8f2598100491ba1f610e2232`。旧 EXE 初始化的原始库 SHA256 `1f43ea9f299835cfae4a6ca1b1a5e2276f4d206cc11a34daa78452a71ad025a6` 未变；新增旧版评价的副本库 SHA256 `3ca6e9c4aeea3b989bde3c99c91e566205f76670325938bcf038dbca31fe2f41` 未变；升级克隆库变为 `b718bf49b8ca0633b9710339768817868a6ab9668c2c6efcaad64cb3e4e508bd`。评价数 `1→5` 是新自检增加 4 条隔离记录；数据库中标准**版本行** `48→49` 是选煤 r1/r3 并存，标准包仍只随 48 项，包记录 `1→2`。

此测试证明可信旧版业务库记录可由新候选在隔离克隆上保真升级；**旧 0.1 GUI 保存和旧安装器→新安装器同路径覆盖均未通过实测**。旧安装器固定 AppId／默认目录，本机已有安装注册项；为避免覆盖现有环境，未运行旧安装向导。旧 GUI 的隔离 launcher 在当前交互桌面挂起后已中断，没有生成可用 GUI 证据。用户文档 §5 的完整安装升级承诺仍待安全隔离环境或 Owner 明确裁定，不据本次库级结果宣布完成。

**环境与离线：**本机确认为 Windows 10 19045.6466、2560×1440 单屏、原生系统 96 DPI。Win11 因无可用环境为 `BLOCKED`（待人工补验）；原生高 DPI 和跨屏保持 `PENDING-MANUAL`；三类防火墙 profile 均禁用且无管理员令牌，可信离线链保持 `BLOCKED`，未创建规则、未改系统配置、未运行离线 GUI。Owner 已决定先完成本机可做项，但未豁免这些要求。RS05 仍 `IN PROGRESS`、产品闭环仍 `PARTIAL`、0.2.0 仍 `NOT RELEASED`。

原始证据位于本机历史执行环境的 `G:/Python Project/能耗限额/work/rs05-closure-20261020/legacy/`（`payload-test.txt`、`payload-extract.txt`、`old-pyz-modules.json`、`old-library-result.json`、`candidate-self-check-process.json`、`candidate-self-check.json`、`upgrade-compare.json`）及隔离工作树的 `work/rs05-closure-20261020/environment/README.md`；两处均为 Git 忽略目录，不是跨机器固定入口。上述身份、旧源库哈希和升级克隆库哈希已独立复算核对；原始文件不复制进 PR。

## 2026-10-23 标准确认状态与稳定启动入口（计划与阶段结果）

本节承接[当前任务](../../TASK_STATE.md)、[映射总索引](../../standards/mappings/INDEX.md)和本报告上述 RS05 交付门禁，只处理本轮已授权的确认状态表达、普通详情限值展示及稳定启动入口。2026-10-20 的部分通过结果仍是历史证据；以下先保留开工时计划，实际结果另见本节末尾，不把未验事项预写为 PASS。

### 平台 / Contract 预检查

| 项目 | 本轮依据及边界 |
|---|---|
| 业务仓、中央身份 | 本任务从 `origin/main@694ac184d5d71b5f2f5500147a5a79b4690c8514` 开始；`platform-lock.json` 仍锁中央 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`。中央当前 `GUIDE_INDEX` 路由的 UI v0.2／产品规格／验收清单为 ACTIVE 指南，不升级本仓 Frozen 锁 |
| 适用 Frozen 与 MUST / MUST NOT | Architecture 2.1、Numeric Contract／Profiles／Conformance v1 保持 Frozen；正式比较继续 Decimal full-value exact，历史结果及快照不重算。正式评价范围仅选煤；文档已批准、机器定义已发布或旧规则可计算，均不得自动放宽范围、冒充验收或在普通详情把未确认限值展示成正式业务结论 |
| 冲突与中央修改 | 当前未发现新增 Frozen 冲突或 `CENTRAL CONTRACT GAP`；既有 D-ECQ-002～006 仍为已登记偏差。本任务不涉及中央公共 Contract 修改；若实施时发现真实公共语义冲突，再按既有分类治理 |
| Standard Issue 与软件解释 | 选煤无现行 Standard Issue，D01/D02 和现行批准映射不变；水泥 `ECQ-STD-GB16780-001`／`003` 维持原台账状态。2026-10-23 用户重申确认范围，但未批准新公式、限值或解释，也未完成水泥软件 Stage B/C/D |

### 分工、预定通过条件与构建边界

| 工作 | 预定通过条件 | 开工时状态（结果见下节） |
|---|---|---|
| 映射确认记录 | 在既有两个标准入口、总索引和当前交接记录 Owner 日期、依据、范围与未确认事项；不改两份批准映射正文，不新建第二台账，不概括判定所有遗留规则都错 | 治理文字待审；与代码实态分开 |
| 软件确认状态与普通详情 | 标准库选中详情分别表达映射确认与软件正式评价支持状态；选煤已验能力与水泥 V1.2 已批准但软件未完成不混淆。未经批准映射核对与软件验收的旧限值不作为普通详情的正式限值展示；新建／保存的正式评价范围仍仅选煤，后端拒绝不能被页面绕过。状态由结构化数据投影，不运行时解析 Markdown | 应用、UI 与测试待独立实现和验证 |
| 稳定启动与交付 | 从确定的干净源码提交构建新 Candidate，分别核安装版与便携版实际入口、启动、数据目录隔离及受影响操作；记录构建 SHA、产物哈希和实测范围。旧 `rc-4e43490` 的通过证据保留，但不能代表此次变更后的新实物 | 实物构建与验收待完成 |

只有代码和随包资源冻结成干净提交后才构建；最终治理结果可另成文档提交，但应与构建源码 SHA 明确区分。交付验收仍须如实保留 Win11、原生高 DPI／跨屏、离线及 0.1.0 真实安装器覆盖等原缺口，不因本轮确认而自动豁免；Excel 工作簿仍暂缓，水泥核算实现不在本任务启动。当前 `RS05=IN PROGRESS`、产品闭环 `PARTIAL`、`0.2.0=NOT RELEASED`、`RS06=NOT STARTED`。

### 本轮阶段结果与仍待实测项

本轮从干净源码 `f6896584ad8fa9c2dd6cbe4e3b1f3fa5b51dbe17` 构建 `rc-f689658`；构建时 `source_dirty=false`。后续治理文档提交仅记录验收，不改变该构建源码和 Candidate 身份。结构化确认登记、标准库详情展示、旧限值隐藏及正式评价范围保护的源码实现已完成；4 个相关测试模块共 59 项定向测试通过，`git diff --check` 通过。该精确源码提交的 [PR Gate](https://github.com/adgo07/ECQuota-Insight/actions/runs/39930477994)、[Numeric v1](https://github.com/adgo07/ECQuota-Insight/actions/runs/39930477924)、[QZC N01-A](https://github.com/adgo07/ECQuota-Insight/actions/runs/39930477943) 均为 `completed/success`。Candidate 构建 exit 0，full suite、冻结 EXE 隔离自检 6/6 及构建内 Artifact Gate 均通过；构建日志未捕获 full suite 的精确通过项数，本节不推算数字。

| 实物与安装核对 | 2026-10-23 实际证据 |
|---|---|
| Candidate 身份 | 本机历史构建路径 `C:/Users/WANGWEI/.codex/worktrees/standard-confirmation-build/能耗限额/dist/candidate-0.2.0-f6896584`；`release-build-info.json` 记录源码 `f6896584ad8fa9c2dd6cbe4e3b1f3fa5b51dbe17`、`source_dirty=false`、标准包 `.5`（48 项／765 条规则，SHA256 `9547e8214124cd76e999c2949dcdcf45738282a56cc0d725df08cea2a49fa2b5`）、payload tree SHA256 `011891a9b8eb90bc3c7b0213e2aeab896677a89e819011b34fa1260f6f3d40a9` |
| 产物哈希 | 安装包 `UEBench-Setup-0.2.0-rc-f689658-x64.exe` SHA256 `444b5d4ad8dc530cfe50160e08d508d378a4e87ccdf93ec00e906ce014d6fff0`；便携 ZIP `UEBench-0.2.0-rc-f689658-win-x64.zip` SHA256 `4875029eb6dfbf3cba68f4f638c2ce28ba72b667b82dffd1cf6fbf172c1057e8`，已独立复算与 `SHA256SUMS.txt` 一致；新 EXE 仍未做 Authenticode 代码签名，标准包 Ed25519 内容签名是另一机制 |
| 持久安装入口 | 真实 `WANGWEI` 用户下 Inno 安装 exit 0，日志记录 `Installation process succeeded` 且无需重启；`C:/Users/WANGWEI/AppData/Local/Programs/UEBench/UEBench.exe` SHA256 `3ecdc25da5a9d0f209d12140827d6e4845bca9283b278c4fc47dc3f81fad49dd`，与 Candidate payload 一致。HKCU 卸载项、开始菜单及重定向桌面快捷方式均指该持久路径；旧临时目录的 `rc-4e43490` EXE 保留，未拿它冒充新安装 |
| 安装版启动与关闭 | 新已安装 EXE 在进程级隔离数据目录启动，进程属于 `WANGWEI`，取得窗口标题与句柄；本轮测试 PID `24128` 通过 `CloseMainWindow()` 优雅退出，随后进程不存在。隔离数据库创建于本日；默认用户目录仅核文件时间早于本轮，没有启动前哈希，不能声称默认 DB 逐字节未改 |

安装过程曾有一次测试命令参数构造错误（未触发目标安装），修正后上述安装 exit 0；此前尝试通过 Sky／Explorer 自动化进入交互桌面挂起并已中断。这两处是验收操作受阻记录，不推断为产品故障。随后 Sky 能识别已安装 EXE 窗口，但 `get_window_state` 约 123.5 秒挂起并中断，**未取得界面截图或控件树、未点击或输入**。因此标准库选中详情的选煤／水泥／其他标准三态视觉、旧限值隐藏的真实 GUI 呈现，以及选煤最短 GUI 操作链仍为 `PENDING-MANUAL`；源码测试与进程启动不能替代这部分人工验收。本轮亦未从新实物重验 Word GUI／Word／WPS，前轮 `rc-4e43490` 的文档证据仅保留其原身份，不迁移为 `rc-f689658` 的通过结论。

构建原始日志位于上述构建工作树的 `work/build-candidate-f6896584-20261023.log`；持久安装原始日志位于本机历史执行环境 `G:/Python Project/能耗限额/work/standard-confirmation-f689658-install/inno-install.log`。这些绝对路径仅定位本机原始证据，不是跨机器固定入口。当前可确认的是结构化源码／自动测试／Candidate 构建／真实用户持久安装与隔离启动关闭；GUI 视觉和操作链、此前已登记的 Win11、原生高 DPI／跨屏、可信离线链及 0.1.0 真实安装器覆盖仍待对应证据或既定治理裁定。`RS05=IN PROGRESS`、产品闭环 `PARTIAL`、`0.2.0=NOT RELEASED`，不启动水泥实现或 Excel 工作簿。

### 同日 PR #32 审查修正与 `rc-b102e36` 续验

上述 `rc-f689658` 仍是其原提交的历史验收，不代表下述新候选。审查发现随包手册将所有标准写成会展示产品／指标／限值明细，并沿用开发目录的启动路径；本轮修正手册、交付清单及安装说明，明确**只有选煤显示完整明细表**，其他标准仅供标准级目录参考，整张产品/工序、指标、单位及限值明细表不在普通详情展示。安装版从开始菜单或桌面快捷方式启动，便携版解压 ZIP 后运行其中的 `UEBench/UEBench.exe`。同时为确认登记与映射索引增加定向一致性测试，历史 Phase 7 的“仅可预览”原样证据只加当时语境注释。批准映射正文、正式评价 ID、Excel 交付和水泥软件范围均未改变；本节沿用上方平台 / Contract 预检查，Frozen 锁与 Standard Issue 状态未变，无新增中央 Contract 修改。

修正后的干净**构建源码**为 `b102e36a564e5b8874e676e4a1799395d211254b`，不是本报告后续的文档交接提交。4 个相关测试模块 60 项通过，精确源码提交的 [PR Gate](https://github.com/adgo07/ECQuota-Insight/actions/runs/39941739735)、[Numeric v1](https://github.com/adgo07/ECQuota-Insight/actions/runs/39941739805)、[QZC N01-A](https://github.com/adgo07/ECQuota-Insight/actions/runs/39941739975) 均为 `completed/success`。首次完整测试进程 exit 0；原日志的进度字符计为 1124 passed、62 skipped、1 warning，**不是 pytest 最终汇总行**。随后首次打包因 PowerShell 5.1 的 JSON 原生命令参数传递失败，未产出安装器；改用 PowerShell 7 对同一干净提交以 `-SkipTests` 续建 exit 0，未重复声称全量测试又运行一次。新冻结 EXE 隔离自检 6/6，构建内 Artifact Gate 63 点全部通过。这一中断属于构建执行环境参数问题，未发现源码测试失败。

| 新候选核对 | 2026-10-23 实际结果 |
|---|---|
| 构建身份与标准包 | 本机历史构建目录 `C:/Users/WANGWEI/.codex/worktrees/standard-confirmation-rebuild/能耗限额/dist/candidate-0.2.0-b102e36`；`release-build-info.json` 为 `rc-b102e36`、`source_commit=b102e36a564e5b8874e676e4a1799395d211254b`、`source_dirty=false`、标准包 `.5`（48 项／765 条规则、SHA256 `9547e8214124cd76e999c2949dcdcf45738282a56cc0d725df08cea2a49fa2b5`），payload tree SHA256 `014e2e067aef0a0f2e05bc84d927cc94767523550aaaaaaec0719ccb882b8e3a` |
| 产物 | 安装包 SHA256 `272d2cb06e215bf78ee8846a365e8a4e64a4f5c494e4e042c1c9488cb83513f4`；便携 ZIP SHA256 `843a354124c83c8749cf0672bc78cc871a790cc01adc29bb316f81dd75ea2e71`，已独立实算核对；候选根目录三份说明与源码逐字节相同，便携 ZIP 本身不含手册文件 |
| 真实用户持久安装 | `WANGWEI` 用户的 Inno 安装 exit 0，安装日志记录成功且无需重启；已安装 EXE SHA256 `01d0cfe8241258fbd156f880026355681ae5a270f404685515a52a4d59d6dcf9` 与新 Candidate payload 相同。开始菜单和桌面快捷方式指向该持久 EXE；安装目录的手册、交付清单、安装说明三文件与候选根目录各自 SHA256 相同 |
| 数据与启动 | 已安装 EXE 在独立数据目录自检 exit 0、6/6 通过；另以隔离数据和 `LOCALAPPDATA` 启动真实 `WANGWEI` GUI 进程（测试 PID `49956`，窗口句柄存在），再经 `CloseMainWindow()` 优雅退出。默认真实用户数据库在安装前、安装后和隔离验收后均为 3,887,104 B、SHA256 `094115c0635534ddceee50075ee78d8d4c0e26f385d7aa4760236d67c09cc92b`，时间未变、无 WAL/SHM；不将隔离库冒充默认用户数据 |

本轮没有取得新候选的 GUI 控件树或截图，也没有点击标准库、保存选煤记录或重验 Word/WPS。因此三态文字与明细表隐藏的**真实界面视觉**、选煤最短 GUI 操作链仍为 `PENDING-MANUAL`；C 的源码只读复核、定向测试与实际进程启动不能替代人工界面验收。`rc-f689658` 的旧实物记录也不自动升级为 `rc-b102e36` 的 Word/WPS 证据。当前目标仍受上方 Win11、原生高 DPI／跨屏、可信离线链及 0.1.0 真实安装器覆盖缺口约束，`RS05=IN PROGRESS`、产品闭环 `PARTIAL`、`0.2.0=NOT RELEASED`。

本机原始构建记录在上述构建工作树的 `work/build-candidate-b102e36-{stdout,stderr}.log` 与 `work/build-candidate-b102e36-retry-{stdout,stderr}.log`；安装日志及自检报告在 `G:/Python Project/能耗限额/work/standard-confirmation-b102e36-install/`。这些是历史执行环境路径，不是跨机器固定入口。最终文档交接提交将与构建源码分开，不能据其 SHA 宣称 Candidate 从该文档提交重建。

## 2026-10-27 PR #33 合并后的交付衔接

### 平台 / Contract 预检查

| 项目 | 本次文档收口核对 |
|---|---|
| 业务仓与源码 | origin 为 `https://github.com/adgo07/ECQuota-Insight.git`；独占文档工作树 `delivery/rs05-docs-20261027`，开工及 fetch 后 `origin/main` 为 `77665b87c9f1ff77c24d26fa5ffbd057c1d12cee`，PR #33 已合并 |
| Frozen 基线 | `platform-lock.json` 保持 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`；Architecture V2.1、Numeric Contract v1、Profiles v1、Conformance v1 均不变 |
| ACTIVE 指南 | 已核对中央本地 clone origin；main `a389ac1de63c4f331f3b04e5e7b7a17ef02ed111`，按 GUIDE_INDEX 核读交付 Policy、当前 UI 规格、指南 v0.2 与验收清单；不构成 Frozen 升级 |
| MUST / MUST NOT | 保留 Decimal 全值比较、保存快照和仅选煤正式范围；不改公式、批准映射、支持注册表、Schema、Frozen lock；不把 UI 合并或源码截图当作最终实物通过 |
| 冲突与中央修改 | 本任务不涉及中央公共 Contract；未发现新增冲突，不需要中央修改；D-ECQ-002～006 保持原登记状态 |
| Standard Issue / 软件解释 | 无本轮相关新增问题；D01/D02 与现行批准映射不变；水泥问题 001/003 保持原状态，本轮不开发水泥 |

### 已有结果与证据边界

[PR #33](https://github.com/adgo07/ECQuota-Insight/pull/33) 已按用户验收授权合并。统一导航、固定选煤单页、自动保存快照、全库检索分页和只读两页签详情、紧凑表格与长名称、设置和禁用入口、官方原文请求反馈及复制地址均已进入 main。当前文档据源码核对，操作入口使用“新建对标”“对标记录”；历史记录和 Word 使用保存快照，普通历史页没有重新评价入口。保存后再次主动计算另存一条记录；修改输入使旧结果的当前查看／导出关联失效。具体实施、测试及截图身份集中在[UI 实施状态第 12 节](../ui/UI_IMPLEMENTATION_STATUS.md#12-pr-33-已合并与-rs05-交付衔接2026-10-27)，不复制一份新实施报告。

第二轮主体 `1425241` 的源码完整回归为 1165 passed / 66 skipped / 2 warnings；后续长名称实现 `e53ebb5` 已登记定向 25 passed。二者保持原版本边界，本次文档线没有重跑生产全套，没有取得最终候选的新 Gate、CI 或人工验收，不将旧结果改写为新版本通过。

当前 Win11 环境和原生 150% 源码 UI 观察已由协调会话确认；仓内 `docs/ui/screenshots/pr33-round2/native150/observation.json` 记录窗口 DPI 144、DPR 1.5、无 Qt 缩放环境覆盖、隔离数据及源码脏树／实现提交归属。该清单的 platform 仅为 windows，不单独提供 OS 版本身份；最终候选验收仍须记录系统版本。原清单 `native_dpi_acceptance=false` 保留，因为源码截图和局部交互不等于最终安装包完整高 DPI 验收。2026-10-20 的 Win10 19045／无 Win11 设备结论继续保留为历史，不再描述当前环境。

### 最终候选待验矩阵（仅列待验，不预写通过）

| 项目 | 截至本次文档核对的状态与所需证据 |
|---|---|
| 最终构建身份与门禁 | 待构建线纳入经审核文档后，从实际干净 source SHA 构建，记录 Candidate 身份、载荷清单与哈希、Source Gate、Artifact Gate、EXE 自检及对应源码 CI。旧 Candidate／UI 试用包不代替新产物 |
| Win10/11 安装与核心业务链 | 有历史候选及源码 UI 的分版本证据；最终候选仍待隔离实测启动／关闭、中文路径与企业名、标准库状态、保存／重启读回、Word 导出，并记录实际 OS 与安装包身份 |
| 原生缩放／跨屏 | 源码原生 150% 已有局部观察；125%、跨屏、其他未覆盖原生尺寸及最终候选主要页面仍待验，不能以 Qt 离屏缩放或截图尺寸替代 |
| 真实离线 | 待物理断网或等效可审计隔离下实测启动、库、计算保存、历史读回及本地 Word。官方网页本来需要网络，其不可访问不代表本地链失败 |
| 输入法与原生弹层 | 真实中文输入法预编辑、未重测的原生展开弹层及适用键盘路径待对应实测；既有 QTest 不自动变成人工证据 |
| 官方网页呈现 | 系统请求反馈／复制地址已实现并有测试及冻结诊断观察；真实网页呈现、原权限弹窗根因仍未核验。沿用既有受限浏览器停止边界，不据请求返回 true 宣称网页已显示 |
| 0.1.0 → 最终候选升级 | 可信旧载荷库级保真已有历史证据；旧 GUI 保存与两代真实安装器覆盖仍待安全隔离验收。用户安装说明已区分预定路径与已验事实，不承诺兼容所有开发中间数据库 |

构建与验收线使用自己的实际证据文件；本文只承接状态与边界，不预设其结果或最终候选 SHA。文档整理不修改生产代码、构建脚本、版本号、标准数据或治理锁；不操作真实用户数据库、已安装产品及旧 `UI测试版_b1346935`／`e70da765`／`ced969a3` 数据。本轮不发布、不打正式 tag，不自行推送或合并文档分支。

当前保持 `RS05=IN PROGRESS`、`Reference Standard Product Closure=PARTIAL`、`0.2.0=NOT RELEASED`、`RS06=NOT STARTED`。64 项机器定义／48 项交付／16 项原样 draft、仅 GB29446 正式可计算不变；Excel 正式用户流程 DEFERRED，水泥不开发。产品路线仍只有根目录《参考标准开发路线》。

### 文档线验证

本次仅改 8 个既有 Markdown 文档；`git diff --check` 通过。默认 Python 3.11 无 pytest，尝试 pytest 命令未能启动；随后以 `runpy.run_path('tests/test_document_hygiene.py')` 直接调用其中全部 6 个无参检查，6/6 通过（控制字符、三份阶段一致性、产品配套状态、手册、仓库指南及 AGENTS 读取顺序）。这是文档一致性验证，不是 Python 3.13 生产回归或候选验收。核对当前 UI 源码及既有截图清单后，未启动桌面程序、构建或修改用户数据。

## 2026-10-27 rc-3bfbbeb 实包结果与提示修复衔接

**平台 / Contract 预检查：** 文档工作树确认干净后，从 `4f9a53d84873a7a0eb14247d19eef1dc029ad89f` 快进至已审核的 `96aa3cb0b69e55c069dc692c8def74c39cb75656`；仅追加三份既有状态文档。Frozen lock 仍为 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`；Architecture 2.1、Numeric Contract／Profiles／Conformance v1、公式、映射、支持范围和 Schema 不变。本任务不涉及中央公共 Contract；无新增冲突或 Standard Issue，不改变选煤 D01/D02，不需中央修改。MUST 按精确版本区分源码修复、自动测试与实包观察；MUST NOT 将旧包通过项冒充新包验证。

| 版本／证据 | 当前可确认结果与边界 |
|---|---|
| `rc-3bfbbeb`，干净源码 `3bfbbeb148b9724580c51518857c5dbedde01dd2` | B 的 `build/work/candidate-3bfbbeb-20261027/BUILD_DELIVERY.json`：完整回归 1183 passed／66 skipped（0 failed），Artifact Gate 63 passed，冻结 EXE 与中文路径隔离启动器各 6 passed。此全套只属于该源码／候选 |
| 设计独立资产核对 | `evidence/design-review-rc-3bfbbeb.json`：三资产 SHA256、326 个载荷文件、隔离包载荷同字节、身份及 ZIP CRC 已核；不等于安装／升级／卸载通过 |
| C 冻结包实测 | `evidence/acceptance/rc-3bfbbeb-中文 独立实测/候选包独立实测报告.md`：Win11 26300、原生 150% 默认主要页面、正式保存／跨进程重启、历史只读及快照保真、225 条搜索分页／损坏隔离、备份恢复与恢复后继续评价已实测。DOCX 仅 LibreOffice Writer 实开；本候选 MS Word／WPS 仍未验 |
| C-DEF-001／002 | 同目录 `产品提示问题复现.md` 登记损坏备份提示不准、英文确认／提示按钮两项 P3。`96aa3cb0b69e55c069dc692c8def74c39cb75656` 已修复源码；据设计复核反馈，生产／测试 diff 已独立阅读，产品提示／备份迁移安全／架构边界 66 项全通过，B 定向 70 项通过。**新包尚未构建，C 尚未原生复验，两项不关闭为实包 PASS** |

上述证据路径以交付收口目录为根，是本机证据定位，不是跨机器固定仓库路径；C 报告附有自身数据来源、截图与哈希索引。本次文档线读取既有报告，不重复声称亲自执行 C 的桌面验收或设计的测试。

仍保留真实安装／升级／卸载及 0.1.0 两代安装器覆盖、真实离线、Win10、其他 DPI／跨屏、额外原生尺寸、真实 IME、MS Word／WPS 和官方网页实际呈现等缺口。最终包必须纳入本次经审核文档后，再锁定实际干净 SHA 并完成对应构建／续验；本文不预设该 SHA，不把 `3bfbbeb` 全套当作 `96aa3cb` 或新包全套，也不据此声称新源码 CI 已通过。

保持 `RS05=IN PROGRESS`、产品闭环 `PARTIAL`、`0.2.0=NOT RELEASED`、`RS06=NOT STARTED`；本线不推送、不合并、不发布、不打正式 tag，不改 B 文件或生产代码，不触碰真实数据／旧 UI 测试包。64 定义／48 交付／16 draft、仅选煤正式评价不变，水泥不开发，Excel 正式流程延期。

## 2026-10-28 rc-69562ee 定向复验与治理验收补录

**平台 / Contract 预检查：** 文档工作树起点确认干净且为 `69562eed5d072b9a1a1a77ab6a71f63ea0196788`；仅补录 TASK_STATE、HANDOFF 与本报告，不改生产代码、实际打包输入或证据原件，不重打包。Frozen lock 保持 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`，Architecture 2.1、Numeric Contract／Profiles／Conformance v1、公式、Mapping、Schema、正式范围均不变。本任务不涉及中央公共 Contract；无新增冲突或 Standard Issue、不改软件解释、不需中央修改。MUST 绑定精确实物身份与定向范围，MUST NOT 把旧包全矩阵或治理提交当作新实物验收。

实际候选为 `rc-69562ee`，干净构建源码 **`69562eed5d072b9a1a1a77ab6a71f63ea0196788`**。B 的 `build/work/candidate-69562ee-20261027/BUILD_DELIVERY.json` 记录完整回归 **1214 passed／66 skipped／0 failed**、Artifact Gate **63 passed**，EXE／隔离启动器各 6 项自检通过。据设计独立确认，该精确 SHA 的三项适用 CI 全部 success；[PR #34](https://github.com/adgo07/ECQuota-Insight/pull/34) 已存在，仍为草稿、未合并。本次治理补录提交不是新构建身份，不触发重打包。

C 原生 **12 项短定向复验 PASS**，范围为 Win11 原生 150% 的计算错误／成功中文按钮、仅存一条、历史及 Word 快照短冒烟、备份成功、恢复与删除 Enter／Esc／关闭默认取消、坏备份提示与数据保真、确认软删除、有效恢复及保护备份、重启保真、导出错误中文按钮。C-DEF-001（坏备份建议不准）、C-DEF-002（英文按钮）经设计独立复核后在此定向范围关闭。受控导出故障注入仅限合成记录且已撤销；最终唯一记录 ID 及 request／result／rule snapshot 三份 JSON 与基线逐字相同，326 个原载荷一致，正常关闭后无本候选进程残留。

证据以交付收口目录为根：

- `evidence/acceptance/rc-69562ee-定向复验-20261028/定向复验报告.md`、同目录 `C_TARGETED_RETEST_RESULT.json`：原生动作、截图索引、注入撤销与最终数据核对。
- `evidence/design-review-rc-69562ee-targeted.json`：设计已读报告／JSON，目视坏备份、默认取消删除及导出错误三张原生截图，直接只读核对合成数据库与基线、取消／恢复审计、保护备份 CRC 及哈希，结论 `PASS_TARGETED_DESIGN_REVIEW`。

本次文档线读取上述文件，不冒称重复执行 C 或设计的验收。`rc-3bfbbeb` 的 225 条分页、完整原生页面及 LibreOffice Writer 实开仍只属于旧包，不平移为 `rc-69562ee` 全矩阵通过。本候选 Word 仅验证导出、DOCX XML 和快照保真，未在 Word／WPS／Writer 实开；官网实际网页呈现也未验。C 的机器汇总 pending 为空仅指这 12 项定向用例结束，不表示以下环境门禁闭合。

| 剩余未验项 | 可行动的环境条件与下一步 |
|---|---|
| 安装／覆盖升级／卸载及 0.1.0 两代安装器 | 取得可丢弃且与宿主安装登记、用户数据隔离的 Windows 验收环境及可信旧安装器；先记录环境／安装包身份，再验证旧 GUI 保存、真实安装器覆盖、同版本覆盖及卸载保留数据。新目录或库级迁移不替代安装隔离 |
| 可信离线 | 取得物理断网或等效可审计隔离条件，在该候选上记录隔离状态并实测启动、标准库、计算保存、重启历史及本地 Word 导出；不以静态代码、自检或在线运行代替 |
| Win10／其他 DPI／跨屏／真实 IME | 取得 Win10 验收环境、可安全调整的原生系统 DPI（含 125%）及双屏；按实际档位核主要页面／窗口恢复和跨屏。另用真实中文输入法完成预编辑、确认及取消，不能用 Unicode 填入代替 |
| 文档查看器与官方网页 | 取得 Microsoft Word／WPS 环境，实开该候选导出的 DOCX 核内容与排版；在能可靠识别当前 URL 的获准浏览器环境核官网实际呈现。请求返回成功、复制地址或旧包 Writer 实开均不替代这些结论 |

继续保持 `RS05=IN PROGRESS`、`Reference Standard Product Closure=PARTIAL`、`0.2.0=NOT RELEASED`、`RS06=NOT STARTED`。不自行推送、合并、发布或打正式 tag，不触碰真实数据／已安装产品／旧试用包；64 定义／48 交付／16 draft、仅选煤正式可计算不变，水泥排除，Excel 正式流程延后。此补录只更新治理证据，不要求为补录本身重新构建候选。
