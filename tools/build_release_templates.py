"""Generate the release Excel templates headlessly (ECQ-RS05 §7).

Producing a release must never require a human to open the GUI and save a
template by hand.  This tool drives the **real** ``ApplicationFacade`` /
``WorkbookTemplateService`` in an isolated data directory, so the shipped
template is exactly what the product itself produces.

The generated workbooks are then normalised (fixed ZIP member timestamps and
fixed ``docProps/core.xml`` dates) so regeneration is byte-deterministic; that
is what makes ``SHA256SUMS.txt`` meaningful for a template.  Use
``--check-determinism`` to prove it.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import tempfile
import zipfile
from pathlib import Path

# Importable both as `python tools/<name>.py` (tools/ is sys.path[0]) and as
# `tools.<name>` from a test module.
try:
    from release_version import artifact_names, project_version
except ModuleNotFoundError:  # pragma: no cover - package-import style
    from tools.release_version import artifact_names, project_version

ROOT = Path(__file__).resolve().parents[1]

#: Standards whose dedicated template is a required release asset.
REQUIRED_STANDARD_IDS = ("gb-29446-2019",)

#: Fixed timestamp for every ZIP member and DOCPROPS date (1980-01-01, the
#: earliest representable MS-DOS ZIP timestamp).
FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)
FIXED_DOC_DATE = "1980-01-01T00:00:00Z"

_CREATED_RE = re.compile(rb"<dcterms:created[^>]*>[^<]*</dcterms:created>")
_MODIFIED_RE = re.compile(rb"<dcterms:modified[^>]*>[^<]*</dcterms:modified>")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_docprops(payload: bytes) -> bytes:
    payload = _CREATED_RE.sub(
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{FIXED_DOC_DATE}</dcterms:created>'.encode(),
        payload,
    )
    payload = _MODIFIED_RE.sub(
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{FIXED_DOC_DATE}</dcterms:modified>'.encode(),
        payload,
    )
    return payload


def normalise_workbook(path: Path) -> None:
    """Rewrite an .xlsx in place with deterministic metadata.

    The normalised archive is assembled in memory and written over the original
    in a single step: creating a sibling temp file and renaming it fails with
    ``WinError 5`` on hosts where the directory ACL denies ``os.replace``.
    """
    with zipfile.ZipFile(path) as archive:
        members = [(info.filename, archive.read(info.filename)) for info in archive.infolist()]

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for name, payload in members:
            if name == "docProps/core.xml":
                payload = _normalise_docprops(payload)
            info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            out.writestr(info, payload)
    path.write_bytes(buffer.getvalue())


def generate(output_dir: Path, standard_ids: tuple[str, ...] = REQUIRED_STANDARD_IDS) -> dict[str, Path]:
    """Generate every release template into ``output_dir``.

    Returns a mapping of standard id (or ``"generic"``) to produced path.
    """
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from uebench.bootstrap import create_context
    from uebench.domain.models import StandardDefinition
    from uebench.infrastructure.logging import close_logging

    output_dir.mkdir(parents=True, exist_ok=True)
    names = artifact_names(project_version())
    produced: dict[str, Path] = {}

    with tempfile.TemporaryDirectory(prefix="uebench-template-") as temporary:
        context = create_context(Path(temporary) / "data")
        try:
            definitions = {}
            for standard_id in standard_ids:
                definition_path = ROOT / "data" / "definitions" / f"{standard_id}.json"
                if not definition_path.exists():
                    raise SystemExit(f"缺少标准定义：{definition_path}")
                definition = StandardDefinition.model_validate_json(
                    definition_path.read_text(encoding="utf-8")
                )
                context.standards.install(definition)
                definitions[standard_id] = definition

            for standard_id, _definition in definitions.items():
                target = (
                    output_dir / names["template"]
                    if standard_id == REQUIRED_STANDARD_IDS[0]
                    else output_dir / f"{standard_id}-导入模板.xlsx"
                )
                context.application.create_template(target, standard_id)
                normalise_workbook(target)
                produced[standard_id] = target

            generic = output_dir / "单位产品能耗对标导入模板.xlsx"
            context.application.create_template(generic)
            normalise_workbook(generic)
            produced["generic"] = generic
        finally:
            context.database.dispose()
            # Release the rotating log handler before the temporary directory is
            # removed; on Windows an open handle blocks the cleanup.
            close_logging()
    return produced


def main() -> None:
    parser = argparse.ArgumentParser(description="无头生成正式 Excel 导入模板")
    parser.add_argument("--output-dir", type=Path, default=Path("dist/release"))
    parser.add_argument(
        "--check-determinism",
        action="store_true",
        help="生成两次并断言字节完全一致",
    )
    args = parser.parse_args()

    produced = generate(args.output_dir)
    for key, path in produced.items():
        print(f"{key}: {path} sha256={sha256_of(path)} bytes={path.stat().st_size}")

    if args.check_determinism:
        first = {key: sha256_of(path) for key, path in produced.items()}
        with tempfile.TemporaryDirectory(prefix="uebench-template-check-") as temporary:
            second_dir = Path(temporary)
            second_paths = generate(second_dir)
            second = {key: sha256_of(path) for key, path in second_paths.items()}
        if first != second:
            for key in first:
                if first[key] != second.get(key):
                    print(f"不确定：{key} {first[key]} != {second.get(key)}")
            raise SystemExit("模板生成不是字节确定的")
        print("确定性校验通过：两次生成字节一致")


if __name__ == "__main__":
    main()
