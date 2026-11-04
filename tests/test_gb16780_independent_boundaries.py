"""冻结映射V1.2表1/2/3独立45点：从原始用量构造，不导入实现测试助手。"""
from decimal import Decimal
from pathlib import Path

import pytest

from uebench.domain.engine import EvaluationEngine
from uebench.domain.models import (
    CementDetails, CementFuelLine, EvaluationRequest, InputValue, StandardDefinition,
)

LIMITS = {
    "clinker.coal": ("94", "100", "109"),
    "clinker.comprehensive": ("100", "107", "117"),
    "clinker.electricity": ("48", "57", "61"),
    "cement.comprehensive_energy": ("80", "87", "94"),
    "cement-preparation.electricity": ("26", "29", "34"),
}


@pytest.fixture(scope="module")
def definition():
    path = Path(__file__).resolve().parents[1] / "data/definitions/gb-16780-2021.json"
    return StandardDefinition.model_validate_json(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("indicator,threshold", [(key, t) for key, limits in LIMITS.items() for t in limits])
@pytest.mark.parametrize("delta", ["-0.01", "0", "0.01"])
def test_frozen_mapping_raw_quantity_boundary(definition, indicator, threshold, delta):
    value = Decimal(threshold) + Decimal(delta)
    raw = {
        "production_mode": ("integrated", None), "evaluation_period": ("2025年", None),
        "production_line_id": ("独立验收A", None), "altitude_m": ("1500", "m"),
        "clinker_production_t": ("1000", "t"), "cement_production_t": ("1000", "t"),
        "clinker_consumption_t": ("750", "t"), "clinker_ratio_percent": ("75", "%"),
        "clinker_electricity_kwh": ("0", "kW·h"), "waste_heat_generation_kwh": ("0", "kW·h"),
        "waste_heat_self_use_kwh": ("0", "kW·h"), "cement_grinding_packaging_kwh": ("0", "kW·h"),
        "admixture_preparation_kwh": ("0", "kW·h"), "gypsum_preparation_kwh": ("0", "kW·h"),
        "auxiliary_electricity_kwh": ("0", "kW·h"), "cement_fuel_kgce": ("0", "kgce"),
        "grinding_electricity_kwh": ("0", "kW·h"),
    }
    fuel = "0"
    # 热值等于标准煤热值；分母1000t，原量1000×value精确产生目标单位值。
    # 其余贡献为零，预期由冻结限值直接推导，未调用被测公式生成预期。
    if indicator in ("clinker.coal", "clinker.comprehensive"):
        fuel = str(value * 1000)
    elif indicator == "clinker.electricity":
        raw["clinker_electricity_kwh"] = (str(value * 1000), "kW·h")
    elif indicator == "cement.comprehensive_energy":
        raw["cement_fuel_kgce"] = (str(value * 1000), "kgce")
    else:
        raw["grinding_electricity_kwh"] = (str(value * 1000), "kW·h")
    request = EvaluationRequest(
        evaluation_date="2026-11-03", standard_id="gb-16780-2021", product_id="cement", input_mode="DETAIL",
        inputs={key: InputValue(value=v, unit=u) for key, (v, u) in raw.items()},
        cement_details=CementDetails(fuel_lines=[CementFuelLine(
            line_id="f1", name="验收燃料", amount_kg=fuel, low_heat_kj_per_kg="29307.6")]),
    )
    result = next(item for item in EvaluationEngine().evaluate(definition, request).results
                  if item.indicator_id == indicator)
    expected_grade = next((f"LEVEL_{level}" for level, limit in enumerate(LIMITS[indicator], 1)
                           if value <= Decimal(limit)), "NOT_QUALIFIED")
    assert result.actual_value == value
    assert result.grade.value == expected_grade
