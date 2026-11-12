"""GB 21342—2025 式（3）的独立未发布核心；不形成等级或正式记录。"""
from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import (
    Context, Decimal, DecimalException, InvalidOperation, DivisionByZero,
    Overflow, Underflow, Clamped, ROUND_HALF_EVEN, localcontext,
)
from enum import StrEnum

from .models import parse_decimal
from .numeric import ECQUOTA_DECIMAL_FULL_VALUE_V1, NumericProfile

CALCULATOR_ID = "gb21342-energy-balance"
CALCULATOR_VERSION = "gb21342-core-unpublished-v1"
RULE_REVISION = "gb21342-formula3-unpublished-v1"
NUMERIC_BEHAVIOR_VERSION = "gb21342-formula3-full-value-v1"
SOURCE_SHA256 = "00fcc51c02c6d73d39bcab3103227fca2ee93841abce45d1576edaeba25595a0"
SOURCE_LOCATION = "GB 21342—2025 §6.1.1、§6.2式（3）；印刷4/PDF8"
PARTIAL_ISSUE = "ECQ-STD-GB21342-002"


class ExternalServicesStatus(StrEnum):
    INCLUDED_OR_NOT_EXTERNAL = "included_or_not_external"
    BOTH_EXTERNAL_EXCLUDED = "both_external_excluded"
    PARTIAL_OR_UNKNOWN = "partial_or_unknown"


class CokeCalculationError(ValueError):
    """输入或计算不能形成有效的单位能耗。"""


LABELS = {
    "raw_coal_energy_kgce": "原料煤携带有效能量",
    "processing_energy_kgce": "加工耗能",
    "coke_energy_kgce": "焦炭产品携带能量",
    "chemical_products_energy_kgce": "化工产品携带能量",
    "recovered_heat_energy_kgce": "回收有效能量",
    "dry_coke_output_t": "干全焦产量",
}


def _declared_context(profile=ECQUOTA_DECIMAL_FULL_VALUE_V1):
    return Context(
        prec=profile.working_precision, rounding=ROUND_HALF_EVEN,
        Emin=-999999, Emax=999999, capitals=1, clamp=0, flags=[],
        traps=[InvalidOperation, DivisionByZero, Overflow, Underflow, Clamped],
    )


@dataclass(frozen=True, slots=True)
class CokeEnergyInput:
    raw_coal_energy_kgce: Decimal | str | int
    processing_energy_kgce: Decimal | str | int
    coke_energy_kgce: Decimal | str | int
    chemical_products_energy_kgce: Decimal | str | int
    recovered_heat_energy_kgce: Decimal | str | int
    dry_coke_output_t: Decimal | str | int
    external_services_status: ExternalServicesStatus | str

    def __post_init__(self):
        for key, label in LABELS.items():
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, (Decimal, str, int)):
                raise CokeCalculationError(f"{label}须使用十进制文本、整数或Decimal，不能使用浮点数或其他类型")
            try:
                with localcontext(_declared_context()):
                    number = parse_decimal(value, field_name=label)
            except (TypeError, ValueError) as exc:
                raise CokeCalculationError(str(exc)) from exc
            object.__setattr__(self, key, number)
        if self.dry_coke_output_t <= 0:
            raise CokeCalculationError("干全焦产量必须大于0 t")
        try:
            status = ExternalServicesStatus(self.external_services_status)
        except (TypeError, ValueError) as exc:
            raise CokeCalculationError("请明确煤气净化及废水处理的外属、计入情况；不明确时使用部分或未知状态") from exc
        object.__setattr__(self, "external_services_status", status)


@dataclass(frozen=True, slots=True)
class CokeTraceStep:
    sequence: int
    label: str
    expression: str
    value: Decimal | str | None
    unit: str | None


@dataclass(frozen=True, slots=True)
class CokeEnergyResult:
    inputs: CokeEnergyInput
    net_energy_kgce: Decimal
    actual_energy_kgce_per_t: Decimal
    adjustment_kgce_per_t: Decimal | None
    evaluation_energy_kgce_per_t: Decimal | None
    adjustment_status: str
    warnings: tuple[str, ...]
    calculation_trace: tuple[CokeTraceStep, ...]
    numeric_profile: NumericProfile
    numeric_contract_version: str
    numeric_profile_id: str
    calculator_id: str = CALCULATOR_ID
    calculator_version: str = CALCULATOR_VERSION
    rule_revision: str = RULE_REVISION
    numeric_behavior_version: str = NUMERIC_BEHAVIOR_VERSION
    source_sha256: str = SOURCE_SHA256
    source_location: str = SOURCE_LOCATION


def calculate_energy(
    inputs: CokeEnergyInput,
    *,
    profile: NumericProfile = ECQUOTA_DECIMAL_FULL_VALUE_V1,
) -> CokeEnergyResult:
    """计算已折标五分量；部分外属保留actual，调整及评价值未定。

    仅支持现行项目Profile。输入固定kgce和t，不自动猜测tce或其他单位。
    有限负分量按算术保留并警示，是软件入口策略，不是标准许可声明。
    """
    if not isinstance(inputs, CokeEnergyInput):
        raise CokeCalculationError("请提供焦炭五分量及干全焦产量输入")
    if not isinstance(profile, NumericProfile) or profile != ECQUOTA_DECIMAL_FULL_VALUE_V1:
        raise CokeCalculationError("本核心仅支持已声明的项目数值配置ECQUOTA_DECIMAL_FULL_VALUE_V1")
    # 重新构造验证，防止绕过常规构造的未正规化数据进入权威计算。
    inputs = CokeEnergyInput(**{field.name: getattr(inputs, field.name) for field in fields(inputs)})
    trace = []
    warnings = []

    def step(label, expression, value, unit=None):
        trace.append(CokeTraceStep(len(trace) + 1, label, expression, value, unit))

    for key, label in LABELS.items():
        value = getattr(inputs, key)
        step(label, key, value, "t" if key == "dry_coke_output_t" else "kgce")
        if key != "dry_coke_output_t" and value < 0:
            warnings.append(f"{label}为负数，请核查统计口径及计量更正；本次保留原值计算。")
    try:
        # 显式声明全部Context配置，连DefaultContext也不能改变本入口结果。
        # 精度/工作舍入仍是项目Profile；指数范围是本入口版本化工作范围。
        declared_context = _declared_context(profile)
        with localcontext(declared_context) as context:
            context.clear_flags()
            # 零的lexical exponent不应制造范围错误；trace仍保留入口Decimal。
            raw, processing, coke, chemicals, heat = (
                Decimal(0) if getattr(inputs, key).is_zero() else getattr(inputs, key)
                for key in tuple(LABELS)[:5]
            )
            net = raw + processing - coke - chemicals - heat
            step("净能量", "e_yl+e_jg-e_jt-e_jf-e_yr", net, "kgce")
            actual = Decimal(0) if net.is_zero() else net / inputs.dry_coke_output_t
            step("实际单位能耗", "net/p_JT", actual, "kgce/t")
            if inputs.external_services_status is ExternalServicesStatus.PARTIAL_OR_UNKNOWN:
                adjustment = evaluation = None
                status = "UNDETERMINED"
                step("外属调整未定", PARTIAL_ISSUE, None, "kgce/t")
                warnings.append("煤气净化或废水处理仅部分外属、部分计入或情况不明，26调整尚未确定；保留实际单位能耗。")
            else:
                adjustment = Decimal(26) if inputs.external_services_status is ExternalServicesStatus.BOTH_EXTERNAL_EXCLUDED else Decimal(0)
                evaluation = actual + adjustment
                status = "DETERMINED"
                step("外属调整", inputs.external_services_status.value, adjustment, "kgce/t")
                step("调整后评价能耗", "actual+adjustment", evaluation, "kgce/t")
            if context.flags[Underflow] or context.flags[Clamped]:
                raise CokeCalculationError("计算超出项目数值配置的有效范围，请核查输入数量级。")
    except DecimalException as exc:
        raise CokeCalculationError("计算超出项目数值配置的有效范围，请核查输入数量级。") from exc
    if actual < 0:
        warnings.append("实际单位能耗为负数，请核查能量统计边界和回收抵扣；本次保留原值计算。")
    return CokeEnergyResult(
        inputs, net, actual, adjustment, evaluation, status, tuple(warnings), tuple(trace),
        profile, profile.numeric_contract_version, profile.numeric_profile_id,
    )
