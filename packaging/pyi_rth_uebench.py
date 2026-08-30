"""Make the split PySide6 and shiboken6 DLL directories visible to Windows."""

from __future__ import annotations

import os
import sys
from pathlib import Path


if sys.platform == "win32" and hasattr(sys, "_MEIPASS"):
    root = Path(sys._MEIPASS)
    dll_directories = [root / "PySide6", root / "shiboken6", root]
    existing = os.environ.get("PATH", "")
    os.environ["PATH"] = os.pathsep.join(
        [str(path) for path in dll_directories if path.exists()] + [existing]
    )
    for directory in dll_directories[:2]:
        if directory.exists():
            os.add_dll_directory(str(directory))
    # Let PySide6 load its extension modules normally.  Explicitly loading
    # Qt6Core or the bridge with ctypes can block the Windows loader when the
    # collected Qt DLLs have already been mapped by the bootloader.
