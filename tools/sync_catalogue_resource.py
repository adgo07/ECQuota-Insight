"""Keep the bundled GB 29435 preview resource derived from data/definitions.

The resource is read by the bootstrap preview path. It is a byte-for-byte
copy, not another editable rule source.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/definitions/gb-29435-2025.json"
TARGET = ROOT / "src/uebench/resources/catalogue/gb-29435-2025.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="校验或派生 GB 29435 目录预览资源")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        source = SOURCE.read_bytes()
        if args.check:
            if TARGET.read_bytes() != source:
                print("目录预览资源与唯一机器定义源不一致", file=sys.stderr)
                return 1
            print("目录预览资源与唯一机器定义源一致")
            return 0
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_bytes(source)
        print("已派生目录预览资源")
        return 0
    except OSError as exc:
        print(f"目录预览资源校验失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
