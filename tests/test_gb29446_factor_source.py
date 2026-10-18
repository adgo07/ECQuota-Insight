from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from tools.sync_gb29446_factor_rows import synchronize


DEFINITION = Path(__file__).resolve().parents[1] / "data/definitions/gb-29446-2019.json"


def test_factor_display_lookups_follow_formula_source() -> None:
    payload = json.loads(DEFINITION.read_text(encoding="utf-8"))
    assert synchronize(payload) == []


def test_factor_sync_repairs_only_derived_rows() -> None:
    payload = json.loads(DEFINITION.read_text(encoding="utf-8"))
    original = deepcopy(payload)
    product = payload["products"][0]
    display = product["indicators"][0]["display_calculations"]
    lookup = next(item["formula"] for item in display if item["key"] == "process_factor")
    lookup["rows"][0]["expression"]["value"] = "999.00"

    drift = synchronize(payload)
    assert drift == [f"{product['id']}/display_calculations/lookup-1"]
    assert payload == original
