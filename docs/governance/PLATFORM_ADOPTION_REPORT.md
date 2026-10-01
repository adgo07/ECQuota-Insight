# PLATFORM_ADOPTION_REPORT

## Current status — 2026-10-01

Central locked baseline:

`Qingzhou-contracts@ee5feb0cc34dbd99790500fadd0c4c932e202a20`

Current project adoption status:

| Public capability | ECQuota status |
|---|---|
| Architecture 2.1 | **FROZEN / adopted** |
| Numeric Contract v1 | **FROZEN / FULLY ADOPTED** |
| Numeric Profiles v1 | **FROZEN / adopted** |
| Numeric Conformance Vector v1 | **FROZEN / adopted and executable** |
| Unit Contract | **DRAFT / not formally adopted** |
| Module / Capability Contract | **DRAFT / not implemented** |
| Workspace / Attempt / Record / Result | **DRAFT / partial local capability only** |
| qzpack | **DRAFT / not implemented** |

The former QZC-A01 conclusion `Governance Adoption PASS / Numeric Conformance BLOCKED` is now **historical**. The Numeric blocker was resolved by N01-A evidence followed by the current Numeric Contract v1 Full Adoption task.

Current authoritative Numeric rules and evidence are documented in:

- `PLATFORM_BASELINE.md`
- `platform-lock.json`
- `docs/统一判定规范.md`
- `docs/governance/NUMERIC_V1_ADOPTION_REPORT.md`
- `tests/conformance/numeric/`

## Numeric blocker closure

The former blocker was:

`D-ECQ-001-global-round6-vs-frozen-full-value`

It is now **CLOSED**.

The public Engine no longer applies an unjustified default ROUND6 to grade/compliance comparisons. Default formal comparison is Decimal full-value exact; explicit business rounding requires Rule/source authority.

Project Profile:

`ECQUOTA_DECIMAL_FULL_VALUE_V1`

New results can trace Numeric Contract/Profile/calculator/rule/behavior semantics, and authoritative evaluation is isolated from caller ambient Decimal context.

The project also proved that numeric XLSX cells can lose exact decimal boundary information through openpyxl/Python float. Therefore authoritative float-materialized XLSX numeric cells are now rejected; the central lossless workbook-interchange design remains OPEN.

## Remaining public-contract gaps

The following remain intentionally outside the Numeric v1 adoption scope:

1. Module / Capability Manifest;
2. full Workspace / Attempt / Record / Result public envelope;
3. qzpack;
4. Unit Contract v1;
5. central common lossless XLSX numeric-cell interchange scheme.

These remaining gaps must not be interpreted as Numeric Contract v1 non-conformance.

---

# Historical QZC-A01 record — 2026-09-28

Task: `QZC-A01 — 接入 Qingzhou-contracts 公共治理`

At that time ECQuota locked the bootstrap baseline `0cd74d783fa23add6dc881b408a8c8ba8503f8e8`. Architecture V2.1 was FROZEN while Numeric / Unit / Module / Record / qzpack were still DRAFT. QZC-A01 intentionally changed governance files only and did not modify production Numeric behavior.

Its formal conclusion was:

> **Governance Adoption PASS / Numeric Conformance BLOCKED**

The blocker was real: the project-wide historic rule rounded both sides of formal numeric boundaries to six decimal places with `ROUND_HALF_UP`, while the architecture direction required full-value comparison and prohibited unsupported implicit rounding.

QZC-A01 deliberately did **not** resolve that conflict. It registered the deviation and required a later independent Numeric task.

Subsequent governance/evidence chain:

1. QZC-N01-A migrated GB 29446—2019 from unsupported ROUND6 to full-value exact Decimal semantics and independently validated the breaking boundaries.
2. Cross-project QZC-N01 evidence was synthesized and Numeric Contract v1 was frozen centrally.
3. The current ECQuota Numeric Contract v1 Full Adoption removed the remaining public Engine default ROUND6, established the project Numeric Profile and Frozen v1 Conformance, added minimum traceability, proved ambient independence and hardened authoritative Excel ingress.

Therefore the historical QZC-A01 `Numeric Conformance BLOCKED` conclusion must no longer be used as the current project status.
