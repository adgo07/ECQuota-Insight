"""Write ``release-build-info.json`` for a Candidate (ECQ-RS05 §16).

The 0.2.0 Candidate is shipped **unsigned**: there is no code-signing
certificate available.  That fact is a property of the artifact, so it is
recorded in machine-readable form rather than left implicit:

* ``authenticode_signed``  = ``false``
* ``unsigned_reason``      = ``no_signing_certificate``

This is deliberately distinct from the ``.uebench`` standard package's own
Ed25519 signature (see ``src/uebench/infrastructure/packages.py``): that
signature authenticates standard-package content and is verified at install
time, whereas Authenticode would authenticate the Windows PE binaries.  Do not
conflate the two.

Environment values below are **diagnostic only**.  A change in Python version,
dependency lock hash or calculator version must never by itself invalidate the
RS04 Product Golden; the Golden exists precisely to prove that a new build
environment preserves the same business semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Importable both as `python tools/<name>.py` (tools/ is sys.path[0]) and as
# `tools.<name>` from a test module.
try:
    from release_version import ensure_utf8_console, project_version
except ModuleNotFoundError:  # pragma: no cover - package-import style
    from tools.release_version import ensure_utf8_console, project_version

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ecq.release-build-info.v1"
UNSIGNED_REASON = "no_signing_certificate"
SMART_SCREEN_NOTE = (
    "本发布物未进行 Authenticode 代码签名（无可用签名证书）。Windows 可能显示"
    "“未知发布者”或 SmartScreen 提示；在企业环境中，应用控制/白名单策略可能"
    "阻止未签名程序运行。安装前请用 SHA256SUMS.txt 核对文件哈希。"
)


def sha256_of(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _os_details() -> dict[str, str]:
    details = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "release": platform.release(),
        "version": platform.version(),
    }
    if sys.platform == "win32":
        try:
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_OperatingSystem).Caption + '|' + "
                    "(Get-CimInstance Win32_OperatingSystem).BuildNumber",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            caption, _, build = completed.stdout.strip().partition("|")
            details["caption"] = caption.strip()
            details["build"] = build.strip()
        except Exception:
            pass
    return details


def _lock_hash() -> str | None:
    return sha256_of(ROOT / "requirements.lock")


def _standard_package_info(names: dict[str, str]) -> dict[str, object]:
    pinned = ROOT / "release" / "standard-packages" / names["standard_package"]
    info: dict[str, object] = {
        "path": str(pinned.relative_to(ROOT)) if pinned.exists() else None,
        "sha256": sha256_of(pinned),
        "size": pinned.stat().st_size if pinned.exists() else None,
    }
    if pinned.is_file():
        try:
            import zipfile

            with zipfile.ZipFile(pinned) as archive:
                manifest = json.loads(archive.read("manifest.json"))
            info["data_version"] = manifest.get("data_version")
            info["package_id"] = manifest.get("package_id")
            info["standard_count"] = manifest.get("standard_count")
            info["rule_count"] = manifest.get("rule_count")
            info["signature_algorithm"] = "ed25519"
        except Exception as exc:  # pragma: no cover - defensive
            info["error"] = str(exc)
    return info


def _golden_info() -> dict[str, object]:
    """Record the RS04 Golden identity this Candidate was verified against."""
    path = ROOT / "tests" / "golden" / "gb29446_product_golden_v1.json"
    if not path.is_file():
        return {}
    golden = json.loads(path.read_text(encoding="utf-8"))
    return {
        "golden_id": golden.get("golden_id"),
        "golden_version": golden.get("golden_version"),
        "standard_id": golden.get("standard_id"),
        "rule_revision": golden.get("rule_revision"),
        "standard_source_sha256": golden.get("standard_source_sha256"),
    }


def build_info(names: dict[str, str], *, built_at: str | None = None) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "version": project_version(),
        "built_at": built_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        # Unsigned-release declaration (ECQ-RS05 §16).
        "authenticode_signed": False,
        "unsigned_reason": UNSIGNED_REASON,
        "smart_screen_note": SMART_SCREEN_NOTE,
        # Diagnostics only - never a Golden skip condition.
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "requirements_lock_sha256": _lock_hash(),
        "os": _os_details(),
        "standard_package": _standard_package_info(names),
        "golden": _golden_info(),
        "standard_package_signature_note": (
            ".uebench 标准包使用 Ed25519 内容签名，安装时校验；这与 Windows "
            "Authenticode 代码签名是两件事，不要混淆。"
        ),
    }


def main() -> None:
    ensure_utf8_console()
    parser = argparse.ArgumentParser(description="生成 Candidate 构建信息（含未签名声明）")
    parser.add_argument("--names", required=True, help="tools/release_version.py --names 的 JSON")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--built-at", default=None)
    args = parser.parse_args()

    names = json.loads(args.names)
    info = build_info(names, built_at=args.built_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
