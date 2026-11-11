"""只读历史水泥数据模型；不参与新请求或计算。"""
from __future__ import annotations
import json
import hashlib
from typing import Any, Literal
from pydantic import Field, field_validator, PrivateAttr
from .models import (StrictModel, Expression, Scalar, _reject_float,
                     EvaluationRequest, StandardDefinition)

class CementCalculationNode(StrictModel):
    """GB16780 r2 local dependency graph; not a public execution schema."""

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    unit: str | None = None
    formula: Expression
    source: str | None = None


class CementFuelLine(StrictModel):
    line_id: str
    name: str
    amount_kg: Scalar
    low_heat_kj_per_kg: Scalar
    source_note: str | None = None

    @field_validator("amount_kg", "low_heat_kj_per_kg", mode="before")
    @classmethod
    def reject_float(cls, value: Any) -> Any:
        return _reject_float(value)


class CementSharedAllocation(StrictModel):
    allocation_id: str
    product: Literal["clinker", "cement"]
    target_input_key: str
    target_line_id: str
    original_amount: Scalar
    unit: str
    line_production_t: dict[str, Scalar]
    source_note: str | None = None

    @field_validator("original_amount", "line_production_t", mode="before")
    @classmethod
    def reject_float(cls, value: Any) -> Any:
        return _reject_float(value)


class CementDetails(StrictModel):
    fuel_lines: list[CementFuelLine] = Field(default_factory=list)
    shared_allocations: list[CementSharedAllocation] = Field(default_factory=list)



class HistoricalCementRequest(EvaluationRequest):
    cement_details: CementDetails | None = None

class HistoricalCementStandard(StandardDefinition):
    cement_calculation_nodes: list[CementCalculationNode] = Field(default_factory=list)
    _original_payload: dict = PrivateAttr(default_factory=dict)


def parse_saved(model, payload):
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("保存快照必须是JSON对象")
    if model is EvaluationRequest and data.get("standard_id") == "gb-16780-2021" and data.get("product_id") == "cement" and ("cement_details" in data or "production_mode" in data.get("inputs", {})):
        if data.get("product_id") != "cement" or data.get("cement_lines") or data.get("cement_shared_energy"):
            raise ValueError("历史水泥请求结构身份不一致")
        return HistoricalCementRequest.model_validate(data)
    if model is StandardDefinition and data.get("id") == "gb-16780-2021" and "cement_calculation_nodes" in data:
        if data.get("rule_revision") != 2:
            raise ValueError("历史水泥规则版本身份不一致")
        value = HistoricalCementStandard.model_validate(data)
        if len(value.cement_calculation_nodes) != 15:
            raise ValueError("历史水泥规则节点不完整")
        value._original_payload = data
        return value
    return model.model_validate_json(payload)


def original_hash(snapshot):
    payload = snapshot._original_payload
    if snapshot.model_dump(mode="json") != HistoricalCementStandard.model_validate(payload).model_dump(mode="json"):
        raise ValueError("历史水泥只读规则字段被改变，原始哈希不能用于当前字段")
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()
