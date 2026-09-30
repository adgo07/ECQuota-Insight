# QZC-N01-A — ECQuota Exact Decimal / Rounding Pilot Execution Report

Status: **EXECUTION IN PROGRESS — Independent Acceptance not performed**

## 1. Pilot identity and baselines

- Project: `adgo07/ECQuota-Insight`
- Pilot: `QZC-N01-A`
- Representative standard: `GB 29446—2019 选煤电力消耗限额`
- Default branch: `main`
- Main baseline SHA at execution start: `74b3deccfe74559cd08cc16a0705f1589ea6ecdc`
- Local Design baseline SHA: `738d5a9f5a432b10a05b87ae9b9f70ac612360d1`
- Execution branch: `exec/qzc-n01-a-exact-decimal`
- Central Contract read baseline: `adgo07/Qingzhou-contracts@47a268dcebdc43c582f451b2004c9e63b46502a3`
- Locked platform baseline remains `0cd74d783fa23add6dc881b408a8c8ba8503f8e8`.
- `platform-lock.json`: **not modified**.
- Central Contract repository: **read only; not modified**.

## 2. Static findings

### 2.1 GB 29446 standard basis

Repository source evidence identifies the standard PDF as `28.GB 29446-2019选煤电力消耗限额.pdf`, SHA-256 `72011768d81cc35db8e53f6470fadc3b14140b61bd4f9ee3546a3e225e9cb15d`.

Relevant source locations used by the canonical rule:

- Table 1: coking-coal limits `5.0 / 7.0 / 8.5 kW·h/t`;
- Table 2: power-coal limits `2.0 / 3.0 / 4.5 kW·h/t`;
- 5.2 formula (1): `e_d = E_d × k / m`;
- Annex A Table A.1: process conversion factor `k`.

The design-stage source review found no clause requiring a universal six-decimal rounding, `ROUND6`, `ROUND_HALF_UP`, fixed decimal places, or rounding of `e_d` before formal grade comparison. Therefore the former global ROUND6 behavior has no identified GB 29446 standard basis.

### 2.2 Existing authoritative chain before N01-A

Before execution, `src/uebench/domain/engine.py::_grade()` applied `_round_threshold_value()` to both `actual` and every threshold using `Decimal.quantize(0.000001, ROUND_HALF_UP)` before formal comparison. This was an implementation behavior, not a GB 29446 source rule.

The condition/range evaluator already used full Decimal values, and `Expression.round_places` was explicit rule-declared rounding. GB 29446 canonical definitions do not use `round_places` in their formal grade chain.

### 2.3 Input ingress audit

- Domain/Internal API: `InputValue`, numeric line models, rule boundaries and `parse_decimal()` reject Python `float` in authoritative model inputs.
- JSON request parsing: a JSON number that becomes Python `float` is rejected by the `InputValue` pre-validator; canonical decimal transport should use strings.
- GUI: numeric user input reaches the domain as text/decimal lexical input; no separate GUI float conversion was identified in the GB 29446 authoritative path.
- CSV: no dedicated CSV authoritative importer was found in the repository.
- Excel/openpyxl: **remaining issue**. Numeric XLSX cells can be read by openpyxl as Python `float`; the current adapter then converts them with `str(value) -> Decimal`. This loses proof of the original lexical decimal representation and can bypass the domain's direct float rejection. A lossless correction requires an explicit workbook ingress policy (for example exact decimal text cells or a raw-cell representation strategy), so N01-A records it rather than silently claiming conformance.

## 3. Code actually changed

### Production behavior

`src/uebench/domain/engine.py`

- Added explicit numeric behavior identifiers:
  - `ecquota-legacy-round6-v1`
  - `ecquota-gb29446-full-value-v2`
- GB 29446 now invokes `_grade(..., full_value=True)`.
- In the GB 29446 formal grade path, neither actual value nor threshold is passed through `_round_threshold_value()`.
- Grade trace records every attempted threshold comparison using the full Decimal operands and stores `numeric_behavior=ecquota-gb29446-full-value-v2`.
- Legacy ROUND6 helper remains only for standards that have not yet been individually migrated; N01-A does not assert those standards are correct or freeze their semantics.
- Display calculations remain separate from grade comparison.

### Governance/documentation

`docs/统一判定规范.md`

- Reclassified universal ROUND6 as legacy implementation behavior rather than an automatic standard rule.
- Documented standard-explicit rounding vs implicit rounding vs display rounding.
- Recorded the GB 29446 migration and six intentional breaking cases.

### Test/conformance assets

- `tests/pilots/numeric/qzc_n01_a_vectors.json`
- `tests/pilots/numeric/test_qzc_n01_a.py`
- `tests/conftest.py`
- `.github/workflows/qzc-n01-a.yml`

The old ROUND6 tests were not deleted. Changed legacy expectations are retained as strict expected-failure evidence; corrected expectations are asserted by executable N01-A vectors.

## 4. Numerical cases actually executed

**Pending CI execution at this report revision.** This section must be replaced with actual run evidence before execution is closed.

## 5. Legacy vs corrected behavior

| Case | Legacy | New | Standard basis | Reason |
|---|---|---|---|---|
| `5.0000004` | 1级 | 2级 | GB 29446 Table 1, 1级≤5.0 / 2级≤7.0 | Exact value is greater than 5.0; legacy ROUND6 erased the excess |
| `7.0000004` | 2级 | 3级 | GB 29446 Table 1, 2级≤7.0 / 3级≤8.5 | Exact value is greater than 7.0 |
| `8.5000004` | 3级 | 未达标 | GB 29446 Table 1, 3级≤8.5 | Exact value exceeds the lowest qualifying boundary |
| `2.0000004` | 1级 | 2级 | GB 29446 Table 2, 1级≤2.0 / 2级≤3.0 | Exact value is greater than 2.0 |
| `3.0000004` | 2级 | 3级 | GB 29446 Table 2, 2级≤3.0 / 3级≤4.5 | Exact value is greater than 3.0 |
| `4.5000004` | 3级 | 未达标 | GB 29446 Table 2, 3级≤4.5 | Exact value exceeds the lowest qualifying boundary |

These differences are **intentional numeric behavior changes**, not regressions.

## 6. Conformance vectors actually executed

Vectors are committed and executable, covering:

- exact integer, finite decimal and trailing-zero lexical forms;
- business-invalid zero and negative GB 29446 values;
- Python float rejection;
- JSON-number rejection at authoritative domain ingress;
- `T-δ / T / T+δ` for all six GB 29446 grade thresholds;
- the six required legacy-vs-corrected breaking values;
- no implicit ROUND6 in calculation/grade comparison;
- display rounding after formal calculation without feedback into grade;
- detail-formula E2E: `E_d=50.000004`, `m=10`, `k=1.00` → exact `e_d=5.0000004` → corrected grade 2级 while two-decimal display is `5.00`;
- persistence of the numeric behavior trace in a saved result.

**Execution result pending CI.**

## 7. Tests actually run

**Pending CI.** Planned repository-real commands are encoded in `.github/workflows/qzc-n01-a.yml`:

1. `python -m compileall -q src tests`
2. `python -m pytest tests/pilots/numeric/test_qzc_n01_a.py -q -p no:cacheprovider`
3. `python -m pytest tests/test_gb29446.py -q -p no:cacheprovider`
4. `python -m pytest tests/test_engine.py tests/test_excel.py -q -p no:cacheprovider`
5. `python -m pytest -q -p no:cacheprovider --basetemp work/pytest-n01-a`

This report will not claim PASS until real execution evidence exists.

## 8. Remaining issues

1. **Excel/openpyxl float ingress** — unresolved in N01-A. Numeric XLSX cells can traverse `float -> str -> Decimal`; this needs a separately reviewed exact-decimal workbook ingress policy rather than pretending the lexical decimal was preserved.
2. **Other standards still on legacy ROUND6** — deliberately out of scope. They require source-by-source review; N01-A must not automatically remove or justify their ROUND6 behavior.
3. **No platform-wide Numeric Contract freeze** — this Pilot only returns ECQuota evidence/candidate rules.

## 9. Candidate platform rules

Candidate, not frozen:

```ini
representation        = Decimal
binary_float          = forbidden in authoritative chain
implicit_rounding     = forbidden
business_comparison   = full-value
standard_rounding     = only when standard/rule explicitly declares it
display_rounding      = presentation-only
```

Project evidence supports treating numeric text as canonical at system boundaries and keeping display precision separate from decision precision.

## 10. Project-specific rules

- GB 29446 uses `ecquota-gb29446-full-value-v2` in formal grade comparison.
- Existing non-GB29446 standards retain legacy behavior until independently source-audited.
- GB 29446 positive-value business validation for direct and detail numeric inputs remains unchanged.
- GB 29446 enterprise/build status remains outside grade semantics.

## 11. D-012 feedback

For GB 29446 formal grade boundaries, no decision tolerance or epsilon is required. Exact Decimal comparison is well-defined: e.g. `5.0000004 > 5.0`.

Any future internal numerical algorithm tolerance (iterative solver convergence, lookup interpolation, etc.) must remain distinct from formal decision tolerance. N01-A therefore provides evidence for D-012 but does **not** close D-012 platform-wide.

## 12. Central Return Template status

- Pilot identity/baselines: recorded.
- Static source basis: recorded.
- Actual code changes: recorded.
- Legacy/corrected table: recorded.
- Candidate common rules: recorded as candidate only.
- Project-specific rules: recorded.
- D-012 feedback: recorded.
- Actual test execution/evidence: **pending**.
- Independent Acceptance result: **NOT PERFORMED BY EXECUTION TASK**.

Final execution status remains open until the actual test section is filled from real runs.
