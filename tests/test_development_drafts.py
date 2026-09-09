from __future__ import annotations

import json
from pathlib import Path

from uebench.domain.models import PublicationStatus, StandardDefinition


ROOT = Path(__file__).resolve().parents[1]


def _development_definitions() -> list[StandardDefinition]:
    base = ROOT / "standards" / "development" / "scope-63"
    scope = json.loads((base / "scope-63.json").read_text(encoding="utf-8"))
    target = set(scope["standards"])
    definitions: list[StandardDefinition] = []
    for path in sorted((base / "definitions").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["number"] in target:
            definitions.append(StandardDefinition.model_validate(payload))
    return definitions


def test_all_development_drafts_are_structurally_reviewable() -> None:
    definitions = _development_definitions()
    drafts = [item for item in definitions if item.publication_status is PublicationStatus.DRAFT]

    assert len(definitions) == 63
    assert len(drafts) == 16
    for definition in drafts:
        assert definition.source_file
        assert definition.source_sha256 and len(definition.source_sha256) == 64
        assert definition.products
        for product in definition.products:
            assert product.name
            assert product.indicators
            for indicator in product.indicators:
                assert indicator.name
                assert indicator.unit
                assert indicator.source_references
                assert all(
                    reference.standard_number == definition.number and reference.page >= 1
                    for reference in indicator.source_references
                )
                levels = indicator.base_thresholds
                assert any(level is not None for level in (levels.level_1, levels.level_2, levels.level_3))


def test_development_drafts_cannot_enter_formal_scope() -> None:
    definitions = _development_definitions()
    drafts = [item for item in definitions if item.publication_status is PublicationStatus.DRAFT]
    assert drafts
    assert all(item.publication_status is not PublicationStatus.PUBLISHED for item in drafts)
