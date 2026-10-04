"""Single source of truth for the UEBench product version (ECQ-RS05).

``pyproject.toml`` ``[project] version`` is the **only** authoritative product
version.  Every other version-bearing artifact in the formal release chain is
either *generated* from it by this module or *read* from it at build time, so no
release step depends on a human keeping two numbers in sync.

Two entry points matter:

* ``python tools/release_version.py --generate`` rewrites the derived files.
* ``python tools/release_version.py --check`` fails with exit code 1 if any
  derived file has drifted from ``pyproject.toml``.

``tests/test_release_version_consistency.py`` runs the ``--check`` logic, and
``scripts/build_candidate.ps1`` refuses to build when it fails.

**Candidate identity (ECQ-RS05).**  The product version alone cannot distinguish
two different Release Candidates: several builds may all be ``0.2.0`` with
identical PE version resources.  Candidate artifacts therefore carry a
``candidate_id`` of the form ``rc-<first 7 hex of the source commit>`` inserted
into the portable / installer / source file names.  The identity is *runtime
information*: it is derived from the checked-out commit, never from
``pyproject.toml``.

The formal release cut passes ``candidate_id=None`` and gets exactly the
un-suffixed names, and **no generated file depends on the commit** -- the git
SHA never reaches ``_version.py`` / ``version_info.txt`` / ``version.iss``, so
``--check`` stays deterministic on a clean checkout of any commit.  The suffix
is passed to Inno Setup by the build script (``/DMyAppCandidateSuffix=``), not
written into ``version.iss``.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"

#: Files this module generates from the authoritative version.
VERSION_MODULE = Path("src/uebench/_version.py")
VERSION_INFO = Path("packaging/version_info.txt")
VERSION_ISS = Path("packaging/version.iss")

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

#: A git commit as Candidate identity is derived from.  ``git rev-parse HEAD``
#: yields exactly 40 lowercase hex characters; shorter abbreviations are
#: accepted so a human can create a Candidate from an abbreviated SHA, but the
#: *canonical* identity is always ``rc-`` plus the first 7 characters.
_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")

#: Canonical Candidate identity: ``rc-`` + at least 7 hex characters.
CANDIDATE_ID_RE = re.compile(r"^rc-[0-9a-f]{7,40}$")

#: Length of the commit prefix embedded in a Candidate identity.
CANDIDATE_COMMIT_PREFIX = 7


def ensure_utf8_console() -> None:
    """Make Chinese output safe on non-UTF-8 consoles (ECQ-RS05).

    The GitHub Windows runner provides a **cp1252** console, so ``print()`` of
    any Chinese text raises ``UnicodeEncodeError`` and the release step exits
    non-zero.  Every release tool calls this first.

    It is deliberately defensive: under pytest, ``sys.stdout`` is a capture
    object without ``reconfigure``, and streams already set to UTF-8 are left
    alone.  Failures are ignored rather than masked, because a console that
    cannot be reconfigured should not abort a build that otherwise works.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        encoding = (getattr(stream, "encoding", "") or "").lower()
        if encoding.replace("-", "") == "utf8":
            continue
        try:
            reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:  # pragma: no cover - depends on the host console
            pass


def project_version(pyproject: Path | None = None) -> str:
    """Return the authoritative version from ``pyproject.toml``."""
    path = pyproject or PYPROJECT
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    try:
        version = data["project"]["version"]
    except KeyError as exc:  # pragma: no cover - guards a broken pyproject
        raise RuntimeError(f"{path} 缺少 [project] version") from exc
    if not isinstance(version, str) or not _SEMVER_RE.match(version):
        raise RuntimeError(f"{path} 的版本号不是 X.Y.Z 形式：{version!r}")
    return version


def version_tuple(version: str) -> tuple[int, int, int, int]:
    """``"0.2.0"`` -> ``(0, 2, 0, 0)`` for Windows VS_FIXEDFILEINFO."""
    parts = [int(part) for part in version.split(".")]
    if len(parts) > 4:
        raise RuntimeError(f"版本号段数过多：{version}")
    return tuple((parts + [0, 0, 0, 0])[:4])  # type: ignore[return-value]


def candidate_id(commit: str) -> str:
    """Candidate identity for ``commit``: ``rc-<first 7 hex characters>``.

    This is what makes two Candidates built from different commits
    distinguishable *by file name* while the product version stays untouched.
    Uppercase input is normalized to lowercase (git prints lowercase, but a
    human may paste a SHA from elsewhere); anything that is not 7-40 hex
    characters is rejected loudly rather than silently producing a bogus
    identity.
    """
    normalized = (commit or "").strip().lower()
    if not _COMMIT_RE.match(normalized):
        raise ValueError(
            f"不是有效的 git commit：{commit!r}；候选标识要求 7-40 位十六进制字符"
        )
    return "rc-" + normalized[:CANDIDATE_COMMIT_PREFIX]


def normalize_candidate_id(value: str) -> str:
    """Validate a Candidate identity supplied by a build script."""
    normalized = (value or "").strip().lower()
    if not CANDIDATE_ID_RE.match(normalized):
        raise ValueError(
            f"不是有效的候选标识：{value!r}；应形如 rc-<7位十六进制提交前缀>"
        )
    return normalized


def resolve_candidate_id(
    candidate: str | None = None, source_commit: str | None = None
) -> str | None:
    """Combine ``--candidate-id`` and ``--source-commit`` into one identity.

    Passing both is allowed only when they agree: a build script that derives
    the identity from one commit and names the artifacts with another would
    destroy exactly the traceability this feature exists to provide.
    """
    derived = candidate_id(source_commit) if source_commit else None
    if candidate:
        explicit = normalize_candidate_id(candidate)
        if derived is not None and explicit != derived:
            raise ValueError(
                f"--candidate-id {explicit} 与 --source-commit {source_commit} "
                f"推导出的 {derived} 不一致"
            )
        return explicit
    return derived


def artifact_names(version: str, candidate_id: str | None = None) -> dict[str, str]:
    """Canonical release artifact file names for ``version``.

    With ``candidate_id=None`` these are the **formal release** names, exactly
    as before ECQ-RS05 Candidate identity.  With a Candidate identity the three
    build-specific artifacts (portable ZIP / installer / source ZIP) carry it:

    * ``UEBench-<version>-<candidate_id>-win-x64.zip``
    * ``UEBench-Setup-<version>-<candidate_id>-x64.exe``
    * ``UEBench-source-<version>-<candidate_id>.zip``

    Everything else keeps its name: the pinned standard package and the GB
    29446 template are version-less release *inputs*, and the manifest / build
    info / checksum / helper / document names are per-directory fixed so the
    audit and the acceptance helper do not have to guess.
    """
    suffix = f"-{normalize_candidate_id(candidate_id)}" if candidate_id else ""
    return {
        "portable": f"UEBench-{version}{suffix}-win-x64.zip",
        "installer": f"UEBench-Setup-{version}{suffix}-x64.exe",
        "source": f"UEBench-source-{version}{suffix}.zip",
        "standard_package": "initial-standard-package-published.uebench",
        "template": "GB29446选煤电力消耗限额导入模板.xlsx",
        "sha256sums": "SHA256SUMS.txt",
        "payload_manifest": "payload-manifest.json",
        "build_info": "release-build-info.json",
        "helper_ps1": "验收助手.ps1",
        "helper_cmd": "验收助手.cmd",
        "release_notes": f"安装与发布说明-{version}.md",
        "delivery_list": f"交付清单-{version}.md",
    }


def render_version_module(version: str) -> str:
    return (
        '"""Generated by tools/release_version.py - do not edit by hand.\n'
        "\n"
        "The authoritative product version lives in ``pyproject.toml``;\n"
        "``tools/release_version.py --check`` fails the release when this file\n"
        "drifts from it.\n"
        '"""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        f'__version__ = "{version}"\n'
    )


def render_version_info(version: str) -> str:
    """PyInstaller ``version=`` resource file (numeric tuples + strings)."""
    major, minor, patch, build = version_tuple(version)
    return (
        "VSVersionInfo(\n"
        "  ffi=FixedFileInfo(\n"
        f"    filevers=({major}, {minor}, {patch}, {build}),\n"
        f"    prodvers=({major}, {minor}, {patch}, {build}),\n"
        "    mask=0x3f,\n"
        "    flags=0x0,\n"
        "    OS=0x40004,\n"
        "    fileType=0x1,\n"
        "    subtype=0x0,\n"
        "    date=(0, 0)\n"
        "  ),\n"
        "  kids=[\n"
        "    StringFileInfo([\n"
        "      StringTable(\n"
        "        u'080404B0',\n"
        "        [\n"
        "          StringStruct(u'CompanyName', u'UEBench'),\n"
        "          StringStruct(u'FileDescription', u'单位产品能耗对标软件'),\n"
        f"          StringStruct(u'FileVersion', u'{version}'),\n"
        "          StringStruct(u'InternalName', u'UEBench'),\n"
        "          StringStruct(u'OriginalFilename', u'UEBench.exe'),\n"
        "          StringStruct(u'ProductName', u'单位产品能耗对标软件'),\n"
        f"          StringStruct(u'ProductVersion', u'{version}')\n"
        "        ]\n"
        "      )\n"
        "    ]),\n"
        "    VarFileInfo([VarStruct(u'Translation', [2052, 1200])])\n"
        "  ]\n"
        ")\n"
    )


def render_version_iss(version: str) -> str:
    """Inno Setup include generated from the authoritative version."""
    return (
        "; Generated by tools/release_version.py - do not edit by hand.\n"
        f'#define MyAppVersion "{version}"\n'
    )


def derived_files(version: str | None = None) -> dict[Path, str]:
    """Map of derived file path -> expected content for the authoritative version."""
    resolved = version or project_version()
    return {
        VERSION_MODULE: render_version_module(resolved),
        VERSION_INFO: render_version_info(resolved),
        VERSION_ISS: render_version_iss(resolved),
    }


def check(root: Path | None = None, version: str | None = None) -> list[str]:
    """Return a list of drift descriptions (empty means everything is in sync)."""
    base = root or ROOT
    resolved = version or project_version(base / "pyproject.toml")
    problems: list[str] = []
    for relative, expected in derived_files(resolved).items():
        path = base / relative
        if not path.exists():
            problems.append(f"缺少生成文件：{relative}（应为 {resolved}）")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            problems.append(
                f"{relative} 与 pyproject.toml 的版本 {resolved} 不一致；"
                "请运行 python tools/release_version.py --generate"
            )
    return problems


def generate(root: Path | None = None, version: str | None = None) -> list[Path]:
    base = root or ROOT
    resolved = version or project_version(base / "pyproject.toml")
    written: list[Path] = []
    for relative, content in derived_files(resolved).items():
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_console()
    parser = argparse.ArgumentParser(description="UEBench 产品版本单一来源工具")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--print", action="store_true", help="打印权威版本号")
    group.add_argument("--generate", action="store_true", help="按权威版本重写派生文件")
    group.add_argument("--check", action="store_true", help="校验派生文件是否与权威版本一致")
    group.add_argument("--names", action="store_true", help="输出正式产物文件名（JSON）")
    group.add_argument(
        "--print-candidate-id",
        action="store_true",
        help="打印由 --source-commit（或 --candidate-id）确定的候选标识",
    )
    parser.add_argument(
        "--candidate-id",
        default=None,
        help="候选标识（rc-<7位提交前缀>）；省略时输出正式发布文件名",
    )
    parser.add_argument(
        "--source-commit",
        default=None,
        help="候选构建的源提交 SHA；据此推导候选标识，不写入任何生成文件",
    )
    parser.add_argument("--root", type=Path, default=None, help="仓库根目录（默认自动定位）")
    args = parser.parse_args(argv)

    base = args.root or ROOT
    version = project_version(base / "pyproject.toml")
    try:
        resolved_candidate = resolve_candidate_id(args.candidate_id, args.source_commit)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.generate:
        # Deliberately commit-independent: the git SHA never reaches a generated
        # file, so --check stays deterministic on a checkout of any commit.
        for path in generate(base, version):
            print(f"wrote {path}")
        return 0
    if args.check:
        problems = check(base, version)
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            print("版本一致性校验失败。", file=sys.stderr)
            return 1
        print(f"版本一致性校验通过：{version}")
        return 0
    if args.names:
        print(
            json.dumps(artifact_names(version, resolved_candidate), ensure_ascii=False)
        )
        return 0
    if args.print_candidate_id:
        if resolved_candidate is None:
            print(
                "缺少候选标识：请提供 --source-commit 或 --candidate-id。",
                file=sys.stderr,
            )
            return 2
        print(resolved_candidate)
        return 0
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
