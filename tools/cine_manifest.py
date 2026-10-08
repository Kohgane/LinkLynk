#!/usr/bin/env python3
"""Build /fly/v2/cine/manifest.json from encoded MP4 clips."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def require_ffprobe() -> None:
    if shutil.which("ffprobe") is None:
        raise SystemExit("ffprobe not found on PATH. Please install ffmpeg/ffprobe and retry.")


def probe_video(path: Path) -> tuple[float, int, int]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=width,height:format=duration",
        "-select_streams",
        "v:0",
        "-of",
        "json",
        str(path),
    ]
    out = subprocess.check_output(cmd, text=True)
    data = json.loads(out)
    streams = data.get("streams") or []
    if not streams:
        raise SystemExit(f"No video stream found in {path}")
    stream0 = streams[0]
    width = int(stream0["width"])
    height = int(stream0["height"])
    duration = float(data["format"]["duration"])
    return duration, width, height


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build /fly/v2/cine/manifest.json")
    return parser.parse_args()


def main() -> None:
    parse_args()
    require_ffprobe()

    repo_root = Path(__file__).resolve().parents[1]
    cine_dir = repo_root / "static" / "fly" / "v2" / "cine"
    cine_dir.mkdir(parents=True, exist_ok=True)

    clips = {}
    for mp4_path in sorted(cine_dir.glob("*.mp4")):
        slug = mp4_path.stem
        duration, width, height = probe_video(mp4_path)
        clips[slug] = {
            "src": f"/fly/v2/cine/{slug}.mp4",
            "poster": f"/fly/v2/cine/{slug}.jpg",
            "dur": duration,
            "bytes": mp4_path.stat().st_size,
            "w": width,
            "h": height,
        }

    payload = {"v": 1, "clips": clips}
    manifest_path = cine_dir / "manifest.json"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {manifest_path} with {len(clips)} clips")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"ffprobe command failed with exit code {exc.returncode}") from exc
