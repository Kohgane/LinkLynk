#!/usr/bin/env python3
import argparse
import os
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "static" / "fly" / "sky"
OUT_DIR = SRC_DIR / "m"


def center_crop_to_ratio(img: Image.Image, target_ratio: float):
    w, h = img.size
    ratio = w / h
    if abs(ratio - target_ratio) < 1e-6:
        return img, False

    if ratio > target_ratio:
        new_w = int(round(h * target_ratio))
        left = (w - new_w) // 2
        box = (left, 0, left + new_w, h)
    else:
        new_h = int(round(w / target_ratio))
        top = (h - new_h) // 2
        box = (0, top, w, top + new_h)
    return img.crop(box), True


def format_kb(size_bytes: int) -> str:
    return f"{size_bytes / 1024:.1f}"


def process_image(path: Path, quality: int):
    src_bytes = path.stat().st_size
    with Image.open(path) as img:
        img = img.convert("RGB")
        src_w, src_h = img.size
        cropped, was_cropped = center_crop_to_ratio(img, 2.0)
        resized = cropped.resize((2048, 1024), Image.Resampling.LANCZOS)

    out_path = OUT_DIR / path.name
    resized.save(out_path, format="JPEG", quality=quality, progressive=True, optimize=True)
    out_bytes = out_path.stat().st_size

    return {
        "name": path.stem,
        "src_wh": f"{src_w}x{src_h}",
        "src_kb": format_kb(src_bytes),
        "out_kb": format_kb(out_bytes),
        "cropped": was_cropped,
    }


def main():
    parser = argparse.ArgumentParser(description="Build downsized sky panorama variants")
    parser.add_argument("--quality", type=int, default=78, help="JPEG quality (default: 78)")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    src_files = sorted([p for p in SRC_DIR.glob("*.jpg") if p.is_file()])
    if not src_files:
        raise SystemExit(f"No source JPEG files found in {SRC_DIR}")

    rows = []
    warnings = []
    for path in src_files:
        row = process_image(path, args.quality)
        if row["cropped"]:
            warnings.append(f"WARN: {path.name} is not 2:1 ({row['src_wh']}); center-cropped")
        rows.append(row)

    print(f"{'name':<12} {'src WxH':<12} {'src KB':>9} {'out KB':>9}")
    print("-" * 46)
    for row in rows:
        print(f"{row['name']:<12} {row['src_wh']:<12} {row['src_kb']:>9} {row['out_kb']:>9}")

    for warning in warnings:
        print(warning)


if __name__ == "__main__":
    main()
