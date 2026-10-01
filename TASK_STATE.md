# TASK_STATE

更新时间：2026-10-01

## 当前任务

`ECQuota — Numeric Contract v1 Full Adoption`

工作分支：

```text
adopt/numeric-contract-v1-full
```

execution base：

```text
main@031d0bb3406918d841984b3a535e172a8190b876
```

中央 Frozen baseline：

```text
Qingzhou-contracts@ee5feb0cc34dbd99790500fadd0c4c932e202a20
Numeric Contract v1: FROZEN
Numeric Profiles v1: FROZEN
Numeric Conformance Vector v1: FROZEN
```

QZC-N01 已结束；本任务是正式 Adoption，不是新 Pilot。

## 已完成的生产迁移

- 公共 Engine 默认 grade comparison 已从 legacy ROUND6 改为 Decimal full-value exact comparison；
- compliance comparison 已取消默认 ROUND6；
- `_round_threshold_value()` / 全局 ROUND6 正式比较路径已移除；
- 现有 published definitions 中 `round_places` 使用数为 0；
- Rule 层仍保留 explicit rounding 能力，但必须提供 stage / mode / purpose / source；
- 建立项目 Profile `ECQUOTA_DECIMAL_FULL_VALUE_V1`：p28 / ROUND_HALF_EVEN working context / full-value exact / no global epsilon；
- authoritative evaluation 使用 profile-owned `localcontext`，隔离 caller ambient Decimal context；
- `EvaluationResult` 增加向后兼容的 Numeric traceability：contract/profile/calculator/behavior + 原 rule revision；
- GB 29446 原 `ecquota-gb29446-full-value-v2` migration marker 保留；
- authoritative XLSX binary-float numeric cell 现直接拒绝，模板正式数值列改用文本十进制输入。

## Frozen v1 Conformance

新增：

- `tests/conformance/numeric/conformance_vector_v1.schema.json`
- `tests/conformance/numeric/ecquota_numeric_v1_vectors.json`
- `tests/conformance/numeric/test_ecquota_numeric_v1.py`
- `.github/workflows/numeric-v1-adoption.yml`

覆盖：

- Decimal parse / normalization；
- float rejection；
- public grade/compliance ROUND6 migration；
- GB 29446 T−δ/T/T+δ 与六个 breaking cases；
- display separation；
- Profile declaration/propagation；
- ambient independence；
- explicit Rule rounding authority metadata；
- XLSX binary-float 跨业务边界实证与 ingress guard。

## 已执行测试证据

GitHub Actions `Numeric v1 Full Adoption` 已实际验证：

- Frozen v1 Conformance：20 passed；
- 原 N01-A + GB 29446：通过，保留 4 个 strict legacy XFAIL；
- Engine + Excel：24 passed；
- GB 29446 UI：20 passed；
- 字面 full suite：仅 2 个既有资产失败；
- 排除上述 2 个已证明的 base failure 后：完整回归通过；
- 两个资产失败均已在 untouched `main@031d0bb...` 重新执行并复现。

当前测试规模：345 passed + 4 legacy XFAIL；另有 2 个与本任务无关且在 execution base 已存在的 asset failures。

## 已知 OPEN

- `D-ECQ-002` Module/Capability Manifest；
- `D-ECQ-003` Workspace/Attempt/Record/Result 外围；
- `D-ECQ-004` qzpack；
- `D-ECQ-005` Unit Contract 仍 DRAFT；
- `D-ECQ-006` 中央统一 lossless XLSX numeric-cell scheme 仍 OPEN；项目当前通过拒绝 authoritative float materialization 保证 Numeric v1 authoritative path 不静默失真。

`D-ECQ-001-global-round6-vs-frozen-full-value` 已关闭。

## 当前结论

在正式 PR 最终 head 重新通过 CI 的前提下，目标结论为：

```text
FULL NUMERIC V1 ADOPTION
```

PR：`#4` — `https://github.com/adgo07/ECQuota-Insight/pull/4`。

不要自行合并 PR。
