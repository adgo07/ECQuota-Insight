from pathlib import Path

path = Path("HANDOFF.md")
text = path.read_text(encoding="utf-8")

marker = "# ECQuota Numeric Contract v1 Full Adoption（2026-10-01）"
if marker not in text:
    prefix = '''# ECQuota Numeric Contract v1 Full Adoption（2026-10-01）

- 当前中央锁定基线：`Qingzhou-contracts@ee5feb0cc34dbd99790500fadd0c4c932e202a20`。
- 当前 Numeric 状态：**Numeric Contract v1 / Numeric Profiles v1 / Numeric Conformance Vector v1 已正式采用**。
- 项目 Numeric Profile：`ECQUOTA_DECIMAL_FULL_VALUE_V1`（Decimal，working precision=28，working rounding=ROUND_HALF_EVEN，formal comparison=full-value exact，默认无 business epsilon）。
- 公共 Engine 的无依据默认 ROUND6 已取消：grade/compliance 均直接使用 Decimal full-value comparison；`D-ECQ-001` 已关闭。
- explicit business rounding 只能由标准原文或正式 Rule 授权，并必须声明 stage / precision-or-places / mode / purpose / source。
- authoritative evaluation 使用 Profile-owned Decimal context，禁止 caller ambient context 静默改变正式结果。
- 新正式结果至少可追踪 `numeric_contract_version`、`numeric_profile_id`、`calculator_version`、`rule_revision` 和必要的 `numeric_behavior_version`。
- Frozen v1 可执行 Conformance 位于 `tests/conformance/numeric/`；原 N01-A vectors 继续作为 migration evidence。
- Excel authoritative numeric cell 若被 openpyxl 物化为 Python `float`，现在直接拒绝；模板正式数值列使用文本十进制输入。中央统一 lossless XLSX scheme 仍 OPEN。
- 当前权威治理文件：`PLATFORM_BASELINE.md`、`platform-lock.json`、`docs/统一判定规范.md`、`docs/governance/NUMERIC_V1_ADOPTION_REPORT.md`。
- 本节优先于下方 2026-09-28 QZC-A01 / 更早历史记录中的 Numeric 状态。历史记录不要删除，但不得再把“全局 ROUND6”或“Numeric DRAFT/BLOCKED”解释成当前规则。

---

'''
    text = prefix + text

old = "> 新增必读规范：docs/统一判定规范.md。数值边界先ROUND(...,6)再比较；最低要求未满足统一输出未达标；企业属性填写与否均不得阻碍或改变指标等级。现有软件和GB29446 Excel整改为待修改，旧测试通过不代表符合新规范。"
new = "> 历史说明（已被 2026-10-01 Numeric v1 Adoption 取代）：旧版曾要求数值边界先 ROUND(...,6) 再比较；当前权威规则已改为默认 Decimal full-value exact comparison，只有标准/Rule 明确授权时才允许 explicit business rounding。最低要求未满足仍输出未达标；企业属性填写与否不得改变 GB 29446 指标等级。"
if old in text:
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("HANDOFF Numeric v1 current-status section refreshed")
