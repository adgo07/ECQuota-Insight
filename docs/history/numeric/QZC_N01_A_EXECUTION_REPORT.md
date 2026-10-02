# QZC-N01-A — ECQuota Exact Decimal / Rounding Pilot Execution Report

> **状态：`HISTORICAL-SUPERSEDED`**
>
> **用途：QZC-N01-A Pilot 历史审计证据。**
>
> **注意：不得作为当前 Numeric 正式规则依据。** 本文件记录的是 Pilot 当时的执行与验收证据；后续 **Numeric Contract v1 Full Adoption** 已完成正式迁移与验证。
>
> **当前权威：** `platform-lock.json`（locked SHA）、`docs/统一判定规范.md`、`docs/governance/NUMERIC_V1_ADOPTION_REPORT.md`。
>
> 本文件正文保持原样，不重写当时真实结论；文中的 `READY FOR INDEPENDENT ACCEPTANCE` 是 Pilot 当时的记录状态。

Status: **EXECUTION COMPLETE — READY FOR INDEPENDENT ACCEPTANCE**  
Independent Acceptance: **NOT PERFORMED**

## 1. Pilot identity and baselines

- Project: `adgo07/ECQuota-Insight`
- Module: `qz.energy_quota`
- Pilot: `QZC-N01-A`
- Representative standard: `GB 29446—2019 选煤电力消耗限额`
- Default branch: `main`
- Main baseline SHA at execution start and current PR base: `74b3deccfe74559cd08cc16a0705f1589ea6ecdc`
- Local Design commit: `738d5a9f5a432b10a05b87ae9b9f70ac612360d1`
- Execution branch: `exec/qzc-n01-a-exact-decimal`
- Tested execution head: `332a208cc76e7d0bc9f41a18398ae18919ed63ca`
- Execution PR: `#3`
- Central Contract read baseline: `adgo07/Qingzhou-contracts@47a268dcebdc43c582f451b2004c9e63b46502a3`
- Locked platform baseline remains: `0cd74d783fa23add6dc881b408a8c8ba8503f8e8`
- `platform-lock.json`: **not modified**
- Central Contract repository: **read only; not modified**

The execution task supplied a newer design decision than the original local design-only scope: historical Numeric behavior is not a compatibility constraint when it conflicts with the standard source, mathematical semantics, and the Numeric Contract principles. This execution therefore performs the GB 29446 production migration while leaving the central Contract repository untouched.

## 2. Static findings

### 2.1 GB 29446 standard basis

Repository source evidence identifies the standard PDF as `28.GB 29446-2019选煤电力消耗限额.pdf`, SHA-256:

`72011768d81cc35db8e53f6470fadc3b14140b61bd4f9ee3546a3e225e9cb15d`

Relevant standard locations used by the canonical rule:

- Table 1: coking-coal limits `5.0 / 7.0 / 8.5 kW·h/t`;
- Table 2: power-coal limits `2.0 / 3.0 / 4.5 kW·h/t`;
- 5.2 formula (1): `e_d = E_d × k / m`;
- Annex A Table A.1: process conversion factor `k`.

The source review found no clause requiring universal six-decimal rounding, `ROUND6`, `ROUND_HALF_UP`, fixed decimal places, or rounding of `e_d` before formal grade comparison. Therefore the former ROUND6 behavior has no identified GB 29446 source basis.

### 2.2 Authoritative numeric chain before N01-A

Before execution, `EvaluationEngine._grade()` applied `_round_threshold_value()` to both the calculated actual value and every grade threshold using:

```text
Decimal.quantize(0.000001, ROUND_HALF_UP)
```

Only then did the engine perform the formal `<=` / `>=` comparison. This was implementation behavior rather than a GB 29446 rule.

Condition/range evaluation already used direct Decimal comparison. `Expression.round_places` remains a separate capability for rule-declared explicit rounding, but GB 29446 does not use `round_places` in its formal grade chain.

### 2.3 Input ingress audit

- **GUI:** GB 29446 numeric text enters the Domain as lexical decimal text; no GUI float conversion was identified in the authoritative path.
- **Domain/Internal API:** authoritative numeric model inputs reject Python `float`.
- **JSON:** JSON numbers that deserialize as Python `float` are rejected by the authoritative input model; decimal transport should use strings.
- **CSV:** no dedicated authoritative CSV importer was found in this repository.
- **Excel/openpyxl:** a real probe confirms that a numeric XLSX cell is read by openpyxl as Python `float`, after which the current adapter performs `str(value)` before Decimal parsing. This is a remaining ingress issue; N01-A does not claim lossless lexical preservation for numeric XLSX cells.

### 2.4 Decimal calculation precision boundary

The formula evaluator uses Python `Decimal` throughout authoritative arithmetic. For division, it currently uses the active Python Decimal context; the CI runtime used the normal Python context rather than an N01-A-specific arbitrary quantize/ROUND6 step. Therefore:

- N01-A removes **business-decision ROUND6** from GB 29446 comparison;
- it does **not** claim infinite rational precision for non-terminating division;
- no new arbitrary fixed working precision was invented for this Pilot because the central Numeric Contract DRAFT explicitly leaves global precision open and GB 29446 does not declare a special precision rule.

This distinction must be retained in later cross-platform precision work.

## 3. Code actually changed

### 3.1 Production calculation / comparison

`src/uebench/domain/engine.py`

- Added numeric behavior identifiers:
  - `ecquota-legacy-round6-v1`
  - `ecquota-gb29446-full-value-v2`
- GB 29446 now calls `_grade(..., full_value=True)`.
- In the GB 29446 grade path, neither `actual` nor thresholds pass through `_round_threshold_value()`.
- Formal comparison uses the runtime Decimal calculation value directly against the Decimal threshold.
- Every attempted GB 29446 threshold comparison is recorded in the calculation trace with `numeric_behavior=ecquota-gb29446-full-value-v2`.
- The legacy ROUND6 helper remains for standards not yet source-audited; this Pilot does not legitimize or freeze that behavior for them.
- GB 29446 compliance remains outside the legacy compliance-rounding path.

### 3.2 Display separation

`src/uebench/ui/main_window.py`

- GB 29446 explanation text now shows the full-value comparison rather than ROUND6.
- UI display formatting remains presentation-only.
- A displayed `5.00` cannot feed back into a formal grade based on `5.0000004`.

### 3.3 Governance / documentation

`docs/统一判定规范.md`

- Universal ROUND6 is reclassified as legacy implementation behavior, not an automatic standard rule.
- implicit rounding, explicit business rounding, and display rounding are distinguished.
- GB 29446 breaking behavior is documented as intentional migration.

### 3.4 Test / conformance assets

- `tests/pilots/numeric/qzc_n01_a_vectors.json`
- `tests/pilots/numeric/test_qzc_n01_a.py`
- `tests/conftest.py`
- `tests/test_ui.py`
- `tools/qzc_n01_a_excel_ingress_probe.py`
- `.github/workflows/qzc-n01-a.yml`

The old ROUND6 tests were not silently deleted. Exactly four old assertions that encode the superseded GB 29446 ROUND6 behavior are retained as `strict=True` expected-failure legacy evidence. Corrected behavior is asserted separately by the executable N01-A vectors. Other GB 29446 tests continue to run normally.

## 4. Tests actually run

Authoritative GitHub Actions evidence:

- Run: `36686368149`
- Tested SHA: `332a208cc76e7d0bc9f41a18398ae18919ed63ca`
- Runner: Windows Server 2025 / `windows-2025-vs2026`
- Python: `3.13.15`
- pytest: `8.4.2`
- Overall workflow conclusion: **success**

| Command / check | Actual result |
|---|---|
| `python -m compileall -q src tests tools` | PASS |
| `python -m pytest tests/pilots/numeric/test_qzc_n01_a.py -vv -p no:cacheprovider` | **28 passed** |
| `python -m pytest tests/test_gb29446.py -q -ra -p no:cacheprovider` | **53 passed, 4 strict XFAIL legacy cases** |
| `python -m pytest tests/test_engine.py tests/test_excel.py -q -ra -p no:cacheprovider` | **24 passed** |
| `python -m pytest tests/test_ui.py -q -ra -p no:cacheprovider` | **20 passed** |
| `python tools/qzc_n01_a_excel_ingress_probe.py` | PASS; reproduced numeric XLSX `float -> str` ingress |
| Literal full suite | **325 passed, 2 failed, 4 XFAIL** |
| Full suite excluding exactly the two independently proven baseline asset failures | **325 passed, 4 XFAIL** |
| Re-run excluded development-library test on base `74b3dec...` | FAIL on base, as expected |
| Re-run excluded frozen-release artifact test on base `74b3dec...` | FAIL on base, as expected |

The literal full suite was intentionally still executed and its failure was not hidden. The two failures are:

1. `test_unified_development_library_index_is_complete` — existing development library manifest inconsistency;
2. `test_portable_release_does_not_bundle_incompatible_poppler_icu` — CI checkout has no `dist/release/UEBench-0.1.0-win-x64.zip`.

Both tests were then run against the untouched PR base SHA `74b3deccfe74559cd08cc16a0705f1589ea6ecdc` and failed there as well. All other tests passed on the execution head. N01-A did not modify either asset area to manufacture a green full-suite result.

## 5. Numerical cases actually executed

The N01-A Pilot suite executed all six threshold triplets with `δ = 0.0000004`:

### Coking coal

- `4.9999996 / 5.0 / 5.0000004`
- `6.9999996 / 7.0 / 7.0000004`
- `8.4999996 / 8.5 / 8.5000004`

### Power coal

- `1.9999996 / 2.0 / 2.0000004`
- `2.9999996 / 3.0 / 3.0000004`
- `4.4999996 / 4.5 / 4.5000004`

All 18 boundary vectors passed with the corrected full-value semantics.

Additional executed cases include:

- integer lexical Decimal;
- finite Decimal;
- trailing-zero Decimal (`5.0000` remains representationally preserved);
- zero and negative business-invalid inputs;
- Python float rejection;
- JSON-number/float rejection;
- detail-formula E2E;
- display-vs-grade separation;
- persisted numeric behavior trace.

The E2E detail case actually executed:

```text
E_d = 50.000004 kW·h
m   = 10 t
k   = 1.00

calculation value = 5.0000004 kW·h/t
formal comparison = 5.0000004 > 5.0, then 5.0000004 <= 7.0
formal grade      = 2级
display at 2 dp   = 5.00
```

The displayed `5.00` did not alter the grade.

## 6. Legacy vs corrected behavior

| Case | Legacy | New | Standard basis | Reason |
|---|---|---|---|---|
| `5.0000004` | 1级 | 2级 | GB 29446 Table 1: 1级≤5.0 / 2级≤7.0 | Exact value is greater than 5.0; legacy ROUND6 erased the excess |
| `7.0000004` | 2级 | 3级 | GB 29446 Table 1: 2级≤7.0 / 3级≤8.5 | Exact value is greater than 7.0 |
| `8.5000004` | 3级 | 未达标 | GB 29446 Table 1: 3级≤8.5 | Exact value exceeds the lowest qualifying boundary |
| `2.0000004` | 1级 | 2级 | GB 29446 Table 2: 1级≤2.0 / 2级≤3.0 | Exact value is greater than 2.0 |
| `3.0000004` | 2级 | 3级 | GB 29446 Table 2: 2级≤3.0 / 3级≤4.5 | Exact value is greater than 3.0 |
| `4.5000004` | 3级 | 未达标 | GB 29446 Table 2: 3级≤4.5 | Exact value exceeds the lowest qualifying boundary |

These are **intentional numeric behavior changes**, not regressions.

## 7. Rounding semantics actually demonstrated

### implicit rounding

GB 29446 formal grade comparison no longer performs implicit ROUND6 on the actual value or threshold.

### explicit business rounding

No GB 29446 source requirement for pre-grade rounding was identified, and no artificial explicit rounding rule was added.

### display rounding

UI/report formatting may round for presentation. The E2E test proves that presentation rounding does not feed back into grade comparison.

## 8. Conformance vectors actually executed

Vector location:

`tests/pilots/numeric/qzc_n01_a_vectors.json`

Schema candidate:

`qzc-n01-a-candidate-v0`

JSON vectors:

- 18 threshold vectors;
- 1 detail-formula E2E vector.

The executable Pilot test adds ingress, invalid-input, representation, display separation, and persistence checks for a total of **28 passing Pilot tests**.

The vectors demonstrate:

- Decimal authoritative representation;
- T−δ / T / T+δ at all six thresholds;
- legacy vs corrected results;
- no ROUND6 in formal comparison trace;
- display separation;
- saved-result traceability.

They are candidate business-project vectors only. N01-A does not freeze the platform Conformance Schema.

## 9. Numeric behavior / version traceability

New GB 29446 formal results identify their numeric semantics with:

`ecquota-gb29446-full-value-v2`

The marker is stored in grade-comparison calculation trace and survives save/read persistence; this was actually tested. Historical records are not recalculated.

This Pilot does not redesign Record architecture or add a database migration. The minimum requirement is met: a newly calculated result can identify that it used the new GB 29446 numeric behavior rather than the legacy ROUND6 behavior.

## 10. Remaining issues

1. **Excel/openpyxl float ingress — unresolved.** Numeric XLSX cells can traverse `binary float -> str -> Decimal`. The probe proves this route exists. A lossless workbook-ingress policy requires separate design rather than an ad-hoc N01-A patch.
2. **Other standards still use legacy ROUND6.** Deliberately out of N01-A scope. Each must be reviewed against its own source before migration.
3. **Decimal division precision is implementation precision, not infinite rational arithmetic.** The current Python implementation uses Decimal context semantics for non-terminating division. No platform-wide precision declaration is frozen by this Pilot.
4. **Two repository-wide asset tests fail on the untouched base.** Development-library manifest and absent frozen-release ZIP remain project housekeeping/release issues, not N01-A regressions.
5. **No platform-wide Numeric Contract freeze.** N01-A returns evidence only.

## 11. Candidate platform rules

Candidate only:

```ini
representation        = Decimal
binary_float          = forbidden in authoritative chain
implicit_rounding     = forbidden
business_comparison   = full-value
explicit_rounding     = only when Rule/standard explicitly declares it
display_rounding      = presentation-only
```

Additional candidate evidence:

- decimal values should cross authoritative serialized boundaries as strings rather than JSON binary-float numbers;
- precision/work-context policy should be declared separately from business rounding semantics;
- business-decision tolerance must not be inferred from display precision or numerical convenience.

## 12. Project-specific rules

- GB 29446 formal grade behavior is identified as `ecquota-gb29446-full-value-v2`.
- GB 29446 uses exact Decimal threshold operators on the runtime calculation value; no decision epsilon is used.
- Existing non-GB29446 standards remain on legacy behavior until independently source-audited.
- GB 29446 positive-value validation remains unchanged.
- GB 29446 enterprise/build status remains outside grade semantics.
- Excel workbook lexical preservation remains an ECQuota/import-boundary concern until a common ingress rule is agreed.

## 13. D-012 feedback

For GB 29446 formal grade boundaries, no decision tolerance or `is_close` is needed. For example:

```text
5.0000004 > 5.0
```

is a direct Decimal boundary fact in the tested runtime value domain.

N01-A supports the D-012 taxonomy that must distinguish:

- formal business decision tolerance;
- internal numerical-algorithm tolerance;
- test assertion tolerance;
- lookup/interpolation tolerance;
- standard-declared tolerance.

This Pilot provides evidence for D-012 but **does not close D-012 platform-wide**.

## 14. Central Return Template execution-stage feedback

- Static code audit completed: **YES**
- Tests actually executed: **YES**
- Numerical results actually recomputed: **YES**
- Boundary cases actually executed: **YES**
- Conformance vectors actually executed: **YES**
- Cross-language implementation actually executed: **NOT IN SCOPE**
- Contract baseline tag/SHA used: `contracts-v0.1.0` / `0cd74d783fa23add6dc881b408a8c8ba8503f8e8`
- `platform-lock.json` changed: **NO**
- Central Contract changed: **NO**
- Candidate platform rules produced: **YES, candidate only**
- Unit Contract change proposed: **No change proposed**
- D-001: no new transcendental evidence from this Pilot
- D-004: candidate vector structure produced; not sufficient alone to freeze common schema
- D-011: not applicable to this Pilot
- D-012: exact formal threshold comparison evidence produced; cross-pilot decision remains open

## 15. Explicit execution statement

- **Execution task:** COMPLETE
- **Static audit completed:** YES
- **Numerical results actually executed:** YES
- **Conformance vectors actually executed:** YES
- **Independent Acceptance:** NOT PERFORMED
- **Business project acceptance:** NOT SET BY EXECUTION TASK
- **This report freezes a platform-wide Numeric/Unit rule:** NO

Execution stops here. The next permitted phase is the separately requested Independent Acceptance against the latest PR head, actual diff, code, standard basis, vectors, and this report.
