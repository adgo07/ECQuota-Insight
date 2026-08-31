from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.normalize_standard_identity import IdentityError, normalize_root, resolve_family_id


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
    assert updated_current["marker"] == "keep"
    assert updated_old["marker"] == "keep-old"

    second = normalize_root(root, replacements, apply=False, include_retired=False)
    assert second["changed_count"] == 0
    assert second["already_normalized_count"] == 2