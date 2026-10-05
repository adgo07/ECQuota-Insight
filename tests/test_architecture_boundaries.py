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
    def __init__(self, module: str, *, is_package: bool = False) -> None:
        #: Fully qualified name of the module being inspected, for example
        #: ``uebench.ui.main_window``.  For a package ``__init__.py`` this is the
        #: package itself, for example ``uebench.application``.
        self.module = module
        #: ``True`` when inspecting a package ``__init__.py``.  Relative imports
        #: are anchored differently there: ``from . import x`` targets a sibling
        #: of the package, while in a module it targets a sibling of the parent
        #: package.
        self.is_package = is_package
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

        Follows real Python import semantics:

        * ``node.level == 0`` is an **absolute** import: only ``node.module``
          counts.  Prefixing it with the importing module's package produced
          names such as ``uebench.application.openpyxl``, which never matched the
          ``openpyxl`` rule and silently bypassed the gate.
        * ``node.level > 0`` is **relative**.  The anchor is the containing
          package: the parent package of a plain module, or the package itself
          for ``__init__.py``.  ``node.module`` is ``None`` for ``from . import x``.
        """
        if node.level == 0:
            return node.module or None

        anchor_parts = self.module.split(".") if self.is_package else self.module.split(".")[:-1]
        drop = node.level - 1
        if drop > len(anchor_parts):
            return None
        if drop:
            anchor_parts = anchor_parts[: len(anchor_parts) - drop]
        if node.module:
            anchor_parts = [*anchor_parts, *node.module.split(".")]
        if not anchor_parts:
            return None
        return ".".join(anchor_parts)


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


def _is_package_file(path: Path) -> bool:
    return path.name == "__init__.py"


def _collect(path: Path) -> _ImportCollector:
    collector = _ImportCollector(_module_name(path), is_package=_is_package_file(path))
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


def _violations_in_source(source: str, path: Path, forbidden: tuple[str, ...]) -> list[str]:
    """Run the layer rule over an in-memory source using an explicit file path.

    ``_violations`` derives the module name from the file's location, so a
    temporary file would be named after ``tmp_path``.  This helper keeps the
    path-based module derivation intact by pointing at a real dotted location
    while supplying synthetic content.
    """
    collector = _ImportCollector(_module_name(path), is_package=_is_package_file(path))
    collector.visit(ast.parse(source, filename=str(path)))
    return sorted(name for name in collector.runtime if name.startswith(forbidden))


def _resolve(module: str, source: str, *, is_package: bool = False) -> set[str]:
    """Resolve the imports of an in-memory source for a given module name."""
    collector = _ImportCollector(module, is_package=is_package)
    collector.visit(ast.parse(source))
    return collector.runtime


# ---------------------------------------------------------------------------
# Positive control: the resolver itself must catch relative imports.
# ---------------------------------------------------------------------------


def test_relative_import_resolution_catches_evasion() -> None:
    """A deferred relative import must resolve to its real dotted module path.

    This is the regression guard for the boundary gate itself: absolute imports
    were already detected, but ``from ..infrastructure.excel import X`` inside a
    function previously resolved to ``infrastructure.excel`` and slipped through.
    """
    source = (
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
        "    return infrastructure\n"
    )
    forbidden = ("uebench.infrastructure",)
    matched = {name for name in _resolve("uebench.ui.probe_module", source) if name.startswith(forbidden)}
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
# Absolute ImportFrom must be resolved by Python import semantics
# ---------------------------------------------------------------------------


def test_absolute_import_from_is_not_prefixed_with_current_package() -> None:
    """``level == 0`` is absolute: only ``node.module`` counts.

    Regression guard for the bypass where ``from openpyxl import Workbook``
    inside ``uebench.application.facade`` resolved to
    ``uebench.application.openpyxl`` and therefore never matched the
    ``openpyxl`` rule.
    """
    for module, source, expected in (
        ("uebench.application.facade", "from openpyxl import Workbook\n", "openpyxl"),
        ("uebench.application.facade", "def x():\n    from openpyxl import Workbook\n", "openpyxl"),
        (
            "uebench.ui.main_window",
            "from uebench.infrastructure.excel import WorkbookImportService\n",
            "uebench.infrastructure",
        ),
        (
            "uebench.infrastructure.excel",
            "from uebench.ui.main_window import MainWindow\n",
            "uebench.ui",
        ),
    ):
        collector = _ImportCollector(module)
        collector.visit(ast.parse(source))
        matched = sorted(name for name in collector.runtime if name.startswith(expected))
        assert matched, f"{module}: {source.strip()!r} must resolve to a {expected}... name"
        assert not any(name.startswith(module + ".") for name in collector.runtime), (
            f"{module}: absolute import must not be prefixed with the importing package"
        )


APPLICATION_FORBIDDEN = (
    "PySide6",
    "sqlalchemy",
    "openpyxl",
    "uebench.infrastructure",
    "uebench.ui",
    "uebench.bootstrap",
)
UI_FORBIDDEN = ("uebench.infrastructure", "uebench.bootstrap")
INFRASTRUCTURE_FORBIDDEN = ("uebench.ui", "uebench.bootstrap")


def test_application_absolute_openpyxl_import_is_a_violation() -> None:
    path = SRC / "application" / "facade.py"
    assert _violations_in_source("from openpyxl import Workbook\n", path, APPLICATION_FORBIDDEN)


def test_application_function_level_absolute_openpyxl_import_is_a_violation() -> None:
    path = SRC / "application" / "facade.py"
    source = "def lazy():\n    from openpyxl import Workbook\n    return Workbook\n"
    assert _violations_in_source(source, path, APPLICATION_FORBIDDEN)


def test_ui_absolute_infrastructure_import_is_a_violation() -> None:
    path = SRC / "ui" / "main_window.py"
    source = "from uebench.infrastructure.excel import WorkbookImportService\n"
    assert _violations_in_source(source, path, UI_FORBIDDEN)
    # A deferred absolute import must be caught too.
    deferred = "def lazy():\n    from uebench.infrastructure.excel import X\n"
    assert _violations_in_source(deferred, path, UI_FORBIDDEN)


def test_infrastructure_absolute_ui_import_is_a_violation() -> None:
    path = SRC / "infrastructure" / "excel.py"
    source = "from uebench.ui.main_window import MainWindow\n"
    assert _violations_in_source(source, path, INFRASTRUCTURE_FORBIDDEN)


def test_application_relative_infrastructure_import_is_a_violation() -> None:
    """Relative and absolute forms of the same violation must both be caught.

    ``..`` from ``uebench.application.*`` / ``uebench.application`` escapes the
    layer into ``uebench.infrastructure``, which the Application rule forbids.
    """
    source = "from ..infrastructure import excel\n"
    assert "uebench.infrastructure" in _resolve("uebench.application", source, is_package=True)
    assert "uebench.infrastructure" in _resolve("uebench.application.facade", source)
    assert _violations_in_source(source, SRC / "application" / "facade.py", APPLICATION_FORBIDDEN)


def test_relative_import_that_stays_inside_the_layer_is_not_a_violation() -> None:
    """The gate must not over-report a same-layer relative import.

    ``from .infrastructure import excel`` inside ``uebench.application`` targets
    ``uebench.application.infrastructure`` (its own subpackage), not the
    infrastructure layer.
    """
    resolved = _resolve("uebench.application", "from .infrastructure import excel\n", is_package=True)
    assert "uebench.application.infrastructure" in resolved
    assert not any(name.startswith("uebench.infrastructure") for name in resolved)
    assert _violations_in_source(
        "from .infrastructure import excel\n",
        SRC / "application" / "__init__.py",
        APPLICATION_FORBIDDEN,
    ) == []


def test_package_init_relative_imports_resolve_against_the_package() -> None:
    """A package ``__init__.py`` is the package itself, not a submodule."""
    assert _module_name(SRC / "application" / "__init__.py") == "uebench.application"
    assert _is_package_file(SRC / "application" / "__init__.py")
    assert not _is_package_file(SRC / "application" / "facade.py")

    # level 1 from the package -> the package itself
    resolved = _resolve("uebench.application", "from . import services\n", is_package=True)
    assert "uebench.application.services" in resolved

    # level 2 from the package -> its parent package
    resolved = _resolve("uebench.application", "from ..infrastructure import excel\n", is_package=True)
    assert "uebench.infrastructure" in resolved

    # A module one level deeper also anchors level 1 at its package.
    resolved = _resolve("uebench.application.nested.mod", "from . import sibling\n")
    assert "uebench.application.nested.sibling" in resolved

    # The package file itself would be reported by the layer rule.
    assert _violations_in_source(
        "from ..infrastructure import excel\n",
        SRC / "application" / "__init__.py",
        APPLICATION_FORBIDDEN,
    )


def test_legitimate_imports_are_not_flagged() -> None:
    """Normal same-layer and stdlib imports must not be reported."""
    path = SRC / "application" / "facade.py"
    source = (
        "from __future__ import annotations\n"
        "from decimal import Decimal\n"
        "from typing import TYPE_CHECKING\n"
        "from uebench.domain.models import Grade\n"
        "from .ports import TemplatePort\n"
        "from .services import EvaluationService\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from pathlib import Path\n"
    )
    assert _violations_in_source(source, path, APPLICATION_FORBIDDEN) == []
    assert _violations_in_source(source, path, UI_FORBIDDEN) == []
    assert _violations_in_source(source, path, INFRASTRUCTURE_FORBIDDEN) == []


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


def test_package_reconciliation_reaches_cleanup_only_through_the_port() -> None:
    """``package_reconciliation`` must reach the cleanup gate through the port.

    The module calls ``StandardPackagePort.cleanup_legacy_sources()`` on every
    startup reconciliation, before the decision table.  The obvious shortcut
    would be to import ``uebench.infrastructure.packages`` — even deferred
    inside the method — to call the service directly, which the layer rule
    forbids.  The repository-wide application rule already covers this file;
    this guard makes the intent explicit and names the eviction, so the reason
    the port exists (no application→infrastructure import) cannot be
    refactored away silently.  Both runtime and ``TYPE_CHECKING`` imports are
    checked, so a type-only alias cannot smuggle the adapter in either.
    """
    module = SRC / "application" / "package_reconciliation.py"
    assert module.exists()
    collector = _collect(module)
    imports = collector.runtime | collector.type_only
    assert not [name for name in imports if name.startswith("uebench.infrastructure")], (
        "application/package_reconciliation.py must not import the package adapter: "
        "call cleanup_legacy_sources through the port declared in application/ports.py"
    )
    assert "uebench.application.ports" in imports or "ports" in {
        name.split(".")[-1] for name in imports
    }, "the cleanup gate must come from the application-layer port module"
