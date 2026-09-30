from __future__ import annotations

from tempfile import TemporaryDirectory
from pathlib import Path

from openpyxl import Workbook, load_workbook
from pydantic import ValidationError

from uebench.domain.models import InputValue
from uebench.infrastructure.excel import _excel_value


with TemporaryDirectory() as temp_dir:
    path = Path(temp_dir) / "numeric-ingress.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = 5.0000004
    sheet["A2"] = "5.0000004"
    workbook.save(path)

    loaded = load_workbook(path, data_only=True)
    numeric_cell = loaded.active["A1"].value
    text_cell = loaded.active["A2"].value

    assert isinstance(numeric_cell, float)
    assert isinstance(text_cell, str)

    adapter_value = _excel_value(numeric_cell)
    assert isinstance(adapter_value, str)
    assert adapter_value == str(numeric_cell)
    InputValue(value=adapter_value, unit="kW·h/t")

    direct_float_rejected = False
    try:
        InputValue(value=numeric_cell, unit="kW·h/t")
    except (TypeError, ValidationError):
        direct_float_rejected = True
    assert direct_float_rejected

    print(f"xlsx numeric cell type: {type(numeric_cell).__name__}")
    print(f"xlsx numeric cell repr: {numeric_cell!r}")
    print(f"excel adapter value/type: {adapter_value!r}/{type(adapter_value).__name__}")
    print(f"xlsx text cell type/value: {type(text_cell).__name__}/{text_cell!r}")
    print("finding: numeric XLSX cells cross openpyxl as binary float before adapter str -> Decimal parsing")
