"""Pre-registered official source pages for the standards the software shows.

Owner decision: the software does not ship, store, mirror or directly open
standard PDF files.  The ordinary UI offers 「查看标准原文」 and opens a
**pre-registered, deterministic** page on 全国标准信息公共服务平台
(``https://std.samr.gov.cn/``), the platform operated by 国家市场监督管理总局 /
国家标准化管理委员会.

Design constraints:

* This module contains **only fixed constants**.  It performs no network access
  and no text retrieval at runtime, it calls no search service, and it never
  guesses a page address from a search hit.  Registration is a deliberate,
  reviewed act recorded together with its evidence below.
* An address is registered here only after it has actually been fetched and
  confirmed to resolve *and* to be about that standard.
* Unregistered standards return ``None``.  The UI then disables the button and
  shows :data:`NO_OFFICIAL_SOURCE_LABEL` ("官方来源地址尚未登记").  Inventing a
  plausible-looking address would be worse than reporting the gap, because a
  wrong address silently misleads a user who is checking a legal limit value.


Verified registration
=====================

``gb-29446-2019`` -- GB 29446-2019《选煤电力消耗限额》
-----------------------------------------------------

Registered address::

    https://std.samr.gov.cn/gb/search/gbDetailed?id=9A0A4FA998CDD4A5E05397BE0A0AD02D

Verification evidence (page fetched with the agent page-fetch tool, HTTP 200,
fetched twice on separate calls with identical content; local clock at fetch time
showed 2026-10-05):

* The page is served under the title block ``国家标准`` and shows the standard
  name ``选煤电力消耗限额`` with the English title
  ``The norm of the power consumption of coal washing``.
* Its status line reads ``国家标准 强制性 现行`` (national standard, mandatory,
  currently in force).
* Its 基础信息 block states: 标准号 ``GB 29446-2019``; 发布日期 ``2019-12-17``;
  实施日期 ``2020-07-01``; 全部代替标准 ``GB 29446-2012``; 中国标准分类号
  ``F10``; 国际标准分类号 ``27.010``; 技术委员会 ``全国能源基础与管理标准化技术
  委员会``; 归口部门 ``国家标准委``.
* These values match this repository's own rule snapshot
  ``standards/development/scope-65/definitions/gb-29446-2019.json``
  (``number`` GB 29446-2019, ``title`` 选煤电力消耗限额,
  ``publication_date`` 2019-12-17, ``effective_date`` 2020-07-01), so the page
  and the shipped rules describe the same document.
* The address is the *standard* page, not a plan page.  The same content is also
  served by the plan-style query ``?mode=p&id=JQGs%2Ffh4xNM%3D``, while the bare
  ``?id=JQGs%2Ffh4xNM%3D`` form answers HTTP 404; the hex identifier used above
  is the canonical form this module registers.  The revision plan for the same
  title (``20261402-Q-469``, ``id=4C4597F6CA531E8EE06397BE0A0AECD3``) is a
  different document and is deliberately **not** registered.

No other standard has a verified address yet, so
:data:`OFFICIAL_SOURCE_URLS` holds exactly one entry.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "NO_OFFICIAL_SOURCE_LABEL",
    "OFFICIAL_SOURCE_PLATFORM_HOME",
    "OFFICIAL_SOURCE_PLATFORM_NAME",
    "OFFICIAL_SOURCE_URLS",
    "VIEW_OFFICIAL_SOURCE_BUTTON_TEXT",
    "has_official_source",
    "official_source_url",
]


#: Human-readable identity of the platform the registered pages belong to.
OFFICIAL_SOURCE_PLATFORM_NAME: Final[str] = "全国标准信息公共服务平台"
OFFICIAL_SOURCE_PLATFORM_HOME: Final[str] = "https://std.samr.gov.cn/"


#: Canonical standard id -> verified official page.  Fixed constants only; see
#: the module docstring for how the one entry was verified.
OFFICIAL_SOURCE_URLS: dict[str, str] = {
    "gb-29446-2019": (
        "https://std.samr.gov.cn/gb/search/gbDetailed"
        "?id=9A0A4FA998CDD4A5E05397BE0A0AD02D"
    ),
}


#: UI text.  Shared constants so the wording cannot drift between screens.
VIEW_OFFICIAL_SOURCE_BUTTON_TEXT: Final[str] = "查看标准原文"
NO_OFFICIAL_SOURCE_LABEL: Final[str] = "官方来源地址尚未登记"


def _standard_id_of(value: object) -> str | None:
    """Resolve ``value`` to a canonical standard id, or ``None`` when unknown.

    Accepts a plain id string or any object exposing a string ``id`` (notably a
    ``StandardDefinition``), so UI call sites can pass whichever they hold.
    """
    if isinstance(value, str):
        return value
    candidate = getattr(value, "id", None)
    return candidate if isinstance(candidate, str) else None


def official_source_url(standard_id: str | object) -> str | None:
    """Return the registered official page for ``standard_id``.

    ``None`` means "not registered" -- the caller must disable the affordance and
    show :data:`NO_OFFICIAL_SOURCE_LABEL` rather than build an address itself.
    """
    resolved = _standard_id_of(standard_id)
    if resolved is None:
        return None
    return OFFICIAL_SOURCE_URLS.get(resolved)


def has_official_source(standard_id: str | object) -> bool:
    """Return ``True`` when a verified official page is registered."""
    return official_source_url(standard_id) is not None
