from __future__ import annotations

"""Build an auditable draft rule model for GB 29145-2023.

The definition remains ``draft`` until the user confirms every row and the
Appendix C lookup interpretation.  No interpolation is guessed for ore ratios
that are not explicitly present in the normative table.
"""

import argparse
import json
from pathlib import Path

from uebench.domain.models import StandardDefinition

NUMBER = "GB 29145-2023"


def node(op: str, *, value: str | None = None, input_key: str | None = None,
         args: list[dict] | None = None, cases: list[dict] | None = None,
         rows: list[dict] | None = None, default: dict | None = None,
         unit: str | None = None, label: str | None = None) -> dict:
    return {
        "op": op,
        "value": value,
        "input_key": input_key,
        "args": args or [],
        "cases": cases or [],
        "rows": rows or [],
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


def sub(left: dict, right: dict, unit: str | None = None, label: str | None = None) -> dict:
    return node("subtract", args=[left, right], unit=unit, label=label)


def mul(*args: dict, unit: str | None = None, label: str | None = None) -> dict:
    return node("multiply", args=list(args), unit=unit, label=label)


def div(left: dict, right: dict, unit: str | None = None, label: str | None = None) -> dict:
    return node("divide", args=[left, right], unit=unit, label=label)


def negate(expression: dict, unit: str | None = None, label: str | None = None) -> dict:
    return node("negate", args=[expression], unit=unit, label=label)


def input_definition(key: str, label: str, unit: str, *, modes: list[str], minimum: str | None = None, maximum: str | None = None) -> dict:
    return {
        "key": key,
        "label": label,
        "data_type": "decimal",
        "unit": unit,
        "required": True,
        "required_if": None,
        "modes": modes,
        "minimum": minimum,
        "maximum": maximum,
        "choices": [],
        "description": "按GB 29145-2023第6.2节及附录C录入；尚未确认前仅作草案。",
    }


def lookup_mu(key: str, table: str, rows: list[tuple[str, str]]) -> dict:
    return node(
        "lookup",
        rows=[{
            "condition": {"op": "eq", "field": key, "value": k},
            "expression": const(v, "1"),
            "label": f"{table}：K={k}，μ={v}",
        } for k, v in rows],
        unit="1",
        label="原矿品位折算系数 μ（附录C查表）",
    )


def energy_formula(product_name: str, *, comparable: bool, ore_key: str | None, mu_rows: list[tuple[str, str]] | None) -> dict:
    production = inp("energy.category.production_system.net_standard_coal", "kgce", "生产系统能耗（折标准煤）")
    auxiliary = inp("energy.category.auxiliary_system.net_standard_coal", "kgce", "辅助生产系统能耗（折标准煤）")
    affiliated = inp("energy.category.affiliated_system.net_standard_coal", "kgce", "附属生产系统能耗（折标准煤）")
    exported = inp("energy.category.external_output.net_standard_coal", "kgce", "二次能源回收并外供量（明细方向为output）")
    total = sub(
        add(production, auxiliary, affiliated, unit="kgce", label="生产、辅助、附属系统能耗合计"),
        negate(exported, unit="kgce", label="二次能源回收并外供量 E_HW"),
        unit="kgce",
        label="综合能耗分子（公式1）",
    )
    raw = div(
        total,
        inp("production.total_equivalent", "t", "合格产品实物产量 P"),
        unit="kgce/t",
        label=f"{product_name}单位产品能耗 e（公式1）",
    )
    if not comparable:
        return raw
    assert ore_key is not None and mu_rows is not None
    return div(
        raw,
        lookup_mu(ore_key, "附录C", mu_rows),
        unit="kgce/t",
        label=f"{product_name}单位产品可比能耗 e_KB（公式2）",
    )


def refine(data_dir: Path) -> Path:
    path = data_dir / "definitions" / "gb-29145-2023.json"
    definition = json.loads(path.read_text(encoding="utf-8"))
    if definition.get("number") != NUMBER:
        raise ValueError(f"规则文件标准号不符：{definition.get('number')}")
    source_file = definition["source_file"]
    source_sha = definition["source_sha256"]
    refs = [
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 4, "clause": "第4章4.1～4.3", "table": "表1～表3",
         "note": "三级基础限额；1级能耗最低。"},
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 6, "clause": "6.1", "table": "6.1.1～6.1.5",
         "note": "生产、辅助、附属系统统计范围、产量口径和折标系数取值原则。"},
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 6, "clause": "6.2", "table": "公式（1）",
         "note": "单位产品能耗 e 的计算。"},
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 7, "clause": "6.2", "table": "公式（2）",
         "note": "钨精矿、钼精矿单位产品可比能耗 e_KB=e/μ。"},
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 10, "clause": "附录C", "table": "表C.1～表C.2",
         "note": "原矿品位折算系数μ按选矿比K查表；标准未给出表内值之间的插值规则。"},
    ]
    configs = [
        {
            "id": "tungsten-black", "name": "钨精矿—黑钨", "indicator": "单位产品可比能耗",
            "thresholds": ("550", "1150", "1450"), "ore_key": "gb29145.tungsten.ore_ratio",
            "mu_rows": [("250", "0.89"), ("280", "1.00"), ("310", "1.11"), ("340", "1.21"), ("370", "1.32"), ("400", "1.43"), ("430", "1.54"), ("460", "1.64"), ("490", "1.75"), ("520", "1.86"), ("550", "1.96"), ("580", "2.07"), ("610", "2.18")],
            "range_note": "适用于地下开采钨精矿；不适用于露天开采钨精矿。按附录C表C.1查μ。",
        },
        {
            "id": "tungsten-white", "name": "钨精矿—白钨", "indicator": "单位产品可比能耗",
            "thresholds": ("1640", "1750", "2050"), "ore_key": "gb29145.tungsten.ore_ratio",
            "mu_rows": [("250", "0.89"), ("280", "1.00"), ("310", "1.11"), ("340", "1.21"), ("370", "1.32"), ("400", "1.43"), ("430", "1.54"), ("460", "1.64"), ("490", "1.75"), ("520", "1.86"), ("550", "1.96"), ("580", "2.07"), ("610", "2.18")],
            "range_note": "适用于地下开采钨精矿；不适用于露天开采钨精矿。按附录C表C.1查μ。",
        },
        {
            "id": "molybdenum-three-stage", "name": "钼精矿—三段一闭路", "indicator": "单位产品可比能耗",
            "thresholds": ("1250", "1390", "1475"), "ore_key": "gb29145.molybdenum.ore_ratio",
            "mu_rows": [("330", "0.78"), ("380", "0.88"), ("430", "1.00"), ("480", "1.12"), ("530", "1.23"), ("580", "1.35"), ("630", "1.47"), ("680", "1.58"), ("730", "1.70")],
            "range_note": "适用于露天开采钼精矿的三段一闭路工艺；不适用于地下开采钼精矿。按附录C表C.2查μ。",
        },
        {
            "id": "molybdenum-sabc", "name": "钼精矿—SABC", "indicator": "单位产品可比能耗",
            "thresholds": ("1900", "2060", "2150"), "ore_key": "gb29145.molybdenum.ore_ratio",
            "mu_rows": [("330", "0.78"), ("380", "0.88"), ("430", "1.00"), ("480", "1.12"), ("530", "1.23"), ("580", "1.35"), ("630", "1.47"), ("680", "1.58"), ("730", "1.70")],
            "range_note": "适用于露天开采钼精矿的SABC工艺；不适用于地下开采钼精矿。按附录C表C.2查μ。",
        },
        {
            "id": "roasted-molybdenum-multi-hearth", "name": "焙烧钼精矿—多膛炉", "indicator": "单位产品能耗",
            "thresholds": ("210", "230", "260"), "ore_key": None, "mu_rows": None,
            "range_note": "适用于多膛炉焙烧钼精矿；单位产品能耗不执行附录C可比系数修正。",
        },
        {
            "id": "roasted-molybdenum-kiln", "name": "焙烧钼精矿—内热式回转窑", "indicator": "单位产品能耗",
            "thresholds": ("170", "180", "200"), "ore_key": None, "mu_rows": None,
            "range_note": "适用于内热式回转窑焙烧钼精矿；单位产品能耗不执行附录C可比系数修正。",
        },
    ]
    products = []
    for config in configs:
        direct_key = f"actual.GB_29145_2023.{config['id']}.energy"
        definitions = [
            input_definition(direct_key, f"{config['name']}{config['indicator']}实际值", "kgce/t", modes=["DIRECT"], minimum="0"),
        ]
        if config["ore_key"]:
            definitions.append(input_definition(config["ore_key"], "选矿比 K（按附录C表内数值输入）", "ratio", modes=["DETAIL"], minimum="0"))
        detail = energy_formula(config["name"], comparable=bool(config["ore_key"]), ore_key=config["ore_key"], mu_rows=config["mu_rows"])
        indicator = {
            "id": f"GB_29145-2023.{config['id']}.energy",
            "name": config["indicator"],
            "unit": "kgce/t",
            "comparison": "lte",
            "input_definitions": definitions,
            "applicability": {"op": "always"},
            "direct_input_key": direct_key,
            "detail_formula": detail,
            "base_thresholds": {f"level_{i}": const(v, "kgce/t") for i, v in enumerate(config["thresholds"], 1)},
            "thresholds": {f"level_{i}": const(v, "kgce/t") for i, v in enumerate(config["thresholds"], 1)},
            "display_places": 2,
            "source_references": refs,
            "notes": [
                "candidate_from_original_pdf", "not_for_formal_evaluation", "requires_independent_review",
                config["range_note"],
                "公式（1）按生产系统+辅助系统+附属系统−二次能源外供量计算；明细方向为output时引擎使用负值并取相反数抵扣。",
                "焙烧钼精矿不执行公式（2）可比能耗修正。" if not config["ore_key"] else "选矿比不等于附录C表内值时暂返回不完整；未确认前禁止插值或猜测。",
            ],
        }
        products.append({
            "id": config["id"], "name": config["name"],
            "description": f"{config['range_note']}现有生产装置按3级限定值，新建、改建和扩建项目按2级准入值。",
            "input_definitions": [], "indicators": [indicator],
        })
    definition["products"] = products
    definition["publication_status"] = "draft"
    StandardDefinition.model_validate(definition)
    path.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 29145-2023草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-63/data"))
    args = parser.parse_args()
    path = refine(args.data_dir.resolve())
    print(f"已精化 {NUMBER} 草案规则：{path}")


if __name__ == "__main__":
    main()
