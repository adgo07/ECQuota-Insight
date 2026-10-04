"""ECQ-RS05 — access to LEGACY assets that are no longer in the repository.

The old standard package and the old ``reviewed`` user library were moved out of the
repository into a **read-only archive outside the project**, per the operator's
decision:

* they must never be a runtime / build / packaging / release input;
* the archived originals are read-only and must NOT be used in place;
* anything that needs them must **copy** them into an independent temporary
  directory first.

This module performs that copy once per session and hands out the copy's path, so
tests can keep using a plain ``Path`` (and keep their ``.is_file()`` skip guards)
while never touching the archive original.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POINTER_PATH = ROOT / "release" / "standard-packages" / "LEGACY-REFERENCE.json"

_COPY_ROOT: Path | None = None
_PACKAGE_COPY: Path | None = None


def pointer() -> dict:
    return json.loads(POINTER_PATH.read_text(encoding="utf-8"))


def _copy_root() -> Path:
    global _COPY_ROOT
    if _COPY_ROOT is None:
        _COPY_ROOT = Path(tempfile.mkdtemp(prefix="uebench-legacy-copy-"))
    return _COPY_ROOT


def archived_source() -> Path:
    entry = pointer()["parent_baseline"]
    return Path(pointer()["archive_root"]) / entry["relative_path"]


def session_legacy_package() -> Path:
    """Path to a WRITABLE COPY of the archived parent-baseline package.

    Returns a path that does not exist when the archive is unavailable (for
    example on CI), so existing ``pytest.mark.skipif(not X.is_file())`` guards
    keep working instead of erroring.
    """
    global _PACKAGE_COPY
    if _PACKAGE_COPY is not None:
        return _PACKAGE_COPY
    entry = pointer()["parent_baseline"]
    target = _copy_root() / entry["file_name"]
    source = archived_source()
    if not source.is_file():
        _PACKAGE_COPY = target  # deliberately non-existent -> skip guards fire
        return _PACKAGE_COPY
    shutil.copy2(source, target)
    target.chmod(0o644)  # the archived original is read-only; the copy must not be
    _PACKAGE_COPY = target
    return _PACKAGE_COPY


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
