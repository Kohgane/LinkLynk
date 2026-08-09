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


# ══════════ 도장깨기 (발자취 메커니즘: 자동 기록 + 시군구 수집) ══════════
_GEO = None
_SIDO = {"11": "서울", "21": "부산", "22": "대구", "23": "인천", "24": "광주",
         "25": "대전", "26": "울산", "29": "세종", "31": "경기", "32": "강원",
         "33": "충북", "34": "충남", "35": "전북", "36": "전남", "37": "경북",
         "38": "경남", "39": "제주"}


def _geo_load():
    """시군구 경계(251개) 지연 로드 + bbox 프리컴퓨트"""
    global _GEO
    if _GEO is None:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kr_sigungu_geo.json")
        feats = json.load(open(p, encoding="utf-8"))["features"]
        out = []
        for f in feats:
            g = f["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            rings = [pl[0] for pl in polys if pl]
            xs = [x for r in rings for x, y in r]
            ys = [y for r in rings for x, y in r]
            out.append({"code": f["properties"].get("code", ""),
                        "name": f["properties"].get("name", ""),
                        "bbox": (min(xs), min(ys), max(xs), max(ys)), "rings": rings})
        _GEO = out
    return _GEO


def _pip(lat, lng, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def region_of(lat, lng):
    for f in _geo_load():
        x0, y0, x1, y1 = f["bbox"]
        if not (x0 <= lng <= x1 and y0 <= lat <= y1):
            continue
        for ring in f["rings"]:
            if _pip(lat, lng, ring):
                sido = _SIDO.get(str(f["code"])[:2], "")
                return str(f["code"]), (sido + " " + f["name"]).strip()
    return "", ""


def _pg(method, path):
    req = urllib.request.Request(SB_URL + "/rest/v1/" + path, method=method.split(":")[0])
    req.add_header("apikey", SB_KEY)
    req.add_header("Authorization", "Bearer " + SB_KEY)
    return req


def stamp(did, name, lat, lng):
    """지도앱 여는 순간 자동 도장. 같은 곳(소수4자리)+같은 기기 12시간 내 중복 스킵."""
    la, ln = round(lat, 4), round(lng, 4)
    since = (datetime.datetime.utcnow() - datetime.timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        q = "gg_stamps?did=eq.%s&lat=eq.%s&lng=eq.%s&ts=gte.%s&select=id&limit=1" % (
            urllib.request.quote(did), la, ln, since)
        if json.loads(urllib.request.urlopen(_pg("GET", q), timeout=8).read() or b"[]"):
            return {"ok": True, "dup": True}
    except Exception:
        pass
    code, region = region_of(lat, lng)
    try:
        req = _pg("POST", "gg_stamps")
        req.add_header("Content-Type", "application/json")
        req.add_header("Prefer", "return=minimal")
        req.data = json.dumps({"did": did[:64], "name": (name or "")[:40], "lat": la, "lng": ln,
                               "region_code": code, "region": region}).encode()
        urllib.request.urlopen(req, timeout=8).read()
        return {"ok": True, "region": region}
    except Exception:
        return {"ok": False}


_TITLES = [(100, "👑 골든 스로너"), (40, "🛡 화장실 개척자"), (15, "🏇 순례자"),
           (5, "🧭 탐색가"), (1, "🚽 초행자"), (0, "🌱 새싹")]


def mystats(did):
    try:
        q = "gg_stamps?did=eq.%s&select=name,lat,lng,region,region_code,ts&order=ts.desc&limit=2000" % \
            urllib.request.quote(did)
        rows = json.loads(urllib.request.urlopen(_pg("GET", q), timeout=8).read() or b"[]")
    except Exception:
        rows = []
    places = {(r["lat"], r["lng"]) for r in rows}
    regions = {}
    for r in rows:
        if r.get("region_code"):
            regions[r["region_code"]] = r.get("region", "")
    n = len(rows)
    title = next(t for th, t in _TITLES if n >= th)
    return {"ok": True, "stamps": n, "places": len(places),
            "regions": sorted(set(regions.values())), "region_n": len(regions),
            "total_regions": 251, "title": title,
            "recent": [{"name": r.get("name") or "이름 없는 화장실", "region": r.get("region", ""),
                        "ts": (r.get("ts") or "")[:10]} for r in rows[:5]]}
