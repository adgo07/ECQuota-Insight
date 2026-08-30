from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--thumb-width", type=int, default=420)
    args = parser.parse_args()
    files = sorted(args.input_dir.glob("*.png"))
    if not files:
        raise SystemExit("no PNG files")
    images = []
    for path in files:
        image = Image.open(path).convert("RGB")
        ratio = args.thumb_width / image.width
        image = image.resize((args.thumb_width, max(1, int(image.height * ratio))))
        canvas = Image.new("RGB", (args.thumb_width, image.height + 28), "white")
        canvas.paste(image, (0, 28))
        ImageDraw.Draw(canvas).text((6, 6), path.name, fill="black")
        images.append(canvas)
    rows = (len(images) + args.columns - 1) // args.columns
    row_height = max(image.height for image in images)
    sheet = Image.new("RGB", (args.columns * args.thumb_width, rows * row_height), "white")
    for index, image in enumerate(images):
        sheet.paste(image, ((index % args.columns) * args.thumb_width, (index // args.columns) * row_height))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)


if __name__ == "__main__":
    main()
