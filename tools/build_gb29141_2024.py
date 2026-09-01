from __future__ import annotations

import hashlib
import os
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DEFINITIONS = DATA / "definitions"
SOURCE_DIR = Path(os.environ.get("UEBENCH_SOURCE_DIR", r"G:\标准  规范\02_能耗限额_终端产品\单位产品限额\现行强制文本"))
SOURCE_FILE = "GB+29141-2024 工业硫酸、稀硝酸和冰醋酸单位产品能源消耗限额.pdf"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expr(op: str, *, value=None, input_key=None, args=None, cases=None, unit=None, label=None) -> dict:
    return {"op": op, "value": value, "input_key": input_key, "args": args or [], "cases": cases or [], "rows": [], "default": None, "label": label, "unit": unit, "round_places": None}


def const(value: str, unit: str = "kgce/t") -> dict:
    return expr("constant", value=value, unit=unit)


def inp(key: str, label: str, *, data_type="text", unit=None, choices=None, description=None, modes=("DIRECT", "DETAIL")) -> dict:
    return {"key": key, "label": label, "data_type": data_type, "unit": unit, "required": True, "required_if": None, "modes": list(modes), "minimum": None, "maximum": None, "choices": choices or [], "description": description}


def cond(op: str = "always", *, field=None, value=None) -> dict:
    return {"op": op, "field": field, "value": value, "values": [], "minimum": None, "maximum": None, "include_minimum": True, "include_maximum": True, "args": []}


def threshold(value: str | dict | None) -> dict | None:
    return value if isinstance(value, dict) else (const(value) if value is not None else None)


def threshold_set(values: tuple[str | dict | None, str | dict | None, str | dict | None]) -> dict:
    return {f"level_{index}": threshold(value) for index, value in enumerate(values, 1)}


def add35(value: str) -> dict:
    return expr("add", args=[const(value), const("35")], unit="kgce/t", label="浓硫酸基础限额 + 发烟硫酸修正35 kgce/t")


def reference(digest: str, page: int, clause: str, table: str, note: str) -> list[dict]:
    return [{"standard_number": "GB 29141-2024", "source_file": SOURCE_FILE, "source_sha256": digest, "page": page, "clause": clause, "table": table, "note": note}]


def per_unit() -> dict:
    return expr("per_unit", args=[expr("input", input_key="energy.total_standard_coal", unit="kgce"), expr("input", input_key="production.total_equivalent", unit="t")], unit="kgce/t", label="总综合能耗 ÷ 合格产品产量")


def make_indicator(key: str, name: str, levels: tuple[str | dict | None, str | dict | None, str | dict | None], digest: str, *, inputs: list[dict], page: int, clause: str, table: str, notes: list[str]) -> dict:
    iid = f"GB_29141-2024.{key}.comprehensive-energy"
    actual_key = f"actual.{key}.comprehensive_energy"
    return {"id": iid, "name": "单位产品综合能耗", "unit": "kgce/t", "comparison": "lte", "input_definitions": [inp(actual_key, f"{name}单位产品综合能耗实际值", data_type="decimal", unit="kgce/t", modes=("DIRECT",), description="按GB 29141—2024第6章核算。")], "applicability": cond(), "direct_input_key": actual_key, "detail_formula": per_unit(), "base_thresholds": threshold_set(levels), "thresholds": threshold_set(levels), "display_places": 2, "source_references": reference(digest, page, clause, table, "依据GB 29141—2024原文逐项录入。"), "notes": notes}


def make_product(key: str, name: str, levels: tuple[str | dict | None, str | dict | None, str | dict | None], digest: str, *, description: str, inputs: list[dict], notes: list[str], page: int = 9, clause: str = "4.1", table: str = "表1") -> dict:
    return {"id": key, "name": name, "description": description, "input_definitions": inputs, "indicators": [make_indicator(key, name, levels, digest, inputs=inputs, page=page, clause=clause, table=table, notes=notes)]}


def make_special_limit_product(digest):
    name = "铅锌联合冶炼ISP低浓度SO₂烟气提浓工序"
    key = "lead-zinc-isp-so2-enrichment"
    actual_key = f"actual.{key}.specific_energy"
    indicator = {"id": f"GB_29141-2024.{key}.specific-energy", "name": "单位SO₂提浓能耗", "unit": "kgce/tSO₂", "comparison": "lte", "input_definitions": [inp(actual_key, f"{name}实际值", data_type="decimal", unit="kgce/tSO₂", modes=("DIRECT",), description="按GB 29141—2024表1脚注b核算。")], "applicability": cond(), "direct_input_key": actual_key, "detail_formula": expr("per_unit", args=[expr("input", input_key="energy.total_standard_coal", unit="kgce"), expr("input", input_key="production.total_equivalent", unit="tSO₂")], unit="kgce/tSO₂", label="提浓工序总能耗 ÷ SO₂处理量"), "base_thresholds": {"level_1": None, "level_2": None, "level_3": const("960", "kgce/tSO₂")}, "thresholds": {"level_1": None, "level_2": None, "level_3": const("960", "kgce/tSO₂")}, "display_places": 2, "source_references": reference(digest, 9, "4.1表1脚注b", "表1脚注b", "原文仅规定提浓工序能耗≤960 kgce/tSO₂，无1级、2级分级限额。"), "notes": ["原文表1脚注b；仅有3级限定值，1级和2级按原文缺级保留。"]}
    return {"id": key, "name": name, "description": "铅锌联合冶炼ISP工艺低浓度二氧化硫烟气（SO₂浓度≤4%）吸收、解析提浓工序。", "input_definitions": [], "indicators": [indicator]}


def build() -> dict:
    source = SOURCE_DIR / SOURCE_FILE
    digest = sha256(source)
    fuming = inp("acid.product_type", "产品类型", choices=["浓硫酸", "发烟硫酸（20%）"], description="表1：发烟硫酸（20%）在对应原料生产工业硫酸限额基础上增加35 kgce/t。")
    sulfur_recovery = inp("sulfur.has_low_temperature_heat_recovery", "是否有低温热回收", data_type="boolean", description="硫黄制酸3级：无低温热回收≤-110；有低温热回收≤-120 kgce/t。")
    sulfur_level3 = expr("piecewise", cases=[{"condition": cond("eq", field="sulfur.has_low_temperature_heat_recovery", value=True), "expression": const("-120"), "label": "有低温热回收"}, {"condition": cond("eq", field="sulfur.has_low_temperature_heat_recovery", value=False), "expression": const("-110"), "label": "无低温热回收"}], unit="kgce/t", label="硫黄制酸3级限额按低温热回收条件选择")
    products = [
        make_product("sulfur-acid", "硫黄制酸", (const("-160"), const("-150"), sulfur_level3), digest, description="以硫黄为原料生产工业硫酸；可选择浓硫酸或20%发烟硫酸。", inputs=[fuming, sulfur_recovery], notes=["原文表1；发烟硫酸在对应基础上增加35 kgce/t。", "原文脚注a已结构化为低温热回收条件。"]),
        make_product("pyrite-acid", "硫铁矿制酸", (add35("-110"), add35("-100"), add35("-90")), digest, description="以硫铁矿为原料生产工业硫酸；发烟硫酸在对应基础上增加35 kgce/t。", inputs=[fuming], notes=["原文表1；发烟硫酸在对应基础上增加35 kgce/t。"]),
        make_product("copper-acid-so2-over-13", "铜冶炼烟气制酸（SO₂浓度＞13%）", (add35("-30"), add35("-5"), add35("5")), digest, description="以铜冶炼烟气为原料，SO₂浓度＞13%。", inputs=[fuming], notes=["原文表1；发烟硫酸在对应基础上增加35 kgce/t。"]),
        make_product("copper-acid-so2-up-to-13", "铜冶炼烟气制酸（SO₂浓度≤13%）", (add35("2"), add35("6"), add35("12")), digest, description="以铜冶炼烟气为原料，SO₂浓度≤13%。", inputs=[fuming], notes=["原文表1；发烟硫酸在对应基础上增加35 kgce/t。"]),
        make_product("nickel-acid", "镍冶炼烟气制酸", (add35("12"), add35("15"), add35("16")), digest, description="以镍冶炼烟气为原料生产工业硫酸。", inputs=[fuming], notes=["原文表1；发烟硫酸在对应基础上增加35 kgce/t。"]),
        make_product("lead-acid", "铅冶炼烟气制酸", (add35("11"), add35("12"), add35("14")), digest, description="以铅冶炼烟气为原料生产工业硫酸。", inputs=[fuming], notes=["原文表1；发烟硫酸在对应基础上增加35 kgce/t。"]),
        make_product("zinc-acid", "锌冶炼烟气制酸", (add35("15"), add35("16"), add35("18")), digest, description="以锌冶炼烟气为原料生产工业硫酸。", inputs=[fuming], notes=["原文表1；发烟硫酸在对应基础上增加35 kgce/t。"]),
        make_product("lead-zinc-joint-acid", "铅锌联合冶炼烟气制酸", (add35("20"), add35("22"), add35("25")), digest, description="主冶炼工艺烟气直接制酸；低浓度SO₂提浓工序另有≤960 kgce/tSO₂限值，未与单位产品综合能耗混列。", inputs=[fuming], notes=["原文表1；发烟硫酸在对应基础上增加35 kgce/t。", "脚注b的低浓度SO₂提浓工序限值保留为待独立指标复核。"]),
        make_product("gypsum-acid", "石膏制酸", (add35("350"), add35("370"), add35("390")), digest, description="包括石膏预处理、石膏分解、烟气净化及制酸工序；不包括水泥熟料等副产品能耗。", inputs=[fuming], notes=["原文表1；发烟硫酸在对应基础上增加35 kgce/t。"]),
        make_product("ferrous-sulfate-acid", "掺烧硫酸亚铁（或废硫酸）制酸", (add35("-50"), add35("-40"), add35("-30")), digest, description="掺烧量≥25%，与硫铁矿或硫黄一起焙烧生产硫酸。", inputs=[fuming], notes=["原文表1脚注d；掺烧量≥25%时适用。发烟硫酸在对应基础上增加35 kgce/t。"]),
        make_special_limit_product(digest),
        make_product("dilute-nitric-acid", "稀硝酸", ("-20", "-5", "30"), digest, description="以合成氨为原料生产稀硝酸；产量按折100%硝酸计。", inputs=[], notes=["原文表2；不包括生产稀硝酸所用氨的能耗。"], clause="4.2", table="表2"),
        make_product("glacial-acetic-acid", "工业冰醋酸", ("70", "80", "120"), digest, description="工业冰醋酸合格产品按GB/T 1628要求；产量按折100%醋酸计。", inputs=[], notes=["原文表3；不包括生产工业冰醋酸所消耗的原材料（一氧化碳和甲醇等）的能耗。"], clause="4.3", table="表3"),
    ]
    return {"schema_version": "1.0", "id": "gb-29141-2024", "number": "GB 29141-2024", "title": "工业硫酸、稀硝酸和冰醋酸单位产品能源消耗限额", "version": "2024", "publication_status": "published", "publication_date": "2024-05-28", "effective_date": "2025-06-01", "source_file": SOURCE_FILE, "source_sha256": digest, "products": products, "corrections": ["GB 29141-2012、GB 29437-2012、GB 29441-2012已由本标准代替"], "lifecycle_status": "active", "obsolete_date": None, "replaced_by": [], "supersedes": ["GB 29141-2012", "GB 29437-2012", "GB 29441-2012"]}


def strip_fuming_adjustment(node):
    if isinstance(node, dict) and node.get("op") == "add" and len(node.get("args", [])) == 2:
        args = node["args"]
        if args[1].get("op") == "constant" and str(args[1].get("value")) == "35":
            return args[0]
    return node


def fuming_adjusted(base_node):
    return expr("piecewise", cases=[
        {"condition": cond("eq", field="acid.product_type", value="发烟硫酸（20%）"), "expression": expr("add", args=[base_node, const("35")], unit="kgce/t"), "label": "发烟硫酸（20%）"},
        {"condition": cond("eq", field="acid.product_type", value="浓硫酸"), "expression": base_node, "label": "浓硫酸"},
    ], unit="kgce/t", label="按产品类型执行发烟硫酸+35 kgce/t修正")


def normalize_fuming_rules(definition):
    for product in definition["products"]:
        if not any(item.get("key") == "acid.product_type" for item in product.get("input_definitions", [])):
            continue
        old_base = product["indicators"][0]["base_thresholds"]
        base = {key: strip_fuming_adjustment(value) if value is not None else None for key, value in old_base.items()}
        indicator = product["indicators"][0]
        indicator["base_thresholds"] = base
        indicator["thresholds"] = {key: fuming_adjusted(value) if value is not None else None for key, value in base.items()}
    return definition


if __name__ == "__main__":
    definition = normalize_fuming_rules(build())
    output = DEFINITIONS / "gb-29141-2024.json"
    output.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"写入 {output}: products={len(definition['products'])}, indicators={sum(len(p['indicators']) for p in definition['products'])}, sha256={definition['source_sha256']}")
