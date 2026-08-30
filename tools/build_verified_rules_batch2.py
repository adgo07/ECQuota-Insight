"""Transcribe another set of readable source tables into review-ready rules."""
from __future__ import annotations

import json
import re
from pathlib import Path

from build_verified_rules_batch1 import (
    DATA, constant, input_def, input_node, indicator, node, one_product,
    source, write_definition,
)


def detail_input(key: str, label: str, unit: str, description: str) -> dict:
    item = input_def(key, label, unit, description=description)
    item["modes"] = ["DETAIL"]
    return item


def custom_indicator(number: str, identifier: str, name: str, unit: str,
                     values: list[str | None], *, page: int, table: str,
                     detail_formula: dict | None = None,
                     extra_inputs: list[dict] | None = None,
                     threshold_exprs: list[dict | None] | None = None,
                     notes: list[str] | None = None) -> dict:
    file, sha = source(number)
    actual_key = f"actual.{identifier}"
    inputs = [input_def(actual_key, f"{name}实际值", unit)] + (extra_inputs or [])
    base: dict[str, dict | None] = {
        f"level_{level}": (constant(value, unit) if value is not None else None)
        for level, value in zip((1, 2, 3), values, strict=True)
    }
    thresholds = {
        f"level_{level}": expr
        for level, expr in zip((1, 2, 3), threshold_exprs or list(base.values()), strict=True)
    }
    return {
        "id": f"{number.replace(' ', '_')}.{identifier}",
        "name": name, "unit": unit, "comparison": "lte",
        "input_definitions": inputs, "applicability": {"op": "always"},
        "direct_input_key": actual_key,
        "detail_formula": detail_formula or node("per_unit", args=[
            input_node("energy.total_standard_coal"), input_node("production.total_equivalent")
        ], unit=unit, label="单位产品综合能耗"),
        "base_thresholds": base, "thresholds": thresholds, "display_places": 2,
        "source_references": [{
            "standard_number": number, "source_file": file, "source_sha256": sha,
            "page": page, "clause": "第4章 能耗限额等级", "table": table,
            "note": "已按强制性标准原文表格录入；待独立复核和确认表签署。",
        }],
        "notes": notes or ["original_pdf_transcribed", "requires_independent_review"],
    }


def build_21343() -> None:
    number = "GB 21343-2023"
    rows = [
        ("calcium-carbide-energy", "电石单位产品综合能耗", "kgce/t", ["805", "823", "940"], "表1"),
        ("calcium-carbide-electricity", "电石单位产品电炉电耗", "kWh/t", ["3000", "3080", "3200"], "表1"),
        ("vinyl-acetate-acetylene", "乙炔法乙酸乙烯酯单位产品综合能耗", "kgce/t", ["280", "410", "450"], "表2"),
        ("vinyl-acetate-ethylene", "乙烯法乙酸乙烯酯单位产品综合能耗", "kgce/t", ["240", "250", "410"], "表2"),
        ("pva-acetylene", "乙炔法聚乙烯醇单位产品综合能耗", "kgce/t", ["1900", "2000", "2500"], "表3"),
        ("pva-ethylene", "乙烯法聚乙烯醇单位产品综合能耗", "kgce/t", ["1350", "1790", "2230"], "表3"),
        ("bdo-acetaldehyde", "炔醛法1,4-丁二醇单位产品综合能耗", "kgce/t", ["890", "950", "1080"], "表4"),
        ("bdo-maleic", "顺酐法1,4-丁二醇单位产品综合能耗", "kgce/t", ["810", "850", "950"], "表4"),
        ("bdo-allyl", "烯丙醇法1,4-丁二醇单位产品综合能耗", "kgce/t", ["890", "890", "1000"], "表4"),
        ("dicyandiamide", "双氰胺单位产品综合能耗", "kgce/t", ["230", "300", "350"], "表5"),
        ("cyanamide-30", "30%单氰胺单位产品综合能耗", "kgce/t", ["315", "350", "500"], "表6"),
        ("cyanamide-50", "50%单氰胺单位产品综合能耗", "kgce/t", ["600", "750", "900"], "表6"),
    ]
    write_definition(number, [one_product(indicator(number, *row[:4], page=5, table=row[4]))
                              for row in rows])


def build_21344() -> None:
    number = "GB 21344-2023"
    rows = [
        ("ammonia-anthracite", "合成氨（优质无烟块煤）单位产品综合能耗", ["1090", "1100", "1350"]),
        ("ammonia-nonpremium", "合成氨（非优质无烟块煤、型煤）单位产品综合能耗", ["1180", "1200", "1520"]),
        ("ammonia-powder-coal", "合成氨（粉煤，包括无烟粉煤、烟煤）单位产品综合能耗", ["1340", "1350", "1550"]),
        ("ammonia-lignite", "合成氨（褐煤）单位产品综合能耗", ["1700", "1800", "1900"]),
        ("ammonia-natural-gas", "合成氨（天然气）单位产品综合能耗", ["996", "1000", "1200"]),
        ("urea-steam-turbine", "尿素（二氧化碳压缩机汽轮机驱动）单位产品综合能耗", ["130", "150", "170"]),
        ("urea-electric-motor", "尿素（二氧化碳压缩机电动机驱动）单位产品综合能耗", ["115", "138", "165"]),
        ("ammonium-bicarbonate", "碳酸氢铵单位产品电耗", ["18", "20", "30"], "kWh/t", "表3"),
        ("map-traditional-granular", "磷酸一铵（传统法、粒状）单位产品综合能耗", ["235", "255", "275"]),
        ("map-traditional-powder", "磷酸一铵（传统法、粉状）单位产品综合能耗", ["220", "240", "260"]),
        ("map-slurry-granular", "磷酸一铵（料浆法、粒状）单位产品综合能耗", ["150", "170", "190"]),
        ("map-slurry-powder", "磷酸一铵（料浆法、粉状）单位产品综合能耗", ["140", "165", "185"]),
        ("dap-traditional-granular", "磷酸二铵（传统法、粒状）单位产品综合能耗", ["225", "250", "275"]),
        ("dap-slurry-granular", "磷酸二铵（料浆法、粒状）单位产品综合能耗", ["160", "185", "200"]),
        ("potassium-brine", "硫酸钾（水盐体系法、含钾卤水为原料）单位产品综合能耗", ["300", "310", "320"]),
        ("potassium-seawater", "硫酸钾（水盐体系法、海水和卤水为原料）单位产品综合能耗", ["400", "420", "450"]),
        ("potassium-mirabilite", "硫酸钾（水盐体系法、芒硝法）单位产品综合能耗", ["450", "480", "500"]),
        ("potassium-mannheim", "硫酸钾（非水盐体系法、曼海姆法）单位产品综合能耗", ["105", "110", "120"]),
    ]
    products = []
    for idx, row in enumerate(rows, 1):
        ident, name, values = row[:3]
        unit, table = (row[3], row[4]) if len(row) > 3 else ("kgce/t", "表1、表2、表4、表5、表6")
        products.append(one_product(indicator(number, ident, name, unit, values, page=5 if idx <= 7 else 6, table=table), name))
    write_definition(number, products)


def build_29140() -> None:
    number = "GB 29140-2024"
    methods = [
        ("ammonia", "氨碱法", ["310", "320", "370"], ["350", "365", "420"]),
        ("soda-ash", "联碱法（精制工业盐为原料）", ["145", "160", "200"], ["185", "205", "250"]),
        ("natural-carbonation", "天然碱法（碳化法）", ["390", "410", "440"], ["430", "455", "490"]),
        ("natural-evaporation", "天然碱法（蒸发法）", ["340", "360", "390"], ["380", "405", "440"]),
    ]
    products = []
    for ident, method, light, heavy in methods:
        for form, vals in (("轻质纯碱", light), ("重质纯碱", heavy)):
            factor = None
            extra = None
            thresholds = None
            notes = ["original_pdf_transcribed", "requires_independent_review"]
            if ident == "soda-ash":
                factor = "condition.sun_dried_salt_factor"
                extra = [input_def(factor, "日晒工业盐修正系数", "1", description="精制工业盐取1.00；日晒工业盐按表1规定取1.18。")]
                thresholds = [node("multiply", args=[constant(v, "kgce/t"), input_node(factor)], unit="kgce/t", label="日晒工业盐修正") for v in vals]
                notes.append("sun_dried_salt_factor_from_clause_4")
            form_key = "light" if form.startswith("轻") else "heavy"
            ind = custom_indicator(
                number, f"{ident}-{form_key}", f"{method}{form}单位产品综合能耗", "kgce/t", vals,
                page=6, table="表1", extra_inputs=extra, threshold_exprs=thresholds, notes=notes)
            products.append(one_product(ind))
    write_definition(number, products)


def build_29445() -> None:
    number = "GB 29445-2025"
    coeff_names = [
        ("condition.k1", "采煤条件及工艺折算系数"), ("condition.k2", "运输距离折算系数"),
        ("condition.k3", "矿井瓦斯等级折算系数"), ("condition.k4", "矿井涌水量折算系数"),
        ("condition.k5", "单井生产能力折算系数"),
    ]
    factor_inputs = [detail_input(key, label, "1", "按附录B对应区间取值。") for key, label in coeff_names]
    factor_sum = node("add", args=[constant("1", "1")] + [input_node(key) for key, _ in coeff_names], unit="1", label="附录B折算系数合计")
    energy_adjusted = node("multiply", args=[input_node("energy.total_standard_coal"), factor_sum], unit="kgce", label="折算后综合能耗")
    detail = node("per_unit", args=[energy_adjusted, input_node("production.total_equivalent")], unit="kgce/t", label="煤炭开采单位产品能耗")
    rows = [
        ("underground", "煤炭井工开采企业单位产品能耗", ["2.5", "6.2", "10.8"]),
        ("surface", "煤炭露天开采企业单位产品能耗", ["3.0", "5.4", "8.0"]),
    ]
    products = []
    for ident, name, vals in rows:
        products.append(one_product(custom_indicator(number, ident, name, "kgce/t", vals, page=8, table="表1", detail_formula=detail, extra_inputs=factor_inputs)))
    write_definition(number, products)


def build_29449() -> None:
    number = "GB 29449-2024"
    rows = [
        ("all-steel-radial", "全钢子午线轮胎单位产品综合能耗", ["215", "235", "340"], "表1"),
        ("semi-steel-radial", "半钢子午线轮胎单位产品综合能耗", ["255", "290", "430"], "表1"),
        ("earthmover", "工程机械轮胎单位产品综合能耗", ["300", "330", "560"], "表1"),
        ("bias", "斜交轮胎单位产品综合能耗", [None, None, "515"], "表1"),
        ("carbon-black-excluding-feedstock", "炭黑单位产品综合能耗（扣除原料用能）", ["300", "330", "460"], "表2"),
        ("carbon-black-including-feedstock", "炭黑单位产品综合能耗（不扣除原料用能）", ["1650", "1800", "1950"], "附录A表A.1"),
    ]
    write_definition(number, [one_product(custom_indicator(number, ident, name, "kgce/t", vals, page=6 if table == "表1" else 10, table=table,
                                             notes=["original_pdf_transcribed", "missing_grade_preserved" if None in vals else "original_pdf_transcribed", "缺级：原文为—，保留空值" if None in vals else "", "requires_independent_review"]))
                              for ident, name, vals, table in rows])


def build_29995() -> None:
    number = "GB 29995-2024"
    rows = [
        ("columnar-activated-carbon", "柱状活性炭单位产品能耗（原料用能不纳入）", ["1300", "1400", "1650"], "表1", 7),
        ("briquette-activated-carbon", "压块活性炭单位产品能耗（原料用能不纳入）", ["1250", "1350", "1600"], "表1", 7),
        ("raw-coal-crushed-activated-carbon", "原煤破碎活性炭单位产品能耗（原料用能不纳入）", ["1200", "1300", "1500"], "表1", 7),
        ("activated-coke", "活性焦单位产品能耗（原料用能不纳入）", ["650", "680", "750"], "表1", 7),
        ("semi-coke", "兰炭单位产品能耗", ["160", "180", "210"], "表2", 7),
        ("columnar-activated-carbon-feedstock", "柱状活性炭单位产品能耗（原料用能纳入）", ["3800", "4000", "4350"], "附录A表A.1", 8),
        ("briquette-activated-carbon-feedstock", "压块活性炭单位产品能耗（原料用能纳入）", ["3900", "4250", "4450"], "附录A表A.1", 8),
        ("raw-coal-crushed-activated-carbon-feedstock", "原煤破碎活性炭单位产品能耗（原料用能纳入）", ["3750", "3900", "4250"], "附录A表A.1", 8),
        ("activated-coke-feedstock", "活性焦单位产品能耗（原料用能纳入）", ["1900", "2100", "2200"], "附录A表A.1", 8),
    ]
    products = []
    for ident, name, vals, table, page in rows:
        extra = None
        detail = None
        notes = ["original_pdf_transcribed", "requires_independent_review"]
        if ident == "semi-coke":
            key = "condition.semi_coke_correction"
            extra = [detail_input(key, "兰炭单位产品能耗修正值", "kgce/t", "按附录C的兰炭产品得率区间取值。")]
            detail = node("subtract", args=[node("per_unit", args=[input_node("energy.total_standard_coal"), input_node("production.total_equivalent")], unit="kgce/t"), input_node(key)], unit="kgce/t", label="兰炭修正后单位产品能耗")
            notes.append("semi_coke_yield_correction_from_appendix_C")
        products.append(one_product(custom_indicator(number, ident, name, "kgce/t", vals, page=page, table=table, detail_formula=detail, extra_inputs=extra, notes=notes), name))
    write_definition(number, products)


if __name__ == "__main__":
    build_21343(); build_21344(); build_29140(); build_29445(); build_29449(); build_29995()
    print("已按原文重建GB 21343、21344、29140、29445、29449、29995；均为reviewed，尚未published。")
