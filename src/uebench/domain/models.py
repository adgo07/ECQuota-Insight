from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Grade(StrEnum):
    LEVEL_1 = "LEVEL_1"
    LEVEL_2 = "LEVEL_2"
    LEVEL_3 = "LEVEL_3"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    INCOMPLETE = "INCOMPLETE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


GRADE_LABELS = {
    Grade.LEVEL_1: "1级",
    Grade.LEVEL_2: "2级",
    Grade.LEVEL_3: "3级",
    Grade.NOT_QUALIFIED: "未达标",
    Grade.INCOMPLETE: "不完整",
    Grade.NOT_APPLICABLE: "不适用",
}


class InputMode(StrEnum):
    DIRECT = "DIRECT"
    DETAIL = "DETAIL"


class ComparisonDirection(StrEnum):
    LTE = "lte"
    GTE = "gte"


class PublicationStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    PUBLISHED = "published"


class LifecycleStatus(StrEnum):
    ACTIVE = "active"
    FUTURE = "future"
    OBSOLETE = "obsolete"


class StandardSelectionMode(StrEnum):
    CURRENT = "current"
    HISTORICAL = "historical"
    FUTURE = "future"


class DataType(StrEnum):
    DECIMAL = "decimal"
    TEXT = "text"
    BOOLEAN = "boolean"


Scalar = Decimal | int | str | bool | None


def _reject_float(value: Any) -> Any:
    if isinstance(value, float):
        raise TypeError("浮点数不允许进入规则或评价模型，请使用字符串、整数或 Decimal")
    if isinstance(value, list):
        return [_reject_float(item) for item in value]
    if isinstance(value, dict):
        return {key: _reject_float(item) for key, item in value.items()}
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SourceReference(StrictModel):
    standard_number: str
    source_file: str
    source_sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    page: int = Field(ge=1)
    clause: str | None = None
    table: str | None = None
    note: str | None = None


class InputValue(StrictModel):
    value: Scalar
    unit: str | None = None
    source_note: str | None = None

    @field_validator("value", mode="before")
    @classmethod
    def reject_float(cls, value: Any) -> Any:
        return _reject_float(value)


class EnergyLine(StrictModel):
    line_id: str
    energy_name: str
    category_key: str | None = Field(default=None, pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]*$")
    direction: Literal["input", "output"] = "input"
    amount: Decimal
    unit: str
    standard_coal_coefficient: Decimal
    coefficient_unit: str
    allocation_ratio: Decimal = Decimal("1")
    source_note: str | None = None

    @field_validator("amount", "standard_coal_coefficient", "allocation_ratio", mode="before")
    @classmethod
    def parse_numbers(cls, value: Any) -> Decimal:
        if isinstance(value, float):
            raise TypeError("能源明细数值不允许使用浮点数")
        return value if isinstance(value, Decimal) else Decimal(str(value))

    @model_validator(mode="after")
    def validate_values(self) -> EnergyLine:
        if self.amount < 0:
            raise ValueError("能源实物量不能为负数，请使用 direction=output 表示输出能源")
        if self.standard_coal_coefficient < 0:
            raise ValueError("折标系数不能为负数")
        if self.allocation_ratio < 0 or self.allocation_ratio > 1:
            raise ValueError("能源分摊比例必须在 0 到 1 之间")
        return self


class ProductionLine(StrictModel):
    line_id: str
    product_name: str
    category_key: str | None = Field(default=None, pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]*$")
    quantity: Decimal
    unit: str
    conversion_factor: Decimal = Decimal("1")
    qualified: bool = True
    source_note: str | None = None

    @field_validator("quantity", "conversion_factor", mode="before")
    @classmethod
    def parse_numbers(cls, value: Any) -> Decimal:
        if isinstance(value, float):
            raise TypeError("产量数值不允许使用浮点数")
        return value if isinstance(value, Decimal) else Decimal(str(value))

    @model_validator(mode="after")
    def validate_values(self) -> ProductionLine:
        if self.quantity < 0:
            raise ValueError("产品产量不能为负数")
        if self.conversion_factor < 0:
            raise ValueError("产品折算系数不能为负数")
        return self


class InputDefinition(StrictModel):
    key: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]*$")
    label: str
    data_type: DataType = DataType.DECIMAL
    unit: str | None = None
    required: bool = True
    required_if: Condition | None = None
    modes: list[InputMode] = Field(default_factory=lambda: [InputMode.DIRECT, InputMode.DETAIL])
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    choices: list[str] = Field(default_factory=list)
    description: str | None = None

    @field_validator("minimum", "maximum", mode="before")
    @classmethod
    def parse_decimal(cls, value: Any) -> Any:
        if value is None or isinstance(value, Decimal):
            return value
        if isinstance(value, float):
            raise TypeError("边界值必须使用字符串或 Decimal")
        return Decimal(str(value))

    @model_validator(mode="after")
    def validate_range(self) -> InputDefinition:
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum 不能大于 maximum")
        return self


class SelectionLevel(StrictModel):
    """A rule-declared level in the product/process selection cascade.

    The options are intentionally derived from ``ProductDefinition``
    selection values instead of being duplicated here.  This keeps one
    authoritative product list while allowing a standard to declare two or
    more levels (for example, product category then specification/process).
    """

    key: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]*$")
    label: str
    required: bool = True


class Condition(StrictModel):
    op: Literal[
        "always",
        "eq",
        "ne",
        "lt",
        "lte",
        "gt",
        "gte",
        "in",
        "range",
        "all",
        "any",
        "not",
    ] = "always"
    field: str | None = None
    value: Scalar = None
    values: list[Scalar] = Field(default_factory=list)
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    include_minimum: bool = True
    include_maximum: bool = True
    args: list[Condition] = Field(default_factory=list)

    @field_validator("value", "values", mode="before")
    @classmethod
    def reject_float(cls, value: Any) -> Any:
        return _reject_float(value)

    @field_validator("minimum", "maximum", mode="before")
    @classmethod
    def parse_decimal(cls, value: Any) -> Any:
        if value is None or isinstance(value, Decimal):
            return value
        if isinstance(value, float):
            raise TypeError("区间边界必须使用字符串或 Decimal")
        return Decimal(str(value))


class ManualReviewCondition(StrictModel):
    condition: Condition
    message: str


class PiecewiseCase(StrictModel):
    condition: Condition
    expression: Expression
    label: str | None = None


class LookupRow(StrictModel):
    condition: Condition
    expression: Expression
    label: str | None = None


class Expression(StrictModel):
    op: Literal[
        "constant",
        "input",
        "add",
        "subtract",
        "multiply",
        "divide",
        "sum",
        "min",
        "max",
        "negate",
        "piecewise",
        "lookup",
        "energy_conversion",
        "per_unit",
        "allocation",
    ]
    value: Scalar = None
    input_key: str | None = None
    args: list[Expression] = Field(default_factory=list)
    cases: list[PiecewiseCase] = Field(default_factory=list)
    rows: list[LookupRow] = Field(default_factory=list)
    default: Expression | None = None
    label: str | None = None
    unit: str | None = None
    round_places: int | None = Field(default=None, ge=0, le=12)

    @field_validator("value", mode="before")
    @classmethod
    def reject_float(cls, value: Any) -> Any:
        return _reject_float(value)


class CalculatedDisplayValue(StrictModel):
    """An auditable auxiliary calculation shown with an indicator result."""

    key: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]*$")
    label: str
    unit: str | None = None
    modes: list[InputMode] = Field(default_factory=lambda: [InputMode.DIRECT, InputMode.DETAIL])
    formula: Expression


class ComplianceCase(StrictModel):
    value: str
    requirement: str
    threshold_key: Literal["LEVEL_2", "LEVEL_3"]


class ComplianceRule(StrictModel):
    input_key: str
    cases: list[ComplianceCase]


class ThresholdSet(StrictModel):
    # Some mandatory standards use an em dash for a grade (for example,
    # certain product rows have only a level-3 limit).  Preserve that source
    # gap instead of inventing a numeric threshold.
    level_1: Expression | None = None
    level_2: Expression | None = None
    level_3: Expression


class IndicatorDefinition(StrictModel):
    id: str
    name: str
    unit: str
    comparison: ComparisonDirection = ComparisonDirection.LTE
    input_definitions: list[InputDefinition] = Field(default_factory=list)
    applicability: Condition = Field(default_factory=Condition)
    direct_input_key: str | None = None
    detail_formula: Expression | None = None
    base_thresholds: ThresholdSet | None = None
    thresholds: ThresholdSet
    display_calculations: list[CalculatedDisplayValue] = Field(default_factory=list)
    manual_review_conditions: list[ManualReviewCondition] = Field(default_factory=list)
    compliance_rule: ComplianceRule | None = None
    display_places: int = Field(default=2, ge=0, le=8)
    source_references: list[SourceReference]
    notes: list[str] = Field(default_factory=list)


class ProductDefinition(StrictModel):
    id: str
    name: str
    description: str | None = None
    selection_values: dict[str, str] = Field(default_factory=dict)
    input_definitions: list[InputDefinition] = Field(default_factory=list)
    indicators: list[IndicatorDefinition]


class StandardDefinition(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    id: str
    number: str
    title: str
    version: str
    standard_family_id: str | None = None
    rule_revision: int = Field(default=1, ge=1)
    publication_status: PublicationStatus
    publication_date: date
    effective_date: date
    source_file: str
    source_sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    selection_schema: list[SelectionLevel] = Field(default_factory=list)
    products: list[ProductDefinition]
    corrections: list[str] = Field(default_factory=list)
    lifecycle_status: LifecycleStatus = LifecycleStatus.ACTIVE
    obsolete_date: date | None = None
    replaced_by: list[str] = Field(default_factory=list)
    supersedes: list[str] = Field(default_factory=list)
    @property
    def family_id(self) -> str:
        """Return the stable family identifier, deriving it for legacy JSON."""
        return self.standard_family_id or self.number.rsplit("-", 1)[0]



    def is_effective_on(self, evaluation_date: date) -> bool:
        if self.lifecycle_status is LifecycleStatus.OBSOLETE:
            return False
        if evaluation_date < self.effective_date:
            return False
        return self.obsolete_date is None or evaluation_date < self.obsolete_date

    def selection_warning(self, evaluation_date: date) -> str | None:
        if self.lifecycle_status is LifecycleStatus.OBSOLETE or (self.obsolete_date and evaluation_date >= self.obsolete_date):
            replacement = "、".join(self.replaced_by) if self.replaced_by else "暂无替代标准信息"
            return f"{self.number} 已作废/被替代（替代标准：{replacement}），仅建议用于历史评价。"
        if evaluation_date < self.effective_date:
            return f"{self.number} 尚未实施，实施日期为 {self.effective_date}；当前只能预览，不能形成正式判定。"
        return None


    @model_validator(mode="after")
    def validate_edition_year(self) -> StandardDefinition:
        match = re.search(r"-(\d{4})$", self.number.strip())
        if match and self.version != match.group(1):
            raise ValueError(
                f"标准版本年份与标准编号不一致：{self.number} version={self.version}"
            )
        return self


    @model_validator(mode="after")
    def validate_unique_ids(self) -> StandardDefinition:
        selection_keys = [level.key for level in self.selection_schema]
        if len(selection_keys) != len(set(selection_keys)):
            raise ValueError("产品选择层级 key 重复")
        product_ids = [product.id for product in self.products]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("产品/工序 ID 重复")
        indicator_ids = [indicator.id for product in self.products for indicator in product.indicators]
        if len(indicator_ids) != len(set(indicator_ids)):
            raise ValueError("指标 ID 重复")
        return self


class EvaluationRequest(StrictModel):
    evaluation_date: date
    standard_id: str
    product_id: str
    selection_mode: StandardSelectionMode = StandardSelectionMode.CURRENT

    input_mode: InputMode
    inputs: dict[str, InputValue]
    energy_lines: list[EnergyLine] = Field(default_factory=list)
    production_lines: list[ProductionLine] = Field(default_factory=list)
    organization_name: str | None = None
    project_name: str | None = None
    notes: str | None = None


class CalculationStep(StrictModel):
    sequence: int
    label: str
    operation: str
    expression: str
    value: Decimal | str | bool | None
    unit: str | None = None


class IndicatorResult(StrictModel):
    indicator_id: str
    indicator_name: str
    actual_value: Decimal | None
    unit: str
    base_thresholds: dict[str, Decimal] = Field(default_factory=dict)
    corrected_thresholds: dict[str, Decimal] = Field(default_factory=dict)
    display_values: dict[str, Decimal] = Field(default_factory=dict)
    compliance_requirement: str | None = None
    compliance_limit: Decimal | None = None
    compliance_result: Literal["符合", "不符合"] | None = None
    grade: Grade
    calculation_trace: list[CalculationStep] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)



class EvaluationSummary(StrictModel):
    """UI-neutral summary of a saved evaluation record."""

    evaluation_id: str
    created_at: datetime
    evaluation_date: date
    standard_id: str
    standard_number: str
    product_id: str
    organization_name: str | None = None
    project_name: str | None = None


class PackageHistoryEntry(StrictModel):
    """UI-neutral record of one successfully installed standard package."""

    package_id: str
    data_version: str
    package_mode: str
    issued_at: datetime
    installed_at: datetime
    parent_package_id: str | None = None
    standard_count: int = Field(ge=0)
    rule_count: int = Field(ge=0)
    package_sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")


class AuditEntry(StrictModel):
    """UI-neutral audit event; SQLAlchemy rows must not cross the application boundary."""

    id: int
    created_at: datetime
    actor: str
    action: str
    entity_type: str
    entity_id: str | None = None
    details_json: str


class EvaluationResult(StrictModel):
    evaluation_id: str
    evaluated_at: datetime
    standard_id: str
    standard_number: str
    standard_title: str
    standard_version: str
    product_id: str
    standard_family_id: str | None = None
    rule_revision: int = Field(default=1, ge=1)
    product_name: str
    results: list[IndicatorResult]
    rule_snapshot_sha256: str
    warnings: list[str] = Field(default_factory=list)


def parse_decimal(value: Scalar, *, field_name: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field_name} 不是数值")
    if isinstance(value, float):
        raise TypeError(f"{field_name} 不允许使用浮点数")
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} 不是有效十进制数") from exc
