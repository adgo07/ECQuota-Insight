"""Tests for the UTC -> local presentation helpers.

These tests are written to pass in any CI time zone: instant comparisons are used
wherever the wall clock is not the point, and the one wall-clock assertion (the
reported UTC+8 defect) is pinned only when the process time zone can actually be
put into UTC+8.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from uebench.ui.presentation import (
    DISPLAY_PLACEHOLDER,
    format_local_date,
    format_local_datetime,
    to_local,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "uebench" / "ui" / "presentation.py"

#: The exact stored value from the reported defect.
REPORTED_UTC = datetime(2026, 10, 4, 15, 31, 39, 338366)

_DATETIME_RE = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
_DATE_RE = r"\d{4}-\d{2}-\d{2}"

#: POSIX TZ syntax: the offset is what you add to local time to reach UTC, so
#: ``UTC-8`` means UTC+8 (the zone the reporter's Windows clock was in).
_UTC_PLUS_8_TZ = "UTC-8"
_UTC_PLUS_8 = timedelta(hours=8)


@contextmanager
def _process_timezone(tz: str | None) -> Iterator[None]:
    """Temporarily set ``TZ`` and re-sync the C runtime when the platform can.

    ``time.tzset()`` does not exist on Windows; there the variable may have no
    effect at all, which the caller detects by measuring the resulting offset.
    The variable is always restored and ``tzset`` re-run afterwards so a later
    test in the same process never inherits this zone.
    """
    original = os.environ.get("TZ")
    if tz is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = tz
    if hasattr(time, "tzset"):
        time.tzset()
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        if hasattr(time, "tzset"):
            time.tzset()


# ---------------------------------------------------------------------------
# to_local
# ---------------------------------------------------------------------------


def test_naive_datetime_is_treated_as_utc() -> None:
    """A naive stored value is UTC, not local: same instant, never a double shift."""
    aware_utc = REPORTED_UTC.replace(tzinfo=timezone.utc)

    local = to_local(REPORTED_UTC)

    assert local.tzinfo is not None, "to_local must return an aware datetime"
    assert local.utcoffset() is not None
    # Compare instants, so this passes in any CI time zone.
    assert local == aware_utc.astimezone()
    assert local.timestamp() == aware_utc.timestamp(), (
        "a naive stored value must be read as UTC; a double local shift or a "
        "'naive is already local' reading would move the instant"
    )
    # Guard the specific misreading: taking the naive value as already local would
    # land on a different instant whenever the local zone is not UTC.
    offset = local.utcoffset()
    assert offset is not None
    if offset != timedelta(0):
        as_if_already_local = REPORTED_UTC.replace(tzinfo=local.tzinfo)
        assert local.timestamp() != as_if_already_local.timestamp()


def test_aware_datetime_is_converted_from_its_own_zone() -> None:
    aware_utc = REPORTED_UTC.replace(tzinfo=timezone.utc)
    assert to_local(aware_utc) == aware_utc.astimezone()
    assert to_local(aware_utc).timestamp() == aware_utc.timestamp()

    other_zone = aware_utc.astimezone(timezone(timedelta(hours=3)))
    assert to_local(other_zone) == aware_utc.astimezone()
    assert to_local(other_zone).timestamp() == aware_utc.timestamp()


def test_to_local_is_idempotent_on_an_already_local_value() -> None:
    """Re-formatting an already converted value must not shift it again."""
    local = to_local(REPORTED_UTC)
    assert to_local(local) == local
    assert format_local_datetime(local) == format_local_datetime(REPORTED_UTC)


# ---------------------------------------------------------------------------
# format_local_datetime
# ---------------------------------------------------------------------------


def test_format_is_second_precision_without_microseconds() -> None:
    for value in (
        REPORTED_UTC,
        REPORTED_UTC.replace(tzinfo=timezone.utc),
        datetime(2026, 1, 2, 3, 4, 5),
        datetime(2026, 12, 31, 23, 59, 59, 999999),
    ):
        text = format_local_datetime(value)
        assert re.fullmatch(_DATETIME_RE, text), text
        assert len(text) == 19, text
        assert "." not in text, text
        assert "338366" not in text, text
        assert "," not in text, text


def test_aware_utc_and_naive_utc_format_identically() -> None:
    """No double conversion: the two spellings of one instant agree."""
    naive = REPORTED_UTC
    aware_utc = REPORTED_UTC.replace(tzinfo=timezone.utc)
    assert format_local_datetime(naive) == format_local_datetime(aware_utc)

    # A non-UTC aware spelling of the same instant must also agree; a helper that
    # blindly added the local offset again would break this.
    same_instant_in_plus3 = aware_utc.astimezone(timezone(timedelta(hours=3)))
    assert format_local_datetime(same_instant_in_plus3) == format_local_datetime(naive)
    assert format_local_datetime(same_instant_in_plus3) == format_local_datetime(aware_utc)


def test_none_yields_the_placeholder_instead_of_raising() -> None:
    assert format_local_datetime(None) == DISPLAY_PLACEHOLDER
    assert DISPLAY_PLACEHOLDER == "—"
    assert format_local_datetime(None) != ""


def test_reported_case_formats_as_utc_plus_8() -> None:
    """Pin the reported defect: 15:31:39.338366 UTC displays as 23:31:39 local."""
    with _process_timezone(_UTC_PLUS_8_TZ):
        offset = REPORTED_UTC.replace(tzinfo=timezone.utc).astimezone().utcoffset()
        if offset != _UTC_PLUS_8:
            pytest.skip(
                "this platform cannot put the process time zone into UTC+8 at test "
                f"time (TZ={_UTC_PLUS_8_TZ!r} still resolves to {offset}), so the "
                "reported wall-clock case cannot be pinned here"
            )
        assert format_local_datetime(REPORTED_UTC) == "2026-10-04 23:31:39"


# ---------------------------------------------------------------------------
# format_local_date
# ---------------------------------------------------------------------------


def test_date_only_values_use_the_date_format() -> None:
    assert format_local_date(date(2026, 10, 4)) == "2026-10-04"
    assert re.fullmatch(_DATE_RE, format_local_date(date(2026, 10, 4)))
    assert re.fullmatch(_DATE_RE, format_local_date(REPORTED_UTC))


def test_datetime_is_converted_before_the_calendar_day_is_taken() -> None:
    aware_utc = REPORTED_UTC.replace(tzinfo=timezone.utc)
    expected = aware_utc.astimezone().date().isoformat()
    # Independent second opinion from the C runtime's own local-time conversion.
    independent = datetime.fromtimestamp(aware_utc.timestamp()).date().isoformat()
    assert expected == independent

    assert format_local_date(aware_utc) == expected
    assert format_local_date(REPORTED_UTC) == expected, "naive UTC must be converted too"


def test_date_placeholder_for_none() -> None:
    assert format_local_date(None) == DISPLAY_PLACEHOLDER


# ---------------------------------------------------------------------------
# Module-level guard
# ---------------------------------------------------------------------------


def test_presentation_module_is_importable_without_qt() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "PySide6" not in source
    assert "import PySide6" not in source
