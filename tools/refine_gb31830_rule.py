from __future__ import annotations

"""Refine GB 31830-2024 TDI/MDI unit-energy rules."""

import argparse
import json
from pathlib import Path

from uebench.domain.models import StandardDefinition


def node(
    op: str,
    *,
    value: str | None = None,
    input_key: str | None = None,
    args: list[dict] | None = None,
    unit: str | None = None,
    label: str | None = None,
) -> dict:
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


def direct_definition(key: str, label: str, unit: str) -> dict:
    return {
        "key": key,
        "label": label,
        "data_type": "decimal",
        "unit": unit,
        "required": True,
        "required_if": None,
        "modes": ["DIRECT"],
        "minimum": "0",
        "maximum": None,
        "choices": [],
        "description": "直接录入按GB 31830-2024第6.2节核算的单位产品能耗。",
    }


def make_indicator(
    number: str,
    source_file: str,
    source_sha: str,
    *,
    product_id: str,
    product_name: str,
    table: str,
    levels: tuple[str, str, str],
) -> dict:
    unit = "kgce/t"
    actual_key = f"actual.GB_31830-2024.{product_id}.energy"
    references = [
        {
            "standard_number": number,
            "source_file": source_file,
            "source_sha256": source_sha,
            "page": 5,
            "clause": "第1章",
            "table": "范围",
            "note": "TDI以DNT、氢气、氯气和一氧化碳为原料；MDI以苯胺、甲醛、氯气和一氧化碳为原料，产品范围不得混用。",
        },
        {
            "standard_number": number,
            "source_file": source_file,
            "source_sha256": source_sha,
            "page": 6,
            "clause": "4.1～5.2",
            "table": table,
            "note": "表格值依次映射为1级、2级、3级；现有企业执行3级限定值，新建或改扩建项目执行2级准入值。",
        },
        {
            "standard_number": number,
            "source_file": source_file,
            "source_sha256": source_sha,
            "page": 7,
            "clause": "6.1～6.2.6",
            "table": "公式（1）、公式（2）",
            "note": "综合能耗包含生产、辅助和附属系统；回收并供范围外利用的能源按实际利用量扣除；单位产品能耗为E/P。",
        },
        {
            "standard_number": number,
            "source_file": source_file,
            "source_sha256": source_sha,
            "page": 8,
            "clause": "附录A",
            "table": "表A.1、表A.2",
            "note": "能源折标准煤系数优先采用报告期实测值；无实测条件时可参考附录A。",
        },
        {
            "standard_number": number,
            "source_file": source_file,
            "source_sha256": source_sha,
            "page": 10,
            "clause": "附录B",
            "table": "表B.1",
            "note": "耗能工质等价值按企业实际条件修正；不得把附录参考值误作不可变的固定值。",
        },
    ]
    return {
        "id": f"GB_31830-2024.{product_id}.comprehensive-energy",
        "name": f"{product_name}单位产品综合能耗",
        "unit": unit,
        "comparison": "lte",
        "input_definitions": [
            direct_definition(actual_key, f"{product_name}单位产品能耗实际值", unit)
        ],
        "applicability": {"op": "always"},
        "direct_input_key": actual_key,
        "detail_formula": node(
            "per_unit",
            args=[
                node("input", input_key="energy.total_standard_coal", unit="kgce", label="统计期产品综合能耗E"),
                node("input", input_key="production.total_equivalent", unit="t", label=f"{product_name}合格产品产量P"),
            ],
            unit=unit,
            label=f"{product_name}单位产品能耗（公式1、公式2）",
        ),
        "base_thresholds": {
            f"level_{index}": node("constant", value=value, unit=unit)
            for index, value in enumerate(levels, 1)
        },
        "thresholds": {
            f"level_{index}": node("constant", value=value, unit=unit)
            for index, value in enumerate(levels, 1)
        },
        "display_places": 2,
        "source_references": references,
        "notes": [
            "candidate_from_original_pdf",
            "not_for_formal_evaluation",
            "requires_independent_review",
            "formula_1_energy_total_equals_production_plus_auxiliary_affiliated_inputs_minus_external_recovery",
            "formula_2_unit_energy_equals_E_divided_by_qualified_product_mass",
            "standard_scope_excludes_construction_renovation_and_living_energy",
            "production_boundary_includes_normal_major_overhaul_and_storage_loss",
            "qualified_product_must_meet_GB_T_32469_for_TDI_or_GB_T_13941_for_MDI",
            "energy.total_standard_coal_input_unit_is_kgce_and_production.total_equivalent_input_unit_is_t",
        ],
    }


def build(data_dir: Path) -> Path:
    path = data_dir / "definitions" / "gb-31830-2024.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    number = "GB 31830-2024"
    if data.get("number") != number:
        raise ValueError(f"规则文件标准号不符：{data.get('number')}")
    source_file = data["source_file"]
    source_sha = data["source_sha256"]
    products = [
        {
            "id": "tdi",
            "name": "甲苯二异氰酸酯（TDI）",
            "description": "按GB 31830-2024生产系统、辅助生产系统和附属生产系统统计；合格TDI产量以t计。",
            "input_definitions": [],
            "indicators": [
                make_indicator(
                    number,
                    source_file,
                    source_sha,
                    product_id="tdi",
                    product_name="甲苯二异氰酸酯（TDI）",
                    table="表1",
                    levels=("340", "500", "950"),
                )
            ],
        },
        {
            "id": "mdi",
            "name": "二苯基甲烷二异氰酸酯（MDI）",
            "description": "按GB 31830-2024生产系统、辅助生产系统和附属生产系统统计；合格MDI产量以t计。",
            "input_definitions": [],
            "indicators": [
                make_indicator(
                    number,
                    source_file,
                    source_sha,
                    product_id="mdi",
                    product_name="二苯基甲烷二异氰酸酯（MDI）",
                    table="表2",
                    levels=("175", "180", "190"),
                )
            ],
        },
    ]
    data["supersedes"] = ["GB 31828-2015", "GB 31830-2015"]
    data["publication_status"] = "draft"
    data["products"] = products
    StandardDefinition.model_validate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="精化GB 31830-2024草案规则（仍为draft）")
    parser.add_argument("--data-dir", type=Path, default=Path("work/next-scope-63/data"))
    args = parser.parse_args()
    print(f"已精化GB 31830-2024草案规则：{build(args.data_dir.resolve())}")


if __name__ == "__main__":
    main()
