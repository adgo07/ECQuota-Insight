"""Architecture boundary gates.

These tests walk the whole module AST, not just top-level statements, so a
deferred import inside a function cannot smuggle a forbidden dependency past the
layering rules.

Imports guarded by ``if TYPE_CHECKING:`` never execute at runtime, so they are
tracked separately: a type-only import of the composition root is acceptable for
the presentation layer, while importing the composition root or the
infrastructure layer at runtime is not.
"""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "uebench"


class _ImportCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.runtime: set[str] = set()
        self.type_only: set[str] = set()
        self._type_checking_depth = 0

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking_guard(node.test):
            self._type_checking_depth += 1
            for child in node.body:
                self.visit(child)
            self._type_checking_depth -= 1
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        target = self.type_only if self._type_checking_depth else self.runtime
        target.update(alias.name for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if not node.module:
            return
        target = self.type_only if self._type_checking_depth else self.runtime
        target.add(node.module)
        if node.level == 0:
            target.update(f"{node.module}.{alias.name}" for alias in node.names)


def _is_type_checking_guard(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def _collect(path: Path) -> _ImportCollector:
    collector = _ImportCollector()
    collector.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
    return collector


def _python_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*.py") if path.name != "__pycache__")


def _violations(directory: Path, forbidden: tuple[str, ...], *, include_type_only: bool = False) -> list[str]:
    found: list[str] = []
    for path in _python_files(directory):
        collector = _collect(path)
        checked = collector.runtime | (collector.type_only if include_type_only else set())
        for module in checked:
            if module.startswith(forbidden):
                found.append(f"{path.relative_to(ROOT)} imports {module}")
    return sorted(set(found))


def test_domain_has_no_framework_or_outer_layer_imports() -> None:
    assert not _violations(
        SRC / "domain",
        ("PySide6", "sqlalchemy", "openpyxl", "uebench.application", "uebench.infrastructure", "uebench.ui", "uebench.bootstrap"),
        include_type_only=True,
    )


def test_application_layer_has_no_desktop_storage_or_outer_layer_imports() -> None:
    assert not _violations(
        SRC / "application",
        ("PySide6", "sqlalchemy", "openpyxl", "uebench.infrastructure", "uebench.ui", "uebench.bootstrap"),
        include_type_only=True,
    )


def test_ui_never_imports_infrastructure_even_for_typing() -> None:
    """UI must depend on application ports, not on concrete adapters."""
    assert not _violations(SRC / "ui", ("uebench.infrastructure",), include_type_only=True)


def test_ui_does_not_import_composition_root_at_runtime() -> None:
    assert not _violations(SRC / "ui", ("uebench.bootstrap",))


def test_infrastructure_does_not_import_ui() -> None:
    assert not _violations(
        SRC / "infrastructure", ("uebench.ui", "uebench.bootstrap"), include_type_only=True
    )


def test_gb29446_shared_mapping_is_ui_and_excel_free() -> None:
    """The GUI/Excel shared mapping must stay a plain application-layer module."""
    module = SRC / "application" / "gb29446.py"
    assert module.exists()
    collector = _collect(module)
    imports = collector.runtime | collector.type_only
    frameworks = sorted(
        name for name in imports
        if name.split(".")[0] in {"PySide6", "openpyxl", "sqlalchemy"}
        or name.startswith(("uebench.infrastructure", "uebench.ui"))
    )
    assert not frameworks, f"application/gb29446.py must not depend on these: {frameworks}"
