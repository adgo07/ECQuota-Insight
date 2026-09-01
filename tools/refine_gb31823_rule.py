from __future__ import annotations

"""Build an auditable draft definition for GB 31823-2021."""

import argparse
import hashlib
import os
import json
from pathlib import Path
from typing import Any

from uebench.domain.models import StandardDefinition

NUMBER = "GB 31823-2021"
TITLE = "码头作业单位产品能源消耗限额"
SOURCE_DIR = Path(os.environ.get("UEBENCH_SOURCE_DIR", r"G:\标准  规范\02_能耗限额_终端产品\单位产品限额\现行强制文本"))
SOURCE_FILE_HINT = "31823-2021"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def node(op: str, *, value: str | bool | None = None, input_key: str | None = None,
         args: list[dict[str, Any]] | None = None, cases: list[dict[str, Any]] | None = None,
         unit: str | None = None, label: str | None = None) -> dict[str, Any]:
    return {"op": op, "value": value, "input_key": input_key, "args": args or [],
            "cases": cases or [], "rows": [], "default": None, "label": label,
            "unit": unit, "round_places": None}


def const(value: str, unit: str | None, label: str) -> dict[str, Any]:
    return node("constant", value=value, unit=unit, label=label)


def inp(key: str, unit: str | None, label: str) -> dict[str, Any]:
    return node("input", input_key=key, unit=unit, label=label)


def add(*args: dict[str, Any], unit: str, label: str) -> dict[str, Any]:
    return node("add", args=list(args), unit=unit, label=label)


def multiply(*args: dict[str, Any], unit: str, label: str) -> dict[str, Any]:
    return node("multiply", args=list(args), unit=unit, label=label)


def divide(a: dict[str, Any], b: dict[str, Any], unit: str, label: str) -> dict[str, Any]:
    return node("divide", args=[a, b], unit=unit, label=label)


def per_unit(total: dict[str, Any], production: dict[str, Any], unit: str, label: str) -> dict[str, Any]:
    return node("per_unit", args=[total, production], unit=unit, label=label)


def condition(op: str = "always", *, field: str | None = None, value: str | bool | None = None,
              minimum: str | None = None, maximum: str | None = None,
              include_minimum: bool = True, include_maximum: bool = True,
              args: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"op": op, "field": field, "value": value, "values": [],
            "minimum": minimum, "maximum": maximum,
            "include_minimum": include_minimum, "include_maximum": include_maximum, "args": args or []}


def piecewise(cases: list[tuple[dict[str, Any], dict[str, Any], str]], *, unit: str, label: str) -> dict[str, Any]:
    return node("piecewise", cases=[{"condition": c, "expression": e, "label": l} for c, e, l in cases], unit=unit, label=label)


def detail_input(key: str, label: str, *, data_type: str = "decimal", unit: str | None = None,
                minimum: str | None = None, maximum: str | None = None,
                choices: list[str] | None = None, required_if: dict[str, Any] | None = None,
                description: str) -> dict[str, Any]:
    return {"key": key, "label": label, "data_type": data_type, "unit": unit,
            "required": True, "required_if": required_if, "modes": ["DETAIL"],
            "minimum": minimum, "maximum": maximum, "choices": choices or [],
            "description": description}


def direct_input(key: str, product_name: str, unit: str) -> dict[str, Any]:
    return {"key": key, "label": product_name + "单位产品可比综合能耗实际值",
            "data_type": "decimal", "unit": unit, "required": True,
            "required_if": None, "modes": ["DIRECT"], "minimum": "0", "maximum": None,
            "choices": [], "description": "按GB 31823-2021第6章和标准统计边界核算后录入单位产品可比综合能耗。"}


def energy_category(category_key: str, label: str) -> dict[str, Any]:
    return inp(f"energy.category.{category_key}.net_standard_coal", "kgce", label)


def kgce_to_tce(value: dict[str, Any], label: str) -> dict[str, Any]:
    return multiply(value, const("0.001", "tce/kgce", "kgce换算为tce"), unit="tce", label=label)


def common_energy_tce() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        kgce_to_tce(energy_category("production_system", "生产系统能耗（折标准煤）"), "生产系统能耗 Ez（kgce换算为tce）"),
        kgce_to_tce(energy_category("auxiliary_system", "辅助生产系统能耗（折标准煤）"), "辅助生产系统能耗 Ef（kgce换算为tce）"),
        kgce_to_tce(energy_category("affiliated_system", "附属生产系统能耗（折标准煤）"), "附属生产系统能耗 Ef（kgce换算为tce）"),
    )


def thresholds(values: tuple[str, str, str], unit: str) -> dict[str, dict[str, Any]]:
    return {f"level_{index}": const(value, unit, f"表1：{index}级") for index, value in enumerate(values, 1)}


def container_inputs() -> list[dict[str, Any]]:
    return [detail_input(
        "condition.GB31823.container.adaptation_degree", "集装箱码头吞吐量适应程度 L",
        unit="ratio", minimum="0",
        description="L=设计通过能力/统计期实际完成吞吐量；按原文分段选择码头吞吐量适应系数a。"
    )]


def container_adaptation_factor() -> dict[str, Any]:
    key = "condition.GB31823.container.adaptation_degree"
    return piecewise([
        (condition("range", field=key, minimum="0", maximum="2", include_minimum=False),
         const("1.0", "ratio", "0＜L≤2时a=1.0"), "0＜L≤2"),
        (condition("range", field=key, minimum="2", maximum="3", include_minimum=False),
         const("0.95", "ratio", "2＜L≤3时a=0.95"), "2＜L≤3"),
        (condition("range", field=key, minimum="3", maximum="4", include_minimum=False),
         const("0.9", "ratio", "3＜L≤4时a=0.9"), "3＜L≤4"),
        (condition("gt", field=key, value="4"),
         const("0.85", "ratio", "L＞4时a=0.85"), "L＞4"),
    ], unit="ratio", label="集装箱码头吞吐量适应系数a")


def container_formula() -> dict[str, Any]:
    production, auxiliary, affiliated = common_energy_tce()
    total = add(production, auxiliary, affiliated, unit="tce", label="Ez+Ef：码头总综合能耗")
    base = per_unit(total, inp("production.total_equivalent", "10^4TEU", "集装箱吞吐量 T"),
                    "tce/10^4TEU", "（Ez+Ef）/T：集装箱码头单位能耗基础值")
    return multiply(base, container_adaptation_factor(), unit="tce/10^4TEU",
                    label="eₖ=（Ez+Ef）/T×a（公式1）")


def dry_bulk_inputs() -> list[dict[str, Any]]:
    portal_key = "condition.GB31823.dry_bulk.portal_crane"
    return [
        detail_input(portal_key, "是否使用门座式起重机装卸", data_type="boolean",
                     description="门座式起重机装卸时，不适用卸货量修正系数g。"),
        detail_input("condition.GB31823.dry_bulk.direct_to_factory", "是否直接卸货至后方工厂",
                     data_type="boolean", required_if=condition("eq", field=portal_key, value=False),
                     description="仅在不使用门座式起重机时填写；直接卸货至后方工厂按原文取g=1.3。"),
        detail_input("condition.GB31823.dry_bulk.unloading_share", "卸货量占比 w", unit="fraction",
                     minimum="0", maximum="1", required_if=condition("all", args=[
                         condition("eq", field=portal_key, value=False),
                         condition("eq", field="condition.GB31823.dry_bulk.direct_to_factory", value=False),
                     ]),
                     description="仅在不使用门座式起重机且非直接卸货至后方工厂时用于计算g；按0～1录入。"),
        detail_input("condition.GB31823.dry_bulk.work_line_length", "装卸作业线长度 L", unit="m",
                     minimum="0", description="按原文分段选择装卸作业线长度修正系数k。"),
        detail_input("condition.GB31823.dry_bulk.heating_region", "所在地区是否采暖地区", data_type="text",
                     choices=["采暖地区", "非采暖地区"],
                     description="按GB 50189规定选择采暖修正系数c：采暖地区0.95，非采暖地区1.0。"),
    ]


def dry_unloading_factor() -> dict[str, Any]:
    portal_key = "condition.GB31823.dry_bulk.portal_crane"
    direct_key = "condition.GB31823.dry_bulk.direct_to_factory"
    share_key = "condition.GB31823.dry_bulk.unloading_share"
    w = inp(share_key, "fraction", "卸货量占比 w")
    return piecewise([
        (condition("eq", field=portal_key, value=True),
         const("1.0", "ratio", "门座式起重机装卸，不适用g修正，取g=1.0"), "门座式起重机装卸"),
        (condition("eq", field=direct_key, value=True),
         const("1.3", "ratio", "直接卸货至后方工厂，取g=1.3"), "直接卸货至后方工厂"),
        (condition("range", field=share_key, minimum="0.5", maximum="1"),
         divide(const("1", "ratio", "g分子"),
                add(multiply(const("1.4", "ratio", "1.4"), w, unit="ratio", label="1.4w"),
                    const("0.04", "ratio", "0.04"), unit="ratio", label="1.4w+0.04"),
                "ratio", "g=1/(1.4w+0.04)"), "50%≤w≤100%"),
        (condition("range", field=share_key, minimum="0", maximum="0.5", include_maximum=False),
         divide(const("1", "ratio", "g分子"),
                node("subtract", args=[const("1", "ratio", "1"),
                                       multiply(const("0.53", "ratio", "0.53"), w, unit="ratio", label="0.53w")],
                     unit="ratio", label="1−0.53w"),
                "ratio", "g=1/(1−0.53w)"), "0≤w＜50%"),
    ], unit="ratio", label="干散货码头卸货量修正系数g")


def dry_work_line_factor() -> dict[str, Any]:
    key = "condition.GB31823.dry_bulk.work_line_length"
    return piecewise([
        (condition("range", field=key, minimum="0", maximum="500"),
         const("1.1", "ratio", "L≤500m时k=1.1"), "L≤500m"),
        (condition("range", field=key, minimum="500", maximum="1000", include_minimum=False),
         const("1.05", "ratio", "500＜L≤1000m时k=1.05"), "500＜L≤1000m"),
        (condition("range", field=key, minimum="1000", maximum="1500", include_minimum=False),
         const("1.0", "ratio", "1000＜L≤1500m时k=1.0"), "1000＜L≤1500m"),
        (condition("range", field=key, minimum="1500", maximum="2000", include_minimum=False),
         const("0.95", "ratio", "1500＜L≤2000m时k=0.95"), "1500＜L≤2000m"),
        (condition("range", field=key, minimum="2000", maximum="3000", include_minimum=False),
         const("0.9", "ratio", "2000＜L≤3000m时k=0.9"), "2000＜L≤3000m"),
        (condition("gt", field=key, value="3000"),
         const("0.85", "ratio", "L＞3000m时k=0.85"), "L＞3000m"),
    ], unit="ratio", label="干散货码头装卸作业线长度修正系数k")


def dry_heating_factor() -> dict[str, Any]:
    key = "condition.GB31823.dry_bulk.heating_region"
    return piecewise([
        (condition("eq", field=key, value="采暖地区"),
         const("0.95", "ratio", "采暖地区c=0.95"), "采暖地区"),
        (condition("eq", field=key, value="非采暖地区"),
         const("1.0", "ratio", "非采暖地区c=1.0"), "非采暖地区"),
    ], unit="ratio", label="干散货码头采暖修正系数c")


def dry_bulk_formula() -> dict[str, Any]:
    production, auxiliary, affiliated = common_energy_tce()
    corrected_production = multiply(dry_unloading_factor(), dry_work_line_factor(), production,
                                    unit="tce", label="g×k×Ez：生产系统修正能耗")
    numerator = add(corrected_production, auxiliary, affiliated, unit="tce",
                    label="g×k×Ez+Ef（公式4）")
    base = per_unit(numerator, inp("production.total_equivalent", "10^4t", "干散货吞吐量 T"),
                    "tce/10^4t", "（g×k×Ez+Ef）/T（公式4）")
    return multiply(base, dry_heating_factor(), unit="tce/10^4t",
                    label="eₖ=（gkEz+Ef）/T×c（公式4）")


def crude_oil_inputs() -> list[dict[str, Any]]:
    return [detail_input(
        "condition.GB31823.crude_oil.pipeline_heat_temperature", "管道伴热温度条件（℃）",
        unit="℃",
        description="原文规定管道伴热温度修正系数βt：0℃条件取0.95，其他条件取1.0；正式发布前请对照原文边界确认。"
    )]


def crude_pipeline_heat_factor() -> dict[str, Any]:
    key = "condition.GB31823.crude_oil.pipeline_heat_temperature"
    return piecewise([
        (condition("lte", field=key, value="0"),
         const("0.95", "ratio", "温度≤0℃时βt=0.95"), "温度≤0℃"),
        (condition("gt", field=key, value="0"),
         const("1.0", "ratio", "温度＞0℃时βt=1.0"), "温度＞0℃"),
    ], unit="ratio", label="原油码头管道伴热温度修正系数βt")


def crude_oil_formula() -> dict[str, Any]:
    production, auxiliary, affiliated = common_energy_tce()
    pipeline = kgce_to_tce(energy_category("pipeline_heat", "管道伴热能耗（折标准煤）"),
                            "管道伴热能耗 Ebp（kgce换算为tce）")
    corrected_pipeline = multiply(crude_pipeline_heat_factor(), pipeline, unit="tce",
                                  label="βt×Ebp：管道伴热修正能耗")
    total = add(production, auxiliary, affiliated, corrected_pipeline, unit="tce",
                label="Ez+Ef+βt×Ebp（公式10）")
    return per_unit(total, inp("production.total_equivalent", "10^4t", "原油吞吐量 T"),
                    "tce/10^4t", "eₖ=（Ez+Ef）/T（公式8）")


def references(source_file: str, source_sha: str) -> list[dict[str, Any]]:
    rows = [
        (4, "第1章；第3章；第4章", "表1", "专业化集装箱、干散货（煤炭/矿石）和原油码头的范围、术语与三级限额。"),
        (4, "第5章5.1～5.2", "技术要求", "现有码头执行3级；新建、改建和扩建码头执行2级。"),
        (5, "6.1.1～6.1.3", "统计范围", "统计生产系统、辅助生产系统和附属生产系统；按标准边界核算。"),
        (5, "6.2.1.1～6.2.1.3", "公式（1）～（3）", "集装箱码头eₖ=(Ez+Ef)/T×a；Ez、Ef按能源实物量乘折标系数求和。"),
        (6, "6.2.2.1～6.2.2.2", "公式（4）～（5）", "干散货码头eₖ=(gkEz+Ef)/T×c；卸货量g、作业线长度k、采暖c修正。"),
        (7, "6.2.2.3～6.2.2.4", "公式（6）～（7）", "干散货码头生产系统和辅助/附属系统能耗求和及作业线长度修正分段。"),
        (8, "6.3.1～6.3.2.3", "公式（8）～（10）", "原油码头eₖ=(Ez+Ef)/T；管道伴热能耗按βt修正后计入Ef。"),
        (9, "附录A", "表A.1", "能源折标准煤参考系数；明细录入保留能源折标系数和来源。"),
        (10, "附录B", "表B.1", "集装箱箱型折算为TEU：48ft、45ft、40ft、35ft、20ft、10ft对应2.40、2.25、2.00、1.75、1.00、0.50。"),
    ]
    return [{"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
             "page": page, "clause": clause, "table": table, "note": note}
            for page, clause, table, note in rows]


def make_indicator(product_id: str, product_name: str, unit: str, levels: tuple[str, str, str],
                    formula: dict[str, Any], detail_inputs: list[dict[str, Any]],
                    source_file: str, source_sha: str, notes: list[str]) -> dict[str, Any]:
    actual_key = f"actual.GB_31823-2021.{product_id}.comparable_energy"
    return {
        "id": f"GB_31823-2021.{product_id}.comparable-energy",
        "name": "单位产品可比综合能耗",
        "unit": unit,
        "comparison": "lte",
        "input_definitions": [direct_input(actual_key, product_name, unit), *detail_inputs],
        "applicability": {"op": "always"},
        "direct_input_key": actual_key,
        "detail_formula": formula,
        "base_thresholds": thresholds(levels, unit),
        "thresholds": thresholds(levels, unit),
        "display_places": 2,
        "source_references": references(source_file, source_sha),
        "notes": [
            "candidate_from_original_pdf",
            "not_for_formal_evaluation",
            "requires_independent_review",
            "指标名称按原文术语统一为“单位产品可比综合能耗”；产品/工序名称仅保留码头类型。",
            "直接模式使用表1三级限额；明细模式按第6章公式计算，正式发布前必须完成复核表确认。",
            *notes,
        ],
    }


def make_product(product_id: str, product_name: str, unit: str, levels: tuple[str, str, str],
                 formula: dict[str, Any], detail_inputs: list[dict[str, Any]],
                 source_file: str, source_sha: str, notes: list[str]) -> dict[str, Any]:
    return {"id": product_id, "name": product_name,
            "description": f"{product_name}；按GB 31823-2021第4章和第6章统计、计算。",
            "input_definitions": [], "indicators": [
                make_indicator(product_id, product_name, unit, levels, formula, detail_inputs,
                               source_file, source_sha, notes)
            ]}


def build(source_file: str, source_sha: str) -> dict[str, Any]:
    products = [
        make_product(
            "container-terminal", "集装箱码头", "tce/10^4TEU", ("24", "28", "45"),
            container_formula(), container_inputs(), source_file, source_sha,
            ["适用于专业化集装箱码头；自动化集装箱码头按原文范围排除时不得套用本产品行。",
             "L为设计通过能力与实际完成吞吐量之比；a分段为0＜L≤2取1.0、2＜L≤3取0.95、3＜L≤4取0.9、L＞4取0.85。",
             "吞吐量按附录B箱型折算为TEU；48ft、45ft、40ft、35ft、20ft、10ft分别为2.40、2.25、2.00、1.75、1.00、0.50TEU。"],
        ),
        make_product(
            "dry-bulk-terminal", "干散货码头", "tce/10^4t", ("1.8", "2.0", "2.7"),
            dry_bulk_formula(), dry_bulk_inputs(), source_file, source_sha,
            ["适用于专业化干散货码头中的煤炭、矿石码头；是否属于原文范围由用户在评价前确认。",
             "门座式起重机装卸时不适用g修正；直接卸货至后方工厂按g=1.3。",
             "g按卸货量占比w分段计算，k按装卸作业线长度分段计算，c按GB 50189采暖地区取0.95、非采暖地区取1.0。"],
        ),
        make_product(
            "crude-oil-terminal", "原油码头", "tce/10^4t", ("0.36", "0.51", "0.88"),
            crude_oil_formula(), crude_oil_inputs(), source_file, source_sha,
            ["适用于单一原油或原油吞吐量占总吞吐量50%以上的原油码头；不含后方储存区。",
             "管道伴热能源单独使用pipeline_heat分类，不能与辅助或附属系统重复计入。",
             "管道伴热温度修正系数βt当前按温度≤0℃取0.95、温度＞0℃取1.0，原文边界需在确认表中最终核对。"],
        ),
    ]
    return {
        "schema_version": "1.0", "id": "gb-31823-2021", "number": NUMBER, "title": TITLE,
        "version": "2021", "publication_status": "draft",
        "publication_date": "2021-10-11", "effective_date": "2022-11-01",
        "source_file": source_file, "source_sha256": source_sha, "products": products,
        "corrections": ["GB 31823-2021替代GB 31823-2015、GB 31827-2015；旧版仅保留为历史关系记录。",
                        "本次先按现行强制文本建立三类码头的草案规则，复核确认前不得参与正式评价。"],
        "lifecycle_status": "active", "obsolete_date": None, "replaced_by": [],
        "supersedes": ["GB 31823-2015", "GB 31827-2015"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-63/data"))
    parser.add_argument("--source", type=Path, default=None)
    args = parser.parse_args()
    source = args.source.resolve() if args.source else next(
        path for path in SOURCE_DIR.iterdir() if path.is_file() and SOURCE_FILE_HINT in path.name
    )
    definition = build(source.name, sha256(source))
    StandardDefinition.model_validate(definition)
    target = args.data_dir.resolve() / "definitions" / "gb-31823-2021.json"
    target.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已生成GB 31823-2021草案：" + str(target))
    print("产品/工序数=" + str(len(definition["products"])) + "，指标数=" + str(sum(len(p["indicators"]) for p in definition["products"])))
    print("source_sha256=" + definition["source_sha256"])


if __name__ == "__main__":
    main()



