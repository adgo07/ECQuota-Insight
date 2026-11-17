"""GB 21342—2025 独立未发布的能耗与判级预览；不形成正式记录。"""
from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import (
    Context, Decimal, DecimalException, InvalidOperation, DivisionByZero,
    Overflow, Underflow, Clamped, ROUND_HALF_EVEN, localcontext,
)
from enum import StrEnum

from .models import parse_decimal
from .models import Grade
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


ASSESSMENT_CALCULATOR_VERSION = "gb21342-assessment-unpublished-v1"
ASSESSMENT_RULE_REVISION = "gb21342-table1-table2-unpublished-v1"
# 原文表2节点，精确十进制文本；不从legacy JSON或Markdown运行时读取。
VOLATILE_TABLES = {
    "top_charging": tuple(zip(range(21, 29), ("-8.30", "-4.20", "0", "4.25", "8.55", "11.00", "14.08", "18.71"))),
    "stamp_charging": tuple(zip(range(25, 33), ("0", "3.20", "6.44", "11.40", "14.65", "17.93", "21.23", "24.50"))),
}


def _optional_number(value, label):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (Decimal, str, int)):
        raise CokeCalculationError(f"{label}须使用十进制文本、整数或Decimal")
    try:
        with localcontext(_declared_context()):
            return parse_decimal(value, field_name=label)
    except (TypeError, ValueError) as exc:
        raise CokeCalculationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class CokeAssessmentInput:
    energy: CokeEnergyInput
    oven_type: str | None = None
    heating_fuel: str | None = None
    dry_volatile_pct: Decimal | str | int | None = None
    total_moisture_pct: Decimal | str | int | None = None
    oven_age_years: Decimal | str | int | None = None
    quenching_method: str | None = None
    mixed_gas_ratio: Decimal | str | int | None = None
    conventional_oven: bool | None = None

    def __post_init__(self):
        if not isinstance(self.energy, CokeEnergyInput):
            raise CokeCalculationError("缺少焦炭五分量明细输入")
        choices = {
            "oven_type": ({"top_charging", "stamp_charging", None}, "焦炉类型"),
            "heating_fuel": ({"coke_oven_gas", "mixed_gas", "other", "unknown", None}, "加热燃料"),
            "quenching_method": ({"dry", "wet", "mixed", "unknown", None}, "熄焦方式"),
        }
        for key, (allowed, label) in choices.items():
            value = getattr(self, key)
            if value is not None and not isinstance(value, str) or value not in allowed:
                raise CokeCalculationError(f"{label}无效")
        if self.conventional_oven is not None and type(self.conventional_oven) is not bool:
            raise CokeCalculationError("常规焦炉适用事实须为是、否或未知")
        for key, label in (("dry_volatile_pct", "干基挥发分"), ("total_moisture_pct", "全水分"),
                           ("oven_age_years", "炉龄"), ("mixed_gas_ratio", "混合煤气使用时间比例")):
            value = _optional_number(getattr(self, key), label)
            if value is not None:
                if key in {"dry_volatile_pct", "total_moisture_pct"} and not 0 <= value <= 100:
                    raise CokeCalculationError(f"{label}须在0至100%之间")
                if key == "oven_age_years" and value < 0:
                    raise CokeCalculationError("炉龄不能为负数")
                if key == "mixed_gas_ratio" and not 0 <= value <= 1:
                    raise CokeCalculationError("混合煤气使用时间比例须在0至1之间")
            object.__setattr__(self, key, value)


@dataclass(frozen=True, slots=True)
class CokeLevelResult:
    grade: Grade
    base_threshold: Decimal | None
    corrections: tuple[tuple[str, Decimal | None], ...]
    threshold: Decimal | None
    matched: bool | None
    undetermined_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CokeAssessmentResult:
    inputs: CokeAssessmentInput
    energy: CokeEnergyResult
    levels: tuple[CokeLevelResult, ...]
    grade: Grade
    calculation_trace: tuple[CokeTraceStep, ...]
    warnings: tuple[str, ...]
    calculator_version: str = ASSESSMENT_CALCULATOR_VERSION
    rule_revision: str = ASSESSMENT_RULE_REVISION
    calculator_id: str = "gb21342-assessment"
    numeric_behavior_version: str = "gb21342-highest-grade-full-value-v1"
    source_sha256: str = SOURCE_SHA256
    source_location: str = "GB 21342—2025 §4表1、§5.3表2、§6.1.1及式（3）；PDF6—8"

    @property
    def numeric_profile_id(self):
        return self.energy.numeric_profile_id

    @property
    def numeric_contract_version(self):
        return self.energy.numeric_contract_version


def assess_coke(inputs: CokeAssessmentInput, *, profile=ECQUOTA_DECIMAL_FULL_VALUE_V1) -> CokeAssessmentResult:
    """两炉型修正及最高级别业务链；只读，不生成正式记录。"""
    if not isinstance(inputs, CokeAssessmentInput):
        raise CokeCalculationError("请提供焦炭评价输入")
    inputs = CokeAssessmentInput(**{field.name: getattr(inputs, field.name) for field in fields(inputs)})
    energy = calculate_energy(inputs.energy, profile=profile)
    trace = list(energy.calculation_trace)
    warnings = list(energy.warnings)

    def step(label, expression, value, unit="kgce/t"):
        trace.append(CokeTraceStep(len(trace)+1, label, expression, value, unit))

    for key, label, unit in (
        ("oven_type", "焦炉类型", None), ("heating_fuel", "加热燃料", None),
        ("mixed_gas_ratio", "混合煤气使用时间比例", None),
        ("dry_volatile_pct", "干基挥发分", "%"), ("total_moisture_pct", "全水分", "%"),
        ("oven_age_years", "炉龄", "年"), ("quenching_method", "熄焦方式", None),
        ("conventional_oven", "常规焦炉适用事实", None),
    ):
        value = getattr(inputs, key)
        step(label, key, str(value) if isinstance(value, bool) else value, unit)

    reasons = {}

    def unknown(key, message):
        reasons[key] = message
        issue = {"V": "ECQ-STD-GB21342-003", "Q": "ECQ-STD-GB21342-004"}.get(key)
        step("修正未定", f"{key}; {issue}" if issue else key, None)
        return None

    def compute(key, expression, calculation):
        try:
            with localcontext(_declared_context(profile)):
                value = calculation()
        except DecimalException:
            return unknown(key, "修正计算超出项目数值配置范围")
        step("修正量", expression, value)
        return value

    top = inputs.oven_type == "top_charging"
    if inputs.oven_type is None:
        fuel = volatile = moisture = None
        for key in ("F", "V", "M"):
            unknown(key, "缺少焦炉类型")
        bases = (None, None, None)
    else:
        bases = tuple(Decimal(value) for value in ((110, 110, 135) if top else (115, 115, 140)))
        if inputs.heating_fuel == "coke_oven_gas":
            fuel = Decimal(0)
            step("燃料修正", "F=0；焦炉煤气基准", fuel)
        elif inputs.heating_fuel == "mixed_gas" and inputs.mixed_gas_ratio is not None:
            fuel = compute("F", "F=(8或12)×混合煤气使用时间比例", lambda: Decimal(8 if top else 12)*inputs.mixed_gas_ratio)
        else:
            fuel = unknown("F", "缺少加热燃料或混合煤气使用时间比例，或燃料无表列修正规则")
        table = VOLATILE_TABLES[inputs.oven_type]
        x = inputs.dry_volatile_pct
        if x is None:
            volatile = unknown("V", "缺少干基挥发分")
        elif x < table[0][0] or x > table[-1][0]:
            volatile = unknown("V", "干基挥发分超出表列范围，未外推或夹取端点")
        else:
            node = next((Decimal(value) for point, value in table if x == point), None)
            if node is not None:
                volatile = node
                step("挥发分修正", "表2精确节点", volatile)
            else:
                (a, fa), (b, fb) = next((left, right) for left, right in zip(table, table[1:]) if left[0] < x < right[0])
                volatile = compute("V", f"相邻线性插值：{fa}+({x}-{a})×({fb}-{fa})/({b}-{a})",
                                   lambda: Decimal(fa)+(x-Decimal(a))*(Decimal(fb)-Decimal(fa))/Decimal(b-a))
        moisture = (unknown("M", "缺少全水分") if inputs.total_moisture_pct is None else
                    compute("M", "M=3.67(Mt−10)或3.71(Mt−10.5)",
                            lambda: Decimal("3.67" if top else "3.71")*(inputs.total_moisture_pct-Decimal("10" if top else "10.5"))))
    age = inputs.oven_age_years
    if age is None:
        age_correction = unknown("A", "缺少炉龄")
    else:
        age_correction = Decimal(0 if age <= 15 else "2.50" if age <= 25 else "5.50")
        step("炉龄修正", "≤15:0；(15,25]:2.50；>25:5.50", age_correction)
    if inputs.quenching_method in {"dry", "wet"}:
        quench = Decimal(0 if inputs.quenching_method == "dry" else "46.46")
        step("熄焦修正", "干熄焦0；湿熄焦46.46（仅3级）", quench)
    else:
        quench = unknown("Q", "熄焦方式缺失、未知或干湿并存，3级修正未定")
    applicable = inputs.conventional_oven
    if applicable is not True:
        warnings.append("不属于常规焦炉，标准不适用。" if applicable is False else "常规焦炉适用事实尚未确定。")
    levels = []
    for index, base in enumerate(bases, 1):
        corrections = [("F", fuel), ("V", volatile), ("M", moisture)]
        if index == 3:
            corrections.append(("Q", quench))
        if index != 2:
            corrections.append(("A", age_correction))
        missing = tuple(reasons[key] for key, value in corrections if value is None)
        threshold = None
        if base is not None and not missing:
            threshold = compute(f"L{index}", f"L{index}=基值+"+"+".join(key for key, _ in corrections),
                                lambda: sum((value for _, value in corrections), base))
            if threshold is None:
                missing += (reasons[f"L{index}"],)
        matched = None
        if energy.evaluation_energy_kgce_per_t is None:
            missing += ("外属调整未定，缺少可比较的评价能耗",)
        if applicable is not True:
            missing += (("不属于常规焦炉" if applicable is False else "常规焦炉适用事实未知"),)
        if threshold is not None and energy.evaluation_energy_kgce_per_t is not None and applicable is True:
            matched = energy.evaluation_energy_kgce_per_t <= threshold
        step(f"{index}级比较", f"评价能耗≤L{index}", "未定" if matched is None else str(matched), None)
        levels.append(CokeLevelResult(Grade(f"LEVEL_{index}"), base, tuple(corrections), threshold, matched, missing))
    if applicable is False:
        grade = Grade.NOT_APPLICABLE
    else:
        grade = Grade.INCOMPLETE
        # 高等级未知不能被低等级满足覆盖；已知高等级满足不要求补低等级。
        for level in levels:
            if level.matched is None:
                break
            if level.matched:
                grade = level.grade
                break
        else:
            grade = Grade.NOT_QUALIFIED
    step("最终级别", "最高满足级别", grade.value, None)
    return CokeAssessmentResult(inputs, energy, tuple(levels), grade, tuple(trace), tuple(warnings))
