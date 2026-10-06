"""ECQ-RS05 — Candidate provenance: ``release-build-info.json`` and the audit.

Two gates live here:

* ``tools/write_build_info.py`` must record ``product_version``,
  ``candidate_id``, the full 40-hex ``source_commit``, ``source_dirty``, the
  standard-package identity, ``payload_tree_sha256`` and ``build_time_utc`` --
  and must refuse to call a dirty tree a formal Candidate.
* ``tools/audit_release.py`` must FAIL when any of that is missing, malformed
  (short/uppercase commit, non-40-hex), dirty, or disagrees with
  ``payload-manifest.json``.

The audit cases are driven against a **synthetic release directory** built in
``tmp_path``: one valid base case proves the audit accepts a correctly identified
Candidate, and each mutation then removes exactly one guarantee so the failure
cannot be caused by anything else.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
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
TOOLS_DIR = ROOT / "tools"

COMMIT = "0123456789abcdef0123456789abcdef01234567"
CANDIDATE = "rc-0123456"
BUILT_AT = "2026-01-02T03:04:05Z"
TREE_SHA256 = "c" * 64

REQUIRED_BUILD_INFO_KEYS = (
    "product_version",
    "candidate_id",
    "source_commit",
    "source_dirty",
    "standard_package_id",
    "standard_data_version",
    "standard_package_sha256",
    "payload_tree_sha256",
    "build_time_utc",
)

IDENTITY_KEYS = (
    "product_version",
    "candidate_id",
    "source_commit",
    "source_dirty",
    "standard_package_id",
    "standard_data_version",
    "standard_package_sha256",
    "build_time_utc",
)

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _load(name: str, path: Path) -> ModuleType:
    """Import a ``tools/`` script that imports its own siblings by bare name."""
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(TOOLS_DIR))
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
def write_build_info() -> ModuleType:
    return _load("write_build_info_under_test", TOOLS_DIR / "write_build_info.py")


@pytest.fixture(scope="module")
def audit_release() -> ModuleType:
    return _load("audit_release_under_test", TOOLS_DIR / "audit_release.py")


@pytest.fixture(scope="module")
def version(release_version: ModuleType) -> str:
    return release_version.project_version()


@pytest.fixture(scope="module")
def candidate_names(release_version: ModuleType, version: str) -> dict[str, str]:
    return release_version.artifact_names(version, CANDIDATE)


# --------------------------------------------------------------------------
# 1. The provenance document
# --------------------------------------------------------------------------


def test_build_info_contains_the_full_provenance(
    write_build_info: ModuleType, version: str, candidate_names: dict[str, str]
) -> None:
    info = write_build_info.build_info(
        candidate_names,
        built_at=BUILT_AT,
        candidate_id=CANDIDATE,
        commit=COMMIT,
        dirty=False,
        payload_tree_sha256=TREE_SHA256,
    )
    for key in REQUIRED_BUILD_INFO_KEYS:
        assert key in info, f"release-build-info.json 缺少必备溯源字段：{key}"

    assert info["product_version"] == version
    assert info["version"] == version, "旧字段 version 必须与 product_version 一致"
    assert info["candidate_id"] == CANDIDATE
    assert COMMIT_RE.match(info["source_commit"]), info["source_commit"]
    assert info["source_dirty"] is False
    assert isinstance(info["source_dirty"], bool)
    assert info["payload_tree_sha256"] == TREE_SHA256
    assert info["build_time_utc"] == BUILT_AT
    assert info["built_at"] == BUILT_AT

    # The standard package is a real, tracked release input: its identity must be
    # recorded, not left null.
    assert isinstance(info["standard_package_id"], str) and info["standard_package_id"]
    assert isinstance(info["standard_data_version"], str) and info["standard_data_version"]
    assert SHA256_RE.match(info["standard_package_sha256"]), info["standard_package_sha256"]

    # The pre-existing unsigned-release declaration must survive.
    assert info["authenticode_signed"] is False
    assert info["unsigned_reason"] == "no_signing_certificate"
    assert info["smart_screen_note"]
    # Diagnostics stay present but are never a Golden skip condition.
    assert info["python_version"]
    assert "golden" in info and "os" in info and "standard_package" in info


def test_build_info_asks_git_when_the_caller_does_not_say(
    write_build_info: ModuleType, candidate_names: dict[str, str]
) -> None:
    """Falling back to git is the documented behaviour for ad-hoc runs."""
    info = write_build_info.build_info(candidate_names, built_at=BUILT_AT)
    detected = write_build_info.source_commit()
    assert info["source_commit"] == detected
    # The real repository is dirty or clean, but either way the value is a bool
    # and agrees with what git reports right now.
    assert isinstance(info["source_dirty"], bool)
    assert info["source_dirty"] == write_build_info.source_dirty()


def test_embedded_identity_has_the_contract_keys(
    write_build_info: ModuleType, version: str, candidate_names: dict[str, str]
) -> None:
    info = write_build_info.build_info(
        candidate_names,
        built_at=BUILT_AT,
        candidate_id=CANDIDATE,
        commit=COMMIT,
        dirty=False,
        payload_tree_sha256=TREE_SHA256,
    )
    identity = write_build_info.build_identity(info)
    assert identity["schema"] == "ecq.build-identity.v1"
    assert set(identity) == {"schema", *IDENTITY_KEYS}
    assert "payload_tree_sha256" not in identity, (
        "内嵌标识位于 payload 内，不能包含描述该 payload 的 payload_tree_sha256"
    )
    assert identity["product_version"] == version
    assert identity["candidate_id"] == CANDIDATE
    assert identity["source_commit"] == COMMIT
    assert identity["source_dirty"] is False
    assert identity["build_time_utc"] == BUILT_AT
    assert identity["standard_package_sha256"] == info["standard_package_sha256"]


def test_embedded_identity_path_is_the_fixed_contract(
    write_build_info: ModuleType,
) -> None:
    """A UI workstream reads this exact path: do not move it."""
    assert (
        write_build_info.EMBEDDED_IDENTITY_RELATIVE_PATH.as_posix()
        == "_internal/uebench/resources/build-identity.json"
    )
    resolved = write_build_info.identity_path_for_payload(Path("dist/UEBench"))
    assert resolved.as_posix() == (
        "dist/UEBench/_internal/uebench/resources/build-identity.json"
    )


def test_active_marker_document_matches_the_contract(
    write_build_info: ModuleType, version: str, candidate_names: dict[str, str]
) -> None:
    info = write_build_info.build_info(
        candidate_names,
        built_at=BUILT_AT,
        candidate_id=CANDIDATE,
        commit=COMMIT,
        dirty=False,
        payload_tree_sha256=TREE_SHA256,
    )
    marker = write_build_info.active_candidate_document(info)
    assert marker["schema"] == "ecq.active-candidate.v1"
    assert marker["status"] == "ACTIVE"
    assert set(marker) == {
        "schema",
        "status",
        "candidate_id",
        "product_version",
        "source_commit",
        "source_dirty",
        "standard_package_id",
        "standard_data_version",
        "standard_package_sha256",
        "payload_tree_sha256",
        "assembled_at_utc",
    }
    assert marker["candidate_id"] == CANDIDATE
    assert marker["product_version"] == version
    assert marker["source_commit"] == COMMIT
    assert marker["source_dirty"] is False
    assert marker["payload_tree_sha256"] == info["payload_tree_sha256"]
    assert marker["assembled_at_utc"] == BUILT_AT


# --------------------------------------------------------------------------
# 2. Git provenance: commit + dirty, honoring .gitignore
# --------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "rs05@example.invalid")
    _git(repo, "config", "user.name", "ECQ-RS05 Test")
    (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    (repo / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt", ".gitignore")
    _git(repo, "commit", "-q", "-m", "initial")
    return repo


def test_source_commit_and_clean_tree(
    write_build_info: ModuleType, git_repo: Path
) -> None:
    commit = write_build_info.source_commit(git_repo)
    assert commit is not None and COMMIT_RE.match(commit), commit
    assert write_build_info.source_dirty(git_repo) is False
    assert write_build_info.git_provenance(git_repo) == (commit, False)


def test_source_dirty_is_true_for_an_untracked_file(
    write_build_info: ModuleType, git_repo: Path
) -> None:
    """An untracked file is a real difference from the commit."""
    (git_repo / "untracked.txt").write_text("new\n", encoding="utf-8")
    assert write_build_info.source_dirty(git_repo) is True


def test_source_dirty_ignores_gitignored_paths(
    write_build_info: ModuleType, git_repo: Path
) -> None:
    """Git applies .gitignore for us; ignored build output is not dirt."""
    (git_repo / "ignored").mkdir()
    (git_repo / "ignored" / "build.txt").write_text("output\n", encoding="utf-8")
    assert write_build_info.source_dirty(git_repo) is False


def test_source_provenance_fails_closed_when_git_cannot_answer(
    write_build_info: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tree whose provenance cannot be proven must not claim to be clean.

    This must NOT be simulated by pointing at an arbitrary temporary directory:
    ``tmp_path`` may well live *inside* the repository (CI runs pytest with a
    ``--basetemp`` under the checkout), and a subdirectory of a repository is
    still part of that repository, so git answers normally and nothing is
    "unprovable".  The contract is about git being *unable to answer*, so break
    git itself rather than relying on where the temporary directory happens to be.
    """
    monkeypatch.setattr(write_build_info, "_run_git", lambda *args, **kwargs: None)
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    assert write_build_info.source_commit(outside) is None
    assert write_build_info.source_dirty(outside) is True


def test_source_commit_rejects_unparseable_git_output(
    write_build_info: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """git answering with something that is not a 40-hex SHA is still unprovable."""
    monkeypatch.setattr(
        write_build_info, "_run_git", lambda *args, **kwargs: "not-a-sha\n"
    )
    assert write_build_info.source_commit(tmp_path) is None


def test_source_commit_resolves_inside_the_repository(
    write_build_info: ModuleType,
) -> None:
    """The counter-case: a real checkout resolves, and a subdirectory resolves too."""
    head = write_build_info.source_commit(ROOT)
    assert head is not None and re.fullmatch(r"[0-9a-f]{40}", head), head
    assert write_build_info.source_commit(ROOT / "tests") == head


# --------------------------------------------------------------------------
# 3. A dirty tree: recorded with --allow-dirty, refused by a formal run
# --------------------------------------------------------------------------


def _manifest_file(tmp_path: Path, names: dict[str, str], tree: str) -> Path:
    path = tmp_path / names["payload_manifest"]
    path.write_text(
        json.dumps({"schema": "ecq.payload-manifest.v1", "payload_tree_sha256": tree}),
        encoding="utf-8",
    )
    return path


def _dirty_tree_args(
    names: dict[str, str], tmp_path: Path, output: Path, manifest: Path, *extra: str
) -> list[str]:
    return [
        "--names",
        json.dumps(names, ensure_ascii=False),
        "--output",
        str(output),
        "--payload-manifest",
        str(manifest),
        "--source-commit",
        COMMIT,
        "--candidate-id",
        CANDIDATE,
        "--built-at",
        BUILT_AT,
        *extra,
    ]


def test_dirty_tree_is_recorded_with_allow_dirty(
    write_build_info: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    candidate_names: dict[str, str],
) -> None:
    # ECQ-RS05：显式提交必须等于真实 HEAD。这些用例用合成提交 COMMIT，
    # 因此把模块的 HEAD 也固定为 COMMIT，其余契约保持不变。
    monkeypatch.setattr(write_build_info, "source_commit", lambda root=None: COMMIT)
    monkeypatch.setattr(write_build_info, "source_dirty", lambda root=None: True)
    manifest = _manifest_file(tmp_path, candidate_names, TREE_SHA256)
    output = tmp_path / candidate_names["build_info"]
    rc = write_build_info.main(
        _dirty_tree_args(candidate_names, tmp_path, output, manifest, "--allow-dirty")
    )
    assert rc == 0
    info = json.loads(output.read_text(encoding="utf-8"))
    assert info["source_dirty"] is True, (
        "--allow-dirty 只允许构建继续，不得把脏工作区写成干净的"
    )
    assert info["source_commit"] == COMMIT


def test_formal_run_refuses_a_dirty_tree(
    write_build_info: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    candidate_names: dict[str, str],
) -> None:
    # ECQ-RS05：显式提交必须等于真实 HEAD。这些用例用合成提交 COMMIT，
    # 因此把模块的 HEAD 也固定为 COMMIT，其余契约保持不变。
    monkeypatch.setattr(write_build_info, "source_commit", lambda root=None: COMMIT)
    monkeypatch.setattr(write_build_info, "source_dirty", lambda root=None: True)
    manifest = _manifest_file(tmp_path, candidate_names, TREE_SHA256)
    output = tmp_path / candidate_names["build_info"]
    rc = write_build_info.main(
        _dirty_tree_args(candidate_names, tmp_path, output, manifest, "--require-clean")
    )
    assert rc == 1, "正式候选构建必须在脏工作区上失败"
    assert not output.exists(), "被拒绝的正式构建不得留下构建信息"


def test_clean_tree_passes_the_formal_run(
    write_build_info: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    candidate_names: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    # ECQ-RS05：显式提交必须等于真实 HEAD。这些用例用合成提交 COMMIT，
    # 因此把模块的 HEAD 也固定为 COMMIT，其余契约保持不变。
    monkeypatch.setattr(write_build_info, "source_commit", lambda root=None: COMMIT)
    monkeypatch.setattr(write_build_info, "source_dirty", lambda root=None: False)
    manifest = _manifest_file(tmp_path, candidate_names, TREE_SHA256)
    output = tmp_path / candidate_names["build_info"]
    rc = write_build_info.main(
        _dirty_tree_args(candidate_names, tmp_path, output, manifest, "--require-clean")
    )
    assert rc == 0, capsys.readouterr().err
    info = json.loads(output.read_text(encoding="utf-8"))
    assert info["source_dirty"] is False
    assert info["payload_tree_sha256"] == TREE_SHA256


def test_embedded_identity_is_written_to_the_payload_before_the_manifest(
    write_build_info: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    candidate_names: dict[str, str],
) -> None:
    # ECQ-RS05：显式提交必须等于真实 HEAD。这些用例用合成提交 COMMIT，
    # 因此把模块的 HEAD 也固定为 COMMIT，其余契约保持不变。
    monkeypatch.setattr(write_build_info, "source_commit", lambda root=None: COMMIT)
    monkeypatch.setattr(write_build_info, "source_dirty", lambda root=None: False)
    payload = tmp_path / "dist" / "UEBench"
    payload.mkdir(parents=True)
    rc = write_build_info.main(
        [
            "--names",
            json.dumps(candidate_names, ensure_ascii=False),
            "--payload-dir",
            str(payload),
            "--source-commit",
            COMMIT,
            "--candidate-id",
            CANDIDATE,
            "--built-at",
            BUILT_AT,
        ]
    )
    assert rc == 0
    identity_path = (
        payload / "_internal" / "uebench" / "resources" / "build-identity.json"
    )
    assert identity_path.is_file(), f"内嵌构建标识未写入契约路径：{identity_path}"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    assert identity["schema"] == "ecq.build-identity.v1"
    assert "payload_tree_sha256" not in identity


def test_embedded_identity_is_refused_without_a_commit(
    write_build_info: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    candidate_names: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An untraceable payload must fail instead of embedding a hollow identity."""
    # ECQ-RS05：显式提交必须等于真实 HEAD。这些用例用合成提交 COMMIT，
    # 因此把模块的 HEAD 也固定为 COMMIT，其余契约保持不变。
    monkeypatch.setattr(write_build_info, "source_commit", lambda root=None: COMMIT)
    monkeypatch.setattr(write_build_info, "source_dirty", lambda root=None: False)
    payload = tmp_path / "dist" / "UEBench"
    payload.mkdir(parents=True)
    rc = write_build_info.main(
        [
            "--names",
            json.dumps(candidate_names, ensure_ascii=False),
            "--payload-dir",
            str(payload),
        ]
    )
    assert rc == 1
    assert "拒绝写入" in capsys.readouterr().err
    assert not (payload / "_internal").exists()


def test_active_marker_is_written_for_a_clean_candidate(
    write_build_info: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    version: str,
    candidate_names: dict[str, str],
) -> None:
    # ECQ-RS05：显式提交必须等于真实 HEAD。这些用例用合成提交 COMMIT，
    # 因此把模块的 HEAD 也固定为 COMMIT，其余契约保持不变。
    monkeypatch.setattr(write_build_info, "source_commit", lambda root=None: COMMIT)
    monkeypatch.setattr(write_build_info, "source_dirty", lambda root=None: False)
    manifest = _manifest_file(tmp_path, candidate_names, TREE_SHA256)
    marker_path = tmp_path / "ACTIVE-CANDIDATE.json"
    rc = write_build_info.main(
        [
            "--names",
            json.dumps(candidate_names, ensure_ascii=False),
            "--active-marker",
            str(marker_path),
            "--payload-manifest",
            str(manifest),
            "--source-commit",
            COMMIT,
            "--candidate-id",
            CANDIDATE,
            "--built-at",
            BUILT_AT,
        ]
    )
    assert rc == 0
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    assert marker["schema"] == "ecq.active-candidate.v1"
    assert marker["status"] == "ACTIVE"
    assert marker["candidate_id"] == CANDIDATE
    assert marker["product_version"] == version
    assert marker["source_commit"] == COMMIT
    assert marker["source_dirty"] is False
    assert marker["payload_tree_sha256"] == TREE_SHA256
    assert marker["assembled_at_utc"] == BUILT_AT


def test_active_marker_is_refused_on_a_dirty_tree(
    write_build_info: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    candidate_names: dict[str, str],
) -> None:
    # ECQ-RS05：显式提交必须等于真实 HEAD。这些用例用合成提交 COMMIT，
    # 因此把模块的 HEAD 也固定为 COMMIT，其余契约保持不变。
    monkeypatch.setattr(write_build_info, "source_commit", lambda root=None: COMMIT)
    monkeypatch.setattr(write_build_info, "source_dirty", lambda root=None: True)
    manifest = _manifest_file(tmp_path, candidate_names, TREE_SHA256)
    marker = tmp_path / "ACTIVE-CANDIDATE.json"
    rc = write_build_info.main(
        [
            "--names",
            json.dumps(candidate_names, ensure_ascii=False),
            "--active-marker",
            str(marker),
            "--payload-manifest",
            str(manifest),
            "--source-commit",
            COMMIT,
            "--candidate-id",
            CANDIDATE,
            "--allow-dirty",
        ]
    )
    assert rc == 1, "脏工作区不得声明 ACTIVE 候选"
    assert not marker.exists()


def test_active_marker_is_refused_without_the_payload_digest(
    write_build_info: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    candidate_names: dict[str, str],
) -> None:
    """ACTIVE means "this payload tree"; without the digest it means nothing."""
    # ECQ-RS05：显式提交必须等于真实 HEAD。这些用例用合成提交 COMMIT，
    # 因此把模块的 HEAD 也固定为 COMMIT，其余契约保持不变。
    monkeypatch.setattr(write_build_info, "source_commit", lambda root=None: COMMIT)
    monkeypatch.setattr(write_build_info, "source_dirty", lambda root=None: False)
    marker = tmp_path / "ACTIVE-CANDIDATE.json"
    rc = write_build_info.main(
        [
            "--names",
            json.dumps(candidate_names, ensure_ascii=False),
            "--active-marker",
            str(marker),
            "--source-commit",
            COMMIT,
            "--candidate-id",
            CANDIDATE,
        ]
    )
    assert rc == 1
    assert not marker.exists()


# --------------------------------------------------------------------------
# 4. The scripts and the workflow must carry the guarantees
# --------------------------------------------------------------------------


def test_build_scripts_refuse_a_dirty_tree_and_pass_the_identity() -> None:
    for name in ("build_release.ps1", "sync_release.ps1", "build_candidate.ps1"):
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "git -C" in text and "status --porcelain" in text, (
            f"{name} 必须用 git status --porcelain 判断工作区是否干净"
        )
        assert "rev-parse HEAD" in text, f"{name} 必须由 git rev-parse HEAD 取得源提交"
        assert "--require-clean" in text, (
            f"{name} 必须以 --require-clean 调用 tools/write_build_info.py"
        )
        assert "-AllowDirty" in text, f"{name} 必须提供仅用于本地实验的 -AllowDirty"
        assert "throw" in text
        # No hard-coded artifact name may creep back in.
        assert "UEBench-0.2.0" not in text
        assert "UEBench-Setup-0.2.0" not in text


def test_build_scripts_pass_the_candidate_suffix_to_iscc() -> None:
    for name in ("build_release.ps1", "build_candidate.ps1"):
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "/DMyAppCandidateSuffix=-$CandidateId" in text, (
            f"{name} 必须把候选后缀以 ISCC /D 符号传入，而不是写进 version.iss"
        )
    # The two scripts that ASSEMBLE a Candidate directory must also declare which
    # Candidate that directory holds (§11 单一 ACTIVE Candidate).
    for name in ("build_candidate.ps1", "sync_release.ps1"):
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "ACTIVE-CANDIDATE.json" in text, f"{name} 必须声明 ACTIVE 候选"
        assert "清空候选目录" in text, f"{name} 必须清空装配目录后再装配"
    # build_release.ps1 builds the payload, it does not assemble a delivery
    # directory: it must still clear the stale dist\release, and must NOT claim
    # an ACTIVE candidate it never produced.
    release = (ROOT / "scripts" / "build_release.ps1").read_text(encoding="utf-8")
    assert "清空候选目录" in release
    assert "ACTIVE-CANDIDATE.json" not in release


def test_allow_dirty_local_experiments_cannot_claim_active() -> None:
    """``-AllowDirty`` must not be able to produce an ACTIVE Candidate.

    A dirty tree can never satisfy the Candidate gates (``audit_release``
    rejects ``source_dirty``), so the assemblers refuse to write the marker and
    say so; the CI workflow never passes ``-AllowDirty``.
    """
    for name in ("build_candidate.ps1", "sync_release.ps1"):
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "if ($AllowDirty)" in text, f"{name} 必须区分本地实验与正式候选"
        guard = text.index("if ($AllowDirty)")
        marker = text.index("ACTIVE-CANDIDATE.json", guard)
        branch = text[guard:marker]
        assert "本地实验模式" in branch, f"{name} 必须在实验分支明确警告"
        # The warning branch must be closed and an else-branch opened before the
        # marker is written, i.e. the marker really is formal-path only.
        assert "else" in branch, f"{name} 的 ACTIVE 标记必须位于 else（正式）分支"


def test_build_info_provenance_does_not_leak_into_generated_version_files() -> None:
    """The full provenance document must not be a generated version artifact."""
    for relative in ("src/uebench/_version.py", "packaging/version.iss"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        for marker in ("candidate_id", "source_commit", "payload_tree_sha256"):
            assert marker not in text, f"{relative} 不得包含 {marker}"


def test_candidate_cleanup_fails_loudly() -> None:
    """A locked file must abort the assembly, not be skipped silently."""
    for name in ("sync_release.ps1", "build_candidate.ps1", "build_release.ps1"):
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "清空候选目录" in text, f"{name} 必须清空候选目录"
        assert "-ErrorAction Stop" in text, f"{name} 清理目录时必须硬失败"
        cleanup = text.split("清空候选目录")[1].split("else")[0]
        assert "SilentlyContinue" not in cleanup, (
            f"{name} 清理装配目录时不得使用 -ErrorAction SilentlyContinue"
        )


def test_version_iss_stays_commit_independent() -> None:
    text = (ROOT / "packaging" / "version.iss").read_text(encoding="utf-8")
    assert "CandidateSuffix" not in text, (
        "packaging/version.iss 必须保持纯版本派生：候选后缀由构建脚本以 /D 传入"
    )
    assert COMMIT not in text
    assert CANDIDATE not in text


# --------------------------------------------------------------------------
# 5. Synthetic release directory driving audit_release
# --------------------------------------------------------------------------


def _payload_entries(files: dict[str, bytes]) -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        for path, data in sorted(files.items())
    ]


def _tree_sha256(entries: list[dict[str, Any]]) -> str:
    """The documented payload-tree digest (must match build_payload_manifest)."""
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item["path"]):
        digest.update(
            f"{entry['sha256']}  {entry['size']}  {entry['path']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def _standard_package_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "package_id": "pkg-synthetic",
                    "data_version": "2026.10-published.3",
                    "standard_count": 2,
                    "rule_count": 3,
                }
            ),
        )
        archive.writestr(
            "definitions/a.json",
            json.dumps({"products": [{"indicators": [{"indicator_id": "x"}]}]}),
        )
    return buffer.getvalue()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_release_dir(
    root: Path,
    release_version: ModuleType,
    version: str,
    *,
    candidate_id: str | None = CANDIDATE,
    build_info_overrides: dict[str, Any] | None = None,
    drop_keys: tuple[str, ...] = (),
) -> Path:
    """A minimal but complete release directory, hashed last so it is consistent."""
    names = release_version.artifact_names(version, candidate_id)
    root.mkdir(parents=True, exist_ok=True)

    # ECQ-RS05 溯源：候选必须在**载荷内部**携带完整身份，否则外部声明可被单独
    # 改写而不被发现。这里的字段必须与下面写出的 release-build-info.json 一致。
    package_bytes = _standard_package_bytes()
    embedded_identity = {
        "schema": "ecq.build-identity.v1",
        "product_version": version,
        "candidate_id": candidate_id,
        "source_commit": COMMIT,
        "source_dirty": False,
        "standard_package_id": "pkg-synthetic",
        "standard_data_version": "2026.10-published.3",
        "standard_package_sha256": _sha256(package_bytes),
        "build_time_utc": BUILT_AT,
    }
    payload_files = {
        "UEBench.exe": b"MZ" + b"\x00" * 64,
        "_internal/uebench/resources/build-identity.json": json.dumps(
            embedded_identity, ensure_ascii=False
        ).encode("utf-8"),
    }
    entries = _payload_entries(payload_files)
    tree_sha256 = _tree_sha256(entries)
    manifest = {
        "schema": "ecq.payload-manifest.v1",
        "version": version,
        "root": "UEBench",
        "file_count": len(entries),
        "total_bytes": sum(entry["size"] for entry in entries),
        "payload_tree_sha256": tree_sha256,
        "files": entries,
    }
    (root / names["payload_manifest"]).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with zipfile.ZipFile(root / names["portable"], "w") as archive:
        for path, data in payload_files.items():
            archive.writestr(f"UEBench/{path}", data)

    (root / names["installer"]).write_bytes(b"MZ" + b"\x00" * 2048)
    with zipfile.ZipFile(root / names["source"], "w") as archive:
        archive.writestr("pyproject.toml", "[project]\n")
    (root / names["template"]).write_bytes(b"PK\x03\x04synthetic-template")
    (root / names["helper_ps1"]).write_text("# helper\n", encoding="utf-8")
    (root / names["helper_cmd"]).write_text("@echo off\n", encoding="utf-8")
    (root / names["release_notes"]).write_text("# notes\n", encoding="utf-8")
    (root / names["delivery_list"]).write_text("# list\n", encoding="utf-8")

    (root / names["standard_package"]).write_bytes(package_bytes)

    info: dict[str, Any] = {
        "schema": "ecq.release-build-info.v1",
        "version": version,
        "built_at": BUILT_AT,
        "product_version": version,
        "candidate_id": candidate_id,
        "source_commit": COMMIT,
        "source_dirty": False,
        "standard_package_id": "pkg-synthetic",
        "standard_data_version": "2026.10-published.3",
        "standard_package_sha256": _sha256(package_bytes),
        "payload_tree_sha256": tree_sha256,
        "build_time_utc": BUILT_AT,
        "authenticode_signed": False,
        "unsigned_reason": "no_signing_certificate",
    }
    info.update(build_info_overrides or {})
    for key in drop_keys:
        info.pop(key, None)
    (root / names["build_info"]).write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # SHA256SUMS.txt is written LAST and never lists itself.
    hash_names = [
        names["portable"],
        names["installer"],
        names["source"],
        names["standard_package"],
        names["template"],
        names["payload_manifest"],
        names["build_info"],
        names["helper_ps1"],
        names["helper_cmd"],
        names["release_notes"],
        names["delivery_list"],
    ]
    lines = []
    for name in hash_names:
        data = (root / name).read_bytes()
        lines.append(f"{_sha256(data)}  {name}")
    (root / names["sha256sums"]).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


@pytest.fixture()
def synthetic_release(
    tmp_path: Path, release_version: ModuleType, version: str
) -> Path:
    return _build_release_dir(tmp_path / "release", release_version, version)


def test_synthetic_base_case_passes_the_audit(
    audit_release: ModuleType, synthetic_release: Path
) -> None:
    """Control: the mutations below are the only reason those cases fail."""
    report = audit_release.audit_release(synthetic_release)
    assert report["valid"] is True, report["errors"]
    assert report["candidate_id"] == CANDIDATE
    assert report["build_info"]["source_commit"] == COMMIT
    assert report["build_info"]["payload_tree_sha256"] == report["payload"][
        "recorded_tree_sha256"
    ]


def test_synthetic_base_case_uses_candidate_names(
    release_version: ModuleType,
    version: str,
    synthetic_release: Path,
) -> None:
    """The audit accepted a *Candidate* directory, not a formal-release one."""
    names = release_version.artifact_names(version, CANDIDATE)
    assert (synthetic_release / names["portable"]).is_file()
    assert not (synthetic_release / f"UEBench-{version}-win-x64.zip").exists()
    assert CANDIDATE in names["portable"]


def _audit_errors(audit_release: ModuleType, root: Path) -> tuple[bool, list[str]]:
    report = audit_release.audit_release(root)
    return report["valid"], list(report["errors"])


@pytest.mark.parametrize(
    "commit",
    [
        COMMIT[:7],  # too short to be unambiguous
        COMMIT.upper(),  # uppercase is not the canonical git form
        COMMIT[:39],  # truncated
        COMMIT + "0",
        "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
    ],
)
def test_audit_fails_on_a_malformed_source_commit(
    audit_release: ModuleType,
    release_version: ModuleType,
    version: str,
    tmp_path: Path,
    commit: str,
) -> None:
    root = _build_release_dir(
        tmp_path / "release",
        release_version,
        version,
        build_info_overrides={"source_commit": commit},
    )
    valid, errors = _audit_errors(audit_release, root)
    assert valid is False, f"非法 source_commit 未被拒绝：{commit!r}"
    assert any("source_commit" in error for error in errors), errors


def test_audit_fails_when_a_required_provenance_key_is_absent(
    audit_release: ModuleType,
    release_version: ModuleType,
    version: str,
    tmp_path: Path,
) -> None:
    for key in REQUIRED_BUILD_INFO_KEYS:
        root = _build_release_dir(
            tmp_path / f"release-{key}",
            release_version,
            version,
            drop_keys=(key,),
        )
        valid, errors = _audit_errors(audit_release, root)
        assert valid is False, f"缺少必备字段 {key} 未被拒绝"
        assert any(key in error for error in errors), (key, errors)


def test_audit_fails_on_a_dirty_tree(
    audit_release: ModuleType, release_version: ModuleType, version: str, tmp_path: Path
) -> None:
    root = _build_release_dir(
        tmp_path / "release",
        release_version,
        version,
        build_info_overrides={"source_dirty": True},
    )
    valid, errors = _audit_errors(audit_release, root)
    assert valid is False
    assert any("source_dirty" in error for error in errors), errors


def test_audit_fails_when_payload_tree_sha256_disagrees_with_the_manifest(
    audit_release: ModuleType, release_version: ModuleType, version: str, tmp_path: Path
) -> None:
    root = _build_release_dir(
        tmp_path / "release",
        release_version,
        version,
        build_info_overrides={"payload_tree_sha256": "d" * 64},
    )
    valid, errors = _audit_errors(audit_release, root)
    assert valid is False
    assert any("payload_tree_sha256" in error and "不一致" in error for error in errors), (
        errors
    )


def test_audit_fails_when_the_manifest_itself_is_missing(
    audit_release: ModuleType, release_version: ModuleType, version: str, tmp_path: Path
) -> None:
    root = _build_release_dir(tmp_path / "release", release_version, version)
    names = release_version.artifact_names(version, CANDIDATE)
    (root / names["payload_manifest"]).unlink()
    valid, errors = _audit_errors(audit_release, root)
    assert valid is False
    assert any("payload_tree_sha256" in error for error in errors), errors


def test_audit_fails_on_a_wrong_product_version(
    audit_release: ModuleType, release_version: ModuleType, version: str, tmp_path: Path
) -> None:
    root = _build_release_dir(
        tmp_path / "release",
        release_version,
        version,
        build_info_overrides={"product_version": "9.9.9"},
    )
    valid, errors = _audit_errors(audit_release, root)
    assert valid is False
    assert any("product_version" in error for error in errors), errors


def test_audit_fails_on_a_standard_package_hash_mismatch(
    audit_release: ModuleType, release_version: ModuleType, version: str, tmp_path: Path
) -> None:
    root = _build_release_dir(
        tmp_path / "release",
        release_version,
        version,
        build_info_overrides={"standard_package_sha256": "e" * 64},
    )
    valid, errors = _audit_errors(audit_release, root)
    assert valid is False
    assert any("standard_package_sha256" in error for error in errors), errors


def test_audit_fails_on_an_invalid_candidate_id(
    audit_release: ModuleType, release_version: ModuleType, version: str, tmp_path: Path
) -> None:
    root = _build_release_dir(
        tmp_path / "release",
        release_version,
        version,
        candidate_id=None,
        build_info_overrides={"candidate_id": "not-a-candidate-id"},
    )
    valid, errors = _audit_errors(audit_release, root)
    assert valid is False
    assert any("candidate_id" in error for error in errors), errors


def test_audit_accepts_a_formal_release_directory_without_an_identity(
    audit_release: ModuleType, release_version: ModuleType, version: str, tmp_path: Path
) -> None:
    """``candidate_id: null`` + un-suffixed names is the formal release cut."""
    root = _build_release_dir(
        tmp_path / "release", release_version, version, candidate_id=None
    )
    report = audit_release.audit_release(root)
    assert report["valid"] is True, report["errors"]
    assert report["candidate_id"] is None
    assert (root / f"UEBench-{version}-win-x64.zip").is_file()


def test_audit_required_files_follow_the_candidate_identity(
    audit_release: ModuleType, release_version: ModuleType, version: str
) -> None:
    formal = audit_release.required_files(version)
    candidate = audit_release.required_files(version, CANDIDATE)
    assert formal[0] == f"UEBench-{version}-win-x64.zip"
    assert candidate[0] == f"UEBench-{version}-{CANDIDATE}-win-x64.zip"
    # Nine of the twelve names are identity-free; exactly three differ.
    assert sum(1 for a, b in zip(formal, candidate) if a != b) == 3
    assert audit_release.required_files() == formal


def test_audit_reads_the_candidate_identity_from_the_directory(
    audit_release: ModuleType, release_version: ModuleType, version: str, tmp_path: Path
) -> None:
    root = _build_release_dir(tmp_path / "release", release_version, version)
    assert audit_release.release_candidate_id(root, "release-build-info.json") == CANDIDATE
    (root / "release-build-info.json").unlink()
    assert audit_release.release_candidate_id(root, "release-build-info.json") is None
