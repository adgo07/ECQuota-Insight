"""Regression guard: release tools must survive a non-UTF-8 console (ECQ-RS05).

The GitHub Actions Windows runner provides a **cp1252** console.  Three separate
times during this project a Python step that printed Chinese text died with
``UnicodeEncodeError: 'charmap' codec can't encode characters`` and failed the
build while passing locally (UTF-8 console):

* the RS03 Excel ingress probe,
* the RS04 lifecycle probe,
* the RS05 release tools (first observed on CI run 37144561418, step
  "Read the authoritative version and artifact names").

The fix is ``tools.release_version.ensure_utf8_console()``, called at the start
of every release tool's ``main``.  This module pins that behaviour by running
each tool as a **real subprocess** with ``PYTHONIOENCODING=cp1252`` — the same
way CI does — so a future tool that forgets the call fails here instead of in
the release workflow.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

#: Console encodings the tools must tolerate.  cp1252 is what CI actually gives.
CONSOLES = ("cp1252", "utf-8")


def run_tool(script: str, *args: str, encoding: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = encoding
    return subprocess.run(
        [sys.executable, "-B", str(TOOLS / script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        env=env,
        timeout=300,
    )


@pytest.mark.parametrize("encoding", CONSOLES)
def test_release_version_check_survives_the_console(encoding: str) -> None:
    done = run_tool("release_version.py", "--check", encoding=encoding)
    assert done.returncode == 0, f"{encoding}: {done.stdout}\n{done.stderr}"
    assert "UnicodeEncodeError" not in done.stderr


@pytest.mark.parametrize("encoding", CONSOLES)
def test_release_version_print_and_names_survive_the_console(encoding: str) -> None:
    printed = run_tool("release_version.py", "--print", encoding=encoding)
    assert printed.returncode == 0, printed.stderr
    assert printed.stdout.strip(), "版本号不应为空"

    names = run_tool("release_version.py", "--names", encoding=encoding)
    assert names.returncode == 0, names.stderr
    payload = json.loads(names.stdout)
    assert payload["portable"].endswith("-win-x64.zip")
    assert payload["installer"].endswith("-x64.exe")


@pytest.mark.parametrize("encoding", CONSOLES)
def test_payload_manifest_survives_the_console(encoding: str, tmp_path: Path) -> None:
    payload_dir = tmp_path / "payload"
    payload_dir.mkdir()
    (payload_dir / "a.txt").write_text("x", encoding="utf-8")
    (payload_dir / "中文.txt").write_text("中文内容", encoding="utf-8")
    output = tmp_path / "payload-manifest.json"

    done = run_tool(
        "build_payload_manifest.py",
        "--payload-dir",
        str(payload_dir),
        "--output",
        str(output),
        encoding=encoding,
    )
    assert done.returncode == 0, f"{encoding}: {done.stdout}\n{done.stderr}"
    assert "UnicodeEncodeError" not in done.stderr
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["file_count"] == 2
    assert {entry["path"] for entry in manifest["files"]} == {"a.txt", "中文.txt"}


@pytest.mark.parametrize("encoding", CONSOLES)
def test_write_build_info_survives_the_console(encoding: str, tmp_path: Path) -> None:
    names = run_tool("release_version.py", "--names", encoding="utf-8").stdout
    output = tmp_path / "release-build-info.json"

    done = run_tool(
        "write_build_info.py", "--names", names, "--output", str(output), encoding=encoding
    )
    assert done.returncode == 0, f"{encoding}: {done.stdout}\n{done.stderr}"
    assert "UnicodeEncodeError" not in done.stderr
    info = json.loads(output.read_text(encoding="utf-8"))
    # The unsigned-release declaration must survive the encoder, and the Chinese
    # SmartScreen note must not abort the tool.
    assert info["authenticode_signed"] is False
    assert info["unsigned_reason"] == "no_signing_certificate"
    assert info["smart_screen_note"]


@pytest.mark.parametrize("encoding", CONSOLES)
def test_audit_release_survives_the_console_on_an_empty_dir(encoding: str, tmp_path: Path) -> None:
    """The audit prints Chinese JSON; an empty dir must fail *cleanly*, not crash."""
    done = run_tool("audit_release.py", str(tmp_path), encoding=encoding)
    assert "UnicodeEncodeError" not in done.stderr
    # It reports the missing artifacts (exit 1 is the documented failure signal),
    # and it must still emit parseable JSON on stdout.
    assert done.returncode == 1, f"{encoding}: {done.stdout}\n{done.stderr}"
    report = json.loads(done.stdout)
    assert report["valid"] is False
    assert report["legacy_reference_only"]["correctness_basis"] is False


def test_ensure_utf8_console_is_safe_under_pytest_capture() -> None:
    """It must not raise when stdout is pytest's capture object."""
    sys.path.insert(0, str(TOOLS))
    try:
        from release_version import ensure_utf8_console
    finally:
        sys.path.pop(0)

    ensure_utf8_console()  # must be a no-op, never an exception
    ensure_utf8_console()
    assert True
