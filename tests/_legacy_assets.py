"""ECQ-RS05 — deterministic fixtures for the *legacy* on-disk layouts.

There are two independent things in this module, and the difference matters:

**Synthetic legacy fixtures (the core compatibility path).**
Old UEBench versions really wrote the standard原文 into the user data directory,
in two different shapes:

``flat``            ``standards/<package_id>/*.pdf``          (early layout)
``sources-dir``     ``standards/<package_id>/sources/*.pdf``  (later layout)
``both``            both of the above at once

The regression tests for「清理旧版本原文」and its fail-closed abort must be able to
reproduce those shapes **anywhere**, including CI, without ``G:\\ECQuota-Archive``,
without a real standard PDF and without the gitignored development signing key.
So this module can build them from scratch:

* the PDF bytes are minimal dummy content (``%PDF-1.4`` + text) — never标准原文;
* the package is a real, signed ``.uebench`` built with an **ephemeral Ed25519
  keypair generated at test time**, and the matching public key is handed to
  ``create_context(..., public_key_path=...)`` / ``StandardPackageService`` — no
  private key is ever committed or read from ``work/signing/``.

**Archived historical packages (evidence only).**
The old standard packages and the old ``reviewed`` user library were moved out of
the repository into a read-only archive outside the project, per the operator's
decision:

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

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POINTER_PATH = ROOT / "release" / "standard-packages" / "LEGACY-REFERENCE.json"

#: Pointer keys that name a single archived ``.uebench`` package.
PACKAGE_KEYS = ("parent_baseline", "source_bearing_predecessor")

#: The two legacy on-disk shapes this module can materialise, plus their mix.
LEGACY_LAYOUT_FLAT = "flat"
LEGACY_LAYOUT_SOURCES_DIR = "sources-dir"
LEGACY_LAYOUT_BOTH = "both"
LEGACY_LAYOUTS = (LEGACY_LAYOUT_FLAT, LEGACY_LAYOUT_SOURCES_DIR, LEGACY_LAYOUT_BOTH)

#: Minimal dummy standard原文 bytes.  Deliberately not a real PDF and never any
#: part of a real standard: the cleanup contract only cares about the ``.pdf``
#: extension and the file's location, so committing real原文 is pointless *and*
#: forbidden.
DUMMY_PDF_BYTES = b"%PDF-1.4\n% dummy legacy standard original - synthetic fixture\n"


def dummy_pdf_bytes(index: int = 0) -> bytes:
    """Deterministic, minimal dummy PDF payload (never a real standard原文)."""
    return DUMMY_PDF_BYTES + f"fixture-{index:02d}\n".encode("ascii")


def dummy_pdf_sha256(index: int = 0) -> str:
    return hashlib.sha256(dummy_pdf_bytes(index)).hexdigest()


_COPY_ROOT: Path | None = None
_PACKAGE_COPIES: dict[str, Path] = {}


# ---------------------------------------------------------------------------
# Synthetic legacy fixtures — no external archive, no committed key
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SyntheticLegacyLibrary:
    """A real, installable synthetic standard package + its signed identity.

    ``package`` is signed with ``private_key``; ``public_key_path`` is the PEM
    written next to it, so a test can wire a real composition root with
    ``create_context(root, public_key_path=library.public_key_path)``.
    """

    package: Path
    package_id: str
    data_version: str
    private_key: object
    public_key_path: Path
    definition: object
    source_file_name: str
    source_bytes: bytes = field(default=DUMMY_PDF_BYTES)


def synthetic_legacy_library(
    directory: Path,
    *,
    package_id: str = "synthetic-legacy-package",
    data_version: str = "2026.09-published.2",
    rule_revision: int = 1,
    issued_at: datetime | None = None,
    level_1: str = "10",
) -> SyntheticLegacyLibrary:
    """Build a signed synthetic standard package with an **ephemeral** key.

    The package ships ``sources/*`` (the historical ``embedded`` policy) exactly
    like the archived legacy packages did, so the "legacy package still installs
    but never lands its原文" contract keeps a real end-to-end fixture instead of a
    pinned 21 MB archive file.  Everything is rebuilt deterministically from
    ``make_standard()``: the PDF bytes are dummy, the keypair is generated here
    and only its public half is written to disk.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from uebench.domain.models import PublicationStatus
    from uebench.infrastructure.packages import StandardPackageBuilder

    from .test_engine import make_standard

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    public_key_path = directory / "synthetic-public-key.pem"
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    definition = make_standard()
    definition.rule_revision = rule_revision
    definition.publication_status = PublicationStatus.PUBLISHED
    definition.products[0].indicators[0].thresholds.level_1.value = level_1
    source_bytes = dummy_pdf_bytes(0)
    source = directory / definition.source_file
    source.write_bytes(source_bytes)
    digest = hashlib.sha256(source_bytes).hexdigest()
    definition.source_sha256 = digest
    for product in definition.products:
        for indicator in product.indicators:
            for reference in indicator.source_references:
                reference.source_sha256 = digest
                reference.source_file = definition.source_file
                reference.standard_number = definition.number

    package = StandardPackageBuilder(private_key).build(
        directory / f"{package_id}.uebench",
        [definition],
        {definition.source_file: source},
        data_version=data_version,
        package_id=package_id,
        issued_at=issued_at or datetime(2026, 9, 26, tzinfo=timezone.utc),
        corrections=[{"id": "corr-synthetic-legacy", "note": "合成旧版布局用例"}],
    )
    return SyntheticLegacyLibrary(
        package=package,
        package_id=package_id,
        data_version=data_version,
        private_key=private_key,
        public_key_path=public_key_path,
        definition=definition,
        source_file_name=definition.source_file,
        source_bytes=source_bytes,
    )


def successor_library(
    directory: Path,
    *,
    private_key,
    package_id: str = "synthetic-legacy-successor",
    data_version: str = "2026.11-published.1",
    rule_revision: int = 2,
    issued_at: datetime | None = None,
    level_1: str = "11",
) -> object:
    """Build a **provenance-only** successor package signed by an existing key.

    Used for the upgrade half of the legacy-layout tests: it must be installable
    into the same data directory as ``synthetic_legacy_library``'s package, so it
    reuses that ephemeral private key instead of generating a second one.
    """
    from uebench.domain.models import PublicationStatus
    from uebench.infrastructure.packages import StandardPackageBuilder

    from .test_engine import make_standard

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    definition = make_standard()
    definition.rule_revision = rule_revision
    definition.publication_status = PublicationStatus.PUBLISHED
    definition.products[0].indicators[0].thresholds.level_1.value = level_1
    source_bytes = dummy_pdf_bytes(1)
    digest = hashlib.sha256(source_bytes).hexdigest()
    definition.source_sha256 = digest
    for product in definition.products:
        for indicator in product.indicators:
            for reference in indicator.source_references:
                reference.source_sha256 = digest
    return StandardPackageBuilder(private_key).build(
        directory / f"{package_id}.uebench",
        [definition],
        None,
        data_version=data_version,
        package_id=package_id,
        issued_at=issued_at or datetime(2026, 10, 5, tzinfo=timezone.utc),
        distribute_sources=False,
    )


def materialize_legacy_layout(
    package_directory: Path,
    layout: str,
    *,
    pdf_count: int = 3,
    extra_entries: dict[str, bytes] | None = None,
) -> dict[str, Path]:
    """Write a real legacy on-disk layout inside ``package_directory``.

    ``flat``        only ``<package>/*.pdf``            (early layout)
    ``sources-dir`` only ``<package>/sources/*``         (later layout)
    ``both``        both at once                         (mixed historical state)

    ``extra_entries`` are additional relative paths written verbatim (used to
    prove that non-PDF, non-``sources`` content survives the cleanup).  Returns
    the mapping ``{"flat": dir, "sources": dir}`` with the directories created.
    """
    if layout not in LEGACY_LAYOUTS:
        raise ValueError(f"未知的旧版布局：{layout}（可选 {LEGACY_LAYOUTS}）")
    package_directory = Path(package_directory)
    package_directory.mkdir(parents=True, exist_ok=True)
    created: dict[str, Path] = {}
    if layout in (LEGACY_LAYOUT_FLAT, LEGACY_LAYOUT_BOTH):
        for index in range(pdf_count):
            (package_directory / f"{index:02d}.legacy-flat.pdf").write_bytes(dummy_pdf_bytes(index))
        created["flat"] = package_directory
    if layout in (LEGACY_LAYOUT_SOURCES_DIR, LEGACY_LAYOUT_BOTH):
        sources = package_directory / "sources"
        sources.mkdir(parents=True, exist_ok=True)
        for index in range(pdf_count):
            (sources / f"{index:02d}.legacy-sources.pdf").write_bytes(
                dummy_pdf_bytes(100 + index)
            )
        created["sources"] = sources
    for relative, payload in (extra_entries or {}).items():
        target = package_directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return created


def expected_legacy_removal(layout: str, *, pdf_count: int = 3) -> tuple[int, int, int]:
    """``(directories, files_inside_directories, flat_pdfs)`` for a layout."""
    directories = 1 if layout in (LEGACY_LAYOUT_SOURCES_DIR, LEGACY_LAYOUT_BOTH) else 0
    files_inside = pdf_count if directories else 0
    flat = pdf_count if layout in (LEGACY_LAYOUT_FLAT, LEGACY_LAYOUT_BOTH) else 0
    return directories, files_inside, flat


# ---------------------------------------------------------------------------
# Archived historical packages (evidence only; may be unavailable off this host)
# ---------------------------------------------------------------------------


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
