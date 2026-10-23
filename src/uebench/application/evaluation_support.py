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
from dataclasses import dataclass
from types import MappingProxyType

from uebench.domain.models import StandardDefinition

__all__ = [
    "FORMAL_EVALUATION_SUPPORTED_LABEL",
    "FORMAL_EVALUATION_UNSUPPORTED_LABEL",
    "MappingConfirmation",
    "SUPPORTED_EVALUATION_STANDARD_IDS",
    "evaluation_support_label",
    "filter_formally_evaluable",
    "mapping_confirmation",
    "standard_confirmation_message",
    "supports_formal_evaluation",
]


#: Canonical ids of the standards this software formally supports evaluating.
#: 0.2.0: GB 29446-2019 only.  See the module docstring before widening this.
SUPPORTED_EVALUATION_STANDARD_IDS: frozenset[str] = frozenset({"gb-29446-2019"})


#: User-facing Chinese labels.  They are constants, not computed strings, so the
#: wording is reviewable in one place and cannot drift between screens.
FORMAL_EVALUATION_SUPPORTED_LABEL = "已纳入正式评价范围"
FORMAL_EVALUATION_UNSUPPORTED_LABEL = "尚未纳入正式评价范围"


@dataclass(frozen=True)
class MappingConfirmation:
    """Approval evidence for a business mapping, separate from software support."""

    confirmed: bool
    version: str | None = None
    approved_on: str | None = None
    source: str | None = None


# Only approved mapping evidence belongs here. An absent id is pending review;
# installed legacy rule data must never be promoted into approval evidence.
_MAPPING_CONFIRMATIONS = MappingProxyType({
    "gb-29446-2019": MappingConfirmation(
        confirmed=True,
        version="2026-10-18 已批准版",
        approved_on="2026-10-18",
        source="standards/mappings/GB29446-2019/标准映射表_2026-10-18_已批准.md",
    ),
    "gb-16780-2021": MappingConfirmation(
        confirmed=True,
        version="V1.2 已批准版",
        approved_on="2026-10-13",
        source="standards/mappings/GB16780-2021/标准映射表_V1.2_修订稿.md",
    ),
})
_PENDING_MAPPING = MappingConfirmation(confirmed=False)


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


def mapping_confirmation(standard_id: str | StandardDefinition) -> MappingConfirmation:
    """Return explicit mapping approval evidence, or the pending default."""
    return _MAPPING_CONFIRMATIONS.get(_standard_id_of(standard_id), _PENDING_MAPPING)


def standard_confirmation_message(standard_id: str | StandardDefinition) -> str:
    """Brief library explanation without changing evaluation capability."""
    mapping = mapping_confirmation(standard_id)
    if not mapping.confirmed:
        return "业务映射待整理确认；旧规则未作为已验收依据。产品/工序、指标、单位及限值明细暂不展示。"
    mapping_part = f"业务映射已确认（{mapping.version}，{mapping.approved_on}）。"
    if supports_formal_evaluation(standard_id):
        return mapping_part + "当前已实现的业务核算能力已通过验收；软件交付与环境验收尚未全部完成。"
    return mapping_part + "软件接入及验收待完成。产品/工序、指标、单位及限值明细暂不展示。"


def filter_formally_evaluable(
    standards: Iterable[StandardDefinition],
) -> list[StandardDefinition]:
    """Return the definitions that are formally evaluable, in input order.

    This is the helper the UI needs to narrow a library listing down to the
    standards it may offer as a formal evaluation task.
    """
    return [definition for definition in standards if supports_formal_evaluation(definition)]
