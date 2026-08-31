from __future__ import annotations

import sys
from pathlib import Path

from uebench.infrastructure.paths import AppPaths


def test_data_directory_override_has_highest_priority(monkeypatch) -> None:
    target = Path("X:/uebench-test/custom-data")
    monkeypatch.setenv("UEBENCH_DATA_DIR", str(target))
    assert AppPaths.default().root == target.resolve()


def test_linux_uses_xdg_data_directory(monkeypatch) -> None:
    monkeypatch.delenv("UEBENCH_DATA_DIR", raising=False)
    target = Path("X:/uebench-test/xdg-data")
    monkeypatch.setenv("XDG_DATA_HOME", str(target))
    monkeypatch.setattr(sys, "platform", "linux")
    assert AppPaths.default().root == (target / "UEBench").resolve()
