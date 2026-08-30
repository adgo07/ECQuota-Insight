from __future__ import annotations

import argparse
from pathlib import Path

import pypdfium2 as pdfium


def main() -> None:
    parser = argparse.ArgumentParser(description="Render selected PDF pages to PNG for visual verification")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--pages", nargs="+", type=int, required=True, help="1-based page numbers")
    parser.add_argument("--scale", type=float, default=2.0)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    document = pdfium.PdfDocument(str(args.pdf))
    for page_number in args.pages:
        page = document[page_number - 1]
        bitmap = page.render(scale=args.scale)
        image = bitmap.to_pil()
        target = args.output_dir / f"page-{page_number:03d}.png"
        image.save(target)
        print(target)


if __name__ == "__main__":
    main()
