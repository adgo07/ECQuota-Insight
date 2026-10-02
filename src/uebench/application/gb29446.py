"""GB 29446 application-layer mapping shared by the desktop UI and Excel adapter.

This module is UI-neutral and adapter-neutral.  It holds the mapping rules that
both the GUI and the Excel adapter must agree on, so that a workbook and a
manually filled form produce the same canonical ``EvaluationRequest``:

* the accounting-period vocabulary and its ``notes`` codec;
* the user-facing field vocabulary for the reference standard.

It must not import PySide6, openpyxl, SQLAlchemy, the infrastructure layer or the
UI layer.  The accounting-period codec is a behaviour-preserving extraction from
``uebench.ui.main_window``; the historical decoding compatibility documented
below is part of the contract and must not be changed.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Adapter identity (machine-readable; never shown to end users)
# ---------------------------------------------------------------------------

GB29446_STANDARD_ID = "gb-29446-2019"

GB29446_EXCEL_ADAPTER_ID = "ecq.gb29446.excel.v1"
GB29446_EXCEL_TEMPLATE_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Accounting period
# ---------------------------------------------------------------------------

PERIOD_FULL_YEAR = "全年"
PERIOD_CUSTOM = "自定义"

#: Options offered to users.  Order is user-visible and stable.
GB29446_PERIOD_OPTIONS: tuple[str, ...] = (
    PERIOD_FULL_YEAR,
    *(f"{month}月" for month in range(1, 13)),
    PERIOD_CUSTOM,
)

#: Historical period label that predates the current option list.  Records saved
#: before the vocabulary was normalised used ``1月～12月`` for a full year.  The
#: decoder must keep mapping it to ``全年`` so historical notes continue to
#: decode exactly as they did before this codec was extracted.
_LEGACY_FULL_YEAR_LABEL = "1月～12月"

_PERIOD_PREFIX = "核算周期："
_CUSTOM_PREFIX = "自定义周期："
_NOTE_PREFIX = "备注："

# ---------------------------------------------------------------------------
# User-facing field vocabulary
# ---------------------------------------------------------------------------

#: Sheet/field labels used by the GB29446 template.  These are display labels,
#: not the canonical ``input key`` values used by the domain.
FIELD_ORGANIZATION_NAME = "企业名称"
FIELD_EVALUATION_DATE = "评价日期"
FIELD_PERIOD = "核算周期"
FIELD_CUSTOM_PERIOD = "自定义周期"
FIELD_COAL_TYPE = "煤种"
FIELD_WASHING_PROCESS = "选煤工艺"
FIELD_ELECTRICITY = "统计期选煤电力消耗量 E_d"
FIELD_RAW_COAL = "统计期入选原煤量 m"
FIELD_NOTES = "备注"

#: Canonical domain input keys for the detail-mode calculation.  The Excel
#: adapter maps user fields onto these keys; it never computes ``k``, ``e_d``
#: or a grade itself.
INPUT_WASHING_PROCESS = "washing_process"
INPUT_ELECTRICITY = "electricity_consumption"
INPUT_RAW_COAL = "raw_coal_input"

UNIT_ELECTRICITY = "kW·h"
UNIT_RAW_COAL = "t"

#: The workbook carries exactly one evaluation, so these are fixed.
EXCEL_SELECTION_MODE_VALUE = "CURRENT"


def encode_period_notes(period: str, custom_period: str, note: str) -> str:
    """Encode accounting-period fields into the persisted ``notes`` text.

    Behaviour-preserving extraction from the desktop UI: the GUI and the Excel
    adapter must both call this so a workbook and a form produce identical
    ``notes`` for identical input.
    """
    lines = [f"{_PERIOD_PREFIX}{period}"]
    if period == PERIOD_CUSTOM:
        lines.append(f"{_CUSTOM_PREFIX}{custom_period.strip()}")
    if note.strip():
        lines.append(f"{_NOTE_PREFIX}{note.strip()}")
    return "\n".join(lines)


def decode_period_notes(notes: str | None) -> tuple[str, str, str]:
    """Decode persisted ``notes`` back into ``(period, custom_period, note)``.

    Historical compatibility (must be preserved exactly):

    * a missing or unrecognised first line yields ``("全年", "", notes)``;
    * the legacy full-year label ``1月～12月`` maps to ``全年``;
    * a period outside :data:`GB29446_PERIOD_OPTIONS` falls back to ``全年``
      and the original notes text is returned unchanged as the note;
    * ``自定义周期：`` is only consumed when the period is ``自定义``.
    """
    lines = (notes or "").splitlines()
    if not lines or not lines[0].startswith(_PERIOD_PREFIX):
        return PERIOD_FULL_YEAR, "", notes or ""
    period = lines[0].split("：", 1)[1].strip()
    if period == _LEGACY_FULL_YEAR_LABEL:
        period = PERIOD_FULL_YEAR
    if period not in GB29446_PERIOD_OPTIONS:
        return PERIOD_FULL_YEAR, "", notes or ""
    custom_period = ""
    remaining = lines[1:]
    if period == PERIOD_CUSTOM and remaining and remaining[0].startswith(_CUSTOM_PREFIX):
        custom_period = remaining.pop(0).split("：", 1)[1].strip()
    note = "\n".join(remaining)
    if note.startswith(_NOTE_PREFIX):
        note = note.split("：", 1)[1]
    return period, custom_period, note
