"""ECQ-RS05 — access to LEGACY assets that are no longer in the repository.

The old standard packages and the old ``reviewed`` user library were moved out of
the repository into a **read-only archive outside the project**, per the
operator's decision:

* they must never be a runtime / build / packaging / release input;
* the archived originals are read-only and must NOT be used in place;
* anything that needs them must **copy** them into an independent temporary
  directory first.

This module performs that copy once per session and hands out the copy's path, so
tests can keep using a plain ``Path`` (and keep their ``.is_file()`` skip guards)
while never touching the archive original.

Pointer entries (``release/standard-packages/LEGACY-REFERENCE.json``):

``parent_baseline``
    ``2026.09-published.2`` — the historical baseline of the GB29446 r1→r2
    substitution.  Also the package the runtime-reconciliation evidence uses as
    its LEGACY (r1) input, so this key must keep naming that exact file.
``source_bearing_predecessor``
    ``2026.10-published.3`` — SUPERSEDED: the last package that still shipped
    ``sources/*`` PDFs, and the **direct** parent of the current pinned package.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POINTER_PATH = ROOT / "release" / "standard-packages" / "LEGACY-REFERENCE.json"

#: Pointer keys that name a single archived ``.uebench`` package.
PACKAGE_KEYS = ("parent_baseline", "source_bearing_predecessor")

_COPY_ROOT: Path | None = None
_PACKAGE_COPIES: dict[str, Path] = {}


def pointer() -> dict:
    return json.loads(POINTER_PATH.read_text(encoding="utf-8"))


def _copy_root() -> Path:
    global _COPY_ROOT
    if _COPY_ROOT is None:
        _COPY_ROOT = Path(tempfile.mkdtemp(prefix="uebench-legacy-copy-"))
    return _COPY_ROOT


def archived_source(entry_key: str = "parent_baseline") -> Path:
    """Path of the read-only archive ORIGINAL for a package pointer entry."""
    document = pointer()
    entry = document[entry_key]
    return Path(document["archive_root"]) / entry["relative_path"]


def legacy_package(entry_key: str) -> Path:
    """Path to a WRITABLE COPY of an archived package pointer entry.

    Returns a path that does not exist when the archive is unavailable (for
    example on CI), so existing ``pytest.mark.skipif(not X.is_file())`` guards
    keep working instead of erroring.
    """
    if entry_key in _PACKAGE_COPIES:
        return _PACKAGE_COPIES[entry_key]
    entry = pointer()[entry_key]
    target = _copy_root() / entry_key / entry["file_name"]
    source = archived_source(entry_key)
    if not source.is_file():
        _PACKAGE_COPIES[entry_key] = target  # deliberately non-existent -> skip guards fire
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    target.chmod(0o644)  # the archived original is read-only; the copy must not be
    _PACKAGE_COPIES[entry_key] = target
    return target


def session_legacy_package() -> Path:
    """WRITABLE COPY of the archived ``2026.09-published.2`` parent baseline."""
    return legacy_package("parent_baseline")


def session_source_bearing_predecessor() -> Path:
    """WRITABLE COPY of the archived, SUPERSEDED ``2026.10-published.3`` package."""
    return legacy_package("source_bearing_predecessor")


def session_user_library() -> Path:
    """WRITABLE COPY of the archived legacy ``reviewed`` user library."""
    entry = pointer()["user_library"]
    target = _copy_root() / "user-library"
    source = Path(pointer()["archive_root"]) / entry["relative_path"]
    if target.is_dir():
        return target
    if not source.is_dir():
        return target
    shutil.copytree(source, target)
    for path in target.rglob("*"):
        try:
            path.chmod(0o755 if path.is_dir() else 0o644)
        except OSError:
            pass
    return target
