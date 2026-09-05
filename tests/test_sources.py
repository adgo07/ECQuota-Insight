from __future__ import annotations

import hashlib
from pathlib import Path

from uebench.infrastructure.sources import StandardSourceService


def test_source_service_matches_same_named_pdf_by_hash(tmp_path: Path) -> None:
    root = tmp_path / "standards"
    stale = root / "old-package" / "same.pdf"
    current = root / "new-package" / "same.pdf"
    stale.parent.mkdir(parents=True)
    current.parent.mkdir(parents=True)
    stale.write_bytes(b"old source")
    current.write_bytes(b"selected source")

    service = StandardSourceService(root)

    assert service.find("same.pdf", hashlib.sha256(b"selected source").hexdigest()) == current
    assert service.find("same.pdf", hashlib.sha256(b"missing source").hexdigest()) is None


def test_source_service_rejects_path_like_source_name(tmp_path: Path) -> None:
    service = StandardSourceService(tmp_path)

    assert service.find("../same.pdf", "0" * 64) is None
    assert service.find("", "0" * 64) is None