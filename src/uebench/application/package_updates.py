from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class PackageManifestLike(Protocol):
    package_id: str
    data_version: str
    issued_at: datetime
    package_mode: str
    parent_package_id: str | None
    standard_count: int
    rule_count: int


class PackagePreviewLike(Protocol):
    valid: bool
    manifest: PackageManifestLike | None
    errors: list[str]
    warnings: list[str]


class PackageDiscoveryPort(Protocol):
    def discover(self, directory: Path, *, recursive: bool = False) -> list[Path]: ...

    def preview(self, path: Path) -> PackagePreviewLike: ...


class PackageScanItem(BaseModel):
    """UI-neutral result for one package found in a local/NAS directory."""

    model_config = ConfigDict(extra="forbid")

    path: str
    valid: bool
    package_id: str | None = None
    data_version: str | None = None
    issued_at: datetime | None = None
    package_mode: str | None = None
    parent_package_id: str | None = None
    standard_count: int | None = Field(default=None, ge=0)
    rule_count: int | None = Field(default=None, ge=0)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PackageDirectoryService:
    """Application use case for discovering and previewing update candidates.

    It deliberately never installs a package. Installation remains a separate
    explicit operation after the user has reviewed the returned candidates.
    """

    def __init__(self, packages: PackageDiscoveryPort) -> None:
        self.packages = packages

    def scan(self, directory: Path, *, recursive: bool = False) -> list[PackageScanItem]:
        items: list[PackageScanItem] = []
        for path in self.packages.discover(directory, recursive=recursive):
            try:
                report = self.packages.preview(path)
            except Exception as exc:  # preview adapters may reject a malformed file
                items.append(PackageScanItem(path=str(path), valid=False, errors=[str(exc)]))
                continue
            manifest = report.manifest
            items.append(
                PackageScanItem(
                    path=str(path),
                    valid=report.valid,
                    package_id=manifest.package_id if manifest else None,
                    data_version=manifest.data_version if manifest else None,
                    issued_at=manifest.issued_at if manifest else None,
                    package_mode=manifest.package_mode if manifest else None,
                    parent_package_id=manifest.parent_package_id if manifest else None,
                    standard_count=manifest.standard_count if manifest else None,
                    rule_count=manifest.rule_count if manifest else None,
                    errors=list(report.errors),
                    warnings=list(report.warnings),
                )
            )
        return items