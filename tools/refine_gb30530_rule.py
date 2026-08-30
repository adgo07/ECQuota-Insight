from __future__ import annotations

"""Build an auditable draft definition for GB 30530-2024."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from uebench.domain.models import StandardDefinition

NUMBER = "GB 30530-2024"
TITLE = "二甲基硅氧烷单位产品能源消耗限额"
SOURCE_DIR = Path(r"G:\标准  规范\02_能耗限额_终端产品\单位产品限额\现行强制文本")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def node(
    op: str,
    *,
    value: str | None = None,
    input_key: str | None = None,
    args: list[dict[str, Any]] | None = None,
    unit: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    return {
        "op": op,
        "value": value,
        "input_key": input_key,
        "args": args or [],
        "cases": [],
        "rows": [],
        "default": None,
        "label": label,
        "unit": unit,
        "round_places": None,
    }


def inp(key: str, unit: str, label: str) -> dict[str, Any]:
    return node("input", input_key=key, unit=unit, label=label)


def const(value: str, unit: str, label: str) -> dict[str, Any]:
    return node("constant", value=value, unit=unit, label=label)


def add(*args: dict[str, Any], unit: str, label: str) -> dict[str, Any]:
    return node("add", args=list(args), unit=unit, label=label)


def multiply(*args: dict[str, Any], unit: str, label: str) -> dict[str, Any]:
    return node("multiply", args=list(args), unit=unit, label=label)


def per_unit(total: dict[str, Any], production: dict[str, Any], unit: str, label: str) -> dict[str, Any]:
    return node("per_unit", args=[total, production], unit=unit, label=label)


def detail_input(key: str, label: str, unit: str, description: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "data_type": "decimal",
        "unit": unit,
        "required": True,
        "required_if": None,
        "modes": ["DETAIL"],
        "minimum": "0",
        "maximum": None,
        "choices": [],
        "description": description,
    }


def direct_input(key: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": "二甲基硅氧烷单位产品能耗实际值",
        "data_type": "decimal",
        "unit": "kgce/t",
        "required": True,
        "required_if": None,
        "modes": ["DIRECT"],
        "minimum": "0",
        "maximum": None,
        "choices": [],
        "description": "按GB 30530-2024第6章计算的单位产品能耗；当前规则尚未完成确认。",
    }


def references(source_file: str, source_sha: str) -> list[dict[str, Any]]:
    rows = [
        (5, "第1章；3.1～3.6", "范围与术语", "适用于二甲基硅氧烷单位产品能耗计算、考核及新改扩建项目控制。"),
        (6, "第4章", "表1", "二甲基硅氧烷单位产品能耗1级、2级、3级限额分别为650、750、1000kgce/t。"),
        (6, "第5章5.1～5.2", "技术要求", "现有企业执行3级限定值；新（扩、改）建企业执行2级准入值。"),
        (6, "6.1.1～6.1.5", "统计范围", "生产、辅助、附属系统计入；基建、技改、回收利用及向外输出的能源量不计入。"),
        (7, "6.2.1", "折标方法", "燃料按GB/T2589收到基低位发热量折标准煤；实测或供应数据优先，无法取得时参考附录。"),
        (7, "6.2.2；公式（1）", "产品综合能耗", "生产系统、辅助/附属系统能源折标量与外购硅粉、氯甲烷原材料能耗之和。"),
        (7, "6.2.3；公式（2）", "产品产量", "合格水解物、环体、线性体产量，加外售二甲基二氯硅烷按μ折算的产量；水解物不得重复计入。"),
        (8, "6.2.4；公式（3）", "单位产品能耗", "e=E/M，单位为kgce/t。"),
        (9, "附录A", "各种能源折算系数", "柴油、天然气、电力、热力等折标准煤参考系数。"),
        (10, "附录B", "耗能工质折算系数", "新水、软化水、压缩空气、氮气等耗能工质参考系数。"),
    ]
    return [
        {
            "standard_number": NUMBER,
            "source_file": source_file,
            "source_sha256": source_sha,
            "page": page,
            "clause": clause,
            "table": table,
            "note": note,
        }
        for page, clause, table, note in rows
    ]


def energy_formula() -> dict[str, Any]:
    production = inp(
        "energy.category.production_system.net_standard_coal",
        "kgce",
        "生产系统能源折标准煤量",
    )
    auxiliary = inp(
        "energy.category.auxiliary_system.net_standard_coal",
        "kgce",
        "辅助生产系统能源折标准煤量",
    )
    affiliated = inp(
        "energy.category.affiliated_system.net_standard_coal",
        "kgce",
        "附属生产系统能源折标准煤量",
    )
    silicon = multiply(
        inp("raw_material.silicon_powder.quantity", "t", "外购硅粉量 g₁"),
        inp("raw_material.silicon_powder.unit_energy", "kgce/t", "硅粉单位能源消耗 q₁"),
        unit="kgce",
        label="外购硅粉能耗 g₁×q₁",
    )
    chloromethane = multiply(
        inp("raw_material.chloromethane.quantity", "t", "外购氯甲烷量 g₂"),
        inp("raw_material.chloromethane.unit_energy", "kgce/t", "氯甲烷单位能源消耗 q₂"),
        unit="kgce",
        label="外购氯甲烷能耗 g₂×q₂",
    )
    total = add(
        production,
        auxiliary,
        affiliated,
        silicon,
        chloromethane,
        unit="kgce",
        label="二甲基硅氧烷产品综合能耗 E（公式1）",
    )
    return per_unit(
        total,
        inp("production.total_equivalent", "t", "二甲基硅氧烷产品产量 M（公式2）"),
        "kgce/t",
        "二甲基硅氧烷单位产品能耗 e（公式3）",
    )


def make_product(source_file: str, source_sha: str) -> dict[str, Any]:
    product_id = "dimethylsiloxane"
    actual_key = "actual.GB_30530-2024.dimethylsiloxane.energy"
    indicator = {
        "id": "GB_30530-2024.dimethylsiloxane.energy-per-product",
        "name": "单位产品能耗",
        "unit": "kgce/t",
        "comparison": "lte",
        "input_definitions": [direct_input(actual_key)],
        "applicability": {"op": "always"},
        "direct_input_key": actual_key,
        "detail_formula": energy_formula(),
        "base_thresholds": {
            "level_1": const("650", "kgce/t", "1级限额"),
            "level_2": const("750", "kgce/t", "2级限额"),
            "level_3": const("1000", "kgce/t", "3级限额"),
        },
        "thresholds": {
            "level_1": const("650", "kgce/t", "1级限额"),
            "level_2": const("750", "kgce/t", "2级限额"),
            "level_3": const("1000", "kgce/t", "3级限额"),
        },
        "display_places": 2,
        "source_references": references(source_file, source_sha),
        "notes": [
            "candidate_from_original_pdf",
            "not_for_formal_evaluation",
            "requires_independent_review",
            "产品/工序名称为“二甲基硅氧烷”，指标名称按原文术语为“单位产品能耗”；两者合并为完整指标表述。",
            "1级、2级、3级比较方向为实际值不大于限额；1级能耗最低。",
            "现有企业执行3级限定值；新（扩、改）建企业执行2级准入值。",
            "明细模式能源明细按生产、辅助、附属系统分类；基建、技改、回收利用和向外输出的能源不计入。",
            "外购硅粉和氯甲烷的数量及单位能源消耗必须单独填写；无实际监测时可按原文参考值硅粉0.0275tce/t、氯甲烷0.0797tce/t换算为27.5kgce/t和79.7kgce/t。",
            "产量明细应分别填写合格水解物、环体、线性体和外售二甲基二氯硅烷；外售二甲基二氯硅烷行的折算系数μ按当期监测值填写，无当期数据时可取0.56。用于生产环体或线性体的水解物不得重复计入。",
            "每条能源明细须携带实测或供应数据、GB/T2589或附录A/B的折标依据；软件保留逐步计算轨迹。",
        ],
    }
    return {
        "id": product_id,
        "name": "二甲基硅氧烷",
        "description": "二甲基硅氧烷（包括水解物、环体和线性体）；按GB 30530-2024表1和第6章统计、计算。",
        "input_definitions": [
            detail_input(
                "raw_material.silicon_powder.quantity",
                "外购硅粉量",
                "t",
                "外购硅粉作为有机硅单体生产原料时填写；非外购或没有该项时填0并在备注说明。",
            ),
            detail_input(
                "raw_material.silicon_powder.unit_energy",
                "硅粉单位能源消耗",
                "kgce/t",
                "按企业当期生产硅粉单位能源消耗填写；无实际监测时按原文参考0.0275tce/t，即27.5kgce/t。",
            ),
            detail_input(
                "raw_material.chloromethane.quantity",
                "外购氯甲烷量",
                "t",
                "外购氯甲烷作为有机硅单体生产原料时填写；非外购或没有该项时填0并在备注说明。",
            ),
            detail_input(
                "raw_material.chloromethane.unit_energy",
                "氯甲烷单位能源消耗",
                "kgce/t",
                "按企业当期生产氯甲烷单位能源消耗填写；无实际监测时按原文参考0.0797tce/t，即79.7kgce/t。",
            ),
        ],
        "indicators": [indicator],
    }


def build(source_file: str, source_sha: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "id": "gb-30530-2024",
        "number": NUMBER,
        "title": TITLE,
        "version": "2024",
        "publication_status": "draft",
        "publication_date": "2024-04-29",
        "effective_date": "2025-05-01",
        "source_file": source_file,
        "source_sha256": source_sha,
        "products": [make_product(source_file, source_sha)],
        "corrections": ["GB 30530-2024替代GB 30530-2014；按现行强制文本重新精化产品、原材料能耗和产量折算规则。"],
        "lifecycle_status": "active",
        "obsolete_date": None,
        "replaced_by": [],
        "supersedes": ["GB 30530-2014"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-63/data"))
    parser.add_argument("--source", type=Path, default=None)
    args = parser.parse_args()
    source = args.source.resolve() if args.source else next(
        p for p in SOURCE_DIR.iterdir() if p.is_file() and "30530-2024" in p.name
    )
    definition = build(source.name, sha256(source))
    StandardDefinition.model_validate(definition)
    target = args.data_dir.resolve() / "definitions" / "gb-30530-2024.json"
    target.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已生成GB 30530-2024草案：" + str(target))
    print("产品/工序数=" + str(len(definition["products"])) + "，指标数=" + str(sum(len(p["indicators"]) for p in definition["products"])))
    print("source_sha256=" + definition["source_sha256"])


if __name__ == "__main__":
    main()
