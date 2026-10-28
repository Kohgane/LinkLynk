#!/usr/bin/env python3
"""Generate true-360 dream skydomes with DiT360 (Insta360-Research/DiT360 Space) for entries in domes.json
that carry a "prompt" and no finished source. Needs HF_TOKEN (ZeroGPU quota); without it the step is skipped.
Writes tools/dream/src/<name>_dit360.webp so mkdome.py can build the dome (equirect, no capture loss)."""
import json, os, shutil, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); SRC = os.path.join(HERE, "src")
tok = os.environ.get("HF_TOKEN", "").strip()
if not tok: print("gen360: no HF_TOKEN, skipping"); sys.exit(0)
from gradio_client import Client
domes = json.load(open(os.path.join(HERE, "domes.json")))
todo = {n: s for n, s in domes.items() if s.get("prompt") and not os.path.exists(os.path.join(SRC, n + "_dit360.webp"))}
if not todo: print("gen360: nothing to do"); sys.exit(0)
c = Client("Insta360-Research/DiT360", hf_token=tok)
os.makedirs(SRC, exist_ok=True)
for n, s in todo.items():
    t0 = time.time()
    try:
        r = c.predict(prompt=s["prompt"], seed=float(s.get("seed", 7)), num_inference_steps=float(s.get("steps", 30)), api_name="/infer")
        path = r["path"] if isinstance(r, dict) else r
        shutil.copy(path, os.path.join(SRC, n + "_dit360.webp"))
        print("gen360", n, int(time.time() - t0), "s", flush=True)
    except Exception as e:
        print("gen360 failed", n, str(e)[:200], flush=True)
