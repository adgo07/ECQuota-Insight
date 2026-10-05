# RS05 旧资产依赖审计（Legacy Dependency Audit）

> 状态：**AUDIT ONLY**（只读审计）。本文件是审计结论，不是执行授权。
> 本审计**未修改、未删除、未提交**仓库中任何其他文件。
> 分类标识：`ACTIVE` / `TEST_FIXTURE` / `REFERENCE_ONLY` / `OBSOLETE`（定义见第 2 节）。

## 1. 审计快照与方法

| 项目 | 值 |
|---|---|
| 仓库 | `adgo07/ECQuota-Insight`（`git remote get-url origin` 实测一致） |
| 分支 | `feat/ecq-rs05-windows-v1-release` |
| 审计基线 | head `101885042d1e0e675462229f7cd69a4c4ebdba91` |
| 工作树状态（审计开始时） | `git status --short` 为空（干净） |
| 工作树状态（审计结束时） | **已被并发任务修改**：`M src/uebench/infrastructure/packages.py`、`M src/uebench/ui/main_window.py`、`M tests/_legacy_assets.py`、`M tests/test_package_install_safety.py`、`M tests/test_ui.py`、`M tests/test_ui_release_scope.py`、`?? tests/test_package_legacy_layouts.py`；`?? docs/governance/RS05_LEGACY_DEPENDENCY_AUDIT.md`（本审计文件） |
| Python | `.venv\Scripts\python.exe` = 3.13.3，pytest 8.4.2 |
| 外部归档 | `G:\ECQuota-Archive\ECQ-RS05-LEGACY-REFERENCE-ONLY` **存在**（本次审计时可用） |

**重要说明（并发写入）**：审计开始（`tests/_legacy_assets.py` 读取时为 108 行，等同 HEAD 内容）之后，另一个任务在同一工作区开始改写 Phase 7 相关文件，审计结束时上表的 6 个文件已处于未提交状态。
因此：

1. 本文件所有 **行号一律指向 HEAD `10188504`** 的内容，不指向当前工作树的改动版本；
2. `tests/_legacy_assets.py` 的行号来自审计开始时对该文件的读取，已用 `G:\tmp` 中的 HEAD 副本（108 行）复核一致；
3. 当前工作树为 `source_dirty=true`，`scripts/build_candidate.ps1:110-112` 会**拒绝**正式候选构建（`--require-clean`）——这本身是发布链的一个即时风险；
4. 第 8 节记录了本次观察到的并发改动，供父任务避免重复实现。

### 1.1 方法

- 使用 `grep` / `glob` 工具全仓检索（排除 `.git`），覆盖 `src/`、`tests/`、`tools/`、`scripts/`、`.github/`、`release/`、`packaging/`、`docs/` 与根文件；
- 对被怀疑的测试**实际运行**验证，而不只是 grep：把 HEAD 内容复制到 `G:\tmp\ecq-legacy-audit\repo`（不含 `.git`、`work/`、`dist/`、`tmp/`、`.venv`、`node_modules`），把副本中的 `release/standard-packages/LEGACY-REFERENCE.json` 的 `archive_root` 改指到不存在的路径，用同一解释器运行，实测 skip/pass/fail。原始 `G:\ECQuota-Archive` 与仓库文件**未被修改**；
- `--basetemp` 一律指向 `G:\tmp`（C: 空间紧张）；`pyproject.toml:43` 的 `addopts = "-q --strict-markers"` 会与额外 `-q` 叠成 `-qq` 吞掉汇总行，因此需要计数时使用 `-v` / `-rs`；
- 只运行定向文件，未运行全量套件。

副本同时**不含 `work/`**，因此副本 = 「无外部归档 + 无本机开发签名私钥 + 无 `dist/`」的完整 CI 等价环境。

## 2. 分类定义（本次审计口径）

| 分类 | 含义 |
|---|---|
| `ACTIVE` | 当前运行期 / 构建期 / 发布链真正需要 |
| `TEST_FIXTURE` | 只有测试需要。若依赖外部或本机资产，应改为**确定性仓内夹具**（每次运行时现场构造，密钥临时生成） |
| `REFERENCE_ONLY` | 历史证据。应留在**活动仓库之外**的只读归档区；活动仓库内只允许保留「指针 + 不变量断言」 |
| `OBSOLETE` | 已无独立价值。**每一项都给出当前实现 / 测试 / Gate 已覆盖同一职责的证据**（这是删除的前置条件，不是授权） |

## 3. 分类总览

| 分类 | 条数 |
|---|---|
| `ACTIVE` | 22 |
| `TEST_FIXTURE` | 9 |
| `REFERENCE_ONLY` | 13 |
| `OBSOLETE` | 18 |
| **合计** | **62** |

## 4. 逐项清单

### 4.1 旧标准包（standard packages）

| ID | 位置 | 内容 | 触及阶段 | 分类 |
|---|---|---|---|---|
| LEG-001 | `release/standard-packages/LEGACY-REFERENCE.json`（全文 32 行） | 旧资产归档指针 + `status: REFERENCE ONLY` | 测试期 | `TEST_FIXTURE` |
| LEG-002 | 同上 `:6-14` `parent_baseline` = `2026.09-published.2` | GB29446 r1→r2 的父基线 | 仅证据 | `REFERENCE_ONLY` |
| LEG-003 | 同上 `:15-24` `source_bearing_predecessor` = `2026.10-published.3` | 最后一个随包分发 `sources/*` 的包 | 仅证据 | `REFERENCE_ONLY` |
| LEG-004 | 同上 `:25-31` `user_library` = `2026.08-reviewed.5` | 旧 reviewed 用户库指针 | 仅证据 | `REFERENCE_ONLY` |
| LEG-005 | `tests/_legacy_assets.py:43-91`（`pointer()` / `archived_source()` / `legacy_package()` / `session_legacy_package()` / `session_source_bearing_predecessor()`） | 从归档复制到临时目录再交给测试 | 测试期 | `TEST_FIXTURE` |
| LEG-006 | `tests/_legacy_assets.py:93-108` `session_user_library()` | 复制旧 reviewed 用户库 | 无调用者 | `OBSOLETE` |
| LEG-007 | `release/standard-packages/PIN.json:17-46`（`parent_baseline` / `ancestor_baseline` 退役钉） | 退役包的大小 / SHA256 / 相对路径 | 测试期 | `TEST_FIXTURE` |
| LEG-008 | `release/standard-packages/initial-standard-package-published.uebench`（`2026.10-published.4`，`PIN.json:3-16`） | 唯一固定正式标准包 | 构建期 + 运行期 | `ACTIVE` |
| LEG-009 | 归档 `superseded-packages/`：`initial-standard-package-0.1.0.uebench`、`-44-candidate.uebench`、`-46-candidate.uebench`、`initial-standard-package-published.uebench` | 0.1.0 / 44 / 46 候选与早期 published 包 | 仅证据 | `REFERENCE_ONLY` |

**说明（LEG-001 / LEG-005 / LEG-007 应保留在仓内）**：它们断言的是「旧包**没有**回到仓库」这一仓库卫生不变量。`tests/test_standard_package_revision.py:100-129` 逐条断言：旧包文件不存在、指针存在、`status == REFERENCE ONLY`、两个 SHA256 与归档一致、`relative_path` 以 `superseded-packages/` 开头；`:131-143` 断言 `PIN.json` 不含绝对路径、`archive_relative_path` 必须是相对路径且 `archive_pointer` 前缀为 `release/standard-packages/LEGACY-REFERENCE.json#`。这些断言必须留在可以在 CI 上运行的仓内测试里。

**说明（LEG-006 为何是 `OBSOLETE`）**：`session_user_library` 在全仓**零调用者**（`grep -r "session_user_library"` 仅命中定义处 `tests/_legacy_assets.py:337`（工作树版本）/`93`（HEAD 版本）与 `release/standard-packages/LEGACY-REFERENCE.json:25-26` 的指针）。旧用户库的兼容 / 迁移职责已由以下现行测试覆盖：
- `tests/test_upgrade_0_1_0_to_0_2_0.py`（0.1.0→0.2.0 迁移，夹具由 `tools/build_legacy_0_1_0_fixture.py` 在 `tmp_path` **现场生成**，`test_upgrade_0_1_0_to_0_2_0.py:34-39`）；
- `tests/test_migration_backup.py`（升级前安全备份）；
- `tests/test_package_reconciliation.py`（决策表 A–F，`:359-433`）。
因此 LEG-006 可删；`LEG-004` 的指针条目按 `REFERENCE_ONLY` 保留在归档侧。

### 4.2 旧 reviewed 用户库 / `%LOCALAPPDATA%\UEBench`

| ID | 位置 | 内容 | 触及阶段 | 分类 |
|---|---|---|---|---|
| LEG-010 | 归档 `legacy-releases/0.1.0/UEBench-0.1.0-win-x64.zip`、`UEBench-source-0.1.0.zip` | 上一正式发布物 | 仅证据 | `REFERENCE_ONLY` |
| LEG-011 | 归档 `superseded-candidates/SUPERSEDED-candidate-2026-10-04-before-identity/`（14 文件）+ `SUPERSEDED-INVENTORY.json` | 候选身份改造前的旧 Candidate | 仅证据 | `REFERENCE_ONLY` |
| LEG-012 | 归档 `user-library/UEBench-reviewed-202608/`（47 文件，含 `uebench.sqlite3` 与 44 个 PDF） | `2026.08-reviewed.5` 旧库 | 仅证据 | `REFERENCE_ONLY` |
| LEG-013 | 本机 `%LOCALAPPDATA%\UEBench.SUPERSEDED-reviewed-202608`（`LEGACY-REFERENCE.json:28` 记录） | 旧库改名后的现场原件 | 仅证据 | `REFERENCE_ONLY` |

现行代码**没有任何**读取 `%LOCALAPPDATA%\UEBench.SUPERSEDED-reviewed-202608` 的路径：`src/uebench/infrastructure/paths.py:24` 只拼 `AppPaths` 数据目录（默认 `%LOCALAPPDATA%\UEBench`），`src/uebench/application/self_check.py:15,1256` 与 `tests/test_self_check.py:10,94,425` 明确要求自检**不触碰**真实用户目录。这是正确的边界，无需改动。

### 4.3 0.1.0 / superseded Candidate 产物与发布路径

| ID | 位置 | 内容 | 触及阶段 | 分类 |
|---|---|---|---|---|
| LEG-014 | `tools/build_initial_package.py:44`（默认输出 `dist/standard-packages/initial-standard-package-46-candidate.uebench`）、`:45`（默认 `--data-version 2026.08-reviewed.1`）、`:51`（默认 `work/signing/development-private-key.pem`） | 退役的标准包构建器 | 无调用者 | `OBSOLETE` |
| LEG-015 | `tools/capture_ui.py:28`（回退到 `dist/standard-packages/initial-standard-package-published.uebench`） | UI 截图工具的包搜索路径 | 开发工具 | `OBSOLETE` |
| LEG-016 | `tools/publish_confirmed_rules.py:76-78`（`--scope` 回退、`--private-key work/signing/...`、`--output dist/standard-packages/initial-standard-package-published.uebench`） | legacy publication gate | 开发工具 + 测试期 | `ACTIVE` |
| LEG-017 | `tools/build_legacy_0_1_0_fixture.py` + `tests/test_upgrade_0_1_0_to_0_2_0.py` | 0.1.0 数据目录的**确定性仓内合成夹具** | 测试期 | `ACTIVE` |
| LEG-018 | `tests/test_build_identity.py:43,75,179-205`（字面量 `2026.09-published.2` / `2026.10-published.1` / `2026.10-published.3`） | 构建身份对账的合成夹具数据 | 测试期 | `TEST_FIXTURE` |
| LEG-019 | 本机 `dist/installer/UEBench-Setup-0.1.0-x64.exe` 及一批 `UEBench-Setup-0.2.0-rc-*.exe` | 历史安装程序残留（被 `.gitignore:9` 忽略） | 无 | `OBSOLETE` |
| LEG-020 | `docs/交付清单.md`、`docs/安装发布说明.md`、`docs/非程序员验收与AI开发教程.md`、`docs/验收记录.md`、`docs/交接清单-2026-08-31.md`、`docs/history/**` | 0.1.0 时代交付与验收叙述 | 无（纯 prose） | `REFERENCE_ONLY` |

**LEG-014 覆盖证据**：包构建职责已由 `src/uebench/infrastructure/packages.py` 的 `StandardPackageBuilder` + `tools/build_gb29446_package_revision.py`（被 `release/standard-packages/PIN.json:51,73` 记为生成工具）承担，并由 `tests/test_standard_package_revision.py:151-210`（哈希 / 无 sources / GB29446 r2 / Ed25519 真验签）与 `tests/test_release_source.py:311-360`（`preview` + `install` 真流程）覆盖。`grep -r "build_initial_package"` 仅命中 `tests/test_release_version_consistency.py:20-21` 的一段解释性 docstring，无任何 import。

**LEG-015 覆盖证据**：固定发布输入现在位于 `release/standard-packages/`，由 `tests/test_release_source.py:271-308` 钉住哈希、由 `tests/test_release_source.py:223-234` 断言 `uebench.spec` 打包该路径。

**LEG-016 为何是 `ACTIVE`**：`tests/test_confirmation_tools.py:11` 直接 `from tools.publish_confirmed_rules import validate_confirmation`，且 `参考标准开发路线.md:449` 与 `TASK_STATE.md:148` 明确把它作为 legacy publication gate **保留不改**。但其默认输出路径仍是 `dist/standard-packages/`（见 LEG-033），需要与 LEG-033 一并处置。

**LEG-019 覆盖证据**：当前安装程序名由 `tools/release_version.py:176-189` 的 `artifact_names()` 派生，Artifact Gate `tests/test_release_artifacts.py:204-210` 要求该名字的文件必须存在且非空；构建脚本 `scripts/build_candidate.ps1:186-188` 每次先删除 `dist\UEBench` / `build\uebench`。0.1.0 安装程序无任何引用者。

**LEG-020 为何是 `REFERENCE_ONLY`**：`tests/test_release_version_consistency.py:73-84` 把 `docs/安装发布说明.md`、`docs/交付清单.md`、`docs/非程序员验收与AI开发教程.md`、`docs/验收记录.md`、`docs/history/**` 显式列为 `_OUT_OF_SCOPE_LEGACY`（**未读取**，只是声明不扫描）；`packaging/installer.iss:80-85` 与 `scripts/build_candidate.ps1:304-313` 交付的是**带版本号**的 `docs/安装与发布说明-0.2.0.md`、`docs/交付清单-0.2.0.md`，与这些历史文件无关。

### 4.4 外部归档 `G:\ECQuota-Archive` 与 `ECQ-RS05-LEGACY-REFERENCE-ONLY`

| ID | 位置 | 内容 | 触及阶段 | 分类 |
|---|---|---|---|---|
| LEG-021 | `release/standard-packages/LEGACY-REFERENCE.json:5` `"archive_root": "G:\\ECQuota-Archive\\ECQ-RS05-LEGACY-REFERENCE-ONLY"` | **全仓唯一的机器绝对路径** | 测试期 | `TEST_FIXTURE` |
| LEG-022 | `tools/windows_runtime_evidence.py:25`（`ROOT = Path(r"G:\Python Project\能耗限额")`）、`:26`（`dist/UEBench/UEBench.exe`）、`:27`（指针）、`:30-46`（从归档复制旧包） | 唯一的 Windows 运行期取证脚本 | 人工取证 | `ACTIVE` |
| LEG-023 | `tests/test_standard_package_revision.py:100-129`（仓库卫生不变量） | 旧包不得回到仓库 | 测试期 | `ACTIVE` |
| LEG-024 | `tests/test_standard_package_revision.py:218-221` `_parent_or_skip()` → 用例 `:224`、`:233`、`:259` | 与归档父基线**逐字节**比对 | 仅证据 | `REFERENCE_ONLY` |
| LEG-025 | `tests/test_package_reconciliation.py:46-52`（`session_legacy_package()` 取副本）、`:66-69`（`require_pinned_packages()` 同时要求旧包与当前包） | 决策表 A/B/C/D/E/F 用例的「旧包」输入 | 测试期 | `TEST_FIXTURE` |
| LEG-026 | `tests/test_package_install_safety.py:70-95`（`LEGACY_PACKAGE` + `require_legacy_package()`） | 旧版原文落盘清理契约 | 测试期 | `TEST_FIXTURE` |
| LEG-027 | `tests/test_gb29446_evaluate_wiring.py:41-47`（`session_legacy_package()`）、`:85-87`（**可选**安装旧包）、`:125-126` | r1+r2 并存状态 | 测试期 | `TEST_FIXTURE` |
| LEG-028 | `tests/test_package_reconciliation.py:54,125-133` 与 `tests/test_package_install_safety.py:72-73,129-140`（`work/signing/development-private-key.pem`） | 本机开发签名私钥 | 测试期 | `TEST_FIXTURE` |

**LEG-021 说明**：该绝对路径是「测试 ↔ 外部归档」的唯一耦合点。它本身**不是**错误设计（归档根必须写在某处），但它使「旧包没有回到仓库」这一**可以在任何机器上验证**的不变量，与「这台机器有没有 `G:\` 归档」绑在一起。建议改为 `ECQ_LEGACY_ARCHIVE` 环境变量可覆盖、缺省回落到该常量，从而让 `tests/test_standard_package_revision.py:100-143` 的卫生断言在无归档机器上仍可执行。

**LEG-022 说明**：该脚本产出的是 RS05 报告里**仍然 OPEN** 的「Windows 实机运行期取证」（`docs/安装与发布说明-0.2.0.md:156-157`），因此不能直接判为 `OBSOLETE`。但它有两个明确缺陷需要单独立项修复：
1. `:25` 硬编码 `G:\Python Project\能耗限额`，违反 `AGENTS.md` §1.1「不得把某台电脑的绝对路径当成跨机器固定路径」；
2. `:46` 在**模块导入时**就执行归档复制（`LEGACY_PACKAGE = _legacy_package_copy()`），归档缺失时直接 `SystemExit`，无法只跑 Part A。
`grep -r "windows_runtime_evidence"` 除自身外**零引用**：没有脚本或 workflow 调用它。

**LEG-024 说明（为何是 `REFERENCE_ONLY`）**：这 3 个用例把当前固定包与归档父包做**逐字节**比对（`test_every_definition_is_byte_identical_to_the_parent_baseline`、`test_only_sources_were_removed_from_the_parent_baseline`、`test_parent_baseline_is_byte_identical_to_the_archived_copy`）。它们需要的正是那 21 MB 归档原件，而「把父基线放进仓库」恰恰是 ECQ-RS05 明确要禁止的事。因此这 3 个用例**不可能、也不应该**变成仓内夹具；正确处置是承认它们是**发布证据**而非核心兼容覆盖，让它们不参与「全量套件」的覆盖度统计（例如标记为 `@pytest.mark.evidence` 并在 CI 中显式 deselect），而不是保留「缺失即 skip」的假覆盖。

**LEG-025 / LEG-026 / LEG-027 / LEG-028 说明（为何应改为仓内夹具）**：这三组共 13 个用例**并不真的需要归档原件**。它们需要的是「一个带 `sources/*` 的、已签名的、`data_version` 更低的包」。同一模块里已经有现成能力：
- `tests/test_package_reconciliation.py:136-160` `build_test_package()` 用真实 `StandardPackageBuilder` 造签名包；
- `tests/test_package_install_safety.py:143-181` `definition_with_source()` + `build_embedded_package()` 造**携带 `sources/*`** 的签名包；
- `tests/test_package_install_safety.py:184+` `build_provenance_only_package()` 造去原文包。

真正只能靠归档原件的是 `tests/test_package_install_safety.py:652` `test_real_legacy_package_ships_sources_but_never_lands_them`（用**真实**的旧包证明「即使真实旧包带 48 个 PDF，安装后用户数据目录也没有 PDF」），它属于 LEG-026 组内的证据用例。
同理，`LEG-028` 的两个测试（`:604`、`test_upgrade_of_legacy_data_directory_removes_installed_pdfs` 等）可以用**测试时临时生成的 Ed25519 密钥对**替代 `work/signing/` 私钥；`tests/test_package_install_safety.py:98-126` 的 `make_service()` 已经证明服务可注入任意公钥。

### 4.5 历史 `dist/` `work/` `tmp/` 产物与路径假设

| ID | 位置 | 内容 | 触及阶段 | 分类 |
|---|---|---|---|---|
| LEG-029 | `scripts/sync_release.ps1:43`（默认 `dist\release`）、`:131-139`（清空并装配）；`scripts/build_release.ps1:153,159-163`（清空 `dist\release`） | 旧的候选装配目录布局 | 构建期（本地） | `OBSOLETE` |
| LEG-030 | `packaging/installer.iss:79`（`Source: "..\dist\release\GB29446选煤电力消耗限额导入模板.xlsx"` + `scripts/build_candidate.ps1:218-219,267-271` 预生成） | 模板 staging 依赖 | 构建期 | `ACTIVE` |
| LEG-031 | `scripts/build_candidate.ps1:186-194`、`scripts/build_release.ps1:151-152,175`、`packaging/installer.iss:74` | `dist\UEBench` payload 树 | 构建期 | `ACTIVE` |
| LEG-032 | `packaging/installer.iss:38`（`OutputDir=..\dist\installer`）、`scripts/build_candidate.ps1:238` | 安装程序输出目录 | 构建期 | `ACTIVE` |
| LEG-033 | `tools/capture_ui.py:28`、`tools/build_initial_package.py:44`、`tools/publish_confirmed_rules.py:78` 的 `dist/standard-packages/` | 已废弃的标准包目录布局（本机该目录**存在但为空**） | 开发工具 | `OBSOLETE` |
| LEG-034 | `src/uebench/application/build_identity.py:42`（`DEVELOPMENT_IDENTITY_PATH = ("dist","release","release-build-info.json")`）、`:206-207` | **运行期**在开发模式读取 `dist/release` | 运行期（dev） | `OBSOLETE` |
| LEG-035 | `release/standard-packages/PIN.json:19`、`tools/build_initial_package.py:51`、`tools/publish_confirmed_rules.py:77` | `work/signing/development-private-key.pem` | 开发工具 | `ACTIVE` |
| LEG-036 | 20 个 `tools/refine_*.py`（默认 `--data-dir work/next-scope-63/data`）、9 个 `tools/build_gb*_review.mjs`（`:5-7`）、`tools/prepare_next_scope_drafts.py:273` | 开发库草案工具默认目录 | 开发工具 | `ACTIVE` |
| LEG-037 | `scripts/build_release.ps1:131`、`scripts/build_candidate.ps1:172,370` | `work\pytest-*` 构建期 basetemp | 构建期（本地） | `ACTIVE` |
| LEG-038 | `tools/build_compilation_draft_rules.py:83`、`tools/build_original_draft_rules.py:90`、`tools/prepare_next_scope_drafts.py:344-345`、`tools/verify_scope.py:88` | `work/verification/*.json` 输入 | 开发工具 | `ACTIVE` |
| LEG-039 | 本机 `tmp/`、`outputs/`（`git ls-files -- tmp outputs` = 0） | 只被 `.gitignore:19-20` 忽略的草稿目录 | 无 | `OBSOLETE` |
| LEG-040 | `scripts/build_candidate.ps1:186`、`scripts/build_release.ps1:151` 的 `build\uebench` | PyInstaller 工作目录 | 构建期 | `ACTIVE` |

**关键事实**：`dist/`、`work/`、`tmp/`、`build/`、`outputs/` **没有任何被 Git 跟踪的文件**（`git ls-files -- dist work tmp build outputs` 返回空；`.gitignore:3,8,9,19,20`）。因此 CI 干净检出**永远没有** `dist/`、`work/`、`tmp/`。任何把这三者当作「干净检出上必然存在」的断言都是缺陷。

**LEG-029 覆盖证据**：当前候选装配唯一入口是 `scripts/build_candidate.ps1:151-153`（默认 `dist\candidate-{Version}`）与 CI `windows-release-candidate.yml:125-128`（显式 `-OutputDir "dist/candidate"`），产物由 Artifact Gate `tests/test_release_artifacts.py`（`UEBENCH_ARTIFACT_DIR=dist/candidate`，`windows-release-candidate.yml:190-192`）验证。
**本次实测**：本机 `dist/release` 当前恰好是 head `10188504` 的**新鲜**候选（`release-build-info.json` 的 `source_commit` = HEAD、`source_dirty=false`、`candidate_id=rc-1018850`；`ACTIVE-CANDIDATE.json` status=ACTIVE），因此 `UEBENCH_ARTIFACT_DIR=dist/release` 下 Artifact Gate **66 passed / 0 skipped**。也就是说 `dist/release` **不是**陈旧产物——但这恰好暴露另一个问题：仓库同时存在**两套**都能自称「ACTIVE Candidate」的装配布局（`dist/candidate` 由 CI 使用，`dist/release` 由 `build_release.ps1`+`sync_release.ps1` 使用），而 ECQ-RS05 §11 要求的是**单一** ACTIVE Candidate。`dist/candidate` 在本机**不存在**。

**LEG-033 覆盖证据**：固定发布输入现在只有 `release/standard-packages/initial-standard-package-published.uebench`（`tests/test_release_source.py:271-308` 校验哈希并与 `PIN.json` 比对）。

**LEG-034 覆盖证据**：开发模式的构建身份读取职责，已由**打包路径**覆盖——`tools/write_build_info.py --payload-dir` 写入 `uebench/resources/build-identity.json`（`scripts/build_candidate.ps1:196-210`），并被 `tests/test_build_info_provenance.py:455-461` 断言存在于契约路径。而 `dist/release` 这个路径与 CI 实际产出的 `dist/candidate` **不一致**：在只跑 CI 候选构建的机器上，开发模式诊断页读不到身份（回落为 `未知（未嵌入构建身份）`，`build_identity.py:34`）。此外该读取**不校验** `source_commit` 是否等于当前 HEAD，会把任意历史身份的 `dist/release` 当作当前身份展示。

**LEG-039 覆盖证据**：`outputs/` 仅在 `docs/验收记录.md:217` 作为历史工作簿路径被提及（纯 prose），无任何代码引用；`tmp/` 无任何引用。

### 4.6 过时发布路径 / 退役打包输入

| ID | 位置 | 内容 | 触及阶段 | 分类 |
|---|---|---|---|---|
| LEG-041 | `tools/build_source_zip.py:99`（默认 `dist/release/UEBench-source-<版本>.zip`）**且被 `tests/test_release_source.py:403-454`（断言在 `:450`）钉住** | 源码包默认输出仍是旧布局 | 构建期 + 测试期 | `OBSOLETE` |
| LEG-042 | `tools/build_payload_manifest.py:106`（默认 `dist/release/payload-manifest.json`） | payload 清单默认输出旧布局 | 构建期 | `OBSOLETE` |
| LEG-043 | `tools/build_release_workbooks.mjs:8`（默认 `UEBENCH_WORKBOOK_OUTPUT_DIR=dist/release`） | 开发工作簿生成器 | 开发工具（零引用） | `OBSOLETE` |
| LEG-044 | `tools/build_release_templates.py:142`（默认 `--output-dir dist/release`） | Excel 模板生成 | 构建期 | `ACTIVE` |
| LEG-045 | `src/uebench/application/package_reconciliation.py:5-7`（docstring 仍称现场证据为 `2026.09-published.1` / 发布包为 `2026.10-published.3`） | 陈旧内部叙述 | 无 | `OBSOLETE` |
| LEG-046 | `tests/test_package_reconciliation.py:44`（注释「当前 = `2026.10-published.3`（r2）」） | 陈旧测试注释 | 无 | `OBSOLETE` |
| LEG-047 | `HANDOFF.md:143`（称 `scripts/sync_release.ps1:86` 按 `docs/宏观结构审计-20260905.md` 路径复制） | **失实断言** | 无 | `OBSOLETE` |

**LEG-041 说明（最容易被漏掉的一处）**：`tests/test_release_source.py:403-454` 是一个**正向断言**，它要求 `tools/build_source_zip.py` 的默认输出仍是 `dist/release/...`（`:450-453`）。因此「把默认输出改到 `dist/candidate`」这一改动**必须**同时修改该测试，否则 Source Gate 会红。CI 侧不受影响：`scripts/build_candidate.ps1:279` 总是显式传 `--output`。

**LEG-041/042/043 覆盖证据**：
- 源码包：`scripts/build_candidate.ps1:279-280` 显式 `--output (Join-Path $Release $Names.source)`；Artifact Gate `tests/test_release_artifacts.py:204-210`（`REQUIRED_KEYS` 含 `source`）+ `tools/audit_release.py:121-140` `required_files()`；一致性由 `tests/test_release_artifacts.py:231-248` 与 `tools/audit_release.py` 互相钉住。
- payload 清单：`scripts/build_candidate.ps1:274-275` 显式 `--output`；`tests/test_release_artifacts.py:381-400+` 复核同源树哈希。
- 工作簿：`grep -r "build_release_workbooks"` **零引用**（除自身）；0.2.0 只交付 GB29446 导入模板，由 `tools/build_release_templates.py` 经真实 `WorkbookTemplateService` 生成（`packaging/installer.iss:76-79` 注释与 `scripts/build_candidate.ps1:266-271`）。

**LEG-044 为何仍是 `ACTIVE`**：`packaging/installer.iss:79` 硬编码从 `..\dist\release\` 取模板，且 `tests/test_release_source.py:189-196` 断言 `dist\release\{模板名}` 必须出现在 `installer.iss` 内——即该 staging 路径被**Gate 钉住**。若要清理 `dist/release`（LEG-029），必须同时改这三处（iss + Gate + 构建脚本），否则发布链断开。

**LEG-045/046 覆盖证据**：决策表本身的职责由 `tests/test_package_reconciliation.py:359-433`（表驱动 `decide()` 穷尽性）与 `:434-880` 的真实流程用例覆盖；当前固定包身份由 `release/standard-packages/PIN.json:6-7`（`data_version 2026.10-published.4`、`package_id gb29446-r2-provenance-only-from-2026.10-published.3`）与 `tests/test_standard_package_revision.py:158-164` 断言。docstring / 注释中的旧版本号不承载任何机器语义。

**LEG-047 覆盖证据**：`grep -r "宏观结构审计"` 只命中该文档自身、`HANDOFF.md:143` 与 `docs/交接清单-2026-08-31.md:94`；`scripts/sync_release.ps1` 真正复制的文档清单在 `:220-232`（`docs\用户手册.md`、`docs\安装与发布说明-<版本>.md`、`docs\交付清单-<版本>.md`、`README.md`），**不含**该审计文档。`sync_release.ps1:86` 实际是 `throw` 语句。

### 4.7 被更新的 Gate 取代的旧测试 / 脚本

| ID | 位置 | 内容 | 触及阶段 | 分类 |
|---|---|---|---|---|
| LEG-048 | `tests/test_frozen_release.py`（**已不存在**，由 `tests/test_release_source.py:171-173` 断言必须不存在） | 旧冻结包检查（构建产物缺失时硬失败） | 无 | `OBSOLETE` |
| LEG-049 | `tests/conftest.py:10-32` 的 xfail-strict 标记 → `tests/test_gb29446.py:150`、`:163` | 记录旧 ROUND6 契约的「可执行历史证据」 | 测试期（xfail） | `OBSOLETE` |
| LEG-050 | `tests/test_standard_package_revision.py:151-156`（`PINNED.stat().st_size == record["size"]`、`sha256_of(PINNED) == record["sha256"]`） | 与 Source Gate 重复的钉校验 | 测试期 | `OBSOLETE` |
| LEG-051 | `tests/test_source_zip.py:8-20` | 源码包必须含 `standards/development` 基线 | 测试期 | `ACTIVE` |

**LEG-048 覆盖证据**：Artifact Gate `tests/test_release_artifacts.py`（由 `UEBENCH_ARTIFACT_DIR` 启用，CI 在 `windows-release-candidate.yml:187-192` 显式运行）+ Source Gate `tests/test_release_source.py:151-173`（结构性禁止把构建产物目录当作断言路径）。**前置条件已成立**，无需再动。

**LEG-049 覆盖证据**：`tests/conftest.py:26-31` 自己写明「corrected full-value behavior is asserted by `tests/pilots/numeric/test_qzc_n01_a.py`」；冻结向量由 `tests/conformance/numeric/test_ecquota_numeric_v1.py` + `tests/conformance/numeric/ecquota_numeric_v1_vectors.json` 真实执行。本次实测 `tests/test_gb29446.py` 中 6 个用例以 `x`（xfail）结算，说明它们**不可能**变绿，其断言价值已由 N01-A 覆盖；若保留，应移到「历史证据」目录而不是留在会读汇总行的全量套件里。

**LEG-050 覆盖证据**：`tests/test_release_source.py:300-308`（`test_pinned_package_sha256_matches_pin`，断言 `pin["size"] == package.stat().st_size`、`actual == pin["sha256"]`）是同一职责的 Source Gate 版本，且该文件在 CI 中被**显式**运行（`windows-release-candidate.yml:99-101`）。`tests/test_standard_package_revision.py` 的**独有价值**在于 `:167-179`（无 sources/PDF）、`:181-192`（GB29446 r2 + `coal_type` 选择结构）、`:195-210`（真实 Ed25519 验签），这些应保留。

**LEG-051 说明**：`tests/test_source_zip.py:16-20` 断言 `standards/development/README.md`、`manifest.json`、`library-index.json`、`scope-63/scope-63.json` 与 `scope-63/definitions/` 在源码包内。Source Gate 的 `tests/test_release_source.py:376-387` 只覆盖 `MANDATORY_ROOT_FILES`（根级治理文档），**不含** `standards/development`，因此 `tests/test_source_zip.py` 仍有独立覆盖 → 保留。

### 4.8 工具 / 测试真正读取的文档

| ID | 文档 | 读取代码 | 阶段 | 分类 |
|---|---|---|---|---|
| LEG-052 | `README.md`、`docs/*.md`（**仅顶层**，`glob("*.md")`）、`TASK_STATE.md`、`HANDOFF.md`、`参考标准开发路线.md` | `tests/test_document_hygiene.py:5`（`STABLE_DOCUMENTS`）、`:9`（`README.md` + `docs/*.md`）、`:11-16`（禁止 `\t`/控制字符、禁止行尾空白）、`:27-39`（解析 `RS0x` 阶段状态表）、`:42-50`（三份稳定文档阶段状态必须一致、禁止「等待独立验收」等措辞） | 测试期 | `ACTIVE` |
| LEG-053 | `STANDARD_ISSUES_REGISTER.md` | `tests/test_gb29446_product_golden.py:42`（`ISSUE_REGISTER_PATH`）、`:270-296`（按 `### <issue_id>` 定位小节并解析 `\| 状态 \| ... \|` 行，结果进入 `applicability_report()` 的 `standard_issue_status`） | 测试期 | `ACTIVE` |
| LEG-054 | `AGENTS.md`、`platform-lock.json`、`PLATFORM_BASELINE.md`、`TASK_STATE.md`、`HANDOFF.md`、`STANDARD_ISSUES_REGISTER.md`、`参考标准开发路线.md`、`README.md` | `tools/build_source_zip.py:20-37`（`ROOT_FILES`）、`:41-51`（`MANDATORY_ROOT_FILES`）、`:79-86`（缺失即 `SystemExit`）；`tests/test_release_source.py:55-63`（镜像清单）、`:376-387`（真实构建并断言全在源码包内）、`:390-400`（缺治理文件必须 `SystemExit`，不得静默跳过） | 构建期 + 测试期 | `ACTIVE` |
| LEG-055 | `docs/用户手册.md`、`docs/安装与发布说明-<版本>.md`、`docs/交付清单-<版本>.md`、`README.md` | `scripts/build_candidate.ps1:304-313` 与 `scripts/sync_release.ps1:220-232`（缺失即 `throw`）；`packaging/installer.iss:80-85`（`Source:` 项）；文档名由 `tools/release_version.py:187-188` 派生，并由 `tests/test_release_version_consistency.py:246-247`、`tests/test_candidate_identity.py:287-288` 断言宏化 | 构建期 | `ACTIVE` |
| LEG-056 | `standards/development/README.md`（源码包内路径） | `tests/test_source_zip.py:16` | 测试期 | `ACTIVE` |
| LEG-057 | `standards/development/scope-65/definitions/*.json` | `tests/test_evaluation_support.py:27`（`DEFINITIONS`）、`:38-49`（`_definition()` / `_installed_definitions()` 用 `assert path.is_file()`——**不是 skip**） | 测试期 | `REFERENCE_ONLY` |
| LEG-058 | `standards/development/scope-65/`（`scope-65.json` + 定义） | `tests/test_next_scope_65.py:12`（`ROOT = .../scope-65`）、`:23`（读 `scope-65.json`） | 测试期 | `REFERENCE_ONLY` |
| LEG-059 | `standards/development/scope-63/scope-63.json` + `scope-65/scope-65.json` + `data/standard-replacements.json` | `tests/test_version_identity.py:32-45`（断言 `legacy_only ⊆ 替代关系 keys` 且映射结果 ⊆ canonical） | 测试期 | `ACTIVE` |
| LEG-060 | `standards/development/scope-63/verification/snapshot-comparison.json` | `tests/test_snapshot_merge.py:11-37`（断言 `merge_decision` 前缀、canonical/legacy 根路径、`scope-63` 内无 `scope-65.json` 别名） | 测试期 | `ACTIVE` |
| LEG-061 | `standards/development/scope-65/`（71 个被跟踪文件） | 无工具读取（仅 `:057`、`:058` 两个测试与 `:059` 的映射断言） | 测试期 | `REFERENCE_ONLY` |
| LEG-062 | `src/uebench/application/official_sources.py:46-50`（docstring 引用 `standards/development/scope-65/definitions/gb-29446-2019.json`） | 仅注释，无读取 | 无 | `OBSOLETE` |

**LEG-052 的硬约束**：`tests/test_document_hygiene.py:9` 使用的是 `(ROOT / "docs").glob("*.md")`——**只扫顶层**，不递归。因此把历史文档移入 `docs/history/` 或 `docs/audits/` **不会**削弱该测试对活文档的检查（`docs/audits/UI_CURRENT_STATE_AUDIT.md`、`docs/governance/*`、`docs/history/*` 目前都不被它扫描）。
同时 `:24` 的 `_STATE` 正则与 `:30-31` 的两条匹配规则要求三份稳定文档（`TASK_STATE.md` / `HANDOFF.md` / `参考标准开发路线.md`）都含 `ECQ-GOV01` 与 `RS01`–`RS06` 的阶段状态，且三者取值集合完全一致。**任何**对这三份文档阶段状态表的重写都必须保持该一致性，否则该 Gate 失败。

**LEG-053 的硬约束**：Golden 的适用性报告依赖从 `STANDARD_ISSUES_REGISTER.md` 解析出的状态字符串（`_issue_status()` 会剥离反引号 / 星号并按 `（` 截断）。因此该 register 的 `### <issue_id>` 小节结构与 `| 状态 | ... |` 行是**机器可读契约**，不是纯 prose；重排表格或改写状态行会直接改变 Golden 的判定输入。

**LEG-057 / LEG-058 / LEG-061 说明**：`standards/development/scope-65` 是被跟踪的 71 个文件，它是**被取代的历史快照**（`snapshot-comparison.json` 显示 scope-65 为 65 项、含 4 项已被替代的旧版标准 `GB 29141-2012` / `GB 29435-2012` / `GB 29437-2012` / `GB 29441-2012`；scope-63 为 63 项 = 46 published + 17 draft）。`standards/development/manifest.json:3-5` 与 `library-index.json:5-9` 都把它登记为 `comparison_snapshots` / `legacy_scopes`，并明确「仅作历史对照，禁止作为发布入口」。
因此 scope-65 按本审计口径属于 `REFERENCE_ONLY`：应当移出活动仓库，只保留脚本 / 测试读取的那份**最小可比证据**（例如 `snapshot-comparison.json` 已经固化的对照结论 + 4 项旧版标准的替代关系），或改为由归档提供。
**注意区分**：`tests/test_evaluation_support.py:27` 把 `scope-65/definitions` 当作「真实已安装标准」来加载受支持性登记表，这在语义上就是**用了历史快照当现行数据**；应改指 `standards/development/scope-63/definitions` 或 `data/definitions`（后者才是运行期真值源，见 `src/uebench/application/facade.py:124`）。

**LEG-062 覆盖证据**：GB29446 定义的权威副本是 `data/definitions/gb-29446-2019.json` 与 `standards/development/scope-63/definitions/gb-29446-2019.json`，两者一致性由 `tests/test_gb29446_reference_slice.py:392-397` 断言。`official_sources.py` 的 URL 常量本身由 `tests/test_official_sources.py:50-76` 与 `:116-137` 覆盖，docstring 中的来源描述不参与运行。

## 5. 明确回答四个问题

### 问题 1：是否有 CI workflow 依赖 `G:\` 或任何本机外部归档才能获得完整覆盖？

**没有任何 workflow 在语法上引用 `G:\` 或归档路径。** 对 `.github/workflows/*` 检索 `archive|G:|ECQuota-Archive|legacy|LEGACY|work/signing` 只命中：

- `numeric-v1-adoption.yml:41,47,50`——「legacy global ROUND6」字符串断言，与归档无关；
- `qzc-n01-a.yml:42`——步骤名「legacy migration evidence」，与归档无关。

**但「完整覆盖」这一目标确实被破坏。** 三个 workflow 只通过「全量套件」步骤触达归档相关测试，而这些测试在 runner 上全部 skip：

| workflow | job | step（行） | 结果 |
|---|---|---|---|
| `numeric-v1-adoption.yml` | `numeric-pilot`… 实为 job `numeric-v1-adoption` | `Execute literal full suite` id=`literal_full_suite`（`:95-101`）；`Verify all tests`（`:103-106`） | 16 个归档相关用例 + 1 个 `work/signing` 用例 skip |
| `qzc-n01-a.yml` | `numeric-pilot` | `Execute literal full suite` id=`literal_full_suite`（`:58-64`）；`Verify all tests`（`:66-69`） | 同上 |
| `windows-release-candidate.yml` | `release-candidate` | `Execute literal full suite` id=`literal_full_suite`（`:103-109`，`continue-on-error: true`） | 同上；Artifact Gate 另有独立步骤（`:187-192`，`UEBENCH_ARTIFACT_DIR=dist/candidate`） |

即：**发布链本身不依赖 `G:\`，但「旧版兼容 / 升级 / 对账」这块覆盖在 CI 上是空的**，而且它是静默的（skip 而非 fail），与「核心兼容覆盖不得因归档缺失而丢失」的规则冲突。三个 workflow 都没有任何步骤去准备该归档或替代夹具。

### 问题 2：哪些核心兼容测试在外部资产缺失时会 skip？

以下为 HEAD 行号。实测：归档存在时这 4 个文件 **54 passed / 0 skipped**；归档被改指到不存在路径、且无 `work/signing` 时 **17 skipped**（16 归档 + 1 私钥）。

| 测试 id | skip guard 位置 |
|---|---|
| `tests/test_standard_package_revision.py::test_parent_baseline_is_byte_identical_to_the_archived_copy`（`:224`） | `:218-221` `_parent_or_skip()`（`if not PARENT.is_file(): pytest.skip(ARCHIVE_UNAVAILABLE)`） |
| `tests/test_standard_package_revision.py::test_every_definition_is_byte_identical_to_the_parent_baseline`（`:233`） | 同上 `:218-221` |
| `tests/test_standard_package_revision.py::test_only_sources_were_removed_from_the_parent_baseline`（`:259`） | 同上 `:218-221` |
| `tests/test_package_reconciliation.py::test_empty_library_installs_bundled_package`（`:434`） | `:66-69` `require_pinned_packages()`（同时要求旧包与当前包） |
| `tests/test_package_reconciliation.py::test_second_reconciliation_is_noop_without_backup_or_audit_noise`（`:473`） | 同上 `:66-69` |
| `tests/test_package_reconciliation.py::test_older_installed_package_is_upgraded_to_bundled`（`:506`） | 同上 `:66-69` |
| `tests/test_package_reconciliation.py::test_newer_installed_package_refuses_downgrade`（`:576`） | 同上 `:66-69` |
| `tests/test_package_reconciliation.py::test_invalid_bundled_package_installs_nothing_and_keeps_existing_data`（`:710`） | 同上 `:66-69` |
| `tests/test_package_reconciliation.py::test_content_conflict_with_installed_rules_is_conflict_not_invalid`（`:745`） | 同上 `:66-69` |
| `tests/test_package_reconciliation.py::test_upgrade_preserves_saved_evaluation_snapshot`（`:800`） | 同上 `:66-69` |
| `tests/test_package_reconciliation.py::test_bundled_discovery_prefers_highest_data_version_not_last_filename`（`:851`） | 同上 `:66-69` |
| `tests/test_package_reconciliation.py::test_same_data_version_different_identity_conflicts_without_overwrite`（`:604`） | `:126-127` `developer_private_key()`（`work/signing/development-private-key.pem`） |
| `tests/test_package_install_safety.py::test_upgrade_of_legacy_data_directory_removes_installed_pdfs`（`:299`） | `:93-95` `require_legacy_package()` |
| `tests/test_package_install_safety.py::test_cleanup_scope_never_touches_user_documents`（`:388`） | 同上 `:93-95` |
| `tests/test_package_install_safety.py::test_business_data_survives_the_upgrade_and_cleanup`（`:466`） | 同上 `:93-95` |
| `tests/test_package_install_safety.py::test_real_legacy_package_ships_sources_but_never_lands_them`（`:652`） | 同上 `:93-95` |
| `tests/test_gb29446_evaluate_wiring.py::test_setup_has_both_revisions_installed`（`:118`） | `:125-126`（`if not LEGACY_PACKAGE.is_file(): pytest.skip(...)`） |

**skip 的根因链**：`tests/_legacy_assets.py:73-75`——当归档原件不存在时，`legacy_package()` **故意返回一个不存在的路径**（注释原文：「deliberately non-existent -> skip guards fire」），使调用方 `pytest.mark.skipif(not X.is_file())` 式的守卫触发。这是一种「不报错但静默降级」的设计；它保证了错误信息干净，但也保证了覆盖丢失不会被发现。

**另需注意（非归档但同为外部资产）**：`tests/test_release_artifacts.py:97-111` 的 session 级 `artifact_dir` fixture 在 `UEBENCH_ARTIFACT_DIR` 未设置时 skip，实测使 **76 个** Artifact Gate 用例全部 skip。这是**设计如此**（CI 在 `windows-release-candidate.yml:187-192` 专门设置该变量运行），不构成覆盖丢失，但「全量套件」步骤（`continue-on-error: true`）里的这 76 个 skip 也应被理解为「未执行」而不是「通过」。

### 问题 3：哪些旧发布路径仍被活的脚本 / 测试引用（区别于 prose）？

**A. `dist/release`（旧候选装配布局）—— 9 处活的引用**

| 引用点 | 性质 |
|---|---|
| `scripts/sync_release.ps1:43`（默认 `$ReleaseDir = dist\release`）、`:131-139`（清空后装配）、`:280-282`（审计输出） | 本地装配入口 |
| `scripts/build_release.ps1:153`（`$DefaultReleaseDir`）、`:159-163`（清空） | 本地清理 |
| `scripts/build_candidate.ps1:219`、`:268`（`build_release_templates.py --output-dir dist\release`）、`:270-271`（从该处复制模板到候选目录） | **CI 也走这条**：为满足 `installer.iss:79` |
| `packaging/installer.iss:79`（`Source: "..\dist\release\GB29446选煤电力消耗限额导入模板.xlsx"`） | 构建期输入 |
| `src/uebench/application/build_identity.py:42`、`:206-207`（运行期 dev 模式读 `dist/release/release-build-info.json`） | **运行期** |
| `tools/build_source_zip.py:99`（默认输出）、`tools/build_payload_manifest.py:106`（默认输出）、`tools/build_release_templates.py:142`（默认目录）、`tools/build_release_workbooks.mjs:8`（默认目录） | 默认值 |
| `tests/test_release_source.py:450`（**断言**默认输出就是 `dist/release/...`） | 测试期（正向钉住） |
| `tests/test_build_info_provenance.py:628`（注释，说明 `build_release.ps1` 必须清空陈旧 `dist\release`） | 仅注释 |

**B. `dist/standard-packages`（已废弃的标准包布局，本机该目录存在但为空）—— 3 处**
`tools/capture_ui.py:28`（回退搜索）、`tools/build_initial_package.py:44`（默认输出）、`tools/publish_confirmed_rules.py:78`（默认输出）。

**C. `dist/candidate`（当前 CI 布局）—— 3 处**
`windows-release-candidate.yml:126`（`-OutputDir "dist/candidate"`）、`:190`（`UEBENCH_ARTIFACT_DIR: dist/candidate`）、`:192`；`scripts/build_candidate.ps1:152`（默认 `dist\candidate-{Version}`）。

**D. 0.1.0 产物名（`UEBench-0.1.0-win-x64.zip` 等）—— 0 处活的引用**
`tests/test_release_version_consistency.py:74` 只是一条字符串说明（`"dist/** (0.1.0 legacy artifacts are historical evidence, never rebuilt)"`，属于 `_OUT_OF_SCOPE_LEGACY` 注释元组）；`tests/test_upgrade_0_1_0_to_0_2_0.py:20-29` 与 `tools/build_legacy_0_1_0_fixture.py:28` 只在 docstring 里叙述历史快照，代码在 `tmp_path` 现场生成夹具。**结论：没有任何活代码读取 0.1.0 发布物。**

**E. 旧标准包文件路径（`initial-standard-package-2026.09-published.2.uebench` / `-2026.10-published.3.uebench`）—— 仅「断言不存在」**
`tests/test_standard_package_revision.py:108-115`（断言这两个文件**不存在**于 `release/standard-packages/`）；`release/standard-packages/LEGACY-REFERENCE.json:7,16` 只记录**归档内**的相对路径。

**F. `dist/archive/SUPERSEDED-candidate-2026-10-04-before-identity` —— 0 处活的引用**
只出现在 `TASK_STATE.md:170-171` 与 `docs/governance/RS05_EXECUTION_REPORT.md:666-667`（prose）。实际归档位置是 `G:\ECQuota-Archive\ECQ-RS05-LEGACY-REFERENCE-ONLY\superseded-candidates\`。

### 问题 4：哪些文档被工具 / 测试真正解析或读取（path + 读取代码）？

**被解析内容的（内容即契约）**

1. `TASK_STATE.md`、`HANDOFF.md`、`参考标准开发路线.md` ← `tests/test_document_hygiene.py:5`（常量）与 `:42-50`（`_stage_states()` 在 `:27-39` 解析 `RS0x` 阶段状态表，并要求三份文档取值一致）；另 `:14-16` 要求这三份文档无行尾空白，`:11-13` 要求它们与 `README.md`、`docs/*.md` 无 `\t`/控制字符。
2. `README.md`、`docs/*.md`（顶层 glob） ← `tests/test_document_hygiene.py:9`。
3. `STANDARD_ISSUES_REGISTER.md` ← `tests/test_gb29446_product_golden.py:42`（路径常量）、`:270-296`（`ISSUE_ROW_RE` + `_issue_status()`：按 `### <issue_id>` 切段、解析 `| 状态 | … |`），结果进入 `applicability_report()["standard_issue_status"]`。
4. `standards/development/README.md`（源码包成员名） ← `tests/test_source_zip.py:16`。

**被读取为构建输入（缺失即硬失败，内容不解析）**

5. `AGENTS.md`、`platform-lock.json`、`PLATFORM_BASELINE.md`、`TASK_STATE.md`、`HANDOFF.md`、`STANDARD_ISSUES_REGISTER.md`、`参考标准开发路线.md`、`README.md` ← `tools/build_source_zip.py:20-37`（`ROOT_FILES`）、`:41-51`（`MANDATORY_ROOT_FILES`）、`:79-86`（缺失即 `raise SystemExit`）；镜像断言在 `tests/test_release_source.py:55-63`，真实构建断言在 `:376-400`。
6. `docs/用户手册.md`、`docs/安装与发布说明-<版本>.md`、`docs/交付清单-<版本>.md` ← `scripts/build_candidate.ps1:304-313`、`scripts/sync_release.ps1:220-232`（缺失即 `throw`）；`packaging/installer.iss:80-85`（`Source:`）；名字由 `tools/release_version.py:187-188` 生成，宏化由 `tests/test_release_version_consistency.py:246-247` 与 `tests/test_candidate_identity.py:287-288` 断言。

**明确「不被读取」的文档（避免误判）**

- `tests/test_release_version_consistency.py:73-84` 把 `docs/安装发布说明.md`、`docs/交付清单.md`、`docs/非程序员验收与AI开发教程.md`、`docs/验收记录.md`、`docs/history/**`、`TASK_STATE.md`、`HANDOFF.md`、`README.md`、`参考标准开发路线.md` 列为 `_OUT_OF_SCOPE_LEGACY`——**只是声明不扫描**，不读取内容。
- `docs/统一判定规范.md`、`docs/governance/NUMERIC_V1_ADOPTION_REPORT.md`、`platform-lock.json` 的**内容**没有任何 Python 工具解析（`grep -r "统一判定规范" --include=*.py` 无命中；`platform-lock.json` 只被 `tools/build_source_zip.py:31,44` 当作**要打包的文件名**）。它们是**人读**权威，不是机器契约。
- `HANDOFF.md:143` 声称 `scripts/sync_release.ps1:86` 会按 `docs/宏观结构审计-20260905.md` 的路径复制该文件——**不成立**（见 LEG-047）。

## 6. 最锐利的风险（按严重度排序）

1. **CI 上「旧版兼容 / 升级 / 对账」覆盖为 0，且是静默的。** 17 个用例（16 归档 + 1 私钥）在三个 workflow 里全部 skip，没有任何替代步骤，也没有任何步骤会因此失败。这正是「核心兼容覆盖不得因归档缺失而丢失」所禁止的状态。其中 **13 个可以用仓内确定性夹具恢复**（`tests/test_package_reconciliation.py:136-160`、`tests/test_package_install_safety.py:143-190` 已具备造签名包 / 造带 `sources/*` 包的能力），**1 个**（`tests/test_package_install_safety.py:652`）与 **3 个**（`tests/test_standard_package_revision.py:224,233,259`）属于真实归档证据，应显式标记为 evidence 并排除在核心覆盖统计之外，而不是靠 skip 假装「通过」。
2. **`tests/test_release_source.py:450` 正向钉住了 `dist/release` 这个旧默认输出。** 任何把 `build_source_zip.py` 默认输出改到新布局的动作，都会让 Source Gate 变红；这是一处「改了代码忘了改 Gate」的陷阱，必须成对修改。
3. **`installer.iss:79` + `tests/test_release_source.py:194` + `build_candidate.ps1:218-271` 三方把 `dist\release` 钉在发布链上。** 目前存在两套都能声明 ACTIVE Candidate 的装配布局（`dist/candidate` 与 `dist/release`），与 ECQ-RS05 §11「单一 ACTIVE Candidate」冲突；本机 `dist/candidate` **不存在**，而 `dist/release` 里放着 head `10188504` 的新鲜候选并通过 Artifact Gate（实测 66 passed）。清理 `dist/release` 必须同时改 iss、Gate 与构建脚本。
4. **`src/uebench/application/build_identity.py:42` 在运行期读 `dist/release`，且不校验 `source_commit == HEAD`。** 后果有二：(a) 与 CI 产出的 `dist/candidate` 不一致，只跑 CI 候选的机器上诊断页永远显示「未知（未嵌入构建身份）」；(b) 本机只要残留任意历史 `dist/release`，诊断页就会把**旧构建身份**当作当前身份展示（好在当前值恰好等于 HEAD）。这一职责已由 payload 内 `uebench/resources/build-identity.json`（`build_candidate.ps1:196-210`，`tests/test_build_info_provenance.py:455-461`）覆盖。
5. **`standards/development/scope-65` 既是被取代的历史快照，又被现行测试当数据源。** 71 个被跟踪文件；`tests/test_evaluation_support.py:27` 甚至把它当「真实已安装标准」加载，而运行期真值源是 `data/definitions`（`facade.py:124`）。这既是 `REFERENCE_ONLY` 应移出的对象，也是一处语义错位。
6. **`tools/windows_runtime_evidence.py:25` 硬编码 `G:\Python Project\能耗限额`**，违反 `AGENTS.md` §1.1；且它在模块导入时就要求归档可用（`:46`），无法只执行 Part A。它是当前**唯一**的 Windows 运行期取证脚本，而「Windows 验收证据不完整」仍是 OPEN 项，所以不能简单删除，应先做「路径参数化 + 惰性复制」。
7. **工作树当前为 `source_dirty=true`**（并发改动 5 个文件 + 1 个未跟踪文件）。`scripts/build_candidate.ps1:110-112` 会拒绝正式候选构建；`-AllowDirty` 分支不写 `ACTIVE-CANDIDATE.json` 也不跑 Artifact Gate。任何收口动作前必须先落盘提交。
8. **`tests/test_package_reconciliation.py:44` 的注释与 `package_reconciliation.py:5-7` 的 docstring 仍在说 `2026.10-published.3` 是「当前」包**，实际固定包已是 `2026.10-published.4`。这不影响行为，但会让后续审计/复核者按错误版本理解对账决策表。
9. **`do` 级联陈旧引用**：`tools/capture_ui.py:28`、`tools/build_initial_package.py:44`、`tools/publish_confirmed_rules.py:78` 三个工具默认写/读已被废弃的 `dist/standard-packages/`（本机该目录存在但为空），容易让人误以为那里还有资产。
10. **`HANDOFF.md:143` 的失实脚本引用**（声称 `sync_release.ps1:86` 复制 `docs/宏观结构审计-20260905.md`）。这会误导后续把历史文档「保留在 docs/ 原位」的判断——实际没有任何脚本引用该文件，因此它可以自由移入 `docs/history/`（也不会影响 `tests/test_document_hygiene.py`，因为它只 glob `docs/*.md` 顶层）。

## 7. 建议的处置顺序（仅建议，本审计不执行）

1. 先提交/落盘当前并发改动，让工作树恢复 `source_dirty=false`。
2. 把 13 个「本可用合成夹具」的兼容用例改为确定性仓内夹具（临时 Ed25519 密钥对 + 合成的带 `sources/*` 包 / 低 `data_version` 包），使它们在 CI 上真实执行。
3. 把 `tests/test_standard_package_revision.py:224,233,259` 与 `tests/test_package_install_safety.py:652` 显式标记为 `evidence`，从核心覆盖统计中排除，并保留「归档缺失即 skip」的语义（因为它们**不可能**在 CI 上成立）。
4. `LEGACY-REFERENCE.json:5` 的归档根改为 `ECQ_LEGACY_ARCHIVE` 环境变量可覆盖，缺省保留常量。
5. 统一候选布局：让 `build_source_zip.py:99` / `build_payload_manifest.py:106` / `build_release_workbooks.mjs:8` 的默认值与 `tests/test_release_source.py:450` 同步指向新布局，或彻底移除默认值改为必填；处理 `installer.iss:79` 的模板 staging 与 `dist/release` 的耦合。
6. `build_identity.py:42` 的 dev 回退改为读 `dist/candidate`，或不读（依赖 payload 内身份）。
7. `scope-65` 移入外部归档，`tests/test_evaluation_support.py:27` 改指 `data/definitions`；`LEG-057/058` 改为读取归档快照或改为读取 `snapshot-comparison.json` 已固化的结论。
8. `tools/windows_runtime_evidence.py` 路径参数化；`tools/build_initial_package.py` 删除；`tools/capture_ui.py:28` 与 `tools/publish_confirmed_rules.py:78` 默认路径更新。
9. 最后一并清理 prose 与陈旧注释（LEG-045/046/047），以及本机 `dist/installer/UEBench-Setup-0.1.0-x64.exe`、空的 `dist/standard-packages/`、`tmp/`、`outputs/`。

## 8. 附：本次实测证据

### 8.1 归档可用（真实仓库，基线）

```
pytest tests/test_standard_package_revision.py            -> 11 passed
pytest tests/test_package_reconciliation.py               -> 24 passed
pytest tests/test_package_install_safety.py               -> 10 passed
pytest tests/test_gb29446_evaluate_wiring.py              ->  9 passed
合计 54 passed / 0 skipped
```

### 8.2 归档不可用 + 无 `work/signing`（CI 等价；`G:\tmp` 中 HEAD 副本，`archive_root` 改指不存在路径）

```
pytest tests/test_standard_package_revision.py            ->  8 passed, 3 skipped
pytest tests/test_package_reconciliation.py               -> 15 passed, 9 skipped
pytest tests/test_package_install_safety.py               ->  6 passed, 4 skipped
pytest tests/test_gb29446_evaluate_wiring.py              ->  8 passed, 1 skipped
合计 37 passed / 17 skipped
```

明细（`-rs`）：

```
SKIPPED [3] tests/test_standard_package_revision.py:220  父基线标准包已归档为 SUPERSEDED / REFERENCE ONLY（项目外只读区）且当前不可用
SKIPPED [8] tests/test_package_reconciliation.py:69      缺少固定标准包：…\parent_baseline\initial-standard-package-2026.09-published.2.uebench
SKIPPED [1] tests/test_package_reconciliation.py:127     缺少开发签名私钥：work/signing/development-private-key.pem
SKIPPED [4] tests/test_package_install_safety.py:95      缺少归档旧标准包：…\initial-standard-package-2026.09-published.2.uebench
SKIPPED [1] tests/test_gb29446_evaluate_wiring.py:126    旧包归档不可用（CI 无项目外只读归档），无法构造 r1+r2 并存状态
```

### 8.3 Gate 类文件（同一 CI 等价副本）

```
pytest tests/test_release_source.py tests/test_release_artifacts.py \
       tests/test_release_version_consistency.py tests/test_document_hygiene.py \
       tests/test_candidate_identity.py tests/test_source_zip.py \
       tests/test_ui_release_scope.py tests/test_evaluation_scope_enforcement.py
-> 全部 passed，仅 test_release_artifacts.py 的 76 个用例因 UEBENCH_ARTIFACT_DIR 未设置而 SKIP（设计如此）
```

### 8.4 Artifact Gate 对本机 `dist/release`

```
UEBENCH_ARTIFACT_DIR=dist/release pytest tests/test_release_artifacts.py -> 66 passed, 0 skipped
```

`dist/release/release-build-info.json`：`candidate_id=rc-1018850`、`source_commit=101885042d1e0e675462229f7cd69a4c4ebdba91`（= HEAD）、`source_dirty=false`、`standard_data_version=2026.10-published.4`、`standard_package_sha256=023d5caf…e77ff`；`ACTIVE-CANDIDATE.json`：`status=ACTIVE`、`schema=ecq.active-candidate.v1`。
`dist/candidate`：**不存在**。
`dist/standard-packages`：**存在但为空**。
`work/signing/development-private-key.pem`：**存在**（本机）。

### 8.5 归档实况（只读列出）

```
G:\ECQuota-Archive\ECQ-RS05-LEGACY-REFERENCE-ONLY\
  LEGACY-ARCHIVE.json, README.md
  legacy-releases\0.1.0\{UEBench-0.1.0-win-x64.zip, UEBench-source-0.1.0.zip}
  standard-packages\initial-standard-package-2026.09-published.2.uebench
  superseded-packages\initial-standard-package-{0.1.0,44-candidate,46-candidate,published}.uebench
  superseded-packages\SUPERSEDED-2026-10-05-before-source-free\initial-standard-package-2026.10-published.3.uebench
  superseded-candidates\SUPERSEDED-INVENTORY.json + SUPERSEDED-candidate-2026-10-04-before-identity\（14 文件）
  user-library\UEBench-reviewed-202608\（47 文件）
```

### 8.6 本次观察到的并发改动（不属于本审计结论）

审计期间另一个任务在同一工作区修改了：`src/uebench/infrastructure/packages.py`、`src/uebench/ui/main_window.py`、`tests/_legacy_assets.py`（108 → 352 行）、`tests/test_package_install_safety.py`、`tests/test_ui.py`、`tests/test_ui_release_scope.py`，并新增未跟踪文件 `tests/test_package_legacy_layouts.py`（1089 行）。该组改动在审计收尾阶段仍在继续（`tests/test_package_install_safety.py` 是在审计后期才进入修改列表的）。
其中 `tests/_legacy_assets.py` 已被改写为「**合成旧布局夹具**（`flat` / `sources-dir` / `both`，测试时生成临时 Ed25519 密钥对，不依赖归档与 `work/signing`）+ 归档历史包（仅证据）」的混合模块，`tests/test_package_legacy_layouts.py` 的 docstring 明确声明「不依赖 `G:\ECQuota-Archive`、不依赖 `work/signing/development-private-key.pem`，也不会因为二者缺失而 skip」。
这与本审计第 7 节建议 2 的方向一致，说明**第 4.4 节 LEG-025/026/028 的处置已在并发进行中**；父任务应先确认这批改动的归属与完成度，避免重复实现。

## 9. 未修改声明

本审计**只创建了本文件**（`docs/governance/RS05_LEGACY_DEPENDENCY_AUDIT.md`）。
- 仓库内其他文件未被本审计创建、修改、移动或删除；`git status` 中 `src/uebench/infrastructure/packages.py`、`src/uebench/ui/main_window.py`、`tests/_legacy_assets.py`、`tests/test_package_install_safety.py`、`tests/test_ui.py`、`tests/test_ui_release_scope.py`、`tests/test_package_legacy_layouts.py` 的改动**均非本审计所为**（见第 8.6 节）；
- `G:\ECQuota-Archive` 只被读取（`LEGACY-ARCHIVE.json` 与文件列表），未被写入或改变；
- 归档模拟在 `G:\tmp\ecq-legacy-audit\` 下的独立副本中进行，副本与 `--basetemp` 均在审计结束后删除；
- 未执行 `git add` / `git commit` / `git push`。
