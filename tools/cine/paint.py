#!/usr/bin/env python3
"""Painterly pass for arrival-clip frames (offline, so it costs the phone nothing).
usage: paint.py <frames_dir> <out_dir> [strength 0..1]
Oil-paint brush look (cv2.xphoto) blended with the original to keep temporal stability."""
import sys, os, cv2, numpy as np
src, dst = sys.argv[1], sys.argv[2]; k = float(sys.argv[3]) if len(sys.argv) > 3 else 0.6
os.makedirs(dst, exist_ok=True)
names = sorted(n for n in os.listdir(src) if n.endswith(".png"))
prev = None
for n in names:
    im = cv2.imread(os.path.join(src, n))
    oil = cv2.xphoto.oilPainting(im, 5, 1)
    out = cv2.addWeighted(oil, k, im, 1 - k, 0)
    if prev is not None:  # light temporal smoothing against brush shimmer
        out = cv2.addWeighted(out, 0.75, prev, 0.25, 0)
    prev = out
    cv2.imwrite(os.path.join(dst, n), out)
print("painted", len(names))
