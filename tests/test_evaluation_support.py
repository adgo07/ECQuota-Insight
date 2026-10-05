"""Tests for the formal software evaluation support registry.

The registry exists because "a standard is installed in the library" used to be
conflated with "the software formally supports evaluating it", which made 43 of
48 installed standards look evaluable.  These tests pin the 0.2.0 owner decision
(GB 29446-2019 only) and prove the decision is independent of
``StandardDefinition.publication_status``.

The definitions are read from ``data/definitions`` — the formal runtime source
(``standards/development/manifest.json``: ``"formal_runtime_source": "data"``),
i.e. exactly what ships.  They deliberately do **not** come from
``standards/development/scope-65``: that directory is a superseded historical
comparison snapshot (``"legacy_scopes": ["scope-65"]``) kept only for traceability,
so loading it here would have asserted the 0.2.0 capability decision against
stale data.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from uebench.application.evaluation_support import (
    FORMAL_EVALUATION_SUPPORTED_LABEL,
    FORMAL_EVALUATION_UNSUPPORTED_LABEL,
    SUPPORTED_EVALUATION_STANDARD_IDS,
    evaluation_support_label,
    filter_formally_evaluable,
    supports_formal_evaluation,
)
from uebench.domain.models import PublicationStatus, StandardDefinition

ROOT = Path(__file__).resolve().parents[1]
#: Formal runtime truth source: the published definitions that ship with the product.
DEFINITIONS = ROOT / "data" / "definitions"
MODULE = ROOT / "src" / "uebench" / "application" / "evaluation_support.py"

SUPPORTED_ID = "gb-29446-2019"

#: Real installed standards that are NOT in the 0.2.0 formal evaluation scope.
UNSUPPORTED_INSTALLED_IDS = ("gb-16780-2021", "gb-21252-2023", "gb-21342-2025")

_CHINESE = re.compile(r"[\u4e00-\u9fff]")


def _definition(standard_id: str) -> StandardDefinition:
    """Load a real installed definition from the formal runtime source."""
    path = DEFINITIONS / f"{standard_id}.json"
    assert path.is_file(), f"{standard_id} must be a real installed standard"
    return StandardDefinition.model_validate_json(path.read_text(encoding="utf-8"))


def _installed_definitions() -> list[StandardDefinition]:
    return [
        StandardDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(DEFINITIONS.glob("*.json"))
    ]


# ---------------------------------------------------------------------------
# The registry itself
# ---------------------------------------------------------------------------


def test_registry_is_a_frozenset_with_exactly_the_supported_id() -> None:
    assert isinstance(SUPPORTED_EVALUATION_STANDARD_IDS, frozenset)
    assert SUPPORTED_EVALUATION_STANDARD_IDS == frozenset({"gb-29446-2019"}), (
        "0.2.0 formally supports only GB 29446-2019; widening this set is an owner "
        "decision that must update this test and carry its own evidence"
    )


def test_supported_standard_is_formally_evaluable() -> None:
    assert supports_formal_evaluation("gb-29446-2019") is True
    # A definition object is accepted too, so a UI call site cannot silently get
    # "unsupported" for the one supported standard.
    assert supports_formal_evaluation(_definition("gb-29446-2019")) is True


def test_other_installed_standards_are_not_formally_evaluable() -> None:
    for standard_id in UNSUPPORTED_INSTALLED_IDS:
        definition = _definition(standard_id)
        assert definition.id == standard_id
        assert supports_formal_evaluation(standard_id) is False
        assert supports_formal_evaluation(definition) is False


def test_installed_library_has_exactly_one_formally_evaluable_standard() -> None:
    """The whole published runtime library: one evaluable standard, not 43.

    ``data/definitions`` is the set that actually ships (48 published standards),
    so "43 of 48 looked evaluable" is asserted against the real product data
    rather than against a superseded development snapshot.
    """
    definitions = _installed_definitions()
    assert len(definitions) == 48, "正式运行库必须仍是 48 项已发布标准"
    evaluable = filter_formally_evaluable(definitions)
    assert [definition.id for definition in evaluable] == [SUPPORTED_ID]


def test_filter_preserves_input_order_and_drops_unsupported() -> None:
    unsupported = _definition(UNSUPPORTED_INSTALLED_IDS[0])
    supported = _definition(SUPPORTED_ID)
    other = _definition(UNSUPPORTED_INSTALLED_IDS[1])

    assert filter_formally_evaluable([unsupported, supported, other]) == [supported]
    assert filter_formally_evaluable([unsupported, other]) == []
    assert filter_formally_evaluable([]) == []


# ---------------------------------------------------------------------------
# User-facing labels
# ---------------------------------------------------------------------------


def test_labels_differ_and_are_chinese() -> None:
    supported = evaluation_support_label(SUPPORTED_ID)
    unsupported = evaluation_support_label(UNSUPPORTED_INSTALLED_IDS[0])

    assert supported != unsupported
    assert _CHINESE.search(supported), supported
    assert _CHINESE.search(unsupported), unsupported
    assert (supported, unsupported) == (
        FORMAL_EVALUATION_SUPPORTED_LABEL,
        FORMAL_EVALUATION_UNSUPPORTED_LABEL,
    )
    assert supported == "已纳入正式评价范围"
    assert unsupported == "尚未纳入正式评价范围"


def test_label_accepts_a_definition_as_well_as_an_id() -> None:
    assert evaluation_support_label(_definition(SUPPORTED_ID)) == FORMAL_EVALUATION_SUPPORTED_LABEL
    assert (
        evaluation_support_label(_definition(UNSUPPORTED_INSTALLED_IDS[0]))
        == FORMAL_EVALUATION_UNSUPPORTED_LABEL
    )


# ---------------------------------------------------------------------------
# Guard: the registry must not read publication_status
# ---------------------------------------------------------------------------


def test_published_but_unsupported_standard_stays_unsupported() -> None:
    """`publication_status=published` must not buy a standard evaluation support."""
    definition = _definition(UNSUPPORTED_INSTALLED_IDS[0])
    published = definition.model_copy(update={"publication_status": PublicationStatus.PUBLISHED})

    assert published.publication_status is PublicationStatus.PUBLISHED
    assert supports_formal_evaluation(published.id) is False
    assert supports_formal_evaluation(published) is False
    assert evaluation_support_label(published) == FORMAL_EVALUATION_UNSUPPORTED_LABEL


def test_supported_standard_stays_supported_for_every_lifecycle_status() -> None:
    """Conversely, a non-published status must not remove formal support."""
    definition = _definition(SUPPORTED_ID)
    for status in PublicationStatus:
        variant = definition.model_copy(update={"publication_status": status})
        assert variant.publication_status is status
        assert supports_formal_evaluation(variant.id) is True, status
        assert supports_formal_evaluation(variant) is True, status
        assert evaluation_support_label(variant) == FORMAL_EVALUATION_SUPPORTED_LABEL


def test_draft_but_supported_standard_is_still_supported() -> None:
    draft = _definition(SUPPORTED_ID).model_copy(
        update={"publication_status": PublicationStatus.DRAFT}
    )
    assert draft.publication_status is PublicationStatus.DRAFT
    assert supports_formal_evaluation("gb-29446-2019") is True


def test_module_never_references_publication_status() -> None:
    """The capability source must not read or write the lifecycle field.

    The module docstring *explains* why ``publication_status`` is irrelevant, so a
    raw text scan would be a false positive.  This walks the AST instead and fails
    on any real reference: attribute access (``definition.publication_status``),
    bare name, or the string key used by dict/``getattr`` style access.
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    references: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "publication_status":
            references.append(f"attribute access on line {node.lineno}")
        elif isinstance(node, ast.Name) and node.id == "publication_status":
            references.append(f"name reference on line {node.lineno}")
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.strip() == "publication_status"
        ):
            references.append(f"string key on line {node.lineno}")

    assert references == [], (
        "evaluation_support.py must not read or write StandardDefinition.publication_status; "
        f"software capability is not standard lifecycle: {references}"
    )


def test_unknown_and_empty_ids_are_unsupported() -> None:
    assert supports_formal_evaluation("") is False
    assert supports_formal_evaluation("gb-29446-2018") is False
    assert supports_formal_evaluation("GB 29446-2019") is False
    assert evaluation_support_label("") == FORMAL_EVALUATION_UNSUPPORTED_LABEL
