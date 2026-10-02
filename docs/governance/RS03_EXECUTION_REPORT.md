# ECQ-RS03 — GB29446 Excel Adapter Closure 执行报告

状态：**执行完成，等待独立验收**（本任务不合并、不开始 RS04）。

## 1. 基线

| 项目 | 值 |
|---|---|
| execution base（`main`） | `abf97049e5667573656b6e1c6461916e57d77991` |
| 工作分支 | `feat/ecq-rs03-gb29446-excel-adapter` |
| Canonical repository | `https://github.com/adgo07/ECQuota-Insight.git`（`git remote get-url origin` 已实际核实一致） |

开工时 `git fetch origin` 首次因 `TLS connect error: unexpected eof while reading` 失败，重试即成功（`3d4ca16..abf9704 main`）。**未绕过最新 main 核实**：本地 `origin/main` 在 fetch 后与任务书给出的 `abf97049…` 完全一致。

未跟踪文件 `.acl-recovery/`、`.rs02-check/`、`PR_BODY_DRAFT.md` 全程保留、未覆盖、未提交。

## 2. 平台 / Contract 预检查

| 项目 | 结果 |
|---|---|
| `platform-lock.json` | 锁定中央 `ee5feb0cc34dbd99790500fadd0c4c932e202a20`（`auto_follow_main: false`），**未修改** |
| 中央 Frozen（按 locked SHA 读取） | Architecture V2.1 FROZEN；Numeric Contract v1；Numeric Profiles v1；Numeric Conformance Vector v1 |
| 中央 ACTIVE Guide（按中央当前版本读取） | `docs/GUIDE_INDEX.md` 路由 → `PRODUCT_DELIVERY_POLICY_V1.md`、`UI_DESIGN_GUIDELINES_V0.1.md` |
| 本任务相关 Frozen Contract | Architecture V2.1（Domain/Application 不得依赖 Excel 对象）；Numeric Contract v1 §2 / §2.1 / §8.3 / §8.4 |
| 适用 MUST | 权威数值入口必须声明外部表示如何成为 normalized authoritative value；Excel 不得成为第二套业务算法；GUI 与 Excel 必须共用同一 Application/Domain/Calculator |
| 适用 MUST NOT | 不得把未声明的 binary float 转换路径变成业务权威；不得用 `format→text→parse back` 制造比较值；不得因显示值回流正式比较 |
| 是否存在与当前任务相关的 Standard Issue | **是** |
| 涉及的问题编号 | `ECQ-STD-GB29446-001`（`PROVISIONAL`，本次只引用，未改变其口径） |
| 本任务是否改变既有软件解释 | **否** |
| 是否发现冲突 | 发现并修复本仓 `LOCAL DEFECT`（Excel ingress contract 不一致、committed 卡死）；无中央 Contract 冲突 |
| 是否需要修改中央 Contract | **否** |
| `D-ECQ-006` 状态 | **仍 OPEN**。本任务只收紧本仓入口，**不声称中央 lossless XLSX 公共方案已冻结** |

**Numeric 不变更声明**：Numeric Contract v1、`ECQUOTA_DECIMAL_FULL_VALUE_V1`、`ECQ-STD-GB29446-001`、标准阈值、ROUND policy 全部未修改。本次是**有意的 Excel ingress Contract 收紧**，不是 Numeric Contract 改变。

## 3. Characterization — 修改前现状（before evidence）

修改前用真实服务与真实 Definition 实测得到：

| # | 结论 | 实测证据 |
|---|---|---|
| 1 | generic template 可 create / validate / commit | `validate valid=True`；`commit()` 返回 request（standard/product/inputs 正确） |
| 2 | XLSX numeric float 被 generic importer 拒绝 | `_decimal_from_cell(560.25)` → `None` + "已将其物化为二进制浮点" |
| 3 | XLSX numeric integer **绕过** float-only 检查并被接受 | `_decimal_from_cell(560)` → `Decimal('560')`，无 issue |
| 4 | formula 识别：`data_only=True` 不可靠；`data_only=False` 可识别 | `data_only=True` 时 `=500+60` 读成 `value=None, data_type='n'`；`data_only=False` 时 `value='=500+60', data_type='f'` |
| 5 | `commit(import_id)` **不重新核对** source SHA | 校验后改写文件（SHA `40325a94…` → `f8a17fe5…`），`commit()` 仍接受并返回**旧值 5.0** |
| 6 | `validated → commit()` 变成 `committed`，批次**无法重新提交** | 第二次 `commit()` → `ValueError: 只有验证通过的导入批次可以提交` |
| 7 | `validate()` **本身不调用 Engine** | 打桩 `EvaluationEngine.evaluate`，调用次数 `0`；`evaluations` 行数 `0`。**这是既有正确行为，本次只补回归保护，不报告为"修复"** |
| 8 | `tools/qzc_n01_a_excel_ingress_probe.py` 固化 `float → str → InputValue 成功` 的旧行为 | probe 内 `adapter_value == str(numeric_cell)` 为正向断言，并 import 私有 `_excel_value` |
| 附加 | 非有限值可穿透 ingress（`Decimal('NaN')` 被接受） | `_decimal_from_cell('NaN')` → `Decimal('NaN')`，无 issue |

## 4. 实现

### 4.1 RS03-A — Excel Profile 参数化

- 新增不可变 `WorkbookProfile`（`profile_id` / `template_version` / `sheet_names` / `headers` / `kind` / `requires_meta_sheet`）。
- `GENERIC_PROFILE`（`ecq.generic.excel.v1`）保留原 sheet 名、表头与全部既有行为；`IMPORT_SHEETS` / `IMPORT_HEADERS` / `TEMPLATE_VERSION` 继续作为兼容常量保留。
- `GB29446_PROFILE`（`ecq.gb29446.excel.v1`）：`填写说明` / `评价数据` / `_meta`。
- Profile 由 `_detect_profile` 按**结构**（sheet 名）判定，而非按 metadata，因此 `_meta` 损坏时能报出具体 metadata 错误而不是"未知模板"。
- **未为其他 46 项标准创建专用 Profile。** `create_template(path, standard_definition)` 对未提供专用模板的标准给出明确错误，而不是静默降级。

### 4.2 GB29446 正式模板

- 三张表：`填写说明` / `评价数据` / `_meta`（`_meta` 设为 `hidden`）。
- `评价数据` 只给普通用户 9 个输入字段：企业名称 / 评价日期 / 核算周期 / 自定义周期 / 煤种 / 选煤工艺 / E_d / m / 备注。
- **不显示**：`standard_id` / `product_id` / `input_mode` / `rule_revision` / 内部 input key / `k` / `e_d` / 等级 / numeric profile / calculator ID。由 `test_data_sheet_exposes_inputs_only_never_results` 与 `test_template_user_sheet_has_no_internal_identifiers` 双向守护。
- 下拉：核算周期（全年 / 1月…12月 / 自定义）、煤种、全部已声明工艺。正式 Importer 再校验煤种 + 工艺合法性。
- **模板内无任何业务公式**：无 k 公式、无 e_d 公式、无 grade IF、无 VLOOKUP、无 ROUND、无 threshold。
- 隐藏仅作为易用性处理；Importer 严格校验 metadata，**不把隐藏当安全措施**。

### 4.3 `_meta` Contract

| 字段 | 值 |
|---|---|
| `adapter_id` | `ecq.gb29446.excel.v1` |
| `template_version` | `1.0` |
| `standard_id` | `gb-29446-2019` |
| `standard_version` | 当前正式 `StandardDefinition.version` |
| `rule_revision` | 当前正式 `StandardDefinition.rule_revision` |

`ApplicationFacade.create_template(path, standard_id=None)` 先解析正式 Definition，再把 Definition 传给 `TemplatePort`。`WorkbookTemplateService` **不查 Repository**，`infrastructure` 也**没有注入 Facade**。

### 4.4 TemplatePort 签名

```python
def create_template(self, path: Path, standard_definition: StandardDefinition | None = None) -> Path: ...
```

`bootstrap.py`：**未修改**。Facade 解析 Definition 后传入，composition root 无需调整。

### 4.5 修订兼容 Gate

- Excel 正式评价固定 `selection_mode = CURRENT`，不支持 FUTURE preview。
- Importer 先从 workbook 取得 `evaluation_date`，再用**现有正式解析语义**（`standards.get_for_evaluation(standard_id, evaluation_date, CURRENT)`）确定本次评价真正会采用的 Definition。
- **未在 Excel Adapter 内自行实现 `max(rule_revision)` 等第二套选择规则。**
- 模板 metadata 与解析结果比较；不一致则拒绝并提示"该模板对应的标准/规则修订已不是当前本次评价适用版本，请重新生成模板后填写。"**不静默用新规则计算旧模板。**

### 4.6 通用模板不回归（RS03 P0 Gate）

- `GENERIC_PROFILE` 的 sheet 名、表头、`standard_id`/`product_id`/`input_mode` 机制、generic validate 与 `commit_workbook` 全部保留。
- `tests/test_excel.py` 未重写，6 个既有用例全部继续通过。
- `_meta` **未**塞进 generic sheet list。
- 新增回归：generic create → fill → validate → commit → `EvaluationRequest`（`test_generic_template_regression`）。

### 4.7 RS03-B — XLSX Decimal Ingress Contract

新的 GB29446 权威数值入口 `_lexical_decimal_from_cell` 的契约：

| 输入 | 结果 |
|---|---|
| text `"560"` / `"560.25"` / `"1e3"` | **接受**（有限十进制 lexical） |
| XLSX numeric `int 560` | **拒绝** |
| XLSX numeric `float 560.25` | **拒绝** |
| Excel 公式（无缓存值 / 有缓存值） | **拒绝** |
| `NaN` / `sNaN` / `Infinity` / `-Infinity` / `inf` / `-inf` | **拒绝** |
| `"1,000"` / `"560 kWh"` / 空 / `bool` | **拒绝** |

- **拒绝 numeric integer 的依据不是"整数不精确"**，分类为 `LOCAL DEFECT — ingress contract inconsistency`，目的是建立唯一、稳定、可审计的 decimal lexical text ingress。
- **未新增** max exponent、max digits 或业务最大值；文本 `"1e3"` 继续允许。
- 类型判定基于 `cell.data_type` / workbook cell semantics，**不再只写 `isinstance(value, float)`** 作为 authoritative Gate。
已实测 `"5.0000004"` 的 lexical 值经 Excel 路径完整保留（未经 `float → str` 往返）。

generic Profile 的 `_decimal_from_cell` 保持"拒绝 float、接受整数"的既有语义（`能源明细` / `产量与分摊` 的默认值与"其他 46 项标准"依赖它），并在 docstring 中明确记录该有意差异；同时补上非有限值拒绝。

### 4.8 公式可靠拒绝

`validate()` 改用 `load_workbook(path, data_only=False)`，因此 `cell.data_type == "f"` 可被可靠识别。所有 GB29446 authoritative input cell 先查公式视图，是公式即拒绝，**不因 `data_only=True` 存在缓存值而接受**。

测试覆盖两种情况：
- A 无缓存公式：`workbook["评价数据"]["B8"] = "=500+60"`；
- B 有缓存值的公式：直接改写 sheet XML 为 `<f>500+60</f><v>560</v>`，并断言 `data_only=False` 下 `data_type == 'f'`、`data_only=True` 下读回 `560`，然后断言仍被拒绝。

### 4.9 结构校验

- GB29446 Profile 使用自己的 expected sheets / headers（含 `_meta`）；GENERIC 保留自己的严格结构。
- 真实构造并测试：rename sheet、missing sheet、extra sheet、**真正 append 的额外列**、changed header、changed `_meta`。
- "额外列"测试真的把 `max_column + 1` 列写入表头值并断言 `max_column` 增加，不是只改 A1 名称。
- 结构校验阶段使用非 read-only workbook，以换取 `data_type` 与 `max_column` 的可靠性。

### 4.10 RS03-C — 周期 codec 抽离

- 新增 `src/uebench/application/gb29446.py`（98 行），为纯 Application 模块。
- `encode_period_notes` / `decode_period_notes` / `GB29446_PERIOD_OPTIONS` / 用户字段口径全部集中于此。
- GUI（`main_window._encode_gb29446_notes` / `_decode_gb29446_notes`）与 Excel Adapter **统一调用同一 codec**。
- **BEHAVIOR-PRESERVING REFACTOR**，`notes` 语义未变，特别保留：
  - 历史 `"核算周期：1月～12月"` → `全年`；
  - 首行缺失 / 无法识别 → `("全年", "", notes)`；
  - 非 `自定义` 时不消费 `自定义周期：` 行；
  - RS01 / RS02 已保存历史 notes 的全部解码行为。
- RS02 lifecycle Gate 全绿（见 §6）。

### 4.11 架构 Boundary 加固

`tests/test_architecture_boundaries.py` 从"只看 `tree.body` 顶层 import"改为 **AST `ast.walk` 全文件遍历**，并按 `if TYPE_CHECKING:` 守卫区分 runtime 与 type-only import：

1. `domain` 不得依赖 PySide6 / sqlalchemy / openpyxl / application / infrastructure / ui / bootstrap；
2. `application` 不得依赖 PySide6 / sqlalchemy / openpyxl / infrastructure / ui / bootstrap；
3. `ui` **即使 type-only 也不得** import `uebench.infrastructure`；runtime 不得 import `uebench.bootstrap`（`AppContext` 为 `TYPE_CHECKING` 引用，属允许的类型依赖）；
4. `infrastructure` 不得 import `uebench.ui` / `uebench.bootstrap`；
5. 新增 `application/gb29446.py` 自动纳入 Application Boundary，并单独断言其不依赖 Qt / Excel / SQLAlchemy / infrastructure / ui。

函数内 deferred import 同样被 `ast.walk` 捕获，**不能再用 deferred import 绕过**。

### 4.12 RS03-D — Source SHA 提交保护

- `validate` 继续记录 `source_file`（仅作 locator）与 `source_sha256`（内容 identity）。
- 正式评价前 `prepare(import_id)`：文件不存在 / 不可读 → 拒绝并要求重新选择并重新校验；存在则重算 SHA256，不等 → 拒绝 `"文件在校验后已发生变化，请重新校验。"`
- **路径变化本身不被当作内容变化**；真正的判定依据始终是 SHA。
- 路径改变后无法通过旧 locator 自动找到新文件，因此明确拒绝并要求重新选择，不做猜测性搜索。

### 4.13 修复 committed 卡死（LOCAL DEFECT）

新的正式路径：

```text
validated
→ evaluate_workbook(import_id)
→ SHA recheck
→ EvaluationService.evaluate(request)
→ 成功后 status = evaluated
```

- **只有正式评价成功才标 `evaluated`**；失败时批次保持 `validated`，用户可重试。
- **不再先标 `committed`。**
- 旧 generic `commit_workbook()` 保留以兼容其他标准；**未迁移历史 ImportBatch**。

### 4.14 单一正式 Application Use Case

`ApplicationFacade.evaluate_workbook(import_id)`：

- 向 `WorkbookImportPort.prepare()` 请求 validated draft + source integrity 校验；
- 取得 Canonical `EvaluationRequest`；
- 调用既有 `EvaluationService.evaluate(request)`；
- 成功后 `mark_evaluated(import_id, evaluation_id)`；
- 写 `WORKBOOK_EVALUATION` 审计；
- 返回 `EvaluationResult`。

**硬规则遵守**：`WorkbookImportService` 未直接调用 `EvaluationEngine`，未自行实现 grade；正式 Calculator caller 仍是 Application / `EvaluationService`。

### 4.15 Port 设计

`WorkbookImportPort` 新增 `prepare(import_id)` 与 `mark_evaluated(import_id, evaluation_id)`；`commit(import_id)` 保留为 legacy。`TemplatePort.create_template` 增加 `standard_definition` 参数。`ImportReportPort` 增加 `profile_id`。UI 仍只依赖 Application，**不依赖任何 infrastructure class**。

### 4.16 Audit

`WORKBOOK_EVALUATION` 的 details 至少包含 `import_id` / `evaluation_id` / `source_sha256` / `profile_id`。

- **未给 `evaluations` 新增 `import_id` 列**；
- **无 migration**；
- 测试验证：一个正式 Excel Record 能反查对应 Audit 事件，且 `PRAGMA table_info(evaluations)` 中不存在 `import_id`。

### 4.17 校验结果 UI

GB29446 校验通过后，普通页面显示识别摘要（标准 / 企业 / 评价日期 / 核算周期 / 煤种 / 工艺 / E_d / m），按钮改为 **"确认导入并评价"**，不再只显示"校验通过，可提交计算"。模板入口新增 **"保存 GB29446 专用模板"**。

### 4.18 Excel Adapter 不做计算

- `k` / `e_d` / grade **全部由 Domain / Engine 产生**；Excel Adapter 不计算。
- 煤种 → product 从正式 `StandardDefinition.products` / `selection_values` 解析；**Excel 模块内没有"炼焦煤 → internal product_id"式硬编码真值表**。
- 工艺 choices 与煤种 + 工艺合法组合均从当前 Definition 取得。

### 4.19 一个 workbook = 一次评价

不做批量企业、100 行批量计算、文件夹批处理或多 workbook 合并。

### 4.20 明确未做

- 不重设计 Export workbook（Export 仍从保存 Record 读取，不重新计算）；
- 不处理 RS02 deferred（corrupted/unparsable 历史行隔离、历史列表 result-json 性能优化）；
- 不为其余 46 项标准创建专用模板，但 generic infrastructure 未被破坏。

## 5. 允许 / 禁止修改范围核对

| 预期允许 | 实际 |
|---|---|
| `src/uebench/infrastructure/excel.py` | 已修改 |
| `src/uebench/application/ports.py` | 已修改 |
| `src/uebench/application/facade.py` | 已修改 |
| `src/uebench/application/gb29446.py` | 新增 |
| `src/uebench/ui/main_window.py` | 已修改 |
| `tests/test_excel.py` | **未修改**（无需修改，既有用例继续通过） |
| `tests/test_gb29446_excel_adapter.py` | 新增 |
| `tests/test_architecture_boundaries.py` | 已修改（按要求加固） |
| `tools/qzc_n01_a_excel_ingress_probe.py` | 已修改 |
| `.github/workflows/qzc-n01-a.yml` | **未修改**（probe 仍以同一命令被 CI 执行，无需改 workflow） |
| `TASK_STATE.md` / `HANDOFF.md` / `参考标准开发路线.md` | 已修改（RS03 达标后才更新） |
| `bootstrap.py` | **未修改**（Facade 解析 Definition 后传入 TemplatePort，composition root 无需调整） |

| 原则上禁止 | 实际 |
|---|---|
| `src/uebench/domain/engine.py` / `numeric.py` | **未修改** |
| `EvaluationRequest` / `EvaluationResult` / `IndicatorResult` / `StandardDefinition` schema | **未修改** |
| GB29446 Definition | **未修改** |
| `database.py` schema / `migrations/` | **未修改** |
| 标准阈值 / Numeric Profile / ROUND policy | **未修改** |
| `platform-lock.json` / `PLATFORM_BASELINE.md` / Qingzhou-contracts | **未修改** |
| `scripts/` / `packaging/` / `tools/publish_confirmed_rules.py` | **未修改** |

未重建 EXE / installer / 正式标准包；未发布；未开始 RS04。

## 6. 测试结果

必需 Gate（全部通过）：

```text
tests/test_excel.py
tests/test_gb29446.py
tests/test_gb29446_reference_slice.py
tests/test_gb29446_record_lifecycle.py
tests/test_gb29446_excel_adapter.py
tests/test_ui.py
tests/test_architecture_boundaries.py
tests/pilots/numeric/test_qzc_n01_a.py
tests/conformance/numeric/test_ecquota_numeric_v1.py
tests/test_document_hygiene.py
tools/qzc_n01_a_excel_ingress_probe.py
```

literal full suite（本地，带既有 dist 资产）：

```text
505 passed, 4 xfailed, 1 warning in 377.97s (0:06:17)
```

- 4 个 xfail 为 `tests/test_gb29446.py` 中既有的 legacy strict XFAIL（N01-A 有意数值行为变更证据），**保留不动**；
- 1 个 warning 为 `test_backup_rejects_duplicate_members` 的重复 ZIP 成员预期警告；
- 上述本地结果**无 failed、无 error**，但请注意下面的 CI 事实。

### CI 与旧 portable ZIP（证据更正）

独立验收指出本报告原先把这一项描述为"base 与 head 均通过、因此没有历史发布资产失败需要登记"，**该描述不成立**，现更正：

| 环境 | 结果 | 原因 |
|---|---|---|
| 本地工作区 | `test_portable_release_does_not_bundle_incompatible_poppler_icu` **通过** | 运行前本地已存在 `dist/release/UEBench-0.1.0-win-x64.zip`（该文件被 Git 忽略，不属于仓库内容） |
| CI（干净 checkout） | 旧 portable ZIP 缺失，`tests/test_frozen_release.py` 相关检查**失败** | CI 从不包含 `dist/`，因此上面那条"通过"只反映本地恰好存在旧构建产物 |

因此：

- 本地 `505 passed` **不足以证明 CI 的 literal suite 全绿**；两个 workflow 的 SUCCESS 也不能替代该证明，因为 `.github/workflows/qzc-n01-a.yml` 显式 `--deselect` 了该测试，并有一步专门断言它在 base **同样失败**；
- 该失败在 **actual PR base 与 head 上同时存在**，属于 **historical release asset failure**，按路线留至 **RS05** 处理；
- 本次**未创建、未替换、未重建**任何发布物。

### 关于 `test_portable_release_...` 的分类依据

独立验收已用最新 CI 日志证明：base 与 head 都因旧 portable ZIP 缺失而失败。这属于"历史发布资产缺失"，不是本次 RS03 引入的回归，也不由 RS03 修复。

新增 `tests/test_gb29446_excel_adapter.py` 覆盖任务书 §38 要求的 30 项，映射如下：

| # | 要求 | 测试 |
|---|---|---|
| 1 | GB29446 template generation | `test_gb29446_template_generation` |
| 2 | no internal IDs in user sheet | `test_template_user_sheet_has_no_internal_identifiers`、`test_data_sheet_exposes_inputs_only_never_results` |
| 3 | meta correct | `test_template_metadata_matches_definition`、`test_template_dropdowns_cover_declared_options` |
| 4 | stale revision reject | `test_stale_rule_revision_rejected`（另含 wrong standard_id / wrong template_version / missing meta field） |
| 5 | generic template regression | `test_generic_template_regression` |
| 6-8 | text integer / decimal / exponent accept | `test_text_decimal_lexical_accepted` |
| 9 | numeric int reject | `test_xlsx_numeric_cell_rejected[560-True]` |
| 10 | numeric float reject | `test_xlsx_numeric_cell_rejected[560.25-False]` |
| 11 | formula reject | `test_formula_cell_rejected_without_cache` |
| 12 | cached formula reject | `test_formula_cell_rejected_with_cached_value` |
| 13 | nonfinite reject | `test_non_finite_rejected`（另含 malformed / blank / bool） |
| 14 | coal/process mapping | `test_coal_process_mapped_from_definition`、`test_unknown_coal_type_rejected`、`test_coal_process_mismatch_rejected` |
| 15 | period / custom-period | `test_period_selection`、`test_custom_period_requires_text` |
| 16-17 | validation no Engine / no Record | `test_validation_does_not_run_engine_or_create_record` |
| 18-19 | changed / missing after validation reject | `test_changed_after_validation_rejected`、`test_missing_after_validation_rejected`（另含 `test_failed_evaluation_keeps_batch_retryable`） |
| 20 | GUI Request == Excel Request | `test_gui_request_equals_excel_request` |
| 21 | GUI Result == Excel Result projection | `test_gui_result_equals_excel_result_projection` |
| 22 | full-value boundary parity | `test_full_value_boundary_parity` |
| 23 | formal Excel evaluate creates Record | `test_formal_excel_evaluation_creates_record` |
| 24 | import/evaluation Audit link | `test_import_batch_links_to_evaluation_audit` |
| 25 | selection_mode CURRENT only | `test_excel_evaluation_is_current_only` |
| 26 | RS02 restart/view | `test_excel_record_lifecycle_survives_restart`（**真实独立子进程**） |
| 27 | Import → Export consistency | `test_import_to_export_consistency` |
| 28 | real extra-column rejection | `test_real_extra_column_rejected`（含**表头为空但有数据**的额外列；另含 rename / missing / extra sheet / changed header） |
| 29 | architecture boundary | `test_architecture_boundaries.py`（加固版，含**相对 import 解析**正向对照） |
| 30 | updated N01-A ingress probe | `tools/qzc_n01_a_excel_ingress_probe.py`（20 项检查全 PASS） |

返工新增的持续证据（见 §6.1）：

| 主题 | 测试 |
|---|---|
| 提交前重新核对模板修订 | `test_submit_rejects_template_when_rule_revision_changed` |
| legacy commit 不能绕过 Gate | `test_legacy_commit_does_not_bypass_revision_gate` |
| 注入失败后可重试 | `test_failed_evaluation_keeps_batch_retryable` |
| prepare 不推进状态 | `test_prepare_keeps_batch_retryable` |
| 真实 GUI 控件请求等价 | `test_real_gui_form_request_equals_excel_request` |
| 相对 import 解析 | `test_relative_import_resolution_catches_evasion`、`test_prefix_helper_covers_intermediate_packages` |

## 6.1 独立验收后的返工（本 PR 第三个提交）

独立验收判定 **FAIL — REWORK REQUIRED**，并给出三项必须返工的问题与三处证据强度不足。全部已修复：

### P1-a 正式提交可绕过修订 Gate —— 已修复

**问题**：metadata 检查只发生在初次校验；正式提交只重查文件 SHA，随后 `EvaluationService` 重新解析 current rule。实测"r2 模板校验成功 → 安装 current r3 → `evaluate_workbook` 仍保存 r3 Record"，模拟阈值变化后等级由 2级 变成 1级。

**修复**：`WorkbookImportService.prepare()` 现在执行**两项独立检查**，二者都通过才继续：

1. source integrity（文件存在且 SHA-256 未变）；
2. **适用规则身份**：用与校验时**同一个** `_resolve_gb29446_standard()` 重新解析模板，重新执行 metadata ↔ 解析结果比较；并把校验时记录的 `rule_revision` 与当前解析结果比较。

任一不符即拒绝并提示"该模板对应的标准/规则修订已不是当前本次评价适用版本，请重新生成模板后填写。"，批次**保持 `validated` 可重试**，且**不写入任何正式记录**。

Adapter 仍然**没有**第二套标准选择规则——它复用的就是正式 resolver。

同时 `ImportReport` 新增 `standard_version` / `rule_revision`，把校验时的解析身份落库，使"定义被等价替换"也能被检出。

**持续证据**：`test_submit_rejects_template_when_rule_revision_changed`（真实安装 r3 + 修改阈值，断言拒绝、批次仍 `validated`、`evaluations` 行数为 0）、`test_legacy_commit_does_not_bypass_revision_gate`（legacy `commit_workbook` 也不能绕过）。

### P1-b 真实额外列可通过结构校验 —— 已修复

**问题**：`评价数据!D1` 空、`D2="额外数据"`、`max_column=4` 时返回 `valid=True, issues=[]`；原实现只检查额外列的**表头**。

**修复**：新增 `_first_non_empty_row(sheet, column)`，对超出声明宽度的**每一列**扫描**全部行**（含第 1 行），只要存在非空内容即报"模板不允许增加自定义列"并指向具体单元格。纯格式扩宽（整列无内容）仍然兼容。

**持续证据**：`test_real_extra_column_rejected` 扩展为同时覆盖"有表头的额外列"与"表头为空但有数据的额外列"，并断言 `max_column` 确实增加。

### P2 Boundary Gate 漏检相对 lazy import —— 已修复

**问题**：`from ..infrastructure.excel import WorkbookImportService` 被记录为 `infrastructure.excel`，无法匹配 `uebench.infrastructure`；`from .. import infrastructure` 更被忽略。

**修复**：`_ImportCollector` 现在携带被检模块的完整点分名（由文件相对 `src/` 的路径推导，`__init__.py` 归并到包名），并据此解析 `node.level`：

- `from ..infrastructure.excel import X` → `uebench.infrastructure.excel` + `...WorkbookImportService`
- `from .. import infrastructure` → `uebench.infrastructure`

同时为 `import a.b` 记录所有点分前缀，使前缀规则与真实 import 语义一致。

**持续证据**：`test_relative_import_resolution_catches_evasion` 把三种写法（绝对 deferred、相对 deferred、相对包 deferred）写进临时模块并用真实 collector 断言全部被解析为 `uebench.infrastructure...`；`test_prefix_helper_covers_intermediate_packages` 守护前缀展开。

### 证据强度不足三处 —— 已补为持续可执行测试

| 原弱点 | 现在 |
|---|---|
| "重启"案例实际是同进程重建 context | `test_excel_record_lifecycle_survives_restart` 改为**真实独立 Python subprocess**（`sys.executable -B`）打开同一数据目录，通过 stdout JSON 回传恢复结果，并断言 `engine_calls == 0` |
| "失败可重试"案例没有注入 EvaluationService 失败 | `test_failed_evaluation_keeps_batch_retryable` 向**真实的** `EvaluationService.evaluate` 注入一次失败，断言批次保持 `validated`、重试成功后才变 `evaluated` |
| GUI Request 等价案例使用手工构造的 Request | `test_real_gui_form_request_equals_excel_request` 改为驱动**真实 `MainWindow` 控件**（标准 / 煤种 / 工艺 / 企业 / 周期 / 自定义周期 / E_d / m / 备注）后调用 `_collect_gb29446_request()`，与 Excel 规范请求逐字段比较（`evaluation_date` 因取当天而固定后比较完整 dump） |

保留原有的手工构造对照用例，作为独立于 Qt 的回归保护。



## 7. GUI / Excel 等价证据

代表案例：企业 `宁夏测试企业`、评价日期 `2026-06-01`、周期 `自定义 / 2026年6月`、煤种 `炼焦煤`、工艺 `重介`、`E_d="560"`、`m="100"`、备注 `同一内容`。

- **Request 相等**：`excel_request == gui_request`（Pydantic 全量相等），并逐项断言 `evaluation_date` / `standard_id` / `product_id` / `selection_mode` / `input_mode` / `inputs` / `organization_name` / `notes`。不是只比较最终等级。
- **真实 GUI 控件路径**：`test_real_gui_form_request_equals_excel_request` 驱动真实 `MainWindow` 表单控件后取得请求，与 Excel 规范请求比较完整 dump（`evaluation_date` 固定后比较）。
- **Result 投影相等**：比较 `standard_id` / `standard_version` / `rule_revision` / `product_id` / `actual_value` / `grade` / `display_values` / `corrected_thresholds` / `source_references` / numeric contract & profile / calculator version & behavior。`evaluation_id` 与 `evaluated_at` 允许不同（两条正式 Record）。
- **full-value 边界**：lexical `"5.0000004"` 经 Excel 与 GUI 两条路径均得 `grade = LEVEL_2`，`actual_value = Decimal('5.0000004')`，**未发生 ROUND6**，Excel display value 未回流正式比较。完整 `T−δ / T / T+δ` 继续由既有 Numeric Gate 承担。

## 8. RS02 生命周期继承

Excel 生成正式 Record 后：`get_evaluation` 可读；`test_excel_record_lifecycle_survives_restart` 通过**真实独立 Python subprocess** 打开同一数据目录恢复 Request / Result / Rule Snapshot，并断言只读查看**未运行 Engine**（`engine_calls == 0`）。周期 codec 搬迁后，RS02 历史记录中的全年 / 月度 / 自定义显示行为未改变，`tests/test_gb29446_record_lifecycle.py` 全绿。

## 9. 剩余风险与 Deferred

- `D-ECQ-006` 中央 lossless XLSX numeric-cell 公共方案**仍 OPEN**；本仓只收紧自身入口，未声称公共方案冻结；
- generic Profile 与 GB29446 Profile 的数值入口严格度**有意不同**（generic 接受整数以保护其他 46 项标准与既有模板默认值）；如后续要统一，需独立任务并评估对既有 generic 模板与测试的影响；
- 路径变更后无法自动重新定位文件（按设计拒绝并要求重新选择）；
- RS02 deferred 两项未处理，留待 RS04 前治理；
- `data/catalog.json` 的 `gb-29435-2025.lifecycle_status` 不一致仍只登记未修。

## 10. 结论

GB29446 Business Capability = `COMPLETE`；GB29446 Product Lifecycle = `COMPLETE`；**GB29446 Excel Adapter = `COMPLETE`**。

Reference Standard Product Closure = **`PARTIAL`**（尚欠 RS04–RS05）。

下一阶段：**RS04 — GB29446 Product Golden Gate**（`NOT STARTED`）。本任务不合并、不开始 RS04。
