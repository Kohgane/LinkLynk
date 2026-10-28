#!/usr/bin/env python3
"""Render missing SWEF arrival clips from open data (Copernicus DEM + Sentinel-2 + Blue Marble) with headless Blender.
usage: batch.py [--max N] [--only slug,slug] [--work DIR]
Writes static/fly/v2/cine/<slug>.mp4 + <slug>.jpg and merges static/fly/v2/cine/manifest.json."""
import argparse, json, os, subprocess, sys, shutil, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CINE = os.path.join(ROOT, "static", "fly", "v2", "cine"); MAN = os.path.join(CINE, "manifest.json")
ap = argparse.ArgumentParser(); ap.add_argument("--max", type=int, default=3); ap.add_argument("--only", default=""); ap.add_argument("--work", default=os.path.join(HERE, "work"))
ap.add_argument("--fps", type=int, default=20); ap.add_argument("--dur", type=float, default=6.0); ap.add_argument("--samples", type=int, default=12); ap.add_argument("--res", type=int, default=540)
ap.add_argument("--reuse", action="store_true", help="reuse rendered frames in the work dir")
ap.add_argument("--push", action="store_true", help="git commit+push static/fly/v2/cine after every clip (CI)")
a = ap.parse_args()
os.makedirs(a.work, exist_ok=True); os.makedirs(CINE, exist_ok=True)
man = json.load(open(MAN)) if os.path.exists(MAN) else {"v": 1, "clips": {}}
dests = json.load(open(os.path.join(HERE, "dests.json")))
only = [s for s in a.only.split(",") if s]
todo = [d for d in dests if (d["slug"] in only if only else d["slug"] not in man["clips"])][: a.max]
print("todo", [d["slug"] for d in todo], flush=True)
def run(cmd, **kw):
    print("+", " ".join(cmd), flush=True); subprocess.run(cmd, check=True, cwd=a.work, **kw)
for d in todo:
    s = d["slug"]; t0 = time.time()
    if not os.path.exists(os.path.join(a.work, s, "tex.png")):
        run([sys.executable, os.path.join(HERE, "fetch_world.py"), s, str(d["lon"]), str(d["lat"]), "80", "1600", "6144"])
    if not os.path.exists(os.path.join(a.work, s + "_outer", "tex.png")):
        run([sys.executable, os.path.join(HERE, "fetch_world.py"), s + "_outer", str(d["lon"]), str(d["lat"]), "320", "900", "2048"])
    frames = os.path.join(a.work, s, "frames"); nf = round(a.fps * a.dur)
    if not (a.reuse and os.path.isdir(frames) and len(os.listdir(frames)) >= nf):
        shutil.rmtree(frames, ignore_errors=True)
        env = dict(os.environ, RES_W=str(a.res), SKY=os.path.join(ROOT, "static", "fly", "sky", "pano_4k.jpg"))
        run([sys.executable, "-I", os.path.join(HERE, "render_world.py"), s, str(d["h"]), str(d["r"]), str(d["p"]), str(a.fps), str(a.dur), str(a.samples)], env=env)
    path = json.load(open(os.path.join(a.work, s, "path.json")))
    mp4 = os.path.join(CINE, s + ".mp4"); jpg = os.path.join(CINE, s + ".jpg")
    run(["ffmpeg", "-y", "-v", "error", "-framerate", str(a.fps), "-i", os.path.join(frames, "f%04d.png"), "-an",
         "-vf", "scale=720:1280:flags=lanczos", "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-crf", "26", mp4])
    run(["ffmpeg", "-y", "-v", "error", "-i", mp4, "-frames:v", "1", "-q:v", "4", jpg])
    man["clips"][s] = {"mp4": "/fly/v2/cine/" + s + ".mp4", "poster": "/fly/v2/cine/" + s + ".jpg", "dur": a.dur, "fps": a.fps,
                       "endRange": round(path["endRange"]), "endPitch": path["endPitch"], "bytes": os.path.getsize(mp4), "src": "copernicus-dem+sentinel2+bluemarble", "built": time.strftime("%Y-%m-%d")}
    json.dump(man, open(MAN, "w"), indent=1, sort_keys=True)
    print("clip", s, os.path.getsize(mp4)//1024, "KB", int(time.time() - t0), "s", flush=True)
    if a.push:  # commit each clip as it lands so a cancelled run still keeps what it finished
        try:
            subprocess.run(["git", "add", "static/fly/v2/cine"], check=True, cwd=ROOT)
            subprocess.run(["git", "commit", "-q", "-m", f"cine: {s} (auto-rendered from open data)"], check=True, cwd=ROOT)
            subprocess.run(["git", "pull", "-q", "--rebase", "origin", "main"], check=True, cwd=ROOT)
            subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], check=True, cwd=ROOT)
            print("pushed", s, flush=True)
        except subprocess.CalledProcessError as e:
            print("push failed", s, e, flush=True)
print("done", len(todo))
