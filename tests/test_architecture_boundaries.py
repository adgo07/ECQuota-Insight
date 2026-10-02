"""Architecture boundary gates.

These tests walk the whole module AST, not just top-level statements, so a
deferred import inside a function cannot smuggle a forbidden dependency past the
layering rules.

Import names are resolved to fully qualified module paths, including relative
imports, so ``from ..infrastructure.excel import X`` inside a function is
detected exactly like an absolute ``import uebench.infrastructure.excel``.
Imports guarded by ``if TYPE_CHECKING:`` never execute at runtime and are
tracked separately.
"""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "uebench"
PACKAGE_ROOT = SRC.parent  # ``src`` contains the top-level package ``uebench``


class _ImportCollector(ast.NodeVisitor):
    def __init__(self, module: str) -> None:
        #: Fully qualified name of the module being inspected, for example
        #: ``uebench.ui.main_window``.
        self.module = module
        self.runtime: set[str] = set()
        self.type_only: set[str] = set()
        self._type_checking_depth = 0

    # -- TYPE_CHECKING handling -------------------------------------------
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

    # -- imports ----------------------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        target = self._target()
        # ``import a.b`` binds ``a`` and makes ``a.b`` importable; both names
        # are relevant to a prefix-based rule.
        for alias in node.names:
            target.add(alias.name)
            target.update(_prefixes(alias.name))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base = self._resolve_from_base(node)
        if base is None:
            return
        target = self._target()
        target.add(base)
        target.update(_prefixes(base))
        for alias in node.names:
            if alias.name == "*":
                continue
            target.add(f"{base}.{alias.name}")
            target.update(_prefixes(f"{base}.{alias.name}"))

    def _target(self) -> set[str]:
        return self.type_only if self._type_checking_depth else self.runtime

    def _resolve_from_base(self, node: ast.ImportFrom) -> str | None:
        """Return the fully qualified module a ``from ... import`` targets.

        ``node.module`` is ``None`` for ``from . import x``, so the base is
        derived from the importing module's own package and ``node.level``.
        Without this, a relative import inside a function resolves to a partial
        name such as ``infrastructure.excel`` that never matches the
        ``uebench.infrastructure`` prefix.
        """
        package_parts = self.module.split(".")[:-1]
        if node.level:
            # level 1 stays in the current package, level 2 goes one package up.
            drop = node.level - 1
            if drop > len(package_parts):
                return None
            package_parts = package_parts[: len(package_parts) - drop] if drop else package_parts
        if node.module:
            package_parts = [*package_parts, *node.module.split(".")]
        if not package_parts:
            return None
        return ".".join(package_parts)


def _prefixes(name: str) -> set[str]:
    """All dotted prefixes of ``name``, exclusive of ``name`` itself."""
    parts = name.split(".")
    return {".".join(parts[:index]) for index in range(1, len(parts))}


def _is_type_checking_guard(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def _module_name(path: Path) -> str:
    """Dotted module name derived from the file's location under ``src``."""
    relative = path.resolve().relative_to(PACKAGE_ROOT.resolve()).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _collect(path: Path) -> _ImportCollector:
    collector = _ImportCollector(_module_name(path))
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


# ---------------------------------------------------------------------------
# Positive control: the resolver itself must catch relative imports.
# ---------------------------------------------------------------------------


def test_relative_import_resolution_catches_evasion(tmp_path: Path) -> None:
    """A deferred relative import must resolve to its real dotted module path.

    This is the regression guard for the boundary gate itself: absolute imports
    were already detected, but ``from ..infrastructure.excel import X`` inside a
    function previously resolved to ``infrastructure.excel`` and slipped through.
    """
    sample = tmp_path / "probe_module.py"
    sample.write_text(
        "from __future__ import annotations\n"
        "\n"
        "\n"
        "def lazy() -> object:\n"
        "    import uebench.infrastructure.excel\n"
        "    return uebench.infrastructure.excel\n"
        "\n"
        "\n"
        "def lazy_relative() -> object:\n"
        "    from ..infrastructure.excel import WorkbookImportService\n"
        "    return WorkbookImportService\n"
        "\n"
        "\n"
        "def lazy_relative_package() -> object:\n"
        "    from .. import infrastructure\n"
        "    return infrastructure\n",
        encoding="utf-8",
    )
    collector = _ImportCollector("uebench.ui.probe_module")
    collector.visit(ast.parse(sample.read_text(encoding="utf-8"), filename=str(sample)))

    forbidden = ("uebench.infrastructure",)
    matched = {name for name in collector.runtime if name.startswith(forbidden)}
    assert "uebench.infrastructure.excel" in matched, "absolute deferred import must be caught"
    assert "uebench.infrastructure.excel.WorkbookImportService" in matched, (
        "relative 'from ..infrastructure.excel import X' must resolve to uebench.infrastructure..."
    )
    assert "uebench.infrastructure" in matched, (
        "relative 'from .. import infrastructure' must resolve to the real package"
    )


def test_prefix_helper_covers_intermediate_packages() -> None:
    assert _prefixes("uebench.infrastructure.excel") == {
        "uebench",
        "uebench.infrastructure",
    }
    assert _prefixes("uebench") == set()


# ---------------------------------------------------------------------------
# Layer rules
# ---------------------------------------------------------------------------


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
