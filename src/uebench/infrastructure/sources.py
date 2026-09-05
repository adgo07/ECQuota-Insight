from __future__ import annotations

import hashlib
from pathlib import Path


class StandardSourceService:
    """Find packaged source PDFs by filename and verify their SHA-256."""

    def __init__(self, source_root: Path) -> None:
        self.source_root = source_root.resolve()

    def find(self, source_file: str, source_sha256: str) -> Path | None:
        # Definitions store a basename. Refuse path-like values before using
        # them as a recursive glob pattern.
        if not source_file or Path(source_file).name != source_file:
            return None
        expected_hash = source_sha256.lower()
        candidates = sorted(
            self.source_root.rglob(source_file),
            key=lambda item: str(item).casefold(),
        )
        for candidate in candidates:
            if not candidate.is_file():
                continue
            digest = hashlib.sha256()
            try:
                with candidate.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
            except OSError:
                continue
            if digest.hexdigest() == expected_hash:
                return candidate
        return None