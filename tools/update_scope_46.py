from __future__ import annotations

import hashlib
import os
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DEFINITIONS = DATA / "definitions"
SOURCE = Path(os.environ.get("UEBENCH_SOURCE_DIR", r"G:\标准  规范\02_能耗限额_终端产品\单位产品限额\现行强制文本"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def expr_const(value: str, unit: str) -> dict:
    return {"op": "constant", "value": value, "input_key": None, "args": [], "cases": [], "rows": [], "default": None, "label": None, "unit": unit, "round_places": None}


def input_expr(key: str, unit: str) -> dict:
    return {"op": "input", "value": None, "input_key": key, "args": [], "cases": [], "rows": [], "default": None, "label": None, "unit": unit, "round_places": None}


def per_unit(unit: str) -> dict:
    return {"op": "per_unit", "value": None, "input_key": None, "args": [input_expr("energy.total_standard_coal", "kgce"), input_expr("production.total_equivalent", "unit")], "cases": [], "rows": [], "default": None, "label": "单位产品实际值", "unit": unit, "round_places": None}


def inp(key: str, label: str, unit: str, *, modes=("DIRECT",), minimum=None, maximum=None) -> dict:
    return {"key": key, "label": label, "data_type": "decimal", "unit": unit, "required": True, "required_if": None, "modes": list(modes), "minimum": minimum, "maximum": maximum, "choices": [], "description": None}


def ref(number: str, source_file: str, digest: str, page: int, clause: str, table: str | None) -> list[dict]:
    return [{"standard_number": number, "source_file": source_file, "source_sha256": digest, "page": page, "clause": clause, "table": table, "note": "按强制性标准原文录入；待规则确认表确认。"}]


def indicator(iid: str, name: str, unit: str, levels: tuple[str, str, str], *, comparison="lte", page: int, clause: str, table: str | None, number: str, source_file: str, digest: str, product_key: str, notes=None, detail: bool = False, display_places: int | None = None) -> dict:
    actual_key = f"actual.{product_key}.{iid.rsplit('.', 1)[-1]}"
    return {
        "id": iid, "name": name, "unit": unit, "comparison": comparison,
        "input_definitions": [inp(actual_key, f"{name}实际值", unit, modes=("DIRECT",), minimum="0")],
        "applicability": {"op": "always"}, "direct_input_key": actual_key, "detail_formula": per_unit(unit) if detail else None,
        "base_thresholds": {"level_1": expr_const(levels[0], unit), "level_2": expr_const(levels[1], unit), "level_3": expr_const(levels[2], unit)},
        "thresholds": {"level_1": expr_const(levels[0], unit), "level_2": expr_const(levels[1], unit), "level_3": expr_const(levels[2], unit)},
        "display_places": (2 if unit == "%" else 3) if display_places is None else display_places,
        "source_references": ref(number, source_file, digest, page, clause, table),
        "notes": notes or ["original_pdf_transcribed", "requires_independent_review"],
    }


def make_standard(number: str, title: str, version: str, publication: str, effective: str, source_file: str, digest: str, products: list[dict], corrections=None) -> dict:
    return {"schema_version": "1.0", "id": number.lower().replace(" ", "-").replace("—", "-"), "number": number, "title": title, "version": version, "publication_status": "reviewed", "publication_date": publication, "effective_date": effective, "source_file": source_file, "source_sha256": digest, "products": products, "corrections": corrections or []}


def build_29447() -> dict:
    number = "GB 29447-2026"; title = "硅多晶和锗单位产品能源消耗限额"
    file = "GB+29447-2026 硅多晶和锗单位产品能源消耗限额.pdf"; digest = sha256(SOURCE / file)
    products = []
    for key, name, levels in [
        ("polysilicon-trichlorosilane", "硅多晶（三氯氢硅法）", ("5.0", "5.5", "6.3")),
        ("polysilicon-silane-fluidized-bed", "硅多晶（硅烷流化床法）", ("3.6", "4.0", "4.6")),
    ]:
        products.append({"id": key, "name": name, "description": "以合格硅多晶产量计算的单位产品综合能耗。", "input_definitions": [], "indicators": [indicator(f"GB_29447-2026.{key}.comprehensive-energy", f"{name}单位产品综合能耗", "kgce/kg", levels, page=2, clause="4.1", table="表1", number=number, source_file=file, digest=digest, product_key=key, detail=True)]})
    for key, name, levels in [
        ("high-purity-germanium-tetrachloride", "高纯四氯化锗", ("5.2", "5.5", "9.3")),
        ("high-purity-germanium-dioxide", "高纯二氧化锗", ("0.9", "1.1", "1.7")),
        ("zone-melting-germanium-ingot", "区熔锗锭", ("7.8", "9.5", "18.9")),
        ("germanium-single-crystal", "锗单晶", ("6.0", "6.5", "10.0")),
    ]:
        products.append({"id": key, "name": name, "description": "锗产品能耗按对应锗金属量折算。", "input_definitions": [], "indicators": [indicator(f"GB_29447-2026.{key}.comprehensive-energy", f"{name}单位产品综合能耗", "kgce/kg", levels, page=2, clause="4.2", table="表2", number=number, source_file=file, digest=digest, product_key=key, detail=True)]})
    return make_standard(number, title, "2026", "2026-06-27", "2027-01-01", file, digest, products, ["CAT-029-REPLACE"])


def build_47834() -> dict:
    number = "GB 47834-2026"; title = "晶体硅光伏组件和逆变器能效限定值及能效等级"
    file = "GB+47834-2026 晶体硅光伏组件和逆变器能效限定值及能效等级.pdf"; digest = sha256(SOURCE / file)
    products = []
    module_levels = {"TOPCon": ("24.0", "23.7", "23.2"), "HJT": ("23.8", "23.5", "23.2"), "BC": ("24.2", "23.9", "23.5")}
    for typ, levels in module_levels.items():
        key = f"module-{typ.lower()}"
        indicators = [indicator(f"GB_47834-2026.{key}.conversion-efficiency", f"{typ}电池晶体硅光伏组件光电转换效率", "%", levels, comparison="gte", page=3, clause="5.1.1", table="表1", number=number, source_file=file, digest=digest, product_key=key, display_places=1)]
        indicators.append(indicator(f"GB_47834-2026.{key}.degradation-rate", f"{typ}电池晶体硅光伏组件耦合环境应力衰减率", "%", ("8.6", "8.6", "8.6"), comparison="lte", page=4, clause="5.2.1", table="正文", number=number, source_file=file, digest=digest, product_key=key, display_places=1, notes=["双面/单面组件均适用；限值不高于8.6%，三等级均执行该限定值", "original_pdf_transcribed", "requires_independent_review"]))
        bifacial = {"TOPCon": "75", "HJT": "85", "BC": "70"}[typ]
        indicators.append(indicator(f"GB_47834-2026.{key}.bifaciality", f"{typ}电池双面晶体硅光伏组件双面率", "%", (bifacial, bifacial, bifacial), comparison="gte", page=4, clause="5.2.1", table="正文", number=number, source_file=file, digest=digest, product_key=key, display_places=0, notes=["仅双面组件适用；单面组件标记为不适用；三等级均执行该限定值", "original_pdf_transcribed", "requires_independent_review"]))
        products.append({"id": key, "name": f"{typ}电池晶体硅光伏组件", "description": "适用于地面用n型晶体硅光伏组件。", "input_definitions": [], "indicators": indicators})
    inverter_rows = [("20-50kw", "20<P≤50", ("98.15", "98.00", "97.60"), ("98.55", "98.50", "98.40")), ("50-100kw", "50<P≤100", ("98.20", "98.05", "97.80"), ("98.60", "98.55", "98.45")), ("100-150kw", "100<P≤150", ("98.25", "98.15", "98.00"), ("98.70", "98.60", "98.50")), ("150-200kw", "150<P≤200", ("98.30", "98.25", "98.15"), ("98.80", "98.70", "98.60")), ("200-500kw", "200<P≤500", ("98.50", "98.45", "98.35"), ("99.00", "98.85", "98.65")), ("over-500kw", "P>500", ("98.55", "98.48", "98.38"), ("99.00", "98.85", "98.70"))]
    for key, band, weighted, maximum in inverter_rows:
        pkey = f"inverter-{key}"
        inds = [indicator(f"GB_47834-2026.{pkey}.weighted-total-efficiency", f"光伏并网逆变器（{band}）平均加权总效率", "%", weighted, comparison="gte", page=3, clause="5.1.2", table="表2", number=number, source_file=file, digest=digest, product_key=pkey), indicator(f"GB_47834-2026.{pkey}.max-conversion-efficiency", f"光伏并网逆变器（{band}）最大转换效率", "%", maximum, comparison="gte", page=3, clause="5.1.2", table="表2", number=number, source_file=file, digest=digest, product_key=pkey)]
        products.append({"id": pkey, "name": f"光伏并网逆变器（{band}）", "description": "不适用于20kW及以下以及500kW以上组串式逆变器。", "input_definitions": [], "indicators": inds})
    return make_standard(number, title, "2026", "2026-06-27", "2027-01-01", file, digest, products, ["CAT-064-NEW"])


def build_47835() -> dict:
    number = "GB 47835-2026"; title = "硅单晶单位产品能源消耗限额"
    file = "GB+47835-2026 硅单晶单位产品能源消耗限额.pdf"; digest = sha256(SOURCE / file)
    products = []
    for key, name, unit, levels, table in [("monocrystalline-silicon", "硅单晶（方棒）", "kgce/kg", ("1.90", "2.16", "2.58"), "表1"), ("monocrystalline-wafer", "硅单晶片", "kgce/百万片", ("5900", "7005", "9525"), "表2")]:
        products.append({"id": key, "name": name, "description": "按合格产品产量计算；硅片可比产量需按标准折标系数处理。", "input_definitions": [], "indicators": [indicator(f"GB_47835-2026.{key}.comprehensive-energy", f"{name}单位产品综合能耗", unit, levels, page=1, clause="4.1" if key.endswith("silicon") else "4.2", table=table, number=number, source_file=file, digest=digest, product_key=key, detail=True, notes=["硅片产品应按表3、表4及6.3进行产量折标" if key.endswith("wafer") else "按合格硅单晶方棒产量计算", "original_pdf_transcribed", "requires_independent_review"])]})
    return make_standard(number, title, "2026", "2026-06-27", "2027-01-01", file, digest, products, ["CAT-065-NEW"])


def main() -> None:
    scope_path = DATA / "scope-44.json"
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    standards = ["GB 29447-2026" if x == "GB 29447-2022" else x for x in scope["standards"]]
    standards = list(dict.fromkeys(standards + ["GB 47834-2026", "GB 47835-2026"]))
    scope["scope_name"] = "用户确认的46项强制性能耗限额标准"
    scope["standards"] = standards
    scope_path.write_text(json.dumps(scope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    old = DEFINITIONS / "gb-29447-2022.json"
    if old.exists():
        archive = ROOT / "work" / "obsolete-standards"
        archive.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old), str(archive / old.name))
    for definition in (build_29447(), build_47834(), build_47835()):
        (DEFINITIONS / f"{definition['id']}.json").write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    catalog = json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))
    rows = [r for r in catalog["standards"] if r["number"] not in {"GB 29447-2022", "GB 29447-2026", "GB 47834-2026", "GB 47835-2026"}]
    for number, seq, title, file in [("GB 29447-2026", 29, "硅多晶和锗单位产品能源消耗限额", "GB+29447-2026 硅多晶和锗单位产品能源消耗限额.pdf"), ("GB 47834-2026", 64, "晶体硅光伏组件和逆变器能效限定值及能效等级", "GB+47834-2026 晶体硅光伏组件和逆变器能效限定值及能效等级.pdf"), ("GB 47835-2026", 65, "硅单晶单位产品能源消耗限额", "GB+47835-2026 硅单晶单位产品能源消耗限额.pdf")]:
        rows.append({"sequence": seq, "id": number.lower().replace(" ", "-"), "number": number, "title": title, "publication_date": "2026-06-27", "effective_date": "2027-01-01", "remark": "代替GB 29447-2022" if number == "GB 29447-2026" else "新发布", "source_file": file, "source_sha256": sha256(SOURCE / file), "status": "reviewed"})
    rows.sort(key=lambda r: r["sequence"])
    catalog.update({"catalog_name": "用户确认的46项强制性能耗限额标准", "generated_at": datetime.now(timezone.utc).isoformat(), "standard_count": len(rows), "scope_version": "46", "standards": rows})
    catalog["catalog_sha256"] = catalog.get("catalog_sha256", "")
    (DATA / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    corrections = json.loads((DATA / "corrections" / "catalog-corrections.json").read_text(encoding="utf-8"))
    corrections["corrections"] = [c for c in corrections["corrections"] if c.get("standard_number") != "GB 29447-2022" and c.get("id") not in {"CAT-029-REPLACE", "CAT-064-NEW", "CAT-065-NEW"}] + [
        {"id": "CAT-029-REPLACE", "standard_number": "GB 29447-2026", "fields": ["number", "title", "publication_date", "effective_date", "remark"], "original": {"number": "GB 29447-2022", "title": "多晶硅和锗单位产品能源消耗限额", "publication_date": "2022-12-29", "effective_date": "2024-01-01", "remark": ""}, "corrected": {"number": "GB 29447-2026", "title": "硅多晶和锗单位产品能源消耗限额", "publication_date": "2026-06-27", "effective_date": "2027-01-01", "remark": "代替GB 29447-2022"}, "reason": "用户确认GB 29447-2022已被GB 29447-2026替代，按新标准原文封面更新。", "source": "GB+29447-2026 硅多晶和锗单位产品能源消耗限额.pdf"},
        {"id": "CAT-064-NEW", "standard_number": "GB 47834-2026", "fields": ["scope"], "original": {}, "corrected": {"scope": "纳入当前强制标准范围"}, "reason": "用户确认新增标准。", "source": "GB 47834-2026 原文封面"},
        {"id": "CAT-065-NEW", "standard_number": "GB 47835-2026", "fields": ["scope"], "original": {}, "corrected": {"scope": "纳入当前强制标准范围"}, "reason": "用户确认新增标准。", "source": "GB 47835-2026 原文封面"},
    ]
    (DATA / "corrections" / "catalog-corrections.json").write_text(json.dumps(corrections, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"scope={len(standards)} definitions={len(list(DEFINITIONS.glob('*.json')))} indicators={sum(len(i['indicators']) for d in [build_29447(), build_47834(), build_47835()] for i in d['products'])}")


if __name__ == "__main__":
    main()
