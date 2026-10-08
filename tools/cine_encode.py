#!/usr/bin/env python3
"""Encode arrival cinematic clips to fly/v2 portrait assets."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


SCALE_CROP_VF = "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280"


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found on PATH. Please install ffmpeg and retry.")


def run_ffmpeg_encode(input_path: Path, output_path: Path, dur: float, crf: int) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-ss",
        "0",
        "-t",
        str(dur),
        "-i",
        str(input_path),
        "-an",
        "-vf",
        SCALE_CROP_VF,
        "-c:v",
        "libx264",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-crf",
        str(crf),
        str(output_path),
    ]
    subprocess.run(cmd, check=True)


def run_ffmpeg_poster(input_path: Path, poster_path: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-ss",
        "0.1",
        "-i",
        str(input_path),
        "-frames:v",
        "1",
        "-vf",
        SCALE_CROP_VF,
        "-q:v",
        "4",
        str(poster_path),
    ]
    subprocess.run(cmd, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Encode one arrival cinematic clip for /fly/v2/cine")
    parser.add_argument("--in", dest="input_file", required=True, help="Input source video path")
    parser.add_argument("--slug", required=True, help="Output slug (used as filename)")
    parser.add_argument("--dur", type=float, default=5.0, help="Clip duration in seconds (default: 5)")
    parser.add_argument("--max-mb", type=float, default=2.5, help="Maximum output size in MB (default: 2.5)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require_ffmpeg()

    input_path = Path(args.input_file)
    if not input_path.is_file():
        raise SystemExit(f"Input file not found: {input_path}")
    if args.dur <= 0:
        raise SystemExit("--dur must be greater than 0")
    if args.max_mb <= 0:
        raise SystemExit("--max-mb must be greater than 0")

    repo_root = Path(__file__).resolve().parents[1]
    cine_dir = repo_root / "static" / "fly" / "v2" / "cine"
    cine_dir.mkdir(parents=True, exist_ok=True)

    out_mp4 = cine_dir / f"{args.slug}.mp4"
    out_jpg = cine_dir / f"{args.slug}.jpg"
    max_bytes = int(args.max_mb * 1024 * 1024)

    best_crf = None
    best_bytes = None
    best_file = None

    with tempfile.TemporaryDirectory(prefix="cine_encode_", dir="/tmp") as temp_dir:
        temp_dir_path = Path(temp_dir)
        lo, hi = 18, 34

        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = temp_dir_path / f"candidate_crf_{mid}.mp4"
            run_ffmpeg_encode(input_path, candidate, args.dur, mid)
            size = candidate.stat().st_size

            if size <= max_bytes:
                best_crf = mid
                best_bytes = size
                best_file = candidate
                hi = mid - 1
            else:
                lo = mid + 1

        if best_file is None:
            raise SystemExit(
                f"Unable to reach size limit with CRF 18..34. Limit={max_bytes} bytes for --max-mb={args.max_mb}."
            )

        shutil.copyfile(best_file, out_mp4)

    run_ffmpeg_poster(input_path, out_jpg)
    print(f"final_crf={best_crf} bytes={best_bytes}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"ffmpeg command failed with exit code {exc.returncode}") from exc
