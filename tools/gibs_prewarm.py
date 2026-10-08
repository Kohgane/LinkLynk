#!/usr/bin/env python3
"""Warm the GIBS tile cache via the same-origin proxy."""

import argparse
import concurrent.futures
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import urljoin

LAYERS = {
    "BlueMarble_ShadedRelief_Bathymetry": {
        "date": "2004-08",
        "ext": "jpeg",
    },
    "VIIRS_Black_Marble": {
        "date": "2016-01-01",
        "ext": "png",
    },
}
ALIASES = {
    "both": ["BlueMarble_ShadedRelief_Bathymetry", "VIIRS_Black_Marble"],
    "bluemarble": ["BlueMarble_ShadedRelief_Bathymetry"],
    "bluemarble_shadedrelief_bathymetry": ["BlueMarble_ShadedRelief_Bathymetry"],
    "viirs": ["VIIRS_Black_Marble"],
    "viirs_black_marble": ["VIIRS_Black_Marble"],
    "viirs-black-marble": ["VIIRS_Black_Marble"],
}


def _resolve_layers(layer_arg):
    key = (layer_arg or "").strip()
    if not key:
        return []
    lower = key.lower()
    if lower in ALIASES:
        return ALIASES[lower]
    if key in LAYERS:
        return [key]
    by_name = {}
    for name in LAYERS:
        by_name[name.lower()] = name
        by_name[name.lower().replace("_", "")] = name
        by_name[name.lower().replace("_", "-")] = name
    return [by_name[lower]] if lower in by_name else []


def _iter_levels(spec):
    if spec is None:
        return []
    start, end = spec.split("-", 1) if "-" in spec else (spec, spec)
    if start == "":
        start = "0"
    if end == "":
        end = start
    lo = int(start)
    hi = int(end)
    if lo > hi:
        lo, hi = hi, lo
    return list(range(lo, hi + 1))


def fetch_tile(proxy_base, layer, z, x, y, ext):
    url = f"{proxy_base.rstrip('/')}/fly/tiles/{layer}/{z}/{y}/{x}.{ext}"
    req = urllib.request.Request(url, headers={"User-Agent": "LinkLynk-GIBS-Prewarm/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return "ERR"
            cache_header = resp.headers.get("X-Cache", "MISS")
            return cache_header.upper() if cache_header and cache_header.upper() in {"HIT", "MISS"} else "MISS"
    except Exception:
        return "ERR"


def main():
    parser = argparse.ArgumentParser(description="Prewarm NASA GIBS tiles via the app proxy.")
    parser.add_argument("--base", required=True, help="Base URL for the app, for example https://linklynk.onrender.com")
    parser.add_argument("--levels", default="0-5", help="Level range like 0-5 or single level like 3")
    parser.add_argument("--layers", default="both", help="Layer selector: both, BlueMarble_ShadedRelief_Bathymetry, or VIIRS_Black_Marble")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers (default: 8)")
    args = parser.parse_args()

    layers = _resolve_layers(args.layers)
    if not layers:
        print("ERR: unsupported layer selection", file=sys.stderr)
        return 2

    levels = _iter_levels(args.levels)
    if not levels:
        print("ERR: invalid levels", file=sys.stderr)
        return 2

    tasks = []
    for layer in layers:
        spec = LAYERS[layer]
        ext = spec["ext"]
        for z in levels:
            if not (0 <= z <= 8):
                continue
            max_tiles = 1 << z
            for y in range(max_tiles):
                for x in range(max_tiles):
                    tasks.append((layer, z, x, y, ext))

    counts = {"HIT": 0, "MISS": 0, "ERR": 0}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(fetch_tile, args.base, layer, z, x, y, ext) for layer, z, x, y, ext in tasks]
        for future in concurrent.futures.as_completed(futures):
            status = future.result()
            counts[status if status in counts else "ERR"] += 1

    print(f"HIT={counts['HIT']} MISS={counts['MISS']} ERR={counts['ERR']}")
    return 0 if counts["ERR"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
