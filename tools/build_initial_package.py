from __future__ import annotations

import argparse
import json
import json
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from uebench.domain.models import StandardDefinition
from uebench.infrastructure.packages import StandardPackageBuilder


def load_or_create_key(private_path: Path, public_path: Path) -> Ed25519PrivateKey:
    if private_path.exists():
        key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise TypeError("签名私钥不是Ed25519私钥")
    else:
        private_path.parent.mkdir(parents=True, exist_ok=True)
        key = Ed25519PrivateKey.generate()
        private_path.write_bytes(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return key


def main() -> None:
    parser = argparse.ArgumentParser(description="构建含当前46项标准及已确认历史版本原文和规则的初始离线标准包")
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("dist/standard-packages/initial-standard-package-46-candidate.uebench"))
    parser.add_argument("--data-version", default="2026.08-reviewed.1")
    parser.add_argument("--package-id", default="initial-46-current-plus-history-published-202608")
    parser.add_argument("--issued-at", help="ISO时间；不填写时使用当前UTC时间")
    parser.add_argument("--scope", type=Path, default=Path("data/scope-44.json"))
    parser.add_argument("--history-dir", type=Path, default=Path("data/history/definitions"))
    parser.add_argument("--history-source-dir", type=Path, default=Path(r"G:\标准  规范\10_作废标准"))
    parser.add_argument("--private-key", type=Path, default=Path("work/signing/development-private-key.pem"))
    parser.add_argument(
        "--public-key",
        type=Path,
        default=Path("src/uebench/resources/update_public_key.pem"),
    )
    args = parser.parse_args()

    scope = json.loads(args.scope.resolve().read_text(encoding="utf-8"))
    target = set(scope["standards"])
    definitions = [
        StandardDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(Path("data/definitions").glob("*.json"))
        if json.loads(path.read_text(encoding="utf-8"))["number"] in target
    ]
    if len(definitions) != len(scope["standards"]):
        raise ValueError(f"当前标准定义数量与范围不一致：{len(definitions)} != {len(scope['standards'])}")
    # 历史规则单独存放；只有已发布的历史版本才进入正式包，避免把草案当成可计算规则。
    history_dir = args.history_dir.resolve()
    current_keys = {(item.id, item.version) for item in definitions}
    for path in sorted(history_dir.glob("*.json")) if history_dir.exists() else []:
        definition = StandardDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        if definition.publication_status.value != "published":
            continue
        if (definition.id, definition.version) not in current_keys:
            definitions.append(definition)
    source_dirs = [args.source_dir.resolve(), args.history_source_dir.resolve()]
    source_files = {}
    for definition in definitions:
        candidates = []
        for directory in source_dirs:
            exact = directory / definition.source_file
            if exact.exists():
                candidates.append(exact)
            candidates.extend(sorted(directory.glob(f"*{definition.source_file}")))
        unique = list(dict.fromkeys(candidates))
        source_files[definition.source_file] = unique[0] if len(unique) == 1 else (unique[0] if unique else source_dirs[0] / definition.source_file)
    missing = [name for name, path in source_files.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"缺少标准原文：{missing}")
    corrections_payload = json.loads(
        Path("data/corrections/catalog-corrections.json").read_text(encoding="utf-8")
    )["corrections"]
    key = load_or_create_key(args.private_key.resolve(), args.public_key.resolve())
    issued_at = datetime.fromisoformat(args.issued_at.replace("Z", "+00:00")) if args.issued_at else datetime.now(timezone.utc)
    output = StandardPackageBuilder(key).build(
        args.output.resolve(),
        definitions,
        source_files,
        data_version=args.data_version,
        minimum_app_version="0.1.0",
        corrections=corrections_payload,
        package_id=args.package_id,
        issued_at=issued_at,
    )
    print(output)


if __name__ == "__main__":
    main()
