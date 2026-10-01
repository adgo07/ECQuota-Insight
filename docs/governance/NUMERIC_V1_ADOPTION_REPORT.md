# ECQuota — Numeric Contract v1 Full Adoption Report

Status: **FULL NUMERIC V1 ADOPTION — execution complete, pending independent PR review/merge**  
Date: 2026-10-01  
Business repository: `adgo07/ECQuota-Insight`  
Central Contract repository: `adgo07/Qingzhou-contracts`  
Central Frozen baseline: `ee5feb0cc34dbd99790500fadd0c4c932e202a20`

> QZC-N01 已结束。本任务不是新 Pilot，也没有修改中央 Contract。本报告记录 ECQuota 对已经冻结的 Numeric Contract v1 的正式 Adoption。

## 1. Baseline

- default branch: `main`
- execution base: `031d0bb3406918d841984b3a535e172a8190b876`
- execution branch: `adopt/numeric-contract-v1-full`
- code/conformance closure tested head: `36444e0020d07fc6631885bd5ffe764025045600`
- central Frozen SHA: `ee5feb0cc34dbd99790500fadd0c4c932e202a20`
- central repository modified: **NO**
- historical records automatically recalculated: **NO**

### platform-lock before

```text
commit_sha = 0cd74d783fa23add6dc881b408a8c8ba8503f8e8
Numeric Contract = draft-v1 / DRAFT
D-ECQ-001 = OPEN
```

### platform-lock after

```text
commit_sha = ee5feb0cc34dbd99790500fadd0c4c932e202a20
Numeric Contract = v1 / FROZEN
Numeric Profile = ECQUOTA_DECIMAL_FULL_VALUE_V1
Numeric Conformance Vector = v1 / FROZEN
D-ECQ-001 = CLOSED
```

Unit / Module / Record / qzpack remain **DRAFT**. No release/tag was invented.

## 2. ROUND6 Audit

| Location | Before | Classification | Authority | After |
|---|---|---|---|---|
| `EvaluationEngine._grade()` | actual + threshold both `ROUND(...,6)` / `ROUND_HALF_UP` for non-GB29446 paths | legacy implicit rounding | none identified | direct Decimal full-value exact comparison |
| compliance comparison | actual + limit both ROUND6 | legacy implicit rounding | none identified | direct Decimal full-value comparison |
| GB 29446 grade | N01-A already used full-value special path | accepted migration behavior | GB 29446 source + Numeric v1 | preserved, now under common full-value default |
| `Expression.round_places` | generic HALF_UP capability, source metadata not structurally required | potential explicit business rounding | only valid when Rule/source authorizes | retained only with required stage/mode/purpose/source metadata |
| UI/report formatting | presentation rounding | display rounding | presentation policy | retained, cannot feed formal comparison |
| Decimal arithmetic context | ambient Python Decimal context | working numeric context | implementation behavior | declared project Profile p28/HALF_EVEN and isolated with `localcontext` |

Production scan of all current `data/definitions/*.json` found:

```text
published round_places declarations = 0
```

Therefore no current published standard needed an explicit-rounding exception to preserve a standard-authorized rule.

### Direct answer

> **ECQuota authoritative public Engine no longer contains an unjustified global ROUND6 formal-comparison mechanism.**

The old `_round_threshold_value()` / global six-place grade/compliance path was removed rather than renamed or hidden behind another helper.

## 3. Numeric Profile

Project Profile:

`ECQUOTA_DECIMAL_FULL_VALUE_V1`

Declared semantics:

```text
numeric_contract_version = v1
representation           = Decimal
working_precision        = 28
working_rounding_mode    = ROUND_HALF_EVEN
comparison_policy        = full-value exact
explicit_rounding_policy = Rule/source declared only
transcendental_policy    = not_applicable
tolerance_policy         = none by default; no global epsilon
display_policy           = presentation only
```

The p28/HALF_EVEN working context reflects ECQuota's pre-Adoption Python Decimal working behavior; this task did not invent p40/p50 or a platform-wide rounding default.

`EvaluationService` explicitly creates the production `EvaluationEngine` with this Profile. `EvaluationEngine.evaluate()` executes authoritative work inside the Profile-owned Decimal `localcontext`.

## 4. Profile consistency and ambient independence

Frozen v1 Conformance verifies:

```text
requested/declaration Profile
= ECQUOTA_DECIMAL_FULL_VALUE_V1
= effective result numeric_profile_id
```

Ambient independence is tested by deliberately changing the caller/global Decimal context to a conflicting low precision and `ROUND_UP`; the same authoritative GB 29446 calculation still executes with the declared p28/HALF_EVEN Profile and yields the Profile-governed result.

No helper-local historical Numeric Profile fallback remains in the public grade/compliance path.

## 5. Numeric traceability

New formal `EvaluationResult` can identify:

- `numeric_contract_version`;
- `numeric_profile_id`;
- `calculator_version`;
- `rule_revision`;
- `numeric_behavior_version`.

Current calculator marker:

`ecquota-evaluation-engine-v1`

Generic full-value behavior marker:

`ecquota-full-value-exact-v1`

GB 29446 migration/audit marker remains:

`ecquota-gb29446-full-value-v2`

The new fields are optional on deserialization so historical saved Result JSON is not silently rewritten or made unreadable. Historical Records are not automatically recalculated.

## 6. Frozen Numeric Conformance v1

Project assets:

- `tests/conformance/numeric/conformance_vector_v1.schema.json`
- `tests/conformance/numeric/ecquota_numeric_v1_vectors.json`
- `tests/conformance/numeric/test_ecquota_numeric_v1.py`

Vectors implement the Frozen v1 Common Core and are validated against the pinned central Frozen JSON Schema model.

Actually executed coverage includes:

1. Decimal parse / normalization;
2. Python float rejection;
3. public grade legacy ROUND6 migration;
4. public compliance legacy ROUND6 migration;
5. GB 29446 `T−δ / T / T+δ`;
6. all six required GB 29446 breaking cases;
7. display separation;
8. Profile declaration / propagation;
9. ambient independence;
10. explicit Rule rounding authority metadata;
11. XLSX binary-float exact-boundary loss and ingress rejection.

Actual result on GitHub Actions run `36820423867`:

```text
Frozen Numeric v1 Conformance: 20 passed
```

Vectors were executed; they were not merely generated as JSON.

## 7. Breaking changes

### 7.1 Public grade comparison

Synthetic public-Engine migration evidence:

```text
actual    = 10.0000004
threshold = 10

legacy ROUND6 -> LEVEL_1
Numeric v1    -> LEVEL_2
```

This demonstrates that removal of ROUND6 is a real business-semantic change, not a documentation-only change.

### 7.2 Public compliance comparison

```text
actual = 20.0000004
limit  = 20

legacy ROUND6 -> 符合
Numeric v1    -> 不符合
```

### 7.3 GB 29446 retained breaking behavior

| Exact value | Legacy | Corrected full-value |
|---|---|---|
| `5.0000004` | 1级 | 2级 |
| `7.0000004` | 2级 | 3级 |
| `8.5000004` | 3级 | 未达标 |
| `2.0000004` | 1级 | 2级 |
| `3.0000004` | 2级 | 3级 |
| `4.5000004` | 3级 | 未达标 |

### 7.4 Existing published-standard regression observation

The complete repository regression suite produced no new standard-specific failure after the common ROUND6 default was removed. Therefore this task found no existing published standard test that required restoring ROUND6 or adding a new explicit rounding Rule.

This is regression evidence, not a claim that every source PDF was manually re-reviewed. Per task scope, source review is required only if a concrete regression indicates an explicit-rounding exception may exist.

## 8. Excel / openpyxl finding and correction

The previous path was:

```text
XLSX numeric cell
→ openpyxl Python float
→ str
→ Decimal
→ authoritative result
```

A real test patches worksheet XML with exact decimal:

```text
5.0000000000000001
```

openpyxl materializes it as Python float:

```text
5.0
```

For the GB 29446 5.0 boundary:

```text
exact Decimal 5.0000000000000001 -> 2级
materialized 5.0                 -> 1级
```

Therefore the OPEN ingress issue can change a formal business result and could not be left as an unchecked authoritative path.

Minimal project fix:

- authoritative XLSX cells read as Python `float` are rejected;
- template authoritative numeric input columns are formatted as text;
- users enter decimal lexical text;
- `float -> str -> Decimal` no longer silently becomes business authority.

The **central common lossless XLSX numeric-cell interchange scheme remains OPEN**. ECQuota does not claim to have frozen a cross-platform Excel schema. The remaining deviation is governance/interchange scope, not an active silent-float authoritative path.

## 9. Tests actually run

Primary successful adoption run:

- workflow: `Numeric v1 Full Adoption`
- run id: `36820423867`
- tested head: `36444e0020d07fc6631885bd5ffe764025045600`
- runner: Windows Server 2025
- Python: 3.13.15
- conclusion: **success**

Actual checks:

| Check | Result |
|---|---:|
| compile/static import | PASS |
| no legacy public ROUND6 production path | PASS |
| published Rule rounding audit | PASS, `0` declarations |
| Frozen Numeric v1 Conformance | **20 passed** |
| N01-A + GB 29446 migration evidence | PASS + **4 strict legacy XFAIL** |
| Engine + Excel | **24 passed** |
| GB 29446 UI | **20 passed** |
| literal full suite | only 2 known asset failures + 4 legacy XFAIL |
| full suite excluding exactly the two proven base asset failures | PASS |
| each excluded failure re-run on untouched `main@031d0bb...` | FAIL on base as expected |

Current suite scale after the new conformance tests:

```text
345 passed
4 strict legacy XFAIL
2 pre-existing asset failures in literal full-suite execution
```

The two pre-existing failures remain:

1. `test_unified_development_library_index_is_complete`;
2. `test_portable_release_does_not_bundle_incompatible_poppler_icu`.

Neither failure was hidden or fixed opportunistically; both were independently reproduced on the untouched execution base.

## 10. Remaining deviations / OPEN items

Still OPEN and explicitly outside Numeric v1 Full Adoption scope:

- `D-ECQ-002` — Module/Capability Manifest not implemented;
- `D-ECQ-003` — Workspace/Attempt/Record/Result public envelope partial;
- `D-ECQ-004` — qzpack not implemented;
- `D-ECQ-005` — Unit Contract still DRAFT / not formally adopted;
- `D-ECQ-006` — common lossless XLSX numeric-cell interchange scheme still OPEN; project authoritative floats are rejected.

Closed:

- `D-ECQ-001-global-round6-vs-frozen-full-value`.

## 11. Scope control

This task did **not**:

- modify Qingzhou-contracts;
- restart QZC-N01;
- manually redevelop every energy-quota standard;
- refactor UI architecture;
- migrate database schema;
- implement Unit/Quantity Contract;
- implement qzpack;
- implement Workspace;
- recalculate historical Records.

## 12. Final Adoption Conclusion

Required Full Adoption gates:

- public Engine no unjustified default ROUND6: **PASS**;
- project Numeric Profile implemented and consumed: **PASS**;
- traceability meets Numeric v1 minimum semantics: **PASS**;
- Profile consistency: **PASS**;
- ambient independence: **PASS**;
- Frozen v1 schema validation + actual vectors execution: **PASS**;
- GB 29446 N01-A corrected semantics preserved: **PASS**;
- Excel silent binary-float authoritative path eliminated: **PASS**;
- relevant regressions: **PASS**;

> # **FULL NUMERIC V1 ADOPTION**

This conclusion means ECQuota's adopted authoritative Numeric scope conforms to the frozen Numeric Contract v1 semantics described above. It does **not** mean Unit, Module, Record, qzpack or other DRAFT Contracts have been frozen/adopted.

PR: `#4` — `https://github.com/adgo07/ECQuota-Insight/pull/4`; execution task must not self-merge it.
