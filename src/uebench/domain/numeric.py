from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, ROUND_HALF_EVEN


NUMERIC_CONTRACT_VERSION = "v1"
ECQUOTA_CALCULATOR_VERSION = "ecquota-evaluation-engine-v1"
ECQUOTA_FULL_VALUE_BEHAVIOR_VERSION = "ecquota-full-value-exact-v1"
GB29446_NUMERIC_BEHAVIOR_VERSION = "ecquota-gb29446-full-value-v2"


@dataclass(frozen=True, slots=True)
class NumericProfile:
    """Concrete numeric configuration for one authoritative ECQuota scope."""

    numeric_profile_id: str
    numeric_contract_version: str
    representation: str
    working_precision: int
    rounding_mode: str
    comparison_policy: str
    explicit_rounding_policy: str
    transcendental_policy: str
    tolerance_policy: str
    display_policy: str

    def decimal_context(self) -> Context:
        if self.rounding_mode != "ROUND_HALF_EVEN":
            raise ValueError(f"Unsupported ECQuota working rounding mode: {self.rounding_mode}")
        return Context(prec=self.working_precision, rounding=ROUND_HALF_EVEN)


ECQUOTA_DECIMAL_FULL_VALUE_V1 = NumericProfile(
    numeric_profile_id="ECQUOTA_DECIMAL_FULL_VALUE_V1",
    numeric_contract_version=NUMERIC_CONTRACT_VERSION,
    representation="Decimal",
    working_precision=28,
    rounding_mode="ROUND_HALF_EVEN",
    comparison_policy="full-value exact",
    explicit_rounding_policy="rule/source declared only",
    transcendental_policy="not_applicable",
    tolerance_policy="none by default; no global epsilon",
    display_policy="presentation only; never feeds authoritative comparison",
)
