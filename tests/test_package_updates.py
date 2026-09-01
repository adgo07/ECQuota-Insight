from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from uebench.application.package_updates import PackageDirectoryService


def test_scan_returns_ui_neutral_candidates_without_installing(tmp_path: Path) -> None:
    first = tmp_path / "first.uebench"
    second = tmp_path / "second.uebench"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    packages = Mock()
    packages.discover.return_value = [first, second]
    packages.preview.side_effect = [
        SimpleNamespace(
            valid=True,
            manifest=SimpleNamespace(
                package_id="pkg-1",
                data_version="2026.09-published.1",
                issued_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
                package_mode="full",
                parent_package_id=None,
                standard_count=46,
                rule_count=702,
            ),
            errors=[],
            warnings=["提示"],
        ),
        SimpleNamespace(valid=False, manifest=None, errors=["签名无效"], warnings=[]),
    ]

    items = PackageDirectoryService(packages).scan(tmp_path, recursive=True)

    assert items[0].valid is True
    assert items[0].package_id == "pkg-1"
    assert items[0].data_version == "2026.09-published.1"
    assert items[0].standard_count == 46
    assert items[0].warnings == ["提示"]
    assert items[1].valid is False
    assert items[1].errors == ["签名无效"]
    packages.discover.assert_called_once_with(tmp_path, recursive=True)
    assert packages.preview.call_count == 2
    packages.install.assert_not_called()


def test_scan_keeps_preview_adapter_errors_as_one_candidate(tmp_path: Path) -> None:
    package = tmp_path / "broken.uebench"
    package.write_bytes(b"broken")
    packages = Mock()
    packages.discover.return_value = [package]
    packages.preview.side_effect = RuntimeError("读取失败")

    items = PackageDirectoryService(packages).scan(tmp_path)

    assert len(items) == 1
    assert items[0].path == str(package)
    assert items[0].valid is False
    assert items[0].errors == ["读取失败"]


def test_scan_rejects_extra_fields_in_contract() -> None:
    with pytest.raises(ValueError):
        from uebench.application.package_updates import PackageScanItem

        PackageScanItem(path="x.uebench", valid=True, unexpected="x")