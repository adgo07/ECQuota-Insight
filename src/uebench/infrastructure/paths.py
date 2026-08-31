from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    root: Path
    database: Path
    standards: Path
    backups: Path
    logs: Path
    imports: Path

    @classmethod
    def default(cls) -> AppPaths:
        override = os.environ.get("UEBENCH_DATA_DIR")
        if override:
            return cls.from_root(Path(override))
        if sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "UEBench"
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support" / "UEBench"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "UEBench"
        return cls.from_root(base)

    @classmethod
    def from_root(cls, root: Path) -> AppPaths:
        root = root.resolve()
        return cls(
            root=root,
            database=root / "uebench.sqlite3",
            standards=root / "standards",
            backups=root / "backups",
            logs=root / "logs",
            imports=root / "imports",
        )

    def ensure(self) -> None:
        for directory in (self.root, self.standards, self.backups, self.logs, self.imports):
            directory.mkdir(parents=True, exist_ok=True)
