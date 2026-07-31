# -*- coding: utf-8 -*-
"""사용자 업로드 이미지 → Supabase Storage 공개 URL.
서버 디스크를 쓰지 않는다(디스크 폭증 방지)."""
import os, time, hashlib, mimetypes, urllib.request, json

SB_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or ""
BUCKET = os.environ.get("SUPABASE_BUCKET", "linklynk-media")
MAX = 8 * 1024 * 1024          # 8MB
OK_EXT = {"jpg", "jpeg", "png", "webp", "gif"}

def enabled():
    return bool(SB_URL and SB_KEY)

def upload(uid, filename, data):
    """returns {'ok':True,'url':...} or {'ok':False,'error':...}"""
    if not enabled():
        return {"ok": False, "error": "storage_not_configured"}
    if not data:
        return {"ok": False, "error": "empty"}
    if len(data) > MAX:
        return {"ok": False, "error": "too_large", "detail": "8MB 이하만 됩니다"}
    ext = (filename.rsplit(".", 1)[-1] or "").lower()
    if ext not in OK_EXT:
        return {"ok": False, "error": "bad_ext", "detail": "jpg/png/webp/gif만 됩니다"}
    h = hashlib.md5(data).hexdigest()[:16]
    key = "u%s/%d_%s.%s" % (uid, int(time.time()), h, ext)
    ct = mimetypes.guess_type("x." + ext)[0] or "application/octet-stream"
    url = "%s/storage/v1/object/%s/%s" % (SB_URL, BUCKET, key)
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", "Bearer " + SB_KEY)
    req.add_header("Content-Type", ct)
    req.add_header("x-upsert", "true")
    try:
        urllib.request.urlopen(req, timeout=60).read()
    except Exception as e:
        detail = ""
        try: detail = e.read().decode()[:200]
        except Exception: detail = str(e)[:150]
        return {"ok": False, "error": "upload_failed", "detail": detail}
    pub = "%s/storage/v1/object/public/%s/%s" % (SB_URL, BUCKET, key)
    return {"ok": True, "url": pub, "key": key}

def delete(key):
    if not enabled(): return False
    url = "%s/storage/v1/object/%s/%s" % (SB_URL, BUCKET, key)
    req = urllib.request.Request(url, method="DELETE")
    req.add_header("Authorization", "Bearer " + SB_KEY)
    try:
        urllib.request.urlopen(req, timeout=30); return True
    except Exception:
        return False
