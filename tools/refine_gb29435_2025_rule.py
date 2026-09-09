from __future__ import annotations
"""Build an auditable draft definition for GB 29435-2025."""
import argparse
import hashlib
import os
import json
from pathlib import Path
from typing import Any
from uebench.domain.models import StandardDefinition

NUMBER = "GB 29435-2025"
TITLE = "稀土冶炼企业单位产品能源消耗限额"
SOURCE_DEFAULT_DIR = Path(os.environ.get("UEBENCH_SOURCE_DIR", r"G:\标准  规范\02_能耗限额_终端产品\单位产品限额\现行强制文本"))
SOURCE_FILE_HINT = "29435-2025"

ION = [
("氧化镧","1.41","1.46","1.62"),("氧化铈","1.33","1.42","1.49"),("氧化镨","1.36","1.38","1.58"),("氧化钕","1.34","1.48","1.89"),("氧化钐","1.32","1.45","1.89"),("氧化铕","1.42","1.46","1.53"),("氧化钆","1.33","1.45","1.67"),("氧化铽","1.35","1.45","1.91"),("氧化镝","1.31","1.45","1.58"),("氧化钬","1.34","1.45","1.67"),("氧化铒","1.32","1.45","1.57"),("氧化铥","1.30","1.45","1.49"),("氧化镱","1.28","1.36","1.49"),("氧化镥","1.35","1.46","1.62"),("氧化钇","1.40","1.45","1.67"),("氧化镨钕","1.36","1.46","1.53")]
MIXED = [
("氧化镧","1.87","1.91","2.10"),("氧化铈","1.86","1.98","2.10"),("氧化镨","1.97","2.05","2.13"),("氧化钕","1.97","2.02","2.07"),("氧化钐","1.61","1.63","1.65"),("氧化铕","1.75","1.80","1.85"),("氧化钆","1.72","1.81","1.89"),("氧化铽","1.82","1.83","1.84"),("氧化镝","1.69","1.70","1.71"),("氧化镨钕","1.38","1.44","1.69"),("混合稀土碳酸盐","1.90","1.99","2.12")]
WASTE = [("氧化钆","1.44","1.50","1.59"),("氧化铽","1.46","1.47","1.58"),("氧化镝","1.43","1.46","1.58"),("氧化钬","1.42","1.59","1.69"),("氧化镨钕","1.51","1.80","1.89")]
ELECTROLYTIC = [
("金属镧","1.11","1.13","1.38"),("金属铈","1.12","1.17","1.24"),("金属镨","1.10","1.17","1.25"),("金属钕","1.10","1.12","1.22"),("金属钐","1.46","1.79","1.85"),("金属钆","1.63","1.67","2.09"),("金属铽","1.66","1.85","2.19"),("金属镝","1.84","1.98","2.19"),("金属钇","2.77","2.87","3.02"),("镨钕金属","1.10","1.14","1.28"),("镧铈金属","1.12","1.20","1.29"),("钆铁合金","1.11","1.17","1.23"),("镝铁合金","1.09","1.17","1.23"),("钬铁合金","1.05","1.15","1.20")]
INTERMEDIATE = [("金属钆","2.65","2.79","2.79"),("金属铽","2.65","2.79","2.79"),("金属镝","2.65","2.79","2.79"),("金属钇","4.77","5.02","5.02")]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def node(op: str, *, value: str | None = None, input_key: str | None = None,
         args: list[dict[str, Any]] | None = None, cases: list[dict[str, Any]] | None = None,
         unit: str | None = None, label: str | None = None) -> dict[str, Any]:
    return {"op": op, "value": value, "input_key": input_key, "args": args or [],
            "cases": cases or [], "rows": [], "default": None, "label": label,
            "unit": unit, "round_places": None}

def inp(key: str, unit: str | None, label: str) -> dict[str, Any]:
    return node("input", input_key=key, unit=unit, label=label)

def const(value: str, unit: str, label: str | None = None) -> dict[str, Any]:
    return node("constant", value=value, unit=unit, label=label)

def add(*args: dict[str, Any], unit: str, label: str) -> dict[str, Any]:
    return node("add", args=list(args), unit=unit, label=label)

def multiply(*args: dict[str, Any], unit: str, label: str) -> dict[str, Any]:
    return node("multiply", args=list(args), unit=unit, label=label)

def divide(a: dict[str, Any], b: dict[str, Any], unit: str, label: str) -> dict[str, Any]:
    return node("divide", args=[a, b], unit=unit, label=label)

def direct_input(key: str, label: str) -> dict[str, Any]:
    return {"key": key, "label": label, "data_type": "decimal", "unit": "tce/t",
            "required": True, "required_if": None, "modes": ["DIRECT"],
            "minimum": "0", "maximum": None, "choices": [],
            "description": "按GB 29435-2025第6.2.1条核算；新标准尚未实施，当前仅作草案。"}

def process_input(key: str) -> dict[str, Any]:
    return {"key": key, "label": "氟碳铈矿生产工艺", "data_type": "text", "unit": None,
            "required": True, "required_if": None, "modes": ["DIRECT", "DETAIL"],
            "minimum": None, "maximum": None,
            "choices": ["氧化焙烧-盐酸浸出", "浓硫酸强化焙烧"],
            "description": "按GB 29435-2025表3脚注a选择；浓硫酸强化焙烧按表2限额执行。"}

def energy_formula() -> dict[str, Any]:
    cats = [
        inp("energy.category.production_system.net_standard_coal", "kgce", "主要生产系统能耗（折标准煤）"),
        inp("energy.category.auxiliary_system.net_standard_coal", "kgce", "辅助生产系统能耗（折标准煤）"),
        inp("energy.category.affiliated_system.net_standard_coal", "kgce", "附属生产系统能耗（折标准煤）"),
        inp("energy.category.external_output.net_standard_coal", "kgce", "二次能源回收并外供量（折标准煤，输出方向为负）"),
    ]
    total = add(*cats, unit="kgce", label="公式1分子：生产+辅助+附属+外供回收能源净量")
    return divide(
        multiply(total, const("0.001", "tce/kgce", "kgce换算为tce"), unit="tce", label="公式1分子换算为tce"),
        inp("production.total_equivalent", "t", "合格产品实物产量 M_Z"),
        unit="tce/t", label="单位产品综合能耗 e_z（公式1）",
    )

def piecewise_threshold(key: str, level: str) -> dict[str, Any]:
    table3 = {"level_1": "0.66", "level_2": "1.16", "level_3": "1.52"}
    table2 = {"level_1": "1.38", "level_2": "1.44", "level_3": "1.69"}
    return node("piecewise", cases=[
        {"condition": {"op": "eq", "field": key, "value": "氧化焙烧-盐酸浸出"},
         "expression": const(table3[level], "tce/t", f"表3 {level}级"), "label": "表3：氧化焙烧-盐酸浸出"},
        {"condition": {"op": "eq", "field": key, "value": "浓硫酸强化焙烧"},
         "expression": const(table2[level], "tce/t", f"表2 {level}级"), "label": "表2：浓硫酸强化焙烧（按脚注a）"},
    ], unit="tce/t", label="氟碳铈矿工艺适用限额")

def refs(source_file: str, source_sha: str) -> list[dict[str, Any]]:
    rows = [
        (5, "4.1.1", "表1", "离子型稀土矿生产稀土化合物；1级能耗最低。"),
        (6, "4.1.1～4.1.3", "表1（续）、表2、表3", "混合型、氟碳铈矿产品限额及表3脚注a。"),
        (7, "4.1.4～4.2.1", "表4、表5", "钕铁硼废料综合回收和电解法/热还原法产品限额。"),
        (8, "4.2.2、5.1～5.2", "表6", "中间合金法限额；现有企业执行3级，新建改扩建执行2级。"),
        (8, "6.1.1～6.1.2", "统计范围", "生产、辅助、附属系统和产品边界；同线产品按稀土元素含量比例分摊。"),
        (9, "6.1.2.3～6.2.2", "公式（1）", "余热利用、外供回收能源扣除、单位产品综合能耗和折标系数原则。"),
        (10, "附录A", "表A.1～表A.2", "常用能源、电力和热力折标准煤参考系数。"),
        (11, "附录B", "表B.1", "常用耗能工质能源等价参考值。"),
    ]
    return [{"standard_number": NUMBER, "source_file": source_file, "source_sha256": source_sha,
             "page": page, "clause": clause, "table": table, "note": note}
            for page, clause, table, note in rows]

def product_row(category_id: str, category_name: str, row_no: int, product_name: str,
                levels: tuple[str, str, str], table: str, source_file: str, source_sha: str,
                process_condition: bool = False) -> dict[str, Any]:
    product_id = f"{category_id}-{row_no:02d}"
    actual_key = f"actual.GB_29435_2025.{product_id}.comprehensive_energy"
    process_key = "condition.GB_29435_2025.fluorocarbon_process"
    threshold_set = (
        {f"level_{i}": piecewise_threshold(process_key, f"level_{i}") for i in (1, 2, 3)}
        if process_condition else
        {f"level_{i}": const(value, "tce/t", f"{table}：{i}级")
         for i, value in enumerate(levels, 1)}
    )
    indicator = {
        "id": f"GB_29435-2025.{product_id}.comprehensive-energy",
        "name": "单位产品综合能耗", "unit": "tce/t", "comparison": "lte",
        "input_definitions": [direct_input(actual_key, f"{product_name}单位产品综合能耗实际值")],
        "applicability": {"op": "always"}, "direct_input_key": actual_key,
        "detail_formula": energy_formula(), "base_thresholds": threshold_set, "thresholds": threshold_set,
        "display_places": 2, "source_references": refs(source_file, source_sha),
        "notes": [
            "candidate_from_original_pdf", "not_for_formal_evaluation", "requires_independent_review",
            f"产品分类：{category_name}；限额表：{table}。",
            "1级、2级、3级分别对应原文表中的1级、2级、3级；比较方向为实际值不大于限额。",
            "现有生产企业执行3级限定值；新建、改建和扩建生产企业执行2级准入值。",
            "明细模式按公式（1）：主要生产系统+辅助生产系统+附属生产系统−二次能源回收并外供量；外供行用output方向计入负值。",
            "能源明细按kgce折标准煤分类，软件换算为tce后除以合格产品实物产量t；同线多产品按稀土元素含量比例分摊。",
            "生活等非生产用途不应计入；余热利用应避免重复计算，折标系数按实测/供应数据优先、附录A/B为参考。",
        ],
    }
    if process_condition:
        indicator["notes"].append("表3脚注a：氧化焙烧-盐酸浸出执行表3；浓硫酸强化焙烧执行表2；未选择工艺返回不完整。")
    return {
        "id": product_id, "name": f"{category_name}—{product_name}",
        "description": f"{category_name}生产的{product_name}；按原文{table}执行，统计合格产品实物产量。",
        "selection_values": {"product_category": category_name, "product_spec": product_name},
        "input_definitions": [process_input(process_key)] if process_condition else [],
        "indicators": [indicator],
    }

def build(source_file: str, source_sha: str) -> dict[str, Any]:
    products: list[dict[str, Any]] = []
    groups = [
        ("ion", "离子型稀土矿生产", ION, "表1", False),
        ("mixed", "混合型稀土矿生产", MIXED, "表2", False),
        ("waste-recovery", "钕铁硼废料综合回收生产", WASTE, "表4", False),
        ("electrolytic", "电解法和热还原法（除中间合金法）生产", ELECTROLYTIC, "表5", False),
        ("intermediate-alloy", "中间合金法生产", INTERMEDIATE, "表6", False),
    ]
    for category_id, category_name, rows, table, is_condition in groups:
        for row_no, (name, l1, l2, l3) in enumerate(rows, 1):
            products.append(product_row(category_id, category_name, row_no, name, (l1, l2, l3), table, source_file, source_sha, is_condition))
    products.insert(len(ION) + len(MIXED), product_row(
        "fluorocarbon", "氟碳铈矿生产", 1, "氧化镨钕", ("0.66", "1.16", "1.52"),
        "表3（脚注a另规定浓硫酸强化焙烧按表2）", source_file, source_sha, True))
    return {
        "schema_version": "1.0", "id": "gb-29435-2025", "number": NUMBER, "title": TITLE,
        "version": "2025", "publication_status": "draft",
        "publication_date": "2025-12-31", "effective_date": "2027-01-01",
        "source_file": source_file, "source_sha256": source_sha,
        "selection_schema": [
            {"key": "product_category", "label": "产品类别", "required": True},
            {"key": "product_spec", "label": "产品规格/工序", "required": True},
        ],
        "products": products,
        "corrections": ["用户确认GB 29435-2012已由GB 29435-2025替代；旧版仅保留为历史记录。",
                        "新标准封面发布日期为2025-12-31、实施日期为2027-01-01。"],
        "lifecycle_status": "future", "obsolete_date": None, "replaced_by": [],
        "supersedes": ["GB 29435-2012"],
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-63/data"))
    parser.add_argument("--source", type=Path, default=None)
    args = parser.parse_args()
    source = args.source.resolve() if args.source else next(
        p for p in SOURCE_DEFAULT_DIR.iterdir() if p.is_file() and SOURCE_FILE_HINT in p.name
    )
    source_file, source_sha = source.name, sha256(source)
    definition = build(source_file, source_sha)
    StandardDefinition.model_validate(definition)
    target = args.data_dir.resolve() / "definitions" / "gb-29435-2025.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成{NUMBER}草案：{target}")
    print(f"产品/工序数={len(definition['products'])}，指标数={sum(len(p['indicators']) for p in definition['products'])}")
    print(f"source_sha256={source_sha}")

if __name__ == "__main__":
    main()





