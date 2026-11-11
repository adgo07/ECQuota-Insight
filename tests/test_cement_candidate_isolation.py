"""未发布候选不进入默认生产源；严格交付门禁继续全量执行。"""
import hashlib
import json
from pathlib import Path
import zipfile

from tools.check_delivery_scope import validate_scope
from uebench.application.evaluation_support import supports_formal_evaluation
from uebench.domain.gb16780 import adopted
from uebench.domain.models import StandardDefinition

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "standards/development/GB16780-2021/gb-16780-2021-r3-candidate.json"


def test_only_unpublished_candidate_has_r2_and_preserves_copied_identity():
    assert hashlib.sha256((ROOT / "tests/fixtures/gb16780/pr38-r2-unpublished.json").read_bytes()).hexdigest() == "1e9db2b766c4ce84c0e21d6c899481b86c0e009749f6f63de068544a1211cfa2"
    definition = StandardDefinition.model_validate_json(CANDIDATE.read_text(encoding="utf-8"))
    assert adopted(definition)
    assert not supports_formal_evaluation(definition)
    assert len(list(CANDIDATE.parent.glob("*.json"))) == 1


def test_production_cement_stays_exact_legacy_r1_and_matches_real_signed_pin():
    path = ROOT / "data/definitions/gb-16780-2021.json"
    # Git文本checkout可转换CRLF；规范化后必须等于298a966原Git字节，候选则禁行尾转换。
    assert hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == "f60941f5d9b9e92b959176d0c8cc7ac91c3ba30e37bf62dfbdeb2ede20cb9ab9"
    source = StandardDefinition.model_validate_json(path.read_text(encoding="utf-8"))
    assert source.rule_revision == 1 and not adopted(source)
    package = ROOT / "release/standard-packages/initial-standard-package-published.uebench"
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        definitions = [StandardDefinition.model_validate_json(archive.read(e["path"])) for e in manifest["files"] if e["kind"] == "definition"]
    assert next(d for d in definitions if d.id == source.id) == source
    # 真实门禁全48项检查，没有“忽略水泥”或未发布例外开关。
    assert validate_scope(package_path=package)["formal_evaluation_count"] == 1
