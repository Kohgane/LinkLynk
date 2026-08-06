# -*- coding: utf-8 -*-
"""급해! — 전국 화장실 근접검색 (OSM 스냅샷, 서버 메모리 상주)"""
import json, math, os, datetime, threading, urllib.request

_DATA = None
_REP = None
_rlock = threading.Lock()
SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
BUCKET = os.environ.get("SUPABASE_BUCKET", "linklynk")


def _sb(method, data=None):
    url = "%s/storage/v1/object/%s/gottago/reports.json" % (SB_URL, BUCKET)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + SB_KEY)
    req.add_header("apikey", SB_KEY)
    if method != "GET":
        req.add_header("Content-Type", "application/json")
        req.add_header("x-upsert", "true")
    return urllib.request.urlopen(req, timeout=12).read()


def _rep_load():
    global _REP
    if _REP is None:
        try:
            _REP = json.loads(_sb("GET"))
        except Exception:
            _REP = {"agg": {}, "new": []}
    return _REP


def _rep_save():
    try:
        _sb("POST", json.dumps(_REP, ensure_ascii=False).encode())
    except Exception:
        pass


def _key(lat, lng):
    return "%d_%d" % (round(lat * 1e4), round(lng * 1e4))


def report(lat, lng, kind, name=""):
    """kind: ok(있어요) | closed(잠김·없음) | safe(안심시설) | new(신규 제보)"""
    with _rlock:
        r = _rep_load()
        if kind == "new":
            if not (33 < lat < 39 and 124 < lng < 132):
                return False
            r["new"] = [x for x in r["new"] if _key(x["lat"], x["lng"]) != _key(lat, lng)]
            r["new"].append({"lat": round(lat, 6), "lng": round(lng, 6),
                             "name": (name or "제보된 화장실")[:30], "fee": 0, "h24": 0,
                             "access": "", "ty": "user",
                             "ts": datetime.datetime.utcnow().strftime("%m/%d")})
            r["new"] = r["new"][-2000:]
        else:
            a = r["agg"].setdefault(_key(lat, lng), {"ok": 0, "closed": 0, "safe": 0})
            if kind in a:
                a[kind] += 1
        _rep_save()
        return True


def open_status(t, now=None):
    """타입별 운영시간 휴리스틱 -> (code, label). code: open/maybe/closed"""
    now = now or (datetime.datetime.utcnow() + datetime.timedelta(hours=9))
    h, wd = now.hour + now.minute / 60.0, now.weekday()
    ty = t.get("ty", "pub")
    if t.get("h24"):
        return "open", "24시간"
    if ty in ("pub", "user"):
        return "open", "상시 개방(추정)"
    if ty == "rest":
        return "open", "24시간 휴게소"
    if ty in ("st", "bus"):
        return ("open", "운행시간 내") if 5 <= h < 24 else ("closed", "첫차 전(추정)")
    if ty == "gov":
        return ("open", "업무시간(추정)") if wd < 5 and 9 <= h < 18 else ("closed", "업무시간 외")
    if ty == "lib":
        if wd == 0:
            return "maybe", "휴관일 수 있음"
        return ("open", "개관시간(추정)") if 9 <= h < 22 else ("closed", "개관 전·후")
    if ty == "mart":
        wk = (now.day - 1) // 7 + 1
        if wd == 6 and wk in (2, 4):
            return "maybe", "의무휴업일 수 있음"
        return ("open", "영업중(추정)") if 10 <= h < 22 else ("closed", "영업시간 외")
    if ty == "hosp":
        return ("open", "진료시간(추정)") if wd < 5 and 9 <= h < 18 else ("maybe", "응급실 있으면 가능")
    if ty == "fuel":
        return ("open", "영업중(추정)") if 6 <= h < 24 else ("maybe", "24시 주유소면 가능")
    if ty == "cine":
        return ("open", "상영시간대") if 9 <= h < 25 else ("closed", "영업시간 외")
    if ty == "ff":
        return ("open", "영업중(추정)") if 8 <= h < 23 else ("maybe", "24시 매장이면 가능")
    if ty == "cafe":
        return ("open", "영업중(추정)") if 7 <= h < 23 else ("maybe", "24시 지점이면 가능")
    return "maybe", ""

def _load():
    global _DATA
    if _DATA is None:
        p = os.path.join(os.path.dirname(__file__), "toilets_kr.json")
        _DATA = json.load(open(p, encoding="utf-8"))
    return _DATA

def near(lat, lng, n=15):
    data = _load()
    coslat = math.cos(math.radians(lat))
    out = []
    for t in data:
        dy = (t["lat"] - lat) * 111320.0
        dx = (t["lng"] - lng) * 111320.0 * coslat
        d = math.hypot(dx, dy)
        if d < 30000:
            out.append((d, t))
    out.sort(key=lambda x: x[0])
    res = []
    for d, t in out[:n]:
        res.append({**t, "dist": int(d), "walk": max(1, int(d / 67))})
    return res


def near_v2(lat, lng, n=15):
    data = _load()
    rep = _rep_load()
    agg = rep.get("agg", {})
    coslat = math.cos(math.radians(lat))
    out = []
    for t in list(data) + rep.get("new", []):
        dy = (t["lat"] - lat) * 111320.0
        dx = (t["lng"] - lng) * 111320.0 * coslat
        d = math.hypot(dx, dy)
        if d < 30000:
            a = agg.get(_key(t["lat"], t["lng"]), {})
            w = d * (1.0 if t.get("ty") in ("cafe", "ff") else 0.85)
            if t.get("ty") == "user":
                w *= 0.9
            closed_n = a.get("closed", 0)
            if closed_n >= 3 and closed_n > a.get("ok", 0):
                w *= 2.2
            code, label = open_status(t)
            if code == "closed":
                w *= 1.5
            out.append((w, d, t, a, code, label))
    out.sort(key=lambda x: x[0])
    res = []
    for w, d, t, a, code, label in out[:n]:
        res.append({**t, "dist": int(d), "walk": max(1, int(d / 67)),
                    "open": code, "open_label": label,
                    "rep_ok": a.get("ok", 0), "rep_safe": a.get("safe", 0),
                    "rep_closed": a.get("closed", 0)})
    return res
