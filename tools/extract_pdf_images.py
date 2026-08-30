from __future__ import annotations

import argparse
from pathlib import Path

from pypdf import PdfReader


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract embedded page images for visual/OCR review")
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--contains", nargs="+", required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for pdf in sorted(args.source_dir.glob("*.pdf")):
        if not any(token in pdf.name for token in args.contains):
            continue
        reader = PdfReader(str(pdf))
        stem = pdf.stem
        out = args.output_dir / stem
        out.mkdir(parents=True, exist_ok=True)
        count = 0
        for page_number, page in enumerate(reader.pages, start=1):
            for image_number, image in enumerate(page.images, start=1):
                target = out / f"page-{page_number:03d}-image-{image_number:02d}{Path(image.name).suffix or '.bin'}"
                target.write_bytes(image.data)
                count += 1
        print(f"{pdf.name}: {len(reader.pages)} pages, {count} images -> {out}")


if __name__ == "__main__":
    main()
