#!/usr/bin/env python3
"""Cover revoked test authentication values in genuine screenshots.

Do not use this on active credentials. Revoke the test sessions first, store the
raw image outside the repository, and inspect the output before committing it.
Rectangles use image pixels: left,top,right,bottom. Only opaque covers are used.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def rectangle(value):
    try:
        box = tuple(int(part) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("rectangle coordinates must be integers") from exc
    if len(box) != 4 or box[0] >= box[2] or box[1] >= box[3]:
        raise argparse.ArgumentTypeError("expected left,top,right,bottom")
    return box


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--rect", action="append", type=rectangle, required=True)
    args = parser.parse_args()
    if args.source.resolve() == args.destination.resolve():
        parser.error("keep source and redacted output separate")
    with Image.open(args.source) as original:
        result = original.convert("RGB")
    painter = ImageDraw.Draw(result)
    font = ImageFont.load_default(size=18)
    for left, top, right, bottom in args.rect:
        if left < 0 or top < 0 or right > result.width or bottom > result.height:
            parser.error("rectangle falls outside the screenshot")
        painter.rectangle((left, top, right, bottom), fill="#17212b")
        if right - left > 120 and bottom - top > 24:
            painter.text((left + 8, top + 4), "REDACTED", font=font, fill="white")
    result.save(args.destination, quality=95)
    print(f"Saved redacted screenshot: {args.destination.name} ({result.width}x{result.height})")


if __name__ == "__main__":
    main()
