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

def test_macos_uses_application_support(monkeypatch) -> None:
    monkeypatch.delenv("UEBENCH_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    assert AppPaths.default().root == (Path.home() / "Library" / "Application Support" / "UEBench").resolve()

def test_linux_falls_back_to_local_share(monkeypatch) -> None:
    monkeypatch.delenv("UEBENCH_DATA_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    assert AppPaths.default().root == (Path.home() / ".local" / "share" / "UEBench").resolve()

def test_windows_uses_localappdata(monkeypatch) -> None:
    monkeypatch.delenv("UEBENCH_DATA_DIR", raising=False)
    target = Path("X:/uebench-test/localappdata")
    monkeypatch.setenv("LOCALAPPDATA", str(target))
    monkeypatch.setattr(sys, "platform", "win32")
    assert AppPaths.default().root == (target / "UEBench").resolve()
