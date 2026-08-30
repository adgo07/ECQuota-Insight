from __future__ import annotations

"""Refine the six product/process rows in GB 29450-2012.

The source tables contain six rows.  Table 2 gives admission values only for
E and E(ECR) yarn, so the other four rows intentionally preserve a missing
level-2 value instead of inventing a threshold.
"""

import argparse
import json
from pathlib import Path

from uebench.domain.models import StandardDefinition


NUMBER = "GB 29450-2012"


def node(
    op: str,
    *,
    value: str | None = None,
    input_key: str | None = None,
    args: list[dict] | None = None,
    cases: list[dict] | None = None,
    unit: str | None = None,
    label: str | None = None,
    default: dict | None = None,
) -> dict:
    return {
        "op": op,
        "value": value,
        "input_key": input_key,
        "args": args or [],
        "cases": cases or [],
        "rows": [],
        "default": default,
        "label": label,
        "unit": unit,
        "round_places": None,
    }


def inp(key: str, unit: str | None = None, label: str | None = None) -> dict:
    return node("input", input_key=key, unit=unit, label=label)


def const(value: str, unit: str | None = None, label: str | None = None) -> dict:
    return node("constant", value=value, unit=unit, label=label)


def add(*args: dict, unit: str | None = None, label: str | None = None) -> dict:
    return node("add", args=list(args), unit=unit, label=label)


def mul(*args: dict, unit: str | None = None, label: str | None = None) -> dict:
    return node("multiply", args=list(args), unit=unit, label=label)


def div(left: dict, right: dict, unit: str | None = None, label: str | None = None) -> dict:
    return node("divide", args=[left, right], unit=unit, label=label)


def per_unit(energy: dict, production: dict, label: str) -> dict:
    return node("per_unit", args=[energy, production], unit="kgce/t", label=label)


def decimal_input(
    key: str,
    label: str,
    unit: str,
    *,
    modes: list[str],
    description: str,
    required: bool = True,
    required_if: dict | None = None,
) -> dict:
    return {
        "key": key,
        "label": label,
        "data_type": "decimal",
        "unit": unit,
        "required": required,
        "required_if": required_if,
        "modes": modes,
        "minimum": "0",
        "maximum": None,
        "choices": [],
        "description": description,
    }


def text_input(
    key: str,
    label: str,
    choices: list[str],
    *,
    required_if: dict | None = None,
    description: str,
) -> dict:
    return {
        "key": key,
        "label": label,
        "data_type": "text",
        "unit": None,
        "required": True,
        "required_if": required_if,
        "modes": ["DETAIL"],
        "minimum": None,
        "maximum": None,
        "choices": choices,
        "description": description,
    }


def thresholds(levels: tuple[str | None, str | None, str | None]) -> dict:
    return {
        f"level_{index}": const(value, "kgce/t") if value is not None else None
        for index, value in enumerate(levels, 1)
    }


def fine_yarn_inputs(mode_key: str, mixed_value: str, *, coarse: bool) -> list[dict]:
    required_if_mixed = {"op": "eq", "field": mode_key, "value": mixed_value}
    if coarse:
        return [
            text_input(
                mode_key,
                "池窑混合型纱生产方式",
                ["单纯粗纱", mixed_value],
                description="按GB 29450-2012第5.2.2.1节选择；混合型窑按粗纱为主体使用公式（4）。",
            ),
            decimal_input(
                "glass_fiber.pool.coarse_yarn_t",
                "合格粗纱（纤维直径＞9μm）产量",
                "t",
                modes=["DETAIL"],
                description="公式（4）中的Gy粗；单纯粗纱或混合型窑均填写。",
            ),
            decimal_input(
                "glass_fiber.pool.fine_yarn_total_t",
                "合格细纱（纤维直径≤9μm）总产量",
                "t",
                modes=["DETAIL"],
                required_if=required_if_mixed,
                description="公式（4）中的G细；仅混合型窑按粗纱为主体时填写。",
            ),
        ]
    return [
        text_input(
            mode_key,
            "池窑混合型纱生产方式",
            ["单纯细纱", mixed_value],
            description="按GB 29450-2012第5.2.2.1节选择；混合型窑按细纱为主体使用公式（5）。",
        ),
        decimal_input(
            "glass_fiber.pool.fine_yarn_gt5um_t",
            "合格细纱（纤维直径＞5μm）产量",
            "t",
            modes=["DETAIL"],
            description="公式（3）和（5）中的Gy9。",
        ),
        decimal_input(
            "glass_fiber.pool.fine_yarn_le5um_t",
            "合格细纱（纤维直径≤5μm）产量",
            "t",
            modes=["DETAIL"],
            description="公式（3）中的Gy5；与Gy9合计为细纱实际产量。",
        ),
        decimal_input(
            "glass_fiber.pool.coarse_yarn_t",
            "合格粗纱（纤维直径＞9μm）产量",
            "t",
            modes=["DETAIL"],
            required_if=required_if_mixed,
            description="公式（5）中的G粗；仅混合型窑按细纱为主体时填写。",
        ),
    ]


def pool_yarn_production(*, coarse: bool) -> tuple[list[dict], dict, list[dict]]:
    mode_key = "glass_fiber.pool.yarn_mode"
    mixed_value = "混合型窑（粗纱为主体）" if coarse else "混合型窑（细纱为主体）"
    definitions = fine_yarn_inputs(mode_key, mixed_value, coarse=coarse)
    if coarse:
        production = node(
            "piecewise",
            cases=[
                {
                    "condition": {"op": "eq", "field": mode_key, "value": "单纯粗纱"},
                    "expression": inp("glass_fiber.pool.coarse_yarn_t", unit="t"),
                    "label": "单纯粗纱产量",
                },
                {
                    "condition": {"op": "eq", "field": mode_key, "value": mixed_value},
                    "expression": add(
                        inp("glass_fiber.pool.coarse_yarn_t", unit="t"),
                        mul(const("1.4"), inp("glass_fiber.pool.fine_yarn_total_t", unit="t"), unit="t"),
                        unit="t",
                    ),
                    "label": "混合型窑粗纱主体折算产量 Gyz粗（公式4）",
                },
            ],
            unit="t",
            label="池窑粗纱合格折算产量",
        )
        formula_refs = [
            {"page": 6, "clause": "5.2.2.1", "table": "公式（4）"},
            {"page": 7, "clause": "5.2.2.2～5.2.2.3", "table": "公式（7）、（8）"},
        ]
        return definitions, production, formula_refs

    production = node(
        "piecewise",
        cases=[
            {
                "condition": {"op": "eq", "field": mode_key, "value": "单纯细纱"},
                "expression": add(
                    inp("glass_fiber.pool.fine_yarn_gt5um_t", unit="t"),
                    mul(const("1.5"), inp("glass_fiber.pool.fine_yarn_le5um_t", unit="t"), unit="t"),
                    unit="t",
                ),
                "label": "单纯细纱折算产量 Gyz9（公式3）",
            },
            {
                "condition": {"op": "eq", "field": mode_key, "value": mixed_value},
                "expression": add(
                    inp("glass_fiber.pool.fine_yarn_gt5um_t", unit="t"),
                    inp("glass_fiber.pool.fine_yarn_le5um_t", unit="t"),
                    div(inp("glass_fiber.pool.coarse_yarn_t", unit="t"), const("1.4"), unit="t"),
                    unit="t",
                ),
                "label": "混合型窑细纱主体折算产量 Gyz细（公式5）",
            },
        ],
        unit="t",
        label="池窑细纱合格折算产量",
    )
    formula_refs = [
        {"page": 6, "clause": "5.2.2.1", "table": "公式（3）～（5）"},
        {"page": 7, "clause": "5.2.2.2～5.2.2.3", "table": "公式（7）、（8）"},
    ]
    return definitions, production, formula_refs


def refine(data_dir: Path) -> Path:
    path = data_dir / "definitions" / "gb-29450-2012.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("number") != NUMBER:
        raise ValueError(f"规则文件标准号不符：{data.get('number')}")
    source_file, source_sha = data["source_file"], data["source_sha256"]
    rows = [
        {
            "id": "pool-e-fine",
            "name": "池窑法—E玻璃纤维纱（纤维直径≤9μm）",
            "levels": ("750", "750", "900"),
            "kind": "fine",
            "description": "池窑法E玻璃纤维纱（纤维直径≤9μm）；单纯细纱和混合型窑按主体产量折算。",
        },
        {
            "id": "pool-ecr-coarse",
            "name": "池窑法—E(ECR)玻璃纤维纱（纤维直径＞9μm）",
            "levels": ("550", "550", "700"),
            "kind": "coarse",
            "description": "池窑法E(ECR)玻璃纤维纱（纤维直径＞9μm）；粗纱按实际或混合型窑折算产量计。",
        },
        {
            "id": "pool-medium-alkali-yarn",
            "name": "池窑法—中碱玻璃纤维纱",
            "levels": ("550", None, "650"),
            "kind": "yarn-total",
            "description": "池窑法中碱玻璃纤维纱；表2未列该产品准入值，2级限额保留缺级。",
        },
        {
            "id": "crucible-nonalkali-ball",
            "name": "坩埚法—制球—无碱玻璃球",
            "levels": ("400", None, "580"),
            "kind": "ball",
            "description": "坩埚法制球工序无碱玻璃球；表2未列该产品准入值，2级限额保留缺级。",
        },
        {
            "id": "crucible-medium-alkali-ball",
            "name": "坩埚法—制球—中碱玻璃球",
            "levels": ("300", None, "400"),
            "kind": "ball",
            "description": "坩埚法制球工序中碱玻璃球；表2未列该产品准入值，2级限额保留缺级。",
        },
        {
            "id": "crucible-yarn",
            "name": "坩埚法—拉丝—玻璃纤维纱",
            "levels": ("300", None, "430"),
            "kind": "crucible-yarn",
            "description": "坩埚法拉丝工序玻璃纤维纱；产量按表4线密度折算系数λ计。表2未列该产品准入值，2级限额保留缺级。",
        },
    ]
    products = []
    for row in rows:
        actual_key = f"actual.GB_29450_2012.{row['id']}.comprehensive_energy"
        detail_inputs: list[dict] = []
        if row["kind"] == "fine":
            detail_inputs, production, formula_refs = pool_yarn_production(coarse=False)
            formula_label = "池窑细纱单位产品综合能耗（公式7、8）"
        elif row["kind"] == "coarse":
            detail_inputs, production, formula_refs = pool_yarn_production(coarse=True)
            formula_label = "池窑粗纱单位产品综合能耗（公式7、8）"
        else:
            production = inp("production.total_equivalent", unit="t")
            if row["kind"] == "ball":
                formula_refs = [
                    {"page": 5, "clause": "5.2.1", "table": "公式（1）"},
                    {"page": 6, "clause": "5.2.1.2", "table": "公式（2）"},
                ]
                formula_label = "玻璃球单位产品综合能耗（公式2）"
            else:
                formula_refs = [
                    {"page": 7, "clause": "5.2.2.2～5.2.2.3", "table": "公式（7）、（8）"},
                ]
                formula_label = "玻璃纤维纱单位产品综合能耗（公式8）"
                if row["kind"] == "crucible-yarn":
                    formula_refs.append({"page": 7, "clause": "5.2.2.1", "table": "表4、公式（6）"})
        definitions = [
            {
                "key": actual_key,
                "label": f"{row['name']}单位产品综合能耗实际值",
                "data_type": "decimal",
                "unit": "kgce/t",
                "required": True,
                "required_if": None,
                "modes": ["DIRECT"],
                "minimum": "0",
                "maximum": None,
                "choices": [],
                "description": "直接录入按GB 29450-2012第5.2节核算的单位产品综合能耗。",
            },
            *detail_inputs,
        ]
        indicator = {
            "id": f"GB_29450_2012.{row['id']}.comprehensive-energy",
            "name": "单位产品综合能耗",
            "unit": "kgce/t",
            "comparison": "lte",
            "input_definitions": definitions,
            "applicability": {"op": "always"},
            "direct_input_key": actual_key,
            "detail_formula": per_unit(
                inp("energy.total_standard_coal", unit="kgce"),
                production,
                formula_label,
            ),
            "base_thresholds": thresholds(row["levels"]),
            "thresholds": thresholds(row["levels"]),
            "display_places": 2,
            "source_references": [
                {
                    "standard_number": NUMBER,
                    "source_file": source_file,
                    "source_sha256": source_sha,
                    "page": 3,
                    "clause": "第1章",
                    "table": "适用范围",
                    "note": "适用于中碱或无碱玻璃球、池窑法或坩埚法生产E/ECR和中碱玻璃纤维；不适用于特种玻璃纤维。",
                },
                {
                    "standard_number": NUMBER,
                    "source_file": source_file,
                    "source_sha256": source_sha,
                    "page": 4,
                    "clause": "4.1～4.3",
                    "table": "表1、表2、表3",
                    "note": "1级=先进值，2级=准入值，3级=现有限定值；表2未列的产品保留2级缺级。",
                },
                *[
                    {
                        "standard_number": NUMBER,
                        "source_file": source_file,
                        "source_sha256": source_sha,
                        "page": ref["page"],
                        "clause": ref["clause"],
                        "table": ref["table"],
                        "note": "综合能耗按输入能源折标量减向外输出能源折标量，再除以合格产品折算产量。",
                    }
                    for ref in formula_refs
                ],
            ],
            "notes": [
                "candidate_from_original_pdf",
                "not_for_formal_evaluation",
                "requires_independent_review",
                "product_indicator_split_confirmed",
                "standard_scope_excludes_special_glass_fibers",
                row["description"],
                "detail_energy_lines_are_scoped_to_the_selected_product",
                *(["缺级：表2未列该产品的2级准入值，level_2保留为None，不得补值。"] if row["levels"][1] is None else []),
            ],
        }
        products.append(
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "input_definitions": [],
                "indicators": [indicator],
            }
        )
    data["publication_status"] = "draft"
    data["products"] = products
    StandardDefinition.model_validate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 29450-2012草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-63/data"))
    args = parser.parse_args()
    print(f"已精化GB 29450-2012草案规则：{refine(args.data_dir.resolve())}")


if __name__ == "__main__":
    main()