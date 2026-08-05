# -*- coding: utf-8 -*-
"""불씨(ember) — 둘이서 잇는 공동 스트릭. Supabase Storage를 KV로 사용(재배포 생존).
pair JSON: {code, a:{did,name}, b:{did,name}|None, streak, freeze,
            day: 'YYYY-MM-DD', a_done, b_done, a_mood, b_mood, last_complete}"""
import os, json, random, string, urllib.request, datetime, threading

SB_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or ""
BUCKET = os.environ.get("SUPABASE_BUCKET", "linklynk-media")
_cache = {}
_lock = threading.Lock()

def _kst_today():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")

def _yesterday(day):
    d = datetime.datetime.strptime(day, "%Y-%m-%d") - datetime.timedelta(days=1)
    return d.strftime("%Y-%m-%d")

def _sb(method, key, data=None):
    url = "%s/storage/v1/object/%s/ember/%s.json" % (SB_URL, BUCKET, key)
    if method == "GET":
        url = "%s/storage/v1/object/public/%s/ember/%s.json?t=%d" % (
            SB_URL, BUCKET, key, int(datetime.datetime.utcnow().timestamp()))
    req = urllib.request.Request(url, data=data, method=method)
    if method != "GET":
        req.add_header("Authorization", "Bearer " + SB_KEY)
        req.add_header("apikey", SB_KEY)
        req.add_header("Content-Type", "application/json")
        req.add_header("x-upsert", "true")
    return urllib.request.urlopen(req, timeout=12).read()

def load(code):
    code = (code or "").upper()
    with _lock:
        if code in _cache:
            return dict(_cache[code])
    if SB_URL and SB_KEY:
        try:
            p = json.loads(_sb("GET", code))
            with _lock:
                _cache[code] = p
            return dict(p)
        except Exception:
            return None
    return None

def save(p):
    with _lock:
        _cache[p["code"]] = dict(p)
    if SB_URL and SB_KEY:
        try:
            _sb("POST", p["code"], json.dumps(p, ensure_ascii=False).encode())
        except Exception:
            pass

def create(did, name, solo=False):
    code = "".join(random.choices(string.ascii_uppercase.replace("O", "").replace("I", "") + "23456789", k=6))
    b = {"did": "bot", "name": "불씨봇 🤖"} if solo else None
    p = {"code": code, "a": {"did": did, "name": name[:12]}, "b": b,
         "streak": 0, "freeze": 0, "day": _kst_today(),
         "a_done": False, "b_done": False, "a_mood": "", "b_mood": "",
         "last_complete": ""}
    if solo:
        p["b_done"] = True; p["b_mood"] = "🤖"; p["b_note"] = "오늘도 자동으로 지켰다"
    save(p)
    return p

def join(code, did, name):
    p = load(code)
    if not p:
        return None, "코드를 찾을 수 없어요"
    if p.get("b") and p["b"]["did"] != did and p["a"]["did"] != did:
        return None, "이미 두 명이 연결된 불씨예요"
    if p["a"]["did"] == did:
        return p, None
    if not p.get("b"):
        p["b"] = {"did": did, "name": name[:12]}
        save(p)
    return p, None

def _rollover(p):
    """날짜가 바뀌었으면 스트릭 정산: 어제 완성 못 했으면 프리즈 소모 또는 소멸."""
    today = _kst_today()
    if p["day"] == today:
        return p
    completed = p["a_done"] and p["b_done"]
    if not completed and p["streak"] > 0:
        # 하루 이상 공백: 어제까지가 p['day']였는지 확인
        gap_end = _yesterday(today)
        if p["day"] < gap_end or not completed:
            if p.get("freeze", 0) > 0 and p["day"] == gap_end:
                p["freeze"] -= 1        # 프리즈 1개로 하루 방어
            else:
                p["streak"] = 0
    p["day"] = today
    p["a_done"] = False; p["b_done"] = False
    if p.get("b") and p["b"].get("did") == "bot":
        p["b_done"] = True; p["b_mood"] = "🤖"; p["b_note"] = "오늘도 자동으로 지켰다"
    p["a_mood"] = ""; p["b_mood"] = ""
    p["a_note"] = ""; p["b_note"] = ""
    save(p)
    return p

def checkin(code, did, mood, note="", av=""):
    p = load(code)
    if not p:
        return None, "불씨를 찾을 수 없어요"
    p = _rollover(p)
    side = "a" if p["a"]["did"] == did else ("b" if p.get("b") and p["b"]["did"] == did else None)
    if not side:
        return None, "이 불씨의 멤버가 아니에요"
    p[side + "_done"] = True
    p[side + "_mood"] = (mood or "")[:4]
    p[side + "_note"] = (note or "")[:40]
    if av:
        p[side + "_av"] = av[:4]
    if p["a_done"] and p["b_done"] and p["last_complete"] != p["day"]:
        p["streak"] += 1
        p["last_complete"] = p["day"]
        # ★7일마다 프리즈 1개 보상 (최대 2)
        if p["streak"] % 7 == 0:
            p["freeze"] = min(p.get("freeze", 0) + 1, 2)
    save(p)
    return p, None

def state(code, did):
    p = load(code)
    if not p:
        return None
    p = _rollover(p)
    me, other = ("a", "b") if p["a"]["did"] == did else ("b", "a")
    if me == "b" and not p.get("b"):
        return None
    o = p.get(other) or {}
    return {"code": p["code"], "streak": p["streak"], "freeze": p.get("freeze", 0),
            "partner": o.get("name") or "", "connected": bool(p.get("b")),
            "my_done": p[me + "_done"], "partner_done": p[other + "_done"] if p.get(other) else False,
            "partner_mood": p[other + "_mood"] if p.get(other) else "",
            "partner_note": p.get(other + "_note", "") if p.get(other) else "",
            "my_note": p.get(me + "_note", ""),
            "partner_av": p.get(other + "_av", "") if p.get(other) else "",
            "my_av": p.get(me + "_av", ""),
            "packs": p.get("packs", ["daily"]),
            "custom": p.get("custom", []),
            "both_done": p["a_done"] and p["b_done"]}

def add_freeze(code):
    p = load(code)
    if not p:
        return None
    p["freeze"] = min(p.get("freeze", 0) + 1, 2)
    save(p)
    return p


def set_missions(code, packs, custom):
    p = load(code)
    if not p:
        return None
    p["packs"] = [str(x)[:12] for x in packs][:6] or ["daily"]
    p["custom"] = [str(x)[:60] for x in custom][:10]
    save(p)
    return p
