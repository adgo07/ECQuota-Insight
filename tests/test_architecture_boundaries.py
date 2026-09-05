from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_ui_has_no_runtime_bootstrap_or_infrastructure_import() -> None:
    modules = _top_level_imports(ROOT / "src" / "uebench" / "ui" / "main_window.py")
    assert "uebench.bootstrap" not in modules
    assert not any(module.startswith("uebench.infrastructure") for module in modules)


def test_application_layer_has_no_desktop_or_storage_framework_imports() -> None:
    forbidden_prefixes = ("PySide6", "sqlalchemy", "openpyxl", "uebench.infrastructure")
    for path in sorted((ROOT / "src" / "uebench" / "application").glob("*.py")):
        modules = _top_level_imports(path)
        assert not any(module.startswith(forbidden_prefixes) for module in modules), path.name