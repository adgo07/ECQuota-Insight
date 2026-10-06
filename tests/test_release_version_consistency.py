"""ECQ-RS05 §8 — Version consistency Gate.

``pyproject.toml`` ``[project] version`` is the **only** authoritative product
version.  Everything else in the formal release chain is generated from it by
``tools/release_version.py``.  This module proves three things:

1. the generated files really are in sync with ``pyproject.toml``;
2. no formal release-chain file still carries the previous product version
   ``0.1.0`` (an explicit, auditable allow-list of scanned files — the legacy
   0.1.0 *artifacts* and the historically banner-labelled documents are
   deliberately out of scope, see ``_OUT_OF_SCOPE_LEGACY`` below);
3. the drift detector itself actually detects drift.

Notes on what is intentionally **not** flagged:

* ``RULE_ENGINE_VERSION``, ``NUMERIC_CONTRACT_VERSION``, ``TEMPLATE_VERSION``
  and ``GB29446_EXCEL_TEMPLATE_VERSION`` are *separate version domains* — they
  version a contract or a template, not the product.
* ``minimum_app_version="0.1.0"`` in
  ``src/uebench/infrastructure/packages.py``
  / ``tools/publish_confirmed_rules.py`` is the *minimum application version a
  standard package requires*.  That is a different concept and is correctly
  still ``0.1.0``.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Directory holding ``tools/release_version.py``.  That module imports
#: ``release_version`` as a *sibling* module, so ``tools/`` itself must be on
#: ``sys.path``; every other ``tests/`` module that touches it does the same.
TOOLS_DIR = ROOT / "tools"

#: Files whose version literals are part of the product release chain.
#: Deliberately an explicit list (not a recursive sweep) so that what this gate
#: covers is auditable: adding a new product file means adding one line here.
RELEASE_CHAIN_FILES: tuple[Path, ...] = (
    ROOT / "pyproject.toml",
    ROOT / "uebench.spec",
    ROOT / "run_uebench.py",
    ROOT / "packaging" / "version.iss",
    ROOT / "packaging" / "version_info.txt",
    ROOT / "packaging" / "installer.iss",
    ROOT / "tools" / "release_version.py",
    ROOT / "tools" / "audit_release.py",
    ROOT / "tools" / "build_source_zip.py",
    ROOT / "tools" / "build_payload_manifest.py",
    ROOT / "tools" / "build_release_templates.py",
    ROOT / "tools" / "write_build_info.py",
    ROOT / "scripts" / "build_release.ps1",
    ROOT / "scripts" / "sync_release.ps1",
    ROOT / "scripts" / "验收助手.ps1",
    ROOT / "scripts" / "验收助手.cmd",
)

#: Package source trees that must not carry a stale *product* version literal.
RELEASE_CHAIN_SOURCE_TREES: tuple[Path, ...] = (ROOT / "src" / "uebench",)

#: Files that legitimately still describe the previous formal release.  They are
#: release *history*: 0.1.0 there is a factual statement about the earlier
#: deliverable, not a stale product version.  Listed here so the exclusion is
#: explicit rather than an accident of which directories are scanned.
_OUT_OF_SCOPE_LEGACY: tuple[str, ...] = (
    "dist/** (0.1.0 legacy artifacts are historical evidence, never rebuilt)",
    "docs/安装发布说明.md",
    "docs/交付清单.md",
    "docs/非程序员验收与AI开发教程.md",
    "docs/验收记录.md",
    "docs/history/**",
    "TASK_STATE.md",
    "HANDOFF.md",
    "README.md",
    "参考标准开发路线.md",
)

#: Separate version domains.  A line that *names* one of these is carrying that
#: domain's version, not the product version, so it is not drift.  These are the
#: deliberate exclusions described in the module docstring.
_SEPARATE_VERSION_DOMAINS: tuple[str, ...] = (
    "RULE_ENGINE_VERSION",
    "NUMERIC_CONTRACT_VERSION",
    "TEMPLATE_VERSION",
    "GB29446_EXCEL_TEMPLATE_VERSION",
    "minimum_app_version",
)

_PREVIOUS_PRODUCT_VERSION = "0.1.0"
_VERSION_LITERAL_RE = re.compile(r"\d+\.\d+\.\d+")

#: Line-comment introducers for the languages in the scanned release chain.
_COMMENT_PREFIXES = ("#", ";", "//", "<!--")


def _code_only(line: str) -> str:
    """Strip a full-line comment, keeping code lines (incl. inline notes) intact.

    A full-line comment is documentation: ``# 6) 用户文档与验收助手（0.2.0 集合；
    旧 0.1.0 文档保留为历史材料）`` describes history, it does not assign a
    product version.  Inline comments are deliberately **not** stripped, so a
    stray version literal can never hide behind one.
    """
    stripped = line.strip()
    if stripped.startswith(_COMMENT_PREFIXES):
        return ""
    return line


def stale_version_offenders(path: Path) -> list[str]:
    """Every ``0.1.0`` occurrence in ``path`` that is a stale product version.

    Returns ``"L<line>: <text>"`` entries; an empty list means the file is clean.
    """
    offenders: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        code = _code_only(line)
        if _PREVIOUS_PRODUCT_VERSION not in code:
            continue
        if any(domain in code for domain in _SEPARATE_VERSION_DOMAINS):
            continue
        offenders.append(f"L{number}: {code.strip()}")
    return offenders


def load_release_version() -> ModuleType:
    """Import ``tools/release_version.py`` with ``tools/`` on ``sys.path``."""
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location(
        "release_version", TOOLS_DIR / "release_version.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def release_version() -> ModuleType:
    """The authoritative version tool, imported as a sibling of ``tools/``."""
    return load_release_version()


@pytest.fixture(scope="module")
def version(release_version: ModuleType) -> str:
    return release_version.project_version()


# --------------------------------------------------------------------------
# 1. Derived files are in sync with the authority
# --------------------------------------------------------------------------


def test_release_version_check_reports_no_problems(release_version: ModuleType) -> None:
    """``tools/release_version.check(ROOT)`` is the single gate for drift."""
    problems = release_version.check(ROOT)
    assert problems == [], (
        "派生版本文件与 pyproject.toml 不一致；请运行 "
        f"python tools/release_version.py --generate\n问题：{problems}"
    )


def test_uebench_dunder_version_equals_pyproject_version(
    release_version: ModuleType, version: str
) -> None:
    import uebench

    assert release_version.project_version() == version
    assert uebench.__version__ == version, (
        f"uebench.__version__={uebench.__version__!r} 与 pyproject.toml 的 {version!r} 不一致"
    )


def test_release_version_module_is_the_dunder_version_source() -> None:
    """``uebench/__init__.py`` must re-export the generated single source."""
    source = (ROOT / "src" / "uebench" / "__init__.py").read_text(encoding="utf-8")
    assert "from ._version import __version__" in source


def test_version_info_txt_contains_numeric_tuple_and_string(
    release_version: ModuleType, version: str
) -> None:
    text = (ROOT / "packaging" / "version_info.txt").read_text(encoding="utf-8")
    numeric = release_version.version_tuple(version)
    assert str(tuple(numeric)) in text, (
        f"packaging/version_info.txt 缺少 VS_FIXEDFILEINFO 数值元组 {numeric}"
    )
    assert f"'{version}'" in text, (
        f"packaging/version_info.txt 缺少字符串版本号 '{version}'"
    )
    # Both the file version and the product version must carry it.
    assert text.count(f"'{version}'") == 2, (
        "packaging/version_info.txt 的 FileVersion 与 ProductVersion 都必须是当前版本"
    )


def test_version_iss_declares_my_app_version(version: str) -> None:
    text = (ROOT / "packaging" / "version.iss").read_text(encoding="utf-8")
    declarations = re.findall(r'^\s*#define\s+MyAppVersion\s+"([^"]*)"', text, re.MULTILINE)
    assert declarations == [version], (
        f"packaging/version.iss 必须只声明 MyAppVersion = {version!r}，实际：{declarations}"
    )


def test_installer_iss_includes_version_iss_and_uses_the_macro() -> None:
    text = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    assert '#include "version.iss"' in text, "packaging/installer.iss 必须包含 version.iss"
    assert "AppVersion={#MyAppVersion}" in text
    # ECQ-RS05 candidate identity: the output name is the product version plus the
    # Candidate suffix, which the build script supplies as an ISCC /D symbol and
    # which defaults to the empty string (formal release cut).
    assert "#ifndef MyAppCandidateSuffix" in text
    assert "OutputBaseFilename=UEBench-Setup-{#MyAppVersion}{#MyAppCandidateSuffix}-x64" in text


def test_installer_iss_has_no_hard_coded_version_literal() -> None:
    """Every version-bearing line must be macro-driven.

    ECQ-RS05 removed the last hand-typed version literals (the delivered document
    file names, which used to say ``-0.2.0.md``) so a version bump and a Candidate
    build both flow through ``{#MyAppVersion}``.  Any ``X.Y.Z`` here is drift.
    """
    text = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    offenders: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not _VERSION_LITERAL_RE.search(line):
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith(_COMMENT_PREFIXES):
            continue  # comment / provenance note, not a directive
        offenders.append(f"L{number}: {stripped}")
    assert not offenders, (
        "packaging/installer.iss 出现硬编码版本字面量；所有版本相关名称必须来自 "
        f"{{#MyAppVersion}}/{{#MyAppCandidateSuffix}}：{offenders}"
    )
    # The delivered documents are the case that used to be hand-typed.
    assert "..\\docs\\安装与发布说明-{#MyAppVersion}.md" in text
    assert "..\\docs\\交付清单-{#MyAppVersion}.md" in text
    assert "{#MyAppVersion}" in text


# --------------------------------------------------------------------------
# 2. No formal release-chain file still carries the previous product version
# --------------------------------------------------------------------------


def _release_chain_paths() -> list[Path]:
    paths: list[Path] = []
    for path in RELEASE_CHAIN_FILES:
        if path.exists():
            paths.append(path)
    for tree in RELEASE_CHAIN_SOURCE_TREES:
        assert tree.is_dir(), f"缺少发布链路源码目录：{tree}"
        for path in sorted(tree.rglob("*.py")):
            if "__pycache__" not in path.parts:
                paths.append(path)
    return paths


def test_release_chain_scan_is_non_trivial() -> None:
    """Guard against the scan silently collapsing to an empty file list."""
    paths = _release_chain_paths()
    assert len(paths) >= 20, f"发布链路扫描文件过少（{len(paths)}），allow-list 可能被破坏"
    names = {path.name for path in paths}
    assert {"pyproject.toml", "installer.iss", "version.iss", "audit_release.py"} <= names


@pytest.mark.parametrize("path", _release_chain_paths(), ids=lambda p: str(p.relative_to(ROOT)))
def test_release_chain_file_has_no_stale_product_version(path: Path) -> None:
    offenders = stale_version_offenders(path)
    assert not offenders, (
        f"{path.relative_to(ROOT)} 仍硬编码旧产品版本 {_PREVIOUS_PRODUCT_VERSION}：{offenders}。"
        "产品版本只能来自 pyproject.toml；独立版本域（"
        + "、".join(_SEPARATE_VERSION_DOMAINS)
        + "）与历史材料不在本扫描范围内。"
    )


def test_stale_version_scanner_detects_a_real_offender(tmp_path: Path) -> None:
    """Control for the scanner above: it must actually flag a stale version."""
    offender = tmp_path / "spec.py"
    offender.write_text('VERSION = "0.1.0"\n', encoding="utf-8")
    assert stale_version_offenders(offender) == ['L1: VERSION = "0.1.0"']

    # ... while the separate version domains and pure comments stay clean.
    clean = tmp_path / "clean.py"
    clean.write_text(
        'minimum_app_version: str = "0.1.0"\n'
        'RULE_ENGINE_VERSION = "0.1.0"\n'
        "# 旧 0.1.0 文档保留为历史材料\n",
        encoding="utf-8",
    )
    assert stale_version_offenders(clean) == []


def test_out_of_scope_legacy_material_is_documented() -> None:
    """The exclusion list must stay explicit and non-empty (auditability)."""
    assert len(_OUT_OF_SCOPE_LEGACY) >= 8
    # The legacy artifacts really do still exist, which is why they are excluded
    # instead of asserted against.
    legacy_portable = ROOT / "dist" / "release" / "UEBench-0.1.0-win-x64.zip"
    if legacy_portable.exists():
        assert _PREVIOUS_PRODUCT_VERSION in legacy_portable.name


# --------------------------------------------------------------------------
# 3. The drift detector actually detects drift
# --------------------------------------------------------------------------


def _fake_release_root(tmp_path: Path, version: str) -> Path:
    """A minimal repository skeleton with just the version-bearing files."""
    root = tmp_path
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "uebench"\nversion = "%s"\n' % version, encoding="utf-8"
    )
    (root / "src" / "uebench").mkdir(parents=True)
    (root / "packaging").mkdir(parents=True)
    return root


def test_check_detects_a_drifted_derived_file(
    release_version: ModuleType, tmp_path: Path
) -> None:
    """A drifted ``_version.py`` must be reported as a problem."""
    fake_version = "9.9.9"
    root = _fake_release_root(tmp_path, fake_version)
    release_version.generate(root, fake_version)
    assert release_version.check(root, fake_version) == []

    drifted = root / "src" / "uebench" / "_version.py"
    drifted.write_text(
        '"""Drifted copy."""\n\n__version__ = "1.2.3"\n', encoding="utf-8"
    )

    problems = release_version.check(root, fake_version)
    assert problems != []
    assert any("_version.py" in problem for problem in problems), problems


def test_check_detects_every_derived_file_independently(
    release_version: ModuleType, tmp_path: Path
) -> None:
    """Each generated file is checked on its own, not just the first one."""
    fake_version = "9.9.9"
    for relative in (
        Path("src/uebench/_version.py"),
        Path("packaging/version_info.txt"),
        Path("packaging/version.iss"),
    ):
        root = _fake_release_root(tmp_path / relative.name.replace(".", "-"), fake_version)
        release_version.generate(root, fake_version)
        (root / relative).write_text("garbage\n", encoding="utf-8")
        problems = release_version.check(root, fake_version)
        assert problems, f"{relative} 漂移未被检出"
        assert any(
            relative.as_posix() in problem or str(relative) in problem
            for problem in problems
        ), f"{relative} 的漂移未出现在：{problems}"


def test_check_reports_a_missing_derived_file(
    release_version: ModuleType, tmp_path: Path
) -> None:
    """Deleting a generated file is drift too, not a silent pass."""
    fake_version = "9.9.9"
    root = _fake_release_root(tmp_path, fake_version)
    release_version.generate(root, fake_version)
    (root / "packaging" / "version.iss").unlink()

    problems = release_version.check(root, fake_version)
    assert any("version.iss" in problem for problem in problems), problems


# --------------------------------------------------------------------------
# 4. The authoritative version is machine-readable for CI / scripts
# --------------------------------------------------------------------------


def test_artifact_names_are_version_derived(
    release_version: ModuleType, version: str
) -> None:
    names = release_version.artifact_names(version)
    assert names["portable"] == f"UEBench-{version}-win-x64.zip"
    assert names["installer"] == f"UEBench-Setup-{version}-x64.exe"
    assert names["source"] == f"UEBench-source-{version}.zip"
    assert names["release_notes"] == f"安装与发布说明-{version}.md"
    # The pinned standard package and the GB 29446 template are version-less
    # release inputs: their identity is the pin / the standard, not the product.
    assert names["standard_package"] == "initial-standard-package-published.uebench"
    assert names["template"] == "GB29446选煤电力消耗限额导入模板.xlsx"


def test_cli_print_and_names_agree_with_the_module(
    release_version: ModuleType, version: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert release_version.main(["--print"]) == 0
    assert capsys.readouterr().out.strip() == version

    assert release_version.main(["--names"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == release_version.artifact_names(version)
