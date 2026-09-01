from __future__ import annotations

"""Build an auditable draft definition for GB 30185-2025."""

import argparse
import hashlib
import os
import json
from pathlib import Path
from typing import Any

from uebench.domain.models import StandardDefinition

NUMBER = "GB 30185-2025"
TITLE = "铝(塑)复合板单位产品能源消耗限额"
SOURCE_DIR = Path(os.environ.get("UEBENCH_SOURCE_DIR", r"G:\标准  规范\02_能耗限额_终端产品\单位产品限额\现行强制文本"))

ROWS = [
    ("decorative-thermal", "铝塑复合板—热压复合装饰板", "2400", "3000", "4400"),
    ("decorative-coating-thermal", "铝塑复合板—化成涂装和热压复合", "3500", "5000", "6500"),
    ("curtain-thermal", "铝塑复合板—幕墙板热压复合", "2700", "3200", "4800"),
    ("curtain-coating-thermal", "铝塑复合板—幕墙板化成涂装和热压复合", "4400", "5600", "7600"),
    ("noncombustible", "不燃铝复合板", "3200", "3900", "5400"),
    ("decorative-aluminum-powder", "装饰用铝单板—粉末喷涂", "7000", "8500", "10200"),
    ("decorative-aluminum-liquid", "装饰用铝单板—液体喷涂", "12000", "14000", "17200"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def node(op: str, *, value: str | None = None, input_key: str | None = None,
         args: list[dict[str, Any]] | None = None, unit: str | None = None,
         label: str | None = None) -> dict[str, Any]:
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


def per_unit(total: dict[str, Any], production: dict[str, Any], unit: str, label: str) -> dict[str, Any]:
    return node("per_unit", args=[total, production], unit=unit, label=label)


def direct_definition(key: str, label: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "data_type": "decimal",
        "unit": "kgce/10^4m2",
        "required": True,
        "required_if": None,
        "modes": ["DIRECT"],
        "minimum": "0",
        "maximum": None,
        "choices": [],
        "description": "按GB 30185-2025第6.2.2条核算；新规则尚未完成确认，当前仅作草案。",
    }


def energy_formula(product_name: str) -> dict[str, Any]:
    production = inp(
        "energy.category.production_system.net_standard_coal",
        "kgce",
        "生产系统能耗（折标准煤）",
    )
    auxiliary = inp(
        "energy.category.auxiliary_system.net_standard_coal",
        "kgce",
        "辅助生产系统能耗（折标准煤）",
    )
    affiliated = inp(
        "energy.category.affiliated_system.net_standard_coal",
        "kgce",
        "附属生产系统能耗（折标准煤）",
    )
    total = add(
        production,
        auxiliary,
        affiliated,
        unit="kgce",
        label="产品综合能耗 E（公式1）",
    )
    return per_unit(
        total,
        inp("production.total_equivalent", "10^4m2", "合格产品产量 P"),
        "kgce/10^4m2",
        product_name + "单位产品综合能耗 eb（公式2）",
    )


def references(source_file: str, source_sha: str) -> list[dict[str, Any]]:
    rows = [
        (5, "第1章；3.1～3.3", "范围与术语", "适用于铝塑复合板、不燃铝复合板和装饰用铝单板。"),
        (5, "第4章", "表1", "铝塑复合板、幕墙板、不燃铝复合板和装饰用铝单板三级限额。"),
        (6, "第4章；第5章5.1～5.2", "表1；技术要求", "1级能耗最低；现有企业执行3级，新建改扩建执行2级。"),
        (7, "6.1.1～6.1.4", "统计范围", "按生产线计量；生产、辅助、附属系统计入，生活用能不计入。"),
        (7, "6.1.5", "多种产品能耗分摊", "无法分开计量的公用能耗按比例分摊，同一统计周期内原则不变。"),
        (7, "6.2.1", "公式（1）", "产品综合能耗 E 为各能源实物量乘折标系数之和。"),
        (8, "6.2.2", "公式（2）", "单位产品综合能耗 eb=E/P，P为合格产品产量（10^4m2）。"),
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


def make_product(product_id: str, product_name: str, levels: tuple[str, str, str],
                 source_file: str, source_sha: str) -> dict[str, Any]:
    actual_key = "actual.GB_30185-2025." + product_id + ".energy"
    indicator = {
        "id": "GB_30185-2025." + product_id + ".comprehensive-energy",
        "name": "单位产品综合能耗",
        "unit": "kgce/10^4m2",
        "comparison": "lte",
        "input_definitions": [direct_definition(actual_key, product_name + "单位产品综合能耗实际值")],
        "applicability": {"op": "always"},
        "direct_input_key": actual_key,
        "detail_formula": energy_formula(product_name),
        "base_thresholds": {
            "level_1": const(levels[0], "kgce/10^4m2", "表1：1级"),
            "level_2": const(levels[1], "kgce/10^4m2", "表1：2级"),
            "level_3": const(levels[2], "kgce/10^4m2", "表1：3级"),
        },
        "thresholds": {
            "level_1": const(levels[0], "kgce/10^4m2", "表1：1级"),
            "level_2": const(levels[1], "kgce/10^4m2", "表1：2级"),
            "level_3": const(levels[2], "kgce/10^4m2", "表1：3级"),
        },
        "display_places": 2,
        "source_references": references(source_file, source_sha),
        "notes": [
            "candidate_from_original_pdf",
            "not_for_formal_evaluation",
            "requires_independent_review",
            "指标名称按原文术语统一为“单位产品综合能耗”；产品/工序名称保留具体产品与工艺。",
            "1级、2级、3级分别对应原文表1的1级、2级、3级；比较方向为实际值不大于限额。",
            "现有企业执行表1中3级限定值；新建、改建和扩建企业执行表1中2级准入值。",
            "明细模式只将生产系统、辅助生产系统、附属生产系统三类能源折标量相加；生活（基建、食堂、宿舍）用能不得录入。",
            "按生产线分别计量；多种产品无法分开计量的公用能耗按比例分摊，同一统计周期内保持分摊原则不变。",
            "能源明细中每条能源必须附带实测或GB/T2589参考折标系数；同一统计期不得重计或漏计。",
            "表1脚注a：复合线用于铝蜂窝板、铝波纹芯复合铝板时，其产量和能耗均进行统计。",
        ],
    }
    return {
        "id": product_id,
        "name": product_name,
        "description": product_name + "；按GB 30185-2025表1和第6章统计、计算。",
        "input_definitions": [],
        "indicators": [indicator],
    }


def build(source_file: str, source_sha: str) -> dict[str, Any]:
    products = [
        make_product(product_id, name, (level1, level2, level3), source_file, source_sha)
        for product_id, name, level1, level2, level3 in ROWS
    ]
    return {
        "schema_version": "1.0",
        "id": "gb-30185-2025",
        "number": NUMBER,
        "title": TITLE,
        "version": "2025",
        "publication_status": "draft",
        "publication_date": "2025-02-28",
        "effective_date": "2026-03-01",
        "source_file": source_file,
        "source_sha256": source_sha,
        "products": products,
        "corrections": ["GB 30185-2025替代GB 30185-2013；新标准范围和限额表按现行强制文本重新精化。"],
        "lifecycle_status": "active",
        "obsolete_date": None,
        "replaced_by": [],
        "supersedes": ["GB 30185-2013"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-63/data"))
    parser.add_argument("--source", type=Path, default=None)
    args = parser.parse_args()
    source = args.source.resolve() if args.source else next(
        p for p in SOURCE_DIR.iterdir() if p.is_file() and "30185-2025" in p.name
    )
    definition = build(source.name, sha256(source))
    StandardDefinition.model_validate(definition)
    target = args.data_dir.resolve() / "definitions" / "gb-30185-2025.json"
    target.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已生成GB 30185-2025草案：" + str(target))
    print("产品/工序数=" + str(len(definition["products"])) + "，指标数=" + str(sum(len(p["indicators"]) for p in definition["products"])))
    print("source_sha256=" + definition["source_sha256"])


if __name__ == "__main__":
    main()

