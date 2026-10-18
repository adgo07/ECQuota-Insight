"""Check the explicit boundary between editable definitions and delivery.

The current package carries 48 definitions, including historical GB 29141-2012.
Only GB 29446-2019 is authorized for formal evaluation. A draft can live in
data/definitions without crossing either boundary.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from uebench.domain.models import StandardDefinition  # noqa: E402

SCOPE = ROOT / "data/delivery-scope.json"
DEFINITIONS = ROOT / "data/definitions"
PINNED_PACKAGE = ROOT / "release/standard-packages/initial-standard-package-published.uebench"


def validate_scope(scope_path: Path = SCOPE, definitions_dir: Path = DEFINITIONS,
                   package_path: Path | None = None) -> dict[str, int]:
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    bundled = scope["bundled_definition_ids"]
    formal = scope["formal_evaluation_standard_ids"]
    if scope.get("schema_version") != "1.0":
        raise ValueError("交付范围清单版本不兼容")
    if len(bundled) != 48 or len(set(bundled)) != 48:
        raise ValueError("随包定义必须是明确的48项且无重复")
    if formal != ["gb-29446-2019"] or not set(formal) <= set(bundled):
        raise ValueError("正式评价范围必须且只能包含 GB 29446—2019")
    if "gb-29141-2012" not in bundled:
        raise ValueError("历史随包定义 GB 29141—2012 不得丢失")
    paths = {path.stem: path for path in definitions_dir.glob("*.json")}
    missing = set(bundled) - set(paths)
    if missing:
        raise ValueError(f"随包定义源文件缺失：{sorted(missing)}")
    for standard_id, path in paths.items():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("id") != standard_id:
            raise ValueError(f"定义 ID 与文件名不一致：{path}")
        if standard_id in bundled and payload.get("publication_status") != "published":
            raise ValueError(f"草稿不得进入随包清单：{standard_id}")
        if standard_id not in bundled and payload.get("publication_status") != "draft":
            raise ValueError(f"非随包定义须保持 draft：{standard_id}")
    if package_path is not None:
        with zipfile.ZipFile(package_path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            entries = [entry for entry in manifest["files"] if entry["kind"] == "definition"]
            package_definitions = {
                payload["id"]: payload
                for entry in entries
                for payload in [json.loads(archive.read(entry["path"]))]
            }
            ids = set(package_definitions)
        if ids != set(bundled) or len(entries) != 48:
            raise ValueError("签名包定义范围与显式随包清单不一致")
        for standard_id in bundled:
            current = StandardDefinition.model_validate_json(paths[standard_id].read_text(encoding="utf-8"))
            packaged = StandardDefinition.model_validate(package_definitions[standard_id])
            if packaged != current:
                raise ValueError(f"签名包与当前唯一机器定义源内容不一致：{standard_id}")
    return {"definition_count": len(paths), "bundled_count": len(bundled),
            "formal_evaluation_count": len(formal), "draft_count": len(paths) - len(bundled)}


def main() -> int:
    parser = argparse.ArgumentParser(description="校验开发、随包、正式评价范围")
    parser.add_argument("--package", type=Path, help="同时校验签名包的定义集合")
    args = parser.parse_args()
    try:
        print(json.dumps(validate_scope(package_path=args.package), ensure_ascii=False))
        return 0
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        print(f"交付范围校验失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
