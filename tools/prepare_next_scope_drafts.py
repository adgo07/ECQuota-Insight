from __future__ import annotations

"""Prepare the next full-scope draft workspace without changing the release data.

The current published data set is deliberately kept untouched.  This tool
creates an isolated current-plus-draft workspace from the archive catalog and
current definitions.  Explicit replacement mappings remove superseded standards
(for example GB 29141/29437/29441-2012) and add their replacement definition.
It may add clearly labelled draft candidates from extracted source tables, but
never changes a rule to ``published``.
"""

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

from uebench.domain.models import StandardDefinition


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "work" / "archive-data-63"
CURRENT = ROOT / "data"
SOURCE = Path(r"G:\标准  规范\02_能耗限额_终端产品\单位产品限额\现行强制文本")

# Standards explicitly confirmed as superseded.  The replacement is taken from
# the current published catalog; old definitions are not copied into the active
# isolated scope.  Keep this mapping auditable when future standards change.
REPLACEMENTS = {
    "GB 29447-2022": "GB 29447-2026",
    "GB 29141-2012": "GB 29141-2024",
    "GB 29437-2012": "GB 29141-2024",
    "GB 29441-2012": "GB 29141-2024",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z一-龥]+", "_", value).strip("_")[:80] or "item"


def node(op: str, *, value: str | None = None, input_key: str | None = None,
         args: list[dict] | None = None, unit: str | None = None,
         label: str | None = None) -> dict:
    return {"op": op, "value": value, "input_key": input_key, "args": args or [],
            "cases": [], "rows": [], "default": None, "label": label,
            "unit": unit, "round_places": None}


def constant(value: str, unit: str) -> dict:
    return node("constant", value=str(value), unit=unit)


def candidate_indicator(number: str, source_file: str, source_sha: str,
                        row: dict, index: int, *, source_kind: str) -> dict | None:
    values = [str(value) for value in row.get("numbers", [])][:3]
    if len(values) != 3:
        return None
    label_lines = [str(item) for item in row.get("label_lines", []) if item]
    joined = "".join(re.sub(r"\s+", "", item) for item in label_lines)
    product = joined[:80] or str(row.get("row_prefix") or "标准产品/工序候选")
    metric_tokens = ("单位产品", "单位能耗", "电力单耗", "综合能耗", "产品能耗", "能源消耗")
    split_at = min((joined.find(token) for token in metric_tokens if joined.find(token) >= 0), default=-1)
    name = joined[split_at:] if split_at > 0 else f"{product}单位产品能源消耗"
    unit = str(row.get("unit") or "kgce/t")
    key = f"actual.{slug(number)}.draft_{index}"
    return {
        "id": f"{slug(number)}.draft_candidate_{index}",
        "name": name,
        "unit": unit,
        "comparison": "lte",
        "input_definitions": [{
            "key": key, "label": f"{name}实际值", "data_type": "decimal", "unit": unit,
            "required": True, "required_if": None, "modes": ["DIRECT"],
            "minimum": "0", "maximum": None, "choices": [],
            "description": "候选规则；完成产品、条件、公式和页码独立复核前不得用于正式评价。",
        }],
        "applicability": {"op": "always"},
        "direct_input_key": key,
        "detail_formula": node("per_unit", args=[
            node("input", input_key="energy.total_standard_coal"),
            node("input", input_key="production.total_equivalent"),
        ], unit=unit, label="单位产品实际值（候选通用公式）"),
        "base_thresholds": {f"level_{i}": constant(values[i - 1], unit) for i in (1, 2, 3)},
        "thresholds": {f"level_{i}": constant(values[i - 1], unit) for i in (1, 2, 3)},
        "display_places": 2,
        "source_references": [{
            "standard_number": number, "source_file": source_file, "source_sha256": source_sha,
            "page": max(1, int(row.get("page") or 1)),
            "clause": "第4章能耗限额等级（候选，待复核）",
            "table": row.get("table") or "原文表格候选",
            "note": f"{source_kind}候选；必须人工对照原文后才能进入确认表。",
        }],
        "notes": ["candidate_from_original_pdf", "not_for_formal_evaluation", "requires_independent_review"],
    }


def make_product(indicator: dict, index: int) -> dict:
    return {
        "id": f"draft-candidate-{index}",
        "name": indicator["name"],
        "description": "自动提取候选，待标准原文独立复核。",
        "input_definitions": [],
        "indicators": [indicator],
    }


# Clear table transcriptions retained as draft-only candidates.  These values
# are intentionally not promoted to reviewed/published here; a second person
# must compare every row with the source PDF before formal use.
MANUAL_ROWS: dict[str, list[dict]] = {
    "GB 29441-2012": [
        {"label_lines": ["稀硝酸", "单位产品综合能耗"], "unit": "kgce/t", "numbers": ["0", "20", "160"], "page": 4, "table": "4.1～4.3"},
    ],
    "GB 29450-2012": [
        {"label_lines": ["池窑法 E玻璃纤维纱（纤维直径≤9μm）"], "unit": "kgce/t", "numbers": ["750", "750", "900"], "page": 4, "table": "表1、表2、表3"},
        {"label_lines": ["池窑法 E(ECR)玻璃纤维纱（纤维直径＞9μm）"], "unit": "kgce/t", "numbers": ["550", "550", "700"], "page": 4, "table": "表1、表2、表3"},
    ],
    "GB 31823-2021": [
        {"label_lines": ["集装箱码头"], "unit": "tce/10^4 TEU", "numbers": ["24", "28", "45"], "page": 4, "table": "表1"},
        {"label_lines": ["干散货码头"], "unit": "tce/10^4 t", "numbers": ["1.8", "2.0", "2.7"], "page": 4, "table": "表1"},
        {"label_lines": ["原油码头"], "unit": "tce/10^4 t", "numbers": ["0.36", "0.51", "0.88"], "page": 4, "table": "表1"},
    ],
    "GB 36887-2018": [
        {"label_lines": [f"合成革第{name}类"], "unit": "kgce/tsl", "numbers": [l1, l2, l3], "page": 4, "table": "表2"}
        for name, l1, l2, l3 in [("1", "250", "275", "400"), ("2", "200", "220", "320"), ("3", "50", "55", "80"), ("4", "250", "275", "400"), ("5", "500", "550", "800")]
    ] + [
        {"label_lines": ["DMF回收"], "unit": "kgce/tdmf", "numbers": ["350", "380", "500"], "page": 4, "table": "表2"},
    ],
    "GB 36890-2018": [
        {"label_lines": ["日用瓷一次（烧成温度≤1280℃）"], "unit": "kgce/t", "numbers": ["500", "630", "740"], "page": 4, "table": "表1、表2、表3"},
        {"label_lines": ["日用瓷一次（烧成温度＞1280℃）"], "unit": "kgce/t", "numbers": ["600", "730", "860"], "page": 4, "table": "表1、表2、表3"},
        {"label_lines": ["日用瓷二次（含二次以上）"], "unit": "kgce/t", "numbers": ["740", "890", "1050"], "page": 4, "table": "表1、表2、表3"},
        {"label_lines": ["日用陶器一次（烧成温度≤1280℃）"], "unit": "kgce/t", "numbers": ["430", "550", "640"], "page": 4, "table": "表1、表2、表3"},
        {"label_lines": ["日用陶器二次（含二次以上）"], "unit": "kgce/t", "numbers": ["660", "830", "980"], "page": 4, "table": "表1、表2、表3"},
    ],
    "GB 40877-2021": [
        {"label_lines": ["硅酸铝纤维（1000℃、1200℃、1250℃）"], "unit": "kgce/t", "numbers": ["208", "228", "263"], "page": 4, "table": "表1"},
        {"label_lines": ["硅酸铝纤维（1350℃、1400℃、1500℃）"], "unit": "kgce/t", "numbers": ["245", "256", "311"], "page": 4, "table": "表1"},
        {"label_lines": ["硅酸铝纤维制品-针刺毯"], "unit": "kgce/t", "numbers": ["65", "77", "85"], "page": 4, "table": "表1"},
        {"label_lines": ["硅酸铝纤维制品-湿法制品（连续轧制）"], "unit": "kgce/t", "numbers": ["410", "465", "486"], "page": 4, "table": "表1"},
        {"label_lines": ["硅酸铝纤维制品-湿法制品（真空吸滤）"], "unit": "kgce/t", "numbers": ["750", "780", "836"], "page": 4, "table": "表1"},
    ],
    "GB 40878-2021": [
        {"label_lines": ["淀粉原料发酵法"], "unit": "kgce/t", "numbers": ["272", "280", "324"], "page": 3, "table": "表1"},
        {"label_lines": ["淀粉原料酶法"], "unit": "kgce/t", "numbers": ["260", "268", "290"], "page": 3, "table": "表1"},
        {"label_lines": ["葡萄糖原料催化氧化法"], "unit": "kgce/t", "numbers": ["156", "156", "160"], "page": 3, "table": "表1"},
    ],
    "GB 29435-2012": [
        {"label_lines": [name, "稀土产品单位产品综合能耗"], "unit": "tce/t", "numbers": [advanced, access, existing], "page": 4, "table": "表1、表2、表3"}
        for name, existing, access, advanced in [
            ("氧化镧", "2.54", "2.31", "2.19"), ("氧化铈", "2.86", "2.60", "2.47"),
            ("氧化镨", "2.88", "2.62", "2.49"), ("氧化钕", "2.84", "2.58", "2.45"),
            ("氧化钐", "2.61", "2.37", "2.25"), ("氧化铕", "2.99", "2.72", "2.58"),
            ("氧化钆", "2.25", "2.04", "1.94"), ("氧化铽", "2.50", "2.27", "2.16"),
            ("氧化镝", "2.50", "2.27", "2.16"), ("氧化钬", "2.29", "2.08", "1.98"),
            ("氧化铒", "2.27", "2.07", "1.97"), ("氧化铥", "2.35", "2.13", "2.02"),
            ("氧化镱", "2.41", "2.20", "2.09"), ("灯用稀土三基色荧光粉-红", "0.94", "0.85", "0.81"),
            ("灯用稀土三基色荧光粉-绿", "3.09", "2.81", "2.67"), ("灯用稀土三基色荧光粉-蓝", "4.48", "4.07", "3.87"),
            ("氧化镥", "2.52", "2.29", "2.18"), ("氧化钇", "2.39", "2.17", "2.06"),
            ("荧光级氧化钇铕", "2.26", "2.06", "1.96"), ("镨钕氧化物", "2.71", "2.47", "2.35"),
            ("金属镧", "1.53", "1.39", "1.32"), ("金属铈", "1.28", "1.16", "1.10"),
            ("金属镨", "1.42", "1.29", "1.23"), ("金属钕", "1.33", "1.21", "1.15"),
            ("金属钐", "3.65", "3.32", "3.15"), ("金属镝", "2.60", "2.36", "2.24"),
            ("镨钕合金", "1.42", "1.29", "1.23"), ("钆铁合金", "1.52", "1.38", "1.31"),
            ("镝铁合金", "1.58", "1.44", "1.37"), ("混合稀土金属", "1.87", "1.70", "1.62"),
            ("稀土抛光粉", "1.80", "1.64", "1.56"),
        ]
    ],
    "GB 29437-2012": [
        {"label_lines": [name, "工业冰醋酸单位产品综合能耗"], "unit": "kgce/t", "numbers": [advanced, access, existing], "page": 4, "table": "表1、表2、表3"}
        for name, existing, access, advanced in [
            ("羰基法（年产20万t醋酸）", "176", "124", "106"),
            ("酒精法-空气氧化乙醛", "500", "418", "418"),
            ("酒精法-氧气氧化乙醛", "505", "429", "429"),
            ("乙烯法", "429", "300", "300"),
        ]
    ],
    "GB 30182-2013": [
        {"label_lines": ["摩擦材料单位产品综合能耗"], "unit": "kgce/t", "numbers": ["115", "135", "175"], "page": 4, "table": "表1、表2、表3"},
        {"label_lines": ["摩擦材料单位产品电耗"], "unit": "kWh/t", "numbers": ["800", "1000", "1300"], "page": 4, "table": "表1、表2、表3"},
    ],
    "GB 32044-2015": [
        {"label_lines": [name, "糖单位产品能耗"], "unit": "kgce/t", "numbers": [advanced, access, existing], "page": 3, "table": "表1、表2、表3"}
        for name, existing, access, advanced in [
            ("甘蔗制糖", "550", "320", "225"), ("甜菜制糖", "630", "360", "318"), ("炼糖", "320", "220", "200"),
        ]
    ],
    "GB 45246-2025": [
        {"label_lines": [name, "单位产品综合能耗"], "unit": "kgce/m³", "numbers": [level1, level2, level3], "page": 5, "table": "表1"}
        for name, level1, level2, level3 in [
            ("中密度纤维板全工序", "118", "130", "180"),
            ("中密度纤维板前段工序", "200", "230", "260"),
            ("中密度纤维板后段工序", "170", "197", "223"),
            ("高密度纤维板", "110", "130", "150"),
            ("普通胶合板全工序", "60", "67", "73"),
            ("普通型刨花板", "100", "110", "150"),
        ]
    ],
}


def main() -> None:
    parser = argparse.ArgumentParser(description="建立当前标准范围的隔离draft工作区")
    parser.add_argument("--output", type=Path, default=ROOT / "work" / "next-scope-63")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    data_dir = output / "data"
    shutil.copytree(CURRENT, data_dir)

    archive_catalog = json.loads((ARCHIVE / "catalog.json").read_text(encoding="utf-8"))
    current_catalog = json.loads((CURRENT / "catalog.json").read_text(encoding="utf-8"))
    current_by_number = {item["number"]: item for item in current_catalog["standards"]}
    rows: list[dict] = []
    for item in archive_catalog["standards"]:
        number = item["number"]
        replacement = REPLACEMENTS.get(number)
        if replacement:
            replacement_item = current_by_number.get(replacement)
            if replacement_item:
                rows.append(replacement_item)
            continue
        rows.append(current_by_number.get(number, item))
    for number in ("GB 47834-2026", "GB 47835-2026"):
        rows.append(current_by_number[number])
    rows = sorted({item["number"]: item for item in rows}.values(), key=lambda item: item["sequence"])
    for item in rows:
        source = SOURCE / item["source_file"]
        item["source_sha256"] = sha256(source)
        if item["number"] not in current_by_number:
            item["status"] = "draft"
    catalog = {
        "schema_version": "1.0", "catalog_name": "当前目录及新增标准的当前范围",
        "catalog_sha256": "", "generated_at": "", "standard_count": len(rows),
        "scope_version": "current-draft", "standards": rows,
    }
    (data_dir / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    scope = {"schema_version": "1.0", "scope_name": "当前目录及新增标准的当前范围",
             "standards": [item["number"] for item in rows]}
    scope_text = json.dumps(scope, ensure_ascii=False, indent=2) + "\n"
    # Keep loader compatibility while exposing a canonical current-scope alias.
    (data_dir / "scope-44.json").write_text(scope_text, encoding="utf-8")
    (data_dir / "scope-63.json").write_text(scope_text, encoding="utf-8")
    (data_dir / "scope-65.json").write_text(scope_text, encoding="utf-8")

    archive_defs = {path.stem: path for path in (ARCHIVE / "definitions").glob("*.json")}
    definitions_dir = data_dir / "definitions"
    for number, catalog_item in ((item["number"], item) for item in rows):
        filename = re.sub(r"[^a-z0-9]+", "-", number.lower()).strip("-") + ".json"
        target = definitions_dir / filename
        if number == "GB 29447-2026" or target.exists() and json.loads(target.read_text(encoding="utf-8")).get("publication_status") == "published":
            continue
        if target.exists():
            continue
        archived = archive_defs.get(Path(filename).stem)
        if archived:
            definition = json.loads(archived.read_text(encoding="utf-8"))
            definition["source_file"] = catalog_item["source_file"]
            definition["source_sha256"] = catalog_item["source_sha256"]
            target.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    original = json.loads((ROOT / "work" / "verification" / "original-candidates.json").read_text(encoding="utf-8"))
    compilation = json.loads((ROOT / "work" / "verification" / "compilation-candidates.json").read_text(encoding="utf-8"))["rows"]
    by_stem = {Path(item["source_file"]).stem: item["number"] for item in rows}
    original_by_number: dict[str, list[dict]] = {}
    for stem, candidates in original.items():
        if stem in by_stem:
            original_by_number.setdefault(by_stem[stem], []).extend(candidates)
    for row in compilation:
        original_by_number.setdefault(str(row["standard_number"]), []).append(row)
    for number, rows_for_number in MANUAL_ROWS.items():
        if not original_by_number.get(number):
            original_by_number[number] = rows_for_number

    generated: Counter[str] = Counter()
    for item in rows:
        number = item["number"]
        target = definitions_dir / (re.sub(r"[^a-z0-9]+", "-", number.lower()).strip("-") + ".json")
        if not target.exists():
            continue
        definition = json.loads(target.read_text(encoding="utf-8"))
        if definition.get("publication_status") == "published" or definition.get("products"):
            continue
        candidates = original_by_number.get(number, [])
        indicators = []
        for index, row in enumerate(candidates, 1):
            indicator = candidate_indicator(number, item["source_file"], item["source_sha256"], row, index, source_kind="原文/汇编")
            if indicator:
                indicators.append(indicator)
        if indicators:
            definition["products"] = [make_product(indicator, index) for index, indicator in enumerate(indicators, 1)]
            definition["publication_status"] = "draft"
            target.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            generated[number] = len(indicators)

    errors = []
    for path in sorted(definitions_dir.glob("*.json")):
        try:
            StandardDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
    report = {
        "scope_count": len(rows), "published_count": sum(item["status"] == "published" for item in rows),
        "draft_count": sum(item["status"] == "draft" for item in rows),
        "generated_candidate_indicators": dict(generated), "errors": errors,
        "valid": not errors,
        "warning": "此工作区全部新增规则仍为draft，不能用于正式评价。",
    }
    (output / "prepare-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
