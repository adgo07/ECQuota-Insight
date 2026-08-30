from __future__ import annotations

"""Build an auditable draft model for GB 29435-2012.

The rule stays draft until the 31 product rows and the energy-allocation input
categories are independently confirmed against the source standard.
"""

import argparse
import json
from pathlib import Path

from uebench.domain.models import StandardDefinition

NUMBER = "GB 29435-2012"


def node(op: str, *, value: str | None = None, input_key: str | None = None,
         args: list[dict] | None = None, unit: str | None = None,
         label: str | None = None) -> dict:
    return {
        "op": op, "value": value, "input_key": input_key, "args": args or [],
        "cases": [], "rows": [], "default": None, "label": label,
        "unit": unit, "round_places": None,
    }


def inp(key: str, unit: str | None = None, label: str | None = None) -> dict:
    return node("input", input_key=key, unit=unit, label=label)


def const(value: str, unit: str | None = None) -> dict:
    return node("constant", value=value, unit=unit)


def add(*args: dict, unit: str | None = None, label: str | None = None) -> dict:
    return node("add", args=list(args), unit=unit, label=label)


def div(left: dict, right: dict, unit: str | None = None, label: str | None = None) -> dict:
    return node("divide", args=[left, right], unit=unit, label=label)


def input_definition(key: str, label: str, unit: str, *, modes: list[str], minimum: str | None = None) -> dict:
    return {
        "key": key, "label": label, "data_type": "decimal", "unit": unit,
        "required": True, "required_if": None, "modes": modes,
        "minimum": minimum, "maximum": None, "choices": [],
        "description": "按GB 29435-2012第5.1、5.2节录入；尚未确认前仅作草案。",
    }


def refine(data_dir: Path) -> Path:
    path = data_dir / "definitions" / "gb-29435-2012.json"
    definition = json.loads(path.read_text(encoding="utf-8"))
    if definition.get("number") != NUMBER:
        raise ValueError(f"规则文件标准号不符：{definition.get('number')}")
    source_file = definition["source_file"]
    source_sha = definition["source_sha256"]
    refs = [
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 4, "clause": "4.1～4.2", "table": "表1、表2",
         "note": "现有企业限定值和新建企业准入值；分别作为3级和2级基础限额。"},
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 5, "clause": "4.3", "table": "表3",
         "note": "先进值作为1级基础限额。"},
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 6, "clause": "5.1.1～5.1.7", "table": "式（1）",
         "note": "企业生产能耗统计范围、外销/生活/建设能耗扣除、余热和分摊原则。"},
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 7, "clause": "5.2.1～5.2.3", "table": "式（2）～（4）",
         "note": "工序实物单耗、能源单耗和综合能源单耗计算方法。"},
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 8, "clause": "5.3.1～5.3.8", "table": "计算范围",
         "note": "各类稀土产品的工艺计算范围和适用生产方法。"},
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 10, "clause": "附录A", "table": "表A.1",
         "note": "常用能源折标准煤参考系数。"},
        {"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
         "page": 11, "clause": "附录B", "table": "表B.1",
         "note": "耗能工质能源等价值参考值。"},
    ]
    products = []
    for original_product in definition.get("products", []):
        product_name = original_product["name"]
        original_indicator = original_product["indicators"][0]
        direct_key = f"actual.GB_29435_2012.{original_product['id']}.comprehensive_energy"
        direct_def = input_definition(direct_key, f"{product_name}单位产品综合能耗实际值", "tce/t", modes=["DIRECT"], minimum="0")
        production = inp("production.total_equivalent", "t", "合格产品产量 P_z")
        direct_energy = inp("energy.category.direct_process.net_standard_coal", "tce", "工序直接综合能耗 E_H（折标准煤）")
        indirect_energy = inp("energy.category.indirect_aux_loss.net_standard_coal", "tce", "间接辅助能耗及损耗分摊量")
        direct_unit = div(direct_energy, production, unit="tce/t", label="工序能源单耗 E_I（公式3）")
        indirect_unit = div(indirect_energy, production, unit="tce/t", label="间接辅助能耗单耗 E_F")
        detail_formula = add(direct_unit, indirect_unit, unit="tce/t", label=f"{product_name}综合能源单耗 E_Z（公式4）")
        indicator = {
            "id": original_indicator["id"],
            "name": "单位产品综合能耗",
            "unit": "tce/t",
            "comparison": "lte",
            "input_definitions": [direct_def],
            "applicability": {"op": "always"},
            "direct_input_key": direct_key,
            "detail_formula": detail_formula,
            "base_thresholds": {f"level_{i}": const(v, "tce/t") for i, v in enumerate((original_indicator["base_thresholds"][f"level_{i}"]["value"] for i in (1, 2, 3)), 1)},
            "thresholds": {f"level_{i}": const(v, "tce/t") for i, v in enumerate((original_indicator["thresholds"][f"level_{i}"]["value"] for i in (1, 2, 3)), 1)},
            "display_places": 2,
            "source_references": refs,
            "notes": [
                "candidate_from_original_pdf", "not_for_formal_evaluation", "requires_independent_review",
                "等级映射：先进值=1级，新建准入值=2级，现有企业限定值=3级。",
                "明细模式按公式（3）和（4）计算：直接工序能耗与间接辅助/损耗分摊量分别除以合格产品产量后相加。",
                "能源明细应把外销能源、生活用能、工程建设用能排除；同一生产线多产品无法分别计量时，按原文5.1.7的稀土金属含量比例分摊。",
                "本草案将direct_process和indirect_aux_loss作为录入分类；分类边界和余热抵扣方式需独立复核。",
            ],
        }
        products.append({
            "id": original_product["id"], "name": product_name,
            "description": f"{product_name}；按原文第5.3节对应工艺范围统计。现有企业按3级限定值，新建企业按2级准入值。",
            "input_definitions": [], "indicators": [indicator],
        })
    definition["products"] = products
    definition["publication_status"] = "draft"
    StandardDefinition.model_validate(definition)
    path.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 29435-2012草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-63/data"))
    args = parser.parse_args()
    path = refine(args.data_dir.resolve())
    print(f"已精化 {NUMBER} 草案规则：{path}")


if __name__ == "__main__":
    main()
