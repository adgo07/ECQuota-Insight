"""Formal software evaluation support registry (application layer).

A standard that is *installed in the library* is not the same thing as a standard
whose evaluation the software *formally supports*.  For the 0.2.0 Windows desktop
release the owner decision is that exactly one standard is inside the formal
evaluation scope:

    GB 29446-2019《选煤电力消耗限额》 -> ``gb-29446-2019``

Every other installed standard may still be browsed, inspected and cited, but the
software does not claim a verified formal evaluation capability for it and must
not present it as if it did.

This module is the single, central, testable source of that capability decision.
It is a fixed constant set on purpose -- never a derivation:

* It must **never** be derived from ``StandardDefinition.publication_status``.
  That field describes the lifecycle of the standard *document* (draft /
  reviewed / published); it says nothing about the *software's* capability.  The
  defect this registry removes is precisely that conflation: 43 of 48 installed
  standards used to look evaluable only because their document was published.
  This module therefore does not read (or write) ``publication_status`` at all.
* Widening the supported set is an owner decision that needs real mapping,
  implementation and acceptance evidence elsewhere; here it stays a single
  visible one-line change, so an accidental or unreviewed widening is easy to
  spot -- and ``tests/test_evaluation_support.py`` asserts the exact set so a
  silent widening fails the suite.

Layer rules: application layer only.  This module must not import PySide6 and
must not import ``uebench.infrastructure`` (guarded by
``tests/test_architecture_boundaries.py``).  Importing ``uebench.domain.models``
is allowed.
"""

from __future__ import annotations

from collections.abc import Iterable

from uebench.domain.models import StandardDefinition

__all__ = [
    "FORMAL_EVALUATION_SUPPORTED_LABEL",
    "FORMAL_EVALUATION_UNSUPPORTED_LABEL",
    "SUPPORTED_EVALUATION_STANDARD_IDS",
    "evaluation_support_label",
    "filter_formally_evaluable",
    "supports_formal_evaluation",
]


#: Canonical ids of the standards this software formally supports evaluating.
#: 0.2.0: GB 29446-2019 only.  See the module docstring before widening this.
SUPPORTED_EVALUATION_STANDARD_IDS: frozenset[str] = frozenset({"gb-29446-2019"})


#: User-facing Chinese labels.  They are constants, not computed strings, so the
#: wording is reviewable in one place and cannot drift between screens.
FORMAL_EVALUATION_SUPPORTED_LABEL = "已纳入正式评价范围"
FORMAL_EVALUATION_UNSUPPORTED_LABEL = "尚未纳入正式评价范围"


def _standard_id_of(value: object) -> str | None:
    """Resolve ``value`` to a canonical standard id, or ``None`` when unknown.

    Accepts a plain id string as well as any object exposing a string ``id``
    (notably a ``StandardDefinition``), so a UI call site can pass whichever it
    happens to hold.  Passing a definition where an id is expected must not
    silently answer "unsupported" for the one supported standard.
    """
    if isinstance(value, str):
        return value
    candidate = getattr(value, "id", None)
    return candidate if isinstance(candidate, str) else None


def supports_formal_evaluation(standard_id: str | StandardDefinition) -> bool:
    """Return ``True`` only for standards inside the formal evaluation scope.

    ``standard_id`` may be the canonical id or a ``StandardDefinition``.  The
    answer depends solely on :data:`SUPPORTED_EVALUATION_STANDARD_IDS`; the
    definition's ``publication_status`` is deliberately ignored.
    """
    return _standard_id_of(standard_id) in SUPPORTED_EVALUATION_STANDARD_IDS


def evaluation_support_label(standard_id: str | StandardDefinition) -> str:
    """Return the Chinese user-facing support label for ``standard_id``."""
    if supports_formal_evaluation(standard_id):
        return FORMAL_EVALUATION_SUPPORTED_LABEL
    return FORMAL_EVALUATION_UNSUPPORTED_LABEL


def filter_formally_evaluable(
    standards: Iterable[StandardDefinition],
) -> list[StandardDefinition]:
    """Return the definitions that are formally evaluable, in input order.

    This is the helper the UI needs to narrow a library listing down to the
    standards it may offer as a formal evaluation task.
    """
    return [definition for definition in standards if supports_formal_evaluation(definition)]
