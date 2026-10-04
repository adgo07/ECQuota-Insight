"""UTC to operating-system local time helpers for user-facing display.

Reported defect (ECQ-RS05): the evaluation-record list rendered
``2026-10-04 15:31:39.338366`` while the operator's Windows clock read
``2026-10-04 23:31:39``.  The stored value was correct UTC; the UI printed the
raw column value, in UTC, with microseconds.

Contract:

* storage stays UTC -- no schema change and no rewriting of historical rows;
* the conversion happens here, in the presentation layer only;
* ordinary user-visible output is ``YYYY-MM-DD HH:MM:SS``: to the second, never
  with microseconds;
* a naive ``datetime`` read back from storage is UTC.  It is **never** treated as
  already-local, which is what produced the double-``+8`` class of bug.
  :func:`to_local` attaches ``timezone.utc`` to a naive value and only then
  converts, and an already-aware value is converted as-is -- so the two entry
  forms of the same instant agree exactly.

This module is UI-adjacent but must import without Qt: formatting a timestamp
needs no QApplication, and non-widget code paths need the same helpers.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Final

__all__ = [
    "DISPLAY_DATE_FORMAT",
    "DISPLAY_DATETIME_FORMAT",
    "DISPLAY_PLACEHOLDER",
    "format_local_date",
    "format_local_datetime",
    "to_local",
]


#: Shown instead of a timestamp that does not exist (for example ``None``).
DISPLAY_PLACEHOLDER: Final[str] = "—"

#: Ordinary user-facing formats.  Seconds precision, no microseconds.
DISPLAY_DATETIME_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
DISPLAY_DATE_FORMAT: Final[str] = "%Y-%m-%d"


def to_local(dt: datetime) -> datetime:
    """Return ``dt`` as an aware datetime in the operating-system local zone.

    A naive ``dt`` is interpreted as UTC (that is what the database stores) and a
    ``dt`` that already carries a ``tzinfo`` is converted from that zone.  Either
    way the returned value represents the same instant and is aware, so callers
    can never accidentally add the local offset a second time.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def format_local_datetime(dt: datetime | None) -> str:
    """Format ``dt`` as local ``YYYY-MM-DD HH:MM:SS``; placeholder when ``None``."""
    if dt is None:
        return DISPLAY_PLACEHOLDER
    return to_local(dt).strftime(DISPLAY_DATETIME_FORMAT)


def format_local_date(value: date | datetime | None) -> str:
    """Format a date-only field as local ``YYYY-MM-DD``; placeholder when ``None``.

    A ``datetime`` is converted to local time first, so a UTC instant late in the
    day does not display the previous local date.
    """
    if value is None:
        return DISPLAY_PLACEHOLDER
    if isinstance(value, datetime):
        return to_local(value).strftime(DISPLAY_DATE_FORMAT)
    return value.strftime(DISPLAY_DATE_FORMAT)
