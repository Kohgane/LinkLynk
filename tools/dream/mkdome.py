#!/usr/bin/env python3
"""Build seamless 4096x2048 equirect skydomes for SWEF dream worlds from wide painterly source images.
usage: mkdome.py  (reads tools/dream/domes.json, writes static/fly/sky/<name>.jpg and <name>_4k.jpg)
Source images may be browser captures: a 'crop' box selects the painting inside the capture."""
import json, os
import numpy as np
from PIL import Image, ImageFilter, ImageOps
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SKY = os.path.join(ROOT, "static", "fly", "sky"); W, H = 4096, 2048
def load(spec):
    im = Image.open(os.path.join(HERE, "src", spec["file"])).convert("RGB")
    if "crop" in spec: im = im.crop(tuple(spec["crop"]))
    if "cut" in spec: im = im.crop(tuple(spec["cut"]))  # second crop in cropped coords (e.g. keep the half with the sun at one edge)
    return im
def xfade(parts, f=110):
    out = parts[0]
    for p in parts[1:]:
        f2 = min(f, out.width // 4, p.width // 4)
        a = np.asarray(out).astype(np.float32); b = np.asarray(p.resize((p.width, out.height))).astype(np.float32)
        w = np.linspace(0, 1, f2)[None, :, None]
        a[:, -f2:] = a[:, -f2:] * (1 - w) + b[:, :f2] * w
        out = Image.fromarray(np.concatenate([a, b[:, f2:]], axis=1).clip(0, 255).astype(np.uint8))
    return out
def wrapfade(im, f=110):
    a = np.asarray(im).astype(np.float32); w = np.linspace(0, 1, f)[None, :, None]
    a[:, -f:] = a[:, -f:] * (1 - w) + a[:, :f][:, ::-1] * w
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))
def dome(band, horizon_frac, out):
    band = band.resize((W, int(band.height * W / band.width)), Image.LANCZOS); bh = band.height
    top = 1024 - int(bh * horizon_frac)
    canvas = Image.new("RGB", (W, H))
    sky = band.crop((0, 0, W, max(8, int(bh * 0.12)))).resize((W, top), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    sky = Image.fromarray((np.asarray(sky).astype(np.float32) * np.linspace(0.45, 1.0, top)[:, None, None]).clip(0, 255).astype(np.uint8))
    canvas.paste(sky, (0, 0)); canvas.paste(band, (0, top))
    gb = H - (top + bh)
    ground = band.crop((0, bh - int(bh * 0.10), W, bh)).resize((W, gb), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    ground = Image.fromarray((np.asarray(ground).astype(np.float32) * np.linspace(1.0, 0.25, gb)[:, None, None]).clip(0, 255).astype(np.uint8))
    canvas.paste(ground, (0, top + bh))
    canvas = canvas.filter(ImageFilter.GaussianBlur(0.6))
    canvas.save(out + "_4k.jpg", quality=86)
    canvas.resize((2048, 1024), Image.LANCZOS).save(out + ".jpg", quality=85)
os.makedirs(SKY, exist_ok=True)
for name, spec in json.load(open(os.path.join(HERE, "domes.json"))).items():
    parts = []
    for p in spec["band"]:
        im = load(p)
        parts.append(im)
        if p.get("mirror", True): parts.append(ImageOps.mirror(im))
    band = wrapfade(xfade(parts))
    dome(band, spec.get("horizon", 0.45), os.path.join(SKY, name))
    print("dome", name, band.size)
