from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from uebench.domain.models import StandardDefinition


FIRST_BATCH = [
    "GB 16780-2021",
    "GB 29436-2023",
    "GB 21342-2025",
    "GB 21341-2022",
    "GB 21346-2022",
    "GB 21256-2025",
]


def const(value: str | int, *, unit: str | None = None, label: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"op": "constant", "value": str(value)}
    if unit:
        result["unit"] = unit
    if label:
        result["label"] = label
    return result


def inp(key: str, *, unit: str | None = None, label: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"op": "input", "input_key": key}
    if unit:
        result["unit"] = unit
    if label:
        result["label"] = label
    return result


def calc(op: str, *args: dict[str, Any], unit: str | None = None, label: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"op": op, "args": list(args)}
    if unit:
        result["unit"] = unit
    if label:
        result["label"] = label
    return result


def condition(op: str = "always", *, field: str | None = None, value: Any = None, **kwargs: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"op": op}
    if field is not None:
        result["field"] = field
    if value is not None:
        result["value"] = value
    result.update(kwargs)
    return result


def choose(cases: list[tuple[dict[str, Any], dict[str, Any], str]], default: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "op": "piecewise",
        "cases": [
            {"condition": case_condition, "expression": expression, "label": label}
            for case_condition, expression, label in cases
        ],
    }
    if default is not None:
        result["default"] = default
    return result


def thresholds(level_1: dict[str, Any], level_2: dict[str, Any] | None, level_3: dict[str, Any]) -> dict[str, Any]:
    return {"level_1": level_1, "level_2": level_2, "level_3": level_3}


def input_definition(
    key: str,
    label: str,
    *,
    unit: str | None = None,
    data_type: str = "decimal",
    choices: list[str] | None = None,
    minimum: str | None = None,
    maximum: str | None = None,
    modes: list[str] | None = None,
    required_if: dict[str, Any] | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "key": key,
        "label": label,
        "data_type": data_type,
        "unit": unit,
        "required": True,
        "modes": modes or ["DIRECT", "DETAIL"],
    }
    if choices:
        result["choices"] = choices
    if minimum is not None:
        result["minimum"] = minimum
    if maximum is not None:
        result["maximum"] = maximum
    if required_if is not None:
        result["required_if"] = required_if
    if description:
        result["description"] = description
    return result


def reference(meta: dict[str, Any], page: int, *, clause: str, table: str | None = None, note: str | None = None) -> dict[str, Any]:
    return {
        "standard_number": meta["number"],
        "source_file": meta["source_file"],
        "source_sha256": meta["source_sha256"],
        "page": page,
        "clause": clause,
        "table": table,
        "note": note,
    }


def detailed_per_unit(numerator_key: str, unit: str) -> dict[str, Any]:
    return calc(
        "per_unit",
        inp(numerator_key),
        inp("production.total_equivalent"),
        unit=unit,
        label="单位产品实际能耗",
    )


def indicator(
    meta: dict[str, Any],
    indicator_id: str,
    name: str,
    unit: str,
    direct_key: str,
    limit_values: tuple[str, str | None, str],
    *,
    page: int,
    clause: str,
    table: str,
    detail_numerator: str = "energy.total_standard_coal",
    extra_inputs: list[dict[str, Any]] | None = None,
    corrected: dict[str, Any] | None = None,
    notes: list[str] | None = None,
    applicability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = thresholds(
        const(limit_values[0], unit=unit),
        const(limit_values[1], unit=unit) if limit_values[1] is not None else None,
        const(limit_values[2], unit=unit),
    )
    return {
        "id": indicator_id,
        "name": name,
        "unit": unit,
        "comparison": "lte",
        "input_definitions": [
            input_definition(direct_key, f"{name}实际值", unit=unit, modes=["DIRECT"]),
            *(extra_inputs or []),
        ],
        "applicability": applicability or condition(),
        "direct_input_key": direct_key,
        "detail_formula": detailed_per_unit(detail_numerator, unit),
        "base_thresholds": base if corrected is not None else None,
        "thresholds": corrected or base,
        "display_places": 2,
        "source_references": [reference(meta, page, clause=clause, table=table)],
        "notes": notes or [],
    }


def altitude_factor() -> dict[str, Any]:
    return choose(
        [
            (
                condition("gt", field="site.altitude_m", value="1500"),
                calc(
                    "subtract",
                    const("1.179"),
                    calc("multiply", const("0.211"), calc("divide", inp("site.pressure_pa"), const("101325"))),
                ),
                "海拔高于1500m，按5.3式(1)修正",
            )
        ],
        const("1"),
    )


def only_level3_altitude(values: tuple[str, str, str], unit: str) -> dict[str, Any]:
    return thresholds(
        const(values[0], unit=unit),
        const(values[1], unit=unit),
        calc("multiply", const(values[2]), altitude_factor(), unit=unit),
    )


def gb16780(meta: dict[str, Any]) -> list[dict[str, Any]]:
    altitude_inputs = [
        input_definition("site.altitude_m", "厂区海拔高度", unit="m", minimum="0"),
        input_definition(
            "site.pressure_pa",
            "厂区环境大气压",
            unit="Pa",
            minimum="1",
            required_if=condition("gt", field="site.altitude_m", value="1500"),
        ),
    ]
    cement_ratio_input = input_definition(
        "cement.clinker_ratio_pct", "水泥中熟料比例", unit="%", minimum="0", maximum="100"
    )
    cement_correction = lambda base, coefficient: calc(
        "add",
        const(base),
        calc("multiply", calc("subtract", inp("cement.clinker_ratio_pct"), const("75")), const(coefficient)),
        unit="kgce/t",
    )
    cement_limits = thresholds(
        cement_correction("80", "1.10"),
        cement_correction("87", "1.15"),
        calc("multiply", cement_correction("94", "1.20"), altitude_factor(), unit="kgce/t"),
    )
    cement = {
        "id": "cement",
        "name": "水泥产品",
        "description": "水泥单位产品综合能耗；熟料比例按75%基准修正。",
        "input_definitions": [],
        "indicators": [
            indicator(
                meta,
                "cement.comprehensive_energy",
                "水泥单位产品综合能耗",
                "kgce/t",
                "actual.cement_comprehensive_energy",
                ("80", "87", "94"),
                page=4,
                clause="4.1、5.3、5.4",
                table="表1",
                extra_inputs=[cement_ratio_input, *altitude_inputs],
                corrected=cement_limits,
                notes=["熟料比例每偏离75%一个百分点，三级限额分别按1.10、1.15、1.20 kgce/t增减。", "仅3级指标在海拔高于1500m时乘海拔修正系数。"],
            )
        ],
    }
    clinker_limits = {
        "comprehensive": (("100", "107", "117"), "kgce/t"),
        "electricity": (("48", "57", "61"), "kWh/t"),
        "coal": (("94", "100", "109"), "kgce/t"),
    }
    clinker_indicators = []
    for key, name, numerator in (
        ("comprehensive", "熟料单位产品综合能耗", "energy.total_standard_coal"),
        ("electricity", "熟料单位产品综合电耗", "energy.category.electricity.net_amount"),
        ("coal", "熟料单位产品综合煤耗", "energy.category.fuel_coal.net_standard_coal"),
    ):
        values, unit = clinker_limits[key]
        clinker_indicators.append(
            indicator(
                meta,
                f"clinker.{key}",
                name,
                unit,
                f"actual.clinker_{key}",
                values,
                page=4,
                clause="4.2、5.3",
                table="表2",
                detail_numerator=numerator,
                extra_inputs=altitude_inputs,
                corrected=only_level3_altitude(values, unit),
                notes=["仅3级指标在海拔高于1500m时乘海拔修正系数。"],
            )
        )
    clinker = {
        "id": "clinker",
        "name": "水泥熟料",
        "description": "熟料综合能耗、综合电耗和综合煤耗分别判级。",
        "input_definitions": [],
        "indicators": clinker_indicators,
    }
    preparation = {
        "id": "cement-preparation",
        "name": "水泥制备工段",
        "description": "从水泥熟料、石膏及混合材调配库底至水泥成品入库的工段电耗。",
        "input_definitions": [],
        "indicators": [
            indicator(
                meta,
                "cement-preparation.electricity",
                "水泥制备工段电耗",
                "kWh/t",
                "actual.cement_preparation_electricity",
                ("26", "29", "34"),
                page=4,
                clause="4.3",
                table="表3",
                detail_numerator="energy.category.electricity.net_amount",
            )
        ],
    }
    return [cement, clinker, preparation]


def gb29436(meta: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        ("methanol-bituminous", "烟煤制甲醇", ("1380", "1400", "1800"), "4.1", "表1"),
        ("methanol-anthracite", "无烟煤制甲醇", ("1200", "1250", "1500"), "4.1", "表1"),
        ("methanol-lignite", "褐煤制甲醇", ("1750", "1800", "2000"), "4.1", "表1"),
        ("methanol-natural-gas", "天然气制甲醇", ("1130", "1150", "1380"), "4.1", "表1"),
        ("methanol-coke-oven-gas", "焦炉煤气制甲醇", ("1280", "1400", "1500"), "4.1", "表1"),
        ("ethylene-glycol-ethylene", "乙烯制乙二醇", ("335", "375", "470"), "4.2", "表2"),
        ("ethylene-glycol-syngas", "合成气制乙二醇", ("850", "1000", "1300"), "4.2", "表2"),
        ("ethylene-glycol-coal", "煤制乙二醇", ("2450", "2850", "3100"), "4.2", "表2"),
        ("dimethyl-ether", "甲醇制二甲醚", ("1120", "1140", "1200"), "4.3", "表3"),
    ]
    products = []
    for product_id, name, values, clause, table in rows:
        notes = []
        if product_id == "methanol-anthracite":
            notes.append("常压间歇固定床煤气化技术采用无烟煤时执行本行；连续加压煤气化执行烟煤指标。")
        if product_id == "ethylene-glycol-ethylene":
            notes.append("明细模式产量应按附录E当量环氧乙烷产量折算。")
        if product_id == "dimethyl-ether":
            notes.append("原料甲醇折100%，折标准煤系数0.6794 kgce/kg。")
        products.append(
            {
                "id": product_id,
                "name": name,
                "description": "单位产品综合能耗",
                "input_definitions": [],
                "indicators": [
                    indicator(
                        meta,
                        f"{product_id}.comprehensive-energy",
                        f"{name}单位产品综合能耗",
                        "kgce/t",
                        f"actual.{product_id}.comprehensive_energy",
                        values,
                        page=4 if table != "表3" else 5,
                        clause=clause,
                        table=table,
                        notes=notes,
                    )
                ],
            }
        )
    return products


def interpolate(input_key: str, points: list[tuple[str, str]]) -> dict[str, Any]:
    cases: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for index in range(len(points) - 1):
        x1, y1 = points[index]
        x2, y2 = points[index + 1]
        slope = calc("divide", calc("subtract", const(y2), const(y1)), calc("subtract", const(x2), const(x1)))
        expression = calc(
            "add",
            const(y1),
            calc("multiply", calc("subtract", inp(input_key), const(x1)), slope),
        )
        cases.append(
            (
                condition(
                    "range",
                    field=input_key,
                    minimum=x1,
                    maximum=x2,
                    include_minimum=True,
                    include_maximum=False,
                ),
                expression,
                f"{x1}%至{x2}%线性插值",
            )
        )
    cases.append((condition("eq", field=input_key, value=points[-1][0]), const(points[-1][1]), "表列上边界"))
    return choose(cases)


def gb21342(meta: dict[str, Any]) -> list[dict[str, Any]]:
    configurations = [
        {
            "id": "top-charging-coke-oven",
            "name": "顶装焦炉",
            "limits": ("110", "110", "135"),
            "fuel_coefficient": "8.00",
            "volatile_base": "23",
            "volatile_points": [
                ("21", "-8.30"), ("22", "-4.20"), ("23", "0"), ("24", "4.25"),
                ("25", "8.55"), ("26", "11.00"), ("27", "14.08"), ("28", "18.71"),
            ],
            "moisture_base": "10",
            "moisture_coefficient": "3.67",
        },
        {
            "id": "stamp-charging-coke-oven",
            "name": "捣固焦炉",
            "limits": ("115", "115", "140"),
            "fuel_coefficient": "12.00",
            "volatile_base": "25",
            "volatile_points": [
                ("25", "0"), ("26", "3.20"), ("27", "6.44"), ("28", "11.40"),
                ("29", "14.65"), ("30", "17.93"), ("31", "21.23"), ("32", "24.50"),
            ],
            "moisture_base": "10.5",
            "moisture_coefficient": "3.71",
        },
    ]
    products = []
    for item in configurations:
        fuel_correction = choose(
            [
                (
                    condition("eq", field="coke.heating_fuel", value="混合煤气"),
                    calc("multiply", const(item["fuel_coefficient"]), inp("coke.mixed_gas_ratio")),
                    "混合煤气按使用时间比例修正",
                )
            ],
            const("0"),
        )
        raw_correction = calc(
            "add",
            interpolate("coke.dry_volatile_pct", item["volatile_points"]),
            calc(
                "multiply",
                calc("subtract", inp("coke.total_moisture_pct"), const(item["moisture_base"])),
                const(item["moisture_coefficient"]),
            ),
        )
        age_correction = choose(
            [
                (condition("lte", field="coke.oven_age_years", value="15"), const("0"), "炉龄不超过15年"),
                (
                    condition("range", field="coke.oven_age_years", minimum="15", maximum="25", include_minimum=False, include_maximum=True),
                    const("2.50"),
                    "炉龄大于15年至25年",
                ),
                (condition("gt", field="coke.oven_age_years", value="25"), const("5.50"), "炉龄大于25年"),
            ]
        )
        wet_correction = choose(
            [(condition("eq", field="coke.quenching_method", value="湿熄焦"), const("46.46"), "湿熄焦工艺修正")],
            const("0"),
        )
        base_values = item["limits"]
        corrected = thresholds(
            calc("sum", const(base_values[0]), fuel_correction, raw_correction, age_correction, unit="kgce/t"),
            calc("sum", const(base_values[1]), fuel_correction, raw_correction, unit="kgce/t"),
            calc(
                "sum",
                const(base_values[2]),
                fuel_correction,
                raw_correction,
                wet_correction,
                age_correction,
                unit="kgce/t",
            ),
        )
        extra_inputs = [
            input_definition("coke.heating_fuel", "焦炉加热燃料", data_type="text", choices=["焦炉煤气", "混合煤气"]),
            input_definition(
                "coke.mixed_gas_ratio",
                "混合煤气使用时间比例",
                unit="ratio",
                minimum="0",
                maximum="1",
                required_if=condition("eq", field="coke.heating_fuel", value="混合煤气"),
            ),
            input_definition(
                "coke.dry_volatile_pct",
                "入炉煤干燥基挥发分",
                unit="%",
                minimum=item["volatile_points"][0][0],
                maximum=item["volatile_points"][-1][0],
            ),
            input_definition("coke.total_moisture_pct", "入炉煤全水分", unit="%", minimum="0", maximum="100"),
            input_definition("coke.quenching_method", "熄焦方式", data_type="text", choices=["干熄焦", "湿熄焦"]),
            input_definition("coke.oven_age_years", "焦炉炉龄", unit="年", minimum="0"),
        ]
        products.append(
            {
                "id": item["id"],
                "name": item["name"],
                "description": "常规焦炉焦炭单位产品能耗，按燃料、原料、工艺和炉龄分级修正。",
                "input_definitions": [],
                "indicators": [
                    indicator(
                        meta,
                        f"{item['id']}.energy",
                        f"{item['name']}焦炭单位产品能耗",
                        "kgce/t",
                        f"actual.{item['id']}.energy",
                        base_values,
                        page=6,
                        clause="4、5.3",
                        table="表1、表2",
                        extra_inputs=extra_inputs,
                        corrected=corrected,
                        notes=["1级修正燃料、原料和炉龄；2级修正燃料和原料；3级修正燃料、原料、熄焦方式和炉龄。", "原料条件非表列值按线性插值。"],
                    )
                ],
            }
        )
    return products


def ore_grade_thresholds(values: tuple[str, str, str], grade_key: str, baseline: str, coefficient: str, unit: str) -> dict[str, Any]:
    def corrected(base: str) -> dict[str, Any]:
        return calc(
            "subtract",
            const(base),
            calc("multiply", calc("subtract", inp(grade_key), const(baseline)), const(coefficient)),
            unit=unit,
        )

    return thresholds(corrected(values[0]), corrected(values[1]), corrected(values[2]))


def gb21341(meta: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        ("ferrosilicon", "硅铁", "smelting_electricity", ("8050", "8300", "8400"), ("1700", "1770", "1850"), "98", "40", None),
        ("electric-high-carbon-ferromanganese", "电炉高碳锰铁", "smelting_electricity", ("2100", "2400", "2550"), ("610", "660", "700"), "39", "50", None),
        ("ferromanganese-silicon", "锰硅合金", "smelting_electricity", ("3800", "4000", "4250"), ("850", "860", "950"), "36", "100", None),
        ("low-carbon-ferromanganese-silicon", "低碳锰硅合金", "smelting_electricity", ("4650", "4900", "4990"), ("1180", "1200", "1230"), "38", "100", None),
        ("micro-carbon-ferromanganese", "微碳锰铁", "smelting_electricity", ("1050", "1100", "1140"), ("150", "160", "170"), "44", "30", None),
        ("high-carbon-ferrochrome", "高碳铬铁", "smelting_electricity", ("3100", "3300", "3500"), ("800", "850", "900"), "40", "80", "2.2"),
        ("charge-ferrochrome", "炉料级铬铁", "smelting_electricity", ("3200", "3500", "3650"), ("830", "910", "940"), "40", "80", "1.5"),
        ("medium-low-carbon-ferrochrome", "中（低）碳铬铁", "smelting_electricity", ("1650", "1800", "1950"), ("220", "240", "260"), "48", "35", None),
        ("blast-furnace-ferromanganese", "高炉锰铁", "coke_consumption", ("1280", "1320", "1350"), ("800", "950", "1050"), "37", "30", None),
    ]
    products = []
    for product_id, name, primary_kind, primary_values, comprehensive_values, baseline, coefficient, chromium_ratio in rows:
        grade_key = f"ore.{product_id}.grade_pct"
        if primary_kind == "smelting_electricity":
            primary_name = f"{name}单位产品冶炼电耗"
            primary_unit = "kWh/t"
            numerator = "energy.category.electricity.net_amount"
        else:
            primary_name = f"{name}单位产品焦炭消耗"
            primary_unit = "kg/t"
            numerator = "energy.category.coke.net_amount"
        inputs = [input_definition(grade_key, f"{name}入炉矿实际品位", unit="%", minimum="0", maximum="100")]
        notes = [f"入炉矿品位每升高1个百分点，{primary_name}限额降低{coefficient} {primary_unit}；降低时反向调整。"]
        if chromium_ratio:
            inputs.append(
                input_definition(
                    f"ore.{product_id}.chromium_iron_ratio",
                    "入炉铬矿铬铁比",
                    unit="ratio",
                    minimum=chromium_ratio,
                    description=f"表1修正值仅适用于铬铁比不低于{chromium_ratio}。",
                )
            )
            notes.append(f"修正系数适用条件：铬铁比≥{chromium_ratio}。")
        primary = indicator(
            meta,
            f"{product_id}.{primary_kind}",
            primary_name,
            primary_unit,
            f"actual.{product_id}.{primary_kind}",
            primary_values,
            page=6,
            clause="4",
            table="表1" if primary_kind == "smelting_electricity" else "表2",
            detail_numerator=numerator,
            extra_inputs=inputs,
            corrected=ore_grade_thresholds(primary_values, grade_key, baseline, coefficient, primary_unit),
            notes=notes,
        )
        comprehensive = indicator(
            meta,
            f"{product_id}.comprehensive_energy",
            f"{name}单位产品综合能耗",
            "kgce/t",
            f"actual.{product_id}.comprehensive_energy",
            comprehensive_values,
            page=6,
            clause="4",
            table="表1" if primary_kind == "smelting_electricity" else "表2",
        )
        products.append(
            {
                "id": product_id,
                "name": name,
                "description": "主要能耗指标分别判级，不形成总体等级。",
                "input_definitions": [],
                "indicators": [primary, comprehensive],
            }
        )
    return products


def gb21346(meta: dict[str, Any]) -> list[dict[str, Any]]:
    electrolytic_indicators = []
    electrolytic_rows = [
        ("aluminum-liquid-ac", "铝液交流电耗", "kWh/t", ("12950", "13000", "13350"), "energy.category.electricity.net_amount"),
        ("aluminum-liquid-comprehensive-ac", "铝液综合交流电耗", "kWh/t", ("13250", "13350", "13700"), "energy.category.electricity.net_amount"),
        ("aluminum-ingot-comprehensive-ac", "铝锭综合交流电耗", "kWh/t", ("13300", "13400", "13750"), "energy.category.electricity.net_amount"),
        ("aluminum-ingot-comprehensive-energy", "铝锭综合单耗", "kgce/t", ("1670", "1680", "1720"), "energy.total_standard_coal"),
    ]
    for key, name, unit, values, numerator in electrolytic_rows:
        electrolytic_indicators.append(
            indicator(
                meta,
                f"electrolytic-aluminum.{key}",
                name,
                unit,
                f"actual.electrolytic-aluminum.{key}",
                values,
                page=5,
                clause="4.1",
                table="表1",
                detail_numerator=numerator,
            )
        )
    products = [
        {
            "id": "electrolytic-aluminum",
            "name": "电解铝",
            "description": "电解铝液和铝锭的交流电耗、综合能耗分别判级。",
            "input_definitions": [],
            "indicators": electrolytic_indicators,
        }
    ]
    alumina_rows = [
        ("alumina-bayer", "拜耳法氧化铝", ("310", "360", "430"), ("340", "390", "460")),
        ("alumina-other", "其他工艺氧化铝", ("500", "550", "650"), ("550", "600", "700")),
    ]
    for product_id, name, process_values, comprehensive_values in alumina_rows:
        products.append(
            {
                "id": product_id,
                "name": name,
                "description": "工艺能耗和综合能耗分别判级。",
                "input_definitions": [],
                "indicators": [
                    indicator(
                        meta,
                        f"{product_id}.process-energy",
                        f"{name}工艺能耗",
                        "kgce/t",
                        f"actual.{product_id}.process_energy",
                        process_values,
                        page=6,
                        clause="4.2",
                        table="表2",
                    ),
                    indicator(
                        meta,
                        f"{product_id}.comprehensive-energy",
                        f"{name}综合能耗",
                        "kgce/t",
                        f"actual.{product_id}.comprehensive_energy",
                        comprehensive_values,
                        page=6,
                        clause="4.2",
                        table="表2",
                    ),
                ],
            }
        )
    return products


def mineral_adjustment(prefix: str, coefficients: tuple[str, str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inputs = [
        input_definition(f"{prefix}.rare_earth_ore_pct", "稀土矿用量比例", unit="%", minimum="0", maximum="100"),
        input_definition(f"{prefix}.vanadium_titanium_magnetite_pct", "钒钛磁铁矿用量比例", unit="%", minimum="0", maximum="100"),
        input_definition(f"{prefix}.laterite_nickel_ore_pct", "红土镍矿用量比例", unit="%", minimum="0", maximum="100"),
    ]
    adjustment = calc(
        "sum",
        calc("multiply", inp(f"{prefix}.rare_earth_ore_pct"), const(coefficients[0])),
        calc("multiply", inp(f"{prefix}.vanadium_titanium_magnetite_pct"), const(coefficients[1])),
        calc("multiply", inp(f"{prefix}.laterite_nickel_ore_pct"), const(coefficients[2])),
    )
    return inputs, adjustment


def add_adjustment(values: tuple[str, str, str], adjustment: dict[str, Any], unit: str = "kgce/t") -> dict[str, Any]:
    return thresholds(
        calc("add", const(values[0]), adjustment, unit=unit),
        calc("add", const(values[1]), adjustment, unit=unit),
        calc("add", const(values[2]), adjustment, unit=unit),
    )


def grade_addition(field: str, rows: list[tuple[str, str]]) -> dict[str, Any]:
    return choose(
        [(condition("eq", field=field, value=value), const(amount), value) for value, amount in rows],
        const("0"),
    )


def gb21256(meta: dict[str, Any]) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for product_id, name, values, page, table in (
        ("sintering", "烧结工序", ("43", "46", "52"), 6, "表1"),
        ("pelletizing", "球团工序", ("15", "22", "33"), 6, "表2"),
    ):
        inputs, adjustment = mineral_adjustment(product_id, ("0.15", "0.2", "1.2"))
        products.append(
            {
                "id": product_id,
                "name": name,
                "description": "稀土矿、钒钛磁铁矿和红土镍矿用量按百分点修正。",
                "input_definitions": [],
                "indicators": [
                    indicator(
                        meta,
                        f"{product_id}.energy",
                        f"{name}单位产品能耗",
                        "kgce/t",
                        f"actual.{product_id}.energy",
                        values,
                        page=page,
                        clause="4.1" if product_id == "sintering" else "4.2",
                        table=table,
                        extra_inputs=inputs,
                        corrected=add_adjustment(values, adjustment),
                    )
                ],
            }
        )

    bf_inputs, bf_mineral_adjustment = mineral_adjustment("blast-furnace", ("0.3", "0.45", "0.5"))
    bf_inputs.append(
        input_definition("blast-furnace.feed_grade_pct", "高炉入炉原料品位", unit="%", minimum="0", maximum="100")
    )
    grade_reduction = calc(
        "multiply",
        calc("min", const("5"), calc("max", const("0"), calc("subtract", const("62"), inp("blast-furnace.feed_grade_pct")))),
        const("3.61"),
    )
    bf_adjustment = calc("add", bf_mineral_adjustment, grade_reduction)
    products.append(
        {
            "id": "blast-furnace",
            "name": "高炉工序",
            "description": "矿种比例和入炉原料品位按4.3.2至4.3.5修正。",
            "input_definitions": [],
            "indicators": [
                indicator(
                    meta,
                    "blast-furnace.energy",
                    "高炉工序单位产品能耗",
                    "kgce/t",
                    "actual.blast-furnace.energy",
                    ("361", "370", "415"),
                    page=7,
                    clause="4.3",
                    table="表3",
                    extra_inputs=bf_inputs,
                    corrected=add_adjustment(("361", "370", "415"), bf_adjustment),
                    notes=["入炉原料品位低于62%时每降低1个百分点增加3.61 kgce/t，最多按5个百分点调整；高于62%不反向扣减。"],
                )
            ],
        }
    )

    converter_inputs = [
        input_definition("converter.type", "转炉类型", data_type="text", choices=["普通转炉", "特殊用途转炉"]),
        input_definition("converter.scrap_ratio_pct", "转炉废钢比", unit="%", minimum="0", maximum="100"),
        input_definition(
            "converter.steel_category",
            "主要冶炼钢种",
            data_type="text",
            choices=["普碳钢", "优质碳素结构钢", "优质轴承齿轮硬线工模具钢", "深冲超深冲管线钢"],
        ),
    ]
    converter_adjustment = calc(
        "add",
        calc("multiply", inp("converter.scrap_ratio_pct"), const("0.23")),
        grade_addition(
            "converter.steel_category",
            [("优质碳素结构钢", "0.8"), ("优质轴承齿轮硬线工模具钢", "1.2"), ("深冲超深冲管线钢", "1.5")],
        ),
    )
    products.append(
        {
            "id": "converter",
            "name": "转炉工序",
            "description": "特殊用途转炉不按本指标考核。",
            "input_definitions": [],
            "indicators": [
                indicator(
                    meta,
                    "converter.energy",
                    "转炉工序单位产品能耗",
                    "kgce/t",
                    "actual.converter.energy",
                    ("-30", "-28", "-12"),
                    page=7,
                    clause="4.4",
                    table="表4",
                    extra_inputs=converter_inputs,
                    corrected=add_adjustment(("-30", "-28", "-12"), converter_adjustment),
                    applicability=condition("eq", field="converter.type", value="普通转炉"),
                    notes=["负值表示工序回收能源大于消耗能源。"],
                )
            ],
        }
    )

    eaf_rows = [
        ("electric-arc-furnace-lt50", "电弧炉工序（容量＜50t）", ("61", None, "86")),
        ("electric-arc-furnace-50-70", "电弧炉工序（50t≤容量＜70t）", ("61", None, "72")),
        ("electric-arc-furnace-ge70", "电弧炉工序（容量≥70t）", ("61", "64", "72")),
    ]
    for product_id, name, values in eaf_rows:
        eaf_inputs = [
            input_definition("eaf.hot_metal_ratio_pct", "入炉铁水比", unit="%", minimum="0", maximum="100"),
            input_definition(
                "eaf.steel_category",
                "主要冶炼钢种",
                data_type="text",
                choices=["普碳钢", "全不锈钢", "优质碳素结构钢", "优质轴承齿轮硬线工模具钢"],
            ),
        ]

        def corrected_eaf(base: str) -> dict[str, Any]:
            route_base = choose(
                [(condition("eq", field="eaf.steel_category", value="全不锈钢"), calc("multiply", const(base), const("1.10")), "全不锈钢增加10%")],
                const(base),
            )
            addition = grade_addition(
                "eaf.steel_category",
                [("优质碳素结构钢", "8"), ("优质轴承齿轮硬线工模具钢", "15")],
            )
            return calc(
                "add",
                calc("subtract", route_base, calc("multiply", inp("eaf.hot_metal_ratio_pct"), const("0.8"))),
                addition,
                unit="kgce/t",
            )

        corrected_values = thresholds(
            corrected_eaf(values[0]),
            corrected_eaf(values[1]) if values[1] is not None else None,
            corrected_eaf(values[2]),
        )
        products.append(
            {
                "id": product_id,
                "name": name,
                "description": "表5以全废钢冶炼普碳钢为基准；部分容量档标准未规定2级。",
                "input_definitions": [],
                "indicators": [
                    indicator(
                        meta,
                        f"{product_id}.energy",
                        f"{name}单位产品能耗",
                        "kgce/t",
                        f"actual.{product_id}.energy",
                        values,
                        page=8,
                        clause="4.5",
                        table="表5",
                        extra_inputs=eaf_inputs,
                        corrected=corrected_values,
                        notes=["标准表中“—”保留为缺级，不用推测值替代。", "入炉铁水比每增加1个百分点，限额降低0.8 kgce/t。"],
                    )
                ],
            }
        )
    return products


BUILDERS = {
    "GB 16780-2021": gb16780,
    "GB 29436-2023": gb29436,
    "GB 21342-2025": gb21342,
    "GB 21341-2022": gb21341,
    "GB 21346-2022": gb21346,
    "GB 21256-2025": gb21256,
}


def main() -> None:
    data_root = Path("data")
    catalog_path = data_root / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    by_number = {item["number"]: item for item in catalog["standards"]}
    summary: list[dict[str, Any]] = []
    for number in FIRST_BATCH:
        meta = by_number[number]
        definition_path = data_root / "definitions" / f"{meta['id']}.json"
        raw = json.loads(definition_path.read_text(encoding="utf-8"))
        raw["publication_status"] = "reviewed"
        raw["products"] = BUILDERS[number](meta)
        definition = StandardDefinition.model_validate(raw)
        definition_path.write_text(definition.model_dump_json(indent=2) + "\n", encoding="utf-8")
        meta["status"] = "reviewed"
        indicators = [indicator for product in definition.products for indicator in product.indicators]
        summary.append(
            {
                "number": number,
                "title": definition.title,
                "product_count": len(definition.products),
                "indicator_count": len(indicators),
                "source_file": definition.source_file,
                "source_sha256": definition.source_sha256,
                "status": definition.publication_status.value,
            }
        )
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (data_root / "first-batch-review.json").write_text(
        json.dumps({"schema_version": "1.0", "standards": summary}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已生成首批 {len(summary)} 项 reviewed 规则，共 {sum(item['indicator_count'] for item in summary)} 个指标。")


if __name__ == "__main__":
    main()
