# ECQ-RS05 执行报告 — Windows V1 Release Candidate

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
