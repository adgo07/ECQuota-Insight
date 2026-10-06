"""ECQ-RS05 release-provenance — the identity must be BOUND to the real source.

Reporter's blocker: every identity field was present, internally consistent and
checksummed, and CI was green, yet a Candidate could still be built whose declared
``source_commit`` was some *other* commit, and whose external identity could be
rewritten (with checksums refreshed) while all gates still passed.

Two independent holes, both closed here:

* ``write_build_info.py`` / the build scripts let an explicit ``SourceCommit``
  *override* ``git rev-parse HEAD`` — so ``rc-<old base>`` could be stamped onto a
  tree built from the current HEAD, still claiming ``source_dirty = false``
  (dirtiness is measured against the real tree).
* ``audit_release.py`` never compared the external document against the
  ``rc-<short7>`` prefix in the artifact FILE NAMES, nor against the identity
  EMBEDDED INSIDE the portable payload.

These tests are deliberately negative: each one removes exactly one binding and
asserts the gate fails, so a future refactor cannot silently drop a check.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import write_build_info  # noqa: E402
from audit_release import (  # noqa: E402
    ACTIVE_MARKER_NAME,
    EMBEDDED_IDENTITY_KEYS,
    EMBEDDED_IDENTITY_MEMBER,
    _audit_identity_binding,
)

HEAD = write_build_info.source_commit(ROOT)
OTHER = "fb91ccc6f85791bcaf9751c5681cc00c5a0ed213"


# ---------------------------------------------------------------------------
# 1. An explicit commit may only CONFIRM the real HEAD
# ---------------------------------------------------------------------------


@pytest.mark.skipif(HEAD is None, reason="不在 git 检出中，无法验证提交绑定")
def test_explicit_commit_must_equal_head() -> None:
    assert write_build_info.verified_source_commit(HEAD) == HEAD
    assert write_build_info.verified_source_commit() == HEAD


@pytest.mark.skipif(HEAD is None, reason="不在 git 检出中，无法验证提交绑定")
def test_explicit_commit_that_is_not_head_is_refused() -> None:
    """The reported attack: stamp an old base SHA onto the current tree."""
    other = OTHER if OTHER != HEAD else "0" * 40
    with pytest.raises(ValueError) as excinfo:
        write_build_info.verified_source_commit(other)
    message = str(excinfo.value)
    assert "不一致" in message and other in message and HEAD in message


def test_malformed_explicit_commit_is_refused() -> None:
    with pytest.raises(ValueError):
        write_build_info.verified_source_commit("abc1234")


@pytest.mark.skipif(HEAD is None, reason="不在 git 检出中，无法验证提交绑定")
def test_cli_refuses_a_commit_that_is_not_head(tmp_path: Path) -> None:
    """Same rule through the real command line, writing nothing."""
    other = OTHER if OTHER != HEAD else "0" * 40
    output = tmp_path / "release-build-info.json"
    names = json.dumps({
        "standard_package": "initial-standard-package-published.uebench",
        "payload_manifest": "payload-manifest.json",
        "build_info": "release-build-info.json",
    })
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "write_build_info.py"),
         "--names", names,
         "--source-commit", other,
         "--candidate-id", f"rc-{other[:7]}",
         "--require-clean",
         "--output", str(output)],
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT),
    )
    assert proc.returncode != 0, "显式提交不等于 HEAD 时必须拒绝"
    assert "不一致" in (proc.stderr or "")
    assert not output.exists(), "被拒绝时不得写出任何身份文件"


# ---------------------------------------------------------------------------
# 2. External document <-> file-name prefix <-> payload-embedded identity
# ---------------------------------------------------------------------------


def _identity(commit: str = "a" * 40, candidate: str = "rc-aaaaaaa") -> dict:
    return {
        "schema": "ecq.build-identity.v1",
        "product_version": "0.2.0",
        "candidate_id": candidate,
        "source_commit": commit,
        "source_dirty": False,
        "standard_package_id": "pkg",
        "standard_data_version": "2026.10-published.3",
        "standard_package_sha256": "b" * 64,
        "build_time_utc": "2026-10-04T00:00:00Z",
    }


def _external(commit: str = "a" * 40, candidate: str = "rc-aaaaaaa") -> dict:
    info = {
        "product_version": "0.2.0",
        "candidate_id": candidate,
        "source_commit": commit,
        "source_dirty": False,
        "standard_package_id": "pkg",
        "standard_data_version": "2026.10-published.3",
        "standard_package_sha256": "b" * 64,
        "payload_tree_sha256": "c" * 64,
        "build_time_utc": "2026-10-04T00:00:00Z",
    }
    return info


def _release_dir(
    tmp_path: Path,
    *,
    external: dict,
    embedded: dict | None,
    suffix: str = "rc-aaaaaaa",
    with_marker: bool = False,
) -> dict:
    """Minimal release dir exercising only the identity-binding cross-check."""
    names = {
        "portable": f"UEBench-0.2.0-{suffix}-win-x64.zip",
        "installer": f"UEBench-Setup-0.2.0-{suffix}-x64.exe",
        "source": f"UEBench-source-0.2.0-{suffix}.zip",
        "build_info": "release-build-info.json",
    }
    (tmp_path / names["build_info"]).write_text(
        json.dumps(external, ensure_ascii=False), encoding="utf-8"
    )
    for key in ("installer", "source"):
        (tmp_path / names[key]).write_bytes(b"placeholder")
    if embedded is not None:
        with zipfile.ZipFile(tmp_path / names["portable"], "w") as archive:
            archive.writestr(
                EMBEDDED_IDENTITY_MEMBER,
                json.dumps(embedded, ensure_ascii=False),
            )
    else:
        with zipfile.ZipFile(tmp_path / names["portable"], "w") as archive:
            archive.writestr("UEBench/UEBench.exe", b"placeholder")
    if with_marker:
        (tmp_path / ACTIVE_MARKER_NAME).write_text(
            json.dumps({
                "schema": "ecq.active-candidate.v1",
                "status": "ACTIVE",
                "candidate_id": external["candidate_id"],
                "source_commit": external["source_commit"],
                "payload_tree_sha256": external["payload_tree_sha256"],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
    return names


def _errors(tmp_path: Path, names: dict, external: dict) -> list[str]:
    report = _audit_identity_binding(tmp_path, names, external)
    return report["errors"]


def test_consistent_identity_has_no_errors(tmp_path: Path) -> None:
    external = _external()
    names = _release_dir(tmp_path, external=external, embedded=_identity(), with_marker=True)
    assert _errors(tmp_path, names, external) == []


def test_external_commit_tampering_is_detected(tmp_path: Path) -> None:
    """The reporter's exact negative: only the external document is rewritten."""
    embedded = _identity()
    external = _external()
    names = _release_dir(tmp_path, external=external, embedded=embedded)
    external["source_commit"] = OTHER  # tamper after writing
    errors = _errors(tmp_path, names, external)
    assert errors, "外部 source_commit 与包内身份不一致时必须报错"
    assert any(EMBEDDED_IDENTITY_MEMBER.split("/")[-1] in e or "包内构建身份" in e for e in errors)
    assert any("候选标识" in e for e in errors)


def test_filename_prefix_mismatch_is_detected(tmp_path: Path) -> None:
    external = _external()
    names = _release_dir(
        tmp_path, external=external, embedded=_identity(), suffix="rc-bbbbbbb"
    )
    errors = _errors(tmp_path, names, external)
    assert any("候选标识" in e for e in errors), errors


def test_missing_embedded_identity_is_detected(tmp_path: Path) -> None:
    external = _external()
    names = _release_dir(tmp_path, external=external, embedded=None)
    errors = _errors(tmp_path, names, external)
    assert any("缺少构建身份文件" in e for e in errors), errors


def test_embedded_identity_may_not_contain_the_payload_tree_hash(tmp_path: Path) -> None:
    """A file inside the payload cannot describe that payload's own tree hash."""
    embedded = _identity()
    embedded["payload_tree_sha256"] = "c" * 64
    external = _external()
    names = _release_dir(tmp_path, external=external, embedded=embedded)
    errors = _errors(tmp_path, names, external)
    assert any("payload_tree_sha256" in e for e in errors), errors


@pytest.mark.parametrize("key", sorted(EMBEDDED_IDENTITY_KEYS))
def test_every_embedded_field_is_cross_checked(tmp_path: Path, key: str) -> None:
    embedded = _identity()
    external = _external()
    names = _release_dir(tmp_path, external=external, embedded=embedded)
    tampered = dict(embedded)
    tampered[key] = "tampered" if not isinstance(embedded[key], bool) else True
    with zipfile.ZipFile(tmp_path / names["portable"], "w") as archive:
        archive.writestr(EMBEDDED_IDENTITY_MEMBER, json.dumps(tampered, ensure_ascii=False))
    errors = _errors(tmp_path, names, external)
    assert any(key in e for e in errors), f"包内 {key} 被改动却未被发现：{errors}"


def test_active_marker_must_agree_with_the_identity(tmp_path: Path) -> None:
    external = _external()
    names = _release_dir(tmp_path, external=external, embedded=_identity(), with_marker=True)
    marker = tmp_path / ACTIVE_MARKER_NAME
    data = json.loads(marker.read_text(encoding="utf-8"))
    data["source_commit"] = OTHER
    marker.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    errors = _errors(tmp_path, names, external)
    assert any(ACTIVE_MARKER_NAME in e and "source_commit" in e for e in errors), errors


def test_build_scripts_bind_explicit_commit_to_head() -> None:
    """The PowerShell resolvers must refuse a commit that is not HEAD."""
    for name in ("build_candidate.ps1", "build_release.ps1", "sync_release.ps1"):
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "rev-parse HEAD" in text, f"{name} 必须读取真实 HEAD"
        assert re.search(r"\$commit\s+-ne\s+\$head", text), (
            f"{name} 必须把显式提交与 HEAD 比较，而不是直接采用"
        )
        assert "拒绝构建" in text, f"{name} 不一致时必须拒绝"


def test_no_build_script_adopts_an_explicit_commit_verbatim() -> None:
    """Guard against re-introducing `commit = $Explicit` as the returned value."""
    for name in ("build_candidate.ps1", "build_release.ps1", "sync_release.ps1"):
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "$commit   = $Explicit" not in text
        assert "return $commit.ToLowerInvariant()" not in text
