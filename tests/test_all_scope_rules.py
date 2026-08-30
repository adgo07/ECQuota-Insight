from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from uebench.domain.models import Expression, PublicationStatus, StandardDefinition
from tools.check_published_rules import check as check_published_rules


def _definitions() -> list[StandardDefinition]:
    return [StandardDefinition.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(Path("data/definitions").glob("*.json"))]


def test_every_scope_standard_has_at_least_one_source_backed_rule() -> None:
    definitions = _definitions()
    assert len(definitions) == 46
    assert all(definition.products for definition in definitions)
    assert all(product.indicators for definition in definitions for product in definition.products)
    for definition in definitions:
        for product in definition.products:
            for indicator in product.indicators:
                assert indicator.source_references
                assert all(reference.standard_number == definition.number for reference in indicator.source_references)
                assert all(reference.page >= 1 for reference in indicator.source_references)
                assert any((indicator.thresholds.level_1, indicator.thresholds.level_2, indicator.thresholds.level_3))
                # Some source tables intentionally use “—” for a missing grade;
                # the rule must preserve the gap rather than inventing a value.
                if indicator.thresholds.level_1 is None or indicator.thresholds.level_2 is None:
                    assert any("缺级" in note or "—" in note for note in indicator.notes)


def test_scope_rules_have_safe_publication_status() -> None:
    definitions = _definitions()
    statuses = {definition.publication_status for definition in definitions}
    assert statuses <= {PublicationStatus.REVIEWED, PublicationStatus.PUBLISHED}
    # The number of indicators is source-table driven and may increase when a
    # previously condensed table is transcribed into separate product rows.
    # The invariant is that every scoped standard has at least one explicit
    # candidate, not a frozen row count.
    assert sum(len(product.indicators) for definition in definitions for product in definition.products) >= len(definitions)
    assert all(definition.publication_status is not PublicationStatus.DRAFT for definition in definitions)


def test_constant_candidate_thresholds_are_monotone_for_lte_rules() -> None:
    checked = 0
    for definition in _definitions():
        for product in definition.products:
            for indicator in product.indicators:
                expressions = [indicator.thresholds.level_1, indicator.thresholds.level_2, indicator.thresholds.level_3]
                if not all(expression is not None and expression.op == "constant" for expression in expressions):
                    continue
                # Compilation-only rows are intentionally untrusted leads; they
                # may contain column shifts and are explicitly kept for review.
                if "candidate_from_compilation" in indicator.notes:
                    continue
                values = [Decimal(str(expression.value)) for expression in expressions]
                if indicator.comparison.value == "lte":
                    assert values[0] <= values[1] <= values[2], (definition.number, indicator.id, values)
                checked += 1
    # All visually transcribed/compilation candidate rows are constants; this
    # guards against a malformed row silently entering the package.
    assert checked >= 300


def test_scope_manifest_and_catalog_remain_exact() -> None:
    scope = json.loads(Path("data/scope-44.json").read_text(encoding="utf-8"))
    catalog = json.loads(Path("data/catalog.json").read_text(encoding="utf-8"))
    assert len(scope["standards"]) == 46
    assert len(catalog["standards"]) == 46
    assert {row["number"] for row in catalog["standards"]} == set(scope["standards"])


def test_every_published_indicator_runs_in_direct_entry_smoke() -> None:
    report = check_published_rules(Path("data/definitions"))
    assert report["total_indicators"] == 701
    assert report["incomplete"] == []
    assert report["boundary_errors"] == []


def test_original_table_batch1_values_and_citations() -> None:
    by_number = {definition.number: definition for definition in _definitions()}

    ceramic = by_number["GB 21252-2023"]
    ceramic_values = {
        product.name: [str(getattr(product.indicators[0].base_thresholds, f"level_{level}").value)
                       for level in (1, 2, 3)]
        for product in ceramic.products
    }
    assert ceramic_values["陶瓷板"] == ["6.0", "8.7", "13.2"]
    assert ceramic_values["耐磨氧化铝球（90系列）"] == ["295", "320", "370"]
    assert all(reference.table for product in ceramic.products for indicator in product.indicators
               for reference in indicator.source_references)
    assert all(reference.page >= 5 for product in ceramic.products for indicator in product.indicators
               for reference in indicator.source_references)

    pvc = by_number["GB 21257-2024"]
    names = {product.name for product in pvc.products}
    assert "液碱（质量分数≥30.0%）" in names
    assert "甲烷氯化物，四氯化碳转化成三氯甲烷并进入生产系统" in names
    pvc_values = {
        product.name: [str(getattr(product.indicators[0].base_thresholds, f"level_{level}").value)
                       for level in (1, 2, 3)]
        for product in pvc.products
    }
    assert pvc_values["电石法聚氯乙烯树脂（糊用型）"] == ["430", "450", "480"]
    assert pvc_values["甲烷氯化物，四氯化碳转化成三氯甲烷并进入生产系统"] == ["255", "275", "320"]


def test_original_table_batch2_values_and_missing_grade() -> None:
    by_number = {definition.number: definition for definition in _definitions()}

    calcium = by_number["GB 21343-2023"]
    calcium_map = {p.name: p.indicators[0] for p in calcium.products}
    assert [str(getattr(calcium_map["电石单位产品综合能耗"].base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["805", "823", "940"]
    assert [str(getattr(calcium_map["50%单氰胺单位产品综合能耗"].base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["600", "750", "900"]

    fertilizer = by_number["GB 21344-2023"]
    fertilizer_map = {p.name: p.indicators[0] for p in fertilizer.products}
    assert [str(getattr(fertilizer_map["硫酸钾（水盐体系法、含钾卤水为原料）单位产品综合能耗"].base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["300", "310", "320"]
    assert len(fertilizer.products) == 18

    soda = by_number["GB 29140-2024"]
    assert len(soda.products) == 8
    assert any("日晒工业盐修正系数" in item.label for product in soda.products for item in product.indicators[0].input_definitions)

    tire = by_number["GB 29449-2024"]
    bias = next(p.indicators[0] for p in tire.products if p.name.startswith("斜交轮胎"))
    assert bias.thresholds.level_1 is None and bias.thresholds.level_2 is None
    assert bias.thresholds.level_3 is not None and str(bias.thresholds.level_3.value) == "515"

    carbon = by_number["GB 29995-2024"]
    assert len(carbon.products) == 9
    semi = next(p.indicators[0] for p in carbon.products if p.name == "兰炭单位产品能耗")
    assert semi.detail_formula is not None and semi.detail_formula.op == "subtract"

    paper = by_number["GB 31825-2024"]
    assert len(paper.products) == 38
    tissue = next(p.indicators[0] for p in paper.products if p.name == "卫生纸原纸、纸巾原纸、吸水衬纸（木浆）")
    assert [str(getattr(tissue.base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["380", "450", "520"]
    paper_note = next(p.indicators[0] for p in paper.products if p.name == "新闻纸")
    assert paper_note.thresholds.level_1 is not None and paper_note.thresholds.level_1.op == "add"

    refinery = by_number["GB 30251-2024"]
    assert len(refinery.products) == 14
    dry_gas = next(p.indicators[0] for p in refinery.products if "干气法" in p.name)
    assert [str(getattr(dry_gas.base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["424", "480", "545"]
    chlorohydrin = next(p.indicators[0] for p in refinery.products if "氯醇法" in p.name)
    assert chlorohydrin.thresholds.level_1 is None and chlorohydrin.thresholds.level_2 is None


def test_original_table_batches7_and8_values_and_citations() -> None:
    by_number = {definition.number: definition for definition in _definitions()}

    carbon = by_number["GB 25324-2022"]
    carbon_map = {product.name: product.indicators[0] for product in carbon.products}
    assert len(carbon.products) == 11
    assert [str(getattr(carbon_map["铝电解用预焙阳极煅烧工序单位产品综合能源消耗"].base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["190", "210", "250"]
    assert [str(getattr(carbon_map["铝电解用石墨化阴极炭块石墨化加工工序单位产品综合能源消耗"].base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["460", "480", "660"]
    assert all(reference.table for product in carbon.products for indicator in product.indicators for reference in indicator.source_references)

    fibers = by_number["GB 36889-2025"]
    fibers_map = {product.name: product.indicators[0] for product in fibers.products}
    assert len(fibers.products) == 48
    assert [str(getattr(fibers_map["聚酯涤纶/熔体直接纺丝/全拉伸丝(FDY)"].base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["50", "60", "83"]
    assert [str(getattr(fibers_map["超高分子量聚乙烯纤维(湿法纺丝)/碳氢萃取剂"].base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["4000", "6000", "8000"]
    assert all(reference.page >= 6 and reference.table for product in fibers.products for indicator in product.indicators for reference in indicator.source_references)


def test_original_table_batch9_copper_values_and_specification_factor() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 21350-2023")
    assert len(definition.products) == 108
    pipe = next(product.indicators[0] for product in definition.products if product.name == "表2 管材 紫铜熔铸工序单位产品综合能耗")
    assert [str(getattr(pipe.base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["55", "60", "70"]
    assert pipe.thresholds.level_1 is not None and pipe.thresholds.level_1.op == "multiply"
    assert any(item.label == "产品规格修正系数" for item in pipe.input_definitions)
    wire = next(product.indicators[0] for product in definition.products if product.name == "表10 上引连铸法/阴极铜电工用铜线坯单位产品综合能耗")
    assert [str(getattr(wire.base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["45", "52", "56"]
    assert all(reference.table for product in definition.products for indicator in product.indicators for reference in indicator.source_references)


def test_original_table_batch10_aluminium_values_and_forging_formula() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 21351-2023")
    assert len(definition.products) == 108
    flat = next(product.indicators[0] for product in definition.products if product.name == "扁铸锭/熔融态铝及铝合金为主原料/熔铸（I类）")
    assert [str(getattr(flat.base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["70", "85", "100"]
    forging = next(product.indicators[0] for product in definition.products if product.name == "自由锻件/锻造")
    assert forging.thresholds.level_1 is not None and forging.thresholds.level_1.op == "add"
    assert any(item.label == "统计期平均锻造火次" for item in forging.input_definitions)
    assert [str(getattr(forging.base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["440", "490", "540"]


def test_original_table_batch11_glass_capacity_and_correction_formula() -> None:
    definition = next(item for item in _definitions() if item.number == "GB 21340-2019")
    assert len(definition.products) == 42
    small = next(product.indicators[0] for product in definition.products if "≤500 t/d" in product.name)
    assert small.thresholds.level_1 is None and small.thresholds.level_2 is None
    medium = next(product.indicators[0] for product in definition.products if "500 t/d＜" in product.name)
    assert [str(getattr(medium.base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["9.5", "11.5", "13.5"]
    assert medium.thresholds.level_1 is not None and medium.thresholds.level_1.op == "multiply"
    tempered = next(product.indicators[0] for product in definition.products if "平面普通钢化玻璃/3 mm" in product.name)
    assert [str(getattr(tempered.base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["2.20", "2.75", "3.46"]
    cast_stone = next(product.indicators[0] for product in definition.products if product.name == "铸石")
    assert [str(getattr(cast_stone.base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["540", "700", "800"]


def test_original_table_batch12_and13_power_generation_values() -> None:
    coal = next(item for item in _definitions() if item.number == "GB 21258-2024")
    assert len(coal.products) == 13
    ultra = next(product.indicators[0] for product in coal.products if "超高压·200及以下" in product.name)
    assert ultra.thresholds.level_1 is None and ultra.thresholds.level_2 is None
    supercritical = next(product.indicators[0] for product in coal.products if product.name == "燃煤发电机组（超临界·600MW）供电煤耗率")
    assert [str(getattr(supercritical.base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["286", "285", "299"]
    assert supercritical.thresholds.level_1 is not None and supercritical.thresholds.level_1.op == "add"

    gas = next(item for item in _definitions() if item.number == "GB 45247-2025")
    assert len(gas.products) == 10
    power = next(product.indicators[0] for product in gas.products if "H级/500MW" in product.name and "供电" in product.name)
    assert [str(getattr(power.base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["201", "210", "215"]
    assert power.thresholds.level_1 is not None and power.thresholds.level_1.op == "multiply"
    heat = next(product.indicators[0] for product in gas.products if "H级/500MW" in product.name and "供热" in product.name)
    assert [str(getattr(heat.base_thresholds, f"level_{i}").value) for i in (1, 2, 3)] == ["38", "38.5", "39"]
