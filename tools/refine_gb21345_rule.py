from __future__ import annotations

"""Replace the generic GB 21345 candidate with an auditable rule model.

The definition stays ``draft``.  This tool only records the product, inputs and
formula that were independently transcribed from GB 21345-2024; the separate
confirmation workbook remains the publication gate.
"""

import argparse
import json
from pathlib import Path

from uebench.domain.models import StandardDefinition


NUMBER = "GB 21345-2024"


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


def sub(left: dict, right: dict, unit: str | None = None, label: str | None = None) -> dict:
    return node("subtract", args=[left, right], unit=unit, label=label)


def mul(*args: dict, unit: str | None = None, label: str | None = None) -> dict:
    return node("multiply", args=list(args), unit=unit, label=label)


def div(left: dict, right: dict, unit: str | None = None, label: str | None = None) -> dict:
    return node("divide", args=[left, right], unit=unit, label=label)


def negate(expression: dict, unit: str | None = None, label: str | None = None) -> dict:
    return node("negate", args=[expression], unit=unit, label=label)


def input_definition(key: str, label: str, unit: str, *, minimum: str | None = None,
                     maximum: str | None = None) -> dict:
    return {
        "key": key, "label": label, "data_type": "decimal", "unit": unit,
        "required": True, "required_if": None, "modes": ["DETAIL"],
        "minimum": minimum, "maximum": maximum, "choices": [],
        "description": "按GB 21345-2024第6.2.2节录入；仅明细模式使用。",
    }


def refine(data_dir: Path) -> Path:
    path = data_dir / "definitions" / "gb-21345-2024.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    if original.get("number") != NUMBER:
        raise ValueError(f"规则文件标准号不符：{original.get('number')}")
    source_reference = {
        "standard_number": NUMBER,
        "source_file": original["source_file"],
        "source_sha256": original["source_sha256"],
        "page": 6,
        "clause": "第4章、5.1、5.2",
        "table": "表1",
        "note": "表1等级限额；原文第6.2.2节的统计范围和计算公式另见同一标准第7～9页。",
    }
    formula_reference = {
        "standard_number": NUMBER,
        "source_file": original["source_file"],
        "source_sha256": original["source_sha256"],
        "page": 8,
        "clause": "6.2.2.4～6.2.2.8",
        "table": "公式（4）～（8）",
        "note": "按原文公式建模；能源分类键和产量分类键写入输入说明，不改变原文口径。",
    }
    formula_reference_2 = {
        "standard_number": NUMBER,
        "source_file": original["source_file"],
        "source_sha256": original["source_sha256"],
        "page": 9,
        "clause": "6.2.2.9～6.2.2.10",
        "table": "公式（9）～（10）",
        "note": "泥磷制磷酸和其他化学品折合黄磷量在明细模式中由输入变量计算。",
    }

    carbon = inp("energy.category.carbon_reducing.net_standard_coal", "kgce", "炭质还原剂综合能耗 EPT")
    furnace_electricity = inp("energy.category.furnace_electricity.net_amount", "kWh", "电炉加热电量 QL")
    other_production = inp("energy.category.production_other.net_standard_coal", "kgce", "生产系统其他能源 EPE")
    auxiliary = inp("energy.category.auxiliary_affiliated.net_standard_coal", "kgce", "辅助及附属系统摊入能耗 EPFF")
    exported = inp("energy.category.external_output.net_standard_coal", "kgce", "界区外输出能源（明细方向为output）")
    n1 = inp("yellow_phosphorus.feedstock.p2o5_pct", "%", "配合炉料P2O5加权平均质量分数 N1")
    n2 = inp("yellow_phosphorus.feedstock.fe2o3_pct", "%", "配合炉料Fe2O3加权平均质量分数 N2")
    n3 = inp("yellow_phosphorus.feedstock.co2_pct", "%", "配合炉料CO2加权平均质量分数 N3")
    ppz = inp("yellow_phosphorus.product.qualified_t", "t", "符合GB/T 7816的黄磷量 PPZ")
    ns = inp("yellow_phosphorus.product.phosphoric_acid_mass_fraction", "fraction", "泥磷制得磷酸质量分数 NS（按0~1小数输入）")
    ps = inp("yellow_phosphorus.product.phosphoric_acid_production_t", "t", "泥磷制得磷酸产量 PS")
    ppw_ps = inp("yellow_phosphorus.product.phosphoric_acid_external_yellow_phosphorus_t", "t", "泥磷制磷酸外加/外购折合黄磷量 PPW")
    nh = inp("yellow_phosphorus.product.other_chemical_phosphorus_fraction", "fraction", "其他化学品中磷质量分数 NH（按0~1小数输入）")
    ph = inp("yellow_phosphorus.product.other_chemical_production_t", "t", "泥磷制得其他化学品产量 PH")
    ppw_ph = inp("yellow_phosphorus.product.other_chemical_external_yellow_phosphorus_t", "t", "制备其他化学品外加/外购折合黄磷量 PPW")
    ppwn = inp("yellow_phosphorus.product.external_mud_recovered_t", "t", "外购泥磷回收量 PPWN")

    # EPL = {QL - [170000/(N1-0.5) + (7750/(N1-8)-76)×N2
    #        + (3200/(N1-3.5)+8)×N3 - 7234]×PP}×0.1229
    pps = sub(
        mul(const("0.3163"), ns, ps, unit="t", label="泥磷制磷酸折合黄磷量 PPS（公式9）"),
        ppw_ps, unit="t", label="泥磷制磷酸折合黄磷量 PPS（公式9）",
    )
    pph = sub(
        mul(nh, ph, unit="t", label="泥磷制其他化学品折合黄磷量 PPH（公式10）"),
        ppw_ph, unit="t", label="泥磷制其他化学品折合黄磷量 PPH（公式10）",
    )
    pp = sub(add(ppz, pps, pph, unit="t", label="黄磷产品产量 PP（公式8）"), ppwn, unit="t", label="黄磷产品产量 PP（公式8）")
    correction = sub(
        add(
            div(const("170000"), sub(n1, const("0.5"), unit="%"), unit="kWh/t"),
            mul(
                sub(div(const("7750"), sub(n1, const("8"), unit="%"), unit="kWh/t"), const("76"), unit="kWh/t"),
                n2, unit="kWh/t",
            ),
            mul(
                add(div(const("3200"), sub(n1, const("3.5"), unit="%"), unit="kWh/t"), const("8"), unit="kWh/t"),
                n3, unit="kWh/t",
            ),
            unit="kWh/t",
        ),
        const("7234"),
        unit="kWh/t",
        label="电炉基准电量修正项",
    )
    epl = mul(
        sub(furnace_electricity, mul(correction, pp, unit="kWh", label="电炉修正电量"), unit="kWh", label="电炉电量差额"),
        const("0.1229"), unit="kgce", label="黄磷产品电炉电耗 EPL",
    )
    eps = add(carbon, epl, other_production, unit="kgce", label="黄磷生产系统综合能耗 EPS")
    total = sub(add(eps, auxiliary, unit="kgce", label="生产及辅助附属能耗"), negate(exported, unit="kgce", label="界区外输出能源 EPW"), unit="kgce", label="净综合能耗")
    detail_formula = div(total, pp, unit="kgce/t", label="黄磷单位产品综合能耗 EPZD（公式1）")

    definitions = [
        {
            "key": "actual.GB_21345_2024.electric_furnace_comprehensive_energy",
            "label": "电炉法黄磷单位产品综合能耗实际值",
            "data_type": "decimal",
            "unit": "kgce/t",
            "required": True,
            "required_if": None,
            "modes": ["DIRECT"],
            "minimum": "0",
            "maximum": None,
            "choices": [],
            "description": "直接录入已按GB 21345-2024核算的单位产品综合能耗。",
        },
        input_definition("yellow_phosphorus.feedstock.p2o5_pct", "配合炉料P2O5加权平均质量分数 N1", "%", minimum="0"),
        input_definition("yellow_phosphorus.feedstock.fe2o3_pct", "配合炉料Fe2O3加权平均质量分数 N2", "%", minimum="0"),
        input_definition("yellow_phosphorus.feedstock.co2_pct", "配合炉料CO2加权平均质量分数 N3", "%", minimum="0"),
        input_definition("yellow_phosphorus.product.qualified_t", "符合GB/T 7816的黄磷量 PPZ", "t", minimum="0"),
        input_definition("yellow_phosphorus.product.phosphoric_acid_mass_fraction", "泥磷制得磷酸质量分数 NS（按0~1小数输入）", "fraction", minimum="0", maximum="1"),
        input_definition("yellow_phosphorus.product.phosphoric_acid_production_t", "泥磷制得磷酸产量 PS", "t", minimum="0"),
        input_definition("yellow_phosphorus.product.phosphoric_acid_external_yellow_phosphorus_t", "泥磷制磷酸外加/外购折合黄磷量 PPW", "t", minimum="0"),
        input_definition("yellow_phosphorus.product.other_chemical_phosphorus_fraction", "其他化学品中磷质量分数 NH（按0~1小数输入）", "fraction", minimum="0", maximum="1"),
        input_definition("yellow_phosphorus.product.other_chemical_production_t", "泥磷制得其他化学品产量 PH", "t", minimum="0"),
        input_definition("yellow_phosphorus.product.other_chemical_external_yellow_phosphorus_t", "制备其他化学品外加/外购折合黄磷量 PPW", "t", minimum="0"),
        input_definition("yellow_phosphorus.product.external_mud_recovered_t", "外购泥磷回收量 PPWN", "t", minimum="0"),
    ]
    indicator = {
        "id": f"{NUMBER.replace(' ', '_')}.electric-furnace.comprehensive-energy",
        "name": "单位产品综合能耗",
        "unit": "kgce/t",
        "comparison": "lte",
        "input_definitions": definitions,
        "applicability": {"op": "always"},
        "direct_input_key": "actual.GB_21345_2024.electric_furnace_comprehensive_energy",
        "detail_formula": detail_formula,
        "base_thresholds": {f"level_{i}": const(value, "kgce/t") for i, value in enumerate(("2300", "2450", "2800"), 1)},
        "thresholds": {f"level_{i}": const(value, "kgce/t") for i, value in enumerate(("2300", "2450", "2800"), 1)},
        "display_places": 2,
        "source_references": [source_reference, formula_reference, formula_reference_2],
        "notes": [
            "candidate_from_original_pdf",
            "not_for_formal_evaluation",
            "requires_independent_review",
            "detail_energy_category_keys: carbon_reducing, furnace_electricity, production_other, auxiliary_affiliated, external_output",
            "EPW使用external_output分类且明细方向必须为output；引擎将其记录为负值，公式再取相反数。",
            "EPT能源明细折标系数应按各炭质还原剂固定碳质量分数×1000×1.1564录入，单位kgce/t。",
            "公式9、10的NS、NH按质量分数小数（0~1）录入；确认表中需核对企业原始数据是否采用同一口径。",
        ],
    }
    original["products"] = [{
        "id": "electric-furnace-yellow-phosphorus",
        "name": "电炉法黄磷",
        "description": "适用于电炉法黄磷生产；明细模式按原文第6.2.2节计算。",
        "input_definitions": [],
        "indicators": [indicator],
    }]
    original["publication_status"] = "draft"
    original["supersedes"] = ["GB 21345-2015"]
    StandardDefinition.model_validate(original)
    path.write_text(json.dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 21345-2024草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-63/data"))
    args = parser.parse_args()
    path = refine(args.data_dir.resolve())
    print(f"已精化 {NUMBER} 草案规则：{path}")


if __name__ == "__main__":
    main()
