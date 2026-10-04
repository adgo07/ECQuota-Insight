"""ECQ-RS05 §8 — Source Gate.

This gate runs on a plain checkout, **before** anything is built.  It may only
assert facts provable from source and configuration, and it must never require a
built artifact.  Anything that genuinely depends on a Candidate artifact belongs
in ``tests/test_release_artifacts.py`` (the Artifact Gate) instead.

Three rules are enforced here:

1. **No artifact dependency.**  No path under ``dist/`` is asserted to exist.
2. **Version consistency** is re-checked (the same authority as
   ``tests/test_release_version_consistency.py``, so the Source Gate is a single
   entry point for CI).
3. **Pinned inputs are pinned.**  The standard package is a tracked release
   input at ``release/standard-packages/`` with a recorded SHA256 in
   ``PIN.json``; the PyInstaller spec must bundle *that* file, never the copy a
   clean checkout does not have.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Name of the build-output tree.  The Source Gate must never *require* anything
#: inside it; it only appears here as a forbidden substring in the spec.
FORBIDDEN_PATH_ROOT = "dist"

#: Pinned release input (tracked): a clean checkout has it, ``dist/`` does not.
PINNED_PACKAGE_FILE = "initial-standard-package-published.uebench"
PINNED_PACKAGE_DIR = ROOT / "release" / "standard-packages"
PIN_JSON = PINNED_PACKAGE_DIR / "PIN.json"

SPEC = ROOT / "uebench.spec"
INSTALLER_ISS = ROOT / "packaging" / "installer.iss"
PUBLIC_KEY = ROOT / "src" / "uebench" / "resources" / "update_public_key.pem"

LEGACY_CONFIRMATION_WORKBOOK = "统一标准规则确认表.xlsx"
GB29446_TEMPLATE = "GB29446选煤电力消耗限额导入模板.xlsx"

#: ECQ-RS05 §18 — governance documents a source recipient needs to reproduce
#: the released state.  Mirrors ``tools/build_source_zip.py`` ``MANDATORY_ROOT_FILES``.
MANDATED_GOVERNANCE_FILES: tuple[str, ...] = (
    "AGENTS.md",
    "platform-lock.json",
    "PLATFORM_BASELINE.md",
    "TASK_STATE.md",
    "HANDOFF.md",
    "STANDARD_ISSUES_REGISTER.md",
    "参考标准开发路线.md",
)

#: ICU builds that must never be bundled next to Qt6Core (Poppler's ICU 78
#: exports version-suffixed symbols such as ``ucnv_open_78``).
FORBIDDEN_PAYLOAD_BINARIES: tuple[str, ...] = ("icuuc.dll", "icudt78.dll")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _load_sibling_module(name: str, path: Path) -> ModuleType:
    """Import a ``tools/`` script that itself imports siblings by bare name."""
    import importlib.util

    tools_dir = ROOT / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def release_version() -> ModuleType:
    from tests.test_release_version_consistency import load_release_version

    return load_release_version()


@pytest.fixture(scope="module")
def version(release_version: ModuleType) -> str:
    return release_version.project_version()


def _git_tracks(relative: str) -> bool:
    """True when ``relative`` is a tracked path (i.e. present in a clean clone)."""
    try:
        completed = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:  # pragma: no cover - git unavailable
        return False
    return completed.returncode == 0


def _require_tracked_source(relative: str, why: str) -> None:
    """Skip with an explicit reason when an input is absent from this checkout.

    A source input that git says *should* be here but is not present is a real
    problem and fails; a genuinely absent input is reported as SKIP so the gate
    never invents a PASS.
    """
    if (ROOT / relative).exists():
        return
    if _git_tracks(relative):
        pytest.fail(f"source 输入缺失（git 已跟踪，说明工作区不完整）：{relative} — {why}")
    pytest.skip(f"SKIP: source 输入不在本检出中：{relative}（{why}）")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------
# 1. Version consistency (Source Gate entry point)
# --------------------------------------------------------------------------


def test_source_gate_version_consistency(release_version: ModuleType) -> None:
    problems = release_version.check(ROOT)
    assert problems == [], (
        "派生版本文件与 pyproject.toml 不一致；请运行 "
        f"python tools/release_version.py --generate\n问题：{problems}"
    )


def test_source_gate_asserts_nothing_about_built_artifacts() -> None:
    """The Source Gate must never require a built artifact.

    Enforced structurally (AST, not text matching): this module may not build a
    path into the build-output tree.  The tree's name appears here only as a
    *forbidden substring* that is searched for inside ``uebench.spec``, never as
    a path this test requires to exist.
    """
    checks: list[tuple[str, str]] = []
    source = Path(__file__).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
            continue
        if not isinstance(node.right, ast.Constant) or not isinstance(
            node.right.value, str
        ):
            continue
        if node.right.value.split("/")[0] == FORBIDDEN_PATH_ROOT:
            checks.append((f"line {node.lineno}", ast.unparse(node)))
    assert not checks, f"Source Gate 把构建产物目录当作断言路径：{checks}"
    assert not (ROOT / "tests" / "test_frozen_release.py").exists(), (
        "旧的 tests/test_frozen_release.py 在构建产物缺失时硬失败，已被 Source Gate 取代"
    )


# --------------------------------------------------------------------------
# 2. Installer script contents
# --------------------------------------------------------------------------


def test_installer_does_not_reference_the_legacy_confirmation_workbook() -> None:
    text = INSTALLER_ISS.read_text(encoding="utf-8")
    assert LEGACY_CONFIRMATION_WORKBOOK not in text, (
        f"packaging/installer.iss 不得再引用 {LEGACY_CONFIRMATION_WORKBOOK}"
        "（LEGACY_REFERENCE_ONLY，不是 0.2.0 交付内容）"
    )


def test_installer_references_the_gb29446_template() -> None:
    text = INSTALLER_ISS.read_text(encoding="utf-8")
    assert GB29446_TEMPLATE in text, (
        f"packaging/installer.iss 必须交付 GB 29446 导入模板 {GB29446_TEMPLATE}"
    )
    assert f"dist\\release\\{GB29446_TEMPLATE}" in text, (
        "GB 29446 导入模板必须从交付目录 dist\\release 安装"
    )


# --------------------------------------------------------------------------
# 3. PyInstaller spec: pinned input + forbidden payload binaries
# --------------------------------------------------------------------------


def test_spec_does_not_bundle_the_standard_package_from_the_build_output() -> None:
    """A clean checkout has no ``dist/``; the spec must not depend on it.

    Both the ``datas`` entry and the ICU/WebEngine filter must resolve the
    pinned package from the repository release input.
    """
    text = SPEC.read_text(encoding="utf-8")
    forbidden = "dist" + "/standard-packages/" + PINNED_PACKAGE_FILE
    offenders = [
        f"L{number}: {line.strip()}"
        for number, line in enumerate(text.splitlines(), start=1)
        if forbidden in line.replace("\\", "/")
    ]
    assert not offenders, (
        "uebench.spec 仍引用构建产物目录下的标准包副本；干净检出没有该文件，"
        f"构建会在 Analysis 阶段失败：{offenders}"
    )


def test_spec_bundles_the_pinned_release_input() -> None:
    """The spec must bundle ``release/standard-packages/<pinned>.uebench``."""
    text = SPEC.read_text(encoding="utf-8")
    pinned = "release/standard-packages/" + PINNED_PACKAGE_FILE
    assert pinned in text, (
        "uebench.spec 必须把仓库内固定发布输入 "
        f"{pinned} 打包为 uebench/resources/...；"
        "该发布输入由 release/standard-packages/PIN.json 锁定哈希。"
    )
    assert "uebench/resources" in text, (
        "固定标准包必须打包到 uebench/resources/ 下，应用才能作为初始包安装"
    )


def test_spec_excludes_icu_and_qtwebengine_binaries() -> None:
    text = SPEC.read_text(encoding="utf-8")
    assert "icuuc.dll" in text and "icudt78.dll" in text, (
        "uebench.spec 必须显式排除不兼容的 ICU 二进制 icuuc.dll / icudt78.dll"
    )
    assert "qt6webengine" in text.lower() and "qt6webview" in text.lower(), (
        "uebench.spec 必须排除 QtWebEngine / QtWebView 运行时"
    )


def test_spec_version_resource_points_at_the_generated_file() -> None:
    text = SPEC.read_text(encoding="utf-8")
    assert 'project_root / "packaging" / "version_info.txt"' in text
    assert "version=str(" in text


# --------------------------------------------------------------------------
# 4. Pinned standard package: existence, pin match, verified install
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pin() -> dict[str, Any]:
    _require_tracked_source(
        f"release/standard-packages/{PINNED_PACKAGE_FILE}",
        "固定正式标准包是发布输入",
    )
    if not PIN_JSON.exists():
        pytest.skip(
            "SKIP: release/standard-packages/PIN.json 不存在，无法核对固定标准包哈希"
        )
    return json.loads(PIN_JSON.read_text(encoding="utf-8"))


def test_pinned_package_exists_and_is_not_empty() -> None:
    _require_tracked_source(
        f"release/standard-packages/{PINNED_PACKAGE_FILE}",
        "固定正式标准包是发布输入",
    )
    package = PINNED_PACKAGE_DIR / PINNED_PACKAGE_FILE
    assert package.stat().st_size > 1 << 20, "固定标准包过小，疑似占位文件"


def test_pinned_package_sha256_matches_pin(pin: dict[str, Any]) -> None:
    package = PINNED_PACKAGE_DIR / str(pin["file"])
    assert package.exists(), f"PIN.json 声明的标准包不存在：{package}"
    assert pin["schema"] == "ecq.standard-package-pin.v1"
    assert pin["size"] == package.stat().st_size, "固定标准包大小与 PIN.json 不一致"
    actual = _sha256(package)
    assert actual == pin["sha256"], (
        f"固定标准包 SHA256 与 PIN.json 不一致：{actual} != {pin['sha256']}"
    )


def test_pinned_package_installs_with_signature_verification(
    pin: dict[str, Any], tmp_path: Path
) -> None:
    """The pinned package must really pass the product's own verifier.

    ``StandardPackageService.preview`` is the system's verifier: it checks the
    Ed25519 signature against ``update_public_key.pem``, the manifest/file
    hashes, and the minimum-app-version / rule-engine-version contract.
    ``install`` then performs the real install into an isolated data directory.
    """
    package = PINNED_PACKAGE_DIR / str(pin["file"])
    assert PUBLIC_KEY.exists(), f"缺少更新公钥：{PUBLIC_KEY}"

    from uebench.infrastructure.backup import BackupService
    from uebench.infrastructure.database import DatabaseManager
    from uebench.infrastructure.packages import StandardPackageService
    from uebench.infrastructure.paths import AppPaths
    from uebench.infrastructure.repositories import AuditRepository, SqlStandardRepository

    paths = AppPaths.from_root(tmp_path / "appdata")
    paths.ensure()
    database = DatabaseManager(paths.database)
    database.initialize()
    try:
        audit = AuditRepository(database)
        service = StandardPackageService(
            paths,
            database,
            StandardPackageService.load_public_key(PUBLIC_KEY),
            BackupService(paths, database, audit),
            SqlStandardRepository(database, audit),
            audit,
        )

        report = service.preview(package)
        assert report.valid, f"固定标准包未通过签名/结构校验：{report.errors}"
        assert report.manifest is not None
        assert report.package_sha256 == pin["sha256"], (
            "校验得到的标准包哈希与 PIN.json 不一致"
        )
        assert report.manifest.standard_count == pin["standard_count"]
        assert report.manifest.rule_count == pin["rule_count"]
        assert report.manifest.data_version == pin["data_version"]

        result = service.install(package)
        assert result.standards_installed == pin["standard_count"]
        assert result.package_id == pin["package_id"]
        assert service.latest_manifest() is not None
    finally:
        database.dispose()


def test_pinned_package_public_key_is_the_pin_verifying_key(pin: dict[str, Any]) -> None:
    """The key recorded in ``PIN.json`` is the key this repository actually ships."""
    declared = str(pin["signature"]["verifying_key"]).replace("\\", "/")
    assert declared == "src/uebench/resources/update_public_key.pem"
    assert (ROOT / declared).exists()
    assert pin["signature"]["algorithm"] == "ed25519"


# --------------------------------------------------------------------------
# 5. Source ZIP: mandated governance files + version-derived output name
# --------------------------------------------------------------------------


def test_source_zip_includes_the_mandated_governance_files(tmp_path: Path) -> None:
    from tools.build_source_zip import MANDATORY_ROOT_FILES, build_source_zip

    assert set(MANDATED_GOVERNANCE_FILES) == set(MANDATORY_ROOT_FILES), (
        "Source Gate 与 tools/build_source_zip.py 的强制治理文件清单不一致"
    )
    output = tmp_path / "source.zip"
    build_source_zip(output)
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
    missing = [name for name in MANDATED_GOVERNANCE_FILES if name not in names]
    assert not missing, f"源码包缺少强制治理文件：{missing}"


def test_source_zip_missing_governance_file_fails_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing governance document must fail loudly, not be skipped silently."""
    from tools import build_source_zip as module

    fake_root = tmp_path / "repo"
    (fake_root / "src").mkdir(parents=True)
    monkeypatch.setattr(module, "project_root", lambda: fake_root)
    with pytest.raises(SystemExit):
        module.build_source_zip(tmp_path / "out.zip")


def test_source_zip_default_output_name_is_version_derived(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--output`` is optional; its default must come from the version tool."""
    from tools import build_source_zip as module

    captured: dict[str, Path] = {}

    def fake_build(output: Path) -> Path:
        captured["output"] = output
        # ``output`` is the repository-RELATIVE default.  Resolve it under a
        # temporary working directory (see chdir below) instead of the repo
        # root: writing it at the repo root would overwrite the real built
        # Candidate's UEBench-source-<version>.zip with the placeholder bytes.
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"placeholder")
        return output

    class FakeArchive:
        """Stands in for the re-read ``main()`` does to count members."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> "FakeArchive":
            return self

        def __exit__(self, *_exc: object) -> bool:
            return False

        def namelist(self) -> list[str]:
            return ["pyproject.toml"]

    monkeypatch.setattr(module, "build_source_zip", fake_build)
    monkeypatch.setattr(module.zipfile, "ZipFile", FakeArchive)
    # Run in a temporary directory so the relative default output is written
    # somewhere disposable.  Pointing this at the repository root used to
    # clobber dist/release/UEBench-source-<version>.zip when a Candidate had
    # already been built.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["build_source_zip.py"])
    module.main()

    version = _load_sibling_module(
        "release_version_for_source_gate", ROOT / "tools" / "release_version.py"
    ).project_version()
    expected = Path("dist") / "release" / module.artifact_names(version)["source"]
    assert captured["output"] == expected, (
        f"源码包默认输出名必须由版本推导：{captured['output']} != {expected}"
    )
    assert version in expected.name, "默认输出名必须包含当前产品版本"


def test_source_zip_source_derives_its_default_from_the_version_tool() -> None:
    text = (ROOT / "tools" / "build_source_zip.py").read_text(encoding="utf-8")
    assert "artifact_names(" in text and "project_version()" in text
    assert "UEBench-source-0.1.0" not in text
