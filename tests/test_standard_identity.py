from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.build_catalog import standard_family_id, standard_version
from .test_engine import make_standard
from tools.normalize_standard_identity import IdentityError, normalize_catalog, normalize_root, resolve_family_id


def test_replacement_chain_resolves_to_terminal_family() -> None:
    replacements = {
        "GB 29437-2012": "GB 29141-2024",
        "GB 29141-2024": "GB 29141-2026",
    }
    assert resolve_family_id("gb 29437-2012", replacements) == "GB 29141"
    assert resolve_family_id("GB 16780-2021", replacements) == "GB 16780"


def test_replacement_cycle_is_rejected() -> None:
    with pytest.raises(IdentityError, match="循环"):
        resolve_family_id("GB 00001-2020", {"GB 00001-2020": "GB 00001-2021", "GB 00001-2021": "GB 00001-2020"})


def test_normalize_root_is_idempotent_and_does_not_change_rule_values(tmp_path: Path) -> None:
    root = tmp_path / "scope-63"
    definitions = root / "definitions"
    definitions.mkdir(parents=True)
    current = {"number": "GB 29141-2024", "version": "2024", "publication_status": "draft", "marker": "keep"}
    old = {"number": "GB 29437-2012", "version": "2012", "publication_status": "published", "marker": "keep-old"}
    (definitions / "current.json").write_text(json.dumps(current, ensure_ascii=False), encoding="utf-8")
    (definitions / "old.json").write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    replacements = {"GB 29437-2012": "GB 29141-2024"}

    report = normalize_root(root, replacements, apply=True, include_retired=False)
    assert report["changed_count"] == 2
    updated_current = json.loads((definitions / "current.json").read_text(encoding="utf-8"))
    updated_old = json.loads((definitions / "old.json").read_text(encoding="utf-8"))
    assert updated_current["standard_family_id"] == "GB 29141"
    assert updated_old["standard_family_id"] == "GB 29141"
    assert updated_current["rule_revision"] == 1
    assert updated_old["rule_revision"] == 1
    assert updated_current["marker"] == "keep"
    assert updated_old["marker"] == "keep-old"

    second = normalize_root(root, replacements, apply=False, include_retired=False)
    assert second["changed_count"] == 0
    assert second["already_normalized_count"] == 2

def test_catalog_identity_helpers_keep_family_and_edition_year_separate() -> None:
    assert standard_family_id("GB 29141-2024") == "GB 29141"
    assert standard_version("GB 29141-2024") == "2024"


def test_formal_definitions_have_explicit_family_and_revision_metadata() -> None:
    root = Path(__file__).resolve().parents[1]
    files = sorted((root / "data" / "definitions").glob("*.json"))
    assert files
    for path in files:
        definition = json.loads(path.read_text(encoding="utf-8"))
        assert definition["standard_family_id"] == definition["number"].rsplit("-", 1)[0]
        assert definition["rule_revision"] >= 1


def test_normalize_catalog_adds_family_and_revision_without_changing_numbers(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {
                "standards": [{"number": "GB 29437-2012", "title": "keep"}],
                "historical_standards": [{"number": "GB 29141-2012"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report = normalize_catalog(
        path,
        {"GB 29437-2012": "GB 29141-2024", "GB 29141-2012": "GB 29141-2024"},
        apply=True,
    )
    assert report["changed_count"] == 2
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["standards"][0]["standard_family_id"] == "GB 29141"
    assert payload["historical_standards"][0]["rule_revision"] == 1
    assert payload["standards"][0]["title"] == "keep"


def test_standard_definition_rejects_version_year_mismatch() -> None:
    payload = make_standard().model_dump(mode="json")
    payload["version"] = "2025"
    with pytest.raises(ValueError, match="版本年份"):
        make_standard().__class__.model_validate(payload)
