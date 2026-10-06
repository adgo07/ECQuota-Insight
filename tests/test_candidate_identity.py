"""ECQ-RS05 — Candidate identity in artifact names.

The problem this gate exists for: several *different* Release Candidates can all
be called ``UEBench-0.2.0-win-x64.zip`` and all carry ``0.2.0`` PE version
resources, so a human tester cannot tell two builds apart or trace one back to a
commit.

The fix is a ``candidate_id`` (``rc-<first 7 hex of the commit>``) inserted into
the three build-specific artifact names, while the product version stays exactly
``0.2.0``.  Three properties are pinned here:

1. ``artifact_names(v, None)`` yields the **formal release** names, unchanged, so
   the future formal release cut is not affected by this feature;
2. ``artifact_names(v, "rc-abcdef0")`` yields exactly the expected suffixed
   names, and only the three build-specific ones change;
3. the identity is *runtime* information: ``version.iss`` / ``_version.py`` /
   ``version_info.txt`` stay byte-identical whether or not a commit SHA is in
   play, so ``--check`` remains deterministic.
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
TOOLS_DIR = ROOT / "tools"
INSTALLER_ISS = ROOT / "packaging" / "installer.iss"

#: A synthetic 40-hex commit.  Candidate identity is pure string arithmetic, so
#: the gate does not depend on which commit happens to be checked out.
COMMIT = "0123456789abcdef0123456789abcdef01234567"
CANDIDATE = "rc-0123456"

#: Names that must NOT change when a Candidate identity is used: the standard
#: package and the GB 29446 template are version-less release inputs, and the
#: manifest / build info / checksum / helper / document names are fixed per
#: directory so the audit and the acceptance helper do not have to guess.
IDENTITY_FREE_NAMES: dict[str, str] = {
    "standard_package": "initial-standard-package-published.uebench",
    "template": "GB29446选煤电力消耗限额导入模板.xlsx",
    "sha256sums": "SHA256SUMS.txt",
    "payload_manifest": "payload-manifest.json",
    "build_info": "release-build-info.json",
    "helper_ps1": "验收助手.ps1",
    "helper_cmd": "验收助手.cmd",
}

_VERSION_LITERAL_RE = re.compile(r"\d+\.\d+\.\d+")
_COMMENT_PREFIXES = ("#", ";", "//", "<!--")


def load_release_version() -> ModuleType:
    """Import ``tools/release_version.py`` with ``tools/`` on ``sys.path``."""
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location(
        "release_version_candidate_identity", TOOLS_DIR / "release_version.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def release_version() -> ModuleType:
    return load_release_version()


@pytest.fixture(scope="module")
def version(release_version: ModuleType) -> str:
    return release_version.project_version()


# --------------------------------------------------------------------------
# 1. candidate_id()
# --------------------------------------------------------------------------


def test_candidate_id_uses_the_first_seven_characters(release_version: ModuleType) -> None:
    assert release_version.candidate_id(COMMIT) == "rc-0123456"
    # Seven characters is the documented prefix length, and it is taken from the
    # front of the SHA -- not from an abbreviated SHA's own tail.
    assert release_version.candidate_id(COMMIT)[3:] == COMMIT[:7]
    assert release_version.candidate_id("abcdef0") == "rc-abcdef0"


def test_candidate_id_normalizes_case_and_whitespace(release_version: ModuleType) -> None:
    assert release_version.candidate_id(COMMIT.upper()) == "rc-0123456"
    assert release_version.candidate_id(f"  {COMMIT}\n") == "rc-0123456"


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "not-a-commit", "012345", "zzzzzzz", "0" * 41, "rc-0123456"],
)
def test_candidate_id_rejects_anything_that_is_not_a_commit(
    release_version: ModuleType, bad: str
) -> None:
    with pytest.raises(ValueError):
        release_version.candidate_id(bad)


def test_candidate_id_is_recomputed_from_the_commit_not_stored(
    release_version: ModuleType,
) -> None:
    """Two different commits must never collide onto one identity."""
    other = "fedcba9876543210fedcba9876543210fedcba98"
    assert release_version.candidate_id(COMMIT) != release_version.candidate_id(other)
    assert release_version.candidate_id(other) == "rc-fedcba9"


# --------------------------------------------------------------------------
# 2. artifact_names()
# --------------------------------------------------------------------------


def test_artifact_names_without_identity_are_the_formal_release_names(
    release_version: ModuleType, version: str
) -> None:
    """``candidate_id=None`` is the future formal release cut: names unchanged."""
    names = release_version.artifact_names(version, None)
    assert names["portable"] == f"UEBench-{version}-win-x64.zip"
    assert names["installer"] == f"UEBench-Setup-{version}-x64.exe"
    assert names["source"] == f"UEBench-source-{version}.zip"
    assert names["release_notes"] == f"安装与发布说明-{version}.md"
    assert names["delivery_list"] == f"交付清单-{version}.md"
    for key, value in IDENTITY_FREE_NAMES.items():
        assert names[key] == value
    # The positional call must behave identically (the formal-release default).
    assert release_version.artifact_names(version) == names


def test_artifact_names_with_identity_insert_it_in_exactly_three_names(
    release_version: ModuleType, version: str
) -> None:
    formal = release_version.artifact_names(version)
    candidate = release_version.artifact_names(version, CANDIDATE)

    assert candidate["portable"] == f"UEBench-{version}-{CANDIDATE}-win-x64.zip"
    assert candidate["installer"] == f"UEBench-Setup-{version}-{CANDIDATE}-x64.exe"
    assert candidate["source"] == f"UEBench-source-{version}-{CANDIDATE}.zip"

    changed = {key for key in formal if formal[key] != candidate[key]}
    assert changed == {"portable", "installer", "source"}, (
        "候选标识只应改变便携包/安装包/源码包三个名字，实际变化：" + repr(sorted(changed))
    )
    assert set(candidate) == set(formal)
    for key, value in IDENTITY_FREE_NAMES.items():
        assert candidate[key] == value


def test_candidate_identity_appears_in_every_build_specific_name(
    release_version: ModuleType, version: str
) -> None:
    names = release_version.artifact_names(version, CANDIDATE)
    for key in ("portable", "installer", "source"):
        assert CANDIDATE in names[key], f"{key} 缺少候选标识：{names[key]}"
    assert names["portable"].startswith(f"UEBench-{version}-{CANDIDATE}-")
    assert names["installer"].startswith(f"UEBench-Setup-{version}-{CANDIDATE}-")
    assert names["source"].startswith(f"UEBench-source-{version}-{CANDIDATE}")


@pytest.mark.parametrize(
    "bad",
    ["  ", "0.2.0", "0123456", "rc-012345", "rc-0123456/../x", "rc-" + "0" * 41],
)
def test_artifact_names_reject_an_invalid_candidate_id(
    release_version: ModuleType, version: str, bad: str
) -> None:
    with pytest.raises(ValueError):
        release_version.artifact_names(version, bad)


def test_artifact_names_treat_a_blank_candidate_id_as_formal(
    release_version: ModuleType, version: str
) -> None:
    """An unset/blank identity is the formal release, not an error."""
    assert release_version.artifact_names(version, "") == release_version.artifact_names(
        version, None
    )


def test_artifact_names_normalize_an_uppercase_candidate_id(
    release_version: ModuleType, version: str
) -> None:
    assert release_version.artifact_names(version, CANDIDATE.upper()) == (
        release_version.artifact_names(version, CANDIDATE)
    )


# --------------------------------------------------------------------------
# 3. CLI: scripts obtain names and identity without hard-coding anything
# --------------------------------------------------------------------------


def test_cli_names_honour_source_commit(
    release_version: ModuleType, version: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert release_version.main(["--names", "--source-commit", COMMIT]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == release_version.artifact_names(version, CANDIDATE)
    assert payload["portable"] == f"UEBench-{version}-{CANDIDATE}-win-x64.zip"


def test_cli_names_honour_candidate_id(
    release_version: ModuleType, version: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert release_version.main(["--names", "--candidate-id", CANDIDATE]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == release_version.artifact_names(version, CANDIDATE)


def test_cli_names_without_identity_stay_formal(
    release_version: ModuleType, version: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert release_version.main(["--names"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == release_version.artifact_names(version, None)


def test_cli_prints_the_candidate_id(
    release_version: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    assert release_version.main(["--source-commit", COMMIT, "--print-candidate-id"]) == 0
    assert capsys.readouterr().out.strip() == CANDIDATE

    assert release_version.main(["--print-candidate-id"]) == 2
    assert "缺少候选标识" in capsys.readouterr().err


def test_cli_refuses_a_conflicting_candidate_id_and_commit(
    release_version: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    other = release_version.candidate_id("fedcba9876543210fedcba9876543210fedcba98")
    assert (
        release_version.main(
            ["--names", "--source-commit", COMMIT, "--candidate-id", other]
        )
        == 2
    )
    assert "不一致" in capsys.readouterr().err


# --------------------------------------------------------------------------
# 4. Inno Setup: the suffix is a macro, never a generated version file
# --------------------------------------------------------------------------


def test_installer_iss_uses_the_candidate_suffix_macro() -> None:
    text = INSTALLER_ISS.read_text(encoding="utf-8")
    assert "#ifndef MyAppCandidateSuffix" in text, (
        "packaging/installer.iss 必须为候选后缀提供 #ifndef 默认值"
    )
    assert re.search(
        r'^#define\s+MyAppCandidateSuffix\s+""\s*$', text, re.MULTILINE
    ), "packaging/installer.iss 必须默认 MyAppCandidateSuffix 为空串（正式发布名不变）"
    assert (
        "OutputBaseFilename=UEBench-Setup-{#MyAppVersion}{#MyAppCandidateSuffix}-x64"
        in text
    ), "安装程序输出名必须由 {#MyAppVersion}{#MyAppCandidateSuffix} 组合而成"


def test_installer_iss_has_no_hard_coded_version_literal() -> None:
    """The installer name must be macro-driven, not typed out.

    A single ``0.2.0`` typed into this file would break the 0.2.1 cut, so every
    version-bearing line (including the delivered document file names) is built
    from ``{#MyAppVersion}``.
    """
    text = INSTALLER_ISS.read_text(encoding="utf-8")
    offenders = [
        f"L{number}: {line.strip()}"
        for number, line in enumerate(text.splitlines(), start=1)
        if _VERSION_LITERAL_RE.search(line)
        and line.strip()
        and not line.strip().startswith(_COMMENT_PREFIXES)
    ]
    assert not offenders, f"packaging/installer.iss 出现硬编码版本字面量：{offenders}"
    assert "安装与发布说明-{#MyAppVersion}.md" in text
    assert "交付清单-{#MyAppVersion}.md" in text


# --------------------------------------------------------------------------
# 5. Generated version files stay commit-independent
# --------------------------------------------------------------------------


def _fake_release_root(root: Path, version: str) -> Path:
    """A minimal repository skeleton holding only the version-bearing files."""
    (root / "src" / "uebench").mkdir(parents=True, exist_ok=True)
    (root / "packaging").mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "uebench"\nversion = "%s"\n' % version, encoding="utf-8"
    )
    return root


def test_generated_files_are_commit_independent(
    release_version: ModuleType, version: str, tmp_path: Path
) -> None:
    """Regenerating with a Candidate identity in play changes nothing.

    This is the circularity guard: if the git SHA leaked into ``version.iss`` /
    ``_version.py`` / ``version_info.txt``, then ``--check`` could only pass on
    the commit the files were generated from -- and a Candidate could not be
    built from its own commit.
    """
    root = _fake_release_root(tmp_path / "repo", version)
    release_version.generate(root, version)
    baseline = {
        relative: (root / relative).read_text(encoding="utf-8")
        for relative in release_version.derived_files(version)
    }
    assert baseline, "派生文件集合不应为空"

    assert (
        release_version.main(
            [
                "--root",
                str(root),
                "--generate",
                "--source-commit",
                COMMIT,
                "--candidate-id",
                CANDIDATE,
            ]
        )
        == 0
    )
    for relative, content in baseline.items():
        regenerated = (root / relative).read_text(encoding="utf-8")
        assert regenerated == content, f"{relative} 在候选构建下发生了变化"
        assert CANDIDATE not in regenerated, f"{relative} 混入了候选标识"
        assert COMMIT not in regenerated, f"{relative} 混入了 git 提交号"
        assert COMMIT[:7] not in regenerated, f"{relative} 混入了 git 提交前缀"


def test_committed_generated_files_equal_the_canonical_rendering(
    release_version: ModuleType, version: str
) -> None:
    """The real files are purely version-derived (no commit, no identity)."""
    for relative, expected in release_version.derived_files(version).items():
        actual = (ROOT / relative).read_text(encoding="utf-8")
        assert actual == expected, f"{relative} 与权威版本 {version} 的渲染结果不一致"
        assert CANDIDATE not in actual
        assert "0123456" not in actual


def test_check_ignores_candidate_arguments(
    release_version: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--check`` is commit-independent: passing identity must not change it."""
    assert (
        release_version.main(
            ["--check", "--source-commit", COMMIT, "--candidate-id", CANDIDATE]
        )
        == 0
    )
    assert "版本一致性校验通过" in capsys.readouterr().out
