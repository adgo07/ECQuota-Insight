"""Application ports for UI-neutral adapters.

The domain and application layers depend on these small protocols instead of
desktop-specific infrastructure classes.  The current Windows composition root
uses the SQLite/Excel implementations; a future Web, NAS, Android, iOS, or
Linux adapter can provide the same methods without changing use cases.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from uebench.domain.models import AuditEntry


class TemplatePort(Protocol):
    def create_template(self, path: Path) -> Path: ...


class WorkbookImportPort(Protocol):
    def validate(self, path: Path) -> Any: ...

    def commit(self, import_id: str) -> Any: ...


class WorkbookExportPort(Protocol):
    def export(self, evaluation_id: str, path: Path) -> Path: ...


class StandardPackagePort(Protocol):
    def preview(self, path: Path) -> Any: ...

    def install(self, path: Path) -> Any: ...

    def discover(self, directory: Path, *, recursive: bool = False) -> list[Path]: ...

    def latest_manifest(self) -> Any: ...


class BackupPort(Protocol):
    def create(self, path: Path) -> Path: ...

    def restore(self, path: Path) -> None: ...


class AuditPort(Protocol):
    def list_recent(self, limit: int = 200) -> list[AuditEntry]: ...