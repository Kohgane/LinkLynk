1. Put a source video at `raw/<slug>.mp4`.
2. Run `python tools/cine_encode.py --in raw/<slug>.mp4 --slug <slug>`.
3. This writes `/static/fly/v2/cine/<slug>.mp4` and `<slug>.jpg` (portrait 720x1280).
4. Run `python tools/cine_manifest.py` to refresh `static/fly/v2/cine/manifest.json`.
5. Commit the updated manifest and JPG, but do not commit raw source videos.
